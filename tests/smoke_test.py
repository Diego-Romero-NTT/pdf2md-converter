"""End-to-end check against a running app: convert a scanned one-page PDF with OCR.

Usage: python tests/smoke_test.py [app URL]   (default http://127.0.0.1:7860/)
Needs: pip install gradio_client pillow
"""
import sys
import tempfile
from pathlib import Path

from gradio_client import Client, handle_file
from PIL import Image, ImageDraw, ImageFont

url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:7860/"

# A PDF holding only a picture of text, so the answer can only come from OCR.
image = Image.new("RGB", (1240, 400), "white")
ImageDraw.Draw(image).text((60, 140), "Hello Markdown", fill="black", font=ImageFont.load_default(size=96))
pdf_path = Path(tempfile.mkdtemp()) / "scanned.pdf"
image.save(pdf_path)

markdown_file, preview, raw = Client(url, verbose=False).predict(
    handle_file(str(pdf_path)), "English", True, api_name="/convert"
)
text = Path(markdown_file).read_text(encoding="utf-8")
print(text)
if "hello markdown" not in text.lower():
    sys.exit("FAIL: OCR text not found in the Markdown output")
print("OK")
