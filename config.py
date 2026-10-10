import os
from pathlib import Path
from dotenv import load_dotenv

# Загружаем переменные из файла .env в корне проекта
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "").strip().strip('"').strip("'")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip().strip('"').strip("'")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview").strip().strip('"').strip("'")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip().strip('"').strip("'")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b").strip().strip('"').strip("'")
SERVER_NAME = os.getenv("SERVER_NAME", "ASCENT LEAGUE").strip().strip('"').strip("'")
HELP_CHANNEL_ID_STR = os.getenv("HELP_CHANNEL_ID", "").strip().strip('"').strip("'")
HELP_CHANNEL_ID = int(HELP_CHANNEL_ID_STR) if HELP_CHANNEL_ID_STR.isdigit() else None
ADMIN_ROLE_NAME = os.getenv("ADMIN_ROLE_NAME", "Администратор").strip().strip('"').strip("'")

# Настройки ограничения запросов (Rate Limiting)
RATE_LIMIT_MAX_REQUESTS = int(os.getenv("RATE_LIMIT_MAX_REQUESTS", "5").strip() or "5")
RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "86400").strip() or "86400")  # 86400 сек = 24 часа (день)
RATE_LIMIT_COOLDOWN_SECONDS = int(os.getenv("RATE_LIMIT_COOLDOWN_SECONDS", "60").strip() or "60")    # 60 сек между вопросами

KNOWLEDGE_DIR = BASE_DIR / "knowledge"
SETTINGS_FILE = BASE_DIR / "settings.json"


def get_setting(key: str, default=None):
    """Считывает динамическую настройку из settings.json."""
    if SETTINGS_FILE.exists():
        try:
            import json
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get(key, default)
        except Exception:
            pass
    return default


def set_setting(key: str, value):
    """Сохраняет динамическую настройку в settings.json."""
    data = {}
    if SETTINGS_FILE.exists():
        try:
            import json
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
    data[key] = value
    try:
        import json
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


CURRENT_LOGS_CHANNEL_ID: int | None = None


def get_logs_channel_id() -> int | None:
    """Возвращает ID канала логов/отзывов (из памяти, settings.json или .env)."""
    global CURRENT_LOGS_CHANNEL_ID
    if CURRENT_LOGS_CHANNEL_ID:
        return CURRENT_LOGS_CHANNEL_ID

    # 1. Приоритет: настроенный через команду /set_logs_channel
    saved = get_setting("LOGS_CHANNEL_ID")
    if saved:
        try:
            CURRENT_LOGS_CHANNEL_ID = int(saved)
            return CURRENT_LOGS_CHANNEL_ID
        except (ValueError, TypeError):
            pass

    # 2. Переменная окружения
    env_val = os.getenv("LOGS_CHANNEL_ID", "").strip().strip('"').strip("'")
    if env_val.isdigit():
        CURRENT_LOGS_CHANNEL_ID = int(env_val)
        return CURRENT_LOGS_CHANNEL_ID
    return None


def set_logs_channel_id(channel_id: int):
    """Сохраняет ID канала логов/отзывов в память и settings.json."""
    global CURRENT_LOGS_CHANNEL_ID
    CURRENT_LOGS_CHANNEL_ID = int(channel_id)
    set_setting("LOGS_CHANNEL_ID", int(channel_id))


