from datetime import datetime, timedelta
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal

import psycopg2
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler

from dotenv import load_dotenv
import os

load_dotenv()  # .env faylni yuklaydi

TOKEN = os.getenv("TOKEN")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = int(os.getenv("DB_PORT", 5432))


# 📌 Bazaga ulanish
def get_connection():
    return psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT
    )

# 📌 Jadval yaratish
def create_tables():
    conn = get_connection()
    cur = conn.cursor()

    # 🩺 Doktorlar
    cur.execute("""
        CREATE TABLE IF NOT EXISTS doctors (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            phone TEXT NOT NULL
        );
    """)

    # 🛠 Umumiy xizmatlar
    cur.execute("""
        CREATE TABLE IF NOT EXISTS services (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            price NUMERIC NOT NULL
        );
    """)

    # 📦 Doktorning tanlagan xizmatlari (bu endi alohida)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS doctor_services (
            id SERIAL PRIMARY KEY,
            doctor_id INTEGER REFERENCES doctors(id) ON DELETE CASCADE,
            service_id INTEGER REFERENCES services(id),
            quantity INTEGER DEFAULT 1
);
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS pending_debts (
            doctor_id INTEGER PRIMARY KEY REFERENCES doctors(id) ON DELETE CASCADE,
            amount NUMERIC NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # 💰 To‘lovlar
    cur.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id SERIAL PRIMARY KEY,
            doctor_id INTEGER,
            service_id INTEGER,
            amount NUMERIC,
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            service_name TEXT
        );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS doctor_service_notifications (
        id SERIAL PRIMARY KEY,
        doctor_id INTEGER NOT NULL REFERENCES doctors(id) ON DELETE CASCADE,
        message TEXT NOT NULL,
        sent BOOLEAN DEFAULT FALSE,
        confirmed BOOLEAN DEFAULT FALSE,
        sent_at TIMESTAMP NOT NULL,
        remind_at TIMESTAMP NOT NULL
);

    """)

    conn.commit()
    cur.close()
    conn.close()


async def my_profile(update, context):
    query = update.callback_query
    telegram_id = query.from_user.id

    # ✅ 1. Doctorni olish
    doctor = get_doctor_id_by_telegram_id(telegram_id)
    if not doctor:
        await query.edit_message_text("⚠️ Siz ro'yxatdan o'tmagansiz.")
        return

    doctor_id = doctor["id"]

    # ✅ 2. Ma'lumotlarni olish
    services = get_services_summary_by_doctor(doctor_id)
    payments = get_payments_by_doctor(doctor_id)

    # ✅ 3. Xizmatlarni guruhlash
    service_summary = defaultdict(lambda: {"quantity": 0, "price": 0})
    for name, price, quantity, *_ in services:
        if price == 0 or quantity == 0:
            continue
        service_summary[name]["quantity"] += quantity
        service_summary[name]["price"] = price

    service_lines = []
    total_expected = 0
    for name, data in service_summary.items():
        q = data["quantity"]
        p = data["price"]
        total = q * p
        total_expected += total
        service_lines.append(f"• {name} — {q} ta × {p:.1f} = {total:.1f} so‘m")

    services_text = "\n".join(service_lines) if service_lines else "🚫 Hali xizmatlar yo‘q."

    # ✅ 4. To‘lovlar
    total_paid = sum(float(amount) for amount, _, _ in payments)
    payment_lines = [
        f"• {date} — {amount:.1f} so‘m" for amount, _, date in payments
    ]
    payments_text = "\n".join(payment_lines) if payment_lines else "🚫 To‘lovlar yo‘q."

    # ✅ 5. Qarzdorlik
    debt = max(total_expected - total_paid, 0)

    # ✅ 6. Matn
    text = (
        "🧾 <b>Profilingiz</b>\n\n"
        "🛠 <b>Xizmatlaringiz:</b>\n"
        f"{services_text}\n\n"
        "💰 <b>So‘nggi to‘lovlar:</b>\n"
        f"{payments_text}\n\n"
        f"❌ <b>Qarzdorlik:</b> {debt:.1f} so‘m"
    )


# ➕ Doktor qo‘shish
def add_doctor(name: str, phone: str, telegram_id: int):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO doctors (name, phone, telegram_id) VALUES (%s, %s, %s)",
                (name, phone, telegram_id)
            )

def doctor_exists_by_telegram(telegram_id):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM doctors WHERE telegram_id = %s", (telegram_id,))
            return cur.fetchone() is not None

def add_doctor_auto(telegram_id, full_name, username):
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Avval tekshiramiz: doktor mavjudmi
            cur.execute("SELECT id FROM doctors WHERE telegram_id = %s", (telegram_id,))
            if cur.fetchone():
                return  # allaqachon mavjud, hech narsa qilmaymiz

            # Agar mavjud bo‘lmasa, qo‘shamiz
            cur.execute("""
                INSERT INTO doctors (name, telegram_id, username)
                VALUES (%s, %s, %s)
            """, (full_name, telegram_id, username))
            conn.commit()

async def save_new_doctor_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_name = update.message.text.strip()
    doctor_id = context.user_data.get("edit_doctor_id")

    if not doctor_id:
        await update.message.reply_text("⚠️ Noma'lum xatolik yuz berdi.")
        return ConversationHandler.END

    # Bazada yangilash
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE doctors SET name = %s WHERE id = %s", (new_name, doctor_id))
            conn.commit()
    keyboard = [
        [InlineKeyboardButton("🔙 Orqaga", callback_data=f"open_doctor_{doctor_id}")]
    ]
    markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text("✅ Ism muvaffaqiyatli yangilandi.", reply_markup=markup)
    return ConversationHandler.END


def get_all_doctors():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, phone FROM doctors")
            return cur.fetchall()

# ❌ Doktorni o‘chirish
def delete_doctor(doctor_id: int):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM doctors WHERE id = %s", (doctor_id,))

# ➕ Xizmat (umumiy bazaga)
def add_service(doctor_id, name, price, created_at=None):
    conn = get_connection()
    cur = conn.cursor()

    if created_at:
        cur.execute("""
            INSERT INTO services (doctor_id, name, price, created_at)
            VALUES (%s, %s, %s, %s)
        """, (doctor_id, name, price, created_at))
    else:
        cur.execute("""
            INSERT INTO services (name, price)
            VALUES (%s, %s)
        """, (name, price))
    conn.commit()
    conn.close()


def delete_payments_by_month(doctor_id, month_date):
    month_start = month_date.replace(day=1)
    next_month = (month_start + timedelta(days=32)).replace(day=1)

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                DELETE FROM payments
                WHERE doctor_id = %s
                AND date >= %s
                AND date < %s
            """, (doctor_id, month_start, next_month))



