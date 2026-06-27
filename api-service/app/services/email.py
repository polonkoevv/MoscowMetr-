import aiosmtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from loguru import logger

from app.config import settings

_VERIFY_TTL_HOURS = 24


def _build_verification_email(to_email: str, token: str) -> MIMEMultipart:
    verify_url = f"{settings.FRONTEND_URL}/auth/verify?token={token}"

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <style>
        body {{ font-family: 'Inter', Arial, sans-serif; background: #f1f5f9; margin: 0; padding: 40px 0; }}
        .card {{
          max-width: 480px; margin: 0 auto; background: #fff;
          border-radius: 16px; overflow: hidden;
          box-shadow: 0 4px 24px rgba(0,0,0,0.08);
        }}
        .header {{
          background: linear-gradient(135deg, #1a3a6b, #2563EB);
          padding: 32px; text-align: center; color: white;
        }}
        .header h1 {{ margin: 0; font-size: 1.8rem; letter-spacing: -0.5px; }}
        .header p  {{ margin: 4px 0 0; opacity: 0.85; font-size: 0.9rem; }}
        .body {{ padding: 32px; }}
        .body p {{ color: #475569; line-height: 1.6; margin: 0 0 16px; }}
        .btn {{
          display: block; width: fit-content; margin: 24px auto;
          background: linear-gradient(135deg, #2563EB, #1d4ed8);
          color: white !important; text-decoration: none;
          padding: 14px 36px; border-radius: 10px;
          font-weight: 600; font-size: 1rem;
          box-shadow: 0 4px 14px rgba(37,99,235,0.35);
        }}
        .footer {{ padding: 16px 32px 24px; text-align: center; }}
        .footer p {{ color: #94a3b8; font-size: 0.8rem; margin: 0; }}
        .url {{ word-break: break-all; color: #64748b; font-size: 0.8rem; }}
      </style>
    </head>
    <body>
      <div class="card">
        <div class="header">
          <h1>🏠 ReVal</h1>
          <p>Оценка стоимости недвижимости</p>
        </div>
        <div class="body">
          <p>Здравствуйте!</p>
          <p>Для завершения регистрации подтвердите ваш email-адрес, нажав кнопку ниже.</p>
          <a href="{verify_url}" class="btn">Подтвердить email</a>
          <p>Ссылка действует <strong>{_VERIFY_TTL_HOURS} часа</strong>.</p>
          <p>Если вы не регистрировались в ReVal — просто проигнорируйте это письмо.</p>
        </div>
        <div class="footer">
          <p>Не можете нажать кнопку? Скопируйте ссылку:</p>
          <p class="url">{verify_url}</p>
        </div>
      </div>
    </body>
    </html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Подтвердите email — ReVal"
    msg["From"]    = settings.SMTP_FROM
    msg["To"]      = to_email
    msg.attach(MIMEText(html, "html", "utf-8"))
    return msg


async def send_verification_email(to_email: str, token: str) -> None:
    msg = _build_verification_email(to_email, token)
    # Порт 465 — SSL сразу, порт 587 — STARTTLS
    use_tls    = settings.SMTP_PORT == 465
    start_tls  = settings.SMTP_PORT == 587

    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USER or None,
            password=settings.SMTP_PASSWORD or None,
            use_tls=use_tls,
            start_tls=start_tls,
        )
        logger.info(f"Письмо верификации отправлено на {to_email}")
    except Exception as e:
        logger.error(f"Ошибка отправки письма на {to_email}: {e}")
        raise
