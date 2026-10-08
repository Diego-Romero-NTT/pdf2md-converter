---
title: Pdf2md Converter
emoji: 🐨
colorFrom: yellow
colorTo: pink
sdk: docker
app_port: 7860
pinned: false
---

# PDF to Markdown Converter

Upload a PDF or an image and get Markdown back. Parsing runs inside the Space with
[LiteParse](https://github.com/run-llama/liteparse), so no document leaves the container and
no API key is needed. Digital PDFs keep their headings, lists and links. Scanned pages and
images go through Tesseract OCR.

## What it does

- Accepts PDF, PNG, JPG, TIFF, BMP, WebP and GIF files.
- Returns a downloadable `.md` file, plus a rendered preview and the raw Markdown.
- Runs OCR in English, Spanish, French, German, Italian or Portuguese. The language data is
  downloaded when the image is built, so requests never wait on a download.
- Lets you switch OCR off for PDFs that already contain text. On the free CPU hardware a
  64-page PDF takes about 1 second without OCR and under a minute with it.
- Converts only the first 100 pages of each document and stops any conversion that runs
  longer than 10 minutes. Both limits can be changed with environment variables.

Raster images inside a PDF appear as placeholders in the Markdown. There is no AI summary
anymore: the output is the document's own text.

## Run it locally

With Docker:

```bash
docker build -t pdf2md .
docker run --rm -p 7860:7860 pdf2md
```

Then open http://localhost:7860.

Without Docker you need Node 18+ and Python 3.10+:

```bash
npm install -g @llamaindex/liteparse@2.15.0
pip install -r requirements.txt
python app.py
```

Without `TESSDATA_PATH` set, LiteParse downloads each OCR language from GitHub the first time
it is used.

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `MAX_PAGES` | `100` | Pages converted per document |
| `TIMEOUT_SECONDS` | `600` | Time limit for one conversion |
| `OCR_WORKERS` | CPUs granted to the container | OCR threads per conversion |
| `TESSDATA_PATH` | `/opt/tessdata` in the image | Folder with the `*.traineddata` OCR files. The dropdown only lists languages found there |
| `LIT_BIN` | `lit` | Path to the LiteParse CLI |

## How it works

`app.py` is a Gradio interface around the LiteParse command line. For each request it runs
`lit parse <file> --format markdown` in a separate temporary folder, so several users can
convert files at the same time without seeing each other's results. Outputs older than an
hour are removed on the next request. The `Dockerfile` starts from `node:22-bookworm-slim`, installs Python and a
pinned LiteParse release, downloads the OCR language files (Tesseract's fast models) and runs the app as uid 1000, the
user Hugging Face Spaces expects.
