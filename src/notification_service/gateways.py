import aiosmtplib

from email.message import EmailMessage
from src.config import Settings
from .exceptions import TransientProcessingError

class EmailGateway:
    def __init__(self, settings: Settings):
        self.host = settings.EMAIL_HOST
        self.port = settings.EMAIL_PORT
        self.login = settings.EMAIL_LOGIN
        self.password = settings.EMAIL_PASSWORD.get_secret_value() if settings.EMAIL_PASSWORD else None
        self.from_name = settings.EMAIL_FROM_NAME
        self.from_email = settings.EMAIL_FROM

    async def send(self, to_email: str, subject: str, html_content: str):
        """
        Connects to the SMTP server and sends an email.
        Raises TransientProcessingError on SMTP failures.
        """
        if not all([self.host, self.port, self.login, self.password, self.from_email]):
            print("[ERROR] A configuração de e-mail está incompleta. Verifique as variáveis de ambiente.")
            raise TransientProcessingError("Configuração de e-mail incompleta no servidor.")

        message = EmailMessage()
        message["From"] = f"{self.from_name} <{self.from_email}>"
        message["To"] = to_email
        message["Subject"] = subject
        message.set_content("Por favor, habilite o HTML para visualizar este e-mail corretamente.")
        message.add_alternative(html_content, subtype="html")

        try:
            print(f"Tentando enviar e-mail para {to_email} via {self.host}:{self.port}")
            async with aiosmtplib.SMTP(hostname=self.host, port=self.port, use_tls=True) as smtp:
                await smtp.login(self.login, self.password)
                await smtp.send_message(message)
            print(f"E-mail enviado com sucesso para {to_email}.")
        except aiosmtplib.SMTPException as e:
            print(f"[SMTP_ERROR] Falha ao enviar e-mail: {e}")
            raise TransientProcessingError("Falha ao enviar e-mail via SMTP") from e