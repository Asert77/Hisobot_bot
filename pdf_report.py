import os
from xhtml2pdf import pisa
from datetime import datetime

def generate_pdf_report(doctor_name, payments, total_paid, total_expected, debt, services_summary):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # To‘lovlar qismi
    report_lines = []
    for amount, date, service_name in payments:
        report_lines.append(f"{amount:.0f} so‘m ({service_name}) — {date}")
    rows_html = "<br>".join(report_lines)

    # Xizmatlar qismi (vaqti bilan)
    service_lines = []
    for name, price, quantity, created_at in services_summary:
        date_str = created_at.strftime("%Y-%m-%d %H:%M")
        service_lines.append(f"{name} — {quantity} ta × {price:.0f} so‘m ({date_str})")
    services_html = "<br>".join(service_lines)

    html = f"""
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: DejaVu Sans, sans-serif; }}
            h1 {{ color: #333; }}
            p {{ margin: 6px 0; }}
        </style>
    </head>
    <body>
        <h1>Hisobot: Dr. {doctor_name}</h1>
        <p>Yaratilgan: {now}</p>
        <hr/>
        <p><strong>▪ To‘lovlar:</strong></p>
        {rows_html}
        <hr/>
        <p><strong>▪ Xizmatlar:</strong></p>
        {services_html}
        <hr/>
        <p><strong>To‘langan jami:</strong> {total_paid:.0f} so‘m</p>
        <p><strong>To‘lanishi kerak:</strong> {total_expected:.0f} so‘m</p>
        <p><strong>Qarzdorlik:</strong> {debt:.0f} so‘m</p>
    </body>
    </html>
    """

    filename = f"hisobot_{doctor_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    os.makedirs("reports", exist_ok=True)
    filepath = os.path.join("reports", filename)

    with open(filepath, "wb") as f:
        pisa.CreatePDF(html, dest=f)

    return filepath


