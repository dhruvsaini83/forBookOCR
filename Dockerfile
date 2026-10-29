# ==============================================================================
# Stage 1: Build React 19 Frontend
# ==============================================================================
FROM node:20-slim AS frontend-builder
WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm install

COPY frontend/ ./
RUN npm run build

# ==============================================================================
# Stage 2: Hugging Face Spaces Production Container (Python 3.11 + Tesseract + EasyOCR)
# ==============================================================================
FROM python:3.11-slim

# Prevent Python bytecode & ensure unbuffered UTF-8 logging
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    PORT=7860 \
    EASYOCR_MODULE_PATH=/app/models/easyocr \
    HOME=/home/user

# Install system dependencies: Tesseract OCR (Hindi, Sanskrit, English), Devanagari fonts, and OpenCV libs
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-hin \
    tesseract-ocr-san \
    tesseract-ocr-eng \
    fonts-deva \
    libgl1 \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set up standard Hugging Face Spaces non-root user (UID 1000)
RUN useradd -m -u 1000 user
ENV PATH="/home/user/.local/bin:${PATH}"

WORKDIR /app

# Install Python packages (Using PyTorch CPU to avoid bloated 5GB+ CUDA wheels)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt

# Pre-download and cache EasyOCR Devanagari models at build time (Instant cold boot)
RUN mkdir -p /app/models/easyocr && \
    python -c "import easyocr; easyocr.Reader(['hi', 'en'], gpu=False, model_storage_directory='/app/models/easyocr')"

# Copy built frontend assets
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Copy backend application code
COPY backend ./backend

# Create storage directories and generate initial authentic manuscript samples
RUN mkdir -p backend/storage/uploads backend/storage/processed backend/storage/exports backend/storage/sample_images && \
    python backend/samples/sample_data.py

# Ensure non-root user has full read/write permissions on application and storage
RUN chown -R 1000:1000 /app && \
    chmod -R 777 /app/backend/storage /app/models

# Switch to Hugging Face standard user
USER user

# Hugging Face Spaces listens on port 7860
EXPOSE 7860

# Launch FastAPI server bound to 0.0.0.0:7860
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "7860"]
