"""Verify MemoryFacade is abstract and cannot be instantiated directly."""

from __future__ import annotations

import pytest
from novelgen_memory.facade import MemoryFacade


def test_cannot_instantiate_abstract_facade() -> None:
    with pytest.raises(TypeError):
        MemoryFacade()  # type: ignore[abstract]
