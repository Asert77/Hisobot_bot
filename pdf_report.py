from fpdf import FPDF
import os
from datetime import datetime
import re


def remove_emojis(text: str):
    """Matndan emoji va latin-1 bo‘lmagan belgilarni olib tashlaydi."""
    if not text:
        return ""
    # Emoji va boshqa maxsus belgilarni olib tashlash
    emoji_pattern = re.compile("["
        u"\U0001F600-\U0001F64F"  # emoticons
        u"\U0001F300-\U0001F5FF"  # symbols & pictographs
        u"\U0001F680-\U0001F6FF"  # transport & map
        u"\U0001F1E0-\U0001F1FF"  # flags
        u"\u2014"                 # uzun chiziq —
        "]+", flags=re.UNICODE)
    text = emoji_pattern.sub(r'', text)
    # Latin-1’dan tashqaridagi belgilarni ham olib tashlaymiz
    return ''.join(ch if ord(ch) < 256 else '?' for ch in text)


class PDF(FPDF):
    def header(self):
        self.set_font("Arial", "B", 14)
        self.cell(0, 10, remove_emojis("Doktor bo‘yicha hisobot"), align="C", ln=True)
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font("Arial", "I", 8)
        self.cell(0, 10, f"Sahifa {self.page_no()}", align="C")


def generate_pdf_report(doctor_name, doctor_id, payments, total_expected, total_paid, services_summary):
    pdf = PDF()
    pdf.add_page()
    pdf.set_font("Arial", "", 12)

    # 👨‍⚕️ Doktor haqida
    pdf.cell(0, 10, remove_emojis(f"Doktor: {doctor_name} (ID: {doctor_id})"), ln=True)
    pdf.cell(0, 10, remove_emojis(f"Sana: {datetime.now().strftime('%Y-%m-%d %H:%M')}"), ln=True)
    pdf.ln(5)

    # 💰 Xizmatlar jadvali
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, remove_emojis("Xizmatlar:"), ln=True)
    pdf.set_font("Arial", "", 11)

    pdf.cell(100, 8, remove_emojis("Xizmat nomi"), border=1)
    pdf.cell(30, 8, remove_emojis("Soni"), border=1)
    pdf.cell(50, 8, remove_emojis("Jami (so‘m)"), border=1, ln=True)

    for name, price, quantity, *_ in services_summary:
        total = price * quantity
        pdf.cell(100, 8, remove_emojis(str(name)), border=1)
        pdf.cell(30, 8, str(quantity), border=1)
        pdf.cell(50, 8, f"{total:,.0f}", border=1, ln=True)

    pdf.ln(10)

    # 💳 To‘lovlar
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, remove_emojis("To‘lovlar:"), ln=True)
    pdf.set_font("Arial", "", 11)

    pdf.cell(50, 8, remove_emojis("Miqdori (so‘m)"), border=1)
    pdf.cell(60, 8, remove_emojis("Sana"), border=1, ln=True)

    for amount, date, *_ in payments:
        date_str = date.strftime("%Y-%m-%d") if isinstance(date, datetime) else str(date)
        pdf.cell(50, 8, f"{float(amount):,.0f}", border=1)
        pdf.cell(60, 8, remove_emojis(date_str), border=1, ln=True)

    pdf.ln(10)

    # 🧾 Yakuniy hisobot
    debt = total_expected - total_paid
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, remove_emojis("Yakun:"), ln=True)
    pdf.set_font("Arial", "", 11)
    pdf.cell(0, 8, remove_emojis(f"Umumiy xizmatlar: {total_expected:,.0f} so‘m"), ln=True)
    pdf.cell(0, 8, remove_emojis(f"To‘langan: {total_paid:,.0f} so‘m"), ln=True)
    pdf.cell(0, 8, remove_emojis(f"Qarzdorlik: {debt:,.0f} so‘m"), ln=True)

    # 📁 PDF saqlash
    filename = f"doctor_report_{doctor_id}.pdf"
    filepath = os.path.join("/app", filename)
    pdf.output(filepath)
    return filepath