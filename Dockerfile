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
# Stage 2: Production Container (Python 3.11 + Tesseract + EasyOCR) for Render / Docker
# ==============================================================================
FROM python:3.11-slim

# Prevent Python bytecode & ensure unbuffered UTF-8 logging
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    PORT=8000 \
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

# Set up non-root user (UID 1000) for secure container runtime
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

# Switch to non-root user
USER user

# Expose default application port
EXPOSE 8000

# Launch FastAPI server bound to 0.0.0.0 and dynamic port ($PORT or default 8000)
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000} --timeout-keep-alive 75"]
