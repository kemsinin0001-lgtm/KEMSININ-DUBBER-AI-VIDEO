import whisper
import os

# Load once (large-v3 = best quality, medium = faster)
_model = None
def get_model():
    global _model
    if _model is None:
        _model = whisper.load_model("medium")  # change to "large-v3" for best
    return _model


def transcribe(video_path: str, lang: str = "auto"):
    model = get_model()
    result = model.transcribe(
        video_path,
        language=None if lang == "auto" else lang,
        task="transcribe",
        verbose=False
    )

    segments = []
    for i, s in enumerate(result["segments"], 1):
        segments.append({
            "id": i,
            "orig": s["text"].strip(),
            "kh": "",  # to be filled by translator
            "start": s["start"],
            "end": s["end"],
            "t0": sec_to_ts(s["start"]),
            "t1": sec_to_ts(s["end"]),
        })
    return segments


def sec_to_ts(sec: float) -> str:
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"
