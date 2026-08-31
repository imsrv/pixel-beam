// ─────────────────────────────────────────────
// STATE
// ─────────────────────────────────────────────
let selectedFile = null;
let mapPin = null;
let mapInstance = null;
let resultObjectURL = null;

// ─────────────────────────────────────────────
// DOM REFS
// ─────────────────────────────────────────────
const dropZone        = document.getElementById('drop-zone');
const fileInput       = document.getElementById('file-input');
const browseLink      = document.getElementById('browse-link');
const filePreview     = document.getElementById('file-preview');
const previewThumb    = document.getElementById('preview-thumb');
const previewName     = document.getElementById('preview-name');
const previewSize     = document.getElementById('preview-size');
const removeFileBtn   = document.getElementById('remove-file-btn');
const processBtn      = document.getElementById('process-btn');
const statusBar       = document.getElementById('status-bar');
const statusMsg       = document.getElementById('status-msg');
const statusSpinner   = document.getElementById('status-spinner');
const downloadSection = document.getElementById('download-section');
const resultPreview   = document.getElementById('result-preview');
const downloadBtn     = document.getElementById('download-btn');
const exifTagsDisplay = document.getElementById('exif-tags-display');
const latPill         = document.getElementById('lat-pill');
const lngPill         = document.getElementById('lng-pill');
const latVal          = document.getElementById('lat-val');
const lngVal          = document.getElementById('lng-val');
const clearPinBtn     = document.getElementById('clear-pin-btn');
const mapHint         = document.getElementById('map-hint');

// Pipeline steps
const pipeSteps = {
  upload:   document.getElementById('pipe-upload'),
  sanitize: document.getElementById('pipe-sanitize'),
  exif:     document.getElementById('pipe-exif'),
  gps:      document.getElementById('pipe-gps'),
  download: document.getElementById('pipe-download'),
};

// ─────────────────────────────────────────────
// UPLOAD / DROP ZONE
// ─────────────────────────────────────────────
if (browseLink) browseLink.addEventListener('click', (e) => { e.stopPropagation(); fileInput.click(); });
if (dropZone) {
  dropZone.addEventListener('click', () => fileInput.click());
  dropZone.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') fileInput.click(); });

  dropZone.addEventListener('dragover', (e) => { e.preventDefault(); dropZone.classList.add('drag-over'); });
  dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
  dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('drag-over');
    const files = e.dataTransfer.files;
    if (files.length) handleFile(files[0]);
  });
}

if (fileInput) {
  fileInput.addEventListener('change', () => {
    if (fileInput.files.length) handleFile(fileInput.files[0]);
  });
}

if (removeFileBtn) removeFileBtn.addEventListener('click', (e) => { e.stopPropagation(); clearFile(); });

function handleFile(file) {
  if (!['image/jpeg', 'image/png'].includes(file.type)) {
    showStatus('error', '❌ Only JPEG and PNG images are supported.');
    return;
  }
  selectedFile = file;
  const objectURL = URL.createObjectURL(file);
  previewThumb.src = objectURL;
  previewName.textContent = file.name;
  previewSize.textContent = formatBytes(file.size);
  filePreview.classList.add('visible');
  dropZone.classList.add('has-file');
  setPipeActive('upload');
  updateProcessBtn();
  hideStatus();
  downloadSection.classList.remove('visible');
}

function clearFile() {
  selectedFile = null;
  fileInput.value = '';
  filePreview.classList.remove('visible');
  dropZone.classList.remove('has-file');
  clearPipeActive();
  updateProcessBtn();
}

