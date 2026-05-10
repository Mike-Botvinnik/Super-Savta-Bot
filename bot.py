import csv
import datetime
import os
import json

import gspread
from oauth2client.service_account import ServiceAccountCredentials

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
GOOGLE_CREDENTIALS = os.getenv("GOOGLE_CREDENTIALS")

if not TELEGRAM_TOKEN or not OPENAI_API_KEY:
    raise ValueError("Нет TELEGRAM_TOKEN или OPENAI_API_KEY")

client = AsyncOpenAI(api_key=OPENAI_API_KEY)


# ---------------- GOOGLE SHEETS ----------------

def init_google_sheets():
    if not GOOGLE_CREDENTIALS:
        print("Google Sheets отключен (нет переменной)")
        return None

    try:
        creds_dict = json.loads(GOOGLE_CREDENTIALS)

        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"
        ]

        creds = ServiceAccountCredentials.from_json_keyfile_dict(
            creds_dict,
            scope
        )

        client_gs = gspread.authorize(creds)

        sheet = client_gs.open("logs").sheet1

        print("Google Sheets подключен")

        return sheet

    except Exception as e:
        print("Ошибка подключения Google Sheets:", e)
        return None


sheet = init_google_sheets()


# ---------------- LOGGING ----------------

def log_event(user_id, event, text=""):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # CSV fallback
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    log_file = f"logs-{today}.csv"

    file_exists = os.path.isfile(log_file)

    with open(log_file, "a", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)

        if not file_exists:
            writer.writerow(["timestamp", "user_id", "event", "text"])

        writer.writerow([now, user_id, event, text])

    # Google Sheets
    if sheet:
        try:
            sheet.append_row([now, user_id, event, text])
        except Exception as e:
            print("Ошибка Google Sheets:", e)


# ---------------- QUICK CHECK ----------------

def quick_check(text):
    t = text.lower()

    if "код" in t and "http" in t:
        return "🚨 ОПАСНО", "Просят код и есть ссылка"

    if "срочно" in t and "деньги" in t:
        return "🚨 ОПАСНО", "Просят деньги и торопят"

    return None


# ---------------- BOT ----------------

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет. Я помогаю проверять сообщения на мошенничество.\n\n"
        "Просто перешлите сюда сообщение из SMS или WhatsApp — "
        "я помогу понять, безопасно ли это."
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user_id = update.message.from_user.id
    user_text = update.message.text.strip()

    # Быстрая проверка
    qc = quick_check(user_text)

    if qc:
        await update.message.reply_text(
            f"{qc[0]}\n\n"
            f"Почему:\n"
            f"– {qc[1]}\n\n"
            f"Что делать:\n"
            f"– не отвечайте\n"
            f"– ничего не отправляйте"
        )

        await update.message.reply_text(
            "Если есть сомнения — лучше не отвечать и спросить ещё раз."
        )

        return

    log_event(user_id, "CHECK_MESSAGE", user_text)

    prompt = f"""
Ты помощник, который защищает людей от мошенничества.

Проверь сообщение и выбери только один вариант:
🚨 ОПАСНО
⚠️ ПОДОЗРИТЕЛЬНО
✅ БЕЗОПАСНО

Определи тип (если есть):
– Банк / карта
– Посылка / доставка
– Родственник / знакомый
– Выигрыш / приз
– Работа / заработок
– Другое

Ответ строго в формате:

🚨 ОПАСНО / ⚠️ ПОДОЗРИТЕЛЬНО / ✅ БЕЗОПАСНО

Тип: коротко

Почему:
– причина 1
– причина 2

Что делать:
– простой совет 1
– простой совет 2

Пиши очень просто, как для пожилого человека.
Если есть сомнение — лучше указать, что это подозрительно.
Не используй сложные слова.

Сообщение:
{user_text}
"""

    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
            temperature=0.3,
        )

        result = response.choices[0].message.content.strip()

        await update.message.reply_text(result)

        await update.message.reply_text(
            "Если есть сомнения — лучше не отвечать и спросить ещё раз."
        )

        if result.startswith("🚨"):
            log_event(user_id, "RESULT_DANGEROUS")

            await update.message.reply_text(
                "Это распространённая схема — вы не один, кому такое прислали."
            )

        elif result.startswith("⚠️"):
            log_event(user_id, "RESULT_SUSPICIOUS")

            await update.message.reply_text(
                "Это распространённая схема — вы не один, кому такое прислали."
            )

        elif result.startswith("✅"):
            log_event(user_id, "RESULT_SAFE")

        keyboard = InlineKeyboardMarkup(
            [[
                InlineKeyboardButton("Да", callback_data="yes"),
                InlineKeyboardButton("Нет", callback_data="no"),
            ]]
        )

        await update.message.reply_text(
            "Было полезно?",
            reply_markup=keyboard
        )

    except Exception as e:
        print("OPENAI ERROR:", e)

        log_event(user_id, "OPENAI_ERROR", str(e))

        await update.message.reply_text(
            "Сейчас не получилось проверить сообщение. Попробуйте ещё раз позже."
        )


async def handle_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    if not query:
        return

    await query.answer()

    user_id = query.from_user.id

    if query.data == "yes":
        log_event(user_id, "FEEDBACK_YES")
        await query.edit_message_text("Спасибо за отзыв ❤️")

    else:
        log_event(user_id, "FEEDBACK_NO")
        await query.edit_message_text("Спасибо. Мы будем улучшать бота ❤️")


# ---------------- MAIN ----------------

def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message
        )
    )

    app.add_handler(CallbackQueryHandler(handle_feedback))

    print("Бот запущен")

    app.run_polling()


if __name__ == "__main__":
    main()