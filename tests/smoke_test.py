"""End-to-end check against a running app: convert scanned one-page PDFs with OCR.

Usage: python tests/smoke_test.py [app URL] [Japanese font file]
       (default URL http://127.0.0.1:7860/; the Japanese case is skipped without a font)
Needs: pip install gradio_client pillow
"""
import sys
import tempfile
from pathlib import Path

from gradio_client import Client, handle_file
from PIL import Image, ImageDraw, ImageFont

url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:7860/"
japanese_font = sys.argv[2] if len(sys.argv) > 2 else None
client = Client(url, verbose=False)


def scanned_pdf(text, font):
    """A PDF holding only a picture of text, so the answer can only come from OCR."""
    image = Image.new("RGB", (1240, 400), "white")
    ImageDraw.Draw(image).text((60, 140), text, fill="black", font=font)
    path = Path(tempfile.mkdtemp()) / "scanned.pdf"
    image.save(path)
    return path


def convert(path, language):
    markdown_file, _, _ = client.predict(handle_file(str(path)), language, True, api_name="/convert")
    text = Path(markdown_file).read_text(encoding="utf-8")
    print(f"--- {language}\n{text}")
    return text


failures = []
text = convert(scanned_pdf("Hello Markdown", ImageFont.load_default(size=96)), "English")
if "hello markdown" not in text.lower():
    failures.append("English OCR text not found")

if japanese_font:
    expected = "文書を変換します"
    text = convert(scanned_pdf(expected, ImageFont.truetype(japanese_font, 96)), "Japanese")
    if expected not in text:
        failures.append(f"Japanese OCR text {expected!r} not found as one unspaced line")

if failures:
    sys.exit("FAIL: " + "; ".join(failures))
print("OK")
