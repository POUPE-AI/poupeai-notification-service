from pydantic import BaseModel, Field, EmailStr
from typing import Union
from uuid import UUID
from datetime import datetime, date

class RecipientSchema(BaseModel):
    user_id: str
    email: EmailStr
    name: str

class InvoiceDueSoonPayload(BaseModel):
    """Payload para o evento INVOICE_DUE_SOON."""
    invoice_id: str
    due_date: date
    amount: float
    invoice_deep_link: str

class InvoiceOverduePayload(BaseModel):
    """Payload para o evento INVOICE_OVERDUE."""
    invoice_id: str
    due_date: date
    amount: float
    days_overdue: int
    invoice_deep_link: str

class ProfileDeactivationScheduledPayload(BaseModel):
    """Payload para o evento PROFILE_DEACTIVATION_SCHEDULED."""
    deletion_scheduled_at: datetime
    reactivate_account_deep_link: str

class NotificationEventEnvelope(BaseModel):
    """
    Schema do envelope principal da mensagem, validando a estrutura completa.
    O campo 'payload' é uma união de todos os payloads possíveis.
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