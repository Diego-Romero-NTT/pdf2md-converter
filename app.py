import json
import os
import re
import shutil
import statistics
import subprocess
import tempfile
import threading
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
# Largest upload accepted, in Gradio's size format.
MAX_FILE_SIZE = os.getenv("MAX_FILE_SIZE", "50mb")
# Path to the LiteParse CLI.
LIT_BIN = os.getenv("LIT_BIN", "lit")
# Uploads and outputs older than this are deleted.
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
    # Both models run; Tesseract keeps whichever fits each line, horizontal or vertical.
    "Japanese": "jpn+jpn_vert",
}
# Languages whose OCR boxes LiteParse lays out badly: its line grouping splits Japanese lines
# (punctuation and kana get different box heights) and cannot read vertical columns.
# For these, the app rebuilds the reading order of OCR text from the boxes itself.
REBUILD_READING_ORDER = {"Japanese"}
# Tesseract puts spaces between Japanese words; Japanese is written without them.
CJK = r"\u3000-\u303f\u3040-\u309f\u30a0-\u30ff\u4e00-\u9fff\uff00-\uffef"
SPACE_BETWEEN_CJK = re.compile(f"(?<=[{CJK}]) +(?=[{CJK}])")
EMPTY_CODE_BLOCK = re.compile(r"^```\w*\n\s*```$", re.MULTILINE)
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
            if all((Path(TESSDATA_PATH) / f"{model}.traineddata").exists() for model in code.split("+"))]


def remove_old_outputs():
    """Each request writes to its own folder; drop folders older than OUTPUT_TTL_SECONDS."""
    cutoff = time.time() - OUTPUT_TTL_SECONDS
    for folder in WORK_ROOT.iterdir():
        if folder.is_dir() and folder.stat().st_mtime < cutoff:
            shutil.rmtree(folder, ignore_errors=True)


def remove_old_outputs_forever():
    """Clean up even when no new request arrives."""
    while True:
        time.sleep(OUTPUT_TTL_SECONDS)
        remove_old_outputs()


# Share of a page covered by vector figures above which the page goes through OCR, to catch
# text drawn as outlines. Logos measured 1-5%; an outlined half page measured 46%.
VECTOR_FIGURE_MIN_COVERAGE = 0.10
# LiteParse separates pages in its Markdown output with this line.
PAGE_SEPARATOR = "\n-----\n"


def run_lit(source, work_dir, options, output_path, deadline):
    command = [LIT_BIN, "parse", str(source), "--max-pages", str(MAX_PAGES), "-o", str(output_path), "--quiet"]
    if TESSDATA_PATH:
        config_path = work_dir / "liteparse.config.json"
        config_path.write_text(json.dumps({"tessdataPath": TESSDATA_PATH}))
        command += ["--config", str(config_path)]
    try:
        result = subprocess.run(command + options, capture_output=True, text=True,
                                timeout=max(1, deadline - time.monotonic()))
    except subprocess.TimeoutExpired:
        raise gr.Error(f"Conversion took longer than {TIMEOUT_SECONDS} seconds and was stopped.")
    if result.returncode != 0 or not output_path.exists():
        print(f"lit failed ({result.returncode}): {result.stderr}")
        last_line = (result.stderr.strip().splitlines() or ["unknown error"])[-1]
        raise gr.Error(f"Conversion failed: {last_line}")
    return output_path.read_text(encoding="utf-8")


def needs_ocr(complexity):
    """A page needs OCR when it holds a raster image (inline or a full-page scan) or a vector
    figure big enough to be text drawn as outlines. Small vector logos stay below the cutoff."""
    return (complexity["image_block_count"] > 0
            or complexity["full_page_image"]
            or complexity["layout"]["figure_coverage"] >= VECTOR_FIGURE_MIN_COVERAGE)


def pages_needing_ocr(source, work_dir, deadline):
    """Every page's native text boxes and complexity, and the pages to OCR. The others keep
    their native text only."""
    pages = json.loads(run_lit(source, work_dir, ["--format", "json", "--no-ocr", "--complexity"],
                               work_dir / "complexity.json", deadline))["pages"]
    return pages, [page["page"] for page in pages if needs_ocr(page["complexity"])]


def box_key(item):
    return item["text"], round(item["x"], 1), round(item["y"], 1)


def read_ocr_boxes(items):
    """Join OCR boxes in reading order. Boxes are grouped into lines (horizontal text) or
    columns (vertical text, read right to left) by their centers, then read along each line."""
    items = [item for item in items if item["text"].strip()]
    if not items:
        return ""
    tall = sum(item["height"] > 1.5 * item["width"] for item in items if len(item["text"].strip()) > 1)
    wide = sum(item["width"] > 1.5 * item["height"] for item in items if len(item["text"].strip()) > 1)
    if tall > wide:
        across = lambda item: -(item["x"] + item["width"] / 2)
        along = lambda item: item["y"]
        thickness = lambda item: item["width"]
    else:
        across = lambda item: item["y"] + item["height"] / 2
        along = lambda item: item["x"]
        thickness = lambda item: item["height"]
    tolerance = 0.6 * statistics.median(thickness(item) for item in items)
    lines = []
    for item in sorted(items, key=across):
        if lines and abs(across(item) - lines[-1][0]) <= tolerance:
            lines[-1][1].append(item)
        else:
            lines.append((across(item), [item]))
    text = "\n".join(" ".join(item["text"] for item in sorted(boxes, key=along)) for _, boxes in lines)
    return SPACE_BETWEEN_CJK.sub("", text)