def close_debts(doctor_id, amount):
    """
    Foydalanuvchi 'qarzni yopish' tugmasini bosganda ishlatiladi.
    Joriy oydagi barcha xizmatlar va to‘lovlar o‘chiriladi.
    Qoldiq boshqa oylarga o'tkazilmaydi.
    """
    now = datetime.now()
    month_start = now.replace(day=1)
    next_month = (month_start + timedelta(days=32)).replace(day=1)

    with get_connection() as conn:
        with conn.cursor() as cur:
            # Joriy oydagi xizmatlarni o‘chirish
            cur.execute("""
                DELETE FROM doctor_services
                WHERE doctor_id = %s
                AND created_at >= %s AND created_at < %s
            """, (doctor_id, month_start, next_month))

            # Joriy oydagi to‘lovlarni o‘chirish
            cur.execute("""
                DELETE FROM payments
                WHERE doctor_id = %s
                AND date >= %s AND date < %s
            """, (doctor_id, month_start, next_month))

    return [], 0  # qaytarilishi shart bo‘lgan struktura


# 🔁 Barcha xizmatlar (umumiy)
def get_all_services():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, name, price FROM services
                ORDER BY id
            """)
            return cur.fetchall()

async def confirm_close_debt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    doctor_id = context.user_data.get("doctor_id")

    if not doctor_id:
        await query.edit_message_text("❌ Doctor ID topilmadi.")
        return ConversationHandler.END

    # O'chirish amallari
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM doctor_services WHERE doctor_id = %s", (doctor_id,))
            cur.execute("DELETE FROM payments WHERE doctor_id = %s", (doctor_id,))
            conn.commit()

    await query.edit_message_text("✅ Qarzdorlik to‘liq yopildi. Barcha ma'lumotlar o‘chirildi.")
    return ConversationHandler.END

def get_services_by_doctor(doctor_id, start_date=None, end_date=None):
    with get_connection() as conn:
        with conn.cursor() as cur:
            if start_date and end_date:
                cur.execute("""
                    SELECT s.name, ds.quantity, s.price, ds.created_at
                    FROM doctor_services ds
                    JOIN services s ON ds.service_id = s.id
                    WHERE ds.doctor_id = %s AND ds.created_at BETWEEN %s AND %s
                """, (doctor_id, start_date, end_date))
            else:
                cur.execute("""
                    SELECT s.name, ds.quantity, s.price, ds.created_at
                    FROM doctor_services ds
                    JOIN services s ON ds.service_id = s.id
                    WHERE ds.doctor_id = %s
                """, (doctor_id,))
            return cur.fetchall()



def get_doctor_id_by_telegram_id(telegram_id):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM doctors WHERE telegram_id = %s", (telegram_id,))
            row = cur.fetchone()
            return row[0] if row else None

def get_expected_total_by_doctor(doctor_id: int, start_date=None, end_date=None):
    with get_connection() as conn:
        with conn.cursor() as cur:
            if start_date and end_date:
                cur.execute("""
                    SELECT COALESCE(SUM(s.price * ds.quantity), 0)
                    FROM doctor_services ds
                    JOIN services s ON s.id = ds.service_id
                    WHERE ds.doctor_id = %s
                    AND ds.created_at BETWEEN %s AND %s
                """, (doctor_id, start_date, end_date))
            else:
                cur.execute("""
                    SELECT COALESCE(SUM(s.price * ds.quantity), 0)
                    FROM doctor_services ds
                    JOIN services s ON s.id = ds.service_id
                    WHERE ds.doctor_id = %s
                """, (doctor_id,))
            return float(cur.fetchone()[0])

# 🔍 Bitta xizmat
def get_service_by_id(service_id):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, price FROM services WHERE id = %s", (service_id,))
            row = cur.fetchone()
            if row:
                return {"id": row[0], "name": row[1], "price": float(row[2])}
            return None

# 💵 To‘lov qo‘shish
def add_payment(service_id, amount, doctor_id, service_name=None):
    if not service_id:
        service_name = None  # ❗ xizmat yo'q bo'lsa, nomini ham saqlamaymiz
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO payments (service_id, amount, doctor_id, service_name)
                VALUES (%s, %s, %s, %s)
            """, (service_id, amount, doctor_id, service_name))

