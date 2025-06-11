import gradio as gr
import openai
import os
import fitz  # PyMuPDF for PDFs and image rendering
import base64
import concurrent.futures
from dotenv import load_dotenv

# --- CONFIGURATION ---
# Set the maximum number of parallel API calls.
# A value between 5 and 15 is usually safe.
# Increasing this speeds up processing but also increases the risk of hitting API rate limits.
MAX_WORKERS = 10

# Load environment variables from .env file
load_dotenv()

# Configure OpenAI client with the API key
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("OPENAI_API_KEY not found. Please create a .env file and add your key.")
client = openai.OpenAI(api_key=api_key)


def get_page_analysis_from_gpt(image_base64, page_number):
    """
    Sends an image of a page to GPT-4o and asks it to extract the text and summarize it.
    This function is now designed to be called concurrently from multiple threads.
    """
    try:
        # The print statement helps visualize the parallel execution in the console
        print(f"Analyzing page {page_number}...")
        
        response = client.chat.completions.create(
            model="gpt-4.1",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": """From the attached image of a document page:
1.  **Extract All Text**: Transcribe all the text you see on the page verbatim.
2.  **Generate a Summary**: Based on the extracted text and any visual context (like charts or titles), provide a concise summary of the page's content.

Please format your response clearly in Markdown without code-blocks as follows:
### Extracted Text
_Your verbatim transcription here_

### Summary
_Your concise summary here_
"""
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_base64}"
                            },
                        },
                    ],
                }
            ],
            max_tokens=1000,
        )
        analysis = response.choices[0].message.content
        print(f"Finished analysis for page {page_number}.")
        return f"## Page {page_number}\n\n{analysis}\n"

    except Exception as e:
        print(f"Error analyzing page {page_number}: {e}")
        return f"## Page {page_number}\n\n*Error generating analysis for this page.*\n"


def process_pdf_and_analyze(uploaded_file):
    """
    Main function that now processes PDF pages in parallel.
    """
    if uploaded_file is None:
        raise gr.Error("No file uploaded. Please upload a PDF file.")

    file_path = uploaded_file.name
    filename = os.path.basename(file_path)

    if not filename.lower().endswith('.pdf'):
        raise gr.Error("Unsupported file type. This version only supports PDF files.")

    # STEP 1: Prepare all data first (convert all pages to images)
    print("Preparing pages for analysis...")
    doc = fitz.open(file_path)
    base64_images = []
    for page in doc:
        pix = page.get_pixmap(dpi=150)
        img_bytes = pix.tobytes("png")
        base64_images.append(base64.b64encode(img_bytes).decode('utf-8'))
    doc.close()
    print(f"Prepared {len(base64_images)} pages. Starting parallel analysis...")

    # STEP 2: Process pages in parallel using ThreadPoolExecutor
    markdown_content = f"# AI Analysis of {filename}\n\n"
    page_numbers = range(1, len(base64_images) + 1)
    
    # The 'with' statement ensures threads are cleaned up properly.
    # We create a pool of MAX_WORKERS threads to perform the tasks.
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # executor.map applies the function to each item in the iterables.
        # It sends a new job as soon as a thread becomes free.
        # The results are returned in the same order the jobs were submitted.
        results_iterator = executor.map(get_page_analysis_from_gpt, base64_images, page_numbers)

        # STEP 3: Collect the results as they are completed
        for result in results_iterator:
            markdown_content += result + "\n---\n"

    print("All pages analyzed. Generating markdown file.")
    output_filename = f"analysis_{os.path.splitext(filename)[0]}.md"
    with open(output_filename, "w", encoding="utf-8") as md_file:
        md_file.write(markdown_content)
        
    return output_filename


# --- Gradio Interface (No changes needed here) ---
with gr.Blocks(theme=gr.themes.Soft()) as demo:
    gr.Markdown(
        """
        # 🚀 Fast PDF Visual Analyzer (Parallel)
        Upload a **PDF file**. The app will process up to 10 pages **simultaneously** using GPT-4o Vision
        to extract text and generate a summary for each page.
        """
    )
    with gr.Row():
        file_input = gr.File(label="Upload your PDF file", file_types=[".pdf"])
    analyze_button = gr.Button("Analyze PDF with Vision", variant="primary")
    file_output = gr.File(label="Download Analysis (.md)", interactive=False)

    analyze_button.click(fn=process_pdf_and_analyze, inputs=file_input, outputs=file_output)

if __name__ == "__main__":
    demo.launch()