"""
Shared utilities for Halloween 2026 media processing and transformation pipelines.
"""

import os
import sys
import json
import shutil
import datetime

# Root paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))

PHOTOS_DIR = os.path.join(PROJECT_ROOT, "photos")
ORIG_DIR = os.path.join(PHOTOS_DIR, "original")
TRANS_DIR = os.path.join(PHOTOS_DIR, "transformed")
MANIFEST_PATH = os.path.join(TRANS_DIR, "manifest.json")

PUBLIC_DIR = os.path.join(PROJECT_ROOT, "public")
DATA_DIR = os.path.join(PUBLIC_DIR, "data")
MEDIA_DIR = os.path.join(PUBLIC_DIR, "media")

WEB_IMAGES_DIR = os.path.join(MEDIA_DIR, "web")
THUMB_IMAGES_DIR = os.path.join(MEDIA_DIR, "thumbs")
VIDEOS_DIR = os.path.join(MEDIA_DIR, "videos")
LEGACY_VIDEOS_DIR = os.path.join(PROJECT_ROOT, "output_videos")
PHOTOS_METADATA_PATH = os.path.join(DATA_DIR, "photos.json")


def get_ffmpeg_bin():
    """Find a functional ffmpeg binary across common system paths or environment."""
    candidates = [
        os.environ.get("FFMPEG_PATH"),
        shutil.which("ffmpeg"),
        "/usr/bin/ffmpeg",
        "/usr/local/bin/ffmpeg",
        "/bin/ffmpeg",
        "/usr/sbin/ffmpeg",
        "/usr/local/sbin/ffmpeg",
        os.path.expanduser("~/.local/bin/ffmpeg"),
        os.path.expanduser("~/bin/ffmpeg"),
        "/opt/homebrew/bin/ffmpeg",
        "/home/linuxbrew/.linuxbrew/bin/ffmpeg",
    ]
    for c in candidates:
        if c and os.path.isfile(c) and os.access(c, os.X_OK):
            try:
                res = subprocess.run([c, "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if res.returncode == 0:
                    return os.path.abspath(c)
            except Exception:
                continue
    return None


def load_env_key():
    """Load FAL_KEY from environment or .env file (checked in project root and current dir)."""
    if os.environ.get("FAL_KEY"):
        return os.environ.get("FAL_KEY").strip()
    
    for check_dir in (PROJECT_ROOT, SCRIPT_DIR):
        env_path = os.path.join(check_dir, ".env")
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("#") or not line or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    if k.strip() == "FAL_KEY":
                        val = v.strip().strip("'\"")
                        if val and val != "your_fal_key_here":
                            return val
    return None


def classify_theme(prompt):
    """Categorize AI generation prompt into human-friendly theme metadata."""
    p_lower = (prompt or "").lower()
    if "zombie pirate" in p_lower or "galleon" in p_lower or "tricorn" in p_lower:
        return {
            "id": "zombie-pirates",
            "title": "Cursed Zombie Pirates",
            "tag": "Pirates",
            "color": "cyan",
            "icon": "skull",
            "description": "Cursed undead buccaneers adrift on a spectral sunken galleon"
        }
    elif "eldritch" in p_lower or "tentacle" in p_lower or "cyclopean" in p_lower:
        return {
            "id": "eldritch-abyss",
            "title": "Eldritch Abyssal Horror",
            "tag": "Eldritch",
            "color": "purple",
            "icon": "eye",
            "description": "Deep-sea cosmic nightmare amidst glowing cyclopean ruins"
        }
    elif "ballroom" in p_lower or "chandelier" in p_lower or "tuxedo" in p_lower or "evening gown" in p_lower:
        return {
            "id": "victorian-ballroom",
            "title": "Submerged Victorian Ballroom",
            "tag": "Ballroom",
            "color": "amber",
            "icon": "sparkles",
            "description": "Waterlogged antique finery and spectral phantoms under the sea"
        }
    elif "diving suit" in p_lower or "brass" in p_lower or "copper" in p_lower:
        return {
            "id": "deep-sea-divers",
            "title": "Vintage Deep-Sea Divers",
            "tag": "Divers",
            "color": "orange",
            "icon": "anchor",
            "description": "19th-century brass dive helmets walking the ocean floor"
        }
    elif "murky lake" in p_lower or "lakebed" in p_lower or "reeds" in p_lower:
        return {
            "id": "murky-lakebed",
            "title": "Murky Lakebed Horror",
            "tag": "Lakebed",
            "color": "emerald",
            "icon": "ghost",
            "description": "Haunting waterlogged silt and tangled reeds at the lake floor"
        }
    elif "scuba" in p_lower or "shark" in p_lower or "holiday" in p_lower or "hammerhead" in p_lower:
        return {
            "id": "shark-dive",
            "title": "Tropical Shark Encounter",
            "tag": "Sharks",
            "color": "teal",
            "icon": "fish",
            "description": "Turquoise holiday waters with stealthily circling ocean apex predators"
        }
    return {
        "id": "dark-waters",
        "title": "Dark Waters Halloween",
        "tag": "Halloween",
        "color": "indigo",
        "icon": "wand",
        "description": "Haunted aquatic Halloween transformation"
    }


def parse_orig_time(filename):
    """Parse timestamp from single_YYYYMMDD_HHMMSS_xxxx.jpg"""
    parts = filename.split('_')
    return datetime.datetime.strptime(parts[1] + parts[2], '%Y%m%d%H%M%S')


def parse_trans_time(filename):
    """Parse timestamp from YYYYMMDD_HHMMSS_xxxx.png"""
    parts = filename.split('_')
    return datetime.datetime.strptime(parts[0] + parts[1], '%Y%m%d%H%M%S')


def get_matched_pairs():
    """Build matched list of original and transformed photos with metadata."""
    if not os.path.exists(ORIG_DIR) or not os.path.exists(TRANS_DIR):
        raise FileNotFoundError(f"Missing photos directories in {PHOTOS_DIR}")
    
    orig_files = sorted(f for f in os.listdir(ORIG_DIR) if f.lower().endswith(('.jpg', '.jpeg', '.png')))
    trans_files = sorted(f for f in os.listdir(TRANS_DIR) if f.lower().endswith(('.png', '.jpg')))
    
    manifest_map = {}
    if os.path.exists(MANIFEST_PATH):
        try:
            with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
                manifest_data = json.load(f)
                manifest_map = {m["filename"]: m for m in manifest_data if "filename" in m}
        except Exception as e:
            print(f"[!] Warning: could not parse manifest.json: {e}")
            
    orig_times = [(f, parse_orig_time(f)) for f in orig_files]
    trans_times = [(f, parse_trans_time(f)) for f in trans_files]
    
    pairs = []
    for tf, tt in trans_times:
        # 1-hour timezone offset between camera local time and fal.ai UTC timestamp
        adjusted_t = tt + datetime.timedelta(hours=1)
        best_of, best_diff = None, float("inf")
        for of, ot in orig_times:
            diff = abs((ot - adjusted_t).total_seconds())
            if diff < best_diff:
                best_diff = diff
                best_of = of
                
        # Only accept matches within reasonable delta (less than 60s)
        if best_diff <= 60 and best_of:
            pair_id = len(pairs) + 1
            m_info = manifest_map.get(tf, {})
            prompt = m_info.get("prompt", "Seamless mystical costume transformation, high fantasy Halloween")
            theme_meta = classify_theme(prompt)
            
            # Formatted display time
            camera_dt = parse_orig_time(best_of)
            display_time = camera_dt.strftime("%I:%M %p")
            
            pairs.append({
                "id": pair_id,
                "pair_id": pair_id,
                "display_time": display_time,
                "theme": theme_meta,
                "prompt": prompt,
                "request_id": m_info.get("request_id"),
                "fal_timestamp": m_info.get("timestamp"),
                "fal_image_url": m_info.get("image_url"),
                "fal_source_url": m_info.get("source_inputs", [None])[0] if m_info.get("source_inputs") else None,
                "original_filename": best_of,
                "original_source_path": os.path.join(ORIG_DIR, best_of),
                "transformed_filename": tf,
                "transformed_source_path": os.path.join(TRANS_DIR, tf),
            })
            
    return pairs
