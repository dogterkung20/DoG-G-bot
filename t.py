import os
import re
from datetime import datetime, timezone, timedelta
import pandas as pd
import requests
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

# ---------------------------------------------------------
# 🔑 ตั้งค่า Airtable (ฐานข้อมูลหลัก 100%)
# ---------------------------------------------------------
AIRTABLE_TOKEN = "patQIWF6UL6PXfUC2.8436159311bbebca04f2471c9811a4d18ab89b0713b3a42b42bf17858ecfbc41".strip()
BASE_ID = "appTpva126RduuRno".strip()  
TABLE_NAME = "Customers"

def fetch_all_from_airtable():
    """ดึงข้อมูลทั้งหมดจาก Airtable โดยตรง เพื่อใช้เช็กซ้ำและแสดงผล"""
    try:
        url = f"https://api.airtable.com/v0/{BASE_ID}/{TABLE_NAME}"
        auth_header = f"Bearer {AIRTABLE_TOKEN}".encode('utf-8').decode('latin-1')
        headers = {"Authorization": auth_header}
        
        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code == 200:
            records = response.json().get("records", [])
            rows = []
            for record in records:
                fields = record.get("fields", {})
                rows.append({
                    "วันเวลา": fields.get("วันเวลา", "-"),
                    "ชื่อ": fields.get("ชื่อ", "-"),
                    "ที่อยู่": fields.get("ที่อยู่", "-"),
                    "เบอร์โทร": fields.get("เบอร์โทร", "-"),
                    "เลขผู้เสียภาษี": fields.get("เลขผู้เสียภาษี", "-"),
                    "หมายเหตุ": fields.get("หมายเหตุ", "-"),
                    "รูปถ่าย": fields.get("รูปถ่าย", "-")
                })
            return pd.DataFrame(rows)
    except Exception as e:
        print(f"⚠️ ไม่สามารถดึงข้อมูลจาก Airtable ได้: {e}")
    
    # หากดึงไม่ได้ ให้คืนค่า DataFrame เปล่า
    return pd.DataFrame(columns=["วันเวลา", "ชื่อ", "ที่อยู่", "เบอร์โทร", "เลขผู้เสียภาษี", "หมายเหตุ", "รูปถ่าย"])

def append_to_airtable(row_data):
    """ส่งข้อมูลบันทึกตรงขึ้น Airtable ทันที"""
    try:
        url = f"https://api.airtable.com/v0/{BASE_ID}/{TABLE_NAME}"
        auth_header = f"Bearer {AIRTABLE_TOKEN}".encode('utf-8').decode('latin-1')
        
        headers = {
            "Authorization": auth_header,
            "Content-Type": "application/json; charset=utf-8"
        }
        
        payload = {
            "fields": {
                "วันเวลา": str(row_data["วันเวลา"]),
                "ชื่อ": str(row_data["ชื่อ"]),
                "ที่อยู่": str(row_data["ที่อยู่"]),
                "เบอร์โทร": str(row_data["เบอร์โทร"]),
                "เลขผู้เสียภาษี": str(row_data["เลขผู้เสียภาษี"]),
                "หมายเหตุ": str(row_data["หมายเหตุ"]),
                "รูปถ่าย": str(row_data["รูปถ่าย"])
            }
        }
        
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        
        if response.status_code in [200, 201]:
            print("✅ บันทึกข้อมูลขึ้น Airtable สำเร็จเรียบร้อย!")
            return True, "Success"
        else:
            print(f"⚠️ Airtable Error ({response.status_code}): {response.text}")
            return False, f"Airtable Error ({response.status_code}): {response.text}"
            
    except Exception as e:
        print(f"⚠️ ไม่สามารถเชื่อมต่อ Airtable ได้ : {e}")
        return False, str(e)

# ---------------------------------------------------------
# สถานะการสนทนาและปุ่มเมนู
# ---------------------------------------------------------
NAME, ADDRESS, PHONE, TAX_ID, REMARKS, PHOTOS = range(6)
MONTHS_TH = ["ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.", "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."]

