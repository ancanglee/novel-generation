"""Ingestion pipeline: orchestrates fetch → parse → split → persist for one job."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from novelgen_browser_pool import BrowserPool
from novelgen_obs import emit_job_duration, get_logger
from novelgen_storage import DynamoDBAdapter, S3Adapter, build_s3_prefix, build_team_pk

from worker_ingestion.chapter_splitter import split as heuristic_split
from worker_ingestion.fetchers import fetch_with_downgrade
from worker_ingestion.fetchers.orchestrator import FetchResult
from worker_ingestion.llm_chapter_splitter import split_with_llm
from worker_ingestion.parsers import get_parser
from worker_ingestion.parsers.base import ParsedDocument
from worker_ingestion.parsers.registry import *  # noqa: F403
from worker_ingestion.url_normalizer import cache_key

log = get_logger("worker-ingestion")


@dataclass(frozen=True)
class PipelineJob:
    job_id: str
    team_id: UUID
    novel_id: UUID
    owner_user_id: UUID
    kind: str  # "upload" | "download" | "crawl"
    mime_type: str | None = None
    upload_s3_key: str | None = None
    source_url: str | None = None
    title_hint: str | None = None


@dataclass(frozen=True)
class PipelineOutcome:
    novel_id: UUID
    chapter_count: int
    word_count: int
    raw_s3_key: str


class Pipeline:
    """End-to-end ingestion pipeline. All external deps injected for testability."""

    def __init__(
        self,
        novels_bucket: S3Adapter,
        tenancy_table: DynamoDBAdapter,
        browser_pool: BrowserPool,
        heuristic_confidence_floor: float = 0.6,
    ) -> None:
        self._s3 = novels_bucket
        self._ddb = tenancy_table
        self._pool = browser_pool
        self._confidence_floor = heuristic_confidence_floor

    async def run(self, job: PipelineJob) -> PipelineOutcome:
        started = datetime.now(tz=UTC)
        try:
            parsed = await self._acquire(job)
            chapters = await self._split(parsed.markdown)
            outcome = await self._persist(job, parsed, chapters)
            return outcome
        finally:
            elapsed_ms = (datetime.now(tz=UTC) - started).total_seconds() * 1000
            emit_job_duration(job_type="ingestion", status="done", duration_ms=elapsed_ms)

    async def _acquire(self, job: PipelineJob) -> ParsedDocument:
        if job.kind == "upload":
            assert job.upload_s3_key and job.mime_type
            content = await self._s3.get_object(job.team_id, job.upload_s3_key)
            parser = get_parser(job.mime_type)
            return parser.parse(content, filename=job.title_hint)

        if job.kind in ("download", "crawl"):
            assert job.source_url
            fetched: FetchResult = await fetch_with_downgrade(
                job.source_url, job_id=job.job_id, pool=self._pool
            )
            html_bytes = fetched.html.encode("utf-8")
            await self._cache_crawl(job.team_id, job.source_url, html_bytes)
            parser = get_parser("text/html")
            return parser.parse(html_bytes)

        raise ValueError(f"unknown job kind: {job.kind}")

    async def _cache_crawl(self, team_id: UUID, url: str, html: bytes) -> None:
        key = f"{build_s3_prefix(team_id)}crawl-cache/{cache_key(url)}.html"
        try:
            await self._s3.put_object(team_id, key, html, content_type="text/html")
        except Exception as e:  # non-fatal
            log.warning("crawl cache write failed", extra={"error": str(e), "key": key})

    async def _split(self, markdown: str):
        heuristic = heuristic_split(markdown, confidence_floor=self._confidence_floor)
        if heuristic and heuristic[0].confidence >= self._confidence_floor:
            return heuristic
        log.info("heuristic confidence low; invoking LLM splitter")
        return await split_with_llm(markdown)

    async def _persist(
        self, job: PipelineJob, parsed: ParsedDocument, chapters
    ) -> PipelineOutcome:
        raw_key = f"{build_s3_prefix(job.team_id)}novels/{job.novel_id}/raw.md"
        await self._s3.put_object(
            job.team_id, raw_key, parsed.markdown.encode("utf-8"), content_type="text/markdown"
        )

        total_words = 0
        for ch in chapters:
            chapter_key = (
                f"{build_s3_prefix(job.team_id)}novels/{job.novel_id}/chapters/{ch.idx:05d}.md"
            )
            await self._s3.put_object(
                job.team_id,
                chapter_key,
                ch.content.encode("utf-8"),
                content_type="text/markdown",
            )
            await self._ddb.put(
                job.team_id,
                {
                    "pk": build_team_pk(job.team_id),
                    "sk": f"CHAPTER#{job.novel_id}#{ch.idx:05d}",
                    "novel_id": str(job.novel_id),
                    "chapter_idx": ch.idx,
                    "title": ch.title,
                    "word_count": len(ch.content),
                    "s3_key": chapter_key,
                    "heading_level": ch.heading_level,
                    "confidence": ch.confidence,
                },
            )
            total_words += len(ch.content)

        sha = hashlib.sha256(parsed.markdown.encode("utf-8")).hexdigest()
        now = datetime.now(tz=UTC).isoformat()
        await self._ddb.update(
            team_id=job.team_id,
            pk=build_team_pk(job.team_id),
            sk=f"NOVEL#{job.novel_id}",
            update_expression=(
                "SET #s = :st, chapter_count = :cc, word_count = :wc, "
                "raw_s3_key = :rk, content_sha256 = :sha, updated_at = :u"
            ),
            expression_names={"#s": "status"},
            expression_values={
                ":st": "ingested",
                ":cc": len(chapters),
                ":wc": total_words,
                ":rk": raw_key,
                ":sha": sha,
                ":u": now,
            },
        )

        return PipelineOutcome(
            novel_id=job.novel_id,
            chapter_count=len(chapters),
            word_count=total_words,
            raw_s3_key=raw_key,
        )
