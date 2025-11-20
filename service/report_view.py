from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler, CallbackQueryHandler, MessageHandler, filters
from datetime import datetime
from database import get_all_doctors, get_payments_by_doctor, get_services_by_doctor, get_expected_total_by_doctor, \
    get_services_summary_by_doctor, get_connection
from decimal import Decimal

ASK_REPORT_RANGE = 2000

async def start_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # ❗️ Eski doctor_id bo‘lsa, o‘chirib yuboramiz
    context.user_data.pop("doctor_id", None)

    await query.edit_message_text(
        "📆 Sanani kiriting (boshlanish - tugash):\nMasalan: 2025-10-01 - 2025-10-31"
    )
    return ASK_REPORT_RANGE


async def process_report_range(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        date_text = update.message.text
        start_date, end_date = [x.strip() for x in date_text.split(" - ")]
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
    except Exception:
        await update.message.reply_text("❌ Iltimos, sanani to‘g‘ri formatda kiriting: YYYY-MM-DD - YYYY-MM-DD")
        return ASK_REPORT_RANGE

    with get_connection() as conn:
        with conn.cursor() as cur:
            # ✅ Xizmatlar (asosiy + arxiv)
            cur.execute("""
                SELECT COALESCE(SUM(quantity), 0) FROM (
                    SELECT quantity FROM doctor_services WHERE created_at BETWEEN %s AND %s
                    UNION ALL
                    SELECT quantity FROM archived_services WHERE created_at BETWEEN %s AND %s
                ) AS all_services
            """, (start, end, start, end))
            total_services = cur.fetchone()[0] or 0

            # ✅ To‘lovlar (asosiy + arxiv)
            cur.execute("""
                SELECT COALESCE(SUM(amount), 0) FROM (
                    SELECT amount FROM payments WHERE created_at BETWEEN %s AND %s
                    UNION ALL
                    SELECT amount FROM archived_payments WHERE created_at BETWEEN %s AND %s
                ) AS all_payments
            """, (start, end, start, end))
            total_payments = cur.fetchone()[0] or 0

            # ✅ Narx yig‘indisi (asosiy + arxiv)
            cur.execute("""
                SELECT COALESCE(SUM(ds.quantity * s.price), 0) FROM doctor_services ds
                JOIN services s ON ds.service_id = s.id
                WHERE ds.created_at BETWEEN %s AND %s
            """, (start, end))
            price_1 = cur.fetchone()[0] or 0

            cur.execute("""
                SELECT COALESCE(SUM(ds.quantity * s.price), 0) FROM archived_services ds
                JOIN services s ON ds.service_id = s.id
                WHERE ds.created_at BETWEEN %s AND %s
            """, (start, end))
            price_2 = cur.fetchone()[0] or 0

            total_expected = (price_1 or 0) + (price_2 or 0)
            total_debt = (total_expected or 0) - (total_payments or 0)

    message = (
        f"📊 Umumiy hisobot: {start.date()} - {end.date()}\n\n"
        f"🧱 Xizmatlar soni: {int(total_services)} ta\n"
        f"💰 Xizmatlar summasi: {int(total_expected):,} so‘m\n"
        f"💵 To‘langan summa: {int(total_payments):,} so‘m\n"
        f"📦 Qarz: {int(total_debt):,} so‘m"
    )

    await update.message.reply_text(message)
    return ConversationHandler.END


async def process_date_range(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📅 Sana oralig‘i funksiyasi hali yozilmagan.")
    return ConversationHandler.END