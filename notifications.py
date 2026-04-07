import requests
from models import Settings

def send_discord_notification(settings: Settings, title: str, description: str, color: int = 3447003):
    if not settings or not settings.discord_webhook_url:
        return

    data = {
        "embeds": [{
            "title": title,
            "description": description,
            "color": color
        }]
    }

    try:
        requests.post(settings.discord_webhook_url, json=data, timeout=5)
    except Exception as e:
        print(f"Failed to send Discord notification: {e}")

def send_telegram_notification(settings: Settings, message: str):
    if not settings or not settings.telegram_bot_token or not settings.telegram_chat_id:
        return

    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    data = {
        "chat_id": settings.telegram_chat_id,
        "text": message,
        "parse_mode": "HTML"
    }

    try:
        requests.post(url, json=data, timeout=5)
    except Exception as e:
        print(f"Failed to send Telegram notification: {e}")

def notify_all(title: str, message: str, color: int = 3447003):
    from app import app
    from models import db
    with app.app_context():
        settings = Settings.query.first()
        if settings:
            send_discord_notification(settings, title, message, color)

            # Format telegram message roughly similar to discord embed
            tg_message = f"<b>{title}</b>\n{message}"
            send_telegram_notification(settings, tg_message)
