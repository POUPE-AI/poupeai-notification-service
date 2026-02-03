from prometheus_client import Counter, Histogram

MESSAGES_RECEIVED = Counter(
    "notification_messages_received_total",
    "Total de mensagens recebidas do RabbitMQ",
    ["queue", "routing_key"]
)

MESSAGES_PROCESSED = Counter(
    "notification_messages_processed_total",
    "Total de mensagens processadas com sucesso ou erro",
    ["event_type", "status"]
)

MESSAGE_PROCESSING_TIME = Histogram(
    "notification_message_processing_seconds",
    "Tempo gasto processando a mensagem (inclui envio de email)",
    ["event_type"]
)

EMAILS_SENT = Counter(
    "notification_emails_sent_total",
    "Total de emails tentados/enviados",
    ["template", "status"]
)