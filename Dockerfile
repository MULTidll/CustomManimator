FROM python:3.10-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# (ffmpeg, latexmk, texlive-full, libcairo2-dev, pkg-config)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    latexmk \
    texlive-full \
    libcairo2-dev \
    pkg-config \
    libpango1.0-dev \
    curl \
    build-essential \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

RUN mkdir -p media/videos/generated_video/1080p60 media/Tex media/texts media/images

EXPOSE 8501
#streamlit checks
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s \
  CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# Pass GEMINI_API_KEY as an environment variable during `docker run`
# Example: docker run -p 8501:8501 -e GEMINI_API_KEY='your_api_key' manimator-image
CMD ["streamlit", "run", "src/app.py", "--server.port=8501", "--server.address=0.0.0.0"]
