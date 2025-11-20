from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler, CallbackQueryHandler, MessageHandler, filters
from datetime import datetime
from database import get_all_doctors, get_payments_by_doctor, get_services_by_doctor, get_expected_total_by_doctor, \
    get_services_summary_by_doctor, get_connection
from decimal import Decimal

ASK_REPORT_RANGE = 2000

import re
from datetime import datetime, timedelta
from typing import Optional, Tuple

_DATE_SEPS = r"[./\-–—]"

def _try_parse_single(text: str) -> Optional[datetime]:
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%d.%m.%y", "%d/%m/%y"):
        try:
            return datetime.strptime(text.strip(), fmt)
        except ValueError:
            continue
    return None

def _try_relative(text: str) -> Optional[Tuple[datetime, datetime]]:
    text = text.lower().strip()
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    if text == "bugun":
        return today, today
    if text == "kecha":
        d = today - timedelta(days=1)
        return d, d
    m = re.match(r"(\d+)\s*(kun|oy)", text)
    if m:
        n, unit = int(m[1]), m[2]
        if unit == "kun":
            start = today - timedelta(days=n - 1)
        else:  # oy
            start = today - timedelta(days=n * 30)
        return start, today
    return None

def parse_date_range(text: str) -> Optional[Tuple[datetime, datetime]]:
    # 1. relative so‘zlar
    rel = _try_relative(text)
    if rel:
        return rel

    # 2. ikki sana (ajratgich bilan)
    parts = re.split(r"\s*[-–—]\s*", text.strip())
    if len(parts) == 2:
        d1, d2 = _try_parse_single(parts[0]), _try_parse_single(parts[1])
        if d1 and d2:
            return (d1, d2) if d1 <= d2 else (d2, d1)

    # 3. ikki sana bo‘shliq bilan
    parts = re.split(r"\s+", text.strip())
    if len(parts) == 2:
        d1, d2 = _try_parse_single(parts[0]), _try_parse_single(parts[1])
        if d1 and d2:
            return (d1, d2) if d1 <= d2 else (d2, d1)

    # 4. bitta sana → shu kun
    d = _try_parse_single(text)
    if d:
        return d, d

    return None

async def start_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # ❗️ Eski doctor_id bo‘lsa, o‘chirib yuboramiz
    context.user_data.pop("doctor_id", None)

    await query.edit_message_text(
        "📆 Sanani kiriting (boshlanish - tugash):\nMasalan: “bugun”,\n “7 kun”,\n “01.10.2025 – 31.10.2025”,\n “2025-10-01 2025-10-31” "
    )
    return ASK_REPORT_RANGE


async def process_report_range(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    rng = parse_date_range(text)
    if not rng:
        await update.message.reply_text(
            "❌ Sanani tushunmadim.\n"
            "✅ Masalan:  2025-10-01 2025-10-31\n"
            "             01.10.2025 – 31.10.2025\n"
            "             bugun\n"
            "             7 kun\n"
            "Yana bir bor kiriting (/cancel – bekor)"
        )
        return ASK_REPORT_RANGE

    start_dt, end_dt = rng
    start_dt = start_dt.replace(hour=0, minute=0, second=0, microsecond=0)
    end_dt = end_dt.replace(hour=23, minute=59, second=59, microsecond=999999)

    # ----- hisobot SQL (sizning kod) -----
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COALESCE(SUM(quantity), 0) FROM (
                    SELECT quantity FROM doctor_services WHERE created_at BETWEEN %s AND %s
                    UNION ALL
                    SELECT quantity FROM archived_services WHERE created_at BETWEEN %s AND %s
                ) AS all_services
            """, (start_dt, end_dt, start_dt, end_dt))
            total_services = cur.fetchone()[0] or 0

            cur.execute("""
                SELECT COALESCE(SUM(amount), 0) FROM (
                    SELECT amount FROM payments WHERE created_at BETWEEN %s AND %s
                    UNION ALL
                    SELECT amount FROM archived_payments WHERE created_at BETWEEN %s AND %s
                ) AS all_payments
            """, (start_dt, end_dt, start_dt, end_dt))
            total_payments = cur.fetchone()[0] or 0

            cur.execute("""
                SELECT COALESCE(SUM(ds.quantity * s.price), 0) FROM doctor_services ds
                JOIN services s ON ds.service_id = s.id
                WHERE ds.created_at BETWEEN %s AND %s
            """, (start_dt, end_dt))
            price_1 = cur.fetchone()[0] or 0

            cur.execute("""
                SELECT COALESCE(SUM(ds.quantity * s.price), 0) FROM archived_services ds
                JOIN services s ON ds.service_id = s.id
                WHERE ds.created_at BETWEEN %s AND %s
            """, (start_dt, end_dt))
            price_2 = cur.fetchone()[0] or 0

            total_expected = price_1 + price_2
            total_debt = total_expected - total_payments

    msg = (
        f"📊 Hisobot: {start_dt.date()} → {end_dt.date()}\n\n"
        f"🧱 Xizmatlar: {int(total_services)} ta\n"
        f"💰 Summa: {int(total_expected):,} so‘m\n"
        f"💵 To‘langan: {int(total_payments):,} so‘m\n"
        f"📦 Qarz: {int(total_debt):,} so‘m"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Asosiy menyu", callback_data="go_start")]
    ])
    await update.message.reply_text(msg, reply_markup=kb)
    return ConversationHandler.END


async def process_date_range(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📅 Sana oralig‘i funksiyasi hali yozilmagan.")
    return ConversationHandler.END