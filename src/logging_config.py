import logging
import sys
import structlog
from config import settings

def audit_formatter_processor(logger, method_name: str, event_dict: dict) -> dict:
    if 'event_type' not in event_dict:
        return event_dict

    output_dict = {
        "timestamp": event_dict.pop("timestamp"),
        "level": event_dict.pop("level").upper(),
        "service_name": settings.SERVICE_NAME,
        "correlation_id": event_dict.pop("correlation_id", None),
        "trigger_type": event_dict.pop("trigger_type", "system_scheduled"),
        "event_type": event_dict.pop("event_type"),
        "message": event_dict.pop("event"),
    }

    actor_user_id = event_dict.pop("actor_user_id", None)
    if actor_user_id:
        output_dict["actor"] = {
            "user_id": actor_user_id,
            "source_ip": event_dict.pop("source_ip", "N/A")
        }
    else:
        output_dict["actor"] = None
    
    output_dict["event_details"] = event_dict
    
    return output_dict


def setup_logging(log_level: str = "INFO"):
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level.upper(),
        force=True
    )

    logging.getLogger("aio_pika").setLevel(logging.WARNING)
    logging.getLogger("aiormq").setLevel(logging.WARNING)
    
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.format_exc_info,
            audit_formatter_processor,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    structlog.get_logger(__name__).info("logging_configured_simplified", level=log_level.upper())