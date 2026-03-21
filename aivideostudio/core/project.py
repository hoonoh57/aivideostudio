import json
import time
from pathlib import Path
from dataclasses import dataclass, field
from loguru import logger


@dataclass
class Asset:
    path: str
    name: str = ""
    duration: float = 0.0
    width: int = 0
    height: int = 0
    fps: float = 0.0
    video_codec: str = ""
    audio_codec: str = ""
    file_size: int = 0
    has_video: bool = True
    has_audio: bool = True
    thumbnail_path: str = ""

    def __post_init__(self):
        if not self.name:
            self.name = Path(self.path).name


@dataclass
class Clip:
    asset_path: str
    track_index: int = 0
    timeline_start: float = 0.0
    source_in: float = 0.0
    source_out: float = 0.0
    name: str = ""

    @property
    def duration(self):
        return self.source_out - self.source_in

    def to_dict(self):
        return {
            "asset_path": self.asset_path,
            "track_index": self.track_index,
            "timeline_start": self.timeline_start,
            "source_in": self.source_in,
            "source_out": self.source_out,
            "name": self.name,
        }

    @classmethod
    def from_dict(cls, d):
        return cls(**d)


@dataclass
class Project:
    name: str = "Untitled"
    path: str = ""
    width: int = 1920
    height: int = 1080
    fps: float = 30.0
    assets: list = field(default_factory=list)
    clips: list = field(default_factory=list)
    created_at: str = ""
    modified_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = time.strftime("%Y-%m-%d %H:%M:%S")

    def add_asset(self, asset):
        for a in self.assets:
            if a.path == asset.path:
                logger.info(f"Asset already exists: {asset.name}")
                return a
        self.assets.append(asset)
        logger.info(f"Asset added: {asset.name}")
        return asset

    def remove_asset(self, path):
        self.assets = [a for a in self.assets if a.path != path]

    def add_clip(self, clip):
        self.clips.append(clip)
        logger.info(f"Clip added: {clip.name} at {clip.timeline_start}")
        return clip

    def remove_clip(self, clip):
        if clip in self.clips:
            self.clips.remove(clip)

    def save(self, path=None):
        if path:
            self.path = path
        if not self.path:
            return False
        self.modified_at = time.strftime("%Y-%m-%d %H:%M:%S")
        data = {
            "name": self.name,
            "width": self.width,
            "height": self.height,
            "fps": self.fps,
            "created_at": self.created_at,
            "modified_at": self.modified_at,
            "assets": [
                {"path": a.path, "name": a.name, "duration": a.duration,
                 "width": a.width, "height": a.height, "fps": a.fps}
                for a in self.assets
            ],
            "clips": [c.to_dict() for c in self.clips],
        }
        Path(self.path).write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        logger.info(f"Project saved: {self.path}")
        return True

    @classmethod
    def load(cls, path):
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        proj = cls(
            name=data.get("name", "Untitled"),
            path=path,
            width=data.get("width", 1920),
            height=data.get("height", 1080),
            fps=data.get("fps", 30.0),
            created_at=data.get("created_at", ""),
            modified_at=data.get("modified_at", ""),
        )
        for ad in data.get("assets", []):
            proj.assets.append(Asset(**ad))
        for cd in data.get("clips", []):
            proj.clips.append(Clip.from_dict(cd))
        logger.info(f"Project loaded: {path}")
        return proj
