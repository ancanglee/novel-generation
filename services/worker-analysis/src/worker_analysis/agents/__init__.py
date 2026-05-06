"""U3 sub-agents. Each module exposes a callable that invokes Bedrock via Tool Use."""

from worker_analysis.agents.character_global import extract_characters_global
from worker_analysis.agents.chapter_all import extract_chapter_all
from worker_analysis.agents.classification import classify_tags
from worker_analysis.agents.map_global import extract_map_global
from worker_analysis.agents.memory_writer import write_memory
from worker_analysis.agents.profile_rewrite import rewrite_character_profile
from worker_analysis.agents.rough_read import sample_chapters
from worker_analysis.agents.style import analyze_style

__all__ = [
    "analyze_style",
    "classify_tags",
    "extract_chapter_all",
    "extract_characters_global",
    "extract_map_global",
    "rewrite_character_profile",
    "sample_chapters",
    "write_memory",
]
