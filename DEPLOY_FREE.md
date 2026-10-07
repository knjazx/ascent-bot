# 🚀 Инструкция: Бесплатный хостинг Discord-бота 24/7 (0 рублей, без карты)

Данный бот полностью подготовлен к бесплатному запуску на облачных платформах. В него уже вшит [`Dockerfile`](file:///C:/Users/knjazxx/.gemini/antigravity/scratch/discord-helper-bot/Dockerfile) и встроенный HTTP-сервер для поддержания активности.

---

## 🥇 Вариант 1 (Рекомендуемый): Hugging Face Spaces
> **Условия:** 100% бесплатно навсегда, 2 CPU, 16 ГБ оперативной памяти, без привязки банковской карты, серверы в Европе (Gemini работает напрямую).

### Шаги запуска:
1. Зарегистрируйтесь на сайте [huggingface.co](https://huggingface.co/).
2. В правом верхнем углу нажмите на аватарку ➔ **«New Space»**.
3. Заполните форму:
   * **Space name:** любое имя (например, `ascent-league-bot`)
   * **License:** `mit` или оставьте пустым
   * **Space SDK:** выберите **Docker** ➔ **Blank**
   * **Space Hardware:** оставьте бесплатный **CPU basic (2 vCPU · 16 GB · Free)**
   * **Visibility:** `Public` или `Private` (любой, ваши ключи всё равно будут спрятаны)
   * Нажмите **«Create Space»**.
4. Добавьте секретные ключи:
   * Перейдите во вкладку **«Settings»** вашего Space.
   * Прокрутите вниз до раздела **«Variables and secrets»** ➔ нажмите **«New secret»**.
   * Добавьте по очереди 4 секрета:
     1. `DISCORD_TOKEN` = Ваш токен бота Discord
     2. `GEMINI_API_KEY` = Ваш API ключ Google Gemini
     3. `SERVER_NAME` = `ASCENT LEAGUE`
     4. `HELP_CHANNEL_ID` = ID канала для создания веток (например, `123456789...`)
5. Загрузите файлы проекта:
   * Откройте вкладку **«Files»** в Space ➔ нажмите **«Add file»** ➔ **«Upload files»**.
   * Перетащите все файлы из папки `discord-helper-bot`:
     * `Dockerfile`
     * `requirements.txt`
     * `bot.py`
     * `ai_helper.py`
     * `config.py`
     * `rate_limiter.py`
     * Папку `knowledge/` со всеми `.md` файлами
   * Внизу нажмите зелёную кнопку **«Commit changes to main»**.
6. **Готово!** Hugging Face автоматически соберёт контейнер за 1–2 минуты. Статус изменится на **Running**, и бот появится в сети на вашем Discord-сервере 24/7!

---

## 🥈 Вариант 2: Render.com + UptimeRobot
> **Условия:** 750 бесплатных часов в месяц (хватает на полный месяц непрерывной работы), регистрация через GitHub без карты.

### Шаги запуска:
1. Загрузите проект в ваш приватный или публичный репозиторий на [GitHub](https://github.com/).
2. Зарегистрируйтесь на [render.com](https://render.com/) через ваш аккаунт GitHub.
3. В панели Render нажмите **«New +»** ➔ **«Web Service»**.
4. Выберите ваш репозиторий с ботом.
5. Настройки:
   * **Runtime:** `Python 3` (или `Docker`)
   * **Build Command:** `pip install -r requirements.txt`
   * **Start Command:** `python bot.py`
   * **Instance Type:** `Free` (0$/mo)
6. В разделе **«Environment Variables»** добавьте те же переменные:
   * `DISCORD_TOKEN`
   * `GEMINI_API_KEY`
   * `SERVER_NAME`
   * `HELP_CHANNEL_ID`
7. Нажмите **«Deploy Web Service»**.
8. **Защита от засыпания (UptimeRobot):**
   * Скопируйте полученную ссылку на ваш сервис в Render (вида `https://ascent-bot.onrender.com`).
   * Зарегистрируйтесь на бесплатном сервисе [uptimerobot.com](https://uptimerobot.com/).
   * Нажмите **«Add New Monitor»**:
     * **Monitor Type:** `HTTP(s)`
     * **Friendly Name:** `Discord Bot`
     * **URL:** вставьте вашу ссылку с Render
     * **Monitoring Interval:** `5 minutes`
   * UptimeRobot будет пинговать бота каждые 5 минут, и Render никогда не уйдёт в спящий режим!
