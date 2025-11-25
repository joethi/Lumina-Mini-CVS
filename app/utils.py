"""Utility functions including structured JSON logging."""

import json
import logging
import sys
from datetime import datetime
from typing import Any, Dict
from pythonjsonlogger import jsonlogger

from app.config import settings


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter with timestamp and standard fields."""

    def add_fields(self, log_record: Dict, record: logging.LogRecord, message_dict: Dict):
        """Add custom fields to log record."""
        super().add_fields(log_record, record, message_dict)
        log_record["timestamp"] = datetime.utcnow().isoformat() + "Z"
        log_record["level"] = record.levelname
        if not log_record.get("event"):
            log_record["event"] = record.getMessage()


def setup_logging():
    """Configure structured JSON logging."""
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, settings.LOG_LEVEL))

    # Remove existing handlers
    logger.handlers = []

    # Create console handler with JSON formatter
    handler = logging.StreamHandler(sys.stdout)
    formatter = CustomJsonFormatter(
        "%(timestamp)s %(level)s %(name)s %(event)s %(context)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger


def log_event(event: str, context: Dict[str, Any] = None, level: str = "INFO"):
    """
    Log a structured event with context.

    Args:
        event: Event name/description
        context: Additional context data
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    logger = logging.getLogger(__name__)
    log_func = getattr(logger, level.lower())

    context = context or {}
    log_func(event, extra={"context": context})


def calculate_token_count(text: str, model: str = "gpt-4") -> int:
    """
    Estimate token count for a given text.

    Args:
        text: Input text
        model: Model name for tokenization

    Returns:
        Estimated token count
    """
    try:
        import tiktoken

        encoding = tiktoken.encoding_for_model(model)
        return len(encoding.encode(text))
    except Exception as e:
        # Fallback: rough estimate (1 token ~= 4 characters)
        log_event("token_count_fallback", {"error": str(e)}, level="WARNING")
        return len(text) // 4


def truncate_text(text: str, max_tokens: int, model: str = "gpt-4") -> str:
    """
    Truncate text to a maximum token count.

    Args:
        text: Input text
        max_tokens: Maximum number of tokens
        model: Model name for tokenization

    Returns:
        Truncated text
    """
    try:
        import tiktoken

        encoding = tiktoken.encoding_for_model(model)
        tokens = encoding.encode(text)

        if len(tokens) <= max_tokens:
            return text

        truncated_tokens = tokens[:max_tokens]
        return encoding.decode(truncated_tokens)
    except Exception as e:
        log_event("truncate_text_error", {"error": str(e)}, level="ERROR")
        # Fallback: character-based truncation
        return text[: max_tokens * 4]


# Initialize logging on module import
setup_logging()
