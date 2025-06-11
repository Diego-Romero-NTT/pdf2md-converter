---
title: Pdf2md Converter
emoji: 🐨
colorFrom: yellow
colorTo: pink
sdk: gradio
sdk_version: 5.33.1
app_file: app.py
pinned: false
---

# PDF to Markdown Converter with AI Analysis

This Python application leverages OpenAI's GPT-4.1 model to analyze PDF files page by page, extract text, and generate summaries. It processes pages in parallel for faster analysis and outputs the results into a Markdown file. The application features a user-friendly web interface built with Gradio.

## Features

*   **PDF Processing**: Upload PDF files directly through the web interface.
*   **AI-Powered Analysis**: Uses GPT-4.1 with vision capabilities to:
    *   Extract all text from each page.
    *   Generate a concise summary of each page's content.
*   **Parallel Processing**: Analyzes multiple PDF pages concurrently (up to a configurable limit) to speed up the process.
*   **Markdown Output**: Saves the extracted text and summaries in a structured Markdown file.
*   **Gradio Web Interface**: Easy-to-use interface for uploading files and downloading results.
*   **Environment Variable Support**: Securely manages the OpenAI API key using a `.env` file.
*   **Automatic Deletion of Previous Output**: Cleans up the previously generated Markdown file before a new analysis.

## Requirements

*   Python 3.x
*   OpenAI API Key
*   The following Python libraries (installable via `pip`):
    *   `gradio`
    *   `openai`
    *   `python-dotenv`
    *   `PyMuPDF` (fitz)
    *   `concurrent.futures` (standard library)

You can install these dependencies using the `requirements.txt` file:
```bash
pip install -r requirements.txt
```

## Setup

1.  **Clone the Repository (if applicable)**:
    ```bash
    # git clone <repository-url>
    # cd <repository-directory>
    ```

2.  **Install Dependencies**:
    Make sure you have Python 3 installed. Then, install the required libraries:
    ```bash
    pip install gradio openai python-dotenv PyMuPDF
    ```
    Or, if you have a `requirements.txt` file:
    ```bash
    pip install -r requirements.txt
    ```

3.  **Set up OpenAI API Key**:
    *   Create a file named `.env` in the root directory of the project.
    *   Add your OpenAI API key to the `.env` file as follows:
        ```
        OPENAI_API_KEY="your_openai_api_key_here"
        ```
    *   Replace `"your_openai_api_key_here"` with your actual OpenAI API key.

## Usage

1.  **Run the Application**:
    Execute the `app.py` script from your terminal:
    ```bash
    python app.py
    ```
    This will start the Gradio web server. The output in the terminal will typically provide a local URL (e.g., `http://127.0.0.1:7860`) where you can access the application in your web browser.

2.  **Upload PDF**:
    *   Open the provided URL in your web browser.
    *   Use the file input component to upload your PDF file.

3.  **Analyze PDF**:
    *   Click the "Analyze PDF with Vision" button.
    *   The application will process the PDF. You can see progress messages (e.g., "Analyzing page X...") in the terminal where `app.py` is running.

4.  **Download Markdown**:
    *   Once the analysis is complete, a download link for the generated Markdown file (e.g., `analysis_yourfilename.md`) will appear.
    *   The Markdown file will contain the extracted text and summary for each page.

## Configuration

*   **`MAX_WORKERS`**: Located at the beginning of `app.py`, this constant defines the maximum number of PDF pages to process in parallel.
    ```python
    MAX_WORKERS = 10
    ```
    You can adjust this value. A higher value can speed up processing for PDFs with many pages but increases the risk of hitting API rate limits or using more system resources. A value between 5 and 15 is generally recommended.

## How it Works

1.  **File Upload**: The user uploads a PDF file via the Gradio interface.
2.  **PDF Parsing**: `PyMuPDF` (fitz) is used to open the PDF and convert each page into a PNG image. These images are then encoded in base64.
3.  **Parallel API Calls**: The application uses a `ThreadPoolExecutor` to send requests for multiple pages to the OpenAI GPT-4.1 API simultaneously.
    *   For each page image, a request is made to GPT-4.1 asking it to extract all text and provide a summary.
4.  **Content Aggregation**: The responses from GPT-4.1 (containing extracted text and summaries for each page) are collected.
5.  **Markdown Generation**: The aggregated content is formatted into a Markdown string, with clear headings for each page, its extracted text, and its summary.
6.  **File Output**: The Markdown string is saved to a `.md` file, which is then made available for download. The previously generated output file (if any) is deleted before creating a new one.

## Error Handling

*   The application checks if an OpenAI API key is provided in the `.env` file.
*   It handles errors during the analysis of individual pages, noting the error in the output Markdown for that specific page and continuing with other pages.
*   It raises an error if no file is uploaded or if the uploaded file is not a PDF.
*   Errors during the deletion of previous output files are logged but do not stop the current analysis.


