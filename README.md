# PDF to Markdown Converter

[![Docker build and smoke test](https://github.com/Diego-Romero-NTT/pdf2md-converter/actions/workflows/docker.yml/badge.svg)](https://github.com/Diego-Romero-NTT/pdf2md-converter/actions/workflows/docker.yml)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

A small web app that converts PDFs and images to Markdown. It runs on your own machine with
[LiteParse](https://github.com/run-llama/liteparse) and Tesseract OCR, so your files are not
sent to any external service and you don't need an API key.

## What it does

- Accepts PDF, PNG, JPG, TIFF, BMP, WebP and GIF files up to 50 MB.
- Keeps the headings, lists and links of digital PDFs.
- Reads text inside images, charts and scanned pages with OCR, in English, Spanish, French,
  German, Italian, Portuguese or Japanese.
- Gives you a `.md` file to download, a rendered preview and the raw Markdown.

OCR is slow, so the app only uses it on the PDF pages that need it:

- pages with an image (a scan, a chart, or a picture next to normal text);
- pages where vector graphics cover at least 10% of the page. This is how text that was
  converted to outlines shows up. Small vector logos stay below that limit.

Other pages keep their original text and skip OCR. On a machine with 2 CPUs, a 64-page report
with four such pages converts in about 3 seconds. You can also switch OCR off.

## Quick start

With Docker:

```bash
docker build -t pdf2md .
docker run --rm -p 7860:7860 pdf2md
```

Then open http://localhost:7860. The image includes the OCR data for all seven languages, so
OCR never downloads anything at conversion time.

Without Docker you need Node 18+ and Python 3.10+:

```bash
npm install -g @llamaindex/liteparse@2.15.0
pip install -r requirements.txt
python app.py
```

If `TESSDATA_PATH` is not set, LiteParse downloads each OCR language from GitHub the first
time you use it.

## Limitations

- Only the first 100 pages of a document are converted, and a conversion stops after
  10 minutes. Both limits can be changed (see below).
- Images are not exported. The Markdown keeps an image link where each one was, for example
  `![](img_p3_1.png)`, but the file itself is not included.
- OCR on charts and diagrams can add noisy text, such as axis labels or arrows read as
  letters. The same can happen on pages with large colored tables, which count as vector
  graphics.
- A small block of outlined text (under 10% of the page) is not detected, so it is left out.
- Tables may come out as plain lines of text instead of Markdown tables.
- Handwriting is not supported.

## Japanese

Japanese uses Tesseract's horizontal and vertical models together (`jpn+jpn_vert`). LiteParse
splits Japanese OCR lines in the wrong places and cannot read vertical columns, so for
Japanese the app puts the OCR text in reading order itself: lines from left to right, or
vertical columns from right to left. It also removes the spaces Tesseract adds between
Japanese words. On a scanned A4 test page with 10.5 pt text, this read about 99% of the
characters in order for horizontal text and about 92% for vertical text.

On pages that mix normal text and OCR text, the Japanese OCR text is added after the page's
normal text instead of at its exact position.

On a page that also has normal text, LiteParse drops OCR text from any image whose words are
mostly three characters or shorter, because it takes such an image for a chart. Most Japanese
OCR words are that short, so the text of every image on those pages was lost. When this
happens, the app takes a picture of the whole page, runs OCR on it, and keeps only the text
that is not already in the page's normal text.

## Privacy

Files are processed on the machine that runs the app. Each conversion uses a separate
temporary folder, so users of a shared instance cannot see each other's files or results.
Uploads and results are deleted within two hours. The app keeps no other copy and does not
log document content.

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `MAX_PAGES` | `100` | Pages converted per document |
| `MAX_FILE_SIZE` | `50mb` | Largest upload accepted |
| `TIMEOUT_SECONDS` | `600` | Time limit for one conversion |
| `OCR_WORKERS` | CPUs granted to the container | OCR threads per conversion |
| `TESSDATA_PATH` | `/opt/tessdata` in the image | Folder with the `*.traineddata` OCR files. The language list only shows languages found there |
| `LIT_BIN` | `lit` | Path to the LiteParse CLI |

Set them with `-e` when you start the container, for example
`docker run --rm -p 7860:7860 -e MAX_PAGES=300 pdf2md`.

## How it works

`app.py` is a Gradio interface around the LiteParse command line. For a PDF with OCR on, it:

1. Runs `lit parse --complexity` without OCR to find the pages that hold an image or a
   large vector figure.
2. Converts the whole document to Markdown without OCR.
3. Converts only those pages with OCR and puts them in place of the same pages from step 2.

If the pages of the two runs cannot be matched, it runs OCR on the whole document instead.
Images and PDFs with OCR off go through a single `lit parse` call.

The `Dockerfile` starts from `node:22-bookworm-slim`. It installs Python and a pinned
LiteParse release, downloads Tesseract's fast OCR models, and runs the app as the non-root
`node` user.

## Testing

Every push builds the Docker image, starts the app and runs `tests/smoke_test.py`. The test
converts a scanned one-page PDF with OCR and checks the text in the result. To run it against
a local instance:

```bash
pip install gradio_client pillow
python tests/smoke_test.py http://127.0.0.1:7860/
```

## License

This project is licensed under the [Apache License 2.0](LICENSE).

## Credits

- [LiteParse](https://github.com/run-llama/liteparse) by LlamaIndex (Apache-2.0)
- [Tesseract](https://github.com/tesseract-ocr/tesseract) OCR and its
  [fast language models](https://github.com/tesseract-ocr/tessdata_fast) (Apache-2.0)
- [Gradio](https://www.gradio.app/) for the interface
