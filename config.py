import os

# ── SERVER CONFIGURATION ──────────────────────────────────────
MAX_UPLOAD_MB = int(os.environ.get('MAX_UPLOAD_MB', '16'))
MAX_CONTENT_LENGTH = MAX_UPLOAD_MB * 1024 * 1024
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png'}

DEFAULT_PORT = int(os.environ.get('PORT', 5000))
DEFAULT_DEBUG = os.environ.get('FLASK_DEBUG', 'true').lower() == 'true'

# ── PIPELINE STAGE TOGGLES ────────────────────────────────────
# Enable or disable individual stages in the steganography disruption & sanitization pipeline
PIPELINE_STAGES = {
    "STAGE_4_DCT_QUANTIZATION":      True,  # Intermediate JPEG Q88 4:2:0 frequency domain scrubbing
    "STAGE_5_SHARPNESS_REDUCTION":   True,  # Subtle sharpness reduction (0.93x)
    "STAGE_6_MEDIAN_DENOISE_RENOISE":True,  # 3x3 Median filter + Gaussian re-nosing (sigma=3.5)
    "STAGE_6_1_BILATERAL_FILTER":    True,  # OpenCV Bilateral Filter (edge-preserving smoothing)
    "STAGE_6_2_MORPHOLOGICAL_OPENING":True, # OpenCV Morphological Opening (removes spurious pixel clusters)
    "STAGE_6_3_SCIPY_SPATIAL_CONVOLUTION":True,# SciPy ndimage multidimensional spatial kernel smoothing
    "STAGE_6_4_FFT_DITHER_REMOVAL":   True, # 2D Fast Fourier Transform (FFT) periodic dither notch frequency filter
    "STAGE_7_GRID_PERTURBATION":     True,  # Sub-perceptual spatial checkerboard lattice perturbation
    "STAGE_8_IMG2IMG_RECONSTRUCTION":True,  # Soft edge-preserving smooth abstraction blend (alpha=0.35)
    "STAGE_9_EDGE_CLONING_BLUR":     True,  # 5px edge pixel cloning & Gaussian blur boundary reconstruction
    "STAGE_10_GLOBAL_MICRO_BLUR":    True,  # Global sub-pixel micro-Gaussian blur across every pixel (r=0.45)
    "STAGE_10_1_LSB_BITPLANE_SCRAMBLE":True,# Scrambles b0-b1 bitplanes to destroy LSB steganography (stegano, PIL)
    "STAGE_10_2_DWT_DCT_SUBBAND_SCRUB":True,# DWT 2D Haar sub-band detail coefficient perturbation (invisible-watermark, pywt, blind-watermark)
    "STAGE_10_3_SVD_RIVAGAN_PERTURBATION":True,# Patch SVD singular-value ratio micro-jitter & RivaGAN feature map disruption
    "STAGE_10_4_PATCHWORK_BIAS_ERASURE": True, # Erases Patchwork method mean-difference bias (+/-1 level)
    "STAGE_10_5_SPREAD_SPECTRUM_DECORRELATION": True, # Neutralizes spread-spectrum & additive spatial noise watermarks
    "STAGE_10_6_COMMON_RESOLUTION_CROP": True, # Snaps & center-crops to nearest standard resolution (e.g. 1080x1080) right before save
    "STAGE_10_7_MICRO_SCALE_101":        True, # 101% micro-scale zoom (1.01x) to desynchronize spatial coordinate grids
    "STAGE_10_8_LENS_CORRECTION_1PERCENT":True,# +1% radial lens distortion correction (barrel/pincushion k1=+0.01)
    "STAGE_10_9_COLOR_REDUCTION_5PERCENT":True,# 5% color reduction & palette scrubbing (0.95x)
    "STAGE_11_EXIF_INJECTION":       True,  # Wipes existing EXIF & injects custom piexif payload
}

# ── PIPELINE HYPERPARAMETERS ─────────────────────────────────
PIPELINE_PARAMS = {
    # Stage 1 & 2: Resampling & Grid Rounding
    "STEP_ROUNDING": 50,
    "MICRO_SHRINK_SCALE": 0.88,
    "SHRINK_LEFT": 2,
    "SHRINK_TOP": 1,
    "SHRINK_RIGHT": 1,
    "SHRINK_BOTTOM": 2,

    # Stage 2.5: Multi-Round Resampling Cascade Ratios
    "CASCADE_ROUNDS": 3,
    "CASCADE_SCALE_1": 1.25,
    "CASCADE_SCALE_2": 1.40,
    "CASCADE_SCALE_3": 1.15,

    # Stage 3: Auto Levels & Curves (Bypassed)
    "AUTO_LEVELS_LOW_PERCENTILE": 0.5,
    "AUTO_LEVELS_HIGH_PERCENTILE": 99.5,
    "SCURVE_ALPHA": 0.035,

    # Stage 4: Quantization
    "JPEG_Q_INTERMEDIATE": 88,

    # Stage 5: Post-Enhancement (Neutral Color/Contrast = 1.00)
    "SHARPNESS_FACTOR": 0.93,
    "COLOR_ENHANCE": 1.00,
    "CONTRAST_ENHANCE": 1.00,

    # Stage 6: Denoise & Noise Injection
    "MEDIAN_FILTER_SIZE": 3,
    "GAUSSIAN_NOISE_SIGMA": 3.5,

    # Stage 6.1: OpenCV Bilateral Filter
    "BILATERAL_SIGMA_COLOR": 15.0,
    "BILATERAL_SIGMA_SPACE": 5.0,

    # Stage 6.2: Morphological Opening
    "MORPH_KERNEL_SIZE": 3,

    # Stage 6.4: FFT 2D Frequency Dither Notch Radius
    "FFT_NOTCH_RADIUS": 12,

    # Stage 7: Grid Perturbation
    "CHECKERBOARD_MIN": 0.75,
    "CHECKERBOARD_MAX": 1.75,

    # Stage 8: Img2Img Reconstruction
    "SMOOTH_ALPHA": 0.35,

    # Stage 9: Edge Cloning & Blur
    "EDGE_BORDER_PX": 5,
    "EDGE_BLUR_RADIUS": 2.5,

    # Stage 10: Global Blur
    "GLOBAL_BLUR_RADIUS": 0.45,

    # Stage 10.1: LSB Scramble Mask
    "LSB_BITS_MASK": 0xFC,

    # Stage 10.2: DWT Detail Sub-band Noise
    "DWT_NOISE_SIGMA": 0.35,

    # Stage 10.3: Patch SVD Ratio Jitter
    "SVD_JITTER_STRENGTH": 0.40,

    # Stage 10.4: Patchwork Micro-Jitter Delta
    "PATCHWORK_DELTA_LEVEL": 1,

    # Stage 10.5: Spread-Spectrum Noise Alpha
    "SPREAD_SPECTRUM_ALPHA": 0.50,

    # Stage 10.7: Micro-Scale Zoom Ratio
    "SCALE_ZOOM_RATIO": 1.01,

    # Stage 10.8: Lens Distortion Coefficient (k1)
    "LENS_DISTORTION_K1": 0.01,

    # Stage 10.9: Color Reduction Factor
    "COLOR_REDUCTION_FACTOR": 0.95,

    # Stage 11: Export Quality
    "JPEG_Q_FINAL": 95,
}