// ─────────────────────────────────────────────
// LEAFLET MAP
// ─────────────────────────────────────────────
if (document.getElementById('map')) {
  mapInstance = L.map('map', { zoomControl: true }).setView([20, 0], 2);

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxZoom: 19,
  }).addTo(mapInstance);

  const pinIcon = L.divIcon({
    className: '',
    html: `<div style="
      width:28px; height:28px;
      background: linear-gradient(135deg,#5ed6de,#7c6aff);
      border-radius: 50% 50% 50% 0;
      transform: rotate(-45deg);
      border: 2px solid #fff;
      box-shadow: 0 2px 8px rgba(94,214,222,0.5);
    "></div>`,
    iconSize: [28, 28],
    iconAnchor: [14, 28],
  });

  mapInstance.on('click', (e) => {
    const { lat, lng } = e.latlng;
    placePin(lat, lng);
  });

  function placePin(lat, lng) {
    if (mapPin) mapInstance.removeLayer(mapPin);
    mapPin = L.marker([lat, lng], { icon: pinIcon })
      .addTo(mapInstance)
      .bindPopup(`<b style="font-family:monospace;">${lat.toFixed(6)}, ${lng.toFixed(6)}</b>`)
      .openPopup();

    latVal.value = lat.toFixed(7);
    lngVal.value = lng.toFixed(7);
    latPill.textContent = `Lat: ${lat.toFixed(5)}`;
    lngPill.textContent = `Lng: ${lng.toFixed(5)}`;
    latPill.classList.add('has-value');
    lngPill.classList.add('has-value');
    clearPinBtn.style.display = 'inline';
    mapHint.classList.add('hidden');
    setPipeActive('gps');
  }

  clearPinBtn.addEventListener('click', () => {
    if (mapPin) mapInstance.removeLayer(mapPin);
    mapPin = null;
    latVal.value = '';
    lngVal.value = '';
    latPill.textContent = 'Lat: —';
    lngPill.textContent = 'Lng: —';
    latPill.classList.remove('has-value');
    lngPill.classList.remove('has-value');
    clearPinBtn.style.display = 'none';
    mapHint.classList.remove('hidden');
  });
}

