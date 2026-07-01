"""Centralized logging setup for the SMMA Bot system."""

import logging
import os
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent.parent / "event_log"


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """Configure root logging to console and event_log file."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOG_DIR / "smma_bot.log"

    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    handlers = [
        logging.StreamHandler(),
        logging.FileHandler(log_file, encoding="utf-8"),
    ]
    logging.basicConfig(level=level, format=fmt, handlers=handlers, force=True)

    if os.environ.get("DEBUG", "false").lower() == "true":
        logging.getLogger().setLevel(logging.DEBUG)

    return logging.getLogger("SMMA_Bot")
