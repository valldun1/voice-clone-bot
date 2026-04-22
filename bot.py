"""
Voice Clone Bot — Telegram бот
Deploy: Railway (git push)
Env vars: TELEGRAM_TOKEN, CAPTAIN_ID
"""
import os
import base64
import logging
from io import BytesIO

import httpx
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
CAPTAIN_ID = int(os.environ.get("CAPTAIN_ID", "5838842946"))

# Динамический URL бэкенда (Colab ngrok)
backend_url: str = ""

# In-memory: user_id → ref_audio bytes
user_voices: dict[int, bytes] = {}


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎙️ *Voice Clone Bot*\n\n"
        "1️⃣ Отправь голосовое (3–10 сек) — это образец голоса\n"
        "2️⃣ Напиши текст — бот озвучит его твоим голосом\n"
        "3️⃣ Можешь отправлять тексты подряд или сменить голос\n\n"
        "Начинай — запиши голосовое 🎤",
        parse_mode="Markdown",
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status = "🟢 онлайн" if backend_url else "🔴 оффлайн"
    await update.message.reply_text(
        f"🔹 /start — начать\n"
        f"🔹 /voice — сменить голос\n"
        f"🔹 /status — проверить сервер\n"
        f"🔹 /help — справка\n\n"
        f"Сервер: {status}\n"
        f"Голосовое: 3–10 секунд, чистый голос без шума."
    )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not backend_url:
        await update.message.reply_text("🔴 Сервер не подключён. Капитан ещё не запустил Colab.")
        return

    try:
        health_url = backend_url.replace("/generate", "/health")
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(health_url)
            data = r.json()
        await update.message.reply_text(f"🟢 Сервер онлайн\nGPU: {data.get('gpu', '?')}")
    except Exception:
        await update.message.reply_text("🔴 Сервер не отвечает. Colab мог отключиться.")


async def cmd_seturl(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Устанавливает URL бэкенда (Colab ngrok). Только капитан."""
    if update.effective_user.id != CAPTAIN_ID:
        await update.message.reply_text("⛔ Только капитан может менять URL")
        return

    if not context.args:
        await update.message.reply_text("Использование: /seturl https://xxxx.ngrok-free.app/generate")
        return

    global backend_url
    backend_url = context.args[0].strip()

    # Проверяем доступность
    try:
        health_url = backend_url.replace("/generate", "/health")
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(health_url)
            data = r.json()
        await update.message.reply_text(
            f"✅ Бэкенд подключён!\n"
            f"GPU: {data.get('gpu', '?')}\n"
            f"URL: {backend_url}\n\n"
            f"Бот готов к работе 🎤"
        )
    except Exception as e:
        await update.message.reply_text(
            f"⚠️ URL сохранён, но сервер не отвечает:\n{e}\n\n"
            f"Проверь что Colab запущен."
        )


async def cmd_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in user_voices:
        del user_voices[user_id]
    await update.message.reply_text("🎤 Отправь новое голосовое сообщение (3–10 сек)")


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    voice = update.message.voice or update.message.audio
    if not voice:
        return

    if voice.duration and voice.duration > 15:
        await update.message.reply_text("⚠️ Слишком длинное — нужно 3–10 секунд.")
        return

    if voice.duration and voice.duration < 2:
        await update.message.reply_text("⚠️ Слишком короткое — минимум 3 секунды.")
        return

    file = await context.bot.get_file(voice.file_id)
    audio_bytes = await file.download_as_bytearray()

    user_voices[update.effective_user.id] = bytes(audio_bytes)

    await update.message.reply_text(
        "✅ Голос принят! Теперь отправь текст для озвучки ✍️\n\n"
        "💡 Можешь отправлять несколько текстов подряд."
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if not text:
        return

    if not backend_url:
        await update.message.reply_text(
            "🔴 Сервер не запущен. Попроси капитана запустить Colab."
        )
        return

    if user_id not in user_voices:
        await update.message.reply_text("🎤 Сначала отправь голосовое (3–10 сек)")
        return

    ref_audio = user_voices[user_id]
    msg = await update.message.reply_text("⏳ Генерирую озвучку...")

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                backend_url,
                json={
                    "audio_base64": base64.b64encode(ref_audio).decode(),
                    "text": text,
                },
            )
            response.raise_for_status()
            result = response.json()

        audio_bytes = base64.b64decode(result["audio_base64"])
        duration = result.get("duration_sec", 0)

        audio_file = BytesIO(audio_bytes)
        audio_file.name = "clone.wav"

        await update.message.reply_voice(voice=audio_file)
        await msg.edit_text(f"🎧 Готово! ({duration} сек)\n\nЕщё текст или новое голосовое 🎤")

    except httpx.TimeoutException:
        logger.error("Backend timeout for user %s", user_id)
        await msg.edit_text("⏰ Таймаут. Попробуй короче текст или проверь /status")

    except Exception as e:
        logger.error("Generation error for user %s: %s", user_id, e)
        await msg.edit_text("❌ Ошибка. Проверь /status — возможно Colab отключился.")


def main():
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("help", cmd_help))
    application.add_handler(CommandHandler("status", cmd_status))
    application.add_handler(CommandHandler("seturl", cmd_seturl))
    application.add_handler(CommandHandler("voice", cmd_voice))
    application.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("Voice Clone Bot started (waiting for /seturl)")
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
