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

# ================= GOOGLE SHEETS =================

# sheet = None

# try:
 #   if GOOGLE_CREDENTIALS:
    #    scope = [
            # #"https://spreadsheets.google.com/feeds",
            #"https://www.googleapis.com/auth/drive"
   #     ]

   #     creds_dict = #json.loads(GOOGLE_CREDENTIALS)

      #  creds = #ServiceAccountCredentials.from_json_keyf#ile_dict(
         #   creds_dict, scope
     #   )

    #    client_gs = #gspread.authorize(creds)
    #    sheet = #client_gs.open("logs").sheet1

    #    print("Google Sheets подключен")

  #  else:
    #    print("GOOGLE_CREDENTIALS не #найден")

#except Exception as e:
 #   print("Ошибка Google Sheets:", e)

# ================= ЛОГИ #=================

#def log_event(user_id, event, text=""):
 #   now = #datetime.datetime.now().strftime("%Y-%m-#%d %H:%M:%S")

    # Google Sheets
   # try:
  #      if sheet:
   #         sheet.append_row([now, #user_id, event, text])
   # except Exception as e:
      #  print("Ошибка записи в Google #Sheets:", e)

    # CSV fallback
    try:
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        log_file = f"logs-{today}.csv"
        file_exists = os.path.isfile(log_file)

        with open(log_file, "a", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)

            if not file_exists:
                writer.writerow(["timestamp", "user_id", "event", "text"])

            writer.writerow([now, user_id, event, text])

    except Exception as e:
        print("Ошибка CSV:", e)

# ================= КОМАНДЫ =================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет. Я проверяю сообщения на мошенничество.\n\n"
        "Отправь текст — я скажу:\n"
        "🚨 ОПАСНО\n"
        "⚠️ ПОДОЗРИТЕЛЬНО\n"
        "✅ БЕЗОПАСНО"
    )

# ================= ОСНОВНАЯ ЛОГИКА =================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user_id = update.message.from_user.id
    user_text = update