main_menu_markup = ReplyKeyboardMarkup(
    [
        ["➕ บันทึกข้อมูลลูกค้า", "📋 แสดงรายชื่อทั้งหมด"],
        ["📁 โหลดไฟล์ Excel ทั้งหมด", "📖 คู่มือการใช้งาน"]
    ],
    resize_keyboard=True
)

def get_thai_datetime_str():
    tz_th = timezone(timedelta(hours=7))
    now_th = datetime.now(tz_th)
    day = now_th.day
    month = MONTHS_TH[now_th.month - 1]
    full_year = now_th.year + 543
    time_str = now_th.strftime("%H:%M")
    return f"{day} {month} {full_year} เวลา {time_str} น."

async def upload_image_to_cloud(photo_file):
    """อัปโหลดรูปขึ้น Catbox และลบทิ้งจากเครื่องทันที"""
    temp_filename = f"temp_{int(datetime.now().timestamp())}.jpg"
    try:
        await photo_file.download_to_drive(temp_filename)
        url = "https://catbox.moe/user/api.php"
        with open(temp_filename, 'rb') as f:
            response = requests.post(
                url,
                data={"reqtype": "fileupload"},
                files={"fileToUpload": f},
                timeout=30
            )
        if os.path.exists(temp_filename):
            os.remove(temp_filename)
            
        if response.status_code == 200:
            image_url = response.text.strip()
            if image_url.startswith("http"):
                return image_url
    except Exception as e:
        print(f"Upload error: {e}")
        if os.path.exists(temp_filename):
            os.remove(temp_filename)
    return None

