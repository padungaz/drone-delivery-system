import os
import io
import json
import qrcode
from PIL import Image as PILImage

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
    Image,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm


def generate_json_qr_pdf(output_pdf_path: str):
    # 10 kiện hàng chuẩn hóa dạng JSON Object đóng gói
    json_packages = [
        {
            "productId": "MED_001",
            "senderName": "Benh Vien Da Khoa",
            "address": "Tram Y Te Phuong 1",
            "desc": "Thuoc & Vat tu y te cap cuu",
        },
        {
            "productId": "FOOD_002",
            "senderName": "Bep An Trung Tam",
            "address": "Bai Dap Drone Dock N1",
            "desc": "Suat an nong tieu chuan",
        },
        {
            "productId": "PARCEL_003",
            "senderName": "Fast Logistics",
            "address": "Khu Do Thi Vinhome Grand Park",
            "desc": "Kien hang thuong mai dien tu",
        },
        {
            "productId": "DOC_004",
            "senderName": "Van Phong Cong Chung",
            "address": "Toa Nha Landmark 81",
            "desc": "Tai lieu mat & Hop dong goc",
        },
        {
            "productId": "ELEC_005",
            "senderName": "Linh Kien Dien Tu",
            "address": "Khu Cong Nghe Cao Q9",
            "desc": "Bo mach vi dieu khien STM32",
        },
        {
            "productId": "SAMPLE_006",
            "senderName": "Phong Lab Xet Nghiem",
            "address": "Trung Tam Y Te Du Phong",
            "desc": "Mau benh pham bao quan lanh",
        },
        {
            "productId": "BLOOD_007",
            "senderName": "Ngan Hang Mau TW",
            "address": "Benh Vien Cho Ray",
            "desc": "Che pham mau khan cap",
        },
        {
            "productId": "PARTS_008",
            "senderName": "Kho Phu Tung UAV",
            "address": "Tram Bao Tri Dock N1",
            "desc": "Canh quat & Pin Drone Lipo 6S",
        },
        {
            "productId": "COLD_009",
            "senderName": "Kho Lanh Quoc Gia",
            "address": "Diem Tiem Chung Co So 02",
            "desc": "Hop Vacxin tieu chuan 2-8 do C",
        },
        {
            "productId": "URGENT_010",
            "senderName": "Doi Cuu Ho Cuu Nan",
            "address": "Diem Cuu Tro Vung Cach Ly",
            "desc": "Phao cuu sinh & Bo dam lien lac",
        },
    ]

    # Setup trang A4 (210 x 297 mm) lề 10mm
    doc = SimpleDocTemplate(
        output_pdf_path,
        pagesize=A4,
        leftMargin=10 * mm,
        rightMargin=10 * mm,
        topMargin=8 * mm,
        bottomMargin=8 * mm,
    )

    styles = getSampleStyleSheet()

    header_style = ParagraphStyle(
        name="HeaderStyle",
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=16,
        alignment=1,  # Center
        textColor=colors.HexColor("#0f172a"),
    )

    sub_header_style = ParagraphStyle(
        name="SubHeaderStyle",
        fontName="Helvetica",
        fontSize=8,
        leading=11,
        alignment=1,
        textColor=colors.HexColor("#475569"),
    )

    title_id_style = ParagraphStyle(
        name="TitleID",
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=12,
        textColor=colors.HexColor("#1e40af"),
    )

    field_style = ParagraphStyle(
        name="FieldStyle",
        fontName="Helvetica",
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor("#1e293b"),
    )

    json_raw_style = ParagraphStyle(
        name="JsonRawStyle",
        fontName="Courier",
        fontSize=5.5,
        leading=7.5,
        textColor=colors.HexColor("#64748b"),
    )

    story = []

    # Tiêu đề trang
    story.append(Paragraph("DRONE DELIVERY & SMART WAREHOUSE - JSON QR LABELS", header_style))
    story.append(Paragraph("10 Nhan hang dong goi du lieu JSON Object (productId, senderName, address) - Kho A4", sub_header_style))
    story.append(Spacer(1, 4 * mm))

    # Grid 2 cột x 5 hàng = 10 nhãn kích thước lớn
    cols = 2
    table_data = []
    current_row = []

    # Tạo thư mục PNG riêng
    png_dir = os.path.join(os.path.dirname(output_pdf_path), "qr_codes", "json_labels")
    os.makedirs(png_dir, exist_ok=True)

    for item in json_packages:
        # Chuỗi JSON đóng gói nhỏ gọn 1 dòng
        json_payload = json.dumps({
            "productId": item["productId"],
            "senderName": item["senderName"],
            "address": item["address"]
        }, ensure_ascii=False)

        # Tạo mã QR độ nét cao
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=1,
        )
        qr.add_data(json_payload)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        # Lưu ảnh PNG riêng
        img.save(os.path.join(png_dir, f"{item['productId']}.png"))

        # Lưu ảnh buffer cho ReportLab
        img_buffer = io.BytesIO()
        img.save(img_buffer, format="PNG")
        img_buffer.seek(0)

        # Kích thước ảnh QR trong nhãn: 32mm x 32mm
        rl_img = Image(img_buffer, width=32 * mm, height=32 * mm)

        # Cột thông tin bên phải của mỗi nhãn
        info_elements = [
            Paragraph(f"<b>{item['productId']}</b>", title_id_style),
            Spacer(1, 1 * mm),
            Paragraph(f"<b>Nguoi gui:</b> {item['senderName']}", field_style),
            Paragraph(f"<b>Dia chi:</b> {item['address']}", field_style),
            Paragraph(f"<b>Loai hang:</b> {item['desc']}", field_style),
            Spacer(1, 1 * mm),
            Paragraph(f"<code>JSON: {json_payload}</code>", json_raw_style),
        ]

        # Ghép QR + Thông tin vào 1 ô nhãn (Sub-table)
        cell_inner_table = Table(
            [[rl_img, info_elements]],
            colWidths=[35 * mm, 55 * mm],
        )
        cell_inner_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (0, 0), (0, 0), "CENTER"),
            ("LEFTPADDING", (0, 0), (-1, -1), 1 * mm),
            ("RIGHTPADDING", (0, 0), (-1, -1), 1 * mm),
            ("TOPPADDING", (0, 0), (-1, -1), 1 * mm),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1 * mm),
        ]))

        current_row.append(cell_inner_table)

        if len(current_row) == cols:
            table_data.append(current_row)
            current_row = []

    if current_row:
        while len(current_row) < cols:
            current_row.append([])
        table_data.append(current_row)

    col_width = (210 - 20) / 2 * mm  # ~95mm mỗi cột
    row_height = 52 * mm             # 5 hàng x 52mm = 260mm

    outer_table = Table(table_data, colWidths=[col_width] * cols, rowHeights=[row_height] * 5)
    outer_table.setStyle(
        TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("INNERGRID", (0, 0), (-1, -1), 0.75, colors.HexColor("#94a3b8")),
            ("BOX", (0, 0), (-1, -1), 1.5, colors.HexColor("#475569")),
            ("TOPPADDING", (0, 0), (-1, -1), 1.5 * mm),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5 * mm),
            ("LEFTPADDING", (0, 0), (-1, -1), 1.5 * mm),
            ("RIGHTPADDING", (0, 0), (-1, -1), 1.5 * mm),
        ])
    )

    story.append(outer_table)
    doc.build(story)
    print(f"JSON QR PDF created successfully at: {output_pdf_path}")
    print(f"Exported 10 JSON QR PNG images to: {png_dir}")


if __name__ == "__main__":
    out_path = os.path.abspath("qr_codes_json_10_labels.pdf")
    generate_json_qr_pdf(out_path)