def get_payments_by_doctor(doctor_id, start_date=None, end_date=None):
    with get_connection() as conn:
        with conn.cursor() as cur:
            if start_date and end_date:
                cur.execute("""
                    SELECT amount, service_name, created_at
                    FROM payments
                    WHERE doctor_id = %s AND created_at BETWEEN %s AND %s
                """, (doctor_id, start_date, end_date))
            else:
                cur.execute("""
                    SELECT amount, service_name, created_at
                    FROM payments
                    WHERE doctor_id = %s
                """, (doctor_id,))
            return cur.fetchall()

def add_doctor_service(doctor_id, service_id, quantity, created_at=None):
    conn = get_connection()
    cur = conn.cursor()
    if created_at:
        cur.execute("""
            INSERT INTO doctor_services (doctor_id, service_id, quantity, created_at)
            VALUES (%s, %s, %s, %s)
        """, (doctor_id, service_id, quantity, created_at))
    else:
        cur.execute("""
            INSERT INTO doctor_services (doctor_id, service_id, quantity)
            VALUES (%s, %s, %s)
        """, (doctor_id, service_id, quantity))
    conn.commit()
    cur.close()
    conn.close()

def get_services_summary_by_doctor(doctor_id, start_date=None, end_date=None):
    with get_connection() as conn:
        with conn.cursor() as cur:
            if start_date and end_date:
                cur.execute("""
                    SELECT s.name, SUM(ds.quantity), s.price, MAX(ds.created_at)
                    FROM doctor_services ds
                    JOIN services s ON ds.service_id = s.id
                    WHERE ds.doctor_id = %s AND ds.created_at BETWEEN %s AND %s
                    GROUP BY s.name, s.price
                    ORDER BY MAX(ds.created_at) DESC
                """, (doctor_id, start_date, end_date))
            else:
                cur.execute("""
                    SELECT s.name, SUM(ds.quantity), s.price, MAX(ds.created_at)
                    FROM doctor_services ds
                    JOIN services s ON ds.service_id = s.id
                    WHERE ds.doctor_id = %s
                    GROUP BY s.name, s.price
                    ORDER BY MAX(ds.created_at) DESC
                """, (doctor_id,))
            return cur.fetchall()


