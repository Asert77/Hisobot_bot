import os
from xhtml2pdf import pisa
from datetime import datetime

from fpdf import FPDF
from datetime import datetime

from fpdf import FPDF
from datetime import datetime

def generate_pdf_report(doctor_name, doctor_id, payments, total_expected, total_paid, services_summary):
    """
    Doktor uchun to‘liq PDF hisobot yaratadi.
    :param doctor_name: doktorning to‘liq ismi
    :param doctor_id: doktor ID
    :param payments: [(amount, created_at)] yoki [(amount, created_at, service_name)]
    :param total_expected: xizmatlardan kutilgan jami summa
    :param total_paid: jami to‘langan summa
    :param services_summary: [(service_name, quantity, price, total)]
    """
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # === HEADER ===
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, f"Hisobot — {doctor_name}", ln=True, align="C")
    pdf.ln(5)
    pdf.set_font("Arial", "", 12)
    pdf.cell(0, 8, f"🆔 Doktor ID: {doctor_id}", ln=True)
    pdf.cell(0, 8, f"📅 Sana: {datetime.now().strftime('%d.%m.%Y %H:%M')}", ln=True)
    pdf.ln(10)

    # === XIZMATLAR RO‘YXATI ===
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 8, "🧾 Xizmatlar:", ln=True)
    pdf.set_font("Arial", "", 12)

    if services_summary:
        pdf.cell(70, 8, "Xizmat nomi", border=1)
        pdf.cell(25, 8, "Soni", border=1)
        pdf.cell(40, 8, "Narxi (so‘m)", border=1)
        pdf.cell(50, 8, "Jami (so‘m)", border=1, ln=True)

        for name, quantity, price, total in services_summary:
            pdf.cell(70, 8, str(name), border=1)
            pdf.cell(25, 8, str(quantity), border=1)
            pdf.cell(40, 8, f"{float(price):,.0f}", border=1)
            pdf.cell(50, 8, f"{float(total):,.0f}", border=1, ln=True)
    else:
        pdf.cell(0, 8, "🚫 Xizmatlar topilmadi.", ln=True)

    pdf.ln(8)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 8, f"💰 Umumiy xizmat summasi: {total_expected:,.0f} so‘m", ln=True)
    pdf.ln(5)

    # === TO‘LOVLAR RO‘YXATI ===
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 8, "💳 To‘lovlar:", ln=True)
    pdf.set_font("Arial", "", 12)

    total_paid_calc = 0
    if payments:
        pdf.cell(50, 8, "Sana", border=1)
        pdf.cell(100, 8, "Xizmat (agar mavjud bo‘lsa)", border=1)
        pdf.cell(40, 8, "Miqdor (so‘m)", border=1, ln=True)

        for row in payments:
            # Tuple uzunligiga qarab farqlaymiz
            if len(row) == 3:
                amount, created_at, service_name = row
            elif len(row) == 2:
                amount, created_at = row
                service_name = "-"
            else:
                continue

            total_paid_calc += float(amount)
            date_str = created_at.strftime("%d.%m.%Y") if isinstance(created_at, datetime) else str(created_at)

            pdf.cell(50, 8, date_str, border=1)
            pdf.cell(100, 8, service_name, border=1)
            pdf.cell(40, 8, f"{float(amount):,.0f}", border=1, ln=True)
    else:
        pdf.cell(0, 8, "🚫 To‘lovlar topilmadi.", ln=True)

    pdf.ln(10)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 8, f"✅ To‘langan summa: {total_paid:,.0f} so‘m", ln=True)

    # === QARZDORLIK ===
    debt = max(total_expected - total_paid, 0)
    pdf.cell(0, 8, f"❌ Qarzdorlik: {debt:,.0f} so‘m", ln=True)

    # === PDF YARATISH ===
    safe_name = doctor_name.replace(" ", "_")
    filename = f"report_{safe_name}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
    pdf.output(filename)

    return filename


