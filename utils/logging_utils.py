import logging
import structlog
from structlog.stdlib import add_log_level, add_logger_name


def setup_logging(level: int = logging.INFO) -> None:
    """Configure structlog and standard logging with the given level."""
    logging.basicConfig(level=level, format="%(message)s")
    processors = (
        structlog.contextvars.merge_contextvars,
        add_logger_name,
        add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=False),
        structlog.dev.ConsoleRenderer(colors=True),
    )
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
