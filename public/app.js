/**
 * DARK WATERS • Halloween 2026 Transformations
 * Main Application Logic & Interactive Before/After Engine
 */

class DarkWatersGallery {
  constructor() {
    // State
    this.photos = [];
    this.filteredPhotos = [];
    this.currentTheme = "all";
    this.currentIndex = 0;
    this.currentMode = "photo-slider"; // 'photo-slider' | 'full-video'
    this.preferredMode = "photo-slider";
    this.sliderPos = 50; // percentage
    this.isDragging = false;
    this.isVideoScrubbing = false;
    this.touchStartX = 0;
    this.touchStartY = 0;

    // DOM Elements - Shell
    this.galleryGrid = document.getElementById("gallery-grid");
    this.galleryEmpty = document.getElementById("gallery-empty");
    this.filterPills = document.getElementById("filter-pills");
    this.statVideosReady = document.getElementById("stat-videos-ready");
    this.btnResetFilter = document.getElementById("btn-reset-filter");
    this.toast = document.getElementById("toast");
    this.toastMessage = document.getElementById("toast-message");

    // DOM Elements - Modal & Lightbox
    this.modal = document.getElementById("modal");
    this.btnCloseModal = document.getElementById("btn-close-modal");
    this.btnPrev = document.getElementById("btn-prev-photo");
    this.btnNext = document.getElementById("btn-next-photo");
    this.modalTitle = document.getElementById("modal-title");
    this.modalThemeBadge = document.getElementById("modal-theme-badge");
    this.modalTime = document.getElementById("modal-time");
    this.btnTogglePrompt = document.getElementById("btn-toggle-prompt");
    this.promptDrawer = document.getElementById("modal-prompt-drawer");
    this.promptText = document.getElementById("modal-prompt-text");
    this.btnShare = document.getElementById("btn-share");

    // DOM Elements - Stage & Slider
    this.stage = document.getElementById("comparison-stage");
    this.stageOrigImg = document.getElementById("stage-orig-img");
    this.stageTransImg = document.getElementById("stage-trans-img");
    this.stageVideo = document.getElementById("stage-video");
    this.sliderHandle = document.getElementById("slider-handle");
    this.stageLoader = document.getElementById("stage-loader");
    this.btnShowOrig = document.getElementById("btn-show-original");
    this.btnShowTrans = document.getElementById("btn-show-transformed");

    // DOM Elements - Mode Bar
    this.modePhotoSlider = document.getElementById("mode-photo-slider");
    this.modeFullVideo = document.getElementById("mode-full-video");

    // DOM Elements - Video Controls
    this.videoControlsBar = document.getElementById("video-controls-bar");
    this.btnVideoPlay = document.getElementById("btn-video-play");
    this.iconPlay = document.getElementById("icon-play");
    this.iconPause = document.getElementById("icon-pause");
    this.videoTimeSlider = document.getElementById("video-time-slider");
    this.videoTimeDisplay = document.getElementById("video-time-display");
    this.btnVideoLoop = document.getElementById("btn-video-loop");

    // DOM Elements - Download Bar
    this.btnDlOrig = document.getElementById("btn-dl-orig");
    this.btnDlTrans = document.getElementById("btn-dl-trans");
    this.btnDlVideo = document.getElementById("btn-dl-video");
    this.dlOrigSize = document.getElementById("dl-orig-size");
    this.dlTransSize = document.getElementById("dl-trans-size");
    this.dlVideoSize = document.getElementById("dl-video-size");

    // Ambient Canvas
    this.canvas = document.getElementById("ambient-canvas");
    this.ctx = this.canvas ? this.canvas.getContext("2d") : null;
    this.particles = [];
    this.animFrameId = null;

    // Initialization
    this.initAmbientCanvas();
    this.initEventListeners();
    this.loadData();
  }

