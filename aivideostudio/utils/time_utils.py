def seconds_to_timecode(seconds, fps=30.0):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    f = int((seconds % 1) * fps)
    return f"{h:02d}:{m:02d}:{s:02d}:{f:02d}"

def timecode_to_seconds(tc, fps=30.0):
    parts = tc.split(":")
    if len(parts) == 4:
        h, m, s, f = map(int, parts)
        return h * 3600 + m * 60 + s + f / fps
    elif len(parts) == 3:
        h, m, s = map(int, parts)
        return h * 3600 + m * 60 + s
    return 0.0

def format_duration(seconds):
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m}:{s:02d}"
