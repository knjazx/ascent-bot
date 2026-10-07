import time
from collections import defaultdict
from typing import Optional, Tuple
import config


class UserRateLimiter:
    """Управление лимитами запросов к ИИ для предотвращения спама."""

    def __init__(
        self,
        max_requests: int = 5,
        window_seconds: int = 86400,
        cooldown_seconds: int = 60
    ):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.cooldown_seconds = cooldown_seconds
        self.requests = defaultdict(list)
        self.last_request = {}

    def format_time(self, seconds: int) -> str:
        """Красиво форматирует секунды в читаемый вид (часы, минуты, секунды)."""
        if seconds < 60:
            return f"{seconds} сек."
        elif seconds < 3600:
            minutes = seconds // 60
            secs = seconds % 60
            return f"{minutes} мин. {secs} сек." if secs > 0 else f"{minutes} мин."
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            return f"{hours} ч. {minutes} мин." if minutes > 0 else f"{hours} ч."

    def is_rate_limited(self, user_id: int, is_admin: bool = False) -> Tuple[bool, Optional[str], Optional[int]]:
        """
        Проверяет, превысил ли пользователь лимит запросов.
        
        :param user_id: ID пользователя Discord
        :param is_admin: Имеет ли пользователь права администратора (байпас лимитов)
        :return: (is_limited: bool, reason: str | None, retry_after_seconds: int | None)
                 reason может быть 'cooldown' или 'daily_limit'
        """
        if is_admin:
            return False, None, None

        now = time.time()

        # 1. Проверка паузы (cooldown) между подряд идущими вопросами (60 сек)
        last_time = self.last_request.get(user_id, 0)
        cooldown_remaining = int(self.cooldown_seconds - (now - last_time))
        if cooldown_remaining > 0:
            return True, "cooldown", cooldown_remaining

        # 2. Очистка меток времени за пределами скользящего окна (24 часа)
        timestamps = [t for t in self.requests[user_id] if now - t < self.window_seconds]
        self.requests[user_id] = timestamps

        # 3. Проверка максимального числа вопросов за день (5 вопросов)
        if len(timestamps) >= self.max_requests:
            oldest_in_window = timestamps[0]
            retry_after = int(self.window_seconds - (now - oldest_in_window)) + 1
            return True, "daily_limit", max(1, retry_after)

        return False, None, None

    def get_remaining_requests(self, user_id: int, is_admin: bool = False) -> int:
        """Возвращает количество оставшихся запросов на сегодня."""
        if is_admin:
            return 999
        now = time.time()
        timestamps = [t for t in self.requests[user_id] if now - t < self.window_seconds]
        return max(0, self.max_requests - len(timestamps))

    def record_request(self, user_id: int):
        """Регистрирует выполненный запрос пользователя."""
        now = time.time()
        self.last_request[user_id] = now
        self.requests[user_id].append(now)
