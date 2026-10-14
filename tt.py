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
# 🔑 ตั้งค่า Airtable (ฐานข้อมูลหลัก 100%)
# 🔑 ดึงค่าความลับจาก Environment Variables (ปลอดภัย 100%)
# ---------------------------------------------------------
AIRTABLE_TOKEN = "patQIWF6UL6PXfUC2.8436159311bbebca04f2471c9811a4d18ab89b0713b3a42b42bf17858ecfbc41".strip()
BASE_ID = "appTpva126RduuRno".strip()  
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
@@ -515,34 +529,32 @@
    # รัน Web Server บน Thread แยก เพื่อป้องกัน Port Scan Timeout บน Render
    threading.Thread(target=run_web, daemon=True).start()

    TOKEN = "8833667054:AAGKg3jMULFB3nE41275yphBulgDCTFCw8Q"
    
    request = HTTPXRequest(connect_timeout=30.0, read_timeout=30.0)
    app = ApplicationBuilder().token(TOKEN).request(request).build()
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
