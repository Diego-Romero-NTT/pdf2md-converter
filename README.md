---
title: Pdf2md Converter
emoji: 🐨
colorFrom: yellow
colorTo: pink
sdk: docker
app_port: 7860
pinned: false
license: apache-2.0
short_description: Convert PDFs and images to Markdown, with local OCR
---

# PDF to Markdown Converter

Upload a PDF or an image and get Markdown back. The conversion runs inside this Space with
[LiteParse](https://github.com/run-llama/liteparse) and Tesseract OCR. Your file is not sent to
any external AI service, and you don't need an API key.

## What it does

- Accepts PDF, PNG, JPG, TIFF, BMP, WebP and GIF files up to 50 MB.
- Keeps the headings, lists and links of digital PDFs.
- Reads text inside images, charts and scanned pages with OCR, in English, Spanish, French,
  German, Italian or Portuguese.
- Gives you a `.md` file to download, a rendered preview and the raw Markdown.

OCR is slow on the free CPU hardware, so the app only uses it on PDF pages that need it:

- pages with an image (a scan, a chart, or a photo next to normal text);
- pages where vector graphics cover at least 10% of the page. This is how text that was
  converted to outlines shows up. Small vector logos stay below that limit.

Other pages keep their original text and skip OCR. A 64-page report with four such pages
converts in about 3 seconds. You can also switch OCR off.

## Limitations

- Only the first 100 pages of a document are converted, and a conversion stops after
  10 minutes.
- Images are not exported. The Markdown keeps an image link where each one was, for example
  `![](img_p3_1.png)`, but the file itself is not included.
- OCR on charts and diagrams can add noisy text, such as axis labels or arrows read as
  letters. The same can happen on pages with large colored tables, which count as vector
  graphics.
- A small block of outlined text (under 10% of the page) is not detected, so it is left out.
- Tables may come out as plain lines of text instead of Markdown tables.
- Handwriting is not supported.

## Privacy

Files are processed on this Space's own hardware. Each conversion uses a separate temporary
folder, so other users cannot see your files or results. Uploads and results are deleted
within two hours. The app keeps no other copy and does not log document content. Even so,
avoid uploading confidential documents to a public Space.

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

If `TESSDATA_PATH` is not set, LiteParse downloads each OCR language from GitHub the first
time you use it.

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `MAX_PAGES` | `100` | Pages converted per document |
| `MAX_FILE_SIZE` | `50mb` | Largest upload accepted |
| `TIMEOUT_SECONDS` | `600` | Time limit for one conversion |
| `OCR_WORKERS` | CPUs granted to the container | OCR threads per conversion |
| `TESSDATA_PATH` | `/opt/tessdata` in the image | Folder with the `*.traineddata` OCR files. The language list only shows languages found there |
| `LIT_BIN` | `lit` | Path to the LiteParse CLI |

## How it works

`app.py` is a Gradio interface around the LiteParse command line. For a PDF with OCR on, it:

1. Runs `lit parse --complexity` without OCR to find the pages that hold an image or a
   large vector figure.
2. Converts the whole document to Markdown without OCR.
3. Converts only those pages with OCR and puts them in place of the same pages from step 2.

If the pages of the two runs cannot be matched, it runs OCR on the whole document instead.
Images and PDFs with OCR off go through a single `lit parse` call.

The `Dockerfile` starts from `node:22-bookworm-slim`. It installs Python and a pinned
LiteParse release, downloads Tesseract's fast OCR models, and runs the app as uid 1000, the
user Hugging Face Spaces expects.

## License

This project is licensed under the [Apache License 2.0](LICENSE).

## Credits

- [LiteParse](https://github.com/run-llama/liteparse) by LlamaIndex (Apache-2.0)
- [Tesseract](https://github.com/tesseract-ocr/tesseract) OCR and its
  [fast language models](https://github.com/tesseract-ocr/tessdata_fast) (Apache-2.0)
- [Gradio](https://www.gradio.app/) for the interface
