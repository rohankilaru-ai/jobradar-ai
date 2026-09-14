"""End-to-end scan pipeline."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from jobradar.classify import enrich, should_keep
from jobradar.db import Database
from jobradar.dedupe import find_duplicate
from jobradar.director import enqueue as director_enqueue
from jobradar.models import JobRecord
from jobradar.notify import Notifier
from jobradar.scout import ScoutResult, scout_all
from jobradar.sources import Source

log = logging.getLogger("jobradar.pipeline")


@dataclass
class PipelineStats:
    fetched: int = 0
    kept: int = 0
    new: int = 0
    notified: int = 0
    seeded: int = 0
    source_errors: list[str] = field(default_factory=list)
    seed_mode: bool = False


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
            if is_new:
                if notifier.notify(stored):
                    stats.notified += 1
                    try:
                        director_enqueue(stored, db=db)
                    except Exception as exc:
                        log.warning("director enqueue failed: %s", exc)
                    try:
                        from jobradar import notion as notion_mod

                        notion_mod.upsert_job(stored, db=db, status="Seen")
                    except Exception as exc:
                        log.warning("notion upsert failed: %s", exc)
    return stats
