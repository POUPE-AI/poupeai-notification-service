import logging
import sys
import structlog
import traceback
from datetime import datetime
from config import settings

def ecs_processor(logger, method_name: str, event_dict: dict) -> dict:
    timestamp = event_dict.pop("timestamp", datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ"))
    
    level = event_dict.pop("level", method_name).upper()
    
    message = event_dict.pop("event", "")
    
    correlation_id = event_dict.pop("correlation_id", None)
    event_type = event_dict.pop("event_type", None)
    user_id = event_dict.pop("user_id", event_dict.pop("actor_user_id", None))
    
    # "level", "service_name", e "event_type" estao duplicados para compatibilidade com o Loki
    ecs_log = {
        "@timestamp": timestamp,
        "log.level": level,
        "level": level,  # Loki
        "service.name": settings.SERVICE_NAME,
        "service_name": settings.SERVICE_NAME,  # Loki
        "message": message,
        "trace.correlation_id": correlation_id,
        "event.type": event_type,
        "event_type": event_type,  # Loki
        "user.id": user_id,
        "error": None,
        "context": {}
    }

    exc_info = event_dict.pop("exc_info", None)
    if exc_info:
        if isinstance(exc_info, bool) and exc_info:
            import sys
            exc_info = sys.exc_info()
        
        if isinstance(exc_info, tuple) and len(exc_info) == 3:
            exc_type, exc_value, exc_traceback = exc_info
            ecs_log["error"] = {
                "type": exc_type.__name__ if exc_type else None,
                "message": str(exc_value) if exc_value else None,
                "stack_trace": "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
            }
        elif isinstance(exc_info, BaseException):
            ecs_log["error"] = {
                "type": type(exc_info).__name__,
                "message": str(exc_info),
                "stack_trace": "".join(traceback.format_exception(type(exc_info), exc_info, exc_info.__traceback__))
            }
    
    if not ecs_log["error"] and "error" in event_dict:
        error_val = event_dict.pop("error")
        if isinstance(error_val, dict):
             ecs_log["error"] = error_val
        else:
            ecs_log["error"] = {
                "type": "BusinessError" if level == "WARN" else "Error",
                "message": str(error_val),
                "stack_trace": None
            }

    ecs_log["context"] = event_dict
    
    return ecs_log


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
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            #structlog.processors.format_exc_info,
            ecs_processor,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    structlog.get_logger(__name__).debug(
        "Logging configured",
        event_type="LOGGING_CONFIGURED",
        log_level=log_level.upper()
    )