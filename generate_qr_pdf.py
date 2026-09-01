import os
import io
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


def generate_qr_pdf(output_pdf_path: str):
    # Danh sách 20 mã QR: Phục vụ cả 9 ô kho (A1..C3) và 11 kiện hàng nhập/xuất tự do
    items = [
        ("PROD_A1", "Kho Slot A1"),
        ("PROD_A2", "Kho Slot A2"),
        ("PROD_A3", "Kho Slot A3"),
        ("PROD_B1", "Kho Slot B1"),
        ("PROD_B2", "Kho Slot B2"),
        ("PROD_B3", "Kho Slot B3"),
        ("PROD_C1", "Kho Slot C1"),
        ("PROD_C2", "Kho Slot C2"),
        ("PROD_C3", "Kho Slot C3"),
        ("SP001", "Kiện hàng 01"),
        ("SP002", "Kiện hàng 02"),
        ("SP003", "Kiện hàng 03"),
        ("SP004", "Kiện hàng 04"),
        ("SP005", "Kiện hàng 05"),
        ("SP006", "Kiện hàng 06"),
        ("SP007", "Kiện hàng 07"),
        ("SP008", "Kiện hàng 08"),
        ("SP009", "Kiện hàng 09"),
        ("SP010", "Kiện hàng 10"),
        ("SP011", "Kiện hàng 11"),
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
        textColor=colors.HexColor("#1e293b"),
    )

    sub_header_style = ParagraphStyle(
        name="SubHeaderStyle",
        fontName="Helvetica",
        fontSize=8,
        leading=10,
        alignment=1,
        textColor=colors.HexColor("#64748b"),
    )

    code_title_style = ParagraphStyle(
        name="CodeTitle",
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=11,
        alignment=1,
        textColor=colors.HexColor("#0f172a"),
    )

    code_sub_style = ParagraphStyle(
        name="CodeSub",
        fontName="Helvetica",
        fontSize=7,
        leading=9,
        alignment=1,
        textColor=colors.HexColor("#475569"),
    )

    story = []

    # Tiêu đề trang
    story.append(Paragraph("DRONE DELIVERY & SMART WAREHOUSE - QR PACKAGE LABELS", header_style))
    story.append(Paragraph("Bang 20 ma QR dan len hop hang test he thong (Kho 3x3 + Don nhap xuat)", sub_header_style))
    story.append(Spacer(1, 4 * mm))

    # Grid 4 cột x 5 hàng = 20 mã QR
    cols = 4
    table_data = []
    current_row = []

    for code_val, label in items:
        # Tạo ảnh QR độ nét cao
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=1,
        )
        qr.add_data(code_val)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        # Lưu ảnh QR vào buffer bộ nhớ
        img_buffer = io.BytesIO()
        img.save(img_buffer, format="PNG")
        img_buffer.seek(0)

        # Tạo ReportLab Image (kích thước chuẩn 30mm x 30mm)
        rl_img = Image(img_buffer, width=30 * mm, height=30 * mm)

        cell_elements = [
            Spacer(1, 1 * mm),
            rl_img,
            Spacer(1, 1 * mm),
            Paragraph(code_val, code_title_style),
            Paragraph(label, code_sub_style),
            Spacer(1, 1 * mm),
        ]

        current_row.append(cell_elements)

        if len(current_row) == cols:
            table_data.append(current_row)
            current_row = []

    if current_row:
        while len(current_row) < cols:
            current_row.append([])
        table_data.append(current_row)

    col_width = (210 - 20) / 4 * mm  # ~47.5mm mỗi ô
    row_height = 51 * mm

    table = Table(table_data, colWidths=[col_width] * cols, rowHeights=[row_height] * 5)
    table.setStyle(
        TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#94a3b8")),
            ("TOPPADDING", (0, 0), (-1, -1), 1 * mm),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1 * mm),
            ("LEFTPADDING", (0, 0), (-1, -1), 1 * mm),
            ("RIGHTPADDING", (0, 0), (-1, -1), 1 * mm),
        ])
    )

    story.append(table)
    doc.build(story)
    print(f"PDF created successfully at: {output_pdf_path}")

    # Đồng thời xuất 20 file ảnh PNG riêng biệt vào thư mục qr_codes/ để tiện mở trên điện thoại/máy tính
    png_dir = os.path.join(os.path.dirname(output_pdf_path), "qr_codes")
    os.makedirs(png_dir, exist_ok=True)
    for code_val, label in items:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=12,
            border=2,
        )
        qr.add_data(code_val)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        img.save(os.path.join(png_dir, f"{code_val}.png"))
    print(f"Exported 20 PNG images to: {png_dir}")


if __name__ == "__main__":
    out_path = os.path.abspath("qr_codes_20_labels.pdf")
    generate_qr_pdf(out_path)