# ---------------------------------------------------------
# ระบบบันทึกข้อมูลลูกค้า
# ---------------------------------------------------------
async def start_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['new_customer'] = {}
    context.user_data['photo_urls'] = []
    
    cancel_markup = ReplyKeyboardMarkup([["❌ ยกเลิก"]], resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text(
        "📝 **เริ่มกระบวนการบันทึกข้อมูลลูกค้าใหม่**\n\n"
        "1️⃣ กรุณาพิมพ์ **'ชื่อ-นามสกุล'** ของลูกค้าครับ:",
        reply_markup=cancel_markup
    )
    return NAME

async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "❌ ยกเลิก":
        return await cancel(update, context)
        
    context.user_data['new_customer']['name'] = text
    cancel_markup = ReplyKeyboardMarkup([["❌ ยกเลิก"]], resize_keyboard=True, one_time_keyboard=True)
    
    await update.message.reply_text(
        f"🟢 **ข้อมูลปัจจุบันที่บันทึก:**\n"
        f"👤 ชื่อ: {text}\n\n"
        "2️⃣ กรุณาพิมพ์ **'ที่อยู่'** ของลูกค้าต่อครับ:",
        reply_markup=cancel_markup
    )
    return ADDRESS

async def receive_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "❌ ยกเลิก":
        return await cancel(update, context)
        
    context.user_data['new_customer']['address'] = text
    data = context.user_data['new_customer']
    cancel_markup = ReplyKeyboardMarkup([["❌ ยกเลิก"]], resize_keyboard=True, one_time_keyboard=True)
    
    await update.message.reply_text(
        f"🟢 **ข้อมูลปัจจุบันที่บันทึก:**\n"
        f"👤 ชื่อ: {data.get('name')}\n"
        f"📍 ที่อยู่: {text}\n\n"
        "3️⃣ กรุณาพิมพ์ **'เบอร์โทรศัพท์'** ของลูกค้าครับ:",
        reply_markup=cancel_markup
    )
    return PHONE

async def receive_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "❌ ยกเลิก":
        return await cancel(update, context)
        
    context.user_data['new_customer']['phone'] = text
    data = context.user_data['new_customer']
    cancel_markup = ReplyKeyboardMarkup([["❌ ยกเลิก"]], resize_keyboard=True, one_time_keyboard=True)
    
    await update.message.reply_text(
        f"🟢 **ข้อมูลปัจจุบันที่บันทึก:**\n"
        f"👤 ชื่อ: {data.get('name')}\n"
        f"📍 ที่อยู่: {data.get('address')}\n"
        f"📞 เบอร์โทร: {text}\n\n"
        "4️⃣ กรุณาพิมพ์ **'เลขประจำตัวผู้เสียภาษี'** (หากไม่มีพิมพ์ `-`):",
        reply_markup=cancel_markup
    )
    return TAX_ID

async def receive_tax_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "❌ ยกเลิก":
        return await cancel(update, context)
        
    context.user_data['new_customer']['tax_id'] = text
    data = context.user_data['new_customer']
    cancel_markup = ReplyKeyboardMarkup([["❌ ยกเลิก"]], resize_keyboard=True, one_time_keyboard=True)
    
    await update.message.reply_text(
        f"🟢 **ข้อมูลปัจจุบันที่บันทึก:**\n"
        f"👤 ชื่อ: {data.get('name')}\n"
        f"📍 ที่อยู่: {data.get('address')}\n"
        f"📞 เบอร์โทร: {data.get('phone')}\n"
        f"🏢 เลขผู้เสียภาษี: {text}\n\n"
        "5️⃣ กรุณาพิมพ์ **'หมายเหตุ'** (หากไม่มีพิมพ์ `-`):",
        reply_markup=cancel_markup
    )
    return REMARKS

async def receive_remarks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "❌ ยกเลิก":
        return await cancel(update, context)
        
    context.user_data['new_customer']['remarks'] = text
    data = context.user_data['new_customer']
    
    reply_keyboard = [["เสร็จสิ้น", "❌ ยกเลิก"]]
    await update.message.reply_text(
        f"🟢 **ตรวจสอบข้อมูลภาพรวมก่อนแนบรูป:**\n"
        f"👤 ชื่อ: {data.get('name')}\n"
        f"📍 ที่อยู่: {data.get('address')}\n"
        f"📞 เบอร์โทร: {data.get('phone')}\n"
        f"🏢 เลขผู้เสียภาษี: {data.get('tax_id')}\n"
        f"📝 หมายเหตุ: {text}\n\n"
        "6️⃣ กรุณาส่ง **'รูปถ่ายบัตรประชาชนหรือสำเนาเอกสาร'**\n"
        "*(ส่งได้สูงสุด 5 รูป)* เมื่อส่งครบให้กดปุ่ม **'เสร็จสิ้น'** ด้านล่าง",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True, one_time_keyboard=True)
    )
    return PHOTOS

async def receive_photos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text and update.message.text.strip() == "❌ ยกเลิก":
        return await cancel(update, context)

    photo_urls = context.user_data.setdefault('photo_urls', [])
    
    if update.message.text and update.message.text.strip() == "เสร็จสิ้น":
        return await save_customer_to_airtable_process(update, context)

    if update.message.photo:
        if len(photo_urls) >= 5:
            await update.message.reply_text("⚠️ คุณส่งรูปครบ 5 รูปแล้ว กำลังบันทึกข้อมูลลงระบบครับ...")
            return await save_customer_to_airtable_process(update, context)

        status_msg = await update.message.reply_text("☁️ กำลังอัปโหลดรูปภาพขึ้นคลาวด์...")
        photo_file = await update.message.photo[-1].get_file()
        image_url = await upload_image_to_cloud(photo_file)
        await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=status_msg.message_id)

        if image_url:
            photo_urls.append(image_url)
            remaining = 5 - len(photo_urls)
            if remaining > 0:
                await update.message.reply_text(
                    f"✅ อัปโหลดรูปที่ {len(photo_urls)} สำเร็จ! (อัปโหลดแล้ว {len(photo_urls)} รูป)\n"
                    "ส่งรูปถัดไป หรือกดปุ่ม **'เสร็จสิ้น'** เพื่อบันทึกข้อมูล"
                )
            else:
                await update.message.reply_text("✅ ครบ 5 รูปแล้ว กำลังบันทึกข้อมูล...")
                return await save_customer_to_airtable_process(update, context)
        else:
            await update.message.reply_text("❌ อัปโหลดรูปไม่สำเร็จ กรุณาลองใหม่อีกครั้ง")
        return PHOTOS
    else:
        await update.message.reply_text("⚠️ กรุณาส่งเป็นรูปภาพ หรือกดปุ่ม 'เสร็จสิ้น' / '❌ ยกเลิก'")
        return PHOTOS

