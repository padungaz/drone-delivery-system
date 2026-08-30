#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Smart Warehouse & Drone Delivery System — QR Code PDF Label Generator.

Generates professional industrial QR code label PDF files for warehouse inventory sorting.
Supports:
  1. Interactive CLI prompts
  2. Direct CLI arguments (--id SP001 --sender "Nguyen Van A" --address "Da Nang")
  3. Batch mode (--batch)
  4. Programmatic import from FastAPI backend (`from generate_qr_pdf import generate_qr_pdf`)
"""

import argparse
from datetime import datetime
import json
import os

try:
    import qrcode
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Image as RLImage, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    PDF_PACKAGES_AVAILABLE = True
except ImportError:
    PDF_PACKAGES_AVAILABLE = False


def create_qr_image(qr_data_str: str, temp_filename: str = "temp_qr.png") -> str:
    """Tạo file hình ảnh mã QR độ phân giải cao."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=2,
    )
    qr.add_data(qr_data_str)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    img.save(temp_filename)
    return temp_filename


def generate_qr_pdf(
    product_id: str,
    sender_name: str = "Nguyen Van A",
    address: str = "Da Nang",
    output_pdf_path: str = None,
    raw_payload: str = None,
) -> str:
    """Tạo file PDF trang in nhãn tem QR Code đầy đủ thông tin."""
    if not PDF_PACKAGES_AVAILABLE:
        raise RuntimeError("Yêu cầu cài đặt thư viện 'qrcode' và 'reportlab': pip install qrcode[pil] reportlab")

    if not output_pdf_path:
        clean_id = product_id.replace("/", "_").replace("\\", "_")
        output_pdf_path = f"QR_{clean_id}.pdf"

    # Chuẩn bị dữ liệu QR (JSON format hoặc plain product_id)
    if not raw_payload:
        qr_json = {
            "productId": product_id,
            "senderName": sender_name,
            "address": address,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        qr_content_str = json.dumps(qr_json, ensure_ascii=False)
    else:
        qr_content_str = raw_payload

    # Tạo ảnh QR tạm thời
    clean_id = product_id.replace("/", "_").replace("\\", "_")
    temp_qr_path = f"temp_qr_{clean_id}.png"
    create_qr_image(qr_content_str, temp_qr_path)

    # Khởi tạo Document PDF A4
    doc = SimpleDocTemplate(
        output_pdf_path,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    story = []
    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        "TitleStyle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#0f172a"),
        alignment=1,  # Center
        spaceAfter=15,
    )

    subtitle_style = ParagraphStyle(
        "SubTitleStyle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#475569"),
        alignment=1,  # Center
        spaceAfter=25,
    )

    label_style = ParagraphStyle(
        "LabelStyle",
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=15,
        textColor=colors.HexColor("#1e293b"),
    )

    value_style = ParagraphStyle(
        "ValueStyle",
        fontName="Helvetica",
        fontSize=11,
        leading=15,
        textColor=colors.HexColor("#0f172a"),
    )

    # 1. Header
    story.append(Paragraph("HE THONG KHO THONG MINH & DRONE DELIVERY", title_style))
    story.append(Paragraph("THE MA QR SAN PHAM NHAP/XUAT KHO", subtitle_style))
    story.append(Spacer(1, 10))

    # 2. Khung Tem Nhãn Sản phẩm (Table Layout)
    qr_img_element = RLImage(temp_qr_path, width=6 * cm, height=6 * cm)

    now_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    info_data = [
        [Paragraph("MA SAN PHAM (ID):", label_style), Paragraph(f"<b>{product_id}</b>", label_style)],
        [Paragraph("NGUOI GUI:", label_style), Paragraph(sender_name, value_style)],
        [Paragraph("DIA CHI GIAO:", label_style), Paragraph(address, value_style)],
        [Paragraph("NGAY TAO MA:", label_style), Paragraph(now_str, value_style)],
        [Paragraph("TRANG THAI KHO:", label_style), Paragraph("SAN SANG NHAP KHO (A1..C3)", value_style)],
    ]

    info_table = Table(info_data, colWidths=[4 * cm, 7.5 * cm])
    info_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("LINEBELOW", (0, 0), (-1, -2), 0.5, colors.HexColor("#e2e8f0")),
        ])
    )

    # Ghép Bảng Thông tin + Ảnh QR vào một Card chính
    main_card_data = [
        [Paragraph(f"TEM MA QR CHINTH THUC — [{product_id}]", label_style)],
        [qr_img_element],
        [info_table],
        [Paragraph(f"Noi dung ma QR: <i>{qr_content_str}</i>", ParagraphStyle("Mini", fontSize=8, leading=10, textColor=colors.gray, alignment=1))],
    ]

    card_table = Table(main_card_data, colWidths=[13 * cm])
    card_table.setStyle(
        TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#ffffff")),
            ("BOX", (0, 0), (-1, -1), 2, colors.HexColor("#2563eb")),  # Viền màu xanh nổi bật
            ("TOPPADDING", (0, 0), (-1, -1), 12),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
            ("LEFTPADDING", (0, 0), (-1, -1), 12),
            ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ])
    )

    story.append(card_table)
    story.append(Spacer(1, 20))
    story.append(Paragraph("Huong dan: Dan tem QR nay len hop hang de USB Camera nhan dien tu dong.", subtitle_style))

    # Build PDF
    doc.build(story)

    # Cleanup temp QR image
    if os.path.exists(temp_qr_path):
        try:
            os.remove(temp_qr_path)
        except Exception:
            pass

    return output_pdf_path


