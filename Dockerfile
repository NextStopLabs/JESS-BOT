# Use latest Python
FROM python:3.12-slim

# Set work directory
WORKDIR /app

# Install system dependencies (if you ever add voice/TTS you will need these)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy everything else
COPY . .

# Expose FastAPI port
EXPOSE 8080

# Run bot
CMD ["python", "main.py"]
