import asyncio
import json
import os
import struct
import tempfile
from pathlib import Path
from io import BytesIO
from loguru import logger

import requests


# ─── Edge-TTS voices ───
KO_VOICES = {
    "SunHi (Female)": "ko-KR-SunHiNeural",
    "InJoon (Male)": "ko-KR-InJoonNeural",
    "HyunSu (Male)": "ko-KR-HyunsuNeural",
}
EN_VOICES = {
    "Jenny (Female)": "en-US-JennyNeural",
    "Guy (Male)": "en-US-GuyNeural",
}
JA_VOICES = {
    "Nanami (Female)": "ja-JP-NanamiNeural",
    "Keita (Male)": "ja-JP-KeitaNeural",
}


class EdgeTTSEngine:
    """Microsoft Edge TTS (free, cloud-based)."""
    name = "Edge-TTS"

    def __init__(self):
        self.default_voice = "ko-KR-SunHiNeural"
        self.default_rate = "+0%"

    async def _generate(self, text, output_path, voice=None, rate=None, **kw):
        import edge_tts
        voice = voice or self.default_voice
        rate = rate or self.default_rate
        comm = edge_tts.Communicate(text=text, voice=voice, rate=rate)
        await comm.save(str(output_path))
        logger.info(f"[Edge-TTS] saved: {output_path}")

    def generate(self, text, output_path, voice=None, rate=None, **kw):
        asyncio.run(self._generate(text, output_path, voice, rate))
        return str(output_path)

    def get_voices(self, lang="ko"):
        if lang == "ko":
            return KO_VOICES
        elif lang == "en":
            return EN_VOICES
        elif lang == "ja":
            return JA_VOICES
        return {**KO_VOICES, **EN_VOICES, **JA_VOICES}

    def is_available(self):
        try:
            import edge_tts
            return True
        except ImportError:
            return False


class SoVITSEngine:
    """GPT-SoVITS API client (local HTTP server)."""
    name = "GPT-SoVITS"

    def __init__(self, api_url="http://127.0.0.1:9880",
                 ref_audio="D:/GPT-SoVITS/ref_audio.wav",
                 ref_text="",
                 ref_lang="ko"):
        self.api_url = api_url.rstrip("/")
        self.ref_audio = ref_audio
        self.ref_text = ref_text
        self.ref_lang = ref_lang

    def generate(self, text, output_path, voice=None, rate=None,
                 text_lang="ko", ref_audio=None, ref_text=None,
                 ref_lang=None, speed=1.0, **kw):
        ref_audio = ref_audio or self.ref_audio
        ref_text = ref_text or self.ref_text
        ref_lang = ref_lang or self.ref_lang

        payload = {
            "text": text,
            "text_lang": text_lang,
            "ref_audio_path": ref_audio,
            "prompt_text": ref_text,
            "prompt_lang": ref_lang,
            "text_split_method": "cut5",
            "batch_size": 1,
            "speed_factor": speed,
            "media_type": "wav",
            "streaming_mode": False,
            "parallel_infer": True,
            "repetition_penalty": 1.35,
            "sample_steps": 32,
            "super_sampling": False,
        }

        logger.info(f"[SoVITS] POST {self.api_url}/tts text={text[:30]}...")
        try:
            resp = requests.post(f"{self.api_url}/tts", json=payload, timeout=120)
        except requests.ConnectionError:
            raise ConnectionError(
                "GPT-SoVITS server not running! Start it first:\n"
                "  cd /d D:\\GPT-SoVITS\n"
                "  .\\runtime\\python api_v2.py -a 127.0.0.1 -p 9880"
            )

        if resp.status_code != 200:
            error_msg = resp.text[:300]
            logger.error(f"[SoVITS] API error {resp.status_code}: {error_msg}")
            raise RuntimeError(f"GPT-SoVITS error {resp.status_code}: {error_msg}")

        # Save WAV
        out = str(output_path)
        if not out.lower().endswith(".wav"):
            out = str(Path(output_path).with_suffix(".wav"))

        with open(out, "wb") as f:
            f.write(resp.content)

        logger.info(f"[SoVITS] saved: {out} ({len(resp.content)} bytes)")
        return out

    def get_voices(self, lang="ko"):
        return {"GPT-SoVITS (Clone)": "sovits_clone"}

    def is_available(self):
        try:
            resp = requests.get(f"{self.api_url}/tts", timeout=3)
            return True
        except Exception:
            return False

    def set_ref_audio(self, path, text="", lang="ko"):
        self.ref_audio = path
        self.ref_text = text
        self.ref_lang = lang
        logger.info(f"[SoVITS] ref_audio set: {path}")


class TTSEngine:
    """Unified TTS engine manager — wraps Edge-TTS and GPT-SoVITS."""

    def __init__(self):
        self.edge = EdgeTTSEngine()
        self.sovits = SoVITSEngine()
        self._active = self.edge  # default

    @property
    def active_engine(self):
        return self._active

    def set_engine(self, name):
        if name == "GPT-SoVITS":
            self._active = self.sovits
        else:
            self._active = self.edge
        logger.info(f"[TTS] active engine: {self._active.name}")

    def generate(self, text, output_path, **kw):
        return self._active.generate(text, output_path, **kw)

    def get_voices(self, lang="ko"):
        return self._active.get_voices(lang)

    # backward compat
    @property
    def default_voice(self):
        return getattr(self._active, "default_voice", "")

    @property
    def default_rate(self):
        return getattr(self._active, "default_rate", "+0%")
