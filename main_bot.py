import asyncio
import os
import nest_asyncio
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ConversationHandler, ContextTypes, filters
)
from database import (
    create_tables, add_doctor, get_all_doctors, add_service,
    add_payment, get_payments_by_doctor, get_services_by_doctor,
    delete_doctor, get_all_services, get_service_by_id, get_expected_total_by_doctor, get_services_summary_by_doctor,
    delete_service_by_id, get_monthly_debts,
    close_debts, add_doctor_auto, my_profile, save_new_doctor_name, back_to_user_menu, add_phone_request, get_phone,
    get_connection
)
from pdf_report import generate_pdf_report
from service.doctor_view import SELECT_SERVICE_QUANTITY, edit_name_, EDIT_DOCTOR_NAME
from service.doctor_view import open_doctor_menu
from service.doctor_view import (
    show_services_for_payment,  # xizmatlarni ko‘rsatish
    select_service,  # xizmat tanlandi
    ask_service_quantity, add_service_to_doctor  # sonini kiritish
)
from service.report_view import start_report, ASK_REPORT_RANGE, process_report_range
from telegram.request import HTTPXRequest

request = HTTPXRequest(connect_timeout=10.0, read_timeout=20.0)
load_dotenv()
TOKEN = os.getenv("TOKEN")
ADMINS = list(map(int, os.getenv("ADMINS", "").split(",")))

nest_asyncio.apply()

CONFIRM_CLOSE_DEBT = 1001

ENTER_PAYMENT_AMOUNT, ENTER_DEBT_AMOUNT = range(2)

# Bosqichlar
NAME, PHONE, TELEGRAM_ID, SERVICE_NAME, SERVICE_PRICE, ENTER_PAYMENT, DATE_RANGE = range(7)

# 🔙 Orqaga qaytish tugmasi
back_button = InlineKeyboardMarkup([
    [InlineKeyboardButton("🔙 Menyuga qaytish", callback_data="back_to_menu")]
])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()  # avvalgi holatlarni tozalash
    user = update.effective_user
    telegram_id = user.id
    username = user.username or "yo‘q"

    if telegram_id in ADMINS:
        keyboard = [
            [InlineKeyboardButton("📋 Doktorlar ro'yxati", callback_data="list_doctors")],
            [InlineKeyboardButton("📊 Hisobot", callback_data="report_main")],
            [InlineKeyboardButton("🛠 Xizmat turi", callback_data="services")],
            [InlineKeyboardButton("⚙️ Sozlamalar", callback_data="settings")],
        ]
        markup = InlineKeyboardMarkup(keyboard)
        if update.message:
            await update.message.reply_text("🏠 Boshqaruv menyusi:", reply_markup=markup)
        elif update.callback_query:
            await update.callback_query.message.edit_text("🏠 Boshqaruv menyusi:", reply_markup=markup)

    else:
        add_doctor_auto(telegram_id, user.full_name, username)
        # Oddiy foydalanuvchi uchun menyu
        keyboard = [
            [InlineKeyboardButton("👤 Mening profilim", callback_data="my_profile")]
        ]
        markup = InlineKeyboardMarkup(keyboard)

        text = (
            f"👋 Salom, {user.full_name}!\n"
            f"📱 Telegram ID: {telegram_id}\n"
            f"🧾 Username: @{username}\n\n"
            f"Siz ro'yhatdan o'tdingiz!"
            f"📩 Sizga biriktirilgan xizmatlar bo‘yicha bildirishnomalar shu yerga keladi.\n"
            f"❓ Agar xabar kelsa va buyurtmani olgan bo'lsangiz 'Ha' ni bosing. "
            f"Agar olmagan bo'lsangiz 14:00 da qayta xabar yuboriladi."
        )

        if update.message:
            await update.message.reply_text(text, reply_markup=markup)
        elif update.callback_query:
            await update.callback_query.message.edit_text(text, reply_markup=markup)
    return ConversationHandler.END

