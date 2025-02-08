from celery import Celery
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
import os
import logging
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Ensure variables are correctly loaded
MAIL_USERNAME = os.getenv("MAIL_USERNAME")
MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
MAIL_FROM = os.getenv("MAIL_FROM")
MAIL_PORT = os.getenv("MAIL_PORT")
MAIL_SERVER = os.getenv("MAIL_SERVER")
MAIL_TLS = os.getenv("MAIL_TLS") == "True"  # Convert string to boolean
MAIL_SSL = os.getenv("MAIL_SSL") == "True"

# Initialize Celery
celery = Celery("tasks", broker="redis://localhost:6379/0")

# Email Configuration
conf = ConnectionConfig(
    MAIL_USERNAME=os.getenv("MAIL_USERNAME"),
    MAIL_PASSWORD=os.getenv("MAIL_PASSWORD"),
    MAIL_FROM=os.getenv("MAIL_FROM"),
    MAIL_PORT=587,
    MAIL_SERVER="smtp.gmail.com",
    MAIL_STARTTLS=True,  
    MAIL_SSL_TLS=False,
    USE_CREDENTIALS=True
)

fm = FastMail(conf)

@celery.task
def send_email(email: str, subject: str, message: str):
    """Celery task to send email notifications asynchronously."""
    try:
        msg = MessageSchema(
            subject=subject,
            recipients=[email],
            body=message,
            subtype="html"
        )
        # Use async sending
        import asyncio
        asyncio.run(fm.send_message(msg))
        logging.info(f"Email sent successfully to {email}")
    except Exception as e:
        logging.error(f"Failed to send email to {email}: {str(e)}")