def restore_heading_levels(ocr_page, text_page):
    """Heading levels depend on the font sizes seen in one run, so an OCR run over a few
    pages can rank a line differently. Reuse the whole-document run's version of the line."""
    originals = {line.lstrip("#").strip(): line for line in text_page.splitlines() if line.strip()}
    return "\n".join(originals.get(line.lstrip("#").strip(), line) if line.startswith("#") else line
                     for line in ocr_page.splitlines())


def to_markdown(source, work_dir, ocr_options, deadline, rebuild_reading_order=False):
    output_path = work_dir / f"{source.stem}.md"
    if ocr_options is None:
        return run_lit(source, work_dir, ["--format", "markdown", "--no-ocr"], output_path, deadline)
    if source.suffix.lower() != ".pdf":
        if not rebuild_reading_order:
            return run_lit(source, work_dir, ["--format", "markdown"] + ocr_options, output_path, deadline)
        pages = json.loads(run_lit(source, work_dir, ["--format", "json"] + ocr_options,
                                   work_dir / "ocr.json", deadline))["pages"]
        markdown = PAGE_SEPARATOR.join(read_ocr_boxes(page["text_items"]) for page in pages)
        output_path.write_text(markdown, encoding="utf-8")
        return markdown

    pages, pages_to_ocr = pages_needing_ocr(source, work_dir, deadline)
    text_markdown = run_lit(source, work_dir, ["--format", "markdown", "--no-ocr"], output_path, deadline)
    if not pages_to_ocr:
        return text_markdown
    text_pages = text_markdown.split(PAGE_SEPARATOR)
    target_pages = ["--target-pages", ",".join(map(str, pages_to_ocr))]
    if rebuild_reading_order and len(text_pages) == len(pages):
        # Keep each page's native Markdown and add the OCR text, read in the right order.
        native_boxes = {page["page"]: {box_key(item) for item in page["text_items"]} for page in pages}
        ocr_json = run_lit(source, work_dir, ["--format", "json"] + target_pages + ocr_options,
                           work_dir / "ocr_pages.json", deadline)
        for page in json.loads(ocr_json)["pages"]:
            ocr_text = read_ocr_boxes([item for item in page["text_items"]
                                       if box_key(item) not in native_boxes[page["page"]]])
            # A page with no native text renders as an empty code block; drop it.
            native_text = EMPTY_CODE_BLOCK.sub("", text_pages[page["page"] - 1]).strip("\n")
            text_pages[page["page"] - 1] = "\n\n".join(part for part in (native_text, ocr_text) if part)
    else:
        ocr_markdown = run_lit(source, work_dir, ["--format", "markdown"] + target_pages + ocr_options,
                               work_dir / "ocr_pages.md", deadline)
        ocr_pages = ocr_markdown.split(PAGE_SEPARATOR)
        if len(text_pages) != len(pages) or len(ocr_pages) != len(pages_to_ocr):
            # The document itself contains the separator line, so pages cannot be matched. OCR everything.
            print(f"Page split mismatch for {source.name}; running OCR on the whole document.")
            return run_lit(source, work_dir, ["--format", "markdown"] + ocr_options, output_path, deadline)
        for page_number, ocr_page in zip(pages_to_ocr, ocr_pages):
            text_pages[page_number - 1] = restore_heading_levels(ocr_page, text_pages[page_number - 1])
    markdown = PAGE_SEPARATOR.join(text_pages)
    output_path.write_text(markdown, encoding="utf-8")
    return markdown


def convert(uploaded_path, language, use_ocr):
    if not uploaded_path:
        raise gr.Error("No file uploaded. Please upload a PDF or an image.")

    source = Path(uploaded_path)
    if source.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise gr.Error(f"Unsupported file type '{source.suffix}'. Supported: {', '.join(SUPPORTED_EXTENSIONS)}")

    remove_old_outputs()
    work_dir = Path(tempfile.mkdtemp(dir=WORK_ROOT))
    deadline = time.monotonic() + TIMEOUT_SECONDS
    ocr_options = None
    if use_ocr:
        ocr_options = ["--ocr-language", OCR_LANGUAGES[language],
                       "--num-workers", OCR_WORKERS or str(cpu_limit())]
    markdown = to_markdown(source, work_dir, ocr_options, deadline,
                           rebuild_reading_order=language in REBUILD_READING_ORDER)

    if not markdown.strip():
        markdown = "_No text found. If this is a scanned document, enable OCR and try again._"
    preview = markdown
    if len(preview) > PREVIEW_CHARS:
        preview = preview[:PREVIEW_CHARS] + "\n\n_Preview truncated. Download the file for the full text._"
    return str(work_dir / f"{source.stem}.md"), preview, preview


# Gradio keeps its own copy of every upload and returned file; clear it on the same schedule.
with gr.Blocks(title="PDF to Markdown", delete_cache=(OUTPUT_TTL_SECONDS, OUTPUT_TTL_SECONDS)) as demo:
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
            ocr_input = gr.Checkbox(value=True, label="Use OCR on images",
                                    info="Reads text inside pictures, charts and scanned pages. Pages without images skip OCR.")
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
    print(f"OCR workers: {OCR_WORKERS or cpu_limit()} (os.cpu_count={os.cpu_count()})", flush=True)
    threading.Thread(target=remove_old_outputs_forever, daemon=True).start()
    demo.queue(default_concurrency_limit=2, max_size=20).launch(max_file_size=MAX_FILE_SIZE)
