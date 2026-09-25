import subprocess, os, shutil
import imageio_ffmpeg

def get_ffmpeg_binary() -> str:
    """Finds system ffmpeg or bundled imageio-ffmpeg executable."""
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg
    try:
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"

def merge_audio_video(video_path, segments, out_path):
    """
    1. Place each TTS segment at its timestamp using adelay
    2. Mix together as one audio track
    3. Mux with original video
    """
    os.makedirs("temp", exist_ok=True)
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)

    ffmpeg_bin = get_ffmpeg_binary()

    # Filter out empty or missing audio segments
    valid_segments = [s for s in segments if s.get("audio") and os.path.exists(s["audio"]) and os.path.getsize(s["audio"]) > 0]

    # If no valid segments to mix, just copy video
    if not valid_segments:
        cmd = [ffmpeg_bin, "-y", "-i", video_path, "-c", "copy", out_path]
        subprocess.run(cmd, check=True, capture_output=True)
        return out_path

    # Build FFmpeg filter_complex: place audio at correct time using adelay
    inputs = ["-i", video_path]
    filter_parts = []
    mix_labels = []

    for i, seg in enumerate(valid_segments):
        inputs += ["-i", seg["audio"]]
        start_time = seg.get("start") if seg.get("start") is not None else 0.0
        delay_ms = int(float(start_time) * 1000)
        label = f"a{i}"
        filter_parts.append(
            f"[{i+1}:a]adelay={delay_ms}|{delay_ms}[{label}]"
        )
        mix_labels.append(f"[{label}]")

    filter_complex = ";".join(filter_parts) + \
        ";" + "".join(mix_labels) + \
        f"amix=inputs={len(valid_segments)}:duration=longest[aout]"

    cmd = [
        ffmpeg_bin, "-y",
        *inputs,
        "-filter_complex", filter_complex,
        "-map", "0:v", "-map", "[aout]",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        out_path
    ]
    subprocess.run(cmd, check=True, capture_output=True)

    # cleanup
    for seg in valid_segments:
        try: os.remove(seg["audio"])
        except: pass

    return out_path
