"""End-to-end scan pipeline."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from jobradar.classify import enrich, should_keep
from jobradar.db import Database
from jobradar.dedupe import find_duplicate
from jobradar.director import enqueue as director_enqueue
from jobradar.models import JobRecord, is_bad_url
from jobradar.notify import Notifier, within_notify_window
from jobradar.scout import ScoutResult, scout_all
from jobradar.sources import Source

log = logging.getLogger("jobradar.pipeline")


@dataclass
class PipelineStats:
    fetched: int = 0
    kept: int = 0
    skipped_bad_url: int = 0
    new: int = 0
    notified: int = 0
    alerted: int = 0
    alert_cap_hit: bool = False
    alerts_paused: int = 0
    cap_deferred: int = 0
    seeded: int = 0
    source_errors: list[str] = field(default_factory=list)
    seed_mode: bool = False


@dataclass
class RefreshStats:
    scanned: int = 0
    matched: int = 0
    rewritten: int = 0
    skipped: int = 0
    source_errors: list[str] = field(default_factory=list)


def run_scan(
    db: Database | None = None,
    sources: list[Source] | None = None,
    *,
    alert_all: bool = False,
) -> PipelineStats:
    db = db or Database()
    notifier = Notifier(db=db)
    stats = PipelineStats()
    was_empty = db.count_jobs() == 0
    stats.seed_mode = was_empty and not alert_all
    results: list[ScoutResult] = scout_all(db, sources=sources)
    seen_in_pass: list[JobRecord] = []
    from jobradar.notify import max_alerts_per_scan

    alert_cap = max_alerts_per_scan()

    for result in results:
        if result.error:
            stats.source_errors.append(f"{result.source}: {result.error}")
            continue
        if result.not_modified:
            continue
        for job in result.jobs:
            stats.fetched += 1
            if not should_keep(job):
                continue
            job = enrich(job)
            stats.kept += 1
            if is_bad_url(job.url):
                stats.skipped_bad_url += 1
                log.debug("skipping job with bad URL: %s | %s", job.company, job.title)
                continue
            dup = find_duplicate(job, seen_in_pass)
            if dup is not None:
                job.canonical_key = dup.canonical_key
                job.sources = list(dict.fromkeys([*dup.sources, *job.sources]))
            stored, is_new = db.upsert_job(job)
            seen_in_pass.append(stored)
            if is_new:
                stats.new += 1
            if stats.seed_mode:
                if is_new:
                    stats.seeded += 1
                continue
            if stored.is_closed:
                continue
            if is_new and within_notify_window(stored):
                from jobradar import notion as notion_mod
                from jobradar.notify import should_send_alerts, alerts_enabled

                # Check if alerts are enabled at all (not just quality gates)
                alerts_on = alerts_enabled()
                
                # Check if this job passes quality gates
                should_alert = should_send_alerts(stored)
                
                # Track reason for deferral
                defer_reason = None
                record_notification = True
                
                if not alerts_on:
                    # Alerts paused: don't record notification, allow retry later
                    record_notification = False
                    defer_reason = "alerts_paused"
                    stats.alerts_paused += 1
                elif should_alert and alert_cap and stats.alerted >= alert_cap:
                    # Cap hit: don't record notification, allow retry later
                    should_alert = False
                    record_notification = False
                    defer_reason = "cap_deferred"
                    stats.alert_cap_hit = True
                    stats.cap_deferred += 1
                elif not should_alert:
                    # Quality block (outside window, bad URL, etc): record as usual
                    # These are permanent blocks, not deferrals
                    pass
                
                # Notify: silent if not should_alert, record only if not deferred
                if notifier.notify(stored, silent=not should_alert, record_as_notified=record_notification):
                    stats.notified += 1
                    if should_alert:
                        stats.alerted += 1
                        try:
                            director_enqueue(stored, db=db)
                        except Exception as exc:
                            log.warning("director enqueue failed: %s", exc)
                        try:
                            notion_mod.upsert_job(stored, db=db, status=notion_mod.STATUS_BACKLOG)
                        except Exception as exc:
                            log.warning("notion upsert failed: %s", exc)
                    elif defer_reason:
                        log.debug("Job deferred (%s): %s", defer_reason, stored.canonical_key)
    return stats


def refresh_jobs(
    db: Database | None = None,
    sources: list[Source] | None = None,
) -> RefreshStats:
    """Silent job field refresh: re-scout sources, update existing jobs, never notify."""
    db = db or Database()
    stats = RefreshStats()
    results: list[ScoutResult] = scout_all(db, sources=sources)
    seen_in_pass: list[JobRecord] = []

    for result in results:
        if result.error:
            stats.source_errors.append(f"{result.source}: {result.error}")
            continue
        if result.not_modified:
            continue
        for job in result.jobs:
            stats.scanned += 1
            if not should_keep(job):
                stats.skipped += 1
                continue
            job = enrich(job)
            dup = find_duplicate(job, seen_in_pass)
            if dup is not None:
                job.canonical_key = dup.canonical_key
                job.sources = list(dict.fromkeys([*dup.sources, *job.sources]))
            
            existing_job = db.get_job(job.canonical_key)
            if existing_job is None:
                stats.skipped += 1
                continue
            
            stats.matched += 1
            
            needs_rewrite = (
                existing_job.company != job.company
                or existing_job.title != job.title
                or existing_job.location != job.location
                or existing_job.url != job.url
            )
            
            if needs_rewrite:
                stored, _ = db.upsert_job(job)
                stats.rewritten += 1
                seen_in_pass.append(stored)
            else:
                seen_in_pass.append(existing_job)
    
    return stats
