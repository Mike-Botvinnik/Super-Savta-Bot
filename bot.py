import csv
import datetime
import os

from dotenv import load_dotenv
from openai import AsyncOpenAI
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not TELEGRAM_TOKEN or not OPENAI_API_KEY:
    raise ValueError(
        "Не найдены TELEGRAM_TOKEN или OPENAI_API_KEY. Добавь их в файл .env"
    )

client = AsyncOpenAI(api_key=OPENAI_API_KEY)


def log_event(user_id, event, text=""):
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    log_file = f"logs-{today}.csv"
    file_exists = os.path.isfile(log_file)

    with open(log_file, "a", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)

        if not file_exists:
            writer.writerow(["timestamp", "user_id", "event", "text"])

        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        writer.writerow([now, user_id, event, text])


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет. Я проверяю сообщения на мошенничество.\n\n"
        "Просто отправь мне текст сообщения, а я скажу:\n"
        "🚨 ОПАСНО\n"
        "⚠️ ПОДОЗРИТЕЛЬНО\n"
        "✅ БЕЗОПАСНО"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user_id = update.message.from_user.id
    user_text = update.message.text.strip()

    log_event(user_id, "CHECK_MESSAGE", user_text)

    prompt = f"""
Проверь сообщение и определи, насколько оно опасно.

Используй только один из трех вариантов:
🚨 ОПАСНО
⚠️ ПОДОЗРИТЕЛЬНО
✅ БЕЗОПАСНО

После этого:
1. Напиши короткое объяснение простым языком
2. Дай короткий и понятный совет, что делать дальше

Если сообщение явно мошенническое, советуй не отвечать, не переходить по ссылкам, не отправлять деньги, не сообщать коды и при необходимости заблокировать отправителя.
Если сообщение подозрительное, советуй быть осторожнее, ничего не нажимать и сначала все проверить.
Если сообщение выглядит безопасным, советуй все равно сохранять внимательность, если отправитель незнакомый.

Не используй другие смайлики, значки, списки, кавычки или лишний текст.

Отвечай строго в формате:

🚨 ОПАСНО

объяснение

Совет: короткий совет

или

⚠️ ПОДОЗРИТЕЛЬНО

объяснение

Совет: короткий совет

или

✅ БЕЗОПАСНО

объяснение

Совет: короткий совет

Сообщение:
{user_text}
"""

    try:
        response = await client.chat.completions.create(
            model="gpt-5-nano",
            messages=[{"role": "user", "content": prompt}],
        )

        result = response.choices[0].message.content.strip()
        await update.message.reply_text(result)

        if result.startswith("🚨 ОПАСНО"):
            log_event(user_id, "RESULT_DANGEROUS")
        elif result.startswith("⚠️ ПОДОЗРИТЕЛЬНО"):
            log_event(user_id, "RESULT_SUSPICIOUS")
        elif result.startswith("✅ БЕЗОПАСНО"):
            log_event(user_id, "RESULT_SAFE")

        keyboard = InlineKeyboardMarkup(
            [[
                InlineKeyboardButton("Да", callback_data="feedback_yes"),
                InlineKeyboardButton("Нет", callback_data="feedback_no"),
            ]]
        )

        await update.message.reply_text("Было полезно?", reply_markup=keyboard)

    except Exception as e:
        print(e)
        log_event(user_id, "OPENAI_ERROR", str(e))
        await update.message.reply_text(
            "Сейчас не получилось проверить сообщение. Попробуй еще раз чуть позже."
        )


async def handle_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return

    await query.answer()
    user_id = query.from_user.id

    if query.data == "feedback_yes":
        log_event(user_id, "FEEDBACK_YES")
        await query.edit_message_text("Спасибо за отзыв.")
    elif query.data == "feedback_no":
        log_event(user_id, "FEEDBACK_NO")
        await query.edit_message_text("Спасибо за отзыв. Учтем это.")


def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(handle_feedback, pattern="^feedback_"))
    app.run_polling()


if __name__ == "__main__":
    main()
