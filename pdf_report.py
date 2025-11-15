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
import pytz
from datetime import datetime

def generate_pdf_report(doctor_name, payments, total_paid, total_expected, debt, services_summary):
    uzbek_tz = pytz.timezone("Asia/Tashkent")

    # 🛠 Har ehtimolga qarshi noto‘g‘ri qiymatlarni float’ga aylantiramiz
    def normalize_number(value):
        if isinstance(value, list):
            return sum(float(v) for v in value if isinstance(v, (int, float)))
        elif isinstance(value, (int, float)):
            return float(value)
        elif value is None:
            return 0.0
        try:
            return float(str(value).replace(',', ''))
        except Exception:
            return 0.0

    total_paid = normalize_number(total_paid)
    total_expected = normalize_number(total_expected)
    debt = normalize_number(debt)

    # 🧾 PDF sozlamalari
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_font("DejaVu", "", "DejaVuSans.ttf", uni=True)
    pdf.set_font("DejaVu", "", 12)

    # 🧠 Sarlavha
    now_uz = datetime.now(uzbek_tz).strftime("%Y-%m-%d %H:%M")
    pdf.cell(0, 10, f"Doktor: {doctor_name}", ln=True)
    pdf.cell(0, 8, f"Hisobot yaratilgan vaqt: {now_uz}", ln=True)
    pdf.ln(5)

    # 💰 To‘lovlar bo‘limi
    pdf.set_font("DejaVu", "B", 12)
    pdf.cell(0, 8, "To‘lovlar:", ln=True)
    pdf.set_font("DejaVu", "", 11)

    if payments:
        pdf.cell(70, 8, "Sana / Vaqt", border=1)
        pdf.cell(70, 8, "To‘lov summasi (so‘m)", border=1, ln=True)

        for amount, created_at in payments:
            if hasattr(created_at, "astimezone"):
                created_at = created_at.astimezone(uzbek_tz)
            created_str = created_at.strftime("%Y-%m-%d %H:%M") if created_at else "-"
            pdf.cell(70, 8, created_str, border=1)
            pdf.cell(70, 8, f"{float(amount):,.0f}", border=1, ln=True)
    else:
        pdf.cell(0, 8, "To‘lovlar mavjud emas", ln=True)

    pdf.ln(8)

    # 🧾 Xizmatlar bo‘limi
    pdf.set_font("DejaVu", "B", 12)
    pdf.cell(0, 8, "Qo‘shilgan xizmatlar:", ln=True)
    pdf.set_font("DejaVu", "", 11)

    total_services = 0
    total_services_value = 0

    if services_summary:
        pdf.cell(60, 8, "Xizmat nomi", border=1)
        pdf.cell(25, 8, "Soni", border=1)
        pdf.cell(45, 8, "Narxi (so‘m)", border=1)
        pdf.cell(50, 8, "Qo‘shilgan sana / vaqt", border=1, ln=True)

        for s in services_summary:
            name = s.get("name", "-")
            price = normalize_number(s.get("price"))
            qty = int(s.get("quantity", 0))
            created = s.get("created_at")

            if hasattr(created, "astimezone"):
                created = created.astimezone(uzbek_tz)
            created_str = created.strftime("%Y-%m-%d %H:%M") if created else "-"

            pdf.cell(60, 8, name, border=1)
            pdf.cell(25, 8, f"{qty}", border=1)
            pdf.cell(45, 8, f"{price:,.0f}", border=1)
            pdf.cell(50, 8, created_str, border=1, ln=True)

            total_services += qty
            total_services_value += price * qty
    else:
        pdf.cell(0, 8, "Xizmatlar mavjud emas", ln=True)

    pdf.ln(8)

    pdf.set_font("Arial", "", 12)
    pdf.cell(0, 8, "Yakuniy natijalar:", ln=True)
    pdf.cell(0, 8, f"To‘langan summa: {total_paid:,.0f} so‘m", ln=True)
    pdf.cell(0, 8, f"Umumiy xizmatlar qiymati: {total_expected:,.0f} so‘m", ln=True)
    pdf.cell(0, 8, f"Qarzdorlik: {debt:,.0f} so‘m", ln=True)
    pdf.cell(0, 8, f"Umumiy xizmatlar soni: {total_services} ta", ln=True)
    pdf.cell(0, 8, f"Umumiy xizmatlar qiymati (aniq): {total_services_value:,.0f} so‘m", ln=True)

    filename = f"hisobot_{doctor_name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    filepath = f"/app/{filename}"
    pdf.output(filepath)
    return filepath