"""Validate U4 agent JSON schemas are Draft 2020-12 valid."""

from __future__ import annotations

import pytest
from jsonschema import Draft202012Validator

from worker_generation.agents.outline import _SCHEMA as OUTLINE_SCHEMA
from worker_generation.agents.outline_review import _SCHEMA as REVIEW_SCHEMA
from worker_generation.agents.self_critique import _SCHEMA as CRITIQUE_SCHEMA


@pytest.mark.parametrize("schema", [OUTLINE_SCHEMA, REVIEW_SCHEMA, CRITIQUE_SCHEMA])
def test_schema_valid(schema):
    Draft202012Validator.check_schema(schema)


def test_outline_has_required_fields():
    assert set(OUTLINE_SCHEMA["required"]) == {
        "main_plot", "world_summary", "character_table", "items"
    }


def test_critique_has_score_0_to_100():
    props = CRITIQUE_SCHEMA["properties"]
    assert props["score"]["minimum"] == 0
    assert props["score"]["maximum"] == 100