// ─────────────────────────────────────────────
// DEVICE DATA — real EXIF strings from actual devices
// ─────────────────────────────────────────────
const DEVICE_DB = {
  'Apple': [
    { label: 'iPhone 11',             value: 'iPhone 11' },
    { label: 'iPhone 11 Pro',         value: 'iPhone 11 Pro' },
    { label: 'iPhone 11 Pro Max',     value: 'iPhone 11 Pro Max' },
    { label: 'iPhone 12',             value: 'iPhone 12' },
    { label: 'iPhone 12 Pro',         value: 'iPhone 12 Pro' },
    { label: 'iPhone 12 Pro Max',     value: 'iPhone 12 Pro Max' },
    { label: 'iPhone 13',             value: 'iPhone 13' },
    { label: 'iPhone 13 Pro',         value: 'iPhone 13 Pro' },
    { label: 'iPhone 13 Pro Max',     value: 'iPhone 13 Pro Max' },
    { label: 'iPhone 14',             value: 'iPhone 14' },
    { label: 'iPhone 14 Plus',        value: 'iPhone 14 Plus' },
    { label: 'iPhone 14 Pro',         value: 'iPhone 14 Pro' },
    { label: 'iPhone 14 Pro Max',     value: 'iPhone 14 Pro Max' },
    { label: 'iPhone 15',             value: 'iPhone 15' },
    { label: 'iPhone 15 Plus',        value: 'iPhone 15 Plus' },
    { label: 'iPhone 15 Pro',         value: 'iPhone 15 Pro' },
    { label: 'iPhone 15 Pro Max',     value: 'iPhone 15 Pro Max' },
    { label: 'iPhone 16',             value: 'iPhone 16' },
    { label: 'iPhone 16 Plus',        value: 'iPhone 16 Plus' },
    { label: 'iPhone 16 Pro',         value: 'iPhone 16 Pro' },
    { label: 'iPhone 16 Pro Max',     value: 'iPhone 16 Pro Max' },
    { label: 'iPhone 16e',            value: 'iPhone 16e' },
    { label: 'Custom…',              value: '__custom__' },
  ],
  'samsung': [
    { label: 'Galaxy S21 (SM-G991B)',        value: 'SM-G991B' },
    { label: 'Galaxy S21+ (SM-G996B)',       value: 'SM-G996B' },
    { label: 'Galaxy S21 Ultra (SM-G998B)',  value: 'SM-G998B' },
    { label: 'Galaxy S22 (SM-S901B)',        value: 'SM-S901B' },
    { label: 'Galaxy S22+ (SM-S906B)',       value: 'SM-S906B' },
    { label: 'Galaxy S22 Ultra (SM-S908B)',  value: 'SM-S908B' },
    { label: 'Galaxy S23 (SM-S911B)',        value: 'SM-S911B' },
    { label: 'Galaxy S23+ (SM-S916B)',       value: 'SM-S916B' },
    { label: 'Galaxy S23 Ultra (SM-S918B)',  value: 'SM-S918B' },
    { label: 'Galaxy S24 (SM-S921B)',        value: 'SM-S921B' },
    { label: 'Galaxy S24+ (SM-S926B)',       value: 'SM-S926B' },
    { label: 'Galaxy S24 Ultra (SM-S928B)',  value: 'SM-S928B' },
    { label: 'Galaxy S25 (SM-S931B)',        value: 'SM-S931B' },
    { label: 'Galaxy S25 Ultra (SM-S938B)',  value: 'SM-S938B' },
    { label: 'Galaxy A54 (SM-A546B)',        value: 'SM-A546B' },
    { label: 'Galaxy A55 (SM-A556B)',        value: 'SM-A556B' },
    { label: 'Galaxy Z Fold 5 (SM-F946B)',   value: 'SM-F946B' },
    { label: 'Galaxy Z Flip 5 (SM-F731B)',   value: 'SM-F731B' },
    { label: 'Custom…',                     value: '__custom__' },
  ],
  'Google': [
    { label: 'Pixel 6',          value: 'Pixel 6' },
    { label: 'Pixel 6 Pro',      value: 'Pixel 6 Pro' },
    { label: 'Pixel 6a',         value: 'Pixel 6a' },
    { label: 'Pixel 7',          value: 'Pixel 7' },
    { label: 'Pixel 7 Pro',      value: 'Pixel 7 Pro' },
    { label: 'Pixel 7a',         value: 'Pixel 7a' },
    { label: 'Pixel 8',          value: 'Pixel 8' },
    { label: 'Pixel 8 Pro',      value: 'Pixel 8 Pro' },
    { label: 'Pixel 8a',         value: 'Pixel 8a' },
    { label: 'Pixel 9',          value: 'Pixel 9' },
    { label: 'Pixel 9 Pro',      value: 'Pixel 9 Pro' },
    { label: 'Pixel 9 Pro XL',   value: 'Pixel 9 Pro XL' },
    { label: 'Pixel 9 Pro Fold', value: 'Pixel 9 Pro Fold' },
    { label: 'Custom…',         value: '__custom__' },
  ],
  'OnePlus': [
    { label: 'OnePlus 10 Pro (NE2213)',  value: 'NE2213' },
    { label: 'OnePlus 11 (CPH2449)',     value: 'CPH2449' },
    { label: 'OnePlus 12 (CPH2583)',     value: 'CPH2583' },
    { label: 'OnePlus 12R (CPH2609)',    value: 'CPH2609' },
    { label: 'OnePlus Nord 3 (CPH2493)', value: 'CPH2493' },
    { label: 'OnePlus Nord 4 (CPH2699)', value: 'CPH2699' },
    { label: 'OnePlus Open (CPH2551)',   value: 'CPH2551' },
    { label: 'Custom…',                value: '__custom__' },
  ],
  'SONY': [
    { label: 'α1 (ILCE-1)',                 value: 'ILCE-1' },
    { label: 'α1 II (ILCE-1M2)',             value: 'ILCE-1M2' },
    { label: 'α7 II (ILCE-7M2)',             value: 'ILCE-7M2' },
    { label: 'α7 III (ILCE-7M3)',            value: 'ILCE-7M3' },
    { label: 'α7 IV (ILCE-7M4)',             value: 'ILCE-7M4' },
    { label: 'α7 V (ILCE-7M5)',              value: 'ILCE-7M5' },
    { label: 'α7C (ILCE-7C)',                value: 'ILCE-7C' },
    { label: 'α7C II (ILCE-7CM2)',           value: 'ILCE-7CM2' },
    { label: 'α7C R (ILCE-7CR)',             value: 'ILCE-7CR' },
    { label: 'α7R II (ILCE-7RM2)',           value: 'ILCE-7RM2' },
    { label: 'α7R III (ILCE-7RM3)',          value: 'ILCE-7RM3' },
    { label: 'α7R IV (ILCE-7RM4)',           value: 'ILCE-7RM4' },
    { label: 'α7R IV A (ILCE-7RM4A)',        value: 'ILCE-7RM4A' },
    { label: 'α7R V (ILCE-7RM5)',            value: 'ILCE-7RM5' },
    { label: 'α7S II (ILCE-7SM2)',           value: 'ILCE-7SM2' },
    { label: 'α7S III (ILCE-7SM3)',          value: 'ILCE-7SM3' },
    { label: 'α9 (ILCE-9)',                  value: 'ILCE-9' },
    { label: 'α9 II (ILCE-9M2)',             value: 'ILCE-9M2' },
    { label: 'α9 III (ILCE-9M3)',            value: 'ILCE-9M3' },
    { label: 'α6400 (ILCE-6400)',            value: 'ILCE-6400' },
    { label: 'α6600 (ILCE-6600)',            value: 'ILCE-6600' },
    { label: 'α6700 (ILCE-6700)',            value: 'ILCE-6700' },
    { label: 'FX3 (ILCE-FX3)',               value: 'ILCE-FX3' },
    { label: 'FX30 (ILCE-FX30)',             value: 'ILCE-FX30' },
    { label: 'ZV-E1 (ZV-E1)',                value: 'ZV-E1' },
    { label: 'ZV-E10 (ZV-E10)',              value: 'ZV-E10' },
    { label: 'ZV-E10 II (ZV-E10M2)',         value: 'ZV-E10M2' },
    { label: 'RX1R II (DSC-RX1RM2)',         value: 'DSC-RX1RM2' },
    { label: 'RX100 VI (DSC-RX100M6)',       value: 'DSC-RX100M6' },
    { label: 'RX100 VII (DSC-RX100M7)',      value: 'DSC-RX100M7' },
    { label: 'RX10 IV (DSC-RX10M4)',         value: 'DSC-RX10M4' },
    { label: 'Custom…',                    value: '__custom__' },
  ],
  'Canon': [
    { label: 'EOS R3',                            value: 'Canon EOS R3' },
    { label: 'EOS R5',                            value: 'Canon EOS R5' },
    { label: 'EOS R5 Mark II',                    value: 'Canon EOS R5 Mark II' },
    { label: 'EOS R6',                            value: 'Canon EOS R6' },
    { label: 'EOS R6 Mark II',                    value: 'Canon EOS R6 Mark II' },
    { label: 'EOS R7',                            value: 'Canon EOS R7' },
    { label: 'EOS R8',                            value: 'Canon EOS R8' },
    { label: 'EOS R10',                           value: 'Canon EOS R10' },
    { label: 'EOS R50',                           value: 'Canon EOS R50' },
    { label: 'EOS R100',                          value: 'Canon EOS R100' },
    { label: 'EOS-1D X Mark II',                  value: 'Canon EOS-1D X Mark II' },
    { label: 'EOS-1D X Mark III',                 value: 'Canon EOS-1D X Mark III' },
    { label: 'EOS 5D Mark III',                   value: 'Canon EOS 5D Mark III' },
    { label: 'EOS 5D Mark IV',                    value: 'Canon EOS 5D Mark IV' },
    { label: 'EOS 6D',                            value: 'Canon EOS 6D' },
    { label: 'EOS 6D Mark II',                    value: 'Canon EOS 6D Mark II' },
    { label: 'EOS 7D Mark II',                    value: 'Canon EOS 7D Mark II' },
    { label: 'EOS 80D',                           value: 'Canon EOS 80D' },
    { label: 'EOS 90D',                           value: 'Canon EOS 90D' },
    { label: 'EOS 250D (Rebel SL3)',               value: 'Canon EOS 250D' },
    { label: 'EOS 850D (Rebel T8i)',               value: 'Canon EOS 850D' },
    { label: 'PowerShot G7 X Mark III',           value: 'Canon PowerShot G7 X Mark III' },
    { label: 'PowerShot G5 X Mark II',            value: 'Canon PowerShot G5 X Mark II' },
    { label: 'PowerShot V10',                     value: 'Canon PowerShot V10' },
    { label: 'Custom…',                         value: '__custom__' },
  ],
};

