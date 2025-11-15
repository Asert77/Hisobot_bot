from xhtml2pdf import pisa
from io import BytesIO
from datetime import datetime
import pytz
import os


def generate_pdf_report(doctor_name, payments, total_paid, total_expected, debt, services_summary):
    """
    Doktor hisobotini HTML asosida PDF ko‘rinishida yaratadi.
    """

    # 🇺🇿 Tashkent vaqti
    uzbek_tz = pytz.timezone("Asia/Tashkent")
    now = datetime.now(uzbek_tz).strftime("%Y-%m-%d %H:%M")

    # 🔢 Umumiy xizmatlar soni
    total_services_count = sum(qty for _, qty, _ in services_summary) if services_summary else 0

    # 🧾 Xizmatlar jadvali (HTML)
    services_html = ""
    if services_summary:
        for name, qty, total in services_summary:
            services_html += f"""
            <tr>
                <td>{name}</td>
                <td>{qty}</td>
                <td>{total:,.0f}</td>
            </tr>
            """
    else:
        services_html = "<tr><td colspan='3' style='text-align:center;'>Hech qanday xizmat yo‘q</td></tr>"

    # 💰 To‘lovlar jadvali (HTML)
    payments_html = ""
    if payments:
        for amount, created_at in payments:
            if hasattr(created_at, "astimezone"):
                local_time = created_at.astimezone(uzbek_tz).strftime("%Y-%m-%d %H:%M")
            else:
                local_time = str(created_at)
            payments_html += f"""
            <tr>
                <td>{local_time}</td>
                <td>{amount:,.0f}</td>
            </tr>
            """
    else:
        payments_html = "<tr><td colspan='2' style='text-align:center;'>Hech qanday to‘lov yo‘q</td></tr>"

    # 🧩 HTML Shablon
    html = f"""
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{
                font-family: DejaVu Sans, sans-serif;
                font-size: 12pt;
                color: #000;
            }}
            h1 {{
                text-align: center;
                font-size: 18pt;
                margin-bottom: 20px;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin-top: 10px;
                margin-bottom: 20px;
            }}
            th, td {{
                border: 1px solid #000;
                padding: 6px;
                text-align: left;
            }}
            th {{
                background-color: #f0f0f0;
            }}
            .section-title {{
                font-size: 14pt;
                margin-top: 20px;
                font-weight: bold;
            }}
        </style>
    </head>
    <body>
        <h1>Doktor hisobot</h1>
        <p><b>Doktor:</b> {doctor_name}</p>
        <p><b>Hisobot yaratilgan sana:</b> {now}</p>
        <p><b>To‘langan summa:</b> {total_paid:,.0f} so‘m</p>
        <p><b>Umumiy xizmatlar:</b> {total_expected:,.0f} so‘m</p>
        <p><b>Qarzdorlik:</b> {debt:,.0f} so‘m</p>
        <p><b>Umumiy xizmatlar soni:</b> {total_services_count} ta</p>

        <div class="section-title">Xizmatlar ro‘yxati</div>
        <table>
            <tr><th>Nomi</th><th>Soni</th><th>Jami (so‘m)</th></tr>
            {services_html}
        </table>

        <div class="section-title">To‘lovlar tarixi</div>
        <table>
            <tr><th>Sana</th><th>Summa (so‘m)</th></tr>
            {payments_html}
        </table>
    </body>
    </html>
    """

    # 📁 Saqlash joyi
    filename = f"doctor_report_{doctor_name.replace(' ', '_')}.pdf"
    output_path = os.path.join("/app", filename)

    # 🧾 PDF yaratish
    with open(output_path, "wb") as f:
        pisa.CreatePDF(BytesIO(html.encode("utf-8")), dest=f)

    return output_path