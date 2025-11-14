from fpdf import FPDF
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


def generate_pdf_report(doctor_name, payments, total_paid, total_expected, debt, services_summary):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 14)
    pdf.cell(200, 10, txt="Doktor bo'yicha hisobot", ln=True, align="C")

    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt=f"Doktor: {doctor_name}", ln=True)
    pdf.cell(200, 10, txt=f"Sana: {datetime.now().strftime('%Y-%m-%d %H:%M')}", ln=True)
    pdf.ln(5)

    uzbek_tz = pytz.timezone("Asia/Tashkent")

    # --- Xizmatlar bo‘limi ---
    pdf.set_font("Arial", "B", 12)
    pdf.cell(200, 8, txt="Xizmatlar:", ln=True)
    pdf.set_font("Arial", size=11)
    pdf.cell(60, 8, "Xizmat nomi", border=1)
    pdf.cell(20, 8, "Soni", border=1)
    pdf.cell(40, 8, "Jami (so'm)", border=1)
    pdf.cell(60, 8, "Sana va vaqt", border=1, ln=True)

    for name, qty, total, created_at in services_summary:
        local_time = (
            created_at.astimezone(uzbek_tz).strftime("%Y-%m-%d %H:%M")
            if created_at else "-"
        )
        pdf.cell(60, 8, str(name), border=1)
        pdf.cell(20, 8, str(qty), border=1)
        pdf.cell(40, 8, f"{total:,.0f}", border=1)
        pdf.cell(60, 8, local_time, border=1, ln=True)

    pdf.ln(10)

    # --- To‘lovlar bo‘limi ---
    pdf.set_font("Arial", "B", 12)
    pdf.cell(200, 8, txt="To'lovlar:", ln=True)
    pdf.set_font("Arial", size=11)
    pdf.cell(40, 8, "Miqdori (so'm)", border=1)
    pdf.cell(60, 8, "Sana va vaqt", border=1, ln=True)

    for amount, created_at in payments:
        local_time = (
            created_at.astimezone(uzbek_tz).strftime("%Y-%m-%d %H:%M")
            if created_at else "-"
        )
        pdf.cell(40, 8, f"{float(amount):,.0f}", border=1)
        pdf.cell(60, 8, local_time, border=1, ln=True)

    pdf.ln(10)

    # --- Yakun bo‘limi ---
    pdf.set_font("Arial", "B", 12)
    pdf.cell(200, 8, txt="Yakun:", ln=True)
    pdf.set_font("Arial", size=11)
    pdf.cell(200, 8, txt=f"Umumiy xizmatlar: {total_expected:,.0f} so'm", ln=True)
    pdf.cell(200, 8, txt=f"To'langan: {total_paid:,.0f} so'm", ln=True)
    pdf.cell(200, 8, txt=f"Qarz: {debt:,.0f} so'm", ln=True)
    pdf.cell(200, 8, txt=f"Umumiy xizmatlar soni: {len(services_summary)} ta", ln=True)

    filename = f"doctor_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    pdf.output(filename)

    return filename