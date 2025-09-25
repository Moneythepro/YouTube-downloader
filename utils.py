# utils.py
import datetime

def human_size(bytes_num):
    # convert bytes to human readable
    for unit in ['B','KB','MB','GB','TB']:
        if bytes_num < 1024.0:
            return f"{bytes_num:.2f} {unit}"
        bytes_num /= 1024.0
    return f"{bytes_num:.2f} PB"

def now_str():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")