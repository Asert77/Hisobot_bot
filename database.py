from datetime import datetime, timedelta
import psycopg2
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
import pytz
from dotenv import load_dotenv
import os
from datetime import datetime


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

from telegram.error import BadRequest

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import BadRequest
import pytz
from datetime import datetime

async def my_profile(update, context):
    query = update.callback_query
    user = update.effective_user
    telegram_id = user.id

    uzbek_tz = pytz.timezone("Asia/Tashkent")

    # 🩺 Doktor ma'lumotlarini olish
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, phone FROM doctors WHERE telegram_id = %s", (telegram_id,))
            doctor = cur.fetchone()

    if not doctor:
        return await query.edit_message_text("❌ Siz ro‘yxatdan o‘tmagansiz. Iltimos, administrator bilan bog‘laning.")

    doctor_id, doctor_name, phone = doctor

    # 💰 To‘lovlar
    payments = get_payments_by_doctor(doctor_id)
    services = get_services_by_doctor(doctor_id)
    services_summary = get_services_summary_by_doctor(doctor_id)  # ✅ nom, qty, va created_at bo‘lishi kerak

    total_paid = sum(float(amount) for amount, _ in payments)
    total_expected = get_expected_total_by_doctor(doctor_id)
    debt = max(total_expected - total_paid, 0)

    # 🧾 Xizmatlar ro‘yxati
    service_count = len(services)
    total_services_price = float(total_expected)

    if services_summary:
        service_lines = []
        for service_name, qty, created_at in services_summary:
            if hasattr(created_at, "astimezone"):
                created_time = created_at.astimezone(uzbek_tz).strftime("%Y-%m-%d %H:%M")
            else:
                created_time = str(created_at)
            service_lines.append(f"• {service_name} — {qty} ta ({created_time})")
        services_text = "\n".join(service_lines)
    else:
        services_text = "Hech qanday xizmat qo‘shilmagan."

    # 💸 To‘lovlar
    if payments:
        payment_lines = []
        for amount, created_at in payments:
            if hasattr(created_at, "astimezone"):
                local_time = created_at.astimezone(uzbek_tz).strftime("%Y-%m-%d %H:%M")
            else:
                local_time = str(created_at)
            payment_lines.append(f"{local_time} — {float(amount):,.0f} so‘m")
        payments_text = "\n".join(payment_lines)
    else:
        payments_text = "Hech qanday to‘lov yo‘q."

    # 📋 Yakuniy matn
    text = (
        f"<b>👤 Doktor:</b> {doctor_name}\n"
        f"<b>📞 Telefon:</b> {phone or '—'}\n\n"
        f"<b>💰 To‘langan jami:</b> {total_paid:,.0f} so‘m\n"
        f"<b>🧾 Umumiy xizmatlar:</b> {total_services_price:,.0f} so‘m\n"
        f"<b>💸 Qarzdorlik:</b> {debt:,.0f} so‘m\n"
        f"<b>🔢 Umumiy xizmatlar soni:</b> {service_count} ta\n\n"
        f"<b>🧩 Qo‘shilgan xizmatlar:</b>\n{services_text}\n\n"
        f"<b>🕒 So‘nggi to‘lovlar:</b>\n{payments_text}\n\n"
        f"<i>Yangilanish vaqti: {datetime.now(uzbek_tz).strftime('%H:%M:%S')}</i>"
    )

    # 🔙 Orqaga tugmasi
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("◀️ Orqaga", callback_data="my_profile")]
    ])

    try:
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)
    except BadRequest as e:
        if "Message is not modified" in str(e):
            pass
        else:
            raise

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

