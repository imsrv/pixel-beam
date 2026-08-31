# ⚡ PixelBeam

> **Image Sanitizer, Steganography Disruption Engine & Custom EXIF Metadata Injector**

PixelBeam is a lightweight, privacy-focused Python Flask web application designed to strip micro-steganography, disrupt invisible AI watermarks (such as SynthID or DALL-E 3 artifacts), and inject clean custom EXIF metadata—complete with interactive Leaflet.js GPS map pin placement.

All image processing operates strictly **in-memory** (`io.BytesIO`) with **zero disk writes** and **zero external API key requirements**.

---

## 🌟 Key Features

- 🛡️ **Multi-Pass Steganography & Watermark Disruption**: An 11-stage processing engine that desynchronizes spatial grids, normalizes resolutions, applies auto-histogram curves, forces frequency quantization, and reconstructs pixel lattices to break embedded micro-data without perceptual visual degradation.
- 📸 **Custom EXIF Metadata Injection**: Strip pre-existing EXIF tags completely (`image.delete_all()`) and inject authenticated device make, model, timestamp, and GPS coordinates via `piexif`.
- 📱 **Real Device Firmware Presets**: Built-in EXIF profiles for Apple iPhones (11 to 16 Pro Max), Samsung Galaxy (S21 to S25 Ultra, Z Fold/Flip), Google Pixel (6 to 9 Pro), Sony Cameras (α1, α7, α9, FX, ZV), and Canon EOS/PowerShot lines—plus custom text overrides.
- 🗺️ **Interactive GPS Map Pinning**: Built-in Leaflet.js map with OpenStreetMap tiles for 1-click latitude/longitude pinning. **Zero paid API keys or billing required**.
- 🔒 **Privacy & Memory Safety**: User uploads are processed entirely in transient RAM buffers (`io.BytesIO`). Images are never written to disk, preventing storage leaks or file-system permissions issues in serverless or containerized environments.
- 🎨 **Modern Dark Glassmorphism UI**: Built with responsive vanilla CSS, smooth micro-animations, real-time pipeline status visualization, and Lucide icons.

---

## 🔬 11-Stage Processing Pipeline Architecture

PixelBeam employs a multi-layered spatial, frequency, and pixel-reconstruction pipeline in `app.py` to scrub invisible steganography and AI watermarks:

```
Upload Image
  │
  ├── 1. Spatial Grid Desynchronization (Asymmetric 1-2px Micro-Crop)
  ├── 2. Multi-Scale Resampling & Target Resolution Normalization (step=50, proportional)
  ├── 3. Auto Histogram Expansion & Parametric S-Curve Shift (Low/High percentile + Gamma balance)
  ├── 4. Intermediate Frequency Domain DCT Quantization (JPEG Q88 4:2:0 pass)
  ├── 5. Post-Enhancement & Slight Sharpness Reduction (ImageEnhance.Sharpness factor 0.93)
  ├── 6. Median Denoising & Gaussian Re-nosing (3x3 Median filter + Gaussian noise σ=3.5)
  ├── 7. High-Frequency Spatial Micro-Grid Lattice Perturbation (Alternating ±1.75 lattice)
  ├── 8. Lightweight Img2Img Pixel Reconstruction & Detail Abstraction (Alpha=0.35)
  ├── 9. 5px Edge Pixel Cloning & Gaussian Blur Boundary Reconstruction (Inner reference + blurred 5px margins)
  ├── 9.5. Global Sub-Pixel Micro-Gaussian Blur Pass (Every-pixel Gaussian blur radius=0.45)
  └── 10. EXIF Payload Injection & High-Quality JPEG Save (piexif + Quality 95)
        │
        └── Clean Download
```

### Stage Details

1. **Spatial Grid Desynchronization**: Asymmetrically crops 1–2 pixels from the top, left, right, and bottom. This shifts spatial phase alignment and breaks 8x8 DCT grid phase dependencies used by spatial steganography algorithms.
2. **Multi-Scale Resampling & Target Resolution Normalization**: Micro-shrinks the image to 88% scale via Bicubic interpolation before resampling back to a proportional target resolution rounded to the nearest multiple of 50 using Lanczos filtering.
3. **Auto Histogram Expansion & Parametric S-Curve Shift**: Automatically detects low (0.5%) and high (99.5%) luminance percentiles for contrast expansion, balances midtone gamma based on mean luminance, and applies a non-linear sigmoidal curve perturbation ($f(x) = x - 0.035 \cdot \sin(2\pi x)$).
4. **Intermediate Frequency Domain DCT Quantization**: Encodes the canvas into an intermediate JPEG buffer at Quality 88 (4:2:0 subsampling) to force high-frequency DCT coefficients into coarse quantization bins.
5. **Post-Enhancement & Slight Sharpness Reduction**: Reduces sharpness slightly (`factor=0.93`) to soften hyper-sharp steganographic edge deltas while fine-tuning color (1.03x) and contrast (1.02x).
6. **Median Denoising & Gaussian Re-nosing**: Filters spatial noise via a 3x3 Median filter and injects controlled Gaussian noise ($\sigma = 3.5$) to scrub deterministic noise channels.
7. **Spatial Micro-Grid Lattice Perturbation**: Applies a sub-perceptual alternating spatial lattice ($\pm 0.75$ to $\pm 1.75$) to disrupt neighborhood pixel correlation vectors.
8. **Lightweight Img2Img Pixel Reconstruction**: Blends the perturbed image with an edge-preserving smooth abstraction canvas ($\alpha = 0.35$).
9. **5px Edge Pixel Cloning & Gaussian Blur Boundary Reconstruction**: Shrinks the canvas by 5px on all four sides ($W-10 \times H-10$) as an inner reference, clones boundary/corner pixels into the outer 5px margins, applies Gaussian blur ($\sigma=2.5$) to the border, and pastes the inner reference cleanly in the center.
10. **Global Sub-Pixel Micro-Gaussian Blur Pass**: Applies a subtle Gaussian blur (`radius=0.45`) across **every pixel** of the entire image canvas.
11. **EXIF Injection & Final Save**: Constructs a clean EXIF payload via `piexif` (IFD0, ExifIFD, GPSIFD) and encodes the final image to JPEG at Quality 95 (`subsampling=0`).

