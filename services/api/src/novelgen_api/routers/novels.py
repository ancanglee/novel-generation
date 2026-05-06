"""/api/v1/novels/* routes."""

from __future__ import annotations

from uuid import UUID, uuid4

from fastapi import APIRouter, Header, HTTPException, UploadFile, status
from novelgen_auth.principal import PrincipalDep
from novelgen_storage import build_team_pk
from novelgen_types.identity import Principal
from pydantic import BaseModel, HttpUrl

from novelgen_api.deps import tenancy_table
from novelgen_api.services.ingestion_service import (
    TitleExistsError,
    create_job_row,
    create_novel_row,
    find_existing_by_title,
    idempotency_lookup,
    idempotency_store,
    start_ingestion_execution,
    store_upload_content,
)

MAX_UPLOAD_BYTES = 200 * 1024 * 1024
SUPPORTED_MIME = {
    "text/plain",
    "text/markdown",
    "application/epub+zip",
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/html",
}

router = APIRouter(prefix="/api/v1/novels", tags=["novels"])


class JobRef(BaseModel):
    job_id: UUID
    novel_id: UUID
    status: str


class NovelSummary(BaseModel):
    novel_id: UUID
    title: str
    source_type: str
    status: str
    chapter_count: int
    word_count: int
    created_at: str


class DownloadRequest(BaseModel):
    title: str
    engines: list[str] | None = None


class DownloadConfirm(BaseModel):
    title: str
    source: str
    url: HttpUrl


class CrawlRequest(BaseModel):
    url: HttpUrl


@router.post("/upload", response_model=JobRef, status_code=status.HTTP_202_ACCEPTED)
async def upload_novel(
    file: UploadFile,
    title: str,
    principal: Principal = PrincipalDep,
    idempotency_key: str = Header(default="", alias="Idempotency-Key"),
    force: bool = False,
) -> JobRef:
    if file.content_type not in SUPPORTED_MIME:
        raise HTTPException(
            status_code=415,
            detail={"error": {"code": "VALIDATION_UNSUPPORTED_FORMAT", "mime": file.content_type}},
        )

    if existing := await idempotency_lookup(principal.team_id, idempotency_key):
        return JobRef(job_id=uuid4(), novel_id=existing, status="IDEMPOTENT")

    if not force and (conflict_id := await find_existing_by_title(principal.team_id, title)):
        raise TitleExistsError(conflict_id)

    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail={"error": {"code": "VALIDATION_FILE_TOO_LARGE", "limit_bytes": MAX_UPLOAD_BYTES}},
        )

    novel_id = uuid4()
    job_id = uuid4()
    suffix = (file.filename or "novel").rsplit(".", 1)[-1]
    upload_key = await store_upload_content(principal, content, suffix)

    payload = {
        "kind": "upload",
        "mime_type": file.content_type,
        "upload_s3_key": upload_key,
        "title_hint": title,
        "novel_id": str(novel_id),
    }
    await create_novel_row(
        principal, novel_id, title=title, source_type="upload", original_format=file.content_type
    )
    await create_job_row(principal, job_id, novel_id, payload)
    await start_ingestion_execution(principal, job_id, payload)
    await idempotency_store(principal.team_id, idempotency_key, novel_id)

    return JobRef(job_id=job_id, novel_id=novel_id, status="QUEUED")


@router.post("/download", response_model=JobRef, status_code=status.HTTP_202_ACCEPTED)
async def download_public_domain(
    body: DownloadRequest, principal: Principal = PrincipalDep
) -> JobRef:
    novel_id = uuid4()
    job_id = uuid4()
    payload = {
        "kind": "download",
        "search_query": body.title,
        "search_engines": body.engines or ["gutenberg", "ctext", "wikisource", "baidu", "bing"],
        "novel_id": str(novel_id),
        "title_hint": body.title,
    }
    await create_novel_row(principal, novel_id, title=body.title, source_type="public_domain")
    await create_job_row(principal, job_id, novel_id, payload)
    await start_ingestion_execution(principal, job_id, payload)
    return JobRef(job_id=job_id, novel_id=novel_id, status="QUEUED")


@router.post("/download/confirm", response_model=JobRef, status_code=status.HTTP_202_ACCEPTED)
async def confirm_download(
    body: DownloadConfirm, principal: Principal = PrincipalDep
) -> JobRef:
    novel_id = uuid4()
    job_id = uuid4()
    payload = {
        "kind": "crawl",
        "source_url": str(body.url),
        "source": body.source,
        "title_hint": body.title,
        "novel_id": str(novel_id),
    }
    await create_novel_row(
        principal,
        novel_id,
        title=body.title,
        source_type="search_engine" if body.source in ("baidu", "bing") else "public_domain",
        source_url=str(body.url),
    )
    await create_job_row(principal, job_id, novel_id, payload)
    await start_ingestion_execution(principal, job_id, payload)
    return JobRef(job_id=job_id, novel_id=novel_id, status="QUEUED")


@router.post("/crawl", response_model=JobRef, status_code=status.HTTP_202_ACCEPTED)
async def crawl_url(body: CrawlRequest, principal: Principal = PrincipalDep) -> JobRef:
    novel_id = uuid4()
    job_id = uuid4()
    payload = {
        "kind": "crawl",
        "source_url": str(body.url),
        "novel_id": str(novel_id),
    }
    await create_novel_row(
        principal,
        novel_id,
        title=str(body.url),
        source_type="crawl",
        source_url=str(body.url),
    )
    await create_job_row(principal, job_id, novel_id, payload)
    await start_ingestion_execution(principal, job_id, payload)
    return JobRef(job_id=job_id, novel_id=novel_id, status="QUEUED")


@router.get("", response_model=list[NovelSummary])
async def list_novels(principal: Principal = PrincipalDep) -> list[NovelSummary]:
    ddb = tenancy_table()
    items = await ddb.query_by_sk_prefix(principal.team_id, "NOVEL#", limit=100)
    return [
        NovelSummary(
            novel_id=UUID(row["novel_id"]),
            title=row.get("title", ""),
            source_type=row.get("source_type", ""),
            status=row.get("status", "unknown"),
            chapter_count=int(row.get("chapter_count", 0)),
            word_count=int(row.get("word_count", 0)),
            created_at=row.get("created_at", ""),
        )
        for row in items
    ]


@router.get("/{novel_id}", response_model=NovelSummary)
async def get_novel(novel_id: UUID, principal: Principal = PrincipalDep) -> NovelSummary:
    ddb = tenancy_table()
    row = await ddb.get(
        team_id=principal.team_id,
        pk=build_team_pk(principal.team_id),
        sk=f"NOVEL#{novel_id}",
    )
    if not row:
        raise HTTPException(status_code=404, detail={"error": {"code": "NOT_FOUND_NOVEL"}})
    return NovelSummary(
        novel_id=UUID(row["novel_id"]),
        title=row.get("title", ""),
        source_type=row.get("source_type", ""),
        status=row.get("status", "unknown"),
        chapter_count=int(row.get("chapter_count", 0)),
        word_count=int(row.get("word_count", 0)),
        created_at=row.get("created_at", ""),
    )


@router.delete("/{novel_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_novel(novel_id: UUID, principal: Principal = PrincipalDep) -> None:
    ddb = tenancy_table()
    await ddb.delete(
        team_id=principal.team_id,
        pk=build_team_pk(principal.team_id),
        sk=f"NOVEL#{novel_id}",
    )
