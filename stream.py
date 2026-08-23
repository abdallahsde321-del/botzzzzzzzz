import subprocess
import time

cmd = (
    'streamlink --hls-live-edge 1 --ringbuffer-size 1024M '
    '--http-cookies "cookies.txt" --stdout '
    '"https://www.tiktok.com/@___alzahabey4___/live?enter_from_merge=homepage_hot&enter_method=live_entrance_hover_list" best | '
    'ffmpeg -err_detect ignore_err -fflags +genpts+nobuffer+ignidx+discardcorrupt '
    '-flags low_delay -thread_queue_size 131072 -i - '
    '-filter_complex "[0:v]scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,fps=30" '
    '-c:v libx264 -preset ultrafast -tune zerolatency '
    '-b:v 3000k -maxrate 3000k -bufsize 6000k -g 30 '
    '-c:a aac -b:a 128k -ar 44100 -ac 2 '
    '-af "aresample=async=1:min_hard_comp=0.10000:first_pts=0" '
    '-fps_mode cfr -f flv "rtmp://a.rtmp.youtube.com/live2/wk4r-0bcf-6b5f-wtwv-5808"'
)

while True:
    try:
        subprocess.run(cmd, shell=True)
    except Exception:
        pass
    time.sleep(3)