// ─────────────────────────────────────────────
// DEVICE CASCADE — Make → Model dropdown
// ─────────────────────────────────────────────
const makeSelect       = document.getElementById('exif-make-select');
const modelSelect      = document.getElementById('exif-model-select');
const makeCustomRow    = document.getElementById('make-custom-row');
const modelCustomRow   = document.getElementById('model-custom-row');
const makeCustomInput  = document.getElementById('exif-make-custom');
const modelCustomInput = document.getElementById('exif-model-custom');

if (makeSelect) {
  makeSelect.addEventListener('change', () => {
    const brand = makeSelect.value;
    const isCustomMake = brand === '__custom__';

    makeCustomRow.classList.toggle('visible', isCustomMake);
    if (isCustomMake) { makeCustomInput.focus(); }

    modelSelect.innerHTML = '';
    modelCustomRow.classList.remove('visible');

    if (isCustomMake || !DEVICE_DB[brand]) {
      modelSelect.disabled = true;
      modelSelect.innerHTML = '<option value="" disabled selected>— Enter make above first —</option>';
      return;
    }

    const placeholder = document.createElement('option');
    placeholder.value = ''; placeholder.disabled = true; placeholder.selected = true;
    placeholder.textContent = `— Select ${brand === 'samsung' ? 'Samsung' : brand} Model —`;
    modelSelect.appendChild(placeholder);

    DEVICE_DB[brand].forEach(({ label, value }) => {
      const opt = document.createElement('option');
      opt.value = value;
      opt.textContent = label;
      modelSelect.appendChild(opt);
    });
    modelSelect.disabled = false;
  });
}