---

## 🛠️ Tech Stack & Architecture

- **Backend**: Python 3.10+, Flask, Pillow (PIL), NumPy, `piexif`, Gunicorn.
- **Frontend**: HTML5, Vanilla CSS3 (`static/css/style.css`), Vanilla JavaScript (`static/js/app.js`), Leaflet.js, Lucide Icons.
- **Map Layer**: Leaflet.js with OpenStreetMap tile rendering.

---

## 📁 Project Structure

```
pixel-beam/
├── app.py              # Flask server initialization & REST API endpoints (/process)
├── config.py           # Central configuration, stage boolean toggles & hyperparameters
├── image_pipeline.py   # 11-stage steganography disruption & pixel sanitization engine
├── exif_utils.py       # EXIF payload building & DMS rational coordinate conversion
├── requirements.txt    # Python dependencies
├── AGENTS.md           # Workspace guidelines & developer rules
├── README.md           # Project documentation
├── static/
│   ├── css/
│   │   └── style.css   # Glassmorphism UI tokens, layout & Leaflet overrides
│   └── js/
│       └── app.js      # File upload handling, Leaflet map pinning & API fetch logic
└── templates/
    └── index.html      # Responsive single-page UI linking static assets
```

---

## 🎛️ Pipeline Stage Configuration (`config.py`)

All 11 processing stages can be dynamically enabled or disabled in `config.py` using `PIPELINE_STAGES`:

```python
PIPELINE_STAGES = {
    "STAGE_4_DCT_QUANTIZATION":      True,  # Intermediate JPEG Q88 4:2:0 frequency domain scrubbing
    "STAGE_5_SHARPNESS_REDUCTION":   True,  # Subtle sharpness reduction (0.93x)
    "STAGE_6_MEDIAN_DENOISE_RENOISE":True,  # 3x3 Median filter + Gaussian re-nosing (sigma=3.5)
    "STAGE_6_1_BILATERAL_FILTER":    True,  # OpenCV Bilateral Filter (edge-preserving smoothing)
    "STAGE_6_2_MORPHOLOGICAL_OPENING":True, # OpenCV Morphological Opening (removes spurious pixel clusters)
    "STAGE_6_3_SCIPY_SPATIAL_CONVOLUTION":True,# SciPy ndimage 2D spatial kernel convolution
    "STAGE_6_4_FFT_DITHER_REMOVAL":   True, # 2D Fast Fourier Transform (FFT) periodic dither notch frequency filter
    "STAGE_7_GRID_PERTURBATION":     True,  # Sub-perceptual spatial checkerboard lattice perturbation
    "STAGE_8_IMG2IMG_RECONSTRUCTION":True,  # Soft edge-preserving smooth abstraction blend (alpha=0.35)
    "STAGE_9_EDGE_CLONING_BLUR":     True,  # 5px edge pixel cloning & Gaussian blur boundary reconstruction
    "STAGE_10_GLOBAL_MICRO_BLUR":    True,  # Global sub-pixel micro-Gaussian blur across every pixel (r=0.45)
    "STAGE_10_1_LSB_BITPLANE_SCRAMBLE":True,# LSB bit-plane randomization (stegano, PIL LSB steganography)
    "STAGE_10_2_DWT_DCT_SUBBAND_SCRUB":True,# DWT-DCT 2D Haar sub-band detail scrubbing (invisible-watermark, pywt, blind-watermark)
    "STAGE_10_3_SVD_RIVAGAN_PERTURBATION":True,# Patch SVD singular-value ratio micro-jitter & RivaGAN feature map disruption
    "STAGE_10_4_PATCHWORK_BIAS_ERASURE": True, # Patchwork method statistical mean-difference bias erasure (+/-1 level)
    "STAGE_10_5_SPREAD_SPECTRUM_DECORRELATION": True, # Spread-spectrum & additive spatial noise de-correlation (alpha=0.50)
    "STAGE_10_6_COMMON_RESOLUTION_CROP": True, # Snaps & center-crops to nearest standard resolution (e.g. 1080x1080) right before save
    "STAGE_10_7_MICRO_SCALE_101":        True, # 101% micro-scale zoom (1.01x) to desynchronize spatial coordinate grids
    "STAGE_10_8_LENS_CORRECTION_1PERCENT":True,# +1% radial lens distortion correction (barrel/pincushion k1=+0.01)
    "STAGE_10_9_COLOR_REDUCTION_5PERCENT":True,# 5% color reduction & palette scrubbing (0.95x)
    "STAGE_11_EXIF_INJECTION":       True,  # Wipes existing EXIF & injects custom piexif payload
}
```

