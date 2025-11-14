from fpdf import FPDF
import os
from datetime import datetime
import pytz
UZBEK_TZ = pytz.timezone("Asia/Tashkent")

def safe_text(text):
    """Unicode tutuq va belgilarni PDF uchun xavfsiz formatga o‘tkazadi."""
    if not text:
        return ""
    replacements = {
        "‘": "'", "’": "'", "ʻ": "'", "ʼ": "'", "´": "'", "ˋ": "'", "ʹ": "'", "ʽ": "'",
        "“": '"', "”": '"', "–": "-", "—": "-", "…": "...",
    }
    for bad, good in replacements.items():
        text = text.replace(bad, good)
    return text


class PDF(FPDF):
    def header(self):
        self.set_font("Arial", "B", 14)
        self.cell(0, 10, safe_text("Doktor bo‘yicha hisobot"), align="C", ln=True)
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font("Arial", "I", 8)
        self.cell(0, 10, f"Sahifa {self.page_no()}", align="C")


def generate_pdf_report(doctor_name, doctor_id, payments, total_expected, total_paid, services_summary):
    pdf = PDF()
    pdf.add_page()
    pdf.set_font("Arial", "", 12)

    # --- Doktor haqida ma'lumot ---
    pdf.cell(0, 10, safe_text(f"Doktor: {doctor_name} (ID: {doctor_id})"), ln=True)
    pdf.cell(0, 10, f"Sana: {datetime.now().strftime('%Y-%m-%d %H:%M')}", ln=True)
    pdf.ln(5)

    # --- Xizmatlar jadvali ---
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, safe_text("Xizmatlar:"), ln=True)
    pdf.set_font("Arial", "", 11)

    pdf.cell(60, 8, safe_text("Xizmat nomi"), border=1)
    pdf.cell(25, 8, safe_text("Soni"), border=1)
    pdf.cell(40, 8, safe_text("Jami (so‘m)"), border=1)
    pdf.cell(50, 8, safe_text("Sana va vaqt"), border=1, ln=True)

    total_service_count = 0  # Umumiy xizmatlar soni

    for name, price, quantity, created_at in services_summary:
        total = price * quantity
        total_service_count += quantity
        date_str = created_at.strftime("%Y-%m-%d %H:%M") if isinstance(created_at, datetime) else str(created_at)

        pdf.cell(60, 8, safe_text(str(name)), border=1)
        pdf.cell(25, 8, str(quantity), border=1)
        pdf.cell(40, 8, f"{total:,.0f}", border=1)
        pdf.cell(50, 8, date_str, border=1, ln=True)

    pdf.ln(10)

    # --- To‘lovlar jadvali ---
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, safe_text("To‘lovlar:"), ln=True)
    pdf.set_font("Arial", "", 11)

    pdf.cell(50, 8, safe_text("Miqdori (so‘m)"), border=1)
    pdf.cell(70, 8, safe_text("Sana va vaqt"), border=1, ln=True)

    for amount, date in payments:
        date_str = date.strftime("%Y-%m-%d %H:%M") if isinstance(date, datetime) else str(date)
        pdf.cell(50, 8, f"{float(amount):,.0f}", border=1)
        pdf.cell(70, 8, date_str, border=1, ln=True)

    pdf.ln(10)

    # --- Yakuniy hisob ---
    debt = total_expected - total_paid
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, safe_text("Yakun:"), ln=True)
    pdf.set_font("Arial", "", 11)
    pdf.cell(0, 8, safe_text(f"Umumiy xizmatlar: {total_expected:,.0f} so‘m"), ln=True)
    pdf.cell(0, 8, safe_text(f"To‘langan: {total_paid:,.0f} so‘m"), ln=True)
    pdf.cell(0, 8, safe_text(f"Qarzdorlik: {debt:,.0f} so‘m"), ln=True)
    pdf.cell(0, 8, safe_text(f"Umumiy xizmatlar soni: {total_service_count} ta"), ln=True)

    # --- PDF saqlash ---
    filename = f"doctor_report_{doctor_id}.pdf"
    filepath = os.path.join("/app", filename)
    pdf.output(filepath)
    return filepath