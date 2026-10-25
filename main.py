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
    "rtmp://a.rtmp.youtube.com/live2/5czj-a0sq-5cmp-4aps-bq5h"
).strip()

TIKTOK_SESSIONID = os.getenv(
    "TIKTOK_SESSIONID",
    "8df3a0ebb15a97c1452dc36915f86aef"
)

CHECK_INTERVAL_OFFLINE = 10
RETRY_DELAY = 5
CLEANUP_DELAY = 8
PROBE_TIMEOUT = 25
MIN_REAL_SESSION = 20

stop_requested = False
active_processes = []


# =========================================================
# Setup Cookies File for yt-dlp
# =========================================================

def setup_cookies_file():
    if TIKTOK_SESSIONID:
        try:
            with open("cookies.txt", "w", encoding="utf-8") as f:
                f.write("# Netscape HTTP Cookie File\n")
                f.write(f".tiktok.com\tTRUE\t/\tTRUE\t2147483647\tsessionid\t{TIKTOK_SESSIONID}\n")
            print("[INFO] cookies.txt generated successfully.", flush=True)
        except Exception as e:
            print(f"[WARNING] Failed to create cookies.txt: {e}", flush=True)


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
# Get Direct Stream URL using yt-dlp
# =========================================================

def get_direct_stream_url():
    command = [
        "yt-dlp",
        "--get-url",
        "--no-warnings",
    ]
    
    if os.path.exists("cookies.txt"):
        command.extend(["--cookies", "cookies.txt"])
        
    command.append(TIKTOK_URL)

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

        if result.returncode == 0 and url:
            return url

        err_output = result.stderr.strip()
        if err_output:
            last_line = err_output.splitlines()[-1]
            log(f"yt-dlp note: {last_line}")

        return None

    except subprocess.TimeoutExpired:
        log("yt-dlp timed out while getting stream URL.")
        return None
    except Exception as exc:
        log(f"yt-dlp error: {exc}")
        return None


# =========================================================
# Run one fresh relay session using FFmpeg directly
# =========================================================

def run_streaming_session():
    start_time = time.monotonic()
    ffmpeg_proc = None

    log("Fetching direct stream URL via yt-dlp...")
    stream_url = get_direct_stream_url()

    if not stream_url:
        log("Could not retrieve direct stream URL.")
        return 0

    log("Direct stream URL acquired successfully.")

    ffmpeg_cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel", "warning",
        "-nostdin",

        # تحديد صيغة البث المباشر لتيك توك لمنع الانهيار
        "-f", "flv",
        "-fflags", "+genpts+discardcorrupt",
        "-i", stream_url,

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

        log("Starting FFmpeg -> YouTube RTMP...")

        ffmpeg_proc = subprocess.Popen(
            ffmpeg_cmd,
            stdout=subprocess.DEVNULL,
            stderr=None,
            bufsize=0
        )
        active_processes.append(ffmpeg_proc)

        log("Relay session started.")

        while not stop_requested:
            if ffmpeg_proc.poll() is not None:
                log(f"FFmpeg exited with code {ffmpeg_proc.returncode}.")
                break

            time.sleep(1)

    except Exception as exc:
        log(f"Relay error: {exc}")

    finally:
        stop_process(ffmpeg_proc)
        if ffmpeg_proc in active_processes:
            active_processes.remove(ffmpeg_proc)

    duration = time.monotonic() - start_time
    log(f"Relay session closed after {duration:.1f} seconds.")

    return duration


# =========================================================
# Main supervisor
# =========================================================

def main():
    if not YOUTUBE_RTMP:
        log("ERROR: YOUTUBE_RTMP is empty.")
        sys.exit(1)

    setup_cookies_file()

    log("TikTok -> YouTube supervisor started (Direct URL + FLV mode).")
    log("Video: COPY | Audio: AAC 128 kbps.")
    log("Automatic reconnection: enabled.")

    while not stop_requested:
        try:
            stream_url = get_direct_stream_url()
            if not stream_url:
                log("TikTok is offline or the stream is unavailable.")
                wait_interruptibly(CHECK_INTERVAL_OFFLINE)
                continue

            if stop_requested:
                break

            duration = run_streaming_session()

            if stop_requested:
                break

            if duration >= MIN_REAL_SESSION:
                log(
                    f"Waiting {CLEANUP_DELAY} seconds "
                    "before checking for a new live."
                )
                wait_interruptibly(CLEANUP_DELAY)
            else:
                log(f"Retrying in {RETRY_DELAY} seconds.")
                wait_interruptibly(RETRY_DELAY)

        except Exception as exc:
            log(f"Supervisor error: {exc}")
            wait_interruptibly(RETRY_DELAY)

    stop_all_processes()
    log("Supervisor stopped cleanly.")


if __name__ == "__main__":
    main()