def schedule_notification(doctor_id, message):
    now = datetime.now()
    tomorrow_9am = (now + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
    tomorrow_14pm = (now + timedelta(days=1)).replace(hour=14, minute=0, second=0, microsecond=0)

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO doctor_service_notifications
                (doctor_id, message, sent, confirmed, sent_at, remind_at)
                VALUES (%s, %s, FALSE, FALSE, %s, %s)
            """, (doctor_id, message, tomorrow_9am, tomorrow_14pm))


async def send_scheduled_notifications(context: ContextTypes.DEFAULT_TYPE):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT n.id, n.doctor_id, n.message, d.telegram_id
                FROM doctor_service_notifications n
                JOIN doctors d ON d.id = n.doctor_id
                WHERE n.sent = FALSE AND n.sent_at <= NOW()
            """)
            notifications = cur.fetchall()

    for notif_id, doctor_id, message, telegram_id in notifications:
        # ✅ Xabar yuborilishidan oldin sent = TRUE qilish
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE doctor_service_notifications SET sent = TRUE WHERE id = %s", (notif_id,))

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Ha", callback_data=f"confirm_received_{notif_id}")],
            [InlineKeyboardButton("❌ Yo‘q", callback_data=f"reject_received_{notif_id}")]
        ])

        await context.bot.send_message(
            chat_id=telegram_id,
            text=f"📩 {message}\n\nQabul qildingizmi?",
            reply_markup=keyboard
        )

def get_notification_doctor_id(notif_id):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT doctor_id FROM doctor_service_notifications WHERE id = %s
            """, (notif_id,))
            result = cur.fetchone()
            return result[0] if result else None

async def resend_reminder_notifications(context: ContextTypes.DEFAULT_TYPE):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT n.id, n.doctor_id, n.message, d.telegram_id
                FROM doctor_service_notifications n
                JOIN doctors d ON d.id = n.doctor_id
                WHERE n.sent = TRUE AND n.confirmed = FALSE AND n.remind_at <= NOW()
            """)
            reminders = cur.fetchall()

    for notif_id, doctor_id, message, telegram_id in reminders:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Ha", callback_data=f"confirm_received_{notif_id}")],
            [InlineKeyboardButton("❌ Yo‘q", callback_data=f"reject_received_{notif_id}")]
        ])

        await context.bot.send_message(
            chat_id=telegram_id,
            text=f"🔁 Eslatma!\n{message}\n\nQabul qildingizmi?",
            reply_markup=keyboard
        )


async def handle_notification_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data.startswith("confirm_received_"):
        notif_id = int(data.split("_")[-1])
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE doctor_service_notifications
                    SET confirmed = TRUE
                    WHERE id = %s
                """, (notif_id,))
        await query.edit_message_text("✅ Xizmat qabul qilindi.")
    elif data.startswith("reject_received_"):
        notif_id = int(data.split("_")[-1])
        # Agar yo‘q deb bosgan bo‘lsa, shunchaki qayd etmaslik mumkin (yoki log yuritish)
        await query.edit_message_text("❌ Xizmat rad etildi.")

def delete_notification(notif_id):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM doctor_service_notifications WHERE id = %s", (notif_id,))

def get_doctor_telegram_id(doctor_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT telegram_id FROM doctors WHERE id = %s", (doctor_id,))
    result = cur.fetchone()
    conn.close()
    return result[0] if result else None

def get_doctor_name_by_id(doctor_id):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT name FROM doctors WHERE id = %s", (doctor_id,))
            result = cur.fetchone()
            return result[0] if result else "Noma'lum doktor"


def get_pending_notifications():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, doctor_id, message FROM doctor_service_notifications
                WHERE NOT sent AND sent_at <= NOW()
            """)
            return cur.fetchall()


