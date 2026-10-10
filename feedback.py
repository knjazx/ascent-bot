import logging
import discord
from discord import ui
import config

logger = logging.getLogger("DiscordBot")


async def get_target_logs_channel(client: discord.Client, guild: discord.Guild = None) -> discord.TextChannel | None:
    """
    Находит канал для логов:
    1. По сохранённому ID (из команды или .env/settings.json)
    2. Автоматическим поиском по названиям каналов сервера (bot-logs, логи, logs, отзывы)
    """
    # 1. По ID
    logs_channel_id = config.get_logs_channel_id()
    if logs_channel_id:
        ch = client.get_channel(logs_channel_id)
        if not ch:
            try:
                ch = await client.fetch_channel(logs_channel_id)
            except Exception as e:
                logger.debug(f"Не удалось получить канал логов по ID {logs_channel_id}: {e}")
                ch = None
        if ch and isinstance(ch, discord.TextChannel):
            return ch

    # 2. Авто-поиск по ключевым именам каналов
    guilds_to_check = [guild] if guild else client.guilds
    for g in guilds_to_check:
        if not g:
            continue
        for ch in g.text_channels:
            name_clean = ch.name.lower().replace("-", "_").replace(" ", "_")
            if any(key in name_clean for key in ["bot_log", "лог", "log", "отзыв", "feedback"]):
                config.set_logs_channel_id(ch.id)
                logger.info(f"Автоматически определён канал логов: #{ch.name} (ID: {ch.id})")
                return ch
    return None


async def log_bot_activity(
    client: discord.Client,
    title: str,
    color: discord.Color,
    user: discord.User | discord.Member,
    location_str: str,
    fields: list[tuple[str, str, bool]] = None,
    guild: discord.Guild = None
):
    """Отправляет структурированный лог в назначенный канал логов."""
    channel = await get_target_logs_channel(client, guild=guild)
    if not channel:
        logger.debug(f"Канал логов не найден. Пропуск логирования '{title}'.")
        return

    embed = discord.Embed(
        title=title,
        color=color,
        timestamp=discord.utils.utcnow()
    )
    embed.add_field(
        name="👤 Пользователь",
        value=f"{user.mention} (`{user.display_name}`)",
        inline=True
    )
    embed.add_field(
        name="📍 Локация",
        value=location_str,
        inline=True
    )

    if fields:
        for name, val, inline in fields:
            embed.add_field(name=name, value=val, inline=inline)

    embed.set_footer(text=f"{config.SERVER_NAME} • Журнал активности")
    try:
        await channel.send(embed=embed)
    except Exception as e:
        logger.error(f"Ошибка отправки сообщения в канал логов {channel.id}: {e}")


class FeedbackNegativeModal(ui.Modal, title="Отзыв: Что не так с ответом?"):
    """Модальное окно для указания причины недовольства ответом бота."""

    reason_input = ui.TextInput(
        label="Что не так с ответом бота?",
        style=discord.TextStyle.paragraph,
        placeholder="Укажите, что исправить: неверный пункт правил, нет ответа по сути, устаревшая инфа...",
        required=False,
        max_length=600
    )

    def __init__(self, question: str, answer: str, parent_view: "FeedbackView"):
        super().__init__()
        self.question = question
        self.answer = answer
        self.parent_view = parent_view

    async def on_submit(self, interaction: discord.Interaction):
        self.parent_view.voted_users.add(interaction.user.id)
        reason_text = self.reason_input.value.strip() or "*(Причина не указана)*"

        # Ответ пользователю (виден только ему)
        await interaction.response.send_message(
            "✅ **Спасибо за обратную связь!** Ваше замечание передано руководству Лиги для улучшения базы знаний.",
            ephemeral=True
        )

        loc_str = interaction.channel.mention if hasattr(interaction.channel, "mention") else "Личные сообщения"
        ans_preview = self.answer[:1000] + ("..." if len(self.answer) > 1000 else "")

        await log_bot_activity(
            client=interaction.client,
            title="👎 Отрицательный отзыв на ответ бота",
            color=discord.Color.red(),
            user=interaction.user,
            location_str=loc_str,
            fields=[
                ("⚠️ Замечание / Причина", f"```\n{reason_text}\n```", False),
                ("❓ Вопрос участника", f"*{self.question[:450]}*", False),
                ("🤖 Ответ бота", ans_preview, False)
            ],
            guild=interaction.guild
        )


class FeedbackView(ui.View):
    """Интерактивные кнопки оценки ответа под каждым сообщением бота."""

    def __init__(self, question: str, answer: str):
        super().__init__(timeout=86400)  # Активны 24 часа
        self.question = question
        self.answer = answer
        self.voted_users = set()

    @ui.button(label="Полезно", style=discord.ButtonStyle.secondary, emoji="👍", custom_id="btn_feedback_like")
    async def like_button(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id in self.voted_users:
            await interaction.response.send_message("Вы уже оценили этот ответ.", ephemeral=True)
            return

        self.voted_users.add(interaction.user.id)
        await interaction.response.send_message("✅ **Спасибо за отзыв!** Рады, что ответ помог.", ephemeral=True)

        loc_str = interaction.channel.mention if hasattr(interaction.channel, "mention") else "Личные сообщения"
        ans_preview = self.answer[:600] + ("..." if len(self.answer) > 600 else "")

        await log_bot_activity(
            client=interaction.client,
            title="👍 Положительный отзыв",
            color=discord.Color.green(),
            user=interaction.user,
            location_str=loc_str,
            fields=[
                ("❓ Вопрос", f"*{self.question[:450]}*", False),
                ("🤖 Ответ бота", ans_preview, False)
            ],
            guild=interaction.guild
        )

    @ui.button(label="Не помогло", style=discord.ButtonStyle.secondary, emoji="👎", custom_id="btn_feedback_dislike")
    async def dislike_button(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id in self.voted_users:
            await interaction.response.send_message("Вы уже оценили этот ответ.", ephemeral=True)
            return

        modal = FeedbackNegativeModal(self.question, self.answer, self)
        await interaction.response.send_modal(modal)