def get_services_by_doctor(doctor_id):
    uzbek_tz = pytz.timezone("Asia/Tashkent")
    results = []

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT s.name, s.price, ds.quantity, ds.created_at
                FROM doctor_services ds
                JOIN services s ON s.id = ds.service_id
                WHERE ds.doctor_id = %s
                ORDER BY ds.created_at ASC
            """, (doctor_id,))
            rows = cur.fetchall()

    for row in rows:
        try:
            name = row[0]
            price = float(row[1])
            quantity = int(row[2])
            created_at = row[3]

            # ✅ Sana to‘g‘rilash
            if created_at is None:
                created_at = datetime.now(uzbek_tz)
            elif not hasattr(created_at, "astimezone"):
                created_at = datetime.strptime(str(created_at), "%Y-%m-%d %H:%M:%S")
            if created_at.tzinfo is None:
                created_at = pytz.UTC.localize(created_at)
            created_at = created_at.astimezone(uzbek_tz)
            results.append({
                "name": name,
                "price": price,
                "quantity": quantity,
                "created_at": created_at
            })
        except Exception as e:
            print(f"⚠️ Xizmatni o‘qishda xato: {e}")
            continue

    return results

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

from datetime import datetime

def add_payment(service_id, amount, doctor_id, service_name=None, created_at=None):
    with get_connection() as conn:
        with conn.cursor() as cur:
            now = datetime.utcnow()  # UTC vaqtni saqlaymiz
            cur.execute("""
                INSERT INTO payments (service_id, amount, doctor_id, service_name, created_at)
                VALUES (%s, %s, %s, %s, %s)
            """, (service_id, amount, doctor_id, service_name, created_at or now))
        conn.commit()

def get_payments_by_doctor(doctor_id):

    uzbek_tz = pytz.timezone("Asia/Tashkent")
    results = []

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT amount, created_at
                FROM payments
                WHERE doctor_id = %s
                ORDER BY created_at ASC
            """, (doctor_id,))
            rows = cur.fetchall()

    for row in rows:
        try:
            amount = float(row[0])
            created_at = row[1]

            # Agar sana null bo‘lsa yoki noto‘g‘ri bo‘lsa, hozirgi vaqtni ishlatamiz
            if created_at is None:
                created_at = datetime.now(uzbek_tz)
            elif not hasattr(created_at, "astimezone"):
                created_at = datetime.strptime(str(created_at), "%Y-%m-%d %H:%M:%S")

            if created_at.tzinfo is None:
                created_at = pytz.UTC.localize(created_at)
            created_at = created_at.astimezone(uzbek_tz)

            results.append((amount, created_at))
        except Exception as e:
            print(f"⚠️ To‘lovni o‘qishda xato: {e}")
            continue

    return results

def add_doctor_service(doctor_id, service_id, quantity, created_at=None):
    conn = get_connection()
    cur = conn.cursor()

    now = datetime.utcnow()  # UTC sifatida saqlanadi
    cur.execute("""
        INSERT INTO doctor_services (doctor_id, service_id, quantity, created_at)
        VALUES (%s, %s, %s, %s)
    """, (doctor_id, service_id, quantity, created_at or now))

    conn.commit()
    cur.close()
    conn.close()

def get_services_summary_by_doctor(doctor_id):
    uzbek_tz = pytz.timezone("Asia/Tashkent")

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    s.name AS service_name,
                    SUM(ds.quantity) AS total_quantity,
                    SUM(ds.quantity * s.price) AS total_price,
                    MAX(ds.created_at) AS last_added
                FROM doctor_services ds
                JOIN services s ON ds.service_id = s.id
                WHERE ds.doctor_id = %s
                GROUP BY s.name
                ORDER BY last_added DESC
            """, (doctor_id,))
            rows = cur.fetchall()

    # Har bir sana UTC bo‘lsa, Tashkent vaqtiga o‘tkazamiz
    results = []
    for row in rows:
        name, qty, total, created_at = row
        if created_at and hasattr(created_at, "astimezone"):
            created_at = created_at.astimezone(uzbek_tz)
        results.append((name, int(qty), float(total), created_at))

    return results


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