# Asosiy handler
async def handle_menu_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    telegram_id = query.from_user.id
    if telegram_id not in ADMINS:
        await query.edit_message_text("❌ Sizda bu menyudan foydalanish huquqi yo‘q.")
        return

    # 📋 Doktorlar ro‘yxati
    if data == "list_doctors":
        doctors = get_all_doctors()
        if not doctors:
            try:
                await query.edit_message_text("📄 Doktorlar yo‘q.", reply_markup=back_button)
            except Exception:
                await query.message.reply_text("📄 Doktorlar yo‘q.", reply_markup=back_button)
            return

        keyboard = [[InlineKeyboardButton(f"👨‍⚕️ {name}", callback_data=f"doctor_{doc_id}")]
                    for doc_id, name, _ in doctors]
        keyboard.append([InlineKeyboardButton("🔙 Menyuga qaytish", callback_data="back_to_menu")])
        try:
            await query.edit_message_text("📋 Doktorlar ro‘yxati:", reply_markup=InlineKeyboardMarkup(keyboard))
        except Exception:
            await query.message.reply_text("📋 Doktorlar ro‘yxati:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "add_doctor":
        await query.edit_message_text("🧾 Doktorning ismini yuboring:")
        return NAME

    elif data == "report_main":
        return await start_report(update, context)

    elif data == "my_profile":
        await my_profile(update, context)

    elif data.startswith("doctor_"):
        doctor_id = int(data.split("_")[1])
        context.user_data["doctor_id"] = doctor_id
        await open_doctor_menu(update, context, doctor_id)

    # 🧾 Hisobot chiqarish
    elif data.startswith("report_") and data != "report_main":
        try:
            doctor_id = int(data.split("_")[1])
        except (IndexError, ValueError):
            await query.edit_message_text("❌ Noto‘g‘ri doctor ID.")
            return ConversationHandler.END

        context.user_data["doctor_id"] = doctor_id
        doctors = get_all_doctors()
        doctor_name = next((name for id_, name, _ in doctors if id_ == doctor_id), "Noma'lum")

        payments = get_payments_by_doctor(doctor_id)
        services = get_services_by_doctor(doctor_id)
        total_paid = sum(float(amount) for amount, _ in payments)
        total_expected = get_expected_total_by_doctor(doctor_id)

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COALESCE(SUM(amount), 0) FROM pending_debts WHERE doctor_id = %s", (doctor_id,))
                extra_debt = float(cur.fetchone()[0] or 0)

        debt = max(total_expected - total_paid + extra_debt, 0)
        services_summary = get_services_summary_by_doctor(doctor_id)

        filepath = generate_pdf_report(
            doctor_name,
            payments,
            total_paid,
            total_expected,
            debt,
            services_summary
        )
        with open(filepath, "rb") as f:
            await query.message.reply_document(
                document=f,
                filename=os.path.basename(filepath),
                caption="📎 Hisobot PDF fayli"
            )

        await query.edit_message_text("✅ Hisobot PDF yuborildi.", reply_markup=back_button)

    elif data == "go_start":
        await start(update, context)

    # ⚙️ Sozlamalar
    elif data == "settings":
        doctors = get_all_doctors()
        if not doctors:
            await query.edit_message_text("📋 Doktorlar yo‘q.", reply_markup=back_button)
            return

        keyboard = [
            [InlineKeyboardButton(f"👨‍⚕️ {name}", callback_data=f"request_del_{doc_id}")]
            for doc_id, name, _ in doctors
        ]
        keyboard.append([InlineKeyboardButton("🔙 Menyuga qaytish", callback_data="back_to_menu")])
        await query.edit_message_text("🗑 O‘chirmoqchi bo‘lgan doktoringizni tanlang:",
                                      reply_markup=InlineKeyboardMarkup(keyboard))


    elif data == "add_service":
        await show_services_for_payment(update, context)


    elif data == "close_debt":
        doctor_id = context.user_data.get("doctor_id")
        if not doctor_id:
            await query.edit_message_text("❌ Doktor aniqlanmadi.", reply_markup=back_button)
            return ConversationHandler.END
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COALESCE(SUM(amount), 0) FROM pending_debts WHERE doctor_id = %s", (doctor_id,))
                total_debt = float(cur.fetchone()[0] or 0)
        if total_debt <= 0:
            await query.edit_message_text("✅ Ushbu doktorning hech qanday qarzi yo‘q.", reply_markup=back_button)
            return ConversationHandler.END
        keyboard = [
            [
                InlineKeyboardButton("✅ Ha, qarzni yopaman", callback_data="confirm_close_debt"),
                InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel_close_debt")
            ]
        ]
        context.user_data["debt_total"] = total_debt
        await query.edit_message_text(
            f"🧾 Ushbu doktorning qarzi: <b>{total_debt:,.0f} so‘m</b>\n\n"
            "Qarzni to‘liq yopmoqchimisiz?",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return ConversationHandler.END


    elif data == "confirm_close_debt":
        doctor_id = context.user_data.get("doctor_id")
        total_debt = context.user_data.get("debt_total", 0)
        if not doctor_id or total_debt <= 0:
            await query.edit_message_text("⚠️ Qarzni yopishda xatolik yuz berdi.", reply_markup=back_button)
            return ConversationHandler.END

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM pending_debts WHERE doctor_id = %s", (doctor_id,))
                conn.commit()
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT telegram_id, name FROM doctors WHERE id = %s", (doctor_id,))
                doctor = cur.fetchone()
        if doctor:
            doctor_telegram_id, doctor_name = doctor
            msg = f"✅ Hurmatli {doctor_name}, sizning {total_debt:,.0f} so‘mlik qarzingiz to‘liq yopildi."
            try:
                await context.bot.send_message(chat_id=doctor_telegram_id, text=msg)
            except Exception as e:
                print(f"⚠️ Doktorga xabar yuborilmadi: {e}")
        await query.edit_message_text(
            f"✅ Doktorning {total_debt:,.0f} so‘mlik qarzi yopildi.",
            reply_markup=back_button
        )
        return ConversationHandler.END

    elif data == "cancel_close_debt":
        await query.edit_message_text("❌ Qarzni yopish bekor qilindi.", reply_markup=back_button)
        return ConversationHandler.END


    elif data == "services":
        services = get_all_services()

        keyboard = []

        if services:
            for sid, name, price in services:
                keyboard.append([InlineKeyboardButton(f"💠 {name} ({price:.0f} so‘m)", callback_data="ignore")])
                keyboard.append([InlineKeyboardButton(f"❌ O‘chirish: {name}", callback_data=f"delete_service_{sid}")])
        else:
            keyboard.append([InlineKeyboardButton("❌ Hech qanday xizmat yo‘q", callback_data="ignore")])

        keyboard.append([InlineKeyboardButton("➕ Yangi xizmat qo‘shish", callback_data="add_service_direct")])
        keyboard.append([InlineKeyboardButton("🔙 Menyuga qaytish", callback_data="back_to_menu")])

        await query.edit_message_text("🛠 Xizmatlar bo‘limi:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("delete_service_"):
        service_id = int(data.split("_")[-1])
        delete_service_by_id(service_id)
        await query.edit_message_text("🗑 Xizmat o‘chirildi. ✅", reply_markup=back_button)


    # ➕ Xizmat qo‘shish
    elif data == "add_service_direct":
        context.user_data.pop("doctor_id", None)  # 💡 Buni qo‘shing — eski qiymatni o‘chirish
        await query.edit_message_text("📝 Xizmat nomini kiriting:")
        return SERVICE_NAME


    elif data == "add_debt":
        doctor_id = context.user_data.get("doctor_id")
        if not doctor_id:
            await query.edit_message_text("❌ Doktor aniqlanmadi.", reply_markup=back_button)
            return ConversationHandler.END
        await query.edit_message_text("💸 Qarz miqdorini kiriting:")
        return ENTER_DEBT_AMOUNT

    elif data == "add_service_to_doctor":
        services = get_all_services()
        if not services:
            await query.edit_message_text("📋 Hozircha hech qanday xizmat mavjud emas.", reply_markup=back_button)
            return

        keyboard = [
            [InlineKeyboardButton(f"{name} ({price:.0f} so‘m)", callback_data=f"select_global_service_{sid}")]
            for sid, name, price in services
        ]
        keyboard.append([InlineKeyboardButton("🔙 Orqaga", callback_data=f"doctor_{context.user_data['doctor_id']}")])
        await query.edit_message_text("🛠 Qo‘shiladigan xizmatni tanlang:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("select_payment_service_"):
        service_id = int(data.split("_")[-1])
        context.user_data["service_id"] = service_id
        await query.edit_message_text("💵 To‘lov summasini kiriting:")
        return ENTER_PAYMENT

    elif data.startswith("request_del_"):
        doctor_id = int(data.split("_")[2])
        context.user_data["delete_doctor_id"] = doctor_id
        keyboard = [
            [InlineKeyboardButton("✅ Ha, o‘chirilsin", callback_data=f"confirm_del_{doctor_id}")],
            [InlineKeyboardButton("❌ Yo‘q, bekor qilish", callback_data="cancel_del")]
        ]
        await query.edit_message_text(
            "❗️ Siz rostdan ham ushbu doktorni o‘chirmoqchimisiz?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    elif data.startswith("confirm_del_"):
        doctor_id = int(data.split("_")[2])
        delete_doctor(doctor_id)
        await query.edit_message_text("✅ Doktor o‘chirildi.", reply_markup=back_button)


    elif data == "cancel_del":
        await query.edit_message_text("❌ O‘chirish bekor qilindi.", reply_markup=back_button)

    # Orqaga qaytish
    elif data == "back_to_menu":
        await start(update, context)

    elif data == "report_main":
        return await start_report(update, context)

async def process_debt_closing(update, context):
    try:
        amount = float(update.message.text)
    except ValueError:
        await update.message.reply_text("❌ To‘g‘ri raqam kiriting.")
        return ENTER_DEBT_AMOUNT

    doctor_id = context.user_data.get("doctor_id")
    if not doctor_id:
        await update.message.reply_text("❌ Doktor aniqlanmadi.", reply_markup=back_button)
        return ConversationHandler.END

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO pending_debts (doctor_id, amount, created_at)
                VALUES (%s, %s, NOW())
                ON CONFLICT (doctor_id)
                DO UPDATE SET amount = pending_debts.amount + EXCLUDED.amount,
                              created_at = NOW();
            """, (doctor_id, amount))
            conn.commit()

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT telegram_id, name FROM doctors WHERE id = %s", (doctor_id,))
            doctor = cur.fetchone()

    if doctor:
        doctor_telegram_id, doctor_name = doctor
        message_text = f"📩 Hurmatli {doctor_name}, sizga {amount:,.0f} so‘m qarz qo‘shildi."
        try:
            await context.bot.send_message(chat_id=doctor_telegram_id, text=message_text)
        except Exception as e:
            print(f"⚠️ Doktorga xabar yuborilmadi: {e}")

    await update.message.reply_text(
        f"✅ Doktorga {amount:,.0f} so‘m qarz qo‘shildi. Bu haqida xabar doktorga"
        f" yuborildi",
        reply_markup=back_button
    )

    return ConversationHandler.END

async def process_service_payment(update, context):
    amount = float(update.message.text)
    doctor_id = context.user_data["doctor_id"]

    service_id = context.user_data.get("service_id")
    service_name = context.user_data.get("service_name")

    add_payment(service_id, amount, doctor_id, service_name)

    if service_name:
        await update.message.reply_text(f"💳 {service_name} uchun {amount} so‘m to‘lov qo‘shildi.", reply_markup=back_button)
    else:
        await update.message.reply_text(f"💳 {amount} so‘m to‘lov qo‘shildi.", reply_markup=back_button)
    return ConversationHandler.END



# 1-qadam: Ism
async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text.strip()
    await update.message.reply_text("📱 Telefon raqamini yuboring:")
    return PHONE

async def get_telegram_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_input = update.message.text.strip()

    name = context.user_data["name"]
    phone = context.user_data["phone"]

    if telegram_input.startswith("@"):
        telegram_input = telegram_input[1:]

    try:
        user = await update.get_bot().get_chat(telegram_input)
        telegram_id = user.id
    except Exception as e:
        await update.message.reply_text(
            "❌ Foydalanuvchi topilmadi.\n"
            "❗ Iltimos, u botga /start buyrug‘ini yuborganligiga ishonch hosil qiling."
        )
        print("❌ get_chat error:", e)
        return TELEGRAM_ID

    add_doctor(name, phone, telegram_id)

    await update.message.reply_text(
        f"✅ Doktor qo‘shildi:\n👨‍⚕️ {name}\n📞 {phone}\n🆔 Telegram ID: {telegram_id}",
        reply_markup=back_button
    )
    return ConversationHandler.END


# Xizmat nomi
async def get_service_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["service_name"] = update.message.text
    await update.message.reply_text("💰 Xizmat narxini kiriting (raqam):")
    return SERVICE_PRICE

# Xizmat narxi
async def get_service_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        price = float(update.message.text)
    except ValueError:
        await update.message.reply_text("❌ Raqamni to‘g‘ri kiriting.")
        return SERVICE_PRICE

    name = context.user_data.get("service_name")
    doctor_id = context.user_data.get("doctor_id")

    print(f"📥 Xizmat: {name}, narx: {price}, doctor_id: {doctor_id}")

    if doctor_id:
        print("✅ Doktor uchun xizmat qo‘shilmoqda")
        add_service(doctor_id, name, price)

        await update.message.reply_text(
            f"✅ Xizmat qo‘shildi (doktor uchun):\n🔹 {name} - {price:.0f} so‘m",
            reply_markup=back_button
        )
    else:
        print("ℹ️ Umumiy xizmat qo‘shilmoqda")
        add_service(None, name, price)
        await update.message.reply_text(
            f"✅ Umumiy xizmat qo‘shildi:\n🔹 {name} - {price:.0f} so‘m",
            reply_markup=back_button
        )

    return ConversationHandler.END


async def cancel_close_debt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("❌ Amaliyot bekor qilindi.", reply_markup=back_button)
    return ConversationHandler.END


# 💰 To‘lov summasi
async def enter_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text)
        if amount <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Iltimos, to‘g‘ri raqam kiriting.")
        return ENTER_PAYMENT

    doctor_id = context.user_data.get("doctor_id")
    if not doctor_id:
        await update.message.reply_text("❌ Doktor aniqlanmadi.", reply_markup=back_button)
        return ConversationHandler.END
    else:
        add_payment(None, amount, doctor_id)
        await update.message.reply_text(f"✅ {amount:.0f} so‘m to‘lov saqlandi.", reply_markup=back_button)

    return ConversationHandler.END


async def start_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("✅ start_payment ishladi")
    query = update.callback_query
    await query.answer()

    # ❌ Eski service-related ma'lumotlarni tozalash
    context.user_data.pop("selected_service_name", None)
    context.user_data.pop("selected_service_id", None)
    context.user_data.pop("selected_service_price", None)

    doctor_id = context.user_data.get("doctor_id")
    if not doctor_id:
        await query.edit_message_text("❌ Doktor aniqlanmadi.", reply_markup=back_button)
        return ConversationHandler.END

    await query.edit_message_text("💳 To‘lov summasini kiriting:")
    context.user_data["doctor_id"] = doctor_id
    return ENTER_PAYMENT_AMOUNT


# Bekor qilish
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Jarayon bekor qilindi.", reply_markup=back_button)
    return ConversationHandler.END


async def select_global_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    service_id = int(query.data.split("_")[-1])
    context.user_data["selected_service_id"] = service_id

    service = get_service_by_id(service_id)
    if not service:
        await query.edit_message_text("❌ Xizmat topilmadi.", reply_markup=back_button)
        return ConversationHandler.END

    context.user_data["selected_service_name"] = service["name"]
    context.user_data["selected_service_price"] = service["price"]

    await query.edit_message_text(f"📦 {service['name']} sonini kiriting:")
    return SELECT_SERVICE_QUANTITY


# Botni ishga tushirish
async def main():
    create_tables()

    app = ApplicationBuilder().token(TOKEN).request(request).build()

    await app.initialize()


    conv_edit_doctor_name = ConversationHandler(
        entry_points=[CallbackQueryHandler(edit_name_, pattern="^edit_name_\\d+$")],
        states={
            EDIT_DOCTOR_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, save_new_doctor_name)
            ]
        },
        fallbacks=[CommandHandler("start", start), CommandHandler("cancel", cancel)],
    )

    service_quantity_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(show_services_for_payment, pattern="^add_service$")
        ],
        states={
            SELECT_SERVICE_QUANTITY: [
                CallbackQueryHandler(select_service, pattern="^select_service_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, ask_service_quantity)
            ],
        },
        fallbacks=[CommandHandler("start", start), CommandHandler("cancel", cancel)],
    )

    # Doktor qo‘shish
    conv_add_doctor = ConversationHandler(
        entry_points=[CallbackQueryHandler(handle_menu_selection, pattern="^add_doctor$")],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            TELEGRAM_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_telegram_id)],  # ✅ BU QATORNI QO‘SH

        },
        fallbacks=[CommandHandler("start", start), CommandHandler("cancel", cancel)],
    )

    # ConversationHandler yaratish
    phone_conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(add_phone_request, pattern="^add_phone_")
        ],
        states={
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    conv_payment = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_payment, pattern="^add_payment$"),
            CallbackQueryHandler(handle_menu_selection, pattern="^close_debt$"),
            CallbackQueryHandler(handle_menu_selection, pattern="^add_debt$")

        ],
        states={
            ENTER_PAYMENT_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_service_payment)
            ],
            ENTER_DEBT_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_debt_closing)
            ],
        },
        fallbacks=[CommandHandler("start", start), CommandHandler("cancel", cancel)],
    )

    # Xizmat qo‘shish
    conv_add_service = ConversationHandler(
        entry_points=[CallbackQueryHandler(handle_menu_selection, pattern="^add_service_direct$")],
        states={
            SERVICE_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_service_name)],
            SERVICE_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_service_price)],
        },
        fallbacks=[CommandHandler("start", start), CommandHandler("cancel", cancel)],
    )

    report_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_report, pattern="^report_main$")],
        states={
            ASK_REPORT_RANGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_report_range)
            ],
        },
        fallbacks=[CommandHandler("start", start), CommandHandler("cancel", cancel)],
    )


    conv_start = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={},  # start tugagach hech qanday state yo‘q — lekin agar kerak bo‘lsa, qo‘shasiz
        fallbacks=[],
    )

    conv_report = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_report, pattern="^report_main$")],
        states={
            ASK_REPORT_RANGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_report_range)
            ],
        },
        fallbacks=[CommandHandler("start", start), CommandHandler("cancel", cancel)],
    )

    # 1️⃣ Asosiy ConversationHandler’lar
    app.add_handler(conv_start)
    app.add_handler(conv_add_doctor)
    app.add_handler(conv_add_service)
    app.add_handler(conv_payment)
    app.add_handler(conv_report)
    app.add_handler(phone_conv_handler)
    app.add_handler(CallbackQueryHandler(back_to_user_menu, pattern="^back_to_user_menu$"))
    app.add_handler(conv_edit_doctor_name)
    app.add_handler(CallbackQueryHandler(select_global_service, pattern="^select_global_service_\\d+$"))
    app.add_handler(CallbackQueryHandler(my_profile, pattern="^my_profile$"))
    app.add_handler(report_handler)
    app.add_handler(CallbackQueryHandler(show_services_for_payment, pattern="^add_service_to_doctor$"))
    app.add_handler(CallbackQueryHandler(select_service, pattern="^select_service_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, ask_service_quantity))
    app.add_handler(CallbackQueryHandler(handle_menu_selection))


    print("🤖 Bot ishga tushdi...")
    await app.run_polling()


if __name__ == "__main__":
    asyncio.run(main())