async def save_customer_to_airtable_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = context.user_data.get('new_customer', {})
    photo_urls = context.user_data.get('photo_urls', [])
    
    timestamp = get_thai_datetime_str()
    name = data.get('name', '-')
    address = data.get('address', '-')
    phone = data.get('phone', '-')
    tax_id = data.get('tax_id', '-')
    remarks = data.get('remarks', '-')
    
    # 🔍 เช็กข้อมูลซ้ำโดยดึงข้อมูลสดจาก Airtable โดยตรง
    df_airtable = fetch_all_from_airtable()
    duplicate_fields = []
    if not df_airtable.empty:
        if name in df_airtable["ชื่อ"].values:
            duplicate_fields.append("ชื่อ-นามสกุล")
        if phone in df_airtable["เบอร์โทร"].values:
            duplicate_fields.append("เบอร์โทรศัพท์")
        if tax_id != "-" and tax_id in df_airtable["เลขผู้เสียภาษี"].values:
            duplicate_fields.append("เลขประจำตัวผู้เสียภาษี")
            
    if duplicate_fields:
        dup_str = ", ".join(duplicate_fields)
        await update.message.reply_text(
            f"❌ **ไม่สามารถบันทึกได้ เนื่องจากข้อมูลซ้ำในระบบ Airtable!**\n\n"
            f"⚠️ จุดที่ซ้ำ: **{dup_str}**",
            reply_markup=main_menu_markup
        )
        context.user_data.clear()
        return ConversationHandler.END

    photos_str = ", ".join(photo_urls) if photo_urls else "-"

    new_row = {
        "วันเวลา": timestamp,
        "ชื่อ": name,
        "ที่อยู่": address,
        "เบอร์โทร": phone,
        "เลขผู้เสียภาษี": tax_id,
        "หมายเหตุ": remarks,
        "รูปถ่าย": photos_str
    }

    # 🚀 บันทึกตรงขึ้น Airtable ทันที
    success, err_msg = append_to_airtable(new_row)
    
    # ดึงจำนวนรายการล่าสุดจาก Airtable มาแสดงผล
    df_updated = fetch_all_from_airtable()
    total_records = len(df_updated)

    if success:
        sync_status = "✅ **บันทึกและซิงก์ขึ้น Airtable สำเร็จเรียบร้อย!**"
    else:
        sync_status = f"⚠️ **เกิดข้อผิดพลาดในการบันทึก Airtable:**\n`{err_msg}`"

    await update.message.reply_text(
        f"🎉 **สถานะการบันทึกข้อมูล:**\n\n"
        f"{sync_status}\n\n"
        f"📊 ลำดับที่ใน Airtable: **{total_records}**\n"
        f"📅 วันเวลา: {timestamp}\n"
        f"👤 ชื่อ: {name}\n"
        f"📍 ที่อยู่: {address}\n"
        f"📞 เบอร์โทร: {phone}\n"
        f"🏢 เลขผู้เสียภาษี: {tax_id}\n"
        f"📝 หมายเหตุ: {remarks}\n"
        f"🔗 แนบรูปลิงก์คลาวด์: {len(photo_urls)} รูป",
        reply_markup=main_menu_markup
    )
    
    context.user_data.clear()
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ ยกเลิกการบันทึกข้อมูลเรียบร้อยแล้ว สามารถเริ่มใหม่ได้ทันที", reply_markup=main_menu_markup)
    return ConversationHandler.END

