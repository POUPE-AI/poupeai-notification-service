class SchemaValidationError(Exception):
    """Error for schema validation failures that should not be retried."""
    pass

class EventTypeValidationError(Exception):
    """Error for event_type validation failures that should not be retried."""
    def __init__(self, event_type: str, message="Invalid or unsupported event"):
        self.event_type = event_type
        self.message = f"{message}: '{event_type}'"
        super().__init__(self.message)

class TransientProcessingError(Exception):
    """Error for processing failures that can be retried."""
    pass

class TemplateRenderingError(Exception):
    """Error for template rendering failures that should not be retried."""
    pass