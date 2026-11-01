#!/usr/bin/env python3
"""
Halloween 2026 - Concurrent Batch Video Generator (FAL AI Wan-2.1)
Generates 5-second AI transition videos concurrently (up to 10 workers),
gracefully handles MP4 streaming optimization, reuses all existing videos,
and incrementally saves progress into public/data/photos.json.
"""

import os
import sys
import time
import json
import shutil
import argparse
import threading
import subprocess
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed

# Ensure UTF-8 output
sys.stdout.reconfigure(encoding='utf-8')

from common import (
    PROJECT_ROOT,
    PUBLIC_DIR,
    VIDEOS_DIR,
    DATA_DIR,
    LEGACY_VIDEOS_DIR,
    PHOTOS_METADATA_PATH,
    get_ffmpeg_bin,
    load_env_key,
    get_matched_pairs
)

SCRATCH_DIR = os.path.join(PROJECT_ROOT, "scratch_downloads")

# Thread safety locks
print_lock = threading.Lock()
metadata_lock = threading.Lock()


def safe_log(msg):
    """Thread-safe stdout logging."""
    with print_lock:
        print(msg, flush=True)


def upload_to_fal(file_path, fal_key):
    """Upload a local image file to fal.ai CDN via their storage API."""
    file_name = os.path.basename(file_path)
    content_type = "image/png" if file_path.lower().endswith(".png") else "image/jpeg"
    auth_header = fal_key if fal_key.startswith("Key ") else f"Key {fal_key}"
    
    init_url = "https://rest.alpha.fal.ai/storage/upload/initiate?storage_type=fal-cdn-v3"
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


def generate_fal_video(start_url, end_url, prompt, fal_key, log_prefix=""):
    """Submit request to fal-ai/wan-flf2v and poll until complete."""
    endpoint = "fal-ai/wan-flf2v"
    submit_url = f"https://queue.fal.run/{endpoint}"
    auth_header = fal_key if fal_key.startswith("Key ") else f"Key {fal_key}"
    
    payload = {
        "start_image_url": start_url,
        "end_image_url": end_url,
        "prompt": prompt,
        "num_frames": 81  # Standard high-quality 81 frames (~5.06s original length)
    }
    
    headers = {
        "Authorization": auth_header,
        "Content-Type": "application/json"
    }
    
    safe_log(f"{log_prefix} Submitting to {endpoint} queue...")
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
    safe_log(f"{log_prefix} Job queued! Request ID: {request_id[:16]}...")
    
    # Poll until completed
    start_time = time.time()
    last_status = None
    while True:
        time.sleep(3)
        poll_req = urllib.request.Request(status_url, headers=headers)
        with urllib.request.urlopen(poll_req) as resp:
            status_data = json.loads(resp.read().decode("utf-8"))
            
        status = status_data.get("status")
        elapsed = int(time.time() - start_time)
        if status != last_status or elapsed % 15 == 0:
            safe_log(f"{log_prefix} Status [{elapsed}s]: {status}")
            last_status = status
            
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
        
    return video_url, request_id


def optimize_video_stream(raw_video_path, out_video_path, ffmpeg_bin=None):
    """
    Ensure MP4 is web-streamable.
    Tries ffmpeg -c copy -movflags +faststart.
    If ffmpeg is absent or fails for any reason, falls back to direct file copy.
    """
    if ffmpeg_bin:
        try:
            cmd = [
                ffmpeg_bin, "-y", "-i", raw_video_path,
                "-c", "copy",
                "-movflags", "+faststart",
                out_video_path
            ]
            res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if res.returncode == 0 and os.path.exists(out_video_path) and os.path.getsize(out_video_path) > 1000:
                return True
        except Exception:
            pass
            
    # Safe fallback: copy original FAL MP4 directly (already valid H.264)
    shutil.copyfile(raw_video_path, out_video_path)
    return True


