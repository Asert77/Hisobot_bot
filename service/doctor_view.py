from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from database import get_connection, add_doctor_service, get_doctor_id_by_telegram_id, get_service_by_id

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

    services = get_services_summary_by_doctor(doctor_id)
    total_expected = get_expected_total_by_doctor(doctor_id)
    payments = get_payments_by_doctor(doctor_id)
    total_paid = sum(float(amount) for amount, _, _ in payments)

    debt = max(total_expected - total_paid, 0)

    service_lines = []
    for name, price, quantity, *_ in services:
        if quantity == 0 or price == 0:
            continue
        service_lines.append(f"🔹 {name} — {quantity} ta × {price:.0f} = {price * quantity:.0f} so‘m")

    services_text = "\n".join(service_lines) if service_lines else '🚫 Hali xizmat qo‘shilmagan.'

    message_text = (
        f"👨‍⚕️ Doktor uchun ma'lumotlar:\n\n"
        f"{services_text}\n\n"
        f"💰 Umumiy: {total_expected:.0f} so‘m\n"
        f"✅ To‘langan: {total_paid:.0f} so‘m\n"
        f"❌ Qarzdorlik: {debt:.0f} so‘m"
    )

    keyboard = [
        [InlineKeyboardButton("➕ Xizmat qo‘shish", callback_data="add_service_to_doctor")],
        [InlineKeyboardButton("💳 To‘lov qo‘shish", callback_data="add_payment")],
        [InlineKeyboardButton("🧾 Qarzni yopish", callback_data="close_debt")],
        [InlineKeyboardButton("➕ Qarz qo‘shish", callback_data="add_debt")],
        [InlineKeyboardButton("📊 Hisobot", callback_data=f"report_{doctor_id}")],
        [InlineKeyboardButton("✏️ Ismni o‘zgartirish", callback_data=f"edit_name_{doctor_id}")],
        [InlineKeyboardButton("🔙 Orqaga", callback_data="list_doctors")],
    ]
    markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await update.callback_query.edit_message_text(message_text, reply_markup=markup)
    else:
        await update.message.reply_text(message_text, reply_markup=markup)


async def show_services_for_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, price FROM services ORDER BY id ASC")
            services = cur.fetchall()

    if not services:
        await update.callback_query.edit_message_text("⚠️ Xizmatlar topilmadi.")
        return

    keyboard = []
    for service_id, name, price in services:
        keyboard.append([
            InlineKeyboardButton(
                f"{name} — {price:.0f} so‘m",
                callback_data=f"select_service_{service_id}"   # 👈 MUHIM
            )
        ])

    markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text(
        "🧾 Xizmat turini tanlang:",
        reply_markup=markup
    )

async def edit_name_(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    doctor_id = int(query.data.split("_")[-1])
    context.user_data["edit_doctor_id"] = doctor_id

    await query.edit_message_text("✏️ Yangi ismni kiriting:")
    return EDIT_DOCTOR_NAME

async def select_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    try:
        service_id = int(data.split("_")[-1])
    except (ValueError, IndexError):
        await query.edit_message_text("⚠️ Xizmat ID topilmadi.")
        return ConversationHandler.END
    print("📩 CALLBACK DATA:", data)
    print("🔎 PARSED SERVICE ID:", service_id)
    service = get_service_by_id(service_id)
    print("📋 SERVICE FROM DB:", service)
    if not service:
        await query.edit_message_text("⚠️ Xizmat topilmadi.")
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
    # 1️⃣ Miqdorni tekshiramiz
    try:
        quantity = int(update.message.text.strip())
        if quantity <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Iltimos, to‘g‘ri son kiriting (1 yoki undan katta).")
        return SELECT_SERVICE_QUANTITY

    # 2️⃣ Contextdan ma'lumotlarni olamiz
    service_id = context.user_data.get("selected_service_id")
    name = context.user_data.get("selected_service_name")
    price = context.user_data.get("selected_service_price")
    doctor_id = context.user_data.get("doctor_id")

    if not service_id or not name or price is None:
        await update.message.reply_text("⚠️ Xizmat ma'lumotlari topilmadi. Qaytadan urinib ko‘ring.")
        return ConversationHandler.END

    if not doctor_id:
        telegram_id = update.effective_user.id
        doctor_id = get_doctor_id_by_telegram_id(telegram_id)
        if not doctor_id:
            await update.message.reply_text("❌ Doktor aniqlanmadi. Iltimos, admin bilan bog‘laning.")
            return ConversationHandler.END
        context.user_data["doctor_id"] = doctor_id

    # 3️⃣ Bazaga yozamiz: doctor_services jadvaliga qo‘shamiz
    add_doctor_service(doctor_id, service_id, quantity)

    total = quantity * price

    # 4️⃣ Javob + orqaga tugma
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Doktor menyusiga qaytish", callback_data=f"doctor_{doctor_id}")]
    ])

    await update.message.reply_text(
        f"✅ {name} — {quantity} dona × {price:.0f} = {total:.0f} so‘m xizmat qo‘shildi.",
        reply_markup=keyboard
    )

    # 5️⃣ Contextni tozalab qo‘yamiz
    context.user_data.pop("selected_service_id", None)
    context.user_data.pop("selected_service_name", None)
    context.user_data.pop("selected_service_price", None)

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

    # ✅ Admin uchun javob
    await query.edit_message_text(
        text=f"✅ {name} — {quantity} dona × {float(price):.0f} = {total:.0f} so‘m xizmat qo‘shildi.",
        parse_mode="HTML"
    )