# ---------------------------------------------------------
# ฟังก์ชันแสดงรายชื่อทั้งหมดจาก Airtable โดยตรง
# ---------------------------------------------------------
async def show_all_customers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        df = fetch_all_from_airtable()
        if df.empty:
            await update.message.reply_text("⚠️ ยังไม่มีข้อมูลรายชื่อใน Airtable ครับ", reply_markup=main_menu_markup)
            return

        total_records = len(df)
        header = f"📋 **รายชื่อลูกค้าทั้งหมดใน Airtable ({total_records} รายการ):**\n\n"
        messages, current_chunk = [], header
        
        for idx, row in df.iterrows():
            rec_num = idx + 1
            remark_text = row.get('หมายเหตุ', '-')
            
            line = (
                f"🔹 **ลำดับที่ {rec_num}**: {row['ชื่อ']}\n"
                f"   📅 บันทึกเมื่อ: {row['วันเวลา']}\n"
                f"   📝 หมายเหตุ: {remark_text}\n"
                "----------------------------------------\n"
            )
            if len(current_chunk) + len(line) > 3800:
                messages.append(current_chunk)
                current_chunk = line
            else:
                current_chunk += line
        
        if current_chunk:
            messages.append(current_chunk)
            
        for i, msg in enumerate(messages):
            markup = main_menu_markup if i == len(messages) - 1 else None
            await update.message.reply_text(msg, reply_markup=markup)

    except Exception as e:
        await update.message.reply_text(f"⚠️ เกิดข้อผิดพลาด: {str(e)}", reply_markup=main_menu_markup)

# ---------------------------------------------------------
# ฟังก์ชันดาวน์โหลดไฟล์ Excel จาก Airtable โดยตรง
# ---------------------------------------------------------
async def export_excel_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        df = fetch_all_from_airtable()
        if df.empty:
            await update.message.reply_text("⚠️ ยังไม่มีข้อมูลใน Airtable ครับ", reply_markup=main_menu_markup)
            return
            
        export_filename = "customer_database.xlsx"
        df.to_excel(export_filename, index=False)
        
        with open(export_filename, 'rb') as f:
            await update.message.reply_document(
                document=f,
                filename="Customer_Database.xlsx",
                caption=f"📁 **ไฟล์ Excel ข้อมูลลูกค้าทั้งหมดจาก Airtable** ({len(df)} รายการ)",
                reply_markup=main_menu_markup
            )
        if os.path.exists(export_filename):
            os.remove(export_filename)
            
    except Exception as e:
        await update.message.reply_text(f"⚠️ เกิดข้อผิดพลาดในการสร้างไฟล์ Excel: {str(e)}", reply_markup=main_menu_markup)

