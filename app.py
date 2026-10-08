import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import gradio as gr

# --- CONFIGURATION (override with environment variables) ---
# Only the first MAX_PAGES pages of a document are converted.
MAX_PAGES = int(os.getenv("MAX_PAGES", "100"))
# A conversion that runs longer than this is aborted.
TIMEOUT_SECONDS = int(os.getenv("TIMEOUT_SECONDS", "600"))
# Folder holding the Tesseract *.traineddata files baked into the image.
# When unset, LiteParse uses its own cache and downloads missing languages.
TESSDATA_PATH = os.getenv("TESSDATA_PATH")
# OCR threads per conversion. Defaults to the CPUs the container may use.
OCR_WORKERS = os.getenv("OCR_WORKERS")
# Path to the LiteParse CLI.
LIT_BIN = os.getenv("LIT_BIN", "lit")
# Outputs older than this are deleted on the next request.
OUTPUT_TTL_SECONDS = 3600
# The preview is cut at this many characters; the download is always complete.
PREVIEW_CHARS = 100_000

OCR_LANGUAGES = {
    "English": "eng",
    "Spanish": "spa",
    "French": "fra",
    "German": "deu",
    "Italian": "ita",
    "Portuguese": "por",
}
SUPPORTED_EXTENSIONS = [".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp", ".gif"]

WORK_ROOT = Path(tempfile.gettempdir()) / "pdf2md"
WORK_ROOT.mkdir(exist_ok=True)


def cpu_limit():
    """CPUs granted to this container. os.cpu_count() reports the host, which oversubscribes OCR threads."""
    try:
        quota, period = Path("/sys/fs/cgroup/cpu.max").read_text().split()
        if quota != "max":
            return max(1, int(quota) // int(period))
    except (OSError, ValueError):
        pass
    return os.cpu_count() or 1


def available_languages():
    """Languages whose OCR data is present, or every language when LiteParse manages its own cache."""
    if not TESSDATA_PATH:
        return list(OCR_LANGUAGES)
    return [name for name, code in OCR_LANGUAGES.items()
            if (Path(TESSDATA_PATH) / f"{code}.traineddata").exists()]


def remove_old_outputs():
    """Each request writes to its own folder; drop folders older than OUTPUT_TTL_SECONDS."""
    cutoff = time.time() - OUTPUT_TTL_SECONDS
    for folder in WORK_ROOT.iterdir():
        if folder.is_dir() and folder.stat().st_mtime < cutoff:
            shutil.rmtree(folder, ignore_errors=True)


def convert(uploaded_path, language, use_ocr):
    if not uploaded_path:
        raise gr.Error("No file uploaded. Please upload a PDF or an image.")

    source = Path(uploaded_path)
    if source.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise gr.Error(f"Unsupported file type '{source.suffix}'. Supported: {', '.join(SUPPORTED_EXTENSIONS)}")

    remove_old_outputs()
    work_dir = Path(tempfile.mkdtemp(dir=WORK_ROOT))
    output_path = work_dir / f"{source.stem}.md"

    command = [
        LIT_BIN, "parse", str(source),
        "--format", "markdown",
        "--max-pages", str(MAX_PAGES),
        "-o", str(output_path),
        "--quiet",
    ]
    if use_ocr:
        command += ["--ocr-language", OCR_LANGUAGES[language],
                    "--num-workers", OCR_WORKERS or str(cpu_limit())]
    else:
        command.append("--no-ocr")
    if TESSDATA_PATH:
        config_path = work_dir / "liteparse.config.json"
        config_path.write_text(json.dumps({"tessdataPath": TESSDATA_PATH}))
        command += ["--config", str(config_path)]

    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        raise gr.Error(f"Conversion took longer than {TIMEOUT_SECONDS} seconds and was stopped.")

    if result.returncode != 0 or not output_path.exists():
        print(f"lit failed ({result.returncode}): {result.stderr}")
        last_line = (result.stderr.strip().splitlines() or ["unknown error"])[-1]
        raise gr.Error(f"Conversion failed: {last_line}")

    markdown = output_path.read_text(encoding="utf-8")
    if not markdown.strip():
        markdown = "_No text found. If this is a scanned document, enable OCR and try again._"
    preview = markdown
    if len(preview) > PREVIEW_CHARS:
        preview = preview[:PREVIEW_CHARS] + "\n\n_Preview truncated. Download the file for the full text._"
    return str(output_path), preview, preview


with gr.Blocks(title="PDF to Markdown") as demo:
    gr.Markdown(
        f"""
        # PDF to Markdown Converter
        Upload a **PDF** or an **image** and get clean Markdown back. Parsing runs locally with
        [LiteParse](https://github.com/run-llama/liteparse); scanned pages and images go through OCR.
        Nothing is sent to an external AI service. Only the first {MAX_PAGES} pages are converted.
        """
    )
    with gr.Row():
        with gr.Column(scale=1):
            file_input = gr.File(label="PDF or image", file_types=SUPPORTED_EXTENSIONS, type="filepath")
            language_input = gr.Dropdown(available_languages(), value="English", label="OCR language")
            ocr_input = gr.Checkbox(value=True, label="Use OCR for scanned pages and images",
                                    info="OCR takes a few seconds per page. Turn it off for digital PDFs: they convert in about a second.")
            convert_button = gr.Button("Convert to Markdown", variant="primary")
            file_output = gr.File(label="Download Markdown (.md)", interactive=False)
        with gr.Column(scale=2):
            with gr.Tab("Preview"):
                preview_output = gr.Markdown()
            with gr.Tab("Raw Markdown"):
                raw_output = gr.Code(language="markdown", interactive=False)

    convert_button.click(
        fn=convert,
        inputs=[file_input, language_input, ocr_input],
        outputs=[file_output, preview_output, raw_output],
    )

if __name__ == "__main__":
    print(f"OCR workers: {OCR_WORKERS or cpu_limit()} (os.cpu_count={os.cpu_count()})")
    demo.queue(default_concurrency_limit=2).launch()
