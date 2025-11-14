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

    conn.commit()
    cur.close()
    conn.close()



async def my_profile(update, context):
    query = update.callback_query
    telegram_id = query.from_user.id

    # 1. Xizmatlar va to‘lovlar ma'lumotlarini olish
    services = get_services_summary_by_doctor(telegram_id)
    payments = get_payments_by_doctor(telegram_id)

    # 2. Xizmatlarni guruhlash
    from collections import defaultdict
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
        service_lines.append(f"{name} — {q} ta × {p:.0f} = {total:.0f} so‘m")

    services_text = "\n".join(service_lines) if service_lines else "Hali xizmatlar yo‘q."

    # 3. To‘lovlar (2ta qiymatga moslashtiramiz)
    total_paid = 0
    payment_lines = []
    for amount, created_at in payments:
        total_paid += float(amount)
        if hasattr(created_at, "strftime"):
            date_str = created_at.strftime("%Y-%m-%d %H:%M")
        else:
            date_str = str(created_at)
        payment_lines.append(f"{date_str} — {float(amount):,.0f} so‘m")

    payments_text = "\n".join(payment_lines) if payment_lines else "To‘lovlar yo‘q."

    # 4. Qarzdorlik
    debt = max(total_expected - total_paid, 0)

    # 5. Matnni yig‘ish
    text = (
        "<b>Profilingiz</b>\n\n"
        "<b>Xizmatlaringiz:</b>\n"
        f"{services_text}\n\n"
        "<b>To‘lovlar:</b>\n"
        f"{payments_text}\n\n"
        f"<b>Qarzdorlik:</b> {debt:,.0f} so‘m"
    )

    await query.edit_message_text(text=text, parse_mode="HTML")

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

    # 🛠 Bazada yangilash
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE doctors SET name = %s WHERE id = %s", (new_name, doctor_id))
            conn.commit()

    # 🔙 Orqaga tugmasi
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Orqaga", callback_data=f"doctor_{doctor_id}")]
    ])

    await update.message.reply_text(
        text="✅ Ism muvaffaqiyatli yangilandi.",
        reply_markup=keyboard
    )

    # 🧹 Contextni tozalash
    context.user_data.pop("edit_doctor_id", None)

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

import logging

def get_service_by_id(service_id):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, price FROM services WHERE id = %s", (service_id,))
            row = cur.fetchone()

    if not row:
        return None

    return {
        "id": row[0],
        "name": row[1],
        "price": float(row[2]),
    }

def add_payment(service_id, amount, doctor_id, service_name=None):
    if not service_id:
        service_name = None  # ❗ xizmat yo'q bo'lsa, nomini ham saqlamaymiz
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO payments (service_id, amount, doctor_id, service_name)
                VALUES (%s, %s, %s, %s)
            """, (service_id, amount, doctor_id, service_name))

def get_payments_by_doctor(doctor_id):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT amount, created_at
                FROM payments
                WHERE doctor_id = %s
                ORDER BY created_at ASC
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

def get_services_summary_by_doctor(doctor_id):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT s.name, s.price, ds.quantity, ds.created_at
                FROM doctor_services ds
                JOIN services s ON s.id = ds.service_id
                WHERE ds.doctor_id = %s
                ORDER BY ds.created_at ASC
            """, (doctor_id,))
            return cur.fetchall()


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

