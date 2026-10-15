import os
import subprocess
import time
import signal
import sys
import gc

TIKTOK_URL = "https://www.tiktok.com/@___alzahabey4___/live"
YOUTUBE_RTMP = "rtmp://a.rtmp.youtube.com/live2/t1u5-kzfa-eep1-77yu-44q3"

CHECK_INTERVAL_OFFLINE = 15
SESSION_RESET_DELAY = 15

STREAMLINK_CMD = [
    "streamlink",
    "--hls-live-edge", "3",
    "--hls-segment-threads", "3",
    "--ringbuffer-size", "256M",
    "--retry-streams", "5",
    "--retry-max", "5",
    "--stream-segment-attempts", "5",
    "--stream-segment-timeout", "10",
    "--stream-timeout", "15",
    "--stdout",
    TIKTOK_URL,
    "best"
]

FFMPEG_CMD = [
    "ffmpeg",
    "-hide_banner",
    "-loglevel", "warning",
    "-stats",

    "-thread_queue_size", "8192",
    "-analyzeduration", "10000000",
    "-probesize", "10000000",
    "-use_wallclock_as_timestamps", "1",
    "-i", "-",

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

streamlink_process = None
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
    global streamlink_process, ffmpeg_process
    stop_process(ffmpeg_process)
    stop_process(streamlink_process)
    streamlink_process = None
    ffmpeg_process = None
    gc.collect()

def signal_handler(sig, frame):
    print("\n[SYSTEM] Received stop signal. Cleaning up...")
    cleanup()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

print("========================================")
print("TikTok -> YouTube Ultra-Native Restreamer")
print("Status: 24/7 AUTOMATED MONITORING")
print("========================================\n")

while True:
    try:
        cleanup()
        
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Checking TikTok Live status...")
        
        streamlink_process = subprocess.Popen(
            STREAMLINK_CMD,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=0
        )

        time.sleep(4)
        
        if streamlink_process.poll() is not None:
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] TikTok is OFFLINE. Re-checking in {CHECK_INTERVAL_OFFLINE}s...")
            cleanup()
            time.sleep(CHECK_INTERVAL_OFFLINE)
            continue

        print(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] TikTok Live ONLINE! Forwarding feed to YouTube...")
        
        ffmpeg_process = subprocess.Popen(
            FFMPEG_CMD,
            stdin=streamlink_process.stdout,
            stdout=None,
            stderr=None,
            bufsize=0
        )

        streamlink_process.stdout.close()

        while True:
            sl_code = streamlink_process.poll()
            ff_code = ffmpeg_process.poll()
            
            if sl_code is not None or ff_code is not None:
                print(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] Stream ended. Terminating YouTube feed...")
                cleanup()
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Waiting {SESSION_RESET_DELAY}s for YouTube session reset...")
                time.sleep(SESSION_RESET_DELAY)
                break
                
            time.sleep(2)

    except KeyboardInterrupt:
        print("\nStopping application...")
        cleanup()
        break

    except Exception as e:
        print(f"\n[ERROR] Unexpected issue: {e}")

    finally:
        cleanup()

    time.sleep(CHECK_INTERVAL_OFFLINE)
