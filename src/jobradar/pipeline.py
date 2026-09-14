"""End-to-end scan pipeline."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from jobradar.classify import enrich, should_keep
from jobradar.db import Database
from jobradar.dedupe import find_duplicate
from jobradar.models import JobRecord
from jobradar.notify import MockNotifier
from jobradar.grok import post_job
from jobradar.scout import ScoutResult, scout_all
from jobradar.sources import Source

log = logging.getLogger("jobradar.pipeline")


@dataclass
class PipelineStats:
    fetched: int = 0
    kept: int = 0
    new: int = 0
    notified: int = 0
    source_errors: list[str] = field(default_factory=list)


def run_scan(db: Database | None = None, sources: list[Source] | None = None) -> PipelineStats:
    db = db or Database()
    notifier = MockNotifier(db=db)
    stats = PipelineStats()
    results: list[ScoutResult] = scout_all(db, sources=sources)
    # load recent jobs for fuzzy dedupe within this pass
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
                # merge source onto existing key
                job.canonical_key = dup.canonical_key
                job.sources = list(dict.fromkeys([*dup.sources, *job.sources]))
            stored, is_new = db.upsert_job(job)
            seen_in_pass.append(stored)
            if is_new:
                stats.new += 1
                if notifier.notify(stored):
                    stats.notified += 1
                    try:
                        post_job(stored)
                    except Exception:
                        log.exception("grok post failed (ignored)")
            else:
                # still never notify twice
                if not db.was_notified(stored.canonical_key):
                    if notifier.notify(stored):
                        stats.notified += 1
                        try:
                            post_job(stored)
                        except Exception:
                            log.exception("grok post failed (ignored)")
    return stats