def main():
    parser = argparse.ArgumentParser(description="Tao tem QR Code San Pham & In ra PDF")
    parser.add_argument("--id", type=str, help="Ma san pham (VD: SP001, PROD-8899)")
    parser.add_argument("--sender", type=str, default="Nguyen Van A", help="Ten nguoi gui")
    parser.add_argument("--address", type=str, default="Da Nang", help="Dia chi giao hang")
    parser.add_argument("--batch", action="store_true", help="Tao nhanh bo ma QR mau tu SP005 den SP010")
    parser.add_argument("--output", type=str, help="Ten file PDF xuat ra")

    args = parser.parse_args()

    # Che do Batch: Tao bo ma QR mau tu SP005 den SP010
    if args.batch:
        print("\n--- Dang khoi tao bo ma QR tem san pham mau (SP005 .. SP010) ---")
        for i in range(5, 11):
            p_id = f"SP{i:03d}"
            generate_qr_pdf(p_id, sender_name=f"Nguyen Van {chr(64 + i)}", address=f"Tram {i} - Da Nang")
        print("\n==> Da tao xong cac file PDF tem QR thanh cong!")
        return

    # Che do nhan tham so CLI
    if args.id:
        generate_qr_pdf(
            product_id=args.id,
            sender_name=args.sender,
            address=args.address,
            output_pdf_path=args.output,
        )
        return

    # Che do nhap truc tiep tuong tac (Interactive Input)
    print("=" * 60)
    print(" CHUONG TRINH TAO MA QR SAN PHAM & IN RA PDF (SMART WAREHOUSE)")
    print("=" * 60)

    try:
        user_id = input("1. Nhap Ma San Pham / QR (VD: SP001 hoac PROD-101): ").strip()
        if not user_id:
            user_id = "SP001"
            print("   -> Mac dinh chon: SP001")

        user_sender = input("2. Nhap Ten Nguoi Gui (Nhan Enter de chon mac dinh 'Nguyen Van A'): ").strip()
        if not user_sender:
            user_sender = "Nguyen Van A"

        user_address = input("3. Nhap Dia Chi Giao (Nhan Enter de chon mac dinh 'Da Nang'): ").strip()
        if not user_address:
            user_address = "Da Nang"

        pdf_file = generate_qr_pdf(
            product_id=user_id,
            sender_name=user_sender,
            address=user_address,
        )

        print("\n" + "=" * 60)
        print(f" Hoan tat! File PDF da duoc luu tai: {os.path.abspath(pdf_file)}")
        print(" Meo: Mo file PDF nay va in ra giay hoac chieu len man hinh de USB Camera quet thu!")
        print("=" * 60)

    except KeyboardInterrupt:
        print("\nĐã hủy lệnh tạo QR.")


if __name__ == "__main__":
    main()