  /* ========================================================
     1. AMBIENT BIOLUMINESCENT PARTICLES (Reused from Photobooth)
     ======================================================== */
  initAmbientCanvas() {
    if (!this.canvas || !this.ctx) return;
    this.resizeCanvas();
    window.addEventListener("resize", () => this.resizeCanvas());

    // Generate floating particulate motes
    const numParticles = Math.min(80, Math.floor(window.innerWidth / 16));
    this.particles = [];
    for (let i = 0; i < numParticles; i++) {
      this.particles.push({
        x: Math.random() * window.innerWidth,
        y: Math.random() * window.innerHeight,
        radius: Math.random() * 2.2 + 0.8,
        vx: (Math.random() - 0.5) * 0.35,
        vy: -Math.random() * 0.45 - 0.15, // upward aquatic drift
        alpha: Math.random() * 0.55 + 0.2,
        pulseSpeed: Math.random() * 0.02 + 0.01,
      });
    }

    this.renderCanvas();

    // Pause rendering when tab is hidden to save battery
    document.addEventListener("visibilitychange", () => {
      if (document.hidden) {
        if (this.animFrameId) {
          cancelAnimationFrame(this.animFrameId);
          this.animFrameId = null;
        }
      } else {
        if (!this.animFrameId) this.renderCanvas();
      }
    });
  }

  resizeCanvas() {
    if (!this.canvas) return;
    this.canvas.width = window.innerWidth;
    this.canvas.height = window.innerHeight;
  }

  renderCanvas() {
    if (!this.ctx || !this.canvas) return;

    const w = this.canvas.width;
    const h = this.canvas.height;
    const t = Date.now() * 0.001;

    // Deep aquatic gradient
    const grad = this.ctx.createLinearGradient(0, 0, 0, h);
    grad.addColorStop(0, "#020b12");
    grad.addColorStop(0.5, "#041624");
    grad.addColorStop(1, "#010609");
    this.ctx.fillStyle = grad;
    this.ctx.fillRect(0, 0, w, h);

    // Subtle caustic wave
    const waveY = h * 0.35 + Math.sin(t * 0.7) * 35;
    const causticGrad = this.ctx.createRadialGradient(w * 0.5, waveY, 50, w * 0.5, waveY, w * 0.75);
    causticGrad.addColorStop(0, "rgba(11, 243, 200, 0.055)");
    causticGrad.addColorStop(1, "transparent");
    this.ctx.fillStyle = causticGrad;
    this.ctx.fillRect(0, 0, w, h);

    // Particulate motes
    for (const p of this.particles) {
      p.x += p.vx + Math.sin(t + p.y * 0.01) * 0.25;
      p.y += p.vy;

      if (p.y < -10) {
        p.y = h + 10;
        p.x = Math.random() * w;
      }
      if (p.x < -10) p.x = w + 10;
      if (p.x > w + 10) p.x = -10;

      const alphaPulse = p.alpha + Math.sin(t * 2.5 + p.radius) * 0.12;
      this.ctx.beginPath();
      this.ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
      this.ctx.fillStyle = `rgba(11, 243, 200, ${Math.max(0.04, alphaPulse)})`;
      this.ctx.shadowBlur = 8;
      this.ctx.shadowColor = "rgba(11, 243, 200, 0.35)";
      this.ctx.fill();
    }
    this.ctx.shadowBlur = 0;

    this.animFrameId = requestAnimationFrame(() => this.renderCanvas());
  }

  /* ========================================================
     2. DATA LOADING & RENDERING
     ======================================================== */
  async loadData() {
    try {
      const res = await fetch("data/photos.json");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();

      this.photos = data.photos || [];
      this.filteredPhotos = [...this.photos];

      // Update Header Stats
      if (this.statVideosReady) this.statVideosReady.textContent = "59 morphs ready";

      // Render Theme Filter Pills
      this.renderThemePills(data.themes || []);

      // Render Gallery
      this.renderGallery();

      // Check URL Hash (e.g. #photo-12)
      this.handleInitialHash();

    } catch (err) {
      console.error("[DarkWaters] Error loading photos.json:", err);
      this.galleryGrid.innerHTML = `
        <div style="grid-column: 1/-1; text-align: center; padding: 4rem 1rem; color: #ff6b6b;">
          <h3>Failed to load gallery data</h3>
          <p style="color: var(--text-muted); margin-top: 0.5rem;">Could not load data/photos.json. Please verify that media optimization has run.</p>
        </div>
      `;
    }
  }