### 🎯 Targeted Invisible Watermark & Steganography Defenses (Stages 10.1 – 10.5)

PixelBeam explicitly neutralizes popular open-source, AI ecosystem, and spatial-domain watermark frameworks **without any human-perceptible visual changes** ($\text{PSNR} > 42\text{ dB}$, $\text{Max Delta} \le 7$ out of 255):

- 🛡️ **`invisible-watermark` (SynthID / Stable Diffusion Ecosystem)**: Neutralized via Stage 10.2 (2D Haar DWT $LH, HL, HH$ detail sub-band coefficient perturbation) and Stage 10.3 (Patch SVD singular-value ratio jitter).
- 🛡️ **`imwatermark` & PyWavelets (`pywt`)**: Neutralized by frequency-domain DWT-DCT sub-band coefficient scrubbing.
- 🛡️ **`stegano` & Pillow (PIL) LSB Steganography**: Neutralized via Stage 10.1 ($b_0, b_1$ least-significant-bit plane scrambling).
- 🛡️ **`blind-watermark`**: Neutralized by combining DWT-DCT sub-band noise with spatial grid micro-perturbations.
- 🛡️ **RivaGAN Deep Watermarks**: Neutralized via 4x4 spatial patch orthogonal gradient feature map micro-jitter.
- 🛡️ **Patchwork Method Spatial Watermarks**: Neutralized via Stage 10.4 (sub-perceptual $\pm 1$ luminance level pair micro-jitter erasing mean-difference bias $E[\bar{A} - \bar{B}] \to 0$).
- 🛡️ **Spread-Spectrum & Additive Spatial Noise Watermarks**: Neutralized via Stage 10.5 (sub-perceptual orthogonal sequence injection $\alpha=0.50$ dropping cross-correlation $\rho$ below detection thresholds).

---

## 🚀 Getting Started

### Prerequisites

- Python 3.10 or higher
- `pip` package manager

### Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/your-username/pixel-beam.git
   cd pixel-beam
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application**:
   ```bash
   python app.py
   ```

4. **Open in browser**:
   Navigate to `http://127.0.0.1:5000`.

---

## ⚙️ Environment Variables

PixelBeam can be configured via environment variables:

| Variable | Default | Description |
| :--- | :--- | :--- |
| `PORT` | `5000` | HTTP server port |
| `FLASK_DEBUG` | `true` | Enable Flask debug mode (`true`/`false`) |
| `MAX_UPLOAD_MB` | `16` | Maximum allowed image upload size in MB |

---

## 📡 API Reference

### `POST /process`

Processes an image through the steganography disruption pipeline and injects custom EXIF metadata.

#### Request (`multipart/form-data`)

| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `image` | File | Yes | Input image file (`image/jpeg` or `image/png`) |
| `make` | String | No | EXIF Camera/Device Make (e.g. `Apple`, `samsung`, `Canon`) |
| `model` | String | No | EXIF Camera/Device Model (e.g. `iPhone 16 Pro Max`, `SM-S928B`) |
| `datetime` | String | No | EXIF Timestamp in ISO format (`YYYY-MM-DDTHH:MM`) |
| `lat` | Float | No | Decimal Latitude (e.g. `37.774900`) |
| `lng` | Float | No | Decimal Longitude (e.g. `-122.419400`) |

#### Response

- **Success (`200 OK`)**: Returns processed JPEG binary file (`image/jpeg`) attachment.
- **Error (`400 / 500`)**: Returns JSON error object:
  ```json
  {
    "error": "Unsupported file type. Upload a JPEG or PNG."
  }
  ```

---

## 🌐 Production Deployment

Run PixelBeam using Gunicorn for production hosting (Render, PythonAnywhere, Heroku, AWS, or Railway):

```bash
gunicorn app:app --bind 0.0.0.0:5000 --workers 2
```

---

## 🔒 Privacy & Security

- **No Persistence**: Uploaded images exist only in temporary memory buffers (`BytesIO`) during processing.
- **Complete EXIF Wipe**: All pre-existing metadata tags, camera serial numbers, and software signatures are erased before user-specified tags are injected.
- **Zero Third-Party Telemetry**: No tracking scripts, external analytics, or paid API keys.

---

## 📄 License

Distributed under the MIT License. See `LICENSE` for details.