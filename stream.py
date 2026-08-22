import subprocess

cmd = (
    'streamlink --hls-live-edge 3 --ringbuffer-size 512M --stdout '
    '"https://vt.tiktok.com/ZS9kmFyxTsAu-TicDw/" best | '
    'ffmpeg -err_detect ignore_err -thread_queue_size 65536 '
    '-fflags +genpts+nobuffer -flags low_delay -i - '
    '-filter_complex "[0:v]scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,fps=30" '
    '-c:v libx264 -preset ultrafast -tune zerolatency '
    '-b:v 2500k -maxrate 2500k -bufsize 5000k -g 30 '
    '-c:a aac -b:a 128k -ar 44100 -ac 2 '
    '-af "aresample=async=1:min_hard_comp=0.10000:first_pts=0" '
    '-fps_mode cfr -f flv "rtmp://a.rtmp.youtube.com/live2/6jkd-xtf5-buc2-kc0j-bmhj"'
)

subprocess.run(cmd, shell=True)