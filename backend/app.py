from fastapi import FastAPI, UploadFile, File, WebSocket, WebSocketDisconnect, BackgroundTasks, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional
import shutil, os, uuid, asyncio
from pathlib import Path

from whisper_engine import transcribe
from translator import translate_srt, translate_text_robust
from tts_engine import generate_voice
from video_processor import merge_audio_video
from ws_manager import manager
from gpt_sovits import gpt_sovits_engine

app = FastAPI(title="KEMSININ DUBBER API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

UPLOAD_DIR = "uploads"
TEMP_DIR = "temp"
OUTPUT_DIR = "output"

for d in [UPLOAD_DIR, TEMP_DIR, OUTPUT_DIR]:
    os.makedirs(d, exist_ok=True)

app.mount("/output", StaticFiles(directory=OUTPUT_DIR), name="output")
app.mount("/temp", StaticFiles(directory=TEMP_DIR), name="temp")
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

@app.get("/")
def read_root():
    for p in [Path("ui/index.html"), Path("index.html"), Path("../ui/index.html"), Path("../index.html")]:
        if p.exists() and p.stat().st_size > 0:
            return FileResponse(str(p.resolve()))
    return {"message": "KEMSININ DUBBER API is live with WebSocket support! 🎬"}

# ---------- Models ----------
class DubRequest(BaseModel):
    video: str
    src_lang: str = "auto"
    tgt_lang: str = "km"
    voice: str = "female"
    ref_audio: Optional[str] = None
    prompt_text: Optional[str] = None

class MultiDubRequest(BaseModel):
    video: str
    src_lang: str = "auto"
    tgt_langs: List[str] = ["km"]
    voice: str = "female"
    ref_audio: Optional[str] = None
    prompt_text: Optional[str] = None


class SegmentUpdate(BaseModel):
    id: int
    orig: Optional[str] = None
    kh: str
    start: Optional[float] = None
    end: Optional[float] = None
    t0: Optional[str] = None
    t1: Optional[str] = None
    voice: Optional[str] = "female"

class BatchDubRequest(BaseModel):
    video: str
    segments: List[SegmentUpdate]
    tgt_lang: str = "km"
    voice: str = "female"

class TTSRequest(BaseModel):
    text: str
    voice: str = "female"
    lang: str = "km"
    ref_audio: Optional[str] = None
    prompt_text: Optional[str] = None

class TranslateRequest(BaseModel):
    text: str
    src_lang: str = "auto"
    tgt_lang: str = "km"


class BatchJobRequest(BaseModel):
    video: str
    src_lang: str = "auto"
    target_langs: List[str] = ["km"]
    voice_gender: str = "female"

batch_jobs: Dict[str, Dict[str, Any]] = {}

# ---------- WebSocket Route ----------
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    await manager.send_status("connected", "Connected to KEMSININ DUBBER Real-time Engine")
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except (WebSocketDisconnect, Exception):
        manager.disconnect(websocket)

@app.websocket("/ws/{job_id}")
async def websocket_job_endpoint(websocket: WebSocket, job_id: str):
    await manager.connect_job(websocket, job_id)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except (WebSocketDisconnect, Exception):
        manager.disconnect_job(websocket, job_id)


# ---------- Language Dictionary & File Download ----------
@app.get("/languages")
def get_languages():
    return {
        "km": {"name": "ខ្មែរ", "flag": "🇰🇭"},
        "en": {"name": "English", "flag": "🇺🇸"},
        "zh": {"name": "中文", "flag": "🇨🇳"},
        "th": {"name": "ไทย", "flag": "🇹🇭"},
        "vi": {"name": "Tiếng Việt", "flag": "🇻🇳"},
        "ja": {"name": "日本語", "flag": "🇯🇵"},
        "ko": {"name": "한국어", "flag": "🇰🇷"},
        "fr": {"name": "Français", "flag": "🇫🇷"},
        "es": {"name": "Español", "flag": "🇪🇸"},
        "de": {"name": "Deutsch", "flag": "🇩🇪"},
        "id": {"name": "Indonesia", "flag": "🇮🇩"},
        "hi": {"name": "हिन्दी", "flag": "🇮🇳"}
    }

@app.get("/file")
def serve_file(p: str):
    """Serve dubbed output file"""
    target = p
    if not os.path.exists(target):
        # Fallback to output or temp directory lookup
        for parent_dir in [OUTPUT_DIR, TEMP_DIR, UPLOAD_DIR]:
            candidate = os.path.join(parent_dir, os.path.basename(p))
            if os.path.exists(candidate):
                target = candidate
                break
    if not os.path.exists(target):
        raise HTTPException(404, f"File not found: {p}")
    return FileResponse(os.path.abspath(target), media_type="video/mp4", filename=os.path.basename(target))


async def process_batch_job(job_id: str, req: BatchJobRequest):
    job_info = batch_jobs.get(job_id)
    if not job_info:
        return

    try:
        total_langs = len(req.target_langs)
        
        # 1. Whisper Stage
        await manager.broadcast_job(job_id, {
            "step": "stt",
            "percent": 10,
            "message": "កំពុងដំណើរការ Whisper ទាញយកសំឡេង..."
        })

        base_segments = transcribe(req.video, lang=req.src_lang)
        if not base_segments or job_info.get("canceled"):
            if not base_segments:
                await manager.broadcast_job(job_id, {"step": "error", "message": "មិនមានសំឡេងនិយាយនៅក្នុងវីដេអូទេ"})
            return

        await manager.broadcast_job(job_id, {
            "step": "stt_done",
            "percent": 25,
            "message": f"Whisper រួចរាល់ ({len(base_segments)} segments)"
        })

        # 2. Iterate each language
        results = {}
        for idx, lang in enumerate(req.target_langs, 1):
            if job_info.get("canceled"):
                break

            base_pct = 25 + int(((idx - 1) / total_langs) * 70)
            span_pct = int(70 / total_langs)

            # Translation step
            await manager.broadcast_job(job_id, {
                "step": f"lang:{lang}",
                "lang": lang,
                "percent": base_pct + int(span_pct * 0.15),
                "message": f"កំពុងបកប្រែជាភាសា {lang}..."
            })

            lang_segs = [
                {
                    "id": s["id"], "orig": s["orig"], "kh": s["orig"],
                    "start": s.get("start", 0.0), "end": s.get("end", 0.0),
                    "t0": s["t0"], "t1": s["t1"]
                }
                for s in base_segments
            ]
            lang_segs = translate_srt(lang_segs, target=lang)

            # TTS step
            await manager.broadcast_job(job_id, {
                "step": f"lang:{lang}",
                "lang": lang,
                "percent": base_pct + int(span_pct * 0.5),
                "message": f"កំពុងបញ្ចេញសំឡេង TTS ({lang})..."
            })

            for s in lang_segs:
                audio_out = f"{TEMP_DIR}/batch_{job_id}_{lang}_{s['id']}.mp3"
                s["audio"] = generate_voice(
                    text=s["kh"],
                    voice=req.voice_gender,
                    lang=lang,
                    out=audio_out
                )

            # Mux step
            await manager.broadcast_job(job_id, {
                "step": f"lang:{lang}",
                "lang": lang,
                "percent": base_pct + int(span_pct * 0.85),
                "message": f"កំពុងបញ្ចូលសំឡេងជាមួយវីដេអូ..."
            })

            out_filename = f"kemsinin_{lang}_{uuid.uuid4().hex[:6]}.mp4"
            out_path = f"{OUTPUT_DIR}/{out_filename}"
            merged_file = merge_audio_video(
                video_path=req.video,
                segments=lang_segs,
                out_path=out_path
            )

            # Finished this language!
            results[lang] = merged_file
            await manager.broadcast_job(job_id, {
                "step": f"lang:{lang}",
                "lang": lang,
                "percent": 100,
                "done": True,
                "path": merged_file,
                "video_url": f"/output/{out_filename}",
                "message": "✅ បំពងបានជោគជ័យ"
            })

        if not job_info.get("canceled"):
            await manager.broadcast_job(job_id, {
                "step": "done",
                "percent": 100,
                "message": "🎉 បំពងគ្រប់ភាសារួចរាល់!",
                "results": results
            })
    except Exception as err:
        print(f"[!] Batch job {job_id} error: {err}")
        await manager.broadcast_job(job_id, {
            "step": "error",
            "message": str(err)
        })


@app.post("/batch/start")
async def start_batch_job(req: BatchJobRequest, background_tasks: BackgroundTasks):
    job_id = f"job_{uuid.uuid4().hex[:8]}"
    batch_jobs[job_id] = {
        "job_id": job_id,
        "video": req.video,
        "target_langs": req.target_langs,
        "voice_gender": req.voice_gender,
        "canceled": False
    }
    background_tasks.add_task(process_batch_job, job_id, req)
    return {"job_id": job_id, "status": "started"}


@app.post("/batch/cancel/{job_id}")
async def cancel_batch_job(job_id: str):
    if job_id in batch_jobs:
        batch_jobs[job_id]["canceled"] = True
        await manager.broadcast_job(job_id, {
            "step": "error",
            "message": "⏹ ការបំពងត្រូវបានបញ្ឈប់ដោយអ្នកប្រើប្រាស់"
        })
        return {"status": "canceled", "job_id": job_id}
    return JSONResponse(status_code=404, content={"detail": "Job not found"})



# ---------- HTTP Routes ----------
@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    ext = os.path.splitext(file.filename)[1]
    safe_name = f"{uuid.uuid4().hex}{ext}"
    path = f"{UPLOAD_DIR}/{safe_name}"
    with open(path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    
    await manager.send_status("uploaded", f"File {file.filename} uploaded successfully", {"path": path})
    return {"path": path, "filename": file.filename}


@app.post("/translate")
async def translate_single(req: TranslateRequest):
    translated = translate_text_robust(req.text, target=req.tgt_lang)
    return {"original": req.text, "translated": translated}


@app.post("/transcribe")
async def transcribe_only(video: str, lang: str = "auto"):
    """
    Transcribes video and translates text without rendering video.
    Ideal for Editor timeline mode!
    """
    await manager.send_progress("whisper", 10.0, "Extracting audio and recognizing speech...")
    segments = transcribe(video, lang=lang)
    
    await manager.send_progress("translate", 50.0, f"Translating {len(segments)} dialogue segments...")
    segments = translate_srt(segments, target="km")
    
    await manager.send_progress("ready", 100.0, "Transcription & translation complete")
    return {"segments": segments}


@app.post("/dub")
async def dub(req: DubRequest):
    """
    Full Automatic Dubbing Pipeline with WebSocket Real-time Status updates
    Flow: Whisper (15%) → Translate (40%) → TTS (70%) → FFmpeg Mux (95%) → Done (100%)
    """
    try:
        # 1) Speech to text (Whisper)
        await manager.send_progress("whisper", 15.0, "Transcribing speech from video via Whisper...")
        segments = transcribe(req.video, lang=req.src_lang)
        if not segments:
            await manager.send_error("No audible speech detected in video", "whisper")
            return JSONResponse(status_code=400, content={"detail": "No speech detected"})

        # 2) Translate each segment
        await manager.send_progress("translate", 40.0, f"Translating {len(segments)} segments to {req.tgt_lang}...")
        segments = translate_srt(segments, target=req.tgt_lang)

        # 3) TTS each segment
        total = len(segments)
        for idx, seg in enumerate(segments, 1):
            pct = 40.0 + (idx / total) * 35.0
            await manager.send_progress("tts", pct, f"Generating AI speech {idx}/{total}...")
            
            # Check for GPT-SoVITS or Neural TTS
            audio_out = f"{TEMP_DIR}/seg_{seg['id']}_{uuid.uuid4().hex[:6]}.mp3"
            if req.voice.lower().startswith("gpt_sovits") and gpt_sovits_engine.is_available():
                try:
                    seg["audio"] = gpt_sovits_engine.synthesize(
                        text=seg["kh"],
                        out_path=audio_out,
                        text_lang=req.tgt_lang,
                        ref_audio_path=req.ref_audio,
                        prompt_text=req.prompt_text
                    )
                except Exception:
                    seg["audio"] = generate_voice(
                        text=seg["kh"], voice="female", lang=req.tgt_lang, out=audio_out
                    )
            else:
                seg["audio"] = generate_voice(
                    text=seg["kh"], voice=req.voice, lang=req.tgt_lang, out=audio_out
                )

        # 4) Merge all audio + mux into video
        await manager.send_progress("ffmpeg", 85.0, "Synchronizing timeline and muxing audio with video...")
        out_filename = f"dubbed_{uuid.uuid4().hex}.mp4"
        output = merge_audio_video(
            video_path=req.video,
            segments=segments,
            out_path=f"{OUTPUT_DIR}/{out_filename}"
        )

        await manager.send_progress("complete", 100.0, "Video dubbing rendered successfully!", {"output": output})

        return {
            "subtitles": [
                {
                    "id": s["id"],
                    "orig": s["orig"],
                    "kh": s["kh"],
                    "start": s.get("start", 0.0),
                    "end": s.get("end", 0.0),
                    "t0": s["t0"],
                    "t1": s["t1"],
                    "voice": req.voice
                }
                for s in segments
            ],
            "output": output
        }
    except Exception as e:
        await manager.send_error(str(e), "pipeline")
        return JSONResponse(status_code=500, content={"detail": str(e)})


@app.post("/dub_multi")
async def dub_multi(req: MultiDubRequest):
    """
    High-Performance Multi-Language Dubbing:
    1. Whisper Transcribes Source Audio ONCE (10% - 30%)
    2. Fan-out to multiple target languages in sequence:
       - Translate SRT segments to target language
       - TTS voice synthesis per segment
       - FFmpeg timeline sync & merge
    3. Returns list of all generated dubbed video paths!
    """
    try:
        tgt_langs = req.tgt_langs or ["km"]
        total_langs = len(tgt_langs)

        # 1) Speech to text (Whisper ONCE)
        await manager.send_progress("whisper", 15.0, f"Running Whisper once on {os.path.basename(req.video)}...")
        base_segments = transcribe(req.video, lang=req.src_lang)
        if not base_segments:
            await manager.send_error("No audible speech detected in video", "whisper")
            return JSONResponse(status_code=400, content={"detail": "No speech detected"})

        await manager.send_progress("whisper", 30.0, f"Whisper extracted {len(base_segments)} speech segments! Processing {total_langs} languages...")

        results = {}
        for l_idx, tgt_lang in enumerate(tgt_langs, 1):
            lang_progress_base = 30.0 + ((l_idx - 1) / total_langs) * 65.0
            lang_progress_span = 65.0 / total_langs

            # Copy base segments for this language
            lang_segments = [
                {
                    "id": s["id"],
                    "orig": s["orig"],
                    "kh": s["orig"],
                    "start": s.get("start", 0.0),
                    "end": s.get("end", 0.0),
                    "t0": s["t0"],
                    "t1": s["t1"],
                }
                for s in base_segments
            ]

            # 2) Translate for this language
            await manager.send_progress(
                "translate",
                lang_progress_base + 0.1 * lang_progress_span,
                f"[{l_idx}/{total_langs}] Translating dialogue to '{tgt_lang}'..."
            )
            lang_segments = translate_srt(lang_segments, target=tgt_lang)

            # 3) TTS synthesis for this language
            seg_count = len(lang_segments)
            for s_idx, seg in enumerate(lang_segments, 1):
                tts_progress = lang_progress_base + (0.1 + (s_idx / seg_count) * 0.6) * lang_progress_span
                await manager.send_progress(
                    "tts",
                    tts_progress,
                    f"[{l_idx}/{total_langs}] TTS ({tgt_lang}): line {s_idx}/{seg_count}..."
                )

                audio_out = f"{TEMP_DIR}/multi_{tgt_lang}_seg_{seg['id']}_{uuid.uuid4().hex[:6]}.mp3"
                if req.voice.lower().startswith("gpt_sovits") and gpt_sovits_engine.is_available():
                    try:
                        seg["audio"] = gpt_sovits_engine.synthesize(
                            text=seg["kh"],
                            out_path=audio_out,
                            text_lang=tgt_lang,
                            ref_audio_path=req.ref_audio,
                            prompt_text=req.prompt_text
                        )
                    except Exception:
                        seg["audio"] = generate_voice(
                            text=seg["kh"], voice="female", lang=tgt_lang, out=audio_out
                        )
                else:
                    seg["audio"] = generate_voice(
                        text=seg["kh"], voice=req.voice, lang=tgt_lang, out=audio_out
                    )

            # 4) FFmpeg merge for this language
            await manager.send_progress(
                "ffmpeg",
                lang_progress_base + 0.85 * lang_progress_span,
                f"[{l_idx}/{total_langs}] Muxing dubbed video for '{tgt_lang}'..."
            )
            out_filename = f"dubbed_{tgt_lang}_{uuid.uuid4().hex[:8]}.mp4"
            out_path = f"{OUTPUT_DIR}/{out_filename}"
            merged_file = merge_audio_video(
                video_path=req.video,
                segments=lang_segments,
                out_path=out_path
            )

            results[tgt_lang] = {
                "language": tgt_lang,
                "video_url": f"/output/{out_filename}",
                "file_path": merged_file,
                "subtitles": lang_segments
            }

        await manager.send_progress("complete", 100.0, f"All {total_langs} dubbed versions rendered successfully!", {"results": results})

        return {
            "status": "success",
            "source_video": req.video,
            "total_segments": len(base_segments),
            "languages": results
        }
    except Exception as e:
        await manager.send_error(str(e), "pipeline")
        return JSONResponse(status_code=500, content={"detail": str(e)})



@app.post("/dub_custom_segments")
async def dub_custom_segments(req: BatchDubRequest):
    """
    Render video after user finishes editing subtitles/timing in UI editor!
    """
    try:
        total = len(req.segments)
        await manager.send_progress("tts", 20.0, f"Synthesizing edited voice lines (0/{total})...")
        
        segments_for_merge = []
        for idx, seg in enumerate(req.segments, 1):
            pct = 20.0 + (idx / total) * 50.0
            await manager.send_progress("tts", pct, f"Synthesizing line {idx}/{total}...")
            
            audio_out = f"{TEMP_DIR}/edited_{seg.id}_{uuid.uuid4().hex[:6]}.mp3"
            audio_path = generate_voice(
                text=seg.kh,
                voice=seg.voice or req.voice,
                lang=req.tgt_lang,
                out=audio_out
            )
            segments_for_merge.append({
                "id": seg.id,
                "orig": seg.orig or "",
                "kh": seg.kh,
                "start": seg.start,
                "end": seg.end,
                "audio": audio_path
            })

        await manager.send_progress("ffmpeg", 80.0, "Muxing edited segments into high-quality video...")
        out_filename = f"edited_dubbed_{uuid.uuid4().hex}.mp4"
        output = merge_audio_video(
            video_path=req.video,
            segments=segments_for_merge,
            out_path=f"{OUTPUT_DIR}/{out_filename}"
        )

        await manager.send_progress("complete", 100.0, "Custom edited dub rendered successfully!", {"output": output})
        return {"output": output, "status": "success"}
    except Exception as e:
        await manager.send_error(str(e), "editor_pipeline")
        return JSONResponse(status_code=500, content={"detail": str(e)})


@app.post("/tts")
async def tts(req: TTSRequest):
    """Quick single-line TTS for previewing in subtitle editor"""
    out_file = f"{TEMP_DIR}/preview_{uuid.uuid4().hex}.mp3"
    
    if req.voice.lower().startswith("gpt_sovits") and gpt_sovits_engine.is_available():
        try:
            path = gpt_sovits_engine.synthesize(
                text=req.text,
                out_path=out_file,
                text_lang=req.lang,
                ref_audio_path=req.ref_audio,
                prompt_text=req.prompt_text
            )
            return FileResponse(path, media_type="audio/mpeg")
        except Exception:
            pass

    path = generate_voice(
        text=req.text, voice=req.voice, lang=req.lang, out=out_file
    )
    return FileResponse(path, media_type="audio/mpeg")


@app.get("/gpt_sovits/status")
async def gpt_sovits_status():
    available = gpt_sovits_engine.is_available()
    return {
        "available": available,
        "api_url": gpt_sovits_engine.api_url,
        "message": "GPT-SoVITS Engine connected" if available else "GPT-SoVITS local server not running"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
