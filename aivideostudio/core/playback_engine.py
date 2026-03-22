"""Timeline Playback Engine - central authority for timeline playback."""
import time as _time
from loguru import logger


class TimelinePlaybackEngine:
    """Resolves timeline time -> source file + source time.
    
    All clip-finding logic lives here. PreviewPanel only displays frames.
    Supports multi-track with priority (higher track index = on top).
    """

    def __init__(self):
        self._tracks = []  # list of {"name", "type", "clips": [dict]}
        self._playhead = 0.0
        self._playing = False
        self._play_start_real = 0.0
        self._play_start_tl = 0.0
        self._on_frame_cb = None  # callback: (video_info, audio_infos, timeline_pos)
        self._on_end_cb = None
        self._total_duration = 0.0

    def set_tracks(self, tracks_data):
        """tracks_data: list of {"name", "type", "clips": [clip_dict]}
        clip_dict: {path, timeline_start, duration, in_point, out_point, name}
        """
        self._tracks = tracks_data
        self._update_duration()

    def _update_duration(self):
        max_end = 0.0
        for track in self._tracks:
            for clip in track.get("clips", []):
                end = clip.get("timeline_start", 0) + clip.get("duration", 0)
                if end > max_end:
                    max_end = end
        self._total_duration = max_end

    @property
    def total_duration(self):
        return self._total_duration

    @property
    def playhead(self):
        return self._playhead

    @playhead.setter
    def playhead(self, t):
        self._playhead = max(0.0, min(t, self._total_duration))

    def query(self, t):
        """Query what should be displayed at timeline time t.
        
        Returns:
            {
                "video": {"path": str, "source_time": float, "clip": dict} or None,
                "audio": [{"path": str, "source_time": float, "clip": dict}, ...],
                "timeline_pos": float,
                "is_gap": bool,
            }
        """
        result = {
            "video": None,
            "audio": [],
            "timeline_pos": t,
            "is_gap": True,
        }

        for track in self._tracks:
            track_type = track.get("type", "video")
            for clip in track.get("clips", []):
                cs = clip.get("timeline_start", 0)
                ce = cs + clip.get("duration", 0)
                if cs <= t < ce:
                    offset = t - cs
                    source_time = clip.get("in_point", 0) + offset
                    info = {
                        "path": clip.get("path", ""),
                        "source_time": source_time,
                        "clip": clip,
                    }
                    if track_type == "video":
                        # Higher track overwrites (last found wins)
                        result["video"] = info
                        result["is_gap"] = False
                    elif track_type == "audio":
                        result["audio"].append(info)
                        result["is_gap"] = False

        return result

    def find_next_video_time(self, after_t):
        """Find the start time of the next video clip after time t."""
        best = None
        for track in self._tracks:
            if track.get("type") != "video":
                continue
            for clip in track.get("clips", []):
                cs = clip.get("timeline_start", 0)
                if cs > after_t + 0.01:
                    if best is None or cs < best:
                        best = cs
        return best

    def get_ordered_video_segments(self):
        """Return all video segments sorted by timeline_start.
        Each segment: (timeline_start, timeline_end, path, in_point, out_point)
        """
        segments = []
        for track in self._tracks:
            if track.get("type") != "video":
                continue
            for clip in track.get("clips", []):
                cs = clip.get("timeline_start", 0)
                dur = clip.get("duration", 0)
                segments.append({
                    "timeline_start": cs,
                    "timeline_end": cs + dur,
                    "path": clip.get("path", ""),
                    "in_point": clip.get("in_point", 0),
                    "out_point": clip.get("out_point", clip.get("in_point", 0) + dur),
                })
        segments.sort(key=lambda s: s["timeline_start"])
        return segments
