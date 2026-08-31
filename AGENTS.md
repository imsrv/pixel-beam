# Workspace Guidelines: Image Sanitizer & EXIF Injector

This workspace contains PixelBeam, a modular Python Flask application designed to sanitize images against micro-steganography (via multi-pass spatial, frequency, and pixel reconstruction filters) and inject custom EXIF metadata with interactive Leaflet.js GPS pin mapping.

---

## 1. Tech Stack & Architecture

- **Backend:** Python 3.10+, Flask, Pillow (PIL), `piexif`, `numpy`, `gunicorn`
- **Frontend:** HTML5, Vanilla CSS (`/static/css/style.css`), Vanilla JS (`/static/js/app.js`), Leaflet.js (OpenStreetMap tiles — **Zero external API keys required**)
- **Data Flow:** In-memory stream processing using `io.BytesIO` (no persistent disk writes for uploaded user images)
- **Modular Project Structure:**
  - `config.py`: Central configuration, environment variables, pipeline hyperparameters, and granular stage enable/disable boolean toggles (`PIPELINE_STAGES`).
  - `exif_utils.py`: EXIF metadata payload generator (`build_exif_bytes`) and rational DMS coordinate converters.
  - `image_pipeline.py`: 11-stage steganography & AI watermark disruption engine (`sanitize_and_inject`).
  - `app.py`: Clean Flask server initialization, error handling, and REST endpoints (`/`, `/process`).
  - `static/css/style.css`: Glassmorphism design tokens, layout styles, and animations.
  - `static/js/app.js`: Drop-zone file handling, Leaflet map pinning, device database cascade, and API fetch calls.
  - `templates/index.html`: Clean HTML5 template linking static assets via Flask `url_for()`.

---

## 2. Core Processing Rules

### A. Steganography & Watermark Disruption
- Granularly configurable via `PIPELINE_STAGES` dictionary in `config.py`.
- Includes spatial grid phase shifts, multi-scale resizes, auto-levels/S-curves, DCT frequency quantization, sharpness reduction, median denoise + Gaussian noise injection ($\sigma=3.5$), spatial lattice perturbation, Img2Img reconstruction ($\alpha=0.35$), 5px edge pixel cloning + Gaussian border blur, and a global micro-Gaussian blur pass ($\text{radius}=0.45$).

### B. EXIF & Metadata Standards
- **Library:** Use `piexif` (`build_exif_bytes` in `exif_utils.py`).
- **GPS Coordinates:** Convert decimal coordinates to rational DMS tuples (`(deg, 1), (min, 1), (sec_num, 1000)`).
- **Tag Cleanup:** Wipes pre-existing EXIF tags before injecting the sanitized payload.
- **In-Memory Return:** Write output JPEG bytes to a `BytesIO` stream for direct response download.

---

## 3. Agent Execution & Coding Rules

- **Zero API Keys:** Never introduce external map services requiring paid credentials or billing. Always rely on open-source tile layers like Leaflet + OpenStreetMap.
- **Minimal Dependencies:** Core stack: `flask`, `pillow`, `piexif`, `numpy`, `gunicorn`. Add `flask-cors` only when running in decoupled API mode.
- **Modular Separation of Concerns:** Keep pipeline math in `image_pipeline.py`, EXIF logic in `exif_utils.py`, tunables in `config.py`, and HTTP routing in `app.py`. Keep CSS in `static/css/style.css` and JS in `static/js/app.js`.
- **Security & Memory Safety:** Process image files in memory buffers (`io.BytesIO`) to prevent disk leaks and file system permission issues in serverless environments.
- **API Design:** Flask routes return JSON for errors; binary file downloads via `send_file`. Use `multipart/form-data` for uploads.
- **Error Handling:** All routes must return structured JSON errors with appropriate HTTP status codes (e.g. 400, 413, 500).

---

## 4. Commands & Deployment Reference

- **Local Development:**
  ```bash
  python app.py
  ```
- **Dependencies Installation:**
  ```bash
  pip install -r requirements.txt
  ```
- **Cloud Entrypoint (Render / PythonAnywhere / AWS):**
  ```bash
  gunicorn app:app
  ```