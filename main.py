import os
import subprocess
import time
import signal
import sys
import gc

TIKTOK_URL = "https://www.tiktok.com/@abdullahal3085/live"
YOUTUBE_RTMP = "rtmp://a.rtmp.youtube.com/live2/43wg-ubwg-3wea-ezd4-7wj1"

CHECK_INTERVAL_OFFLINE = 15
SESSION_RESET_DELAY = 15

ffmpeg_process = None

def stop_process(process):
    if process and process.poll() is None:
        try:
            process.terminate()
            process.wait(timeout=3)
        except Exception:
            try:
                process.kill()
                process.wait(timeout=2)
            except Exception:
                pass

def cleanup():
    global ffmpeg_process
    stop_process(ffmpeg_process)
    ffmpeg_process = None
    gc.collect()

def signal_handler(sig, frame):
    print("\n[SYSTEM] Received stop signal. Cleaning up...")
    cleanup()
    sys.exit(0)

def get_tiktok_live_url(tiktok_url):
    cmd = [
        "yt-dlp",
        "-g",
        "-f", "b/best",
        "--no-warnings",
        "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        tiktok_url
    ]
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=15)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip().splitlines()[0]
        else:
            if result.stderr:
                print(f"[DEBUG DETAILS] {result.stderr.strip().splitlines()[-1]}")
            return None
    except Exception as e:
        print(f"[DEBUG ERROR] Exception while getting URL: {e}")
        return None

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

print("========================================")
print("TikTok -> YouTube Ultra-Native Restreamer")
print("Engine: yt-dlp + FFmpeg Direct Pipeline")
print("========================================\n")

while True:
    try:
        cleanup()
        
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Checking TikTok Live status via yt-dlp...")
        
        live_stream_url = get_tiktok_live_url(TIKTOK_URL)

        if not live_stream_url:
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] TikTok is OFFLINE or Blocked. Re-checking in {CHECK_INTERVAL_OFFLINE}s...")
            time.sleep(CHECK_INTERVAL_OFFLINE)
            continue

        print(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] TikTok Live ONLINE! Direct URL extracted.")
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Forwarding feed to YouTube...")

        ffmpeg_cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel", "warning",
            "-stats",

            "-reconnect", "1",
            "-reconnect_streamed", "1",
            "-reconnect_delay_max", "5",

            "-thread_queue_size", "8192",
            "-analyzeduration", "10000000",
            "-probesize", "10000000",
            "-use_wallclock_as_timestamps", "1",
            "-i", live_stream_url,

            "-map", "0:v:0",
            "-c:v", "copy",
            "-bsf:v", "dump_extra",

            "-map", "0:a:0?",
            "-c:a", "aac",
            "-b:a", "128k",
            "-ar", "44100",
            "-ac", "2",
            "-af", "aresample=async=1000:min_hard_comp=0.100000:first_pts=0",

            "-fflags", "+genpts+discardcorrupt",
            "-avoid_negative_ts", "make_zero",
            "-dts_delta_threshold", "2",
            "-max_interleave_delta", "0",
            "-flush_packets", "1",

            "-flvflags", "no_duration_filesize",

            "-f", "flv",
            YOUTUBE_RTMP
        ]

        ffmpeg_process = subprocess.Popen(ffmpeg_cmd)

        while True:
            ff_code = ffmpeg_process.poll()
            if ff_code is not None:
                print(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] Stream ended. Terminating YouTube feed...")
                cleanup()
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Waiting {SESSION_RESET_DELAY}s for YouTube session reset...")
                time.sleep(SESSION_RESET_DELAY)
                break
                
            time.sleep(3)

    except KeyboardInterrupt:
        print("\nStopping application...")
        cleanup()
        break

    except Exception as e:
        print(f"\n[ERROR] Unexpected issue: {e}")

    finally:
        cleanup()

    time.sleep(CHECK_INTERVAL_OFFLINE)
