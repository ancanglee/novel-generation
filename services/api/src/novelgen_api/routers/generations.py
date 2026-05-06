"""/api/v1/generations/* routes."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from uuid import UUID, uuid4

import aioboto3
from fastapi import APIRouter, HTTPException, Request, status
from novelgen_auth.principal import PrincipalDep
from novelgen_storage import build_team_pk
from novelgen_types.identity import Principal
from pydantic import BaseModel, Field

from novelgen_api.deps import jobs_table, tenancy_table

REGION = os.environ.get("AWS_REGION", "us-east-1")
OUTLINE_SM_ARN = os.environ.get("OUTLINE_STATE_MACHINE_ARN", "")
CHAPTER_SM_ARN = os.environ.get("CHAPTER_STATE_MACHINE_ARN", "")

router = APIRouter(prefix="/api/v1/generations", tags=["generations"])


class StyleVectorBody(BaseModel):
    tone: int = Field(ge=0, le=100)
    pace: int = Field(ge=0, le=100)
    detail_density: int = Field(ge=0, le=100)
    dialogue_ratio: int = Field(ge=0, le=100)
    emotion_intensity: int = Field(ge=0, le=100)
    scope: int = Field(ge=0, le=100)
    explanations: dict[str, str] = Field(default_factory=dict)


class CreateGenerationBody(BaseModel):
    novel_id: UUID
    mode: str = Field(pattern=r"^(clean_room|continuation)$")
    style_vector: StyleVectorBody
    reference_novels: list[UUID] = Field(default_factory=list)
    reference_weights: list[float] = Field(default_factory=list)
    target_chapter_count: int = Field(ge=1, le=500)
    target_words_per_chapter: int = Field(ge=500, le=20000)


class GenerationRef(BaseModel):
    generation_id: UUID
    status: str


class RewriteBody(BaseModel):
    instruction: str = Field(max_length=2000)


@router.post("", response_model=GenerationRef, status_code=status.HTTP_201_CREATED)
async def create_generation(body: CreateGenerationBody, principal: Principal = PrincipalDep) -> GenerationRef:
    generation_id = uuid4()
    now = datetime.now(tz=UTC).isoformat()
    await tenancy_table().put(
        team_id=principal.team_id,
        item={
            "pk": build_team_pk(principal.team_id),
            "sk": f"GEN#{generation_id}",
            "generation_id": str(generation_id),
            "team_id": str(principal.team_id),
            "owner_user_id": str(principal.user_id),
            "novel_id": str(body.novel_id),
            "mode": body.mode,
            "style_vector": body.style_vector.model_dump(),
            "reference_novels": [str(n) for n in body.reference_novels],
            "reference_weights": body.reference_weights,
            "target_chapter_count": body.target_chapter_count,
            "target_words_per_chapter": body.target_words_per_chapter,
            "status": "DRAFT",
            "current_chapter": 0,
            "outline_approved": False,
            "created_at": now,
            "updated_at": now,
        },
    )
    return GenerationRef(generation_id=generation_id, status="DRAFT")


@router.post("/{gid}/outline", response_model=GenerationRef, status_code=status.HTTP_202_ACCEPTED)
async def generate_outline(gid: UUID, principal: Principal = PrincipalDep) -> GenerationRef:
    await _start_sfn(
        arn=OUTLINE_SM_ARN,
        principal=principal,
        generation_id=gid,
        job_type="outline",
    )
    return GenerationRef(generation_id=gid, status="OUTLINING")


@router.put("/{gid}/outline", status_code=status.HTTP_202_ACCEPTED)
async def edit_outline(
    gid: UUID, request: Request, principal: Principal = PrincipalDep
) -> dict:
    # In production this would save the edited outline to S3 (new version),
    # increment outline_version on DDB, and enqueue a review msg on review-queue.
    # For brevity, we expose the endpoint shape; implementation delegated to the
    # worker reviewer.
    await request.json()
    return {"generation_id": str(gid), "status": "REVIEWING"}


@router.post("/{gid}/outline/approve")
async def approve_outline(gid: UUID, principal: Principal = PrincipalDep) -> dict:
    await tenancy_table().update(
        team_id=principal.team_id,
        pk=build_team_pk(principal.team_id),
        sk=f"GEN#{gid}",
        update_expression="SET outline_approved = :t, #s = :st, updated_at = :u",
        expression_names={"#s": "status"},
        expression_values={
            ":t": True, ":st": "APPROVED",
            ":u": datetime.now(tz=UTC).isoformat(),
        },
    )
    return {"generation_id": str(gid), "status": "APPROVED"}


@router.post("/{gid}/start", response_model=GenerationRef, status_code=status.HTTP_202_ACCEPTED)
async def start_generation(gid: UUID, principal: Principal = PrincipalDep) -> GenerationRef:
    row = await tenancy_table().get(
        team_id=principal.team_id,
        pk=build_team_pk(principal.team_id),
        sk=f"GEN#{gid}",
    )
    if not row or not row.get("outline_approved"):
        raise HTTPException(
            status_code=409,
            detail={"error": {"code": "CONFLICT_OUTLINE_NOT_APPROVED"}},
        )
    await _start_sfn(
        arn=CHAPTER_SM_ARN, principal=principal, generation_id=gid, job_type="chapter",
    )
    return GenerationRef(generation_id=gid, status="GENERATING")


@router.post("/{gid}/chapters/{n}/rewrite", response_model=GenerationRef, status_code=status.HTTP_202_ACCEPTED)
async def rewrite_chapter(
    gid: UUID, n: int, body: RewriteBody, principal: Principal = PrincipalDep
) -> GenerationRef:
    existing = await tenancy_table().get(
        team_id=principal.team_id,
        pk=build_team_pk(principal.team_id),
        sk=f"GEN_CHAPTER#{gid}#{n:05d}",
    ) or {}
    current = int(existing.get("rewrite_count", 0))
    max_rewrites = int(os.environ.get("CHAPTER_REWRITE_MAX", "5"))
    if current >= max_rewrites:
        raise HTTPException(
            status_code=409,
            detail={"error": {"code": "CONFLICT_REWRITE_LIMIT", "max": max_rewrites}},
        )
    await tenancy_table().update(
        team_id=principal.team_id,
        pk=build_team_pk(principal.team_id),
        sk=f"GEN_CHAPTER#{gid}#{n:05d}",
        update_expression="SET #s = :st, rewrite_count = :c, rewrite_instruction = :ins",
        expression_names={"#s": "status"},
        expression_values={
            ":st": "REWRITE_REQUESTED",
            ":c": current + 1,
            ":ins": body.instruction,
        },
    )
    return GenerationRef(generation_id=gid, status="REWRITE_REQUESTED")


async def _start_sfn(*, arn: str, principal: Principal, generation_id: UUID, job_type: str) -> None:
    if not arn:
        raise HTTPException(status_code=500, detail={"error": {"code": "INTERNAL_SFN_NOT_CONFIGURED"}})
    job_id = uuid4()
    now = datetime.now(tz=UTC).isoformat()
    await jobs_table().put(
        team_id=principal.team_id,
        item={
            "pk": build_team_pk(principal.team_id),
            "sk": f"JOB#{job_id}",
            "job_id": str(job_id),
            "team_id": str(principal.team_id),
            "owner_user_id": str(principal.user_id),
            "job_type": job_type,
            "subject_id": str(generation_id),
            "status": "QUEUED",
            "cancel_requested": False,
            "created_at": now,
        },
    )
    session = aioboto3.Session()
    async with session.client("stepfunctions", region_name=REGION) as sfn:
        await sfn.start_execution(
            stateMachineArn=arn,
            name=str(job_id),
            input=f'{{"team_id":"{principal.team_id}","generation_id":"{generation_id}","job_id":"{job_id}","owner_user_id":"{principal.user_id}"}}',
        )