# ---------------------------------------------------------
# ระบบค้นหาข้อมูลลูกค้าจาก Airtable โดยตรง
# ---------------------------------------------------------
async def search_excel_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query_text = update.message.text.strip()
    
    if query_text == "➕ บันทึกข้อมูลลูกค้า":
        return await start_add(update, context)
    elif query_text == "📋 แสดงรายชื่อทั้งหมด":
        return await show_all_customers(update, context)
    elif query_text == "📁 โหลดไฟล์ Excel ทั้งหมด":
        return await export_excel_file(update, context)
    elif query_text in ["📖 คู่มือการใช้งาน", "คู่มือ"]:
        return await help_command(update, context)

    try:
        df = fetch_all_from_airtable()
        if df.empty:
            await update.message.reply_text("⚠️ ยังไม่มีข้อมูลในระบบ Airtable", reply_markup=main_menu_markup)
            return

        total_records = len(df)
        mask = df.astype(str).apply(
            lambda x: x.str.contains(query_text, regex=False, case=False, na=False)
        ).any(axis=1)
        matched_df = df[mask]

        if not matched_df.empty:
            await update.message.reply_text(
                f"🔍 **ผลการค้นหาจาก Airtable สำหรับ:** `{query_text}`\n"
                f"📊 พบ {len(matched_df)} รายการ (จากทั้งหมด {total_records} รายการ)",
                reply_markup=main_menu_markup
            )

            for idx, row in matched_df.head(5).iterrows():
                info_text = (
                    f"📌 **ข้อมูลลำดับที่ {idx + 1} จากทั้งหมด {total_records} รายการ**\n"
                    f"📅 **บันทึกเมื่อ:** {row['วันเวลา']}\n"
                    f"👤 **ชื่อ:** {row['ชื่อ']}\n"
                    f"📍 **ที่อยู่:** {row['ที่อยู่']}\n"
                    f"📞 **เบอร์โทร:** {row['เบอร์โทร']}\n"
                    f"🏢 **เลขผู้เสียภาษี:** {row['เลขผู้เสียภาษี']}\n"
                    f"📝 **หมายเหตุ:** {row['หมายเหตุ']}\n"
                    "----------------------------------------"
                )
                await update.message.reply_text(info_text)

                photos_str = row['รูปถ่าย']
                if photos_str and photos_str != "-":
                    photo_urls = [p.strip() for p in photos_str.split(',') if p.strip() and p.strip().startswith("http")]
                    media_group = [InputMediaPhoto(media=u) for u in photo_urls]
                    if media_group:
                        try:
                            await update.message.reply_media_group(media=media_group)
                        except Exception as e:
                            await update.message.reply_text(f"⚠️ ไม่สามารถดึงรูปภาพได้: {str(e)}")

            if len(matched_df) > 5:
                await update.message.reply_text(f"*(แสดง 5 รายการแรก จากทั้งหมดที่พบ {len(matched_df)} รายการ)*", reply_markup=main_menu_markup)
        else:
            await update.message.reply_text(f"❌ ไม่พบข้อมูลที่ตรงกับ `{query_text}` ใน Airtable", reply_markup=main_menu_markup)

    except Exception as e:
        await update.message.reply_text(f"⚠️ เกิดข้อผิดพลาด: {str(e)}", reply_markup=main_menu_markup)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 **ยินดีต้อนรับสู่บอทบันทึกและค้นหาข้อมูลลูกค้า!**\n\n"
        "✨ ระบบดึงและซิงก์ข้อมูลตรงจาก Airtable 100% มั่นใจได้ว่าข้อมูลถูกต้องแม่นยำและปลอดภัยไร้กังวล",
        reply_markup=main_menu_markup
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 **คู่มือการใช้งานบอท:**\n\n"
        "1. **บันทึกข้อมูล**: กดปุ่ม **'➕ บันทึกข้อมูลลูกค้า'** (เช็กข้อมูลซ้ำและบันทึกตรงเข้า Airtable ทันที)\n"
        "2. **ดาวน์โหลดไฟล์ Excel**: กดปุ่ม **'📁 โหลดไฟล์ Excel ทั้งหมด'** เพื่อดึงข้อมูลสดๆ จาก Airtable มาสร้างไฟล์รายงาน\n"
        "3. **แสดงรายชื่อและค้นหา**: ข้อมูลทั้งหมดดึงจาก Airtable แบบ Real-time 100%",
        reply_markup=main_menu_markup
    )

if __name__ == "__main__":
    TOKEN = "8833667054:AAFz7v2VA7SSR1QzqK2J9EQFPiMpN8WeL4w"
    
    request = HTTPXRequest(connect_timeout=30.0, read_timeout=30.0)
    app = ApplicationBuilder().token(TOKEN).request(request).build()
    
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
    
    print("🤖 Telegram Bot เชื่อมต่อ Airtable 100% พร้อมทำงานแล้ว...")
    app.run_polling()