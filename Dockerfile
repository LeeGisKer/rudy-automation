FROM python:3.11.9-slim-bullseye

# Install Tesseract OCR
RUN apt-get update && apt-get install -y tesseract-ocr && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy project files
COPY . /app

# Install Python dependencies
RUN pip install --no-cache-dir pillow pytesseract flask

# Expose Flask port
EXPOSE 5000

# Default command launches the dashboard
CMD ["python", "src/dashboard/app.py"]