if (modelSelect) {
  modelSelect.addEventListener('change', () => {
    const isCustomModel = modelSelect.value === '__custom__';
    modelCustomRow.classList.toggle('visible', isCustomModel);
    if (isCustomModel) modelCustomInput.focus();
  });
}

function getEffectiveMake() {
  const sel = makeSelect ? makeSelect.value : '';
  if (!sel || sel === '__custom__') return makeCustomInput ? makeCustomInput.value.trim() : '';
  return sel;
}

function getEffectiveModel() {
  const sel = modelSelect ? modelSelect.value : '';
  if (!sel || sel === '__custom__') return modelCustomInput ? modelCustomInput.value.trim() : '';
  return sel;
}

// ─────────────────────────────────────────────
// PROCESS
// ─────────────────────────────────────────────
if (processBtn) processBtn.addEventListener('click', processImage);

async function processImage() {
  if (!selectedFile) return;

  const fd = new FormData();
  fd.append('image', selectedFile);

  const make  = getEffectiveMake();
  const model = getEffectiveModel();
  const dt    = document.getElementById('exif-datetime').value;
  const lat   = latVal.value;
  const lng   = lngVal.value;

  if (make)  fd.append('make', make);
  if (model) fd.append('model', model);
  if (dt)    fd.append('datetime', dt);
  if (lat)   fd.append('lat', lat);
  if (lng)   fd.append('lng', lng);

  processBtn.disabled = true;
  showStatus('processing', 'Sanitizing pixels and injecting EXIF…');
  setPipeActive('sanitize');
  downloadSection.classList.remove('visible');

  try {
    const response = await fetch('/process', { method: 'POST', body: fd });

    if (!response.ok) {
      let errMsg = `Server error (${response.status})`;
      try {
        const errData = await response.json();
        errMsg = errData.error || errMsg;
      } catch (_) {}
      throw new Error(errMsg);
    }

    const blob = await response.blob();

    if (resultObjectURL) URL.revokeObjectURL(resultObjectURL);
    resultObjectURL = URL.createObjectURL(blob);

    resultPreview.src = resultObjectURL;
    downloadBtn.href = resultObjectURL;
    const ext = blob.type === 'image/png' ? 'png' : 'jpg';
    downloadBtn.download = `pixelbeam_processed.${ext}`;

    const inColors = response.headers.get('X-Input-Colors');
    const outColors = response.headers.get('X-Output-Colors');

    exifTagsDisplay.innerHTML = '';
    const tags = [];

    if (inColors) {
      tags.push({ icon: 'palette', text: `Input Colors: ${parseInt(inColors, 10).toLocaleString()} (PIL)`, type: 'amber' });
    }
    if (outColors) {
      tags.push({ icon: 'palette', text: `Sanitized Colors: ${parseInt(outColors, 10).toLocaleString()} (PIL)`, type: 'cyan' });
    }

    tags.push(
      // Core Pipeline Sanitization Badges
      { icon: 'binary', text: 'DCT Frequency Quantized (Q88)', type: 'cyan' },
      { icon: 'sliders', text: 'Sharpness Reduced (0.93x)', type: 'cyan' },
      { icon: 'waves', text: 'Median Denoised & Re-Noised', type: 'cyan' },
      { icon: 'shield-check', text: 'Bilateral Edge-Preserving Filter (OpenCV)', type: 'cyan' },
      { icon: 'grid', text: 'Morphological Opening (OpenCV)', type: 'cyan' },
      { icon: 'cpu', text: 'SciPy Spatial Kernel Convolution', type: 'cyan' },
      { icon: 'radio', text: 'FFT 2D Frequency Dither Notch Filter', type: 'cyan' },
      { icon: 'grid', text: 'Spatial Lattice Perturbed', type: 'cyan' },
      { icon: 'palette', text: 'Img2Img Detail Abstracted', type: 'cyan' },
      { icon: 'box-select', text: '5px Edge Cloned & Blurred', type: 'cyan' },
      { icon: 'sun', text: 'Global Micro-Blur (r=0.45)', type: 'cyan' },

      // Targeted Stego & Invisible Watermark Defenses
      { icon: 'shield-alert', text: 'LSB Bit-Planes Scrambled (stegano/PIL)', type: 'purple' },
      { icon: 'activity', text: 'DWT-DCT Sub-Bands Scrubbed (invisible-watermark/pywt)', type: 'purple' },
      { icon: 'cpu', text: 'Patch SVD & RivaGAN Disrupted', type: 'purple' },
      { icon: 'target', text: 'Patchwork Bias Erased (+/-1)', type: 'purple' },
      { icon: 'radio', text: 'Spread-Spectrum Decorrelated (alpha=0.50)', type: 'purple' },
      { icon: 'zoom-in', text: '101% Micro-Scale Zoom (1.01x)', type: 'purple' },
      { icon: 'eye', text: 'OpenCV +1% Lens Distortion Correction', type: 'purple' },
      { icon: 'droplet', text: '5% Color Saturation Reduction (0.95x)', type: 'purple' },

      // Resolution & Metadata Badges
      { icon: 'crop', text: 'Auto Common Resolution & Center-Crop', type: 'cyan' },
      { icon: 'trash-2', text: 'Pre-existing EXIF Wiped', type: 'green' }
    );

    if (make || model) tags.push({ icon: 'smartphone', text: [make, model].filter(Boolean).join(' '), type: 'green' });
    if (dt)            tags.push({ icon: 'calendar', text: new Date(dt).toLocaleDateString(), type: 'green' });
    if (lat && lng)    tags.push({ icon: 'map-pin', text: `${parseFloat(lat).toFixed(4)}, ${parseFloat(lng).toFixed(4)}`, type: 'amber' });

    tags.forEach(t => {
      const pill = document.createElement('span');
      pill.className = `exif-tag ${t.type || ''}`;
      pill.innerHTML = `<i data-lucide="${t.icon}" style="width:12px; height:12px;"></i>${t.text}`;
      exifTagsDisplay.appendChild(pill);
    });

    setPipeActive('download');
    showStatus('success', 'Image processed successfully! Click Download below.');
    downloadSection.classList.add('visible');
    downloadSection.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    if (window.lucide) lucide.createIcons();

  } catch (err) {
    showStatus('error', err.message);
    clearPipeActive();
    setPipeActive('upload');
  } finally {
    processBtn.disabled = false;
    updateProcessBtn();
  }
}

