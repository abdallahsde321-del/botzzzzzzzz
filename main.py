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
# Check whether TikTok is live using yt-dlp
# =========================================================

def is_tiktok_live():
    command = [
        "yt-dlp",
        "--get-url",
        "--no-warnings",
        TIKTOK_URL
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

        if result.returncode == 0 and url:
            log("TikTok live detected via yt-dlp.")
            return True

        err_output = result.stderr.strip()
        if err_output:
            last_line = err_output.splitlines()[-1]
            log(f"yt-dlp check note: {last_line}")
        else:
            log("TikTok is offline or the stream is unavailable.")

        return False

    except subprocess.TimeoutExpired:
        log("TikTok detection timed out.")
        return False

    except Exception as exc:
        log(f"yt-dlp detection error: {exc}")
        return False


# =========================================================
# Run one fresh relay session using yt-dlp + ffmpeg
# =========================================================

def run_streaming_session():
    start_time = time.monotonic()
    ytdl_proc = None
    ffmpeg_proc = None

    ytdl_cmd = [
        "yt-dlp",
        "--no-warnings",
        "-o", "-",
        TIKTOK_URL
    ]

    ffmpeg_cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel", "warning",
        "-nostdin",

        # Input from yt-dlp pipe
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

        log("Starting yt-dlp stream extractor...")

        ytdl_proc = subprocess.Popen(
            ytdl_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=0
        )
        active_processes.append(ytdl_proc)

        log("Starting FFmpeg -> YouTube RTMP...")

        ffmpeg_proc = subprocess.Popen(
            ffmpeg_cmd,
            stdin=ytdl_proc.stdout,
            stdout=subprocess.DEVNULL,
            stderr=None,
            bufsize=0
        )
        active_processes.append(ffmpeg_proc)

        # Close the parent's copy of the pipe.
        ytdl_proc.stdout.close()

        log("Relay session started.")

        while not stop_requested:
            if ytdl_proc.poll() is not None:
                log(f"yt-dlp exited with code {ytdl_proc.returncode}.")
                break

            if ffmpeg_proc.poll() is not None:
                log(f"FFmpeg exited with code {ffmpeg_proc.returncode}.")
                break

            time.sleep(1)

    except Exception as exc:
        log(f"Relay error: {exc}")

    finally:
        stop_process(ffmpeg_proc)
        stop_process(ytdl_proc)

        for proc in (ffmpeg_proc, ytdl_proc):
            if proc in active_processes:
                active_processes.remove(proc)

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

    log("TikTok -> YouTube supervisor started (using yt-dlp).")
    log("Video: COPY | Audio: AAC 128 kbps.")
    log("Automatic reconnection: enabled.")

    while not stop_requested:
        try:
            if not is_tiktok_live():
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
