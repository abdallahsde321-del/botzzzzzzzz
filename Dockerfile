FROM python:3.11-slim

# تثبيت الأدوات اللازمة لتحميل فك الضغط
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    xz-utils \
    && rm -rf /var/lib/apt/lists/*

# تحميل أحدث إصدار رسمي وثابت من FFmpeg يدعم ترميز الفيديو الحديث
RUN wget https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz \
    && tar -xf ffmpeg-release-amd64-static.tar.xz \
    && cp ffmpeg-*-amd64-static/ffmpeg /usr/local/bin/ \
    && cp ffmpeg-*-amd64-static/ffprobe /usr/local/bin/ \
    && rm -rf ffmpeg-*

# تحديد مجلد العمل داخل الحاوية
WORKDIR /app

# نسخ ملف المتطلبات وتثبيتها
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# نسخ باقي ملفات المشروع
COPY . .

# أمر تشغيل السكريبت
CMD ["python", "main.py"]
