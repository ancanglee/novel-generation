"""U1 smoke test: basic adapter wiring (no real AWS calls required)."""

from __future__ import annotations

from uuid import uuid4

from novelgen_types.config import DEFAULT_MODEL_MAPPING, ModelStage
from novelgen_types.fact import FactType, build_fact_key
from novelgen_types.job import JobStatus, is_valid_transition


def test_default_model_mapping_covers_all_stages():
    for stage in ModelStage:
        assert stage in DEFAULT_MODEL_MAPPING, f"stage {stage} missing in default model mapping"
        entry = DEFAULT_MODEL_MAPPING[stage]
        assert entry.model_id.startswith("anthropic.claude-"), entry.model_id


def test_fact_key_deterministic():
    k1 = build_fact_key(FactType.CHARACTER_SNAPSHOT, name="主角", chapter=1)
    k2 = build_fact_key(FactType.CHARACTER_SNAPSHOT, name="主角", chapter=1)
    assert k1 == k2


def test_fact_key_unique_per_chapter():
    k1 = build_fact_key(FactType.CHARACTER_SNAPSHOT, name="主角", chapter=1)
    k2 = build_fact_key(FactType.CHARACTER_SNAPSHOT, name="主角", chapter=2)
    assert k1 != k2


def test_job_transition_full_matrix():
    for s in JobStatus:
        for t in JobStatus:
            result = is_valid_transition(s, t)
            assert isinstance(result, bool)


def test_style_fact_key_needs_novel():
    novel_id = uuid4()
    key = build_fact_key(FactType.STYLE_VECTOR, novel_id=novel_id)
    assert str(novel_id) in key