def mark_notification_sent(notification_id: int):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE doctor_service_notifications
                SET sent = TRUE, sent_at = NOW()
                WHERE id = %s
            """, (notification_id,))
        conn.commit()


def get_reminder_notifications():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, doctor_id, message
                FROM doctor_service_notifications
                WHERE confirmed = FALSE AND remind_at <= NOW()
            """)
            return cur.fetchall()

def mark_notification_confirmed(notification_id):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE doctor_service_notifications
                SET confirmed = TRUE
                WHERE id = %s
            """, (notification_id,))


def confirm_notification(doctor_telegram_id):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE doctor_service_notifications
                SET confirmed = TRUE
                WHERE doctor_id = (
                    SELECT id FROM doctors WHERE telegram_id = %s
                ) AND confirmed = FALSE
            """, (doctor_telegram_id,))

def delete_service_by_id(service_id: int):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM services WHERE id = %s", (service_id,))


def get_monthly_debts(doctor_id):
    with get_connection() as conn:
        with conn.cursor() as cur:
            # JOIN qilib service narxini olamiz
            cur.execute("""
                SELECT
                    DATE_TRUNC('month', ds.created_at) AS month,
                    SUM(s.price * ds.quantity) AS total_services
                FROM doctor_services ds
                JOIN services s ON ds.service_id = s.id
                WHERE ds.doctor_id = %s
                GROUP BY month
                ORDER BY month
            """, (doctor_id,))
            services = dict(cur.fetchall())

            # Har oyda to‘langan summalar
            cur.execute("""
                SELECT
                    DATE_TRUNC('month', created_at) AS month,
                    SUM(amount) AS total_payments
                FROM payments
                WHERE doctor_id = %s
                GROUP BY month
                ORDER BY month
            """, (doctor_id,))
            payments = dict(cur.fetchall())

            # Qarzni hisoblash
            debts = []
            for month, service_total in services.items():
                payment_total = payments.get(month, 0)
                debt = round(service_total - payment_total)
                if debt > 0:
                    debts.append((month, debt))

            return debts

def delete_doctor_services(doctor_id):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM doctor_services WHERE doctor_id = %s", (doctor_id,))

def delete_doctor_services_by_month(doctor_id, month_date):
    month_start = month_date.replace(day=1)
    next_month = (month_start + timedelta(days=32)).replace(day=1)

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                DELETE FROM doctor_services
                WHERE doctor_id = %s
                AND created_at >= %s
                AND created_at < %s
            """, (doctor_id, month_start, next_month))


def delete_services_by_month(doctor_id, month):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                DELETE FROM doctor_services
                WHERE doctor_id = %s
                  AND DATE_TRUNC('month', created_at) = DATE_TRUNC('month', %s::date)
            """, (doctor_id, month))


def get_service_by_name_and_doctor(doctor_id, service_name, month_start):
    """
    Doktorga tegishli, ma'lum bir oyda, shu nomli xizmat mavjudligini tekshiradi
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id FROM doctor_services
                WHERE doctor_id = %s
                  AND name = %s
                  AND DATE_TRUNC('month', created_at) = DATE_TRUNC('month', %s::date)
            """, (doctor_id, service_name, month_start))
            return cur.fetchone()

def delete_doctor_payments_by_month(doctor_id, month_start):
    next_month = (month_start + timedelta(days=32)).replace(day=1)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                DELETE FROM payments
                WHERE doctor_id = %s
                AND created_at >= %s AND created_at < %s
            """, (doctor_id, month_start, next_month))

def get_doctor_by_telegram(telegram_id):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name FROM doctors WHERE telegram_id = %s", (telegram_id,))
            row = cur.fetchone()
            if row:
                return {"id": row[0], "name": row[1]}
            return None

