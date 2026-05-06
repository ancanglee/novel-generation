"""Pipeline test using mocked adapters."""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from worker_ingestion.pipeline import Pipeline, PipelineJob


@pytest.mark.asyncio
async def test_upload_pipeline_runs_end_to_end():
    team_id = uuid4()
    novel_id = uuid4()
    owner = uuid4()

    upload_content = ("# Intro\n\n" + ("word " * 500) + "\n\n## Part 1\n\n" + ("句子。" * 300) + "\n\n## Part 2\n\n" + ("句子。" * 300)).encode("utf-8")

    s3 = AsyncMock()
    s3.get_object = AsyncMock(return_value=upload_content)
    s3.put_object = AsyncMock(return_value="s3://bucket/key")

    ddb = AsyncMock()
    ddb.put = AsyncMock()
    ddb.update = AsyncMock()

    pool = AsyncMock()

    pipe = Pipeline(novels_bucket=s3, tenancy_table=ddb, browser_pool=pool)
    outcome = await pipe.run(
        PipelineJob(
            job_id="j1",
            team_id=team_id,
            novel_id=novel_id,
            owner_user_id=owner,
            kind="upload",
            mime_type="text/markdown",
            upload_s3_key=f"teams/{team_id}/uploads/tmp/x",
            title_hint="test",
        )
    )

    assert outcome.novel_id == novel_id
    assert outcome.chapter_count >= 1
    assert outcome.word_count > 0
    # Put raw + chapter files + update novel row
    assert s3.put_object.await_count >= 2
    assert ddb.update.await_count == 1
