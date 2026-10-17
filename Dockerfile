FROM python:3.10-slim

# تثبيت الأدوات الأساسية وتحميل أحدث نسخة static من FFmpeg
RUN apt-get update && apt-get install -y \
    curl \
    xz-utils \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# تثبيت FFmpeg حديث داعم لـ HEVC و Enhanced FLV
RUN curl -L https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz -o ffmpeg.tar.xz \
    && tar -xf ffmpeg.tar.xz \
    && mv ffmpeg-*-amd64-static/ffmpeg /usr/local/bin/ \
    && mv ffmpeg-*-amd64-static/ffprobe /usr/local/bin/ \
    && rm -rf ffmpeg*

WORKDIR /app

# تثبيت مكتبات البايثون
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# نسخ كود البث الرئيسي
COPY main.py .

# تشغيل السكريبت مع طباعة الـ Logs فورياً
CMD ["python", "-u", "main.py"]
