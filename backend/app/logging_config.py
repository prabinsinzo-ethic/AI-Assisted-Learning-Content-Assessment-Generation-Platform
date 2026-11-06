import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .config import DATA_DIR


def setup_logging():
    log_dir = DATA_DIR
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "app.log"

    level = os.getenv("LOG_LEVEL", "INFO").upper()
    fmt = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"

    root = logging.getLogger()
    root.setLevel(level)
    # avoid duplicate handlers on reload
    if root.handlers:
        return

    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter(fmt))
    root.addHandler(console)

    file_handler = RotatingFileHandler(log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter(fmt))
    root.addHandler(file_handler)

    # quiet noisy libs
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
