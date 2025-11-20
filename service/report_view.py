from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler, CallbackQueryHandler, MessageHandler, filters
from datetime import datetime, timedelta
from database import get_connection
from decimal import Decimal

ASK_REPORT_RANGE = 2000
ASK_CUSTOM_RANGE = 2001


async def start_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    context.user_data.pop("doctor_id", None)

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 Bugun", callback_data="report_today")],
        [InlineKeyboardButton("📆 Bir hafta", callback_data="report_week")],
        [InlineKeyboardButton("🗓 Bir oy", callback_data="report_month")],
        [InlineKeyboardButton("📊 Uch oy", callback_data="report_3months")],
        [InlineKeyboardButton("📈 Yil boshidan", callback_data="report_year")],
        [InlineKeyboardButton("✏️ Boshqa sana", callback_data="report_custom")],
        [InlineKeyboardButton("🔙 Orqaga", callback_data="go_start")]
    ])

    await query.edit_message_text(
        "📊 Hisobot uchun davr tanlang:",
        reply_markup=keyboard
    )
    return ASK_REPORT_RANGE


async def handle_report_period(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    today = datetime.now().date()

    if query.data == "report_today":
        start_date = today
        end_date = today
    elif query.data == "report_week":
        start_date = today - timedelta(days=7)
        end_date = today
    elif query.data == "report_month":
        start_date = today - timedelta(days=30)
        end_date = today
    elif query.data == "report_3months":
        start_date = today - timedelta(days=90)
        end_date = today
    elif query.data == "report_year":
        start_date = datetime(today.year, 1, 1).date()
        end_date = today
    elif query.data == "report_custom":
        await query.edit_message_text(
            "📆 Sanani kiriting (boshlanish - tugash):\n"
            "Masalan: 2025-10-01 - 2025-10-31\n\n"
            "❌ Bekor qilish: /cancel"
        )
        return ASK_CUSTOM_RANGE
    else:
        return ConversationHandler.END

    # Hisobotni ko'rsatish
    await show_report(query, start_date, end_date)
    return ConversationHandler.END


async def process_custom_range(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        date_text = update.message.text
        start_date, end_date = [x.strip() for x in date_text.split(" - ")]
        start = datetime.strptime(start_date, "%Y-%m-%d").date()
        end = datetime.strptime(end_date, "%Y-%m-%d").date()
    except Exception:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Orqaga", callback_data="report_menu")]
        ])
        await update.message.reply_text(
            "❌ Iltimos, sanani to'g'ri formatda kiriting:\n"
            "YYYY-MM-DD - YYYY-MM-DD\n\n"
            "Masalan: 2025-01-01 - 2025-01-31",
            reply_markup=keyboard
        )
        return ASK_CUSTOM_RANGE

    await show_report_message(update.message, start, end)
    return ConversationHandler.END


async def show_report(query, start_date, end_date):
    """Callback query orqali hisobot ko'rsatish"""
    start = datetime.combine(start_date, datetime.min.time())
    end = datetime.combine(end_date, datetime.max.time())

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

            # ✅ To'lovlar (asosiy + arxiv)
            cur.execute("""
                SELECT COALESCE(SUM(amount), 0) FROM (
                    SELECT amount FROM payments WHERE created_at BETWEEN %s AND %s
                    UNION ALL
                    SELECT amount FROM archived_payments WHERE created_at BETWEEN %s AND %s
                ) AS all_payments
            """, (start, end, start, end))
            total_payments = cur.fetchone()[0] or 0

            # ✅ Narx yig'indisi (asosiy + arxiv)
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
        f"📊 <b>Umumiy hisobot:</b> {start_date} - {end_date}\n\n"
        f"🧱 Xizmatlar soni: {int(total_services)} ta\n"
        f"💰 Xizmatlar summasi: {int(total_expected):,} so'm\n"
        f"💵 To'langan summa: {int(total_payments):,} so'm\n"
        f"📦 Qarz: {int(total_debt):,} so'm"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Asosiy menyu", callback_data="go_start")]
    ])

    await query.edit_message_text(message, parse_mode="HTML", reply_markup=keyboard)


async def show_report_message(message, start_date, end_date):
    """Message orqali hisobot ko'rsatish"""
    start = datetime.combine(start_date, datetime.min.time())
    end = datetime.combine(end_date, datetime.max.time())

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

            # ✅ To'lovlar (asosiy + arxiv)
            cur.execute("""
                SELECT COALESCE(SUM(amount), 0) FROM (
                    SELECT amount FROM payments WHERE created_at BETWEEN %s AND %s
                    UNION ALL
                    SELECT amount FROM archived_payments WHERE created_at BETWEEN %s AND %s
                ) AS all_payments
            """, (start, end, start, end))
            total_payments = cur.fetchone()[0] or 0

            # ✅ Narx yig'indisi (asosiy + arxiv)
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

    text = (
        f"📊 <b>Umumiy hisobot:</b> {start_date} - {end_date}\n\n"
        f"🧱 Xizmatlar soni: {int(total_services)} ta\n"
        f"💰 Xizmatlar summasi: {int(total_expected):,} so'm\n"
        f"💵 To'langan summa: {int(total_payments):,} so'm\n"
        f"📦 Qarz: {int(total_debt):,} so'm"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Asosiy menyu", callback_data="go_start")]
    ])

    await message.reply_text(text, parse_mode="HTML", reply_markup=keyboard)


async def cancel_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Asosiy menyu", callback_data="go_start")]
    ])
    await update.message.reply_text("❌ Bekor qilindi.", reply_markup=keyboard)
    context.user_data.clear()
    return ConversationHandler.END