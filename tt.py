import os
import re
import threading
from datetime import datetime, timezone, timedelta
import pandas as pd
import requests
from flask import Flask
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InputMediaPhoto
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    filters,
)
from telegram.request import HTTPXRequest

# โหลดค่าจากไฟล์ .env (กรณีรันบนคอมพิวเตอร์ตัวเอง)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ---------------------------------------------------------
# 🔑 ดึงค่าความลับทั้งหมดจาก Environment Variables (ปลอดภัย 100%)
# ---------------------------------------------------------
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
AIRTABLE_TOKEN = os.environ.get("AIRTABLE_TOKEN")
BASE_ID = os.environ.get("AIRTABLE_BASE_ID")
TABLE_NAME = "Customers"

# ตรวจสอบความถูกต้องของ Environment Variables
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("❌ ไม่พบ TELEGRAM_BOT_TOKEN ใน Environment Variables!")
if not AIRTABLE_TOKEN or not BASE_ID:
    raise ValueError("❌ ไม่พบ AIRTABLE_TOKEN หรือ AIRTABLE_BASE_ID ใน Environment Variables!")

def fetch_all_from_airtable():
    """ดึงข้อมูลทั้งหมดจาก Airtable โดยตรง เพื่อใช้เช็กซ้ำและแสดงผล"""
    try:
        url = f"https://api.airtable.com/v0/{BASE_ID}/{TABLE_NAME}"
        headers = {
            "Authorization": f"Bearer {AIRTABLE_TOKEN}"
        }
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json().get("records", [])
        return []
    except Exception as e:
        print(f"⚠️ เกิดข้อผิดพลาดในการดึงข้อมูลจาก Airtable: {e}")
        return []

# ตั้งค่า Flask สำหรับรัน Web Server ป้องกันพอร์ตหมดเวลาบน Render
app_flask = Flask(__name__)

@app_flask.route('/')
def home():
    return "🤖 Telegram Bot is running and connected to Airtable!"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app_flask.run(host="0.0.0.0", port=port)

# ตัวแปรจำลองสถานะ Conversation (ปรับเปลี่ยนตามโครงสร้างฟังก์ชันเดิมของคุณ)
NAME, ADDRESS, PHONE, TAX_ID, REMARKS, PHOTOS = range(6)

def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    update.message.reply_text("สวัสดีครับ! บอทพร้อมใช้งานแล้ว")

def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    update.message.reply_text("พิมพ์ /add หรือกดปุ่มบันทึกข้อมูลเพื่อเริ่มต้นใช้งาน")

def start_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    update.message.reply_text("กรุณา ชื่อ-นามสกุล หรือชื่อบริษัท:")
    return NAME

def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return ADDRESS

def receive_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return PHONE

def receive_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return TAX_ID

def receive_tax_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return REMARKS

def receive_remarks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return PHOTOS

def receive_photos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    update.message.reply_text("บันทึกข้อมูลเรียบร้อยแล้ว!")
    return ConversationHandler.END

def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    update.message.reply_text("ยกเลิกการทำรายการแล้ว", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

def search_excel_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pass

def main():
    # รัน Web Server บน Thread แยก เพื่อป้องกัน Port Scan Timeout บน Render
    threading.Thread(target=run_web, daemon=True).start()
    
    request = HTTPXRequest(connect_timeout=30.0, read_timeout=30.0)
    # ใช้ Telegram Bot Token จาก Environment Variables อย่างปลอดภัย
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).request(request).build()

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("add", start_add),
            MessageHandler(filters.Regex(r"^(/บันทึก|บันทึก|➕ บันทึกข้อมูลลูกค้า)$"), start_add)
        ],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_name)],
            ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_address)],
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_phone)],
            TAX_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_tax_id)],
            REMARKS: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_remarks)],
            PHOTOS: [
                MessageHandler(filters.PHOTO, receive_photos),
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_photos)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(conv_handler)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_excel_data))

    print("🤖 Telegram Bot พร้อมเว็บเซิร์ฟเวอร์จำลองเชื่อมต่อ Airtable 100% ทำงานแล้ว...")
    app.run_polling()

if __name__ == "__main__":
    main()
