import asyncio
from pathlib import Path
from loguru import logger

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


class TTSEngine:
    def __init__(self):
        self.default_voice = "ko-KR-SunHiNeural"
        self.default_rate = "+0%"

    async def _generate(self, text, output_path, voice=None, rate=None):
        import edge_tts
        voice = voice or self.default_voice
        rate = rate or self.default_rate
        comm = edge_tts.Communicate(text=text, voice=voice, rate=rate)
        await comm.save(str(output_path))
        logger.info(f"TTS saved: {output_path}")

    def generate(self, text, output_path, voice=None, rate=None):
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
