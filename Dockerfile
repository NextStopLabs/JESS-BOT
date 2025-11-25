FROM python:3.12-slim

WORKDIR /app

# Install system dependencies for TTS (pyttsx3 / espeak-ng)
RUN apt-get update && apt-get install -y --no-install-recommends \
    espeak \
    espeak-ng \
    ffmpeg \
    libasound2 \
    libasound2-dev \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy bot
COPY . .

EXPOSE 8080

CMD ["python", "main.py"]
