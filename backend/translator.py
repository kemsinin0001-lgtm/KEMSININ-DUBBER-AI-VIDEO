import sys
from typing import List, Dict, Any
from deep_translator import GoogleTranslator, MyMemoryTranslator

def translate_text_robust(text: str, target: str = "km") -> str:
    """
    Translates text with fallback hierarchy: Google -> MyMemory -> original.
    Prevents 429 rate limit errors from crashing the dubbing pipeline.
    """
    if not text or not text.strip():
        return ""

    target_code = target if target else "km"

    # 1. Try Google Translator
    try:
        translated = GoogleTranslator(source="auto", target=target_code).translate(text)
        if translated and translated.strip():
            return translated
    except Exception as e:
        print(f"[*] Google translate error: {e}")

    # 2. Try MyMemory Translator
    try:
        src = "en-US"
        tgt = f"{target_code}-KH" if target_code == "km" else target_code
        translated = MyMemoryTranslator(source=src, target=tgt).translate(text)
        if translated and translated.strip():
            return translated
    except Exception as err:
        print(f"[*] MyMemory error: {err}")

    return text

def translate_srt(segments: List[Dict[str, Any]], target: str = "km") -> List[Dict[str, Any]]:
    """
    Translates segments and populates the 'kh' key for each segment.
    """
    if not segments:
        return []

    for seg in segments:
        orig = seg.get("orig", "").strip()
        if orig:
            seg["kh"] = translate_text_robust(orig, target=target)
        else:
            seg["kh"] = ""

    return segments
