"""robots.txt compliance with in-process TTL cache (24h)."""

from __future__ import annotations

import urllib.robotparser
from urllib.parse import urlparse

import httpx
from cachetools import TTLCache

from novelgen_types.errors import NovelGenError

_CACHE: TTLCache[str, urllib.robotparser.RobotFileParser] = TTLCache(maxsize=1024, ttl=86400)

USER_AGENT = "NovelGenBot/0.1 (+https://novelgen.example.com/bot)"


class RobotsDenied(NovelGenError):
    error_code = "FORBIDDEN_ROBOTS_DISALLOWED"
    http_status = 403


def _fetch_robots(host: str) -> urllib.robotparser.RobotFileParser:
    rp = urllib.robotparser.RobotFileParser()
    url = f"https://{host}/robots.txt"
    try:
        resp = httpx.get(url, timeout=5.0, headers={"User-Agent": USER_AGENT})
        if resp.status_code >= 400:
            rp.parse([])
        else:
            rp.parse(resp.text.splitlines())
    except httpx.HTTPError:
        rp.parse([])  # treat as allow-all if robots unreachable (with warning upstream)
    return rp


def _get_parser(host: str) -> urllib.robotparser.RobotFileParser:
    cached = _CACHE.get(host)
    if cached is not None:
        return cached
    parser = _fetch_robots(host)
    _CACHE[host] = parser
    return parser


def ensure_allowed(url: str, user_agent: str = USER_AGENT) -> None:
    """Raise RobotsDenied if the target path is disallowed."""
    host = urlparse(url).netloc
    if not host:
        raise RobotsDenied("invalid url: missing host", url=url)
    parser = _get_parser(host)
    if not parser.can_fetch(user_agent, url):
        raise RobotsDenied("robots.txt disallows this path", url=url, user_agent=user_agent)


def get_crawl_delay(url: str, user_agent: str = USER_AGENT) -> float:
    host = urlparse(url).netloc
    parser = _get_parser(host)
    delay = parser.crawl_delay(user_agent) or 1.0
    return float(max(1.0, min(30.0, delay)))
