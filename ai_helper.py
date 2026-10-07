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
            f"   - Никаких длинных предисловий, приветствий и повторов вопроса. Сразу к сути!\n\n"
            f"2. ФОРМАТ НАЧАЛА ОТВЕТА (СТРОГО ПО СМЫСЛУ ВОПРОСА):\n"
            f"   - Если вопрос о допустимости действия (можно/нельзя, разрешено/запрещено): начинай строго с прямого вердикта: **Да, разрешено** или **Нет, запрещено**.\n"
            f"   - Если вопрос открытый, процедурный или уточняющий (как, сколько, когда, кто, что делать, каков регламент): отвечай сразу по существу регламента или порядка действий. КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО начинать со слов 'Нет, запрещено' или 'Да, разрешено', если в вопросе не спрашивалось о разрешении/запрете действия!\n\n"
            f"3. ОФИЦИАЛЬНЫЙ И УВАЖИТЕЛЬНЫЙ ТОН:\n"
            f"   - Обращайся строго на «Вы» (с прописной буквы).\n"
            f"   - Деловой, сдержанный судейский тон, без сленга и эмоций.\n\n"
            f"4. ОБЯЗАТЕЛЬНАЯ ССЫЛКА НА ПУНКТ:\n"
            f"   - Всегда указывай точный пункт Регламента (например, **п. 3.6 Регламента**, **п. 8.6 Регламента**, **раздел 4 Правил Discord**) или код санкции (**код D-13**).\n\n"
            f"5. РЕАКЦИЯ НА ОСКОРБЛЕНИЯ, ТОКСИЧНОСТЬ И НЕЦЕНЗУРНУЮ БРАНЬ:\n"
            f"   - Если игрок оскорбляет бота, участников или судей, использует ненормативную лексику, провоцирует или токсичит — НЕ ОТВЕЧАЙ 'Нет, запрещено'!\n"
            f"   - Сохраняй судейскую выдержку и напомни о правилах сервера:\n"
            f"     *«Просим соблюдать культуру общения на сервере {config.SERVER_NAME}. Оскорбления, провокации и ненормативная лексика строго запрещены согласно п. 1 Правил Discord-сервера. Нарушение влечёт за собой меры модерации (мут/тайм-аут по п. 9).»*\n\n"
            f"6. ОПИСАНИЕ ИГРОВЫХ И СПОРНЫХ СИТУАЦИЙ В МАТЧЕ:\n"
            f"   - Если игрок описывает конкретную игровую ситуацию, инцидент в матче, спорный эпизод или нарушение соперника, обязательно добавь в конце ответа:\n"
            f"     *«Данный ответ не является окончательным решением. Окончательное решение принимает ASCENT Head Referee.»*\n\n"
            f"7. ДИАЛОГ В ВЕТКЕ (THREAD):\n"
            f"   - Если вопрос является продолжением предшествующего обсуждения в ветке, учитывай контекст предыдущих реплик, понимай местоимения ('он', 'они', 'это') и развивай ответ с учётом сказанного ранее.\n\n"
            f"8. ЕСЛИ ИНФОРМАЦИИ НЕТ В РЕГЛАМЕНТЕ ИЛИ ВОПРОС НЕ ПО ТЕМЕ:\n"
            f"   - Если вопрос касается лиги, но не урегулирован правилами: 'Данный вопрос не урегулирован Регламентом. Обратитесь в тикет к Администрации Лиги.'\n"
            f"   - Если вопрос абсолютно посторонний (оффтоп): 'Я консультирую исключительно по регламенту CS2 и правилам лиги {config.SERVER_NAME}.'\n\n"
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
        """Синхронный вызов через google.genai с каскадным переключением моделей."""
        models_to_try = [config.GEMINI_MODEL, "gemini-3-flash-preview", "gemini-flash-lite-latest"]
        seen = set()
        unique_models = [m for m in models_to_try if not (m in seen or seen.add(m))]

        last_error = None
        for m in unique_models:
            try:
                response = self.client.models.generate_content(
                    model=m,
                    contents=prompt,
                    config=genai_types.GenerateContentConfig(
                        system_instruction=self.get_system_instruction(),
                        temperature=0.2,
                    )
                )
                if response and response.text:
                    return response.text.strip()
            except Exception as e:
                err_text = str(e)
                logger.warning(f"Ошибка при вызове модели {m}: {err_text[:120]}. Пробуем резервную модель...")
                last_error = e
                continue

        if last_error:
            raise last_error
        return "Не удалось сформировать ответ. Пожалуйста, попробуйте снова."

    def _sync_generate_old(self, prompt: str) -> str:
        """Синхронный вызов через legacy google.generativeai."""
        response = self.legacy_model.generate_content(prompt)
        if response and response.text:
            return response.text.strip()
        return "Не удалось сформировать ответ. Пожалуйста, попробуйте снова."

    async def generate_answer(
        self,
        user_question: str,
        author_name: str = "Игрок",
        chat_history: list = None
    ) -> str:
        """Асинхронно генерирует ответ на вопрос игрока с учётом контекста ветки."""
        if not self.is_configured:
            return (
                "⚠️ **ИИ-помощник ещё не настроен администратором!**\n"
                "Чтобы бот мог отвечать на вопросы, необходимо указать `GEMINI_API_KEY` в файле `.env`.\n"
                "Вы можете ознакомиться с правилами в канале регламента или создать тикет в поддержке."
            )

        if chat_history:
            history_lines = []
            for speaker, text in chat_history:
                short_text = text[:800] + ("..." if len(text) > 800 else "")
                history_lines.append(f"[{speaker}]:\n{short_text}\n")
            history_context = "\n".join(history_lines)
            prompt = (
                f"=== ИСТОРИЯ ДИАЛОГА В ЭТОЙ ВЕТКЕ ОБРАЩЕНИЯ ===\n"
                f"{history_context}\n"
                f"=== КОНЕЦ ИСТОРИИ ДИАЛОГА ===\n\n"
                f"Текущее продолжение вопроса от игрока '{author_name}': {user_question}\n"
                f"Ответь на текущее сообщение игрока с учётом контекста предшествующего диалога выше."
            )
        else:
            prompt = f"Вопрос от игрока '{author_name}': {user_question}"

        for attempt in range(2):
            try:
                if USE_NEW_GENAI and self.client:
                    return await asyncio.to_thread(self._sync_generate_new, prompt)
                elif USE_OLD_GENAI and self.legacy_model:
                    return await asyncio.to_thread(self._sync_generate_old, prompt)
                else:
                    return "⚠️ Ошибка конфигурации библиотеки Gemini."
            except Exception as e:
                logger.error(f"Ошибка при обращении к Gemini API (попытка {attempt + 1}/2): {e}")
                error_str = str(e)
                if attempt == 0 and ("503" in error_str or "UNAVAILABLE" in error_str or "ResourceExhausted" in error_str):
                    await asyncio.sleep(1.5)
                    continue
                if "ResourceExhausted" in error_str or "quota" in error_str.lower():
                    return "⚠️ Превышен лимит запросов к ИИ. Пожалуйста, подождите минутку и попробуйте снова."
                elif "API_KEY_INVALID" in error_str or ("invalid" in error_str.lower() and "key" in error_str.lower()):
                    return "⚠️ Указан недействительный API-ключ Gemini в `.env`. Проверьте ключ на https://aistudio.google.com."
                return f"⚠️ Произошла ошибка при обработке запроса: `{e}`. Пожалуйста, обратитесь к администрации."
