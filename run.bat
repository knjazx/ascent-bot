@echo off
chcp 65001 > nul
title Discord Server Assistant Bot
echo ======================================================
echo           Запуск Discord Helper AI Бота...
echo ======================================================
echo.

if not exist venv (
    echo [!] Виртуальное окружение не найдено, создаем...
    python -m venv venv
    call venv\Scripts\activate.bat
    pip install -r requirements.txt
) else (
    call venv\Scripts\activate.bat
)

if not exist .env (
    echo [!] Файл .env не найден! Создаю копию из .env.example...
    copy .env.example .env
    echo [!] Пожалуйста, откройте файл .env и введите ваш DISCORD_TOKEN и GEMINI_API_KEY!
    pause
    exit /b
)

python bot.py
pause