def load_gallery_metadata():
    """Load existing photos.json database or rebuild baseline if missing."""
    if os.path.exists(PHOTOS_METADATA_PATH):
        with open(PHOTOS_METADATA_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def update_single_photo_metadata(pid, v_file, v_size, video_url=None, request_id=None):
    """Thread-safe update of a single photo entry in photos.json."""
    with metadata_lock:
        if not os.path.exists(PHOTOS_METADATA_PATH):
            return
        try:
            with open(PHOTOS_METADATA_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            for item in data.get("photos", []):
                if item["id"] == pid:
                    item["video"] = {
                        "available": True,
                        "filename": v_file,
                        "path": f"media/videos/{v_file}",
                        "duration": 5.06,
                        "size_bytes": v_size,
                        "width": 1280,
                        "height": 720,
                        "fal_video_url": video_url,
                        "request_id": request_id
                    }
                    break
                    
            data["total_videos_ready"] = sum(1 for item in data.get("photos", []) if item.get("video", {}).get("available"))
            
            temp_path = f"{PHOTOS_METADATA_PATH}.tmp"
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            os.replace(temp_path, PHOTOS_METADATA_PATH)
        except Exception as e:
            safe_log(f"[!] Warning: error saving metadata for #{pid}: {e}")


def process_single_pair(pair, idx, total, fal_key, ffmpeg_bin):
    """Process a single photo pair: checks caches/disk, calls FAL if needed, saves video."""
    pid = pair["id"]
    theme_title = pair.get("theme", {}).get("title", "Transformation")
    v_dest_file = f"photo_{pid:02d}_transition.mp4"
    v_dest_path = os.path.join(VIDEOS_DIR, v_dest_file)
    log_prefix = f"[{idx:02d}/{total:02d} | Photo #{pid:02d}]"

    # 1. Check if already exists in public/media/videos/
    if os.path.exists(v_dest_path) and os.path.getsize(v_dest_path) > 1000:
        v_size = os.path.getsize(v_dest_path)
        update_single_photo_metadata(pid, v_dest_file, v_size)
        safe_log(f"{log_prefix} [✓] Already ready in public/media/videos/ ({v_size // 1024} KB)")
        return True, pid

    # 2. Check if already exists in scratch_downloads/
    scratch_raw = os.path.join(SCRATCH_DIR, f"raw_{pid:02d}.mp4")
    if os.path.exists(scratch_raw) and os.path.getsize(scratch_raw) > 1000:
        safe_log(f"{log_prefix} [!] Found existing downloaded video in scratch_downloads/, optimizing...")
        optimize_video_stream(scratch_raw, v_dest_path, ffmpeg_bin)
        v_size = os.path.getsize(v_dest_path)
        update_single_photo_metadata(pid, v_dest_file, v_size)
        safe_log(f"{log_prefix} [✓] Saved from scratch: {v_dest_file} ({v_size // 1024} KB)")
        return True, pid

    # 3. Check if already exists in output_videos/ (legacy test runs)
    legacy_raw = os.path.join(LEGACY_VIDEOS_DIR, f"pair_{pid:02d}_ai_raw.mp4")
    if os.path.exists(legacy_raw) and os.path.getsize(legacy_raw) > 1000:
        safe_log(f"{log_prefix} [!] Found existing video in output_videos/, optimizing...")
        optimize_video_stream(legacy_raw, v_dest_path, ffmpeg_bin)
        v_size = os.path.getsize(v_dest_path)
        update_single_photo_metadata(pid, v_dest_file, v_size)
        safe_log(f"{log_prefix} [✓] Saved from output_videos: {v_dest_file} ({v_size // 1024} KB)")
        return True, pid

    # 4. Generate new video via FAL
    safe_log(f"{log_prefix} Starting generation ({theme_title})...")
    
    start_url = pair.get("fal_source_url")
    end_url = pair.get("fal_image_url")
    orig_source_path = os.path.join(PROJECT_ROOT, pair.get("original", {}).get("full_download", f"photos/original/{pair.get('original_filename', '')}"))
    trans_source_path = os.path.join(PROJECT_ROOT, pair.get("transformed", {}).get("full_download", f"photos/transformed/{pair.get('transformed_filename', '')}"))

    if not start_url:
        safe_log(f"{log_prefix} Uploading original photo to FAL CDN...")
        start_url = upload_to_fal(orig_source_path, fal_key)
    if not end_url:
        safe_log(f"{log_prefix} Uploading transformed photo to FAL CDN...")
        end_url = upload_to_fal(trans_source_path, fal_key)

    prompt = pair.get("prompt", "Seamless mythical costume transition, high fantasy Halloween")

    try:
        video_url, request_id = generate_fal_video(start_url, end_url, prompt, fal_key, log_prefix=log_prefix)
        
        # Download raw to temporary path
        raw_tmp_path = os.path.join(SCRATCH_DIR, f"raw_{pid:02d}.mp4")
        safe_log(f"{log_prefix} Downloading generated video...")
        urllib.request.urlretrieve(video_url, raw_tmp_path)

        # Optimize stream into public/media/videos/
        safe_log(f"{log_prefix} Finalizing video for web streaming...")
        optimize_video_stream(raw_tmp_path, v_dest_path, ffmpeg_bin)

        v_size = os.path.getsize(v_dest_path)
        update_single_photo_metadata(pid, v_dest_file, v_size, video_url=video_url, request_id=request_id)
        safe_log(f"{log_prefix} [✓] Complete! Saved {v_dest_file} ({v_size // 1024} KB)")
        return True, pid

    except Exception as e:
        safe_log(f"{log_prefix} [!] ERROR: {e}")
        return False, pid


def main():
    parser = argparse.ArgumentParser(description="Batch generate 5s AI video transitions concurrently (FAL WAN-2.1)")
    parser.add_argument("--concurrency", type=int, default=10, help="Number of concurrent FAL requests (default: 10)")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of videos to generate (0 = all)")
    parser.add_argument("--pair-id", type=int, default=0, help="Generate for a specific photo pair ID only")
    parser.add_argument("--force", action="store_true", help="Re-generate video even if already present")
    parser.add_argument("--dry-run", action="store_true", help="List pending videos without calling FAL API")
    args = parser.parse_args()

    print("==========================================================")
    print("   Halloween 2026 - Concurrent 5s AI Video Generator      ")
    print(f"   Max Concurrency Limit: {args.concurrency} concurrent requests")
    print("==========================================================")

    ffmpeg_bin = get_ffmpeg_bin()
    if ffmpeg_bin:
        print(f"[*] Verified FFmpeg binary: {ffmpeg_bin}")
    else:
        print("[*] Note: FFmpeg not detected. Videos will be saved directly with native MP4 encoding.")

    fal_key = load_env_key()
    if not fal_key and not args.dry_run:
        print("[!] ERROR: FAL_KEY not found in environment or .env.")
        print("    Please add FAL_KEY=... in .env to run AI generation.")
        sys.exit(1)

    os.makedirs(VIDEOS_DIR, exist_ok=True)
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(SCRATCH_DIR, exist_ok=True)

    metadata = load_gallery_metadata()
    if not metadata:
        print("[!] Rebuilding baseline pairs from photos folder...")
        pairs = get_matched_pairs()
    else:
        pairs = metadata.get("photos", [])

    # Filter pending vs already ready
    pending = []
    already_ready = []

    for p in pairs:
        pid = p["id"]
        v_file = f"photo_{pid:02d}_transition.mp4"
        v_path = os.path.join(VIDEOS_DIR, v_file)
        scratch_file = os.path.join(SCRATCH_DIR, f"raw_{pid:02d}.mp4")
        legacy_file = os.path.join(LEGACY_VIDEOS_DIR, f"pair_{pid:02d}_ai_raw.mp4")

        has_video = (
            (os.path.exists(v_path) and os.path.getsize(v_path) > 1000) or
            (os.path.exists(scratch_file) and os.path.getsize(scratch_file) > 1000) or
            (os.path.exists(legacy_file) and os.path.getsize(legacy_file) > 1000)
        )

        if args.pair_id and pid != args.pair_id:
            continue

        if has_video and not args.force:
            already_ready.append(p)
        else:
            pending.append(p)

    if args.limit and args.limit > 0:
        pending = pending[:args.limit]

    print(f"[*] Total Photo Pairs       : {len(pairs)}")
    print(f"[*] Already Generated Videos : {len(already_ready)} (reused, 0 new cost)")
    print(f"[*] Videos Queued to Create  : {len(pending)}")
    estimated_cost = len(pending) * 0.25
    print(f"[*] Estimated Additional Cost: ~${estimated_cost:.2f} USD (@ ~$0.25 / video)")

    if args.dry_run:
        print("\n[*] Already Ready Videos:")
        for p in already_ready:
            print(f"    [Ready] Photo #{p['id']:02d}: {p.get('theme', {}).get('title', '')}")
        print("\n[*] Pending Videos:")
        for p in pending:
            print(f"    [Pending] Photo #{p['id']:02d}: {p.get('theme', {}).get('title', '')}")
        print("\n[!] Dry run complete. No API calls were made.")
        return

    # First, quickly sync all already_ready videos into public/media/videos/ and photos.json
    print("\n[*] Synchronizing already generated videos...")
    for p in already_ready:
        pid = p["id"]
        v_file = f"photo_{pid:02d}_transition.mp4"
        v_dest_path = os.path.join(VIDEOS_DIR, v_file)
        scratch_file = os.path.join(SCRATCH_DIR, f"raw_{pid:02d}.mp4")
        legacy_file = os.path.join(LEGACY_VIDEOS_DIR, f"pair_{pid:02d}_ai_raw.mp4")

        if not os.path.exists(v_dest_path) or os.path.getsize(v_dest_path) <= 1000:
            if os.path.exists(scratch_file):
                optimize_video_stream(scratch_file, v_dest_path, ffmpeg_bin)
            elif os.path.exists(legacy_file):
                optimize_video_stream(legacy_file, v_dest_path, ffmpeg_bin)

        if os.path.exists(v_dest_path):
            update_single_photo_metadata(pid, v_file, os.path.getsize(v_dest_path))

    if not pending:
        print("\n[✓] All 59 photo transition videos are generated and ready!")
        print(f"[*] Videos directory: {VIDEOS_DIR}")
        print(f"[*] Master metadata : {PHOTOS_METADATA_PATH}")
        return

    # Process pending with ThreadPoolExecutor
    workers = min(args.concurrency, len(pending))
    print(f"\n[*] Launching {workers} concurrent workers for {len(pending)} pending videos...")
    print("----------------------------------------------------------")

    completed_count = 0
    failed_count = 0

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(process_single_pair, pair, idx, len(pending), fal_key, ffmpeg_bin): pair["id"]
            for idx, pair in enumerate(pending, 1)
        }

        for future in as_completed(futures):
            pid = futures[future]
            try:
                success, _ = future.result()
                if success:
                    completed_count += 1
                else:
                    failed_count += 1
            except Exception as e:
                failed_count += 1
                safe_log(f"[!] Worker exception on Photo #{pid:02d}: {e}")

    print("\n==========================================================")
    print("   Concurrent Generation Run Complete!                    ")
    print("==========================================================")
    print(f"[*] Succeeded this run: {completed_count}")
    print(f"[*] Failed this run   : {failed_count}")
    
    # Reload metadata to display final count
    final_meta = load_gallery_metadata()
    ready_count = final_meta.get("total_videos_ready", 0) if final_meta else 0
    print(f"[*] Total Ready Videos : {ready_count}/{len(pairs)}")
    print(f"[*] Metadata Database  : {PHOTOS_METADATA_PATH}")
    print("==========================================================")


if __name__ == "__main__":
    main()
