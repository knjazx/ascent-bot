import sys
import logging

# Обеспечиваем корректный вывод UTF-8 в консоли Windows
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import os
import discord
from aiohttp import web
from discord import app_commands
from discord.ext import commands

import config
from ai_helper import KnowledgeBaseAI
from rate_limiter import UserRateLimiter
from feedback import FeedbackView

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("DiscordBot")

# Настройка Intents
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)
ai = KnowledgeBaseAI()
rate_limiter = UserRateLimiter(
    max_requests=config.RATE_LIMIT_MAX_REQUESTS,
    window_seconds=config.RATE_LIMIT_WINDOW_SECONDS,
    cooldown_seconds=config.RATE_LIMIT_COOLDOWN_SECONDS
)

# Цвет полоски в Embed-сообщениях (серый)
EMBED_COLOR = discord.Color.light_grey()


def is_user_admin(user: discord.Member | discord.User) -> bool:
    """Проверяет наличие прав администратора или служебной роли у пользователя."""
    if not isinstance(user, discord.Member):
        return False
    if user.guild_permissions.administrator:
        return True
    return any(role.name == config.ADMIN_ROLE_NAME for role in user.roles)





async def handle_ping(request):
    """Ответ на healthcheck запросы хостинга (UptimeRobot, Hugging Face, Render)."""
    return web.Response(text="ASCENT LEAGUE Discord Assistant is online and running!")


