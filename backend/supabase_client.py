import os
from pathlib import Path
from typing import Optional, Dict, Any

try:
    from dotenv import load_dotenv
    # Look for .env in current dir and parent root
    for env_path in [Path(".env"), Path("../.env"), Path(__file__).resolve().parent.parent / ".env"]:
        if env_path.exists():
            load_dotenv(dotenv_path=env_path)
            break
except ImportError:
    pass

from supabase import create_client, Client

# These can be set as environment variables or passed in directly
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

_supabase_client: Optional[Client] = None

def get_supabase() -> Optional[Client]:
    """
    Returns initialized Supabase client singleton if configured.
    """
    global _supabase_client
    if _supabase_client is None:
        url = os.environ.get("SUPABASE_URL", SUPABASE_URL)
        key = os.environ.get("SUPABASE_KEY", SUPABASE_KEY)
        if url and key:
            _supabase_client = create_client(url, key)
            print("[+] Supabase client initialized for project 'kems'")
    return _supabase_client

def save_dub_record(video_path: str, output_path: str, subtitles: list, meta: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
    """
    Saves dubbing task record into Supabase PostgreSQL table 'dub_records'.
    """
    client = get_supabase()
    if not client:
        return None
    try:
        data = {
            "source_video": video_path,
            "output_video": output_path,
            "subtitles": subtitles,
            "metadata": meta or {},
        }
        res = client.table("dub_records").insert(data).execute()
        return res.data
    except Exception as e:
        print(f"[!] Supabase save error: {e}")
        return None

def upload_to_supabase_storage(file_path: str, bucket: str = "videos", destination_path: str = None) -> Optional[str]:
    """
    Uploads dubbed video or audio into Supabase Storage bucket and returns public URL.
    """
    client = get_supabase()
    if not client or not os.path.exists(file_path):
        return None
    try:
        filename = destination_path or os.path.basename(file_path)
        with open(file_path, "rb") as f:
            client.storage.from_(bucket).upload(path=filename, file=f)
        public_url = client.storage.from_(bucket).get_public_url(filename)
        return public_url
    except Exception as e:
        print(f"[!] Supabase storage upload error: {e}")
        return None
