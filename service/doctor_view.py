from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from database import get_connection, add_doctor_service, get_doctor_id_by_telegram_id, get_service_by_id, \
    get_doctor_telegram_id

SELECT_SERVICE_QUANTITY = 1
EDIT_DOCTOR_NAME = range(1)


# 🔙 Orqaga qaytish tugmasi
back_button = InlineKeyboardMarkup([
    [InlineKeyboardButton("🔙 Orqaga", callback_data="list_doctors")]
])

# 👨‍⚕️ Doktor profili menyusi
from database import (
    get_services_summary_by_doctor,
    get_expected_total_by_doctor,
    get_payments_by_doctor
)

from telegram import InlineKeyboardMarkup, InlineKeyboardButton


async def open_doctor_menu(update, context, doctor_id):
    query = update.callback_query
    context.user_data["doctor_id"] = doctor_id

    # 🩺 Doktor ma'lumotlarini olish
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT name, phone FROM doctors WHERE id = %s", (doctor_id,))
            doctor_info = cur.fetchone()

    doctor_name = doctor_info[0] if doctor_info else "Noma'lum"
    doctor_phone = doctor_info[1] if doctor_info and doctor_info[1] else "❌ Kiritilmagan"

    # 🧾 Xizmatlar, to‘lovlar, qarz
    services = get_services_summary_by_doctor(doctor_id)
    total_expected = get_expected_total_by_doctor(doctor_id)
    payments = get_payments_by_doctor(doctor_id)
    total_paid = sum(float(amount) for amount, _ in payments)

    # 🧮 Bazadagi qo‘shimcha qarzlarni olish
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COALESCE(SUM(amount), 0) FROM pending_debts WHERE doctor_id = %s", (doctor_id,))
            extra_debt = float(cur.fetchone()[0] or 0)

    # 🔹 Umumiy qarzdorlikni hisoblash
    debt = max(total_expected - total_paid + extra_debt, 0)

    # 🧱 Xizmatlar matni
    service_lines = []
    for name, quantity, total, *_ in services:
        if quantity == 0 or total == 0:
            continue
        service_lines.append(f"🔹 {name} — {quantity} ta = {total:,.0f} so'm")

    services_text = "\n".join(service_lines) if service_lines else '🚫 Hali xizmat qo‘shilmagan.'

    # 📋 Yakuniy xabar
    message_text = (
        f"👨‍⚕️ <b>Doktor:</b> {doctor_name}\n"
        f"📞 <b>Telefon:</b> {doctor_phone}\n\n"
        f"{services_text}\n\n"
        f"💰 Umumiy: {total_expected:,.0f} so'm\n"
        f"✅ To'langan: {total_paid:,.0f} so'm\n"
        f"❌ Qarzdorlik: {debt:,.0f} so'm"
    )

    keyboard = [
        [InlineKeyboardButton("➕ Xizmat qo'shish", callback_data="add_service_to_doctor")],
        [InlineKeyboardButton("💳 To'lov qo'shish", callback_data="add_payment")],
        [InlineKeyboardButton("🧾 Qarzni yopish", callback_data="close_debt")],
        [InlineKeyboardButton("➕ Qarz qo'shish", callback_data="add_debt")],
        [InlineKeyboardButton("📊 Hisobot", callback_data=f"report_{doctor_id}")],
        [InlineKeyboardButton("✏️ Ismni o'zgartirish", callback_data=f"edit_name_{doctor_id}")],
        [InlineKeyboardButton("📞 Telefon qo'shish", callback_data=f"add_phone_{doctor_id}")],
        [InlineKeyboardButton("🔙 Orqaga", callback_data="list_doctors")],
    ]
    markup = InlineKeyboardMarkup(keyboard)

    # 🔄 Xabarni yangilash
    if update.callback_query:
        await query.edit_message_text(message_text, reply_markup=markup, parse_mode="HTML")
    else:
        await update.message.reply_text(message_text, reply_markup=markup, parse_mode="HTML")

async def show_services_for_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, price FROM services ORDER BY id ASC")
            services = cur.fetchall()

    print("📋 SERVICES:", services)

    if not services:
        await query.edit_message_text("⚠️ Xizmatlar topilmadi.")
        return

    keyboard = [
        [InlineKeyboardButton(f"{name} — {price:.0f} so‘m", callback_data=f"select_service_{service_id}")]
        for service_id, name, price in services
    ]

    markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("🧾 Xizmat turini tanlang:", reply_markup=markup)

