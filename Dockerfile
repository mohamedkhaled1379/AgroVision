FROM python:3.11-slim

WORKDIR /app

# System libs for OpenCV, TensorFlow, PyTorch on headless Linux
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV FLASK_ENV=production
ENV PORT=5000
ENV WEB_CONCURRENCY=1
ENV GUNICORN_TIMEOUT=300
ENV GUNICORN_GRACEFUL_TIMEOUT=300

EXPOSE 5000

CMD ["gunicorn", "-c", "gunicorn.conf.py", "app:app"]
