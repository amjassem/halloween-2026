# Dark Waters • Halloween 2026 Transformations

A gallery website and transformation pipeline built for sharing original party photos and their AI-transformed counterparts with guests.

Designed for free-tier deployment on **Cloudflare Pages**.

---

## 🌟 Key Features

- **Untransformed Gallery Base**: The main gallery displays the original, untransformed party photos.
- **Atmospheric Dark Waters Aesthetic**: Reuses the floating bioluminescent particle canvas from the photobooth project (`#03080e`, `--teal-glow`, `Cinzel` & `Outfit` typography).
- **Interactive Lightbox with 3 Viewing Modes**:
  1. **Photo Slider**: Drag the split-handle to peel between the untransformed original and the AI-transformed photo.
  2. **Video Slider**: Slide the original photo directly over the living **5-second AI video loop**!
  3. **Video Player**: Full-featured video player with play/pause, looping, scrubber, and time display.
- **Download Action Bar**:
  - 📥 **Download Original**: Full-resolution raw JPEG (3264 × 2448)
  - ✨ **Download Transformed**: Full-resolution raw PNG (1195 × 896)
  - 🎬 **Download Video**: 5-second web-optimized MP4 transition video
- **Theme Filtering**: Filter photos by AI realm (*Victorian Ballroom*, *Zombie Pirates*, *Deep-Sea Divers*, *Murky Lakebed*, *Eldritch Abyss*, *Shark Encounter*).
- **Mobile & Desktop First**: Full touch pointer dragging, swipe navigation between photos, and keyboard controls (`ArrowLeft`, `ArrowRight`, `Space`, `[` / `]`, `Esc`).
- **Direct Deep-Linking**: Share direct links like `https://yoursite.pages.dev/#photo-12`.

---

## 🚀 Local Preview

To preview the website locally in your browser:

```bash
python3 -m http.server 8080 -d public
```
Then open [http://localhost:8080](http://localhost:8080) in your web browser.

---

## ☁️ Deploying to Cloudflare Pages (100% Free)

The website is 100% static and requires zero build steps or server maintenance.

### Option 1: Direct Drag-and-Drop (Easiest & Fastest)
1. Log in to [dash.cloudflare.com](https://dash.cloudflare.com/).
2. Navigate to **Workers & Pages** $\rightarrow$ **Create Application** $\rightarrow$ **Pages** $\rightarrow$ **Upload assets**.
3. Name your project (e.g. `halloween-2026`).
4. Drag and drop the `public/` directory into the upload box.
5. Click **Deploy Site** — your site goes live instantly on Cloudflare's global edge network with free SSL (`*.pages.dev`).

### Option 2: Wrangler CLI
```bash
npx wrangler pages deploy public --project-name halloween-2026
```

### Option 3: GitHub Integration
1. Push this repository to GitHub.
2. In Cloudflare Pages, connect your GitHub repository.
3. Configure build settings:
   - **Framework preset**: `None`
   - **Build output directory**: `public`
4. Deploy! Cloudflare will automatically re-deploy whenever you push new changes.

---

## 🛠️ Media & Transformation Tools

All scripts are located in `src/transform/`:

### 1. Media Optimizer (`optimize_media.py`)
Generates responsive 1600px WebP images and 500px thumbnails (94.4% bandwidth reduction), re-muxes videos with `+faststart`, and compiles `public/data/photos.json`:
```bash
python3 src/transform/optimize_media.py
```

### 2. Batch AI Video Generator (`generate_all_videos.py`)
Generates 5-second AI transition videos via fal.ai (`fal-ai/wan-flf2v`) with up to 10 concurrent requests:
```bash
# Check status and pending items without calling the API:
python3 src/transform/generate_all_videos.py --dry-run

# Generate all remaining videos (10 concurrent workers):
python3 src/transform/generate_all_videos.py --concurrency 10

# Generate next 5 videos only:
python3 src/transform/generate_all_videos.py --limit 5
```