async def edit_name_(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    doctor_id = int(query.data.split("_")[-1])
    context.user_data["edit_doctor_id"] = doctor_id

    await query.edit_message_text("✏️ Yangi ismni kiriting:")
    return EDIT_DOCTOR_NAME

async def select_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("🟢 select_service CALLBACK ISHLADI")
    query = update.callback_query
    await query.answer()

    data = query.data
    print("📩 Callback keldi:", data)

    try:
        service_id = int(data.split("_")[-1])
    except (ValueError, IndexError):
        await query.edit_message_text("⚠️ Xizmat ID topilmadi.")
        return ConversationHandler.END

    # Xizmatni bazadan olish
    service = get_service_by_id(service_id)
    if not service:
        await query.edit_message_text("⚠️ Xizmat topilmadi (bazadan hech narsa qaytmadi).")
        return ConversationHandler.END

    context.user_data["selected_service_id"] = service["id"]
    context.user_data["selected_service_name"] = service["name"]
    context.user_data["selected_service_price"] = float(service["price"])

    await query.edit_message_text(
        text=f"📦 <b>{service['name']}</b> uchun sonini kiriting:",
        parse_mode="HTML"
    )

    return SELECT_SERVICE_QUANTITY

async def ask_service_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        quantity = int(update.message.text.strip())
        if quantity <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Iltimos, to‘g‘ri son kiriting (1 yoki undan katta).")
        return SELECT_SERVICE_QUANTITY

    service_id = context.user_data.get("selected_service_id")
    name = context.user_data.get("selected_service_name")
    price = context.user_data.get("selected_service_price")
    doctor_id = context.user_data.get("doctor_id")

    if not doctor_id:
        telegram_id = update.effective_user.id
        doctor_id = get_doctor_id_by_telegram_id(telegram_id)
        if not doctor_id:
            await update.message.reply_text("❌ Doktor aniqlanmadi.")
            return ConversationHandler.END
        context.user_data["doctor_id"] = doctor_id

    add_doctor_service(doctor_id, service_id, quantity)
    total = quantity * price

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Orqaga", callback_data=f"doctor_{doctor_id}")]
    ])

    await update.message.reply_text(
        f"✅ {name} — {quantity} dona × {price:.0f} = {total:.0f} so‘m xizmat qo‘shildi.",
        reply_markup=keyboard
    )

    # 🔔 Doktorga xabar yuborish
    try:
        doctor_telegram_id = get_doctor_telegram_id(doctor_id)
        if doctor_telegram_id:
            await context.bot.send_message(
                chat_id=doctor_telegram_id,
                text=(
                    f"🧾 <b>Yangi xizmat qo‘shildi!</b>\n\n"
                    f"🧑‍⚕️ {name}\n"
                    f"📦 {quantity} dona × {price:.0f} = {total:.0f} so‘m"
                ),
                parse_mode="HTML"
            )
    except Exception as e:
        print(f"Xabar yuborishda xato: {e}")

    context.user_data.clear()
    return ConversationHandler.END

async def add_service_to_doctor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    doctor_id = context.user_data.get("doctor_id")

    # Xizmatni tanlash
    service_id = context.user_data.get("selected_service_id")
    quantity = context.user_data.get("selected_quantity", 1)

    # Bazadan xizmat ma’lumotlarini olish
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT name, price FROM services WHERE id = %s", (service_id,))
            service = cur.fetchone()

            if not service:
                await query.edit_message_text("⚠️ Xizmat topilmadi.")
                return

            name, price = service
            total = float(price) * quantity

            # 🧾 Bazaga qo‘shish
            cur.execute("""
                INSERT INTO doctor_services (doctor_id, service_id, quantity)
                VALUES (%s, %s, %s)
            """, (doctor_id, service_id, quantity))
            conn.commit()

    # 🔔 Endi doktorning Telegram ID sini olish
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT telegram_id FROM doctors WHERE id = %s", (doctor_id,))
            doctor_row = cur.fetchone()
            if not doctor_row:
                return
            doctor_telegram_id = doctor_row[0]

    # 📨 Xizmat qo‘shilganini doktorga xabar yuborish
    message = (
        f"🧾 <b>Yangi xizmat qo‘shildi!</b>\n\n"
        f"🧑‍⚕️ <b>Xizmat nomi:</b> {name}\n"
        f"📦 <b>Miqdori:</b> {quantity} dona\n"
        f"💰 <b>Umumiy narx:</b> {total:.0f} so‘m"
    )

    try:
        await context.bot.send_message(
            chat_id=doctor_telegram_id,
            text=message,
            parse_mode="HTML"
        )
    except Exception as e:
        print(f"Xabar yuborishda xato: {e}")

    await query.edit_message_text(
        text=f"✅ {name} — {quantity} dona × {float(price):.0f} = {total:.0f} so‘m xizmat qo‘shildi.",
        parse_mode="HTML"
    )

