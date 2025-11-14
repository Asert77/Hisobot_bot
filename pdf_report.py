from fpdf import FPDF
from datetime import datetime

def generate_report_pdf(doctor_name, services, payments, output_path):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, f"Hisobot: Dr. {doctor_name}", ln=True)

    pdf.set_font("Arial", '', 12)
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    pdf.cell(0, 10, f"Yaratilgan: {created_at}", ln=True)
    pdf.ln(5)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(8)

    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 8, "■ To‘lovlar:", ln=True)
    pdf.set_font("Arial", '', 11)

    total_paid = 0
    if payments:
        for amount, date, _ in payments:
            date_str = date.strftime("%Y-%m-%d %H:%M") if date else "—"
            pdf.cell(0, 8, f"{amount:.0f} so‘m ({date_str})", ln=True)
            total_paid += float(amount)
    else:
        pdf.cell(0, 8, "To‘lovlar yo‘q.", ln=True)

    pdf.ln(5)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(8)

    # 🧾 Xizmatlar bo‘limi
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 8, "■ Xizmatlar:", ln=True)
    pdf.set_font("Arial", '', 11)

    total_expected = 0
    if services:
        for name, price, quantity, created_at in services:
            date_str = created_at.strftime("%Y-%m-%d %H:%M") if created_at else "—"
            total = float(price) * int(quantity)
            total_expected += total
            pdf.cell(
                0, 8,
                f"{name} — {quantity} ta × {float(price):,.0f} so‘m = {total:,.0f} so‘m ({date_str})",
                ln=True
            )
    else:
        pdf.cell(0, 8, "Xizmatlar yo‘q.", ln=True)

    pdf.ln(5)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(8)

    # 📊 Hisobot yakuni
    debt = max(total_expected - total_paid, 0)

    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 8, f"To‘langan jami: {total_paid:,.0f} so‘m", ln=True)
    pdf.cell(0, 8, f"To‘lanishi kerak: {total_expected:,.0f} so‘m", ln=True)
    pdf.cell(0, 8, f"Qarzdorlik: {debt:,.0f} so‘m", ln=True)

    pdf.output(output_path)


