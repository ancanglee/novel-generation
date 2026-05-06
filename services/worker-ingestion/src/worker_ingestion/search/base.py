"""Search source protocol + result model."""

from __future__ import annotations

from enum import Enum
from typing import Protocol

from pydantic import BaseModel


class SearchSourceId(str, Enum):
    GUTENBERG = "gutenberg"
    CTEXT = "ctext"
    WIKISOURCE = "wikisource"
    BAIDU = "baidu"
    BING = "bing"


class SearchResult(BaseModel):
    source: SearchSourceId
    title: str
    author: str | None = None
    url: str
    format_hint: str = "html"
    language: str = "zh"
    snippet: str = ""
    copyright_warning: bool = False


class SearchSource(Protocol):
    source_id: SearchSourceId

    async def search(self, query: str, limit: int = 10) -> list[SearchResult]: ...