  renderThemePills(themes) {
    if (!this.filterPills) return;
    
    // Clear and build pills
    this.filterPills.innerHTML = "";

    themes.forEach(theme => {
      const btn = document.createElement("button");
      btn.className = `filter-pill ${theme.id === this.currentTheme ? "active" : ""}`;
      btn.dataset.theme = theme.id;
      btn.innerHTML = `
        <span class="pill-title">${this.escapeHtml(theme.title)}</span>
        <span class="pill-count">${theme.count}</span>
      `;
      btn.addEventListener("click", () => this.setThemeFilter(theme.id));
      this.filterPills.appendChild(btn);
    });
  }

  setThemeFilter(themeId) {
    this.currentTheme = themeId;

    // Update active pill styling
    const pills = this.filterPills.querySelectorAll(".filter-pill");
    pills.forEach(p => {
      p.classList.toggle("active", p.dataset.theme === themeId);
    });

    // Filter photo list
    if (themeId === "all") {
      this.filteredPhotos = [...this.photos];
    } else {
      this.filteredPhotos = this.photos.filter(p => p.theme?.id === themeId);
    }

    this.renderGallery();
  }

  renderGallery() {
    if (!this.galleryGrid) return;

    if (this.filteredPhotos.length === 0) {
      this.galleryGrid.innerHTML = "";
      this.galleryEmpty?.classList.remove("hidden");
      return;
    }

    this.galleryEmpty?.classList.add("hidden");
    this.galleryGrid.innerHTML = "";

    const fragment = document.createDocumentFragment();

    this.filteredPhotos.forEach((photo) => {
      const card = document.createElement("article");
      card.className = "photo-card";
      card.setAttribute("role", "button");
      card.setAttribute("tabindex", "0");
      card.setAttribute("aria-label", `View ${photo.title}`);

      const hasVideo = photo.video && photo.video.available;
      const themeColor = photo.theme?.color || "cyan";

      card.innerHTML = `
        <div class="card-image-wrap">
          <!-- UNTRANSFORMED PHOTO THUMBNAIL (As requested) -->
          <img 
            class="card-img" 
            src="${photo.original.thumb}" 
            alt="Original photo from party" 
            loading="lazy" 
            width="500" 
            height="375"
          >
          
          <div class="card-overlay">
            <div class="card-header-meta">
              <span class="card-badge" style="border-color: var(--teal-dim);">
                ${this.escapeHtml(photo.theme?.tag || "Party")}
              </span>
              <span class="card-time">${photo.time_display || ""}</span>
            </div>

            <div class="card-footer-meta">
              <div class="card-title">Photo #${String(photo.id).padStart(2, "0")}</div>
              <span class="card-reveal-hint">
                <span>Reveal</span>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="9 18 15 12 9 6"/></svg>
              </span>
            </div>
          </div>
        </div>
      `;

      card.addEventListener("click", () => this.openModal(photo.id));
      card.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          this.openModal(photo.id);
        }
      });

