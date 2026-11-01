#!/usr/bin/env python3
"""
Halloween 2026 - Photo Transition Video Generator
Generates 2-second and 4-second transition videos (both AI Morph via FAL and Programmatic Fade via FFmpeg)
for matched photo pairs.
"""

import os
import sys
import json
import time
import random
import argparse
import datetime
import shutil
import subprocess
import urllib.request
import urllib.error

# Ensure UTF-8 output
sys.stdout.reconfigure(encoding='utf-8')

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# Support running from within src/transform or from project root
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
PHOTOS_DIR = os.path.join(PROJECT_ROOT, "photos")
ORIG_DIR = os.path.join(PHOTOS_DIR, "original")
TRANS_DIR = os.path.join(PHOTOS_DIR, "transformed")
MANIFEST_PATH = os.path.join(TRANS_DIR, "manifest.json")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output_videos")


def get_ffmpeg_bin():
    """Find ffmpeg binary across common system paths, project bin, or environment."""
    candidates = [
        os.environ.get("FFMPEG_PATH"),
        shutil.which("ffmpeg"),
        os.path.join(PROJECT_ROOT, "bin", "ffmpeg"),
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
            return os.path.abspath(c)
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
            m_info = manifest_map.get(tf, {})
            pairs.append({
                "pair_id": len(pairs) + 1,
                "orig_filename": best_of,
                "orig_path": os.path.join(ORIG_DIR, best_of),
                "trans_filename": tf,
                "trans_path": os.path.join(TRANS_DIR, tf),
                "prompt": m_info.get("prompt", "Seamless mystical costume transformation, high fantasy Halloween"),
                "fal_image_url": m_info.get("image_url", None),
                "fal_source_url": m_info.get("source_inputs", [None])[0] if m_info.get("source_inputs") else None,
            })
            
    return pairs


def upload_to_fal(file_path, fal_key):
    """Upload a local image file to fal.ai CDN via their storage API."""
    file_name = os.path.basename(file_path)
    content_type = "image/png" if file_path.lower().endswith(".png") else "image/jpeg"
    
    # 1. Initiate upload
    init_url = "https://rest.alpha.fal.ai/storage/upload/initiate?storage_type=fal-cdn-v3"
    auth_header = fal_key if fal_key.startswith("Key ") else f"Key {fal_key}"
    req = urllib.request.Request(
        init_url,
        data=json.dumps({"file_name": file_name, "content_type": content_type}).encode("utf-8"),
        headers={
            "Authorization": auth_header,
            "Content-Type": "application/json"
        },
        method="POST"
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        
    upload_url = data["upload_url"]
    file_url = data["file_url"]
    
    # 2. PUT binary file data
    with open(file_path, "rb") as f:
        file_bytes = f.read()
        
    put_req = urllib.request.Request(
        upload_url,
        data=file_bytes,
        headers={"Content-Type": content_type},
        method="PUT"
    )
    with urllib.request.urlopen(put_req) as resp:
        pass
        
    return file_url


def generate_fal_video(start_url, end_url, prompt, fal_key):
    """Submit request to fal-ai/wan-flf2v and poll until complete."""
    endpoint = "fal-ai/wan-flf2v"
    submit_url = f"https://queue.fal.run/{endpoint}"
    auth_header = fal_key if fal_key.startswith("Key ") else f"Key {fal_key}"
    
    payload = {
        "start_image_url": start_url,
        "end_image_url": end_url,
        "prompt": prompt,
        "num_frames": 81  # Standard high-quality 81 frames
    }
    
    headers = {
        "Authorization": auth_header,
        "Content-Type": "application/json"
    }
    
    print(f"    -> Submitting to {endpoint} queue...")
    req = urllib.request.Request(
        submit_url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST"
    )
    
    try:
        with urllib.request.urlopen(req) as resp:
            submit_resp = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        raise RuntimeError(f"FAL API submit error {e.code}: {err_body}")
        
    status_url = submit_resp.get("status_url")
    response_url = submit_resp.get("response_url")
    request_id = submit_resp.get("request_id")
    print(f"    -> Job queued! Request ID: {request_id}")
    
    # Poll until completed
    start_time = time.time()
    while True:
        time.sleep(3)
        poll_req = urllib.request.Request(status_url, headers=headers)
        with urllib.request.urlopen(poll_req) as resp:
            status_data = json.loads(resp.read().decode("utf-8"))
            
        status = status_data.get("status")
        elapsed = int(time.time() - start_time)
        print(f"    -> Status [{elapsed}s]: {status}")
        
        if status == "COMPLETED":
            break
        elif status in ("FAILED", "ERROR"):
            raise RuntimeError(f"FAL job failed: {status_data}")
            
    # Fetch final output
    res_req = urllib.request.Request(response_url, headers=headers)
    with urllib.request.urlopen(res_req) as resp:
        res_data = json.loads(resp.read().decode("utf-8"))
        
    video_url = res_data.get("video", {}).get("url")
    if not video_url:
        raise RuntimeError(f"No video URL in response: {res_data}")
        
    return video_url


def create_ffmpeg_fade(orig_path, trans_path, duration_sec, out_path, ffmpeg_bin=None):
    """
    Generate a high-quality programmatic crossfade video.
    For duration_sec=2: 0.5s still -> 1.0s crossfade -> 0.5s still
    For duration_sec=4: 1.0s still -> 2.0s crossfade -> 1.0s still
    """
    ffmpeg_bin = ffmpeg_bin or get_ffmpeg_bin()
    if not ffmpeg_bin:
        raise FileNotFoundError("Could not find 'ffmpeg' executable. Install ffmpeg or set FFMPEG_PATH.")
        
    still_time = duration_sec * 0.25
    fade_time = duration_sec * 0.50
    input_len = still_time + fade_time
    
    filter_complex = (
        f"[0:v]scale=1200:900:force_original_aspect_ratio=decrease,pad=1200:900:(ow-iw)/2:(oh-ih)/2,setsar=1[v0];"
        f"[1:v]scale=1200:900:force_original_aspect_ratio=decrease,pad=1200:900:(ow-iw)/2:(oh-ih)/2,setsar=1[v1];"
        f"[v0][v1]xfade=transition=fade:duration={fade_time:.2f}:offset={still_time:.2f},format=yuv420p[v]"
    )
    
    cmd = [
        ffmpeg_bin, "-y",
        "-loop", "1", "-t", str(input_len), "-i", orig_path,
        "-loop", "1", "-t", str(input_len), "-i", trans_path,
        "-filter_complex", filter_complex,
        "-map", "[v]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "19",
        "-pix_fmt", "yuv420p",
        out_path
    ]
    
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def process_ai_durations(raw_video_path, out_2s_path, out_4s_path, ffmpeg_bin=None):
    """
    Produce both 2-second and 4-second versions from the single AI video.
    - 2s version: crisp, snappy playback at ~40fps / 2.0s.
    - 4s version: smooth motion-interpolated 4.0s slow motion.
    """
    ffmpeg_bin = ffmpeg_bin or get_ffmpeg_bin()
    if not ffmpeg_bin:
        raise FileNotFoundError("Could not find 'ffmpeg' executable. Install ffmpeg or set FFMPEG_PATH.")
        
    # 1. Create snappy 2-second version
    # Speed up / fit exactly 2.0 seconds with fast motion
    cmd_2s = [
        ffmpeg_bin, "-y", "-i", raw_video_path,
        "-filter_complex",
        "[0:v]trim=duration=2.0,setpts=PTS-STARTPTS,scale=1200:900:force_original_aspect_ratio=decrease,pad=1200:900:(ow-iw)/2:(oh-ih)/2,fps=30,format=yuv420p[v]",
        "-map", "[v]", "-c:v", "libx264", "-crf", "19", "-preset", "fast",
        out_2s_path
    ]
    subprocess.run(cmd_2s, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    # 2. Create smooth 4-second version
    # Use minterpolate for fluid optical-flow motion interpolation over 4 seconds
    cmd_4s = [
        ffmpeg_bin, "-y", "-i", raw_video_path,
        "-filter_complex",
        "[0:v]setpts=1.25*PTS,minterpolate=fps=30:mi_mode=mci:mc_mode=aobmc,trim=duration=4.0,scale=1200:900:force_original_aspect_ratio=decrease,pad=1200:900:(ow-iw)/2:(oh-ih)/2,format=yuv420p[v]",
        "-map", "[v]", "-c:v", "libx264", "-crf", "19", "-preset", "fast",
        out_4s_path
    ]
    try:
        subprocess.run(cmd_4s, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        # Fallback to standard setpts if minterpolate is unavailable
        cmd_4s_fallback = [
            ffmpeg_bin, "-y", "-i", raw_video_path,
            "-filter_complex",
            "[0:v]setpts=1.25*PTS,trim=duration=4.0,scale=1200:900:force_original_aspect_ratio=decrease,pad=1200:900:(ow-iw)/2:(oh-ih)/2,fps=30,format=yuv420p[v]",
            "-map", "[v]", "-c:v", "libx264", "-crf", "19", "-preset", "fast",
            out_4s_path
        ]
        subprocess.run(cmd_4s_fallback, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main():
    parser = argparse.ArgumentParser(description="Generate 2s & 4s Transition Videos (AI Morph & Programmatic Fade)")
    parser.add_argument("--count", type=int, default=3, help="Number of random pairs to generate (default: 3)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for repeatable pair selection")
    parser.add_argument("--mode", choices=["all", "fade", "ai"], default="all",
                        help="'fade' for programmatic only, 'ai' for fal.ai only, 'all' for both")
    args = parser.parse_args()

    print("==========================================================")
    print("   Halloween 2026 - Photo Transition Video Generator      ")
    print("==========================================================")
    
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    ffmpeg_bin = get_ffmpeg_bin()
    if not ffmpeg_bin:
        print("[!] ERROR: 'ffmpeg' executable could not be found in PATH, standard paths, or ./bin/ffmpeg.")
        print("    Please ensure ffmpeg is installed or set the FFMPEG_PATH environment variable.")
        sys.exit(1)
    print(f"[*] FFmpeg executable: {ffmpeg_bin}")
    
    pairs = get_matched_pairs()
    print(f"[*] Found {len(pairs)} matched original/transformed photo pairs.")
    
    random.seed(args.seed)
    selected = random.sample(pairs, min(args.count, len(pairs)))
    
    fal_key = load_env_key()
    has_fal = bool(fal_key)
    
    if args.mode in ("all", "ai") and not has_fal:
        print("[!] Note: No FAL_KEY found in environment or .env file.")
        print("    -> Add your FAL_KEY to .env to enable fal.ai generation.")
        print("    -> Proceeding with Programmatic Fade mode (free & instant) so you have sample clips.")
        run_ai = False
        run_fade = True
    else:
        run_ai = args.mode in ("all", "ai") and has_fal
        run_fade = args.mode in ("all", "fade")
        
    print(f"[*] Selected {len(selected)} random pairs for generation:")
    for i, p in enumerate(selected, 1):
        print(f"    {i}. ID #{p['pair_id']}: {p['orig_filename']} <-> {p['trans_filename']}")
        print(f"       Prompt: {p['prompt'][:70]}...")

    print("\n----------------------------------------------------------")
    for idx, pair in enumerate(selected, 1):
        pid = pair["pair_id"]
        print(f"\n[{idx}/{len(selected)}] Processing Pair #{pid}...")

        # 1. Programmatic Fade (2s and 4s)
        if run_fade:
            print("  [+] Generating Programmatic Fade transitions...")
            fade_2s = os.path.join(OUTPUT_DIR, f"pair_{pid:02d}_fade_2s.mp4")
            fade_4s = os.path.join(OUTPUT_DIR, f"pair_{pid:02d}_fade_4s.mp4")
            
            create_ffmpeg_fade(pair["orig_path"], pair["trans_path"], 2.0, fade_2s, ffmpeg_bin=ffmpeg_bin)
            create_ffmpeg_fade(pair["orig_path"], pair["trans_path"], 4.0, fade_4s, ffmpeg_bin=ffmpeg_bin)
            print(f"      Saved: {os.path.basename(fade_2s)} ({os.path.getsize(fade_2s)//1024} KB)")
            print(f"      Saved: {os.path.basename(fade_4s)} ({os.path.getsize(fade_4s)//1024} KB)")

        # 2. AI Morph via fal-ai/wan-flf2v (2s and 4s)
        if run_ai:
            print("  [+] Requesting AI Morph from fal.ai (wan-flf2v)...")
            raw_ai = os.path.join(OUTPUT_DIR, f"pair_{pid:02d}_ai_raw.mp4")
            ai_2s = os.path.join(OUTPUT_DIR, f"pair_{pid:02d}_ai_2s.mp4")
            ai_4s = os.path.join(OUTPUT_DIR, f"pair_{pid:02d}_ai_4s.mp4")

            start_url = pair["fal_source_url"]
            end_url = pair["fal_image_url"]

            # Fallback upload if remote URLs are missing
            if not start_url:
                print("    -> Uploading original image to fal CDN...")
                start_url = upload_to_fal(pair["orig_path"], fal_key)
            if not end_url:
                print("    -> Uploading transformed image to fal CDN...")
                end_url = upload_to_fal(pair["trans_path"], fal_key)

            try:
                video_url = generate_fal_video(start_url, end_url, pair["prompt"], fal_key)
                print(f"    -> Downloading generated video from {video_url}...")
                urllib.request.urlretrieve(video_url, raw_ai)

                print("    -> Processing into 2s (snappy) and 4s (motion-interpolated) clips...")
                process_ai_durations(raw_ai, ai_2s, ai_4s, ffmpeg_bin=ffmpeg_bin)
                print(f"      Saved: {os.path.basename(ai_2s)} ({os.path.getsize(ai_2s)//1024} KB)")
                print(f"      Saved: {os.path.basename(ai_4s)} ({os.path.getsize(ai_4s)//1024} KB)")
            except Exception as e:
                print(f"    [!] Error during FAL generation: {e}")
            except Exception as e:
                print(f"    [!] Error during FAL generation: {e}")

    print("\n==========================================================")
    print(f"[*] Done! All generated videos saved in:\n    {OUTPUT_DIR}")
    print("==========================================================")


if __name__ == "__main__":
    main()
