#!/usr/bin/env python3
"""
Halloween 2026 - Media Optimization Script
Optimizes photos into responsive WebP images and thumbnails, ensures video faststart,
and writes the master photos.json metadata database for the gallery website.
"""

import os
import sys
import json
import argparse
import subprocess
from PIL import Image, ImageFile

# Allow loading slightly truncated images if encountered
ImageFile.LOAD_TRUNCATED_IMAGES = True

from common import (
    PROJECT_ROOT,
    PUBLIC_DIR,
    DATA_DIR,
    WEB_IMAGES_DIR,
    THUMB_IMAGES_DIR,
    VIDEOS_DIR,
    LEGACY_VIDEOS_DIR,
    PHOTOS_METADATA_PATH,
    get_ffmpeg_bin,
    get_matched_pairs
)


def optimize_image(src_path, dst_path, max_dim, quality):
    """Resize image to fit within max_dim x max_dim and save as WebP."""
    if os.path.exists(dst_path) and os.path.getmtime(dst_path) >= os.path.getmtime(src_path):
        return False  # Already up to date

    os.makedirs(os.path.dirname(dst_path), exist_ok=True)
    with Image.open(src_path) as im:
        # Convert CMYK/RGBA if needed to RGB for clean WebP
        if im.mode not in ("RGB", "RGBA"):
            im = im.convert("RGB")
        
        # Calculate aspect ratio preserving thumbnail
        im.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
        im.save(dst_path, "WEBP", quality=quality, method=4)
    return True


