"""Validate every sub-agent schema is a valid JSON schema."""

from __future__ import annotations

import pytest
from jsonschema import Draft202012Validator
from worker_analysis.agents.chapter_all import _SCHEMA as CH_SCHEMA
from worker_analysis.agents.character_global import _SCHEMA as CHAR_SCHEMA
from worker_analysis.agents.classification import _SCHEMA as CLS_SCHEMA
from worker_analysis.agents.map_global import _SCHEMA as MAP_SCHEMA
from worker_analysis.agents.rough_read import _SCHEMA as RR_SCHEMA
from worker_analysis.agents.style import _SCHEMA as STY_SCHEMA


@pytest.mark.parametrize(
    "schema",
    [CH_SCHEMA, CHAR_SCHEMA, CLS_SCHEMA, MAP_SCHEMA, RR_SCHEMA, STY_SCHEMA],
)
def test_schema_is_valid_draft_2020(schema):
    Draft202012Validator.check_schema(schema)


def test_chapter_extraction_requires_all_four_arrays():
    required = CH_SCHEMA["required"]
    for key in ("character_updates", "map_updates", "events", "facts"):
        assert key in required


def test_style_schema_has_all_six_dimensions():
    props = STY_SCHEMA["properties"]
    for dim in ("tone", "pace", "detail_density", "dialogue_ratio", "emotion_intensity", "scope"):
        assert dim in props
        assert props[dim]["minimum"] == 0
        assert props[dim]["maximum"] == 100
