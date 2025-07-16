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
    invoice_id: str
    due_date: date
    amount: float
    invoice_deep_link: str

class InvoiceOverduePayload(BaseModel):
    """Payload for INVOICE_OVERDUE event."""
    invoice_id: str
    due_date: date
    amount: float
    days_overdue: int
    invoice_deep_link: str

class ProfileDeactivationScheduledPayload(BaseModel):
    """Payload for PROFILE_DEACTIVATION_SCHEDULED event."""
    deletion_scheduled_at: datetime
    reactivate_account_deep_link: str

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
        ProfileDeactivationScheduledPayload
    ] = Field(...)