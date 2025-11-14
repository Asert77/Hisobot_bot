from fpdf import FPDF
import os
from datetime import datetime


class PDF(FPDF):
    def header(self):
        self.set_font("Arial", "B", 14)
        self.cell(0, 10, "Doktor bo‘yicha hisobot", align="C", ln=True)
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
    pdf.cell(0, 10, f"Doktor: {doctor_name} (ID: {doctor_id})", ln=True)
    pdf.cell(0, 10, f"Sana: {datetime.now().strftime('%Y-%m-%d %H:%M')}", ln=True)
    pdf.ln(5)

    # --- Xizmatlar jadvali ---
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "Xizmatlar:", ln=True)
    pdf.set_font("Arial", "", 11)

    pdf.cell(60, 8, "Xizmat nomi", border=1)
    pdf.cell(25, 8, "Soni", border=1)
    pdf.cell(40, 8, "Jami (so‘m)", border=1)
    pdf.cell(50, 8, "Sana va vaqt", border=1, ln=True)

    for name, price, quantity, created_at in services_summary:
        total = price * quantity
        if isinstance(created_at, datetime):
            date_str = created_at.strftime("%Y-%m-%d %H:%M")
        else:
            date_str = str(created_at)

        pdf.cell(60, 8, str(name), border=1)
        pdf.cell(25, 8, str(quantity), border=1)
        pdf.cell(40, 8, f"{total:,.0f}", border=1)
        pdf.cell(50, 8, date_str, border=1, ln=True)

    pdf.ln(10)

    # --- To‘lovlar jadvali ---
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "To‘lovlar:", ln=True)
    pdf.set_font("Arial", "", 11)

    pdf.cell(50, 8, "Miqdori (so‘m)", border=1)
    pdf.cell(70, 8, "Sana va vaqt", border=1, ln=True)

    for amount, date in payments:
        if isinstance(date, datetime):
            date_str = date.strftime("%Y-%m-%d %H:%M")
        else:
            date_str = str(date)

        pdf.cell(50, 8, f"{float(amount):,.0f}", border=1)
        pdf.cell(70, 8, date_str, border=1, ln=True)

    pdf.ln(10)

    # --- Yakuniy hisob ---
    debt = total_expected - total_paid
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "Yakun:", ln=True)
    pdf.set_font("Arial", "", 11)
    pdf.cell(0, 8, f"Umumiy xizmatlar: {total_expected:,.0f} so‘m", ln=True)
    pdf.cell(0, 8, f"To‘langan: {total_paid:,.0f} so‘m", ln=True)
    pdf.cell(0, 8, f"Qarzdorlik: {debt:,.0f} so‘m", ln=True)

    # --- PDF saqlash ---
    filename = f"doctor_report_{doctor_id}.pdf"
    filepath = os.path.join("/app", filename)
    pdf.output(filepath)
    return filepath