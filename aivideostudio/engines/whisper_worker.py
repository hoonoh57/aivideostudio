"""별도 프로세스에서 Whisper 실행 — GPU 가속 + UTF-8 출력"""
import sys
import json
import os
import io

# stdout을 UTF-8로 강제
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

def main():
    audio_path = sys.argv[1]
    language = sys.argv[2] if len(sys.argv) > 2 else "ko"
    model_size = sys.argv[3] if len(sys.argv) > 3 else "medium"

    import torch
    import whisper

    device = "cuda" if torch.cuda.is_available() else "cpu"
    fp16 = device == "cuda"

    model = whisper.load_model(model_size, device=device)
    result = model.transcribe(audio_path, language=language,
                              word_timestamps=True, verbose=False, fp16=fp16)

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
