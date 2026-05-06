"""U5 integration smoke:
- Domain schema roundtrip
- Critic context helpers
- Consistency scan cursor serialization (moto-mocked DDB)
- Conflict rewrite attempts → frozen state machine
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from uuid import uuid4

import boto3
import pytest
from moto import mock_aws

from novelgen_types.critique import (
    ConflictItem,
    ConflictType,
    ConsistencyReport,
    CritiqueReport,
    Issue,
    IssueDimension,
    Severity,
    UserAction,
)


_TABLE = "novelgen_tenancy_u5_smoke"


def _setup_table() -> None:
    ddb = boto3.client("dynamodb", region_name="us-east-1")
    ddb.create_table(
        TableName=_TABLE,
        AttributeDefinitions=[
            {"AttributeName": "pk", "AttributeType": "S"},
            {"AttributeName": "sk", "AttributeType": "S"},
        ],
        KeySchema=[
            {"AttributeName": "pk", "KeyType": "HASH"},
            {"AttributeName": "sk", "KeyType": "RANGE"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )


@pytest.fixture()
def mock_ddb():
    with mock_aws():
        _setup_table()
        yield


def test_critique_report_domain_roundtrip() -> None:
    r = CritiqueReport(
        generation_id=uuid4(),
        team_id=uuid4(),
        chapter_idx=3,
        score=88,
        layer2_issues=[
            Issue(severity=Severity.WARN, dimension=IssueDimension.STYLE, message="tone")
        ],
        summary="ok",
        created_at=datetime.now(timezone.utc),
    )
    js = r.model_dump_json()
    back = CritiqueReport.model_validate_json(js)
    assert back.score == 88 and back.minimal is False


def test_six_conflict_types_are_stable() -> None:
    """Downstream UI depends on exact enum names — protect them."""
    assert {t.value for t in ConflictType} == {
        "character_state",
        "plot_hole",
        "timeline",
        "location",
        "relation",
        "worldbuilding",
    }


def test_scan_cursor_serializes_concurrent_scans(mock_ddb) -> None:
    from worker_consistency.scan_cursor import advance_scan, get_last_scan_to

    team_id, gid = uuid4(), uuid4()
    # First at 10 — accepted.
    r1 = asyncio.run(
        advance_scan(
            table=_TABLE, team_id=team_id, generation_id=gid,
            scan_to=10, region="us-east-1",
        )
    )
    assert r1.advanced is True
    # Duplicate at 10 — rejected.
    r2 = asyncio.run(
        advance_scan(
            table=_TABLE, team_id=team_id, generation_id=gid,
            scan_to=10, region="us-east-1",
        )
    )
    assert r2.advanced is False
    # Forward to 20 — accepted.
    r3 = asyncio.run(
        advance_scan(
            table=_TABLE, team_id=team_id, generation_id=gid,
            scan_to=20, region="us-east-1",
        )
    )
    assert r3.advanced is True
    assert asyncio.run(
        get_last_scan_to(
            table=_TABLE, team_id=team_id, generation_id=gid,
            region="us-east-1",
        )
    ) == 20


def test_conflict_rewrite_loop_freezes_on_third(mock_ddb) -> None:
    """Simulate 3 sequential rewrite attempts transitioning to frozen=True.

    This is a pure-domain state-machine test — it does not exercise the
    FastAPI route, just the ConflictItem invariant.
    """
    ci = ConflictItem(
        conflict_id=uuid4(),
        generation_id=uuid4(),
        team_id=uuid4(),
        scan_to=5,
        type=ConflictType.TIMELINE,
        chapter_refs=[3, 5],
        summary="time mismatch",
        evidence=[],
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    MAX = 3
    for attempt in range(1, MAX + 1):
        # User clicks Rewrite — simulate the repo logic invariants.
        assert not ci.frozen, f"should not be frozen at attempt {attempt}"
        ci = ci.model_copy(
            update={
                "rewrite_attempts": ci.rewrite_attempts + 1,
                "frozen": (ci.rewrite_attempts + 1 >= MAX),
                "user_action": UserAction.REWRITE_REQUESTED,
                "updated_at": datetime.now(timezone.utc),
            }
        )
    assert ci.rewrite_attempts == MAX
    assert ci.frozen is True
    assert ci.user_action == UserAction.REWRITE_REQUESTED


def test_consistency_report_minimal_flag() -> None:
    r = ConsistencyReport(
        generation_id=uuid4(),
        team_id=uuid4(),
        scan_from=1,
        scan_to=10,
        minimal=True,
        memory_unavailable=True,
        created_at=datetime.now(timezone.utc),
    )
    assert r.minimal and r.memory_unavailable and r.conflict_ids == []


def test_memory_unavailable_propagates_to_agent_report() -> None:
    """Regression: an agent invocation with memory_unavailable=True must preserve the flag."""
    from worker_consistency.agent import ConsistencyAgent
    from worker_consistency.context import ConsistencyContext

    ctx = ConsistencyContext(
        generation_id=uuid4(),
        team_id=uuid4(),
        scan_from=1,
        scan_to=10,
        chapters_text={i: f"c{i}" for i in range(1, 11)},
        memory_facts=[],
        character_snapshots=[],
        memory_unavailable=True,
        env="dev",
        request_id="r",
    )
    agent = ConsistencyAgent()
    report, conflicts = agent._assemble(
        [{"type": "plot_hole", "chapter_refs": [3], "summary": "x"}], ctx
    )
    assert report.memory_unavailable is True
    assert len(conflicts) == 1