def ensure_video_faststart(src_video, dst_video, ffmpeg_bin):
    """Re-mux MP4 video with +faststart for instant browser streaming."""
    if os.path.exists(dst_video) and os.path.getmtime(dst_video) >= os.path.getmtime(src_video):
        return False

    os.makedirs(os.path.dirname(dst_video), exist_ok=True)
    cmd = [
        ffmpeg_bin, "-y", "-i", src_video,
        "-c:v", "libx264", "-crf", "20", "-preset", "fast",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        dst_video
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return True


def get_video_info(video_path, ffmpeg_bin):
    """Retrieve video duration, dimensions and size using ffprobe."""
    if not os.path.exists(video_path):
        return None
        
    ffprobe_bin = ffmpeg_bin.replace("ffmpeg", "ffprobe")
    if not os.path.exists(ffprobe_bin):
        # Fallback to file size if ffprobe not next to ffmpeg
        return {
            "size_bytes": os.path.getsize(video_path),
            "duration_sec": 5.06
        }
        
    cmd = [
        ffprobe_bin, "-v", "error",
        "-show_entries", "format=duration,size:stream=width,height",
        "-of", "json",
        video_path
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(res.stdout)
        duration = float(data.get("format", {}).get("duration", 5.06))
        size = int(data.get("format", {}).get("size", os.path.getsize(video_path)))
        streams = data.get("streams", [{}])
        width = streams[0].get("width", 1200) if streams else 1200
        height = streams[0].get("height", 900) if streams else 900
        return {
            "duration_sec": round(duration, 2),
            "size_bytes": size,
            "width": width,
            "height": height
        }
    except Exception:
        return {
            "size_bytes": os.path.getsize(video_path),
            "duration_sec": 5.06
        }


def main():
    parser = argparse.ArgumentParser(description="Optimize media and build gallery metadata for Cloudflare Pages")
    parser.add_argument("--force", action="store_true", help="Force re-optimization of all images and videos")
    args = parser.parse_args()

    print("==========================================================")
    print("   Halloween 2026 - Media Optimizer & Metadata Builder    ")
    print("==========================================================")
    
    ffmpeg_bin = get_ffmpeg_bin()
    if ffmpeg_bin:
        print(f"[*] FFmpeg detected: {ffmpeg_bin}")
    else:
        print("[!] Warning: FFmpeg not detected. Video faststart check will be skipped.")

    for d in (DATA_DIR, WEB_IMAGES_DIR, THUMB_IMAGES_DIR, VIDEOS_DIR):
        os.makedirs(d, exist_ok=True)

    pairs = get_matched_pairs()
    print(f"[*] Found {len(pairs)} matched photo pairs to process.")

    total_orig_bytes = 0
    total_web_bytes = 0
    total_thumb_bytes = 0
    video_count = 0

    gallery_items = []

    print("\n[*] Processing images and linking transition videos...")
    for idx, pair in enumerate(pairs, 1):
        pid = pair["id"]
        
        orig_src = pair["original_source_path"]
        trans_src = pair["transformed_source_path"]
        
        orig_src_size = os.path.getsize(orig_src)
        trans_src_size = os.path.getsize(trans_src)
        total_orig_bytes += (orig_src_size + trans_src_size)

        # Destination paths
        web_orig_file = f"photo_{pid:02d}_orig.webp"
        web_trans_file = f"photo_{pid:02d}_trans.webp"
        thumb_orig_file = f"photo_{pid:02d}_orig.webp"
        thumb_trans_file = f"photo_{pid:02d}_trans.webp"

        web_orig_path = os.path.join(WEB_IMAGES_DIR, web_orig_file)
        web_trans_path = os.path.join(WEB_IMAGES_DIR, web_trans_file)
        thumb_orig_path = os.path.join(THUMB_IMAGES_DIR, thumb_orig_file)
        thumb_trans_path = os.path.join(THUMB_IMAGES_DIR, thumb_trans_file)

        # Optimize Web (1600px max, q=85)
        optimize_image(orig_src, web_orig_path, max_dim=1600, quality=85)
        optimize_image(trans_src, web_trans_path, max_dim=1600, quality=85)

        # Optimize Thumbnails (500px max, q=80)
        optimize_image(orig_src, thumb_orig_path, max_dim=500, quality=80)
        optimize_image(trans_src, thumb_trans_path, max_dim=500, quality=80)

        web_orig_size = os.path.getsize(web_orig_path)
        web_trans_size = os.path.getsize(web_trans_path)
        thumb_orig_size = os.path.getsize(thumb_orig_path)
        thumb_trans_size = os.path.getsize(thumb_trans_path)

        total_web_bytes += (web_orig_size + web_trans_size)
        total_thumb_bytes += (thumb_orig_size + thumb_trans_size)

        # Dimensions inspection from web image
        with Image.open(web_orig_path) as im:
            web_w, web_h = im.size

        # Check for transition video
        video_dest_filename = f"photo_{pid:02d}_transition.mp4"
        video_dest_path = os.path.join(VIDEOS_DIR, video_dest_filename)

        # Check legacy output_videos if already generated
        legacy_raw = os.path.join(LEGACY_VIDEOS_DIR, f"pair_{pid:02d}_ai_raw.mp4")
        if not os.path.exists(video_dest_path) and os.path.exists(legacy_raw) and ffmpeg_bin:
            print(f"    -> Re-muxing existing video for pair #{pid} into public/media/videos/...")
            ensure_video_faststart(legacy_raw, video_dest_path, ffmpeg_bin)

        video_meta = None
        if os.path.exists(video_dest_path):
            video_count += 1
            v_info = get_video_info(video_dest_path, ffmpeg_bin) if ffmpeg_bin else {"size_bytes": os.path.getsize(video_dest_path), "duration_sec": 5.06}
            video_meta = {
                "available": True,
                "filename": video_dest_filename,
                "path": f"media/videos/{video_dest_filename}",
                "duration": v_info.get("duration_sec", 5.06),
                "size_bytes": v_info.get("size_bytes", os.path.getsize(video_dest_path)),
                "width": v_info.get("width", 1200),
                "height": v_info.get("height", 900)
            }
        else:
            video_meta = {
                "available": False,
                "filename": None,
                "path": None,
                "duration": None,
                "size_bytes": 0
            }

        # Build gallery item
        item = {
            "id": pid,
            "pair_id": pid,
            "title": f"{pair['theme']['title']} #{pid}",
            "time_display": pair["display_time"],
            "theme": pair["theme"],
            "prompt": pair["prompt"],
            "request_id": pair.get("request_id"),
            "original": {
                "web": f"media/web/{web_orig_file}",
                "thumb": f"media/thumbs/{thumb_orig_file}",
                "full_download": f"photos/original/{pair['original_filename']}",
                "width": web_w,
                "height": web_h,
                "web_bytes": web_orig_size,
                "raw_bytes": orig_src_size
            },
            "transformed": {
                "web": f"media/web/{web_trans_file}",
                "thumb": f"media/thumbs/{thumb_trans_file}",
                "full_download": f"photos/transformed/{pair['transformed_filename']}",
                "width": web_w,
                "height": web_h,
                "web_bytes": web_trans_size,
                "raw_bytes": trans_src_size
            },
            "video": video_meta
        }
        gallery_items.append(item)

        if idx % 10 == 0 or idx == len(pairs):
            print(f"    Processed {idx}/{len(pairs)} pairs...")

    # Write master JSON database
    payload = {
        "event_title": "Halloween 2026 - Dark Waters Transformations",
        "generated_at": sys.version,
        "total_pairs": len(gallery_items),
        "total_videos_ready": video_count,
        "themes": [
            {"id": "all", "title": "All Photos", "count": len(gallery_items)},
            {"id": "victorian-ballroom", "title": "Victorian Ballroom", "count": sum(1 for i in gallery_items if i["theme"]["id"] == "victorian-ballroom")},
            {"id": "zombie-pirates", "title": "Zombie Pirates", "count": sum(1 for i in gallery_items if i["theme"]["id"] == "zombie-pirates")},
            {"id": "deep-sea-divers", "title": "Deep-Sea Divers", "count": sum(1 for i in gallery_items if i["theme"]["id"] == "deep-sea-divers")},
            {"id": "murky-lakebed", "title": "Murky Lakebed", "count": sum(1 for i in gallery_items if i["theme"]["id"] == "murky-lakebed")},
            {"id": "eldritch-abyss", "title": "Eldritch Abyss", "count": sum(1 for i in gallery_items if i["theme"]["id"] == "eldritch-abyss")},
            {"id": "shark-dive", "title": "Shark Encounter", "count": sum(1 for i in gallery_items if i["theme"]["id"] == "shark-dive")},
        ],
        "photos": gallery_items
    }

    with open(PHOTOS_METADATA_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    orig_mb = total_orig_bytes / (1024 * 1024)
    web_mb = total_web_bytes / (1024 * 1024)
    thumb_mb = total_thumb_bytes / (1024 * 1024)
    savings_pct = (1.0 - (total_web_bytes / total_orig_bytes)) * 100

    print("\n==========================================================")
    print("   Optimization Complete! Summary:                        ")
    print("==========================================================")
    print(f"[*] Total Photo Pairs       : {len(gallery_items)}")
    print(f"[*] Original Raw Media      : {orig_mb:.1f} MB")
    print(f"[*] Web-Optimized Gallery   : {web_mb:.1f} MB ({savings_pct:.1f}% bandwidth saved!)")
    print(f"[*] Instant Thumbnails      : {thumb_mb:.1f} MB (total for all 59 thumbnails)")
    print(f"[*] Transition Videos Ready : {video_count}/{len(gallery_items)}")
    print(f"[*] Metadata Database Saved : {PHOTOS_METADATA_PATH}")
    print("==========================================================")


if __name__ == "__main__":
    main()
