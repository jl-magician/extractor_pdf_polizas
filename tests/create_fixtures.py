"""Create minimal test fixture PDFs for ingestion tests.

Run once to generate tests/fixtures/digital_sample.pdf and tests/fixtures/scanned_sample.pdf.
These PDFs are committed to the repository as test assets.
"""
import io
from pathlib import Path

import fitz  # PyMuPDF

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def create_digital_pdf() -> None:
    """Create a 1-page PDF with selectable text and no images."""
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)  # A4
    page.insert_text(
        (72, 200),
        "Poliza de Seguro - Ejemplo digital\n\n"
        "Numero de poliza: 12345678\n"
        "Aseguradora: Seguros Mexico SA de CV\n"
        "Vigencia: 01/01/2026 - 31/12/2026\n"
        "Prima total: $5,000.00 MXN",
        fontsize=12,
        color=(0, 0, 0),
    )
    output_path = FIXTURES_DIR / "digital_sample.pdf"
    doc.save(str(output_path))
    doc.close()
    print(f"Created: {output_path}")


def create_scanned_pdf() -> None:
    """Create a 1-page PDF containing a full-page raster image (>90% coverage).

    The image is a simple white rectangle rendered as a PNG, then embedded
    into the PDF. Coverage will be ~100% so it classifies as 'scanned'.
    """
    from PIL import Image, ImageDraw

    # Create a full-page image (A4 at 72 dpi = 595x842)
    img_width, img_height = 595, 842
    img = Image.new("RGB", (img_width, img_height), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.rectangle([10, 10, img_width - 10, img_height - 10], outline=(0, 0, 0), width=3)
    draw.text((50, 100), "SCANNED PAGE - Image content", fill=(0, 0, 0))
    draw.text((50, 130), "This page is a raster image, not selectable text.", fill=(50, 50, 50))

    # Save image to bytes
    img_bytes = io.BytesIO()
    img.save(img_bytes, format="PNG")
    img_bytes.seek(0)

    # Create PDF and insert the image as a full-page image
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)

    # Insert image rect covering 95% of the page
    margin = 10
    img_rect = fitz.Rect(margin, margin, 595 - margin, 842 - margin)
    page.insert_image(img_rect, stream=img_bytes.read())

    output_path = FIXTURES_DIR / "scanned_sample.pdf"
    doc.save(str(output_path))
    doc.close()
    print(f"Created: {output_path}")


if __name__ == "__main__":
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    create_digital_pdf()
    create_scanned_pdf()
    print("Fixture PDFs created successfully.")
