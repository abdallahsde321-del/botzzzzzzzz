import os
import sys
import time
import signal
import subprocess
import threading
from datetime import datetime

# ================== SETTINGS ==================

TIKTOK_URL = os.getenv(
    "TIKTOK_URL",
    "https://www.tiktok.com/@abdullahal3085/live"
).strip()

# ضع مفتاح البث الخاص بك في متغير البيئة YOUTUBE_STREAM_KEY أو استبدله هنا
STREAM_KEY = os.getenv("YOUTUBE_STREAM_KEY", "").strip()
DEFAULT_RTMP = f"rtmp://a.rtmp.youtube.com/live2/{STREAM_KEY}" if STREAM_KEY else "rtmp://a.rtmp.youtube.com/live2/43wg-ubwg-3wea-ezd4-7wj1"

YOUTUBE_RTMP = os.getenv("YOUTUBE_RTMP", DEFAULT_RTMP).strip()

CHECK_INTERVAL_OFFLINE = 15
RETRY_DELAY = 5

stop_event = threading.Event()
ffmpeg_process = None


# ================== LOGGING ==================

def log(message):
    print(
        f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}",
        flush=True
    )


# ================== PROCESS MANAGEMENT ==================

def stop_process(process):
    if process is None or process.poll() is not None:
        return

    try:
        process.terminate()
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            process.kill()
            process.wait(timeout=3)
        except Exception:
            pass
    except Exception as exc:
        log(f"Process cleanup warning: {exc}")


def cleanup():
    global ffmpeg_process
    stop_process(ffmpeg_process)
    ffmpeg_process = None


def signal_handler(sig, frame):
    log("Shutdown signal received. Cleaning up...")
    stop_event.set()
    cleanup()


signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)


# ================== STREAMLINK URL EXTRACTION ==================

def get_tiktok_stream_url():
    """استخراج رابط M3U8 المباشر للبث بدون استخدام أنبوب"""
    cmd = [
        "streamlink",
        "--stream-url",
        "--retry-streams", "3",
        "--stream-segment-timeout", "10",
        TIKTOK_URL,
        "best"
    ]
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=20
        )
        if result.returncode == 0 and result.stdout.strip().startswith("http"):
            return result.stdout.strip()
    except Exception as e:
        log(f"Streamlink extraction error: {e}")
    return None


# ================== FFMPEG ==================

def make_ffmpeg_command(stream_url):
    return [
        "ffmpeg",
        "-hide_banner",
        "-loglevel", "error",
        "-stats_period", "10",
        "-nostdin",

        # إعدادات إعادة الاتصال التلقائي لقراءة HLS مباشرة
        "-reconnect", "1",
        "-reconnect_streamed", "1",
        "-reconnect_delay_max", "5",
        "-rw_timeout", "15000000",

        # Input
        "-i", stream_url,

        # إهمال البيانات والترجمة غير المعرفة
        "-sn", "-dn",

        # VIDEO: Re-encode to libx264
        "-map", "0:v:0?",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-tune", "zerolatency",
        "-pix_fmt", "yuv420p",
        "-g", "60",

        # AUDIO: AAC 128k
        "-map", "0:a:0?",
        "-c:a", "aac",
        "-b:a", "128k",
        "-ar", "44100",
        "-ac", "2",

        # Timestamp & Latency Optimizations
        "-fflags", "+genpts+discardcorrupt+nobuffer+fastseek",
        "-avoid_negative_ts", "make_zero",

        # YouTube RTMP output
        "-flvflags", "no_duration_filesize",
        "-f", "flv",
        YOUTUBE_RTMP
    ]


# ================== START STREAM ==================

def start_stream():
    global ffmpeg_process

    if stop_event.is_set():
        return False

    log("Fetching TikTok direct stream URL...")
    stream_url = get_tiktok_stream_url()

    if not stream_url:
        log("TikTok stream offline or URL unavailable.")
        return False

    log("Direct URL obtained. Starting FFmpeg -> YouTube RTMP...")

    ffmpeg_process = subprocess.Popen(
        make_ffmpeg_command(stream_url),
        stdout=subprocess.DEVNULL,
        stderr=None
    )

    log("Relay running cleanly. Video: H.264 (libx264 ultrafast); Audio: AAC 128k.")

    while not stop_event.is_set():
        ff_code = ffmpeg_process.poll()

        if ff_code is not None:
            log(f"FFmpeg stopped (exit code {ff_code}).")
            return False

        time.sleep(1)

    return False


# ================== MAIN LOOP ==================

def main():
    if not TIKTOK_URL:
        log("ERROR: TIKTOK_URL is empty.")
        sys.exit(1)

    if not YOUTUBE_RTMP:
        log("ERROR: Set YOUTUBE_RTMP environment variable.")
        sys.exit(1)

    log("TikTok -> YouTube Relay Started")
    log("Video encoding: H.264 (libx264 ultrafast)")
    log("Audio encoding: AAC 128k")
    log("Automatic reconnection: ON")

    while not stop_event.is_set():
        started_at = time.monotonic()

        try:
            cleanup()
            start_stream()

        except Exception as exc:
            log(f"Unexpected error: {exc}")

        finally:
            cleanup()

        if stop_event.is_set():
            break

        elapsed = time.monotonic() - started_at

        if elapsed > 60:
            delay = RETRY_DELAY
            log(f"Stream disconnected. Retrying in {delay}s...")
        else:
            delay = CHECK_INTERVAL_OFFLINE
            log(f"Stream unavailable. Checking again in {delay}s...")

        stop_event.wait(delay)

    cleanup()
    log("Relay stopped cleanly.")


if __name__ == "__main__":
    main()
