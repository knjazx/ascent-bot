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
        self.groq_client = None
        self.provider = None
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
            f"Ты — официальный судейский представитель и информационный ассистент соревновательной лиги '{config.SERVER_NAME}'.\n"
            f"Твоя задача — давать предельно КРАТКИЕ, ТОЧНЫЕ и ОФИЦИАЛЬНЫЕ ответы по соревновательному Регламенту, "
            f"Правилам Discord-сервера, а также по общим организационным вопросам Лиги (регистрация, даты, дисциплины, новости).\n\n"
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
            f"4. ССЫЛКИ НА ПУНКТЫ ПРАВИЛ:\n"
            f"   - Если вопрос касается соревновательного регламента, матчевых ситуаций, санкций или правил сервера: ОБЯЗАТЕЛЬНО указывай точный пункт Регламента (например, **п. 3.6 Регламента**, **п. 8.6 Регламента**, **раздел 4 Правил Discord**) или код санкции (**код D-13**).\n"
            f"   - Если вопрос общего организационного характера (даты, расписание, регистрация, новые дисциплины), пункт регламента указывать не требуется.\n\n"
            f"5. РЕАКЦИЯ НА ОСКОРБЛЕНИЯ, ТОКСИЧНОСТЬ И НЕЦЕНЗУРНУЮ БРАНЬ:\n"
            f"   - Если игрок оскорбляет бота, участников или судей, использует ненормативную лексику, провоцирует или токсичит — НЕ ОТВЕЧАЙ 'Нет, запрещено'!\n"
            f"   - Сохраняй судейскую выдержку и напомни о правилах сервера:\n"
            f"     *«Просим соблюдать культуру общения на сервере {config.SERVER_NAME}. Оскорбления, провокации и ненормативная лексика строго запрещены согласно п. 1 Правил Discord-сервера. Нарушение влечёт за собой меры модерации (мут/тайм-аут по п. 9).»*\n\n"
            f"6. ОПИСАНИЕ ИГРОВЫХ И СПОРНЫХ СИТУАЦИЙ В МАТЧЕ:\n"
            f"   - Если игрок описывает конкретную игровую ситуацию, инцидент в матче, спорный эпизод или нарушение соперника, обязательно добавь в конце ответа:\n"
            f"     *«Данный ответ не является окончательным решением. Окончательное решение принимает ASCENT Head Referee.»*\n\n"
            f"7. ДИАЛОГ В ВЕТКЕ (THREAD):\n"
            f"   - Если вопрос является продолжением предшествующего обсуждения в ветке, учитывай контекст предыдущих реплик, понимай местоимения ('он', 'они', 'это') и развивай ответ с учётом сказанного ранее.\n\n"
            f"8. ВОПРОСЫ ВНЕ РЕГЛАМЕНТА (ОРГАНИЗАЦИЯ, ДАТЫ, РЕГИСТРАЦИЯ, НОВЫЕ ДИСЦИПЛИНЫ):\n"
            f"   - Если участник спрашивает о событиях или жизни Лиги, которые не прописаны строго в регламенте матчей:\n"
            f"     * О датах регистрации, расписании сезона или старте турниров: сначала сверься с базой знаний. Если точные даты не указаны или ещё не объявлены, официально отвечай, что на данный момент точные даты неизвестны (ещё не опубликованы), и рекомендуй следить за обновлениями в официальных каналах Лиги (в каналах новостей и объявлений на сервере).\n"
            f"     * О новых дисциплинах (Dota 2, Valorant и др.): отвечай в официальном стиле, что на текущий момент официальной дисциплиной Лиги является Counter-Strike 2. Информация о запуске турниров по другим дисциплинам на данный момент не анонсировалась — рекомендуй следить за новостями проекта в официальных каналах.\n"
            f"     * О прочих организационных вопросах: если сведений нет в базе знаний, вежливо сообщи, что официальной информации на данный момент нет, и предложи обратиться в тикет к Администрации Лиги либо ожидать официального анонса.\n\n"
            f"9. СТОРОННИЕ ТЕМЫ (ПОЛНЫЙ ОФФТОП):\n"
            f"   - Если вопрос абсолютно посторонний и не имеет никакого отношения к ASCENT LEAGUE, CS2, турнирам или правилам сервера (например: рецепты, школьные уроки, сторонние игры, бытовые разговоры):\n"
            f"     * Категорически не вступай в посторонний диалог и не отвечай на них как обычный чат-бот!\n"
            f"     * Ответь кратко и сдержанно: *«Я являюсь официальным ассистентом {config.SERVER_NAME} и консультирую исключительно по вопросам деятельности Лиги, соревновательному регламенту и правилам сервера.»*\n\n"
            f"=== ОФИЦИАЛЬНАЯ НОРМАТИВНАЯ БАЗА ASCENT LEAGUE ===\n"
            f"{self.knowledge_text}\n"
            f"=== КОНЕЦ НОРМАТИВНОЙ БАЗЫ ==="
        )

    def setup_ai(self):
        """Инициализирует подключение к Groq AI или Google Gemini API."""
        # 1. Приоритет: Groq API (14 400 бесплатных запросов в день на Llama 3.3 70B)
        if config.GROQ_API_KEY:
            try:
                from groq import Groq
                self.groq_client = Groq(api_key=config.GROQ_API_KEY)
                self.provider = "groq"
                self.is_configured = True
                logger.info(f"Groq AI успешно подключен (модель: {config.GROQ_MODEL}, лимит: 14 400 запр/день)")
                return
            except Exception as e:
                logger.error(f"Ошибка инициализации Groq AI: {e}")

        # 2. Google Gemini API
        if config.GEMINI_API_KEY:
            if USE_NEW_GENAI:
                try:
                    self.client = genai.Client(api_key=config.GEMINI_API_KEY)
                    self.provider = "gemini"
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
                    self.provider = "gemini"
                    self.is_configured = True
                    logger.info(f"Gemini AI успешно подключен (SDK: legacy google.generativeai, модель: {config.GEMINI_MODEL})")
                    return
                except Exception as e:
                    logger.error(f"Ошибка инициализации legacy generativeai: {e}")

        self.is_configured = False
        logger.warning("Ни GROQ_API_KEY, ни GEMINI_API_KEY не настроены в .env.")

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

    def _sync_generate_groq(self, prompt: str) -> str:
        """Синхронный вызов через Groq API с каскадом моделей."""
        models_to_try = [config.GROQ_MODEL, "openai/gpt-oss-120b", "qwen/qwen3.8-27b", "openai/gpt-oss-20b"]
        seen = set()
        unique_models = [m for m in models_to_try if not (m in seen or seen.add(m))]

        last_error = None
        for m in unique_models:
            try:
                completion = self.groq_client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": self.get_system_instruction()},
                        {"role": "user", "content": prompt}
                    ],
                    model=m,
                    temperature=0.2,
                    max_tokens=600
                )
                if completion.choices and completion.choices[0].message.content:
                    return completion.choices[0].message.content.strip()
            except Exception as e:
                logger.warning(f"Ошибка Groq модели {m}: {e}. Пробуем резервную...")
                last_error = e
                continue

        if last_error:
            raise last_error
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
                "Чтобы бот мог отвечать на вопросы, необходимо указать `GROQ_API_KEY` (рекомендуется) или `GEMINI_API_KEY` в файле `.env`.\n"
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
                if self.provider == "groq" and self.groq_client:
                    return await asyncio.to_thread(self._sync_generate_groq, prompt)
                elif USE_NEW_GENAI and self.client:
                    return await asyncio.to_thread(self._sync_generate_new, prompt)
                elif USE_OLD_GENAI and self.legacy_model:
                    return await asyncio.to_thread(self._sync_generate_old, prompt)
                else:
                    return "⚠️ Ошибка конфигурации библиотеки ИИ."
            except Exception as e:
                logger.error(f"Ошибка при обращении к ИИ (попытка {attempt + 1}/2): {e}")
                error_str = str(e)
                if attempt == 0 and ("503" in error_str or "UNAVAILABLE" in error_str or "429" in error_str or "rate_limit" in error_str.lower()):
                    await asyncio.sleep(1.5)
                    continue
                if "402" in error_str or "prepayment" in error_str.lower():
                    return "⚠️ На текущем ключе закончился предоплаченный баланс (Ошибка 402: Prepayment credits depleted). Рекомендуется бесплатный Groq API (14 400 запр/день на https://console.groq.com) или новый ключ Gemini."
                elif "ResourceExhausted" in error_str or "429" in error_str or "quota" in error_str.lower() or "rate_limit" in error_str.lower():
                    return "⚠️ Временно превышен лимит запросов к ИИ. Пожалуйста, подождите минутку и попробуйте снова."
                elif "API_KEY_INVALID" in error_str or ("invalid" in error_str.lower() and "key" in error_str.lower()):
                    return "⚠️ Указан недействительный API-ключ в `.env`."
                return f"⚠️ Произошла ошибка при обращении к ИИ. Пожалуйста, обратитесь к администрации."
