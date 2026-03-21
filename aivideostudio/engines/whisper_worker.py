"""별도 프로세스에서 Whisper 실행 — DLL 충돌 회피"""
import sys
import json
import os

def main():
    audio_path = sys.argv[1]
    language = sys.argv[2] if len(sys.argv) > 2 else "ko"
    model_size = sys.argv[3] if len(sys.argv) > 3 else "base"

    os.environ["CUDA_VISIBLE_DEVICES"] = ""

    import torch
    import whisper

    model = whisper.load_model(model_size, device="cpu")
    result = model.transcribe(audio_path, language=language,
                              word_timestamps=True, verbose=False, fp16=False)

    segments = []
    for seg in result.get("segments", []):
        segments.append({
            "start": round(seg["start"], 2),
            "end": round(seg["end"], 2),
            "text": seg["text"].strip(),
        })

    print(json.dumps(segments, ensure_ascii=False))

if __name__ == "__main__":
    main()