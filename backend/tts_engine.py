import edge_tts, asyncio, os, concurrent.futures

# Microsoft Edge voices — FREE & have Khmer support
# Note: In Microsoft Azure/Edge catalog:
# km-KH-SreymomNeural is female, km-KH-PisethNeural is male
VOICES = {
    "female": {
        "km": "km-KH-SreymomNeural",   # Khmer - female
        "en": "en-US-AriaNeural",      # English - female
        "zh": "zh-CN-XiaoxiaoNeural",  # Chinese - female
        "th": "th-TH-PremwadeeNeural", # Thai - female
        "vi": "vi-VN-HoaiMyNeural",    # Vietnamese - female
        "ja": "ja-JP-NanamiNeural",    # Japanese - female
        "ko": "ko-KR-SunHiNeural",     # Korean - female
        "fr": "fr-FR-DeniseNeural",    # French - female
        "es": "es-ES-ElviraNeural",    # Spanish - female
        "de": "de-DE-KatjaNeural",     # German - female
        "id": "id-ID-GadisNeural",     # Indonesian - female
    },
    "male": {
        "km": "km-KH-PisethNeural",   # Khmer - male
        "en": "en-US-GuyNeural",      # English - male
        "zh": "zh-CN-YunxiNeural",    # Chinese - male
        "th": "th-TH-NiwatNeural",    # Thai - male
        "vi": "vi-VN-NamMinhNeural",  # Vietnamese - male
        "ja": "ja-JP-KeitaNeural",    # Japanese - male
        "ko": "ko-KR-InJoonNeural",   # Korean - male
        "fr": "fr-FR-HenriNeural",    # French - male
        "es": "es-ES-AlvaroNeural",   # Spanish - male
        "de": "de-DE-ConradNeural",   # German - male
        "id": "id-ID-ArdiNeural",     # Indonesian - male
    }
}

def generate_voice(text: str, voice: str, lang: str, out: str):
    if not text or not text.strip():
        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
        with open(out, "wb") as f:
            f.write(b"")
        return out

    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    lang_key = lang.split("-")[0]
    
    # Map voice string if needed
    v_type = "female" if "female" in voice.lower() else "male"
    v = VOICES.get(v_type, {}).get(lang_key) \
        or VOICES["female"].get("en", "en-US-AriaNeural")

    # Check if voice request is for GPT-SoVITS
    if voice.lower().startswith("gpt_sovits") or voice.lower() == "clone":
        try:
            from gpt_sovits import gpt_sovits_engine
            if gpt_sovits_engine.is_available():
                return gpt_sovits_engine.synthesize(text=text, out_path=out, text_lang=lang)
            else:
                print("[*] GPT-SoVITS server unavailable, falling back to neural TTS")
        except Exception as e:
            print(f"[*] GPT-SoVITS error ({e}), falling back to neural TTS")

    # Safe asyncio execution when invoked inside or outside FastAPI's running event loop
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor() as executor:
            executor.submit(lambda: asyncio.run(_synth(text, v, out))).result()
    else:
        asyncio.run(_synth(text, v, out))

    return out


async def _synth(text: str, voice: str, out: str):
    comm = edge_tts.Communicate(text=text, voice=voice, rate="+0%")
    await comm.save(out)
