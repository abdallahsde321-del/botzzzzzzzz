import os
import sys
import time
import signal
import subprocess
from datetime import datetime

# =========================================================
# Configuration
# =========================================================

TIKTOK_URL = os.getenv(
    "TIKTOK_URL",
    "https://www.tiktok.com/@almurtadmazin/live"
)

YOUTUBE_RTMP = os.getenv(
    "YOUTUBE_RTMP",
    "rtmp://a.rtmp.youtube.com/live2/9gs2-gayu-3pjh-wda0-1tp7"
).strip()

CHECK_INTERVAL_OFFLINE = 10
RETRY_DELAY = 5
CLEANUP_DELAY = 8
PROBE_TIMEOUT = 25
MIN_REAL_SESSION = 20

stop_requested = False
active_processes = []


# =========================================================
# Logging
# =========================================================

def log(message):
    print(
        f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}",
        flush=True
    )


def wait_interruptibly(seconds):
    end_time = time.monotonic() + seconds

    while not stop_requested and time.monotonic() < end_time:
        time.sleep(min(1, max(0, end_time - time.monotonic())))


# =========================================================
# Process cleanup
# =========================================================

def stop_process(proc):
    if proc is None:
        return

    try:
        if proc.poll() is not None:
            return

        proc.terminate()

        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=3)

    except (OSError, subprocess.SubprocessError) as exc:
        log(f"Process cleanup warning: {exc}")


def stop_all_processes():
    # Close FFmpeg before Streamlink.
    for proc in reversed(active_processes[:]):
        stop_process(proc)

    active_processes.clear()


def signal_handler(sig, frame):
    global stop_requested

    if not stop_requested:
        log("Shutdown requested.")
        stop_requested = True


signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)


# =========================================================
# Check whether TikTok is live
# =========================================================

def is_tiktok_live():
    command = [
        "streamlink",
        "--loglevel", "debug",  # تم تغيير المستوى إلى debug لطباعة تفاصيل الخطأ بوضوح
        "--stream-timeout", "15",
        "--stream-url",
        TIKTOK_URL,
        "best"
    ]

    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=PROBE_TIMEOUT,
            check=False
        )

        url = result.stdout.strip()

        if result.returncode == 0 and url.startswith(
            ("http://", "https://")
        ):
            log("TikTok live detected.")
            return True

        # طباعة الخطأ الفعلي القادم من Streamlink لمعرفة سبب المشكلة بالتحديد
        err_output = result.stderr.strip()
        if err_output:
            # طباعة آخر أسطر قليلة من الخطأ لتجنب زحمة السجلات
            last_lines = "\n".join(err_output.splitlines()[-5:])
            log(f"TikTok check failed. Streamlink error:\n{last_lines}")
        else:
            log("TikTok is offline or the stream is unavailable.")
            
        return False

    except subprocess.TimeoutExpired:
        log("TikTok detection timed out.")
        return False

    except OSError as exc:
        log(f"Streamlink detection error: {exc}")
        return False


# =========================================================
# Run one fresh relay session
# =========================================================

def run_streaming_session():
    start_time = time.monotonic()
    streamlink_proc = None
    ffmpeg_proc = None

    streamlink_cmd = [
        "streamlink",
        "--loglevel", "warning",
        "--ringbuffer-size", "512M",
        "--stream-segment-threads", "2",
        "--retry-streams", "1",
        "--retry-max", "1",
        "--stream-segment-attempts", "3",
        "--stream-segment-timeout", "15",
        "--stream-timeout", "20",
        "--http-header",
        "User-Agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36",
        "--stdout",
        TIKTOK_URL,
        "best"
    ]

    ffmpeg_cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel", "warning",
        "-nostdin",

        # Input from Streamlink
        "-fflags", "+genpts+discardcorrupt",
        "-i", "pipe:0",

        # Video: copy original encoded video
        "-map", "0:v:0",
        "-c:v", "copy",

        # Audio: AAC encoding
        "-map", "0:a:0?",
        "-c:a", "aac",
        "-b:a", "128k",
        "-ar", "44100",
        "-ac", "2",
        "-af", "aresample=async=1000:first_pts=0",

        # RTMP/FLV output
        "-avoid_negative_ts", "make_zero",
        "-max_interleave_delta", "1000000",
        "-flvflags", "no_duration_filesize",
        "-flush_packets", "1",
        "-f", "flv",
        YOUTUBE_RTMP
    ]

    try:
        if stop_requested:
            return 0

        log("Starting Streamlink...")

        streamlink_proc = subprocess.Popen(
            streamlink_cmd,
            stdout=subprocess.PIPE,
            stderr=None,
            bufsize=0
        )
        active_processes.append(streamlink_proc)
