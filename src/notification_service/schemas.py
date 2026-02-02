from datetime import datetime, date
from pydantic import BaseModel, Field, EmailStr
from typing import Union
from uuid import UUID

class RecipientSchema(BaseModel):
    user_id: str
    email: EmailStr
    name: str

class InvoiceDueSoonPayload(BaseModel):
    """Payload for INVOICE_DUE_SOON event."""
    credit_card: str
    month: int
    year: int
    due_date: date
    amount: float
    invoice_deep_link: str

class InvoiceOverduePayload(BaseModel):
    """Payload for INVOICE_OVERDUE event."""
    credit_card: str
    month: int
    year: int
    due_date: date
    amount: float
    days_overdue: int
    invoice_deep_link: str

class ProfileDeletionScheduledPayload(BaseModel):
    """Payload for PROFILE_DELETION_SCHEDULED event."""
    deletion_scheduled_at: datetime
    reactivate_account_deep_link: str

class StatementProcessingCompletedPayload(BaseModel):
    """Payload for STATEMENT_PROCESSING_COMPLETED event."""
    status: str
    file_name: str
    account_name: str

class StatementProcessingFailedPayload(BaseModel):
    """Payload for STATEMENT_PROCESSING_FAILED event."""
    status: str
    file_name: str
    account_name: str
    error_code: str
    error_message: str

class NotificationEventEnvelope(BaseModel):
    """
    Schema of the main message envelope, validating the complete structure.
    """
    message_id: UUID
    timestamp: datetime
    trigger_type: str
    event_type: str
    recipient: RecipientSchema
    payload: Union[
        InvoiceDueSoonPayload,
        InvoiceOverduePayload,
        ProfileDeletionScheduledPayload,
        StatementProcessingCompletedPayload,
        StatementProcessingFailedPayload
    ] = Field(...)