      fragment.appendChild(card);
    });

    this.galleryGrid.appendChild(fragment);
  }

  /* ========================================================
     3. INTERACTIVE LIGHTBOX & COMPARISON ENGINE
     ======================================================== */
  openModal(photoId) {
    const idx = this.filteredPhotos.findIndex(p => p.id === photoId);
    if (idx === -1) return;

    this.currentIndex = idx;
    const photo = this.filteredPhotos[this.currentIndex];

    // Maintain preferred view mode (photo-slider or full-video) across navigation
    const hasVideo = !!(photo.video && photo.video.available);
    if (this.preferredMode === "full-video" && hasVideo) {
      this.currentMode = "full-video";
    } else {
      this.currentMode = "photo-slider";
    }
    this.sliderPos = 50;
    this.updateSliderUI();

    // Populate metadata
    this.modalTitle.textContent = `Photo #${String(photo.id).padStart(2, "0")}`;
    this.modalThemeBadge.textContent = photo.theme?.title || "Transformation";
    this.modalTime.textContent = photo.time_display || "";
    this.promptText.textContent = photo.prompt || "No prompt recorded.";
    this.promptDrawer.classList.add("hidden");

    // Configure Video Availability on Mode Pills
    if (this.modeFullVideo) {
      this.modeFullVideo.classList.toggle("disabled", !hasVideo);
      this.modeFullVideo.title = hasVideo
        ? "Watch full AI video morph with time scrubber"
        : "Video morph still in progress for this photo";
    }

    // Load High-Res Media
    this.loadStageMedia(photo);

    // Setup Download Links
    this.setupDownloads(photo);

    // Update URL hash without scroll jump
    history.replaceState(null, "", `#photo-${photo.id}`);

    // Show modal & prevent background scroll
    this.modal.classList.remove("hidden");
    document.body.style.overflow = "hidden";
  }

  closeModal() {
    this.modal.classList.add("hidden");
    document.body.style.overflow = "";

    // Stop video playback
    if (this.stageVideo) {
      this.stageVideo.pause();
      this.stageVideo.currentTime = 0;
      this.stageVideo.src = "";
    }

    // Clear hash
    history.replaceState(null, "", window.location.pathname + window.location.search);
  }

  loadStageMedia(photo) {
    this.stageLoader.classList.remove("hidden");

    // Load Original Image
    this.stageOrigImg.src = photo.original.web;
    
    // Load Transformed Image
    this.stageTransImg.src = photo.transformed.web;

    // Load Video if available
    if (photo.video && photo.video.available) {
      this.stageVideo.src = photo.video.path;
      this.stageVideo.load();
    } else {
      this.stageVideo.src = "";
    }

    let loadedCount = 0;
    const onLoaded = () => {
      loadedCount++;
      if (loadedCount >= 2) {
        this.stageLoader.classList.add("hidden");
      }
    };

    if (this.stageOrigImg.complete) loadedCount++;
    else this.stageOrigImg.onload = onLoaded;

    if (this.stageTransImg.complete) loadedCount++;
    else this.stageTransImg.onload = onLoaded;

    if (loadedCount >= 2) this.stageLoader.classList.add("hidden");

    this.setViewMode(this.currentMode);
  }

  setViewMode(mode) {
    const photo = this.filteredPhotos[this.currentIndex];
    const hasVideo = !!(photo.video && photo.video.available);

    if (mode === "full-video" && !hasVideo) {
      mode = "photo-slider";
    }

    this.currentMode = mode;

    // Update Mode Pills
    this.modePhotoSlider?.classList.toggle("active", mode === "photo-slider");
    this.modeFullVideo?.classList.toggle("active", mode === "full-video");

    // Configure Stage Display
    this.stage.classList.toggle("full-video-mode", mode === "full-video");
    this.videoControlsBar?.classList.toggle("hidden", mode !== "full-video");

    if (mode === "photo-slider") {
      this.stageTransImg.classList.remove("hidden");
      this.stageVideo.classList.add("hidden");
      this.stageVideo.pause();
    } else if (mode === "full-video") {
      this.stageTransImg.classList.add("hidden");
      this.stageVideo.classList.remove("hidden");
      this.stageVideo.play().catch(() => {});
      this.updateVideoPlayPauseIcon();
      this.updateVideoTimeDisplay();
    }
  }

  setupDownloads(photo) {
    // 1. Original Download
    this.btnDlOrig.href = photo.original.full_download;
    this.btnDlOrig.setAttribute("download", photo.original.full_download.split("/").pop());
    const origMb = (photo.original.raw_bytes / (1024 * 1024)).toFixed(1);
    this.dlOrigSize.textContent = `${origMb} MB • JPG`;

    // 2. Transformed Download
    this.btnDlTrans.href = photo.transformed.full_download;
    this.btnDlTrans.setAttribute("download", photo.transformed.full_download.split("/").pop());
    const transMb = (photo.transformed.raw_bytes / (1024 * 1024)).toFixed(1);
    this.dlTransSize.textContent = `${transMb} MB • PNG`;

    // 3. Video Download
    if (photo.video && photo.video.available) {
      this.btnDlVideo.href = photo.video.path;
      this.btnDlVideo.setAttribute("download", photo.video.filename || `photo_${photo.id}_transition.mp4`);
      this.btnDlVideo.classList.remove("disabled");
      const videoMb = (photo.video.size_bytes / (1024 * 1024)).toFixed(1);
      this.dlVideoSize.textContent = `${videoMb} MB • MP4`;
      this.btnDlVideo.title = "Download 5s AI Video Transition";
    } else {
      this.btnDlVideo.removeAttribute("href");
      this.btnDlVideo.classList.add("disabled");
      this.dlVideoSize.textContent = "In progress...";
      this.btnDlVideo.title = "Video transition rendering soon";
    }
  }

  nextPhoto() {
    if (this.filteredPhotos.length <= 1) return;
    this.currentIndex = (this.currentIndex + 1) % this.filteredPhotos.length;
    this.openModal(this.filteredPhotos[this.currentIndex].id);
  }

  prevPhoto() {
    if (this.filteredPhotos.length <= 1) return;
    this.currentIndex = (this.currentIndex - 1 + this.filteredPhotos.length) % this.filteredPhotos.length;
    this.openModal(this.filteredPhotos[this.currentIndex].id);
  }

  /* ========================================================
     4. DRAGGABLE SPLIT-SLIDER CONTROLS
     ======================================================== */
  updateSliderUI() {
    this.stage.style.setProperty("--slider-pos", `${this.sliderPos}%`);
    this.btnShowOrig?.classList.toggle("active", this.sliderPos === 0);
    this.btnShowTrans?.classList.toggle("active", this.sliderPos === 100);
  }

  setSliderFromPointer(clientX) {
    const rect = this.stage.getBoundingClientRect();
    const x = clientX - rect.left;
    const width = rect.width;
    if (width <= 0) return;

    let percent = (x / width) * 100;
    percent = Math.max(0, Math.min(100, percent));
    this.sliderPos = Math.round(percent * 10) / 10;
    this.updateSliderUI();
  }

  /* ========================================================
     5. VIDEO CONTROLS
     ======================================================== */
  toggleVideoPlay() {
    if (!this.stageVideo) return;
    if (this.stageVideo.paused) {
      this.stageVideo.play();
    } else {
      this.stageVideo.pause();
    }
    this.updateVideoPlayPauseIcon();
  }

  updateVideoPlayPauseIcon() {
    const isPaused = this.stageVideo.paused;
    this.iconPlay.classList.toggle("hidden", !isPaused);
    this.iconPause.classList.toggle("hidden", isPaused);
  }

  updateVideoTimeDisplay() {
    if (!this.stageVideo || !this.videoTimeDisplay) return;
    const cur = this.stageVideo.currentTime || 0;
    const dur = this.stageVideo.duration || 5;
    const format = (sec) => {
      const m = Math.floor(sec / 60);
      const s = Math.floor(sec % 60);
      return `${m}:${s < 10 ? '0' : ''}${s}`;
    };
    this.videoTimeDisplay.textContent = `${format(cur)} / ${format(dur)}`;
  }

  /* ========================================================
     6. EVENT LISTENERS
     ======================================================== */
  initEventListeners() {
    // Reset Filter Button
    this.btnResetFilter?.addEventListener("click", () => this.setThemeFilter("all"));

    // Modal Close
    this.btnCloseModal?.addEventListener("click", () => this.closeModal());
    this.modal?.addEventListener("click", (e) => {
      if (e.target === this.modal) this.closeModal();
    });

    // Navigation Buttons
    this.btnNext?.addEventListener("click", (e) => {
      e.stopPropagation();
      this.nextPhoto();
    });
    this.btnPrev?.addEventListener("click", (e) => {
      e.stopPropagation();
      this.prevPhoto();
    });

    // Toggle Prompt Drawer
    this.btnTogglePrompt?.addEventListener("click", () => {
      this.promptDrawer.classList.toggle("hidden");
    });

    // Share Button
    this.btnShare?.addEventListener("click", () => {
      const url = window.location.href;
      if (navigator.clipboard) {
        navigator.clipboard.writeText(url).then(() => {
          this.showToast("Link copied to clipboard!");
        }).catch(() => {
          this.showToast(url);
        });
      } else {
        this.showToast("Direct link: " + url);
      }
    });

    // Mode Selector Buttons
    this.modePhotoSlider?.addEventListener("click", () => {
      this.preferredMode = "photo-slider";
      this.setViewMode("photo-slider");
    });
    this.modeFullVideo?.addEventListener("click", () => {
      this.preferredMode = "full-video";
      this.setViewMode("full-video");
    });

    // Clickable Original & Transformed Badges (Snap to 0% Original / 100% Transformed)
    this.btnShowOrig?.addEventListener("click", (e) => {
      e.stopPropagation();
      this.sliderPos = 0;
      this.updateSliderUI();
    });

    this.btnShowTrans?.addEventListener("click", (e) => {
      e.stopPropagation();
      this.sliderPos = 100;
      this.updateSliderUI();
    });

    // Slider Drag (Mouse & Touch Pointer Events)
    const onPointerDown = (e) => {
      if (this.currentMode === "full-video") return;
      this.isDragging = true;
      this.sliderHandle.classList.add("dragging");
      this.setSliderFromPointer(e.clientX);
    };

    const onPointerMove = (e) => {
      if (!this.isDragging) return;
      this.setSliderFromPointer(e.clientX);
    };

    const onPointerUp = () => {
      if (this.isDragging) {
        this.isDragging = false;
        this.sliderHandle.classList.remove("dragging");
      }
    };

    this.stage?.addEventListener("pointerdown", onPointerDown);
    window.addEventListener("pointermove", onPointerMove);
    window.addEventListener("pointerup", onPointerUp);
    window.addEventListener("pointercancel", onPointerUp);

    // Mobile Swipe Navigation - Disabled within photo stage and video slider controls
    this.touchBlockSwipe = false;

    this.modal?.addEventListener("touchstart", (e) => {
      const touch = e.changedTouches[0];
      this.touchStartX = touch.clientX;
      this.touchStartY = touch.clientY;

      // Disable swiping if touch originates anywhere inside the photo stage, stage wrapper, video controls, or download bar
      const target = e.target;
      if (target && target.closest(".stage-wrapper, .comparison-stage, #video-controls-bar, .video-slider-wrap, .modal-download-bar")) {
        this.touchBlockSwipe = true;
      } else {
        this.touchBlockSwipe = false;
      }
    }, { passive: true });

    this.modal?.addEventListener("touchend", (e) => {
      // Never switch photos if touch originated or ended in the photo frame/controls, or while dragging/scrubbing
      if (this.touchBlockSwipe || this.isDragging || this.isVideoScrubbing) {
        this.touchBlockSwipe = false;
        return;
      }

      const endTarget = e.target;
      if (endTarget && endTarget.closest(".stage-wrapper, .comparison-stage, #video-controls-bar, .video-slider-wrap, .modal-download-bar")) {
        return;
      }

      const diffX = e.changedTouches[0].clientX - this.touchStartX;
      const diffY = e.changedTouches[0].clientY - this.touchStartY;

      // Horizontal swipe threshold (only applies outside the photo frame)
      if (Math.abs(diffX) > 60 && Math.abs(diffX) > Math.abs(diffY) * 1.5) {
        if (diffX < 0) this.nextPhoto();
        else this.prevPhoto();
      }
    }, { passive: true });

    // Video Player Events & Time Scrubber Slider
    this.btnVideoPlay?.addEventListener("click", () => this.toggleVideoPlay());
    this.btnVideoLoop?.addEventListener("click", () => {
      this.stageVideo.loop = !this.stageVideo.loop;
      this.btnVideoLoop.classList.toggle("active", this.stageVideo.loop);
    });

    // Scrubber input & change
    this.videoTimeSlider?.addEventListener("input", () => {
      this.isVideoScrubbing = true;
      if (this.stageVideo && this.stageVideo.duration) {
        const time = (parseFloat(this.videoTimeSlider.value) / 100) * this.stageVideo.duration;
        this.stageVideo.currentTime = time;
        this.updateVideoTimeDisplay();
      }
    });

    this.videoTimeSlider?.addEventListener("change", () => {
      this.isVideoScrubbing = false;
    });

    this.stageVideo?.addEventListener("timeupdate", () => {
      if (!this.stageVideo || !this.stageVideo.duration) return;
      if (!this.isVideoScrubbing && this.videoTimeSlider) {
        const pct = (this.stageVideo.currentTime / this.stageVideo.duration) * 100;
        this.videoTimeSlider.value = pct;
      }
      this.updateVideoTimeDisplay();
    });

    this.stageVideo?.addEventListener("ended", () => {
      if (!this.stageVideo.loop) {
        this.updateVideoPlayPauseIcon();
      }
    });

    // Keyboard Shortcuts
    window.addEventListener("keydown", (e) => {
      if (this.modal.classList.contains("hidden")) return;

      if (e.key === "Escape") {
        this.closeModal();
      } else if (e.key === "ArrowLeft") {
        this.prevPhoto();
      } else if (e.key === "ArrowRight") {
        this.nextPhoto();
      } else if (e.key === " ") {
        e.preventDefault();
        if (this.currentMode === "full-video") {
          this.toggleVideoPlay();
        } else {
          // Toggle between min (0 = full original) and max (100 = full transformed)
          this.sliderPos = this.sliderPos === 0 ? 100 : 0;
          this.updateSliderUI();
        }
      } else if (e.key === "[" || e.key === "{") {
        this.sliderPos = Math.max(0, this.sliderPos - 5);
        this.updateSliderUI();
      } else if (e.key === "]" || e.key === "}") {
        this.sliderPos = Math.min(100, this.sliderPos + 5);
        this.updateSliderUI();
      }
    });

    // Listen for Hash Changes (e.g. browser back/forward)
    window.addEventListener("hashchange", () => {
      this.handleInitialHash();
    });
  }

  handleInitialHash() {
    const hash = window.location.hash;
    if (hash && hash.startsWith("#photo-")) {
      const id = parseInt(hash.replace("#photo-", ""), 10);
      if (!isNaN(id)) {
        this.openModal(id);
      }
    }
  }

  showToast(message) {
    if (!this.toast || !this.toastMessage) return;
    this.toastMessage.textContent = message;
    this.toast.classList.remove("hidden");
    setTimeout(() => {
      this.toast.classList.add("hidden");
    }, 2800);
  }

  escapeHtml(str) {
    if (!str) return "";
    return str
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }
}

// Instantiate on DOM Ready
document.addEventListener("DOMContentLoaded", () => {
  window.darkWatersGallery = new DarkWatersGallery();
});
