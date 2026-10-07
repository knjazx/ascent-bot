import os
from pathlib import Path
from dotenv import load_dotenv

# Загружаем переменные из файла .env в корне проекта
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "").strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
SERVER_NAME = os.getenv("SERVER_NAME", "ASCENT LEAGUE").strip()
HELP_CHANNEL_ID_STR = os.getenv("HELP_CHANNEL_ID", "").strip()
HELP_CHANNEL_ID = int(HELP_CHANNEL_ID_STR) if HELP_CHANNEL_ID_STR.isdigit() else None
ADMIN_ROLE_NAME = os.getenv("ADMIN_ROLE_NAME", "Администратор").strip()

# Настройки ограничения запросов (Rate Limiting)
RATE_LIMIT_MAX_REQUESTS = int(os.getenv("RATE_LIMIT_MAX_REQUESTS", "5").strip() or "5")
RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "86400").strip() or "86400")  # 86400 сек = 24 часа (день)
RATE_LIMIT_COOLDOWN_SECONDS = int(os.getenv("RATE_LIMIT_COOLDOWN_SECONDS", "60").strip() or "60")    # 60 сек между вопросами

KNOWLEDGE_DIR = BASE_DIR / "knowledge"
