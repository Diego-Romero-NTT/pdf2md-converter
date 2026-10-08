FROM node:22-bookworm-slim

# Python for the Gradio app, curl for fetching OCR language data at build time.
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-venv ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

RUN npm install -g @llamaindex/liteparse@2.15.0 && npm cache clean --force

# Bake the OCR languages into the image so no download happens at request time.
# The "fast" models are about 3x quicker than "best" with near-identical output.
ENV TESSDATA_PATH=/opt/tessdata
RUN mkdir -p "$TESSDATA_PATH" \
    && for lang in eng spa fra deu ita por; do \
         curl -fsSL -o "$TESSDATA_PATH/$lang.traineddata" \
           "https://github.com/tesseract-ocr/tessdata_fast/raw/main/$lang.traineddata"; \
       done

# Run as the image's non-root "node" user (uid 1000).
USER node
ENV HOME=/home/node \
    PATH=/home/node/venv/bin:$PATH \
    GRADIO_SERVER_NAME=0.0.0.0 \
    GRADIO_SERVER_PORT=7860
WORKDIR /home/node/app

RUN python3 -m venv /home/node/venv
COPY --chown=node requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=node app.py .

EXPOSE 7860
CMD ["python", "app.py"]
