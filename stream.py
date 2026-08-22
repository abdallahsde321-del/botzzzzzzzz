import subprocess

cmd = (
    'streamlink --hls-live-edge 2 --ringbuffer-size 256M --stdout '
    '"https://vt.tiktok.com/ZS9kmFyxTsAu-TicDw/" best | '
    'ffmpeg -err_detect ignore_err -thread_queue_size 32768 '
    '-fflags +genpts+nobuffer -flags low_delay -i - '
    '-filter_complex "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=60" '
    '-c:v libx264 -preset veryfast -tune zerolatency '
    '-b:v 4000k -maxrate 4000k -bufsize 8000k -g 60 '
    '-c:a aac -b:a 128k -ar 44100 -ac 2 '
    '-af "aresample=async=1:min_hard_comp=0.10000:first_pts=0" '
    '-fps_mode cfr -f flv "rtmp://a.rtmp.youtube.com/live2/6jkd-xtf5-buc2-kc0j-bmhj"'
)

subprocess.run(cmd, shell=True)