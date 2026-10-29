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
# Stage 2: Production Python Backend with Tesseract & EasyOCR
# ==============================================================================
FROM python:3.11-slim

# Prevent Python from writing .pyc files and buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    PORT=8000

# Install Linux system dependencies: Tesseract OCR (with Hindi & Sanskrit) and OpenCV libs
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-hin \
    tesseract-ocr-san \
    libgl1 \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies (Using PyTorch CPU to optimize container size)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt

# Pre-download and cache EasyOCR Devanagari detection and recognition models
RUN python -c "import easyocr; easyocr.Reader(['hi', 'en'], gpu=False)"

# Copy built frontend assets
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Copy backend application code
COPY backend ./backend

# Create storage directories and generate initial authentic sample images
RUN mkdir -p backend/storage/uploads backend/storage/processed backend/storage/exports backend/storage/sample_images && \
    python backend/samples/sample_data.py

EXPOSE 8000

# Run FastAPI via uvicorn (respecting $PORT dynamically for Render/Railway/Cloud Run)
CMD uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}

