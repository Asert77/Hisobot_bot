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


from fpdf import FPDF
from datetime import datetime
import pytz

def generate_pdf_report(doctor_name, payments, total_paid, total_expected, debt, services_summary):
    # 🕒 Toshkent vaqti
    uzbek_tz = pytz.timezone("Asia/Tashkent")
    now_local = datetime.now(uzbek_tz).strftime("%Y-%m-%d %H:%M")

    # 🔒 Himoya: noto‘g‘ri tiplarni to‘g‘rilaymiz
    if not isinstance(payments, list):
        payments = []
    if not isinstance(services_summary, list):
        services_summary = []

    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_font('DejaVu', '', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', uni=True)
    pdf.set_font('DejaVu', '', 12)

    # Sarlavha
    pdf.cell(0, 10, f"Hisobot: {doctor_name}", ln=True, align="C")
    pdf.set_font('DejaVu', '', 10)
    pdf.cell(0, 8, f"Yaratilgan sana: {now_local}", ln=True, align="R")
    pdf.ln(5)

    # Umumiy ma'lumot
    pdf.set_font('DejaVu', '', 11)
    pdf.cell(0, 8, f"To‘langan summa: {total_paid:,.0f} so‘m", ln=True)
    pdf.cell(0, 8, f"Umumiy xizmatlar: {total_expected:,.0f} so‘m", ln=True)
    pdf.cell(0, 8, f"Qarzdorlik: {debt:,.0f} so‘m", ln=True)
    pdf.ln(5)

    # 🔹 To‘lovlar ro‘yxati
    pdf.set_font('DejaVu', 'B', 11)
    pdf.cell(0, 10, "To‘lovlar:", ln=True)
    pdf.set_font('DejaVu', '', 10)

    if payments:
        pdf.cell(60, 8, "Sana va vaqt", border=1, align="C")
        pdf.cell(60, 8, "Miqdor (so‘m)", border=1, align="C")
        pdf.ln()
        for payment in payments:
            try:
                amount, created_at = payment[:2]
                if hasattr(created_at, "astimezone"):
                    created_at = created_at.astimezone(uzbek_tz)
                date_str = created_at.strftime("%Y-%m-%d %H:%M") if created_at else "-"
                pdf.cell(60, 8, date_str, border=1)
                pdf.cell(60, 8, f"{float(amount):,.0f}", border=1)
                pdf.ln()
            except Exception:
                continue
    else:
        pdf.cell(0, 8, "To‘lovlar mavjud emas.", ln=True)

    pdf.ln(10)

    # 🔹 Xizmatlar ro‘yxati
    pdf.set_font('DejaVu', 'B', 11)
    pdf.cell(0, 10, "Qo‘shilgan xizmatlar:", ln=True)
    pdf.set_font('DejaVu', '', 10)

    if services_summary:
        pdf.cell(50, 8, "Xizmat nomi", border=1, align="C")
        pdf.cell(30, 8, "Soni", border=1, align="C")
        pdf.cell(40, 8, "Narx (so‘m)", border=1, align="C")
        pdf.cell(50, 8, "Sana va vaqt", border=1, align="C")
        pdf.ln()
        for row in services_summary:
            try:
                name = str(row.get("name", "-"))
                quantity = int(row.get("quantity", 0))
                price = float(row.get("price", 0))
                created_at = row.get("created_at")
                if hasattr(created_at, "astimezone"):
                    created_at = created_at.astimezone(uzbek_tz)
                date_str = created_at.strftime("%Y-%m-%d %H:%M") if created_at else "-"
                pdf.cell(50, 8, name, border=1)
                pdf.cell(30, 8, str(quantity), border=1, align="C")
                pdf.cell(40, 8, f"{price:,.0f}", border=1, align="R")
                pdf.cell(50, 8, date_str, border=1)
                pdf.ln()
            except Exception:
                continue
    else:
        pdf.cell(0, 8, "Xizmatlar mavjud emas.", ln=True)

    pdf.ln(10)

    total_services = len(services_summary)
    pdf.set_font('DejaVu', 'B', 11)
    pdf.cell(0, 10, f"Umumiy xizmatlar soni: {total_services} ta", ln=True)

    filename = f"/mnt/data/hisobot_{doctor_name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    pdf.output(filename)
    return filename