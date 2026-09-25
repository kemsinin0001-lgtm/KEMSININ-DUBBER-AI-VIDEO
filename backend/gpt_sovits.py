import os
import requests
import json
import logging

logger = logging.getLogger("gpt_sovits")

class GPTSovitsEngine:
    """
    Client and fallback connector for GPT-SoVITS voice cloning & zero-shot synthesis.
    Integrates with standard GPT-SoVITS REST API endpoint (typically http://127.0.0.1:9880)
    or custom server endpoint.
    """
    def __init__(self, api_url: str = None):
        self.api_url = api_url or os.getenv("GPT_SOVITS_URL", "http://127.0.0.1:9880")
        self.timeout = 120

    def is_available(self) -> bool:
        try:
            r = requests.get(f"{self.api_url}/", timeout=3)
            return r.status_code in [200, 404, 405]
        except Exception:
            return False

    def set_weights(self, gpt_path: str = "", sovits_path: str = "") -> bool:
        """
        Dynamically swap GPT / SoVITS model weights if API supports it.
        """
        try:
            if gpt_path:
                requests.get(f"{self.api_url}/set_gpt_weights", params={"weights_path": gpt_path}, timeout=10)
            if sovits_path:
                requests.get(f"{self.api_url}/set_sovits_weights", params={"weights_path": sovits_path}, timeout=10)
            return True
        except Exception as e:
            logger.warning(f"Failed to set GPT-SoVITS weights: {e}")
            return False

    def synthesize(self, 
                   text: str, 
                   out_path: str,
                   text_lang: str = "km",
                   ref_audio_path: str = None, 
                   prompt_text: str = None, 
                   prompt_lang: str = "en") -> str:
        """
        Generate audio using GPT-SoVITS API.
        text: target text to speak
        out_path: path to save synthesized audio (.wav / .mp3)
        ref_audio_path: path to 3-10s clean reference voice sample
        prompt_text: text spoken in reference voice sample
        prompt_lang: language of prompt sample (e.g. 'en', 'zh', 'ja', 'auto')
        """
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        
        # Mapping language code to GPT-SoVITS accepted codes
        lang_map = {
            "km": "km",
            "en": "en",
            "zh": "zh",
            "ja": "ja",
            "ko": "ko",
            "auto": "auto"
        }
        sovits_lang = lang_map.get(text_lang.lower().split("-")[0], "auto")
        sovits_prompt_lang = lang_map.get(prompt_lang.lower().split("-")[0], "en")

        payload = {
            "text": text,
            "text_language": sovits_lang,
        }

        # If reference audio is provided for zero-shot cloning
        if ref_audio_path and os.path.exists(ref_audio_path):
            payload["ref_audio_path"] = os.path.abspath(ref_audio_path)
            payload["prompt_text"] = prompt_text or ""
            payload["prompt_language"] = sovits_prompt_lang

        # 1. Try standard JSON POST / endpoint
        endpoint = f"{self.api_url}/tts"
        try:
            resp = requests.post(endpoint, json=payload, timeout=self.timeout)
            if resp.status_code == 200:
                with open(out_path, "wb") as f:
                    f.write(resp.content)
                return out_path
        except Exception as err:
            logger.warning(f"GPT-SoVITS POST /tts failed: {err}")

        # 2. Try GET query fallback (older Fast_API GPT-SoVITS variants)
        try:
            params = {
                "text": text,
                "text_language": sovits_lang
            }
            if ref_audio_path and os.path.exists(ref_audio_path):
                params["refer_wav_path"] = os.path.abspath(ref_audio_path)
                params["prompt_text"] = prompt_text or ""
                params["prompt_language"] = sovits_prompt_lang

            r_get = requests.get(f"{self.api_url}/", params=params, timeout=self.timeout)
            if r_get.status_code == 200:
                with open(out_path, "wb") as f:
                    f.write(r_get.content)
                return out_path
        except Exception as err2:
            logger.warning(f"GPT-SoVITS GET / fallback failed: {err2}")

        raise RuntimeError(f"GPT-SoVITS synthesis failed. Verify service at {self.api_url}")

gpt_sovits_engine = GPTSovitsEngine()
