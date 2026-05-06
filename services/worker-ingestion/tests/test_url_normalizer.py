"""URL normalizer / cache key tests."""

from __future__ import annotations

from worker_ingestion.url_normalizer import cache_key, normalize_url


def test_strips_tracking_params():
    raw = "https://example.com/post?utm_source=x&utm_medium=y&id=42&ref=z"
    norm = normalize_url(raw)
    assert "utm_" not in norm
    assert "ref=" not in norm
    assert "id=42" in norm


def test_normalizes_host_case_and_strips_fragment():
    raw = "HTTPS://Example.COM/a#section"
    norm = normalize_url(raw)
    assert norm.startswith("https://example.com/a")
    assert "#" not in norm


def test_query_key_order_deterministic():
    a = cache_key("https://x.com/p?a=1&b=2")
    b = cache_key("https://x.com/p?b=2&a=1")
    assert a == b


def test_different_real_params_differ():
    a = cache_key("https://x.com/p?page=1")
    b = cache_key("https://x.com/p?page=2")
    assert a != b


def test_tracking_vs_no_tracking_same_key():
    a = cache_key("https://x.com/p?utm_source=a&id=1")
    b = cache_key("https://x.com/p?id=1")
    assert a == b
