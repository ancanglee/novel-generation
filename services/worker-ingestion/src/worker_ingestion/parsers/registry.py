"""Side-effect module: importing this ensures all parsers register themselves."""

from worker_ingestion.parsers import docx, epub, html, markdown, pdf, txt  # noqa: F401
