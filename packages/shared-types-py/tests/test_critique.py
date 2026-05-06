"""Tests for U5 Critic & Consistency models."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from novelgen_types.critique import (
    ConflictItem,
    ConflictType,
    ConsistencyReport,
    CritiqueReport,
    CrossChapterConcern,
    Issue,
    IssueDimension,
    Severity,
    UserAction,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def test_critique_report_roundtrip() -> None:
    gid = uuid4()
    tid = uuid4()
    r = CritiqueReport(
        generation_id=gid,
        team_id=tid,
        chapter_idx=5,
        score=82,
        layer1_confirmed=["节奏紧凑"],
        layer1_overridden=["自检说风格漂移实际未漂移"],
        layer2_issues=[
            Issue(severity=Severity.WARN, dimension=IssueDimension.PLOT, message="伏笔回收不充分")
        ],
        cross_chapter_concerns=[
            CrossChapterConcern(chapter_refs=[3, 4, 5], message="角色动机线与第3章冲突")
        ],
        summary="整体节奏良好",
        created_at=_now(),
    )
    dumped = r.model_dump_json()
    loaded = CritiqueReport.model_validate_json(dumped)
    assert loaded.score == 82
    assert loaded.layer2_issues[0].dimension == IssueDimension.PLOT


def test_critique_report_score_bounds() -> None:
    with pytest.raises(ValidationError):
        CritiqueReport(
            generation_id=uuid4(),
            team_id=uuid4(),
            chapter_idx=1,
            score=101,  # out of range
            created_at=_now(),
        )


def test_critique_report_minimal_flag() -> None:
    r = CritiqueReport(
        generation_id=uuid4(),
        team_id=uuid4(),
        chapter_idx=1,
        score=0,
        minimal=True,
        summary="critic_failed",
        created_at=_now(),
    )
    assert r.minimal is True


def test_conflict_item_defaults_and_enums() -> None:
    ci = ConflictItem(
        conflict_id=uuid4(),
        generation_id=uuid4(),
        team_id=uuid4(),
        scan_to=10,
        type=ConflictType.TIMELINE,
        chapter_refs=[3, 7],
        summary="时间线矛盾：第3章冬天第7章同人物仍穿夏装",
        evidence=["第3章: ...下雪...", "第7章: ...短袖..."],
        created_at=_now(),
        updated_at=_now(),
    )
    assert ci.rewrite_attempts == 0
    assert ci.frozen is False
    assert ci.user_action == UserAction.OPEN


def test_conflict_item_chapter_refs_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        ConflictItem(
            conflict_id=uuid4(),
            generation_id=uuid4(),
            team_id=uuid4(),
            scan_to=5,
            type=ConflictType.PLOT_HOLE,
            chapter_refs=[0, 3],  # 0 not positive
            summary="x",
            created_at=_now(),
            updated_at=_now(),
        )


def test_conflict_item_all_six_types() -> None:
    """Sanity: 6 ConflictType values are present."""
    assert {t.value for t in ConflictType} == {
        "character_state",
        "plot_hole",
        "timeline",
        "location",
        "relation",
        "worldbuilding",
    }


def test_consistency_report_scan_to_ge_from() -> None:
    with pytest.raises(ValidationError):
        ConsistencyReport(
            generation_id=uuid4(),
            team_id=uuid4(),
            scan_from=10,
            scan_to=5,  # < scan_from
            created_at=_now(),
        )


def test_consistency_report_memory_unavailable_flag() -> None:
    r = ConsistencyReport(
        generation_id=uuid4(),
        team_id=uuid4(),
        scan_from=1,
        scan_to=10,
        memory_unavailable=True,
        created_at=_now(),
    )
    assert r.memory_unavailable is True
    assert r.conflict_ids == []


def test_issue_extra_forbidden() -> None:
    with pytest.raises(ValidationError):
        Issue.model_validate(
            {
                "severity": "warn",
                "dimension": "plot",
                "message": "x",
                "unknown_field": "boom",
            }
        )