// ─────────────────────────────────────────────
// HELPERS
// ─────────────────────────────────────────────
function updateProcessBtn() {
  if (processBtn) processBtn.disabled = !selectedFile;
}

function showStatus(type, msg) {
  if (!statusBar) return;
  statusBar.className = `visible ${type}`;
  let prefixIcon = '';
  if (type === 'success') prefixIcon = '<i data-lucide="check-circle-2" style="width:16px; height:16px; vertical-align:middle; margin-right:6px;"></i>';
  if (type === 'error')   prefixIcon = '<i data-lucide="alert-circle" style="width:16px; height:16px; vertical-align:middle; margin-right:6px;"></i>';
  statusMsg.innerHTML = prefixIcon + msg;
  statusSpinner.style.display = type === 'processing' ? 'block' : 'none';
  if (window.lucide) lucide.createIcons();
}

function hideStatus() {
  if (statusBar) {
    statusBar.className = '';
    statusBar.classList.remove('visible');
  }
}

function setPipeActive(step) {
  Object.values(pipeSteps).forEach(el => el && el.classList.remove('active'));
  const order = ['upload', 'sanitize', 'exif', 'gps', 'download'];
  const idx = order.indexOf(step);
  order.slice(0, idx + 1).forEach(s => pipeSteps[s]?.classList.add('active'));
}

function clearPipeActive() {
  Object.values(pipeSteps).forEach(el => el && el.classList.remove('active'));
}

function formatBytes(bytes) {
  if (bytes < 1024)        return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

// Set default datetime to now & initialize Lucide icons
(function initPage() {
  const dtInput = document.getElementById('exif-datetime');
  if (dtInput) {
    const now = new Date();
    now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
    dtInput.value = now.toISOString().slice(0, 16);
  }
  if (window.lucide) lucide.createIcons();
})();
