import subprocess

cmd = (
    'streamlink --hls-live-edge 3 --ringbuffer-size 512M --stdout '
    '"https://www.tiktok.com/@___alzahabey4___/live?enter_from_merge=homepage_hot&enter_method=live_entrance_hover_list" best | '
    'ffmpeg -err_detect ignore_err -thread_queue_size 65536 '
    '-fflags +genpts+nobuffer -flags low_delay -i - '
    '-filter_complex "[0:v]scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,fps=30" '
    '-c:v libx264 -preset ultrafast -tune zerolatency '
    '-b:v 3000k -maxrate 3000k -bufsize 6000k -g 30 '
    '-c:a aac -b:a 128k -ar 44100 -ac 2 '
    '-af "aresample=async=1:min_hard_comp=0.10000:first_pts=0" '
    '-fps_mode cfr -f flv "rtmp://a.rtmp.youtube.com/live2/v2m7-ksr7-kq8a-d12v-8hqy"'
)

subprocess.run(cmd, shell=True)