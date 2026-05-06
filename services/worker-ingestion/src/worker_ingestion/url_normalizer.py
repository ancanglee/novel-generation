"""URL normalization for crawl-cache keys (D4=B).

Strips tracking query parameters, normalizes host case, drops fragment, sorts remaining
query keys for deterministic hashes.
"""

from __future__ import annotations

import hashlib
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

TRACKING_PARAMS: frozenset[str] = frozenset(
    {
        "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
        "ref", "referrer", "fbclid", "gclid", "msclkid",
        "mc_cid", "mc_eid", "_ga", "spm", "share_source",
        "from", "source", "via",
    }
)


def normalize_url(url: str) -> str:
    parsed = urlparse(url)
    qs = parse_qsl(parsed.query, keep_blank_values=True)
    cleaned = sorted(
        (k, v) for k, v in qs if k.lower() not in TRACKING_PARAMS
    )
    new_query = urlencode(cleaned, doseq=True)
    return urlunparse(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path,
            parsed.params,
            new_query,
            "",  # drop fragment
        )
    )


def cache_key(url: str) -> str:
    return hashlib.sha256(normalize_url(url).encode("utf-8")).hexdigest()
