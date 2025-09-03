FROM python:3.11.9-slim-bullseye

# Environment for predictable runtime, fewer pyc files, unbuffered logs
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install Tesseract OCR without extra packages to keep image light for Pi
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-osd libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python dependencies first for better build caching
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY src ./src
COPY README.md ./README.md

# Expose Flask port
EXPOSE 5000

# Default command uses Gunicorn with gthread workers
ENV GUNICORN_WORKERS=2 \
    GUNICORN_THREADS=4
CMD ["gunicorn", "-w", "${GUNICORN_WORKERS}", "-k", "gthread", "--threads", "${GUNICORN_THREADS}", "-b", "0.0.0.0:5000", "src.dashboard.wsgi:app"]
