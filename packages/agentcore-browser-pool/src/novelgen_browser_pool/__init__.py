"""AgentCore Browser concurrency pool (global DDB CAS, max 10 slots)."""

from novelgen_browser_pool.pool import BrowserPool, BrowserSlotUnavailable

__all__ = ["BrowserPool", "BrowserSlotUnavailable"]
