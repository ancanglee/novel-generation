"""Plain-text parser with automatic encoding detection."""

from __future__ import annotations

import chardet

from worker_ingestion.parsers.base import ParsedDocument, ParserError, finalize, register

# 中文测试小说通常是 UTF-8 / GB18030 / GBK / Big5；先按常见候选顺序硬试一遍，
# 只有全部失败时才回落到 chardet（在短文本上猜测不稳定）。
_PREFERRED_ENCODINGS = ("utf-8-sig", "utf-8", "gb18030", "gbk", "big5", "shift_jis")


def _looks_ok(text: str) -> bool:
    # 解码后若含大量 U+FFFD 替换符，视为失败。
    if not text:
        return False
    replacement_ratio = text.count("\ufffd") / max(len(text), 1)
    return replacement_ratio < 0.05


def _decode(content: bytes) -> str:
    for enc in _PREFERRED_ENCODINGS:
        try:
            text = content.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
        if _looks_ok(text):
            return text
    # Fallback：chardet 猜测
    detection = chardet.detect(content) or {}
    encoding = detection.get("encoding") or "utf-8"
    try:
        return content.decode(encoding, errors="replace")
    except LookupError:
        return content.decode("utf-8", errors="replace")


class TxtParser:
    mime_types = ("text/plain",)

    def parse(self, content: bytes, filename: str | None = None) -> ParsedDocument:
        if not content:
            raise ParserError("empty file")
        text = _decode(content)
        title = filename.rsplit(".", 1)[0] if filename else None
        return finalize(text, title=title)


register(TxtParser())
