import subprocess
import time

cmd = [
    "streamlink",
    "--hls-live-edge", "2",
    "--ringbuffer-size", "128M",
    "--http-cookies-file", "cookies.txt",
    "--retry-streams", "30",
    "--retry-max", "0",
    "--stream-segment-attempts", "30",
    "--stream-segment-timeout", "10",
    "--stream-timeout", "20",
    "--stdout",
    "https://www.tiktok.com/@___alzahabey4___/live?enter_from_merge=homepage_hot&enter_method=live_entrance_hover_list",
]

ffmpeg_cmd = [
    "ffmpeg",
    "-err_detect", "ignore_err",
    "-fflags", "+genpts+nobuffer+igndts+discardcorrupt",
    "-flags", "low_delay",
    "-analyzeduration", "0",
    "-probesize", "32",
    "-thread_queue_size", "16384",
    "-i", "-",
    "-filter_complex", "[0:v]scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,fps=30",
    "-c:v", "libx264",
    "-preset", "ultrafast",
    "-tune", "zerolatency",
    "-threads", "1",
    "-b:v", "3000k",
    "-maxrate", "3000k",
    "-bufsize", "6000k",
    "-g", "30",
    "-c:a", "aac",
    "-b:a", "128k",
    "-ar", "44100",
    "-ac", "2",
    "-af", "aresample=async=1:min_hard_comp=0.001:first_pts=0",
    "-fps_mode", "cfr",
    "-f", "flv",
    "rtmp://a.rtmp.youtube.com/live2/uvff-6dbq-eyu2-r74m-934w"
]

while True:
    try:
        p1 = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        p2 = subprocess.Popen(ffmpeg_cmd, stdin=p1.stdout, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        p1.stdout.close()
        p2.wait()
    except Exception:
        pass
    
    time.sleep(1)