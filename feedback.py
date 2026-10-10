import logging
import discord
from discord import ui
import config

logger = logging.getLogger("DiscordBot")


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

        # Отправка подробного лога в канал логов Лиги
        logs_channel_id = config.get_logs_channel_id()
        if logs_channel_id:
            channel = interaction.client.get_channel(logs_channel_id)
            if not channel:
                try:
                    channel = await interaction.client.fetch_channel(logs_channel_id)
                except Exception as e:
                    logger.debug(f"Не удалось получить канал логов {logs_channel_id}: {e}")
                    channel = None

            if channel:
                embed = discord.Embed(
                    title="👎 Отрицательный отзыв на ответ бота",
                    color=discord.Color.red(),
                    timestamp=discord.utils.utcnow()
                )
                embed.add_field(
                    name="👤 Автор вопроса",
                    value=f"{interaction.user.mention} (`{interaction.user.display_name}`)",
                    inline=True
                )
                embed.add_field(
                    name="📍 Локация",
                    value=interaction.channel.mention if hasattr(interaction.channel, "mention") else "Личные сообщения",
                    inline=True
                )
                embed.add_field(
                    name="⚠️ Замечание / Причина",
                    value=f"```\n{reason_text}\n```",
                    inline=False
                )
                embed.add_field(
                    name="❓ Вопрос участника",
                    value=f"*{self.question[:450]}*",
                    inline=False
                )
                ans_preview = self.answer[:1000] + ("..." if len(self.answer) > 1000 else "")
                embed.add_field(
                    name="🤖 Ответ бота",
                    value=ans_preview,
                    inline=False
                )
                embed.set_footer(text=f"{config.SERVER_NAME} • Аналитика базы знаний")
                try:
                    await channel.send(embed=embed)
                except Exception as e:
                    logger.error(f"Ошибка отправки лога в канал {logs_channel_id}: {e}")


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

        logs_channel_id = config.get_logs_channel_id()
        if logs_channel_id:
            channel = interaction.client.get_channel(logs_channel_id)
            if not channel:
                try:
                    channel = await interaction.client.fetch_channel(logs_channel_id)
                except Exception:
                    channel = None

            if channel:
                embed = discord.Embed(
                    title="👍 Положительный отзыв",
                    color=discord.Color.green(),
                    timestamp=discord.utils.utcnow()
                )
                embed.add_field(
                    name="👤 Автор",
                    value=f"{interaction.user.mention} (`{interaction.user.display_name}`)",
                    inline=True
                )
                embed.add_field(
                    name="📍 Локация",
                    value=interaction.channel.mention if hasattr(interaction.channel, "mention") else "Личные сообщения",
                    inline=True
                )
                embed.add_field(
                    name="❓ Вопрос",
                    value=f"*{self.question[:450]}*",
                    inline=False
                )
                ans_preview = self.answer[:600] + ("..." if len(self.answer) > 600 else "")
                embed.add_field(
                    name="🤖 Ответ бота",
                    value=ans_preview,
                    inline=False
                )
                embed.set_footer(text=f"{config.SERVER_NAME} • Аналитика базы знаний")
                try:
                    await channel.send(embed=embed)
                except Exception as e:
                    logger.error(f"Ошибка отправки лога в канал {logs_channel_id}: {e}")

    @ui.button(label="Не помогло", style=discord.ButtonStyle.secondary, emoji="👎", custom_id="btn_feedback_dislike")
    async def dislike_button(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id in self.voted_users:
            await interaction.response.send_message("Вы уже оценили этот ответ.", ephemeral=True)
            return

        modal = FeedbackNegativeModal(self.question, self.answer, self)
        await interaction.response.send_modal(modal)
