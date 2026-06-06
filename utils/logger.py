import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from rich.logging import RichHandler
from utils.config import DATA_DIR, LOG_LEVEL


class JsonFormatter(logging.Formatter):
    """Formats logs in a clean, structured JSON format for files."""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "filename": record.filename,
            "lineno": record.lineno,
        }
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_data)


def setup_logger(name: str = "personal_ai_os") -> logging.Logger:
    """Configures and returns a structured logger.

    Writes JSON logs to data/app.log and rich-formatted logs to stderr.
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
    
    # Avoid duplicate handlers if logger is already configured
    if logger.handlers:
        return logger

    # Ensure log directory exists
    log_file_path = Path(DATA_DIR) / "app.log"
    log_file_path.parent.mkdir(parents=True, exist_ok=True)

    # 1. File Handler for structured JSON logs
    file_handler = logging.FileHandler(log_file_path, encoding="utf-8")
    file_handler.setFormatter(JsonFormatter())
    file_handler.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
    logger.addHandler(file_handler)

    # 2. Console Handler using Rich for visual beauty
    console_handler = RichHandler(
        rich_tracebacks=True,
        markup=True,
        show_time=True,
        show_path=False,
    )
    console_handler.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
    logger.addHandler(console_handler)

    # Prevent logs from bubbling up to root handlers (e.g. duplicate output)
    logger.propagate = False

    return logger


# Global logger instance
logger = setup_logger()