async def start_web_server():
    """Запуск фонового веб-сервера для предотвращения спящего режима на бесплатных облаках."""
    port_str = os.getenv("PORT", "7860").strip()
    port = int(port_str) if port_str.isdigit() else 7860
    app = web.Application()
    app.router.add_get("/", handle_ping)
    app.router.add_get("/ping", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    try:
        await site.start()
        logger.info(f"Healthcheck веб-сервер успешно запущен на порту {port}")
    except Exception as e:
        logger.warning(f"Не удалось запустить healthcheck веб-сервер на порту {port}: {e}")


@bot.event
async def on_ready():
    logger.info(f"Бот успешно авторизован как {bot.user} (ID: {bot.user.id})")
    
    # Запускаем фоновый веб-сервер для облачных платформ
    await start_web_server()
    
    # Установка статуса активности
    activity = discord.Activity(
        type=discord.ActivityType.listening,
        name="/ask | Регламент ASCENT CS2"
    )
    await bot.change_presence(status=discord.Status.online, activity=activity)

    # Синхронизация слэш-команд
    try:
        synced = await bot.tree.sync()
        logger.info(f"Синхронизировано слэш-команд: {len(synced)}")
    except Exception as e:
        logger.error(f"Ошибка синхронизации слэш-команд: {e}")


@bot.tree.command(name="ask", description="Задать вопрос по регламенту ASCENT LEAGUE CS2")
@app_commands.describe(question="Ваш вопрос (например: какое наказание за Snap Tap или опоздание?)")
async def ask_command(interaction: discord.Interaction, question: str):
    """Слэш-команда для вопроса нейросети."""
    # Проверка ограничения частоты запросов
    is_admin = is_user_admin(interaction.user)
    is_limited, reason, retry_after = rate_limiter.is_rate_limited(interaction.user.id, is_admin=is_admin)
    if is_limited:
        time_str = rate_limiter.format_time(retry_after)
        if reason == "cooldown":
            desc = (
                f"Уважаемый(-ая) {interaction.user.mention}!\n\n"
                f"Установлена пауза между вопросами (**{config.RATE_LIMIT_COOLDOWN_SECONDS} сек.**).\n"
                f"Пожалуйста, подождите ещё **{time_str}** перед отправкой следующего вопроса."
            )
        else:
            desc = (
                f"Уважаемый(-ая) {interaction.user.mention}!\n\n"
                f"Вы исчерпали суточный лимит обращений (максимум **{config.RATE_LIMIT_MAX_REQUESTS} вопросов в день**).\n"
                f"Доступ к новым вопросам восстановится через **{time_str}**."
            )

        embed = discord.Embed(
            title="⏳ Ограничение частоты запросов",
            description=desc,
            color=EMBED_COLOR
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    # Сообщаем дискорду, что бот думает (запрос к ИИ может занять 1-3 сек)
    await interaction.response.defer(thinking=True)
    rate_limiter.record_request(interaction.user.id)
    remaining_today = rate_limiter.get_remaining_requests(interaction.user.id, is_admin=is_admin)

    user_name = interaction.user.display_name
    answer = await ai.generate_answer(question, author_name=user_name)

    # Если ответ слишком длинный для одного эмбеда (лимит 4096 символов)
    if len(answer) > 4000:
        answer_truncated = answer[:3950] + "\n\n*(Ответ сокращен из-за ограничений Discord)*"
    else:
        answer_truncated = answer

    footer_text = f"{config.SERVER_NAME} • Заявитель: {user_name}"
    if not is_admin:
        footer_text += f" • Осталось сегодня: {remaining_today}/{config.RATE_LIMIT_MAX_REQUESTS}"

    embed = discord.Embed(
        title="⚖️ Официальное разъяснение ASCENT LEAGUE",
        description=answer_truncated,
        color=EMBED_COLOR
    )
    embed.add_field(name="❓ Запрос участника", value=f"*{question}*", inline=False)
    embed.set_footer(
        text=footer_text,
        icon_url=interaction.user.display_avatar.url if interaction.user.display_avatar else None
    )
    feedback_view = FeedbackView(question=question, answer=answer)
    await interaction.followup.send(embed=embed, view=feedback_view)


@bot.tree.command(name="faq", description="Часто задаваемые вопросы по регламенту ASCENT LEAGUE CS2")
async def faq_command(interaction: discord.Interaction):
    """Выводит список частых вопросов."""
    embed = discord.Embed(
        title="❓ Часто задаваемые вопросы (FAQ) — ASCENT LEAGUE CS2",
        description=(
            "**1. Требования к аккаунту:** ≥150 часов в CS2, открытый профиль, Steam Guard, без банов (п. 3.2).\n"
            "**2. Стендины:** не более 1 на матч и не более 2 за турнир; строго до старта матча (п. 3.6).\n"
            "**3. Скины агентов:** СТРОГО ЗАПРЕЩЕНЫ, только дефолтные модели (п. 8.5).\n"
            "**4. Клавиатуры:** Rapid Trigger РАЗРЕШЁН. Snap Tap / SOCD / Null Binds СТРОГО ЗАПРЕЩЕНЫ (Walkover + бан 6 месяцев, код D-13).\n"
            "**5. Опоздания:** 5-15 мин — Warn 1, >15 мин — ТП на Карте 1, >25 мин — Walkover в серии (п. 7.7).\n"
            "**6. Проверка ПК (PC Check):** только Screen Share в Discord, запись 14 дней, без доступа к перепискам (п. 9.3).\n"
            "**7. Призовые:** выплата в ASCENT Coins (ASC) в течение 7 дней (п. 11.3).\n\n"
            "💬 *Нужен ответ на другой вопрос? Напишите:* `/ask ваш вопрос`"
        ),
        color=EMBED_COLOR
    )
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="rules", description="Показать ключевые положения регламента ASCENT LEAGUE CS2")
async def rules_command(interaction: discord.Interaction):
    """Показывает памятку по правилам."""
    embed = discord.Embed(
        title=f"📜 Регламент соревнований {config.SERVER_NAME} (CS2 v1.0)",
        description=(
            "**Основные разделы Регламента:**\n"
            "• **Раздел 3:** Составы, допуск, квалификационные требования и стендины\n"
            "• **Раздел 5 & 9:** Античит (GameGuard / FACEIT AC), честная игра и PC Check\n"
            "• **Раздел 7:** Организация матчей, расписание, Grace Period, Map Veto, Ножевой раунд\n"
            "• **Раздел 8:** Внутриигровые стандарты CS2 (MR12, овертаймы MR3, запрет кастомных агентов и Snap Tap)\n"
            "• **Раздел 10 & Приложение D:** Протесты в #protests и каталог санкций (D-01 .. D-15)\n"
            "• **Раздел 11:** Регламент выплаты призовых (ASC) и Prizepool Safety Clause\n\n"
            "💡 Чтобы узнать точный пункт или наказание, спросите бота: `/ask <вопрос>`"
        ),
        color=EMBED_COLOR
    )
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="reload_rules", description="Перезагрузить базу знаний правил из файлов (для Администрации)")
async def reload_rules_command(interaction: discord.Interaction):
    """Команда обновления правил без перезапуска бота."""
    if not is_user_admin(interaction.user):
        await interaction.response.send_message("❌ У Вас нет прав для выполнения данной команды.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)
    count = ai.reload()
    await interaction.followup.send(
        f"✅ База знаний успешно обновлена! Загружено файлов: **{count}**.\n"
        f"Статус ИИ: {'🟢 Активен' if ai.is_configured else '🔴 Ключ не настроен'}",
        ephemeral=True
    )


@bot.tree.command(name="set_logs_channel", description="Назначить канал для получения отзывов (👍/👎) и логов (для Администрации)")
@app_commands.describe(channel="Текстовый канал, куда бот будет присылать отзывы и логи")
async def set_logs_channel_command(interaction: discord.Interaction, channel: discord.TextChannel):
    """Команда назначения канала для логирования отзывов."""
    if not is_user_admin(interaction.user):
        await interaction.response.send_message("❌ У Вас нет прав для выполнения данной команды.", ephemeral=True)
        return

    config.set_logs_channel_id(channel.id)
    await interaction.response.send_message(
        f"✅ Канал для отзывов и логов успешно назначен: {channel.mention}\n"
        f"Все оценки ответов (👍 / 👎) и замечания игроков будут поступать в этот канал.",
        ephemeral=True
    )

    try:
        test_embed = discord.Embed(
            title="⚙️ Канал логов и отзывов подключен",
            description=(
                f"Данный канал назначен для сбора отзывов участников и логов **{config.SERVER_NAME}**.\n"
                f"Назначил администратор: {interaction.user.mention}."
            ),
            color=EMBED_COLOR
        )
        await channel.send(embed=test_embed)
    except Exception as e:
        logger.warning(f"Не удалось отправить приветственное сообщение в канал {channel.id}: {e}")



async def get_thread_history(thread: discord.Thread, current_message: discord.Message, max_messages: int = 10) -> list:
    """Собирает историю сообщений в ветке для сохранения контекста диалога."""
    history = []

    # 1. Пытаемся получить исходный вопрос, на основе которого создана ветка
    try:
        starter_text = None
        starter_author = "Игрок"
        if thread.starter_message and thread.starter_message.clean_content:
            starter_text = thread.starter_message.clean_content.strip()
            starter_author = thread.starter_message.author.display_name
        elif thread.parent:
            try:
                parent_msg = await thread.parent.fetch_message(thread.id)
                if parent_msg and parent_msg.clean_content:
                    starter_text = parent_msg.clean_content.strip()
                    starter_author = parent_msg.author.display_name
            except Exception:
                pass

        if starter_text:
            history.append((f"Игрок ({starter_author}) [Исходный вопрос]", starter_text))
    except Exception as e:
        logger.debug(f"Не удалось получить стартовое сообщение ветки: {e}")

    # 2. Собираем сообщения из самой ветки, предшествующие текущему вопросу
    try:
        raw_msgs = []
        async for msg in thread.history(limit=max_messages, before=current_message):
            raw_msgs.append(msg)

        # Переворачиваем в хронологический порядок (от старых к новым)
        raw_msgs.reverse()

        for msg in raw_msgs:
            if msg.author == bot.user:
                # Извлекаем ответ бота из embed.description или контента
                text = ""
                if msg.embeds:
                    for emb in msg.embeds:
                        if emb.description:
                            text += emb.description + "\n"
                if msg.content:
                    clean = msg.content
                    if not clean.startswith("Уважаемый"):
                        text += clean
                text = text.strip()
                if text:
                    history.append(("ASCENT HELPER (ИИ)", text))
            else:
                author_name = msg.author.display_name
                text = msg.clean_content.strip()
                if text:
                    history.append((f"Игрок ({author_name})", text))
    except Exception as e:
        logger.error(f"Ошибка при получении истории сообщений ветки: {e}")

    return history


@bot.event
async def on_message(message: discord.Message):
    """Обработка сообщений в канале помощи или при упоминании бота."""
    if message.author.bot:
        return

    # Проверяем, упоминается ли бот напрямую
    is_mentioned = bot.user in message.mentions if bot.user else False

    # Проверяем канал помощи и ветки
    parent_id = getattr(message.channel, "parent_id", None)
    if parent_id is None and hasattr(message.channel, "parent") and message.channel.parent:
        parent_id = message.channel.parent.id

    is_help_channel = bool(config.HELP_CHANNEL_ID and message.channel.id == config.HELP_CHANNEL_ID)
    is_help_thread = bool(
        config.HELP_CHANNEL_ID
        and isinstance(message.channel, discord.Thread)
        and parent_id == config.HELP_CHANNEL_ID
    )

    if is_help_channel or is_help_thread or is_mentioned:
        clean_content = message.clean_content
        if bot.user:
            clean_content = clean_content.replace(f"@{bot.user.display_name}", "")
        clean_content = clean_content.strip()

        if not clean_content:
            if not is_help_channel:
                await message.reply("Здравствуйте! Пожалуйста, сформулируйте Ваш вопрос касательно соревновательного регламента или правил ASCENT LEAGUE (например: `/ask разрешён ли Rapid Trigger?`).")
            return

        # Проверка ограничения частоты запросов от игрока
        is_admin = is_user_admin(message.author)
        is_limited, reason, retry_after = rate_limiter.is_rate_limited(message.author.id, is_admin=is_admin)
        if is_limited:
            # Защита от спам-атак на бота: отправляем уведомление СТРОГО 1 раз за период кулдауна
            if not rate_limiter.should_notify(message.author.id):
                # Повторные сообщения во время активного кд полностью игнорируются
                return

            time_str = rate_limiter.format_time(retry_after)
            if reason == "cooldown":
                desc = (
                    f"Уважаемый(-ая) {message.author.mention}!\n\n"
                    f"Установлена пауза между вопросами (**{config.RATE_LIMIT_COOLDOWN_SECONDS} сек.**).\n"
                    f"Пожалуйста, подождите ещё **{time_str}** перед отправкой следующего вопроса."
                )
            else:
                desc = (
                    f"Уважаемый(-ая) {message.author.mention}!\n\n"
                    f"Вы исчерпали суточный лимит обращений (максимум **{config.RATE_LIMIT_MAX_REQUESTS} вопросов в день**).\n"
                    f"Доступ к новым вопросам восстановится через **{time_str}**."
                )

            embed = discord.Embed(
                title="⏳ Ограничение частоты запросов",
                description=desc,
                color=EMBED_COLOR
            )

            # Отправляем сообщение в тот же канал с авто-удалением через 6 секунд (не засоряет чат)
            try:
                await message.channel.send(content=f"{message.author.mention}", embed=embed, delete_after=6)
            except Exception:
                pass
            return

        rate_limiter.record_request(message.author.id)

        # Если сообщение написано в основном канале помощи — создаем ветку для ответа
        if is_help_channel and isinstance(message.channel, discord.TextChannel):
            thread_title = clean_content.replace("\n", " ")
            if len(thread_title) > 60:
                thread_title = thread_title[:57] + "..."
            thread_name = f"⚖️ Обращение: {thread_title}"

            thread = None
            try:
                # Создаем ветку на сообщении пользователя
                thread = await message.create_thread(
                    name=thread_name,
                    auto_archive_duration=1440  # 24 часа неактивности
                )
            except discord.HTTPException as e:
                if e.code == 160004 or "already been created" in str(e):
                    thread = message.thread
                    if not thread and hasattr(message.channel, "threads"):
                        thread = discord.utils.get(message.channel.threads, id=message.id)
                else:
                    logger.error(f"Ошибка HTTP при создании ветки: {e}")
            except discord.Forbidden:
                logger.warning("У бота нет прав на создание веток в канале помощи (требуется 'Create Public Threads'). Отвечаем в канале.")
            except Exception as e:
                logger.error(f"Ошибка при создании ветки: {e}")

            if thread:
                async with thread.typing():
                    answer = await ai.generate_answer(clean_content, author_name=message.author.display_name)
                    embed = discord.Embed(
                        title="⚖️ Официальное разъяснение ASCENT LEAGUE",
                        description=answer[:4000],
                        color=EMBED_COLOR
                    )
                    embed.set_footer(text=f"{config.SERVER_NAME} • Заявитель: {message.author.display_name}")
                    feedback_view = FeedbackView(question=clean_content, answer=answer)
                    await thread.send(
                        content=f"Уважаемый(-ая) {message.author.mention}, для рассмотрения Вашего обращения сформирована данная ветка:",
                        embed=embed,
                        view=feedback_view
                    )
                return

        # Если сообщение внутри существующей ветки помощи или при прямом упоминании
        chat_history = None
        if isinstance(message.channel, discord.Thread):
            chat_history = await get_thread_history(message.channel, message)

        async with message.channel.typing():
            answer = await ai.generate_answer(
                clean_content,
                author_name=message.author.display_name,
                chat_history=chat_history
            )
            
            embed = discord.Embed(
                title="⚖️ Официальное разъяснение ASCENT LEAGUE",
                description=answer[:4000],
                color=EMBED_COLOR
            )
            embed.set_footer(text=f"{config.SERVER_NAME} • Заявитель: {message.author.display_name}")
            feedback_view = FeedbackView(question=clean_content, answer=answer)
            await message.reply(embed=embed, view=feedback_view)


    await bot.process_commands(message)


def main():
    if not config.DISCORD_TOKEN:
        print("\n" + "=" * 60)
        print("❌ ОШИБКА: DISCORD_TOKEN не указан в файле .env!")
        print("1. Откройте файл .env в папке бота.")
        print("2. Вставьте ваш DISCORD_TOKEN и GEMINI_API_KEY.")
        print("3. Запустите бота снова через run.bat!")
        print("Подробная инструкция в README.md")
        print("=" * 60 + "\n")
        return

    print("🚀 Запуск Discord бота...")
    bot.run(config.DISCORD_TOKEN)


if __name__ == "__main__":
    main()
