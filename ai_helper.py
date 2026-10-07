import logging
import asyncio
from pathlib import Path
import config

logger = logging.getLogger("AIHelper")

# Поддержка современного google.genai и классического google.generativeai
USE_NEW_GENAI = False
USE_OLD_GENAI = False

try:
    from google import genai
    from google.genai import types as genai_types
    USE_NEW_GENAI = True
except ImportError:
    try:
        import google.generativeai as legacy_genai
        USE_OLD_GENAI = True
    except ImportError:
        pass


class KnowledgeBaseAI:
    def __init__(self):
        self.knowledge_text = ""
        self.client = None
        self.legacy_model = None
        self.is_configured = False
        self.load_knowledge()
        self.setup_ai()

    def load_knowledge(self) -> str:
        """Считывает все markdown и txt файлы из директории knowledge/."""
        content_parts = []
        if config.KNOWLEDGE_DIR.exists():
            for file_path in sorted(config.KNOWLEDGE_DIR.glob("*.*")):
                if file_path.suffix.lower() in [".md", ".txt"]:
                    try:
                        text = file_path.read_text(encoding="utf-8")
                        content_parts.append(
                            f"=== НАЧАЛО ДОКУМЕНТА: {file_path.name} ===\n"
                            f"{text}\n"
                            f"=== КОНЕЦ ДОКУМЕНТА ==="
                        )
                        logger.info(f"Загружен документ базы знаний: {file_path.name}")
                    except Exception as e:
                        logger.error(f"Ошибка при чтении {file_path.name}: {e}")
        
        self.knowledge_text = "\n\n".join(content_parts)
        return self.knowledge_text

    def get_system_instruction(self) -> str:
        return (
            f"Ты — официальный судейский представитель соревновательной лиги '{config.SERVER_NAME}'.\n"
            f"Твоя задача — давать предельно КРАТКИЕ, ТОЧНЫЕ и ОФИЦИАЛЬНЫЕ разъяснения соревновательного Регламента "
            f"и Правил Discord-сервера.\n\n"
            f"ГЛАВНЫЕ ПРАВИЛА ОТВЕТА:\n"
            f"1. МАКСИМАЛЬНАЯ КРАТКОСТЬ И ЛАКОНИЧНОСТЬ (БЕЗ 'ВОДЫ'):\n"
            f"   - Ответ должен быть максимально ёмким и коротким (обычно от 2 до 6 строк, не более 100-120 слов).\n"
            f"   - Никаких длинных предисловий, формальных приветствий и повторов вопроса. Сразу к сути!\n"
            f"   - Начинай с прямого вердикта: **Да, разрешено** / **Нет, запрещено** / **Установленный регламент:**.\n\n"
            f"2. ОФИЦИАЛЬНЫЙ И УВАЖИТЕЛЬНЫЙ ТОН:\n"
            f"   - Обращайся строго на «Вы» (с прописной буквы).\n"
            f"   - Деловой, сдержанный судейский тон, без сленга и эмоций.\n\n"
            f"3. ОБЯЗАТЕЛЬНАЯ ССЫЛКА НА ПУНКТ:\n"
            f"   - Всегда указывай точный пункт Регламента (например, **п. 3.6 Регламента**, **п. 8.6 Регламента**, **раздел 4 Правил Discord**) или код санкции (**код D-13**).\n\n"
            f"4. ШАБЛОН КОРОТКОГО ОТВЕТА:\n"
            f"   - Прямой вердикт (Разрешено / Запрещено / Порядок действий).\n"
            f"   - Пункт Регламента и краткое пояснение (1-2 предложения).\n"
            f"   - Санкция по коду D-XX (если применимо).\n\n"
            f"5. ЕСЛИ ИНФОРМАЦИИ НЕТ В РЕГЛАМЕНТЕ:\n"
            f"   - 'Данный вопрос не урегулирован Регламентом. Обратитесь в тикет к Администрации Лиги.'\n\n"
            f"=== ОФИЦИАЛЬНАЯ НОРМАТИВНАЯ БАЗА ASCENT LEAGUE ===\n"
            f"{self.knowledge_text}\n"
            f"=== КОНЕЦ НОРМАТИВНОЙ БАЗЫ ==="
        )

    def setup_ai(self):
        """Инициализирует подключение к Google Gemini API."""
        if not config.GEMINI_API_KEY:
            logger.warning("GEMINI_API_KEY не установлен. Бот ожидает настройки ключа в .env.")
            self.is_configured = False
            return

        if USE_NEW_GENAI:
            try:
                self.client = genai.Client(api_key=config.GEMINI_API_KEY)
                self.is_configured = True
                logger.info(f"Gemini AI успешно подключен (SDK: google.genai, модель: {config.GEMINI_MODEL})")
                return
            except Exception as e:
                logger.error(f"Ошибка инициализации нового google-genai: {e}")

        if USE_OLD_GENAI:
            try:
                legacy_genai.configure(api_key=config.GEMINI_API_KEY)
                self.legacy_model = legacy_genai.GenerativeModel(
                    model_name=config.GEMINI_MODEL,
                    system_instruction=self.get_system_instruction()
                )
                self.is_configured = True
                logger.info(f"Gemini AI успешно подключен (SDK: legacy google.generativeai, модель: {config.GEMINI_MODEL})")
                return
            except Exception as e:
                logger.error(f"Ошибка инициализации legacy generativeai: {e}")

        self.is_configured = False
        logger.error("Не удалось настроить библиотеку Gemini AI. Проверьте установку google-genai.")

    def reload(self) -> int:
        """Перезагружает базу знаний и обновляет модель."""
        self.load_knowledge()
        self.setup_ai()
        count = len(list(config.KNOWLEDGE_DIR.glob("*.*"))) if config.KNOWLEDGE_DIR.exists() else 0
        return count

    def _sync_generate_new(self, prompt: str) -> str:
        """Синхронный вызов через google.genai."""
        response = self.client.models.generate_content(
            model=config.GEMINI_MODEL,
            contents=prompt,
            config=genai_types.GenerateContentConfig(
                system_instruction=self.get_system_instruction(),
                temperature=0.2,
            )
        )
        if response and response.text:
            return response.text.strip()
        return "Не удалось сформировать ответ. Пожалуйста, попробуйте снова."

    def _sync_generate_old(self, prompt: str) -> str:
        """Синхронный вызов через legacy google.generativeai."""
        response = self.legacy_model.generate_content(prompt)
        if response and response.text:
            return response.text.strip()
        return "Не удалось сформировать ответ. Пожалуйста, попробуйте снова."

    async def generate_answer(self, user_question: str, author_name: str = "Игрок") -> str:
        """Асинхронно генерирует ответ на вопрос игрока."""
        if not self.is_configured:
            return (
                "⚠️ **ИИ-помощник ещё не настроен администратором!**\n"
                "Чтобы бот мог отвечать на вопросы, необходимо указать `GEMINI_API_KEY` в файле `.env`.\n"
                "Вы можете ознакомиться с правилами в канале регламента или создать тикет в поддержке."
            )

        prompt = f"Вопрос от игрока '{author_name}': {user_question}"

        try:
            if USE_NEW_GENAI and self.client:
                return await asyncio.to_thread(self._sync_generate_new, prompt)
            elif USE_OLD_GENAI and self.legacy_model:
                return await asyncio.to_thread(self._sync_generate_old, prompt)
            else:
                return "⚠️ Ошибка конфигурации библиотеки Gemini."
        except Exception as e:
            logger.error(f"Ошибка при обращении к Gemini API: {e}")
            error_str = str(e)
            if "ResourceExhausted" in error_str or "quota" in error_str.lower():
                return "⚠️ Превышен лимит запросов к ИИ. Пожалуйста, подождите минутку и попробуйте снова."
            elif "API_KEY_INVALID" in error_str or "invalid" in error_str.lower() and "key" in error_str.lower():
                return "⚠️ Указан недействительный API-ключ Gemini в `.env`. Проверьте ключ на https://aistudio.google.com."
            return f"⚠️ Произошла ошибка при обработке запроса: `{e}`. Пожалуйста, обратитесь к администрации."
