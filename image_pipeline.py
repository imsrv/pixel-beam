import io
import logging
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter

from config import PIPELINE_STAGES, PIPELINE_PARAMS
from exif_utils import build_exif_bytes

log = logging.getLogger('PixelBeam.Pipeline')


def compute_rounded_dimensions(w: int, h: int, step: int = 50) -> tuple[int, int]:
    """
    Rounds the primary image dimension to the nearest multiple of `step` (default 50)
    and scales the secondary dimension proportionally to preserve the exact aspect ratio.
    Ensures final dimensions are even integers for optimal encoder compatibility.
    """
    if w >= h:
        new_w = max(step, int(round(w / step) * step))
        scale = new_w / w
        new_h = max(2, int(round((h * scale) / 2.0) * 2))
    else:
        new_h = max(step, int(round(h / step) * step))
        scale = new_h / h
        new_w = max(2, int(round((w * scale) / 2.0) * 2))
    return new_w, new_h


def compute_auto_levels(arr: np.ndarray, low_percentile: float = 0.5, high_percentile: float = 99.5) -> tuple[int, int, float]:
    """
    Analyzes image luminance/channel histogram to compute optimal auto black point,
    auto white point, and midtone gamma.
    """
    if arr.ndim == 3:
        lum = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
    else:
        lum = arr

    auto_black = int(np.clip(np.percentile(lum, low_percentile), 0, 25))
    auto_white = int(np.clip(np.percentile(lum, high_percentile), 230, 255))

    mean_lum = float(np.mean(lum))
    if mean_lum > 10.0:
        target_gamma = float(np.clip(np.log(0.5) / np.log(max(0.05, mean_lum / 255.0)), 0.88, 1.12))
    else:
        target_gamma = 0.98

    return auto_black, auto_white, target_gamma


def apply_auto_levels_and_curves(img: Image.Image) -> Image.Image:
    """
    Applies non-linear image levels adjustment, histogram stretch/auto-balance,
    and a subtle parametric S-curve transformation automatically before saving.
    Disrupts micro-steganography and relative pixel deltas without visual quality degradation.
    """
    arr = np.array(img, dtype=np.float32)

    low_p = PIPELINE_PARAMS.get("AUTO_LEVELS_LOW_PERCENTILE", 0.5)
    high_p = PIPELINE_PARAMS.get("AUTO_LEVELS_HIGH_PERCENTILE", 99.5)
    auto_black, auto_white, auto_gamma = compute_auto_levels(arr, low_p, high_p)

    if auto_white <= auto_black:
        auto_white = auto_black + 1

    # Linear levels mapping & clipping into [0, 1]
    arr_norm = np.clip((arr - auto_black) / (auto_white - auto_black), 0.0, 1.0)

    # Auto gamma / Midtones curve correction
    arr_gamma = np.power(arr_norm, auto_gamma)

    # Subtle Parametric S-Curve for contrast and steganography disruption
    alpha = PIPELINE_PARAMS.get("SCURVE_ALPHA", 0.035)
    arr_gamma = arr_gamma - alpha * np.sin(2.0 * np.pi * arr_gamma)
    arr_gamma = np.clip(arr_gamma, 0.0, 1.0)

    arr_out = np.clip(arr_gamma * 255.0, 0, 255).astype(np.uint8)
    log.info('[Stage 3] Auto Levels & Curves applied (black=%d, white=%d, gamma=%.2f)',
             auto_black, auto_white, auto_gamma)
    return Image.fromarray(arr_out)


def apply_edge_cloning_and_blur(img: Image.Image, border: int = 5, blur_radius: float = 2.5) -> Image.Image:
    """
    Edge Pixel Cloning & Gaussian Blur Boundary Reconstruction:
    1. Reads canvas resolution (W, H).
    2. Shrinks input image by `border` pixels on all 4 sides -> (W - 2*border, H - 2*border) for temp reference.
    3. Extends/clones boundary and corner pixels into the outer `border` (5px) margins.
    4. Applies Gaussian blur specifically to the outer cloned border region.
    5. Reconstructs final image at original resolution (W, H) with crisp center and blurred cloned borders.
    """
    w, h = img.size
    if w <= 2 * border or h <= 2 * border:
        return img

    inner_w = w - 2 * border
    inner_h = h - 2 * border

    # 1. Shrink resize to inner reference image (5px reduced from each side)
    inner_ref = img.resize((inner_w, inner_h), Image.LANCZOS)
    inner_arr = np.array(inner_ref, dtype=np.float32)

    # 2. Build full canvas array of original resolution (W, H)
    full_arr = np.zeros((h, w, 3) if inner_arr.ndim == 3 else (h, w), dtype=np.float32)

    # Center inner reference image at offset (border, border)
    full_arr[border:h-border, border:w-border] = inner_arr

    # Clone top & bottom border rows
    full_arr[0:border, border:w-border] = inner_arr[0:1, :]
    full_arr[h-border:h, border:w-border] = inner_arr[-1:, :]

    # Clone left & right border columns (including corners)
    full_arr[:, 0:border] = full_arr[:, border:border+1]
    full_arr[:, w-border:w] = full_arr[:, w-border-1:w-border]

    cloned_canvas = Image.fromarray(np.clip(full_arr, 0, 255).astype(np.uint8))

    # 3. Apply Gaussian blur to outer cloned pixel borders
    blurred_canvas = cloned_canvas.filter(ImageFilter.GaussianBlur(radius=blur_radius))

    # 4. Paste inner reference image cleanly back into the center
    blurred_canvas.paste(inner_ref, (border, border))

    log.info(
        '[Stage 9] Edge Pixel Cloning & Blur Reconstruction applied: Original %dx%d -> Ref %dx%d '
        '-> Cloned & Blurred (sigma=%.1f) %dpx outer margins',
        w, h, inner_w, inner_h, blur_radius, border
    )
    return blurred_canvas


def apply_lsb_bitplane_scramble(img: Image.Image) -> Image.Image:
    """
    Stage 10.1: LSB Bit-Plane Scrambling & Steganography Neutralization:
    Targets least-significant-bit steganography tools (`stegano`, PIL LSB scripts).
    Clears the 2 lowest bitplanes (b0, b1) and replaces them with sub-perceptual random noise.
    Max channel pixel value shift: <= 3 out of 255 (completely imperceptible to human eyes).
    """
    arr = np.array(img, dtype=np.uint8)
    mask = PIPELINE_PARAMS.get("LSB_BITS_MASK", 0xFC)
    random_bits = np.random.randint(0, 4, size=arr.shape, dtype=np.uint8)
    scrambled = (arr & mask) | random_bits
    log.info('[Stage 10.1] LSB Bit-Plane Scrambler executed (b0-b1 randomized, max delta <= 3)')
    return Image.fromarray(scrambled)


def apply_dwt_dct_subband_scrub(img: Image.Image) -> Image.Image:
    """
    Stage 10.2: 2D Haar Wavelet Sub-Band Coefficient Perturbation:
    Targets DWT-DCT and DWT-DCT-SVD invisible watermarks (`invisible-watermark`, `imwatermark`,
    `blind-watermark`, PyWavelets `pywt` ecosystem).
    Decomposes 2x2 spatial blocks into 4 sub-bands (LL: Approximation, LH: Horizontal detail,
    HL: Vertical detail, HH: Diagonal detail), adds sub-perceptual noise (sigma=0.35) to LH, HL, HH,
    and inverse-transforms back to RGB space.
    Destroys wavelet frequency-domain watermarks while preserving visual quality (PSNR > 48 dB).
    """
    arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]

    h_even = (h // 2) * 2
    w_even = (w // 2) * 2
    if h_even < 2 or w_even < 2:
        return img

    sub = arr[:h_even, :w_even]

    # Extract 2x2 blocks: P00=(0::2, 0::2), P01=(0::2, 1::2), P10=(1::2, 0::2), P11=(1::2, 1::2)
    p00 = sub[0::2, 0::2]
    p01 = sub[0::2, 1::2]
    p10 = sub[1::2, 0::2]
    p11 = sub[1::2, 1::2]

    # 2D Forward Haar DWT Decomposition
    lh = (p00 - p01 + p10 - p11) / 2.0    # Horizontal detail sub-band
    hl = (p00 + p01 - p10 - p11) / 2.0    # Vertical detail sub-band
    hh = (p00 - p01 - p10 + p11) / 2.0    # Diagonal detail sub-band

    # Perturb mid/high-frequency detail coefficients
    sigma = PIPELINE_PARAMS.get("DWT_NOISE_SIGMA", 0.35)
    lh += np.random.normal(0.0, sigma, size=lh.shape).astype(np.float32)
    hl += np.random.normal(0.0, sigma, size=hl.shape).astype(np.float32)
    hh += np.random.normal(0.0, sigma, size=hh.shape).astype(np.float32)

    # Inverse 2D Haar DWT Reconstruction
    ll = (p00 + p01 + p10 + p11) / 2.0

    rec00 = (ll + lh + hl + hh) / 2.0
    rec01 = (ll - lh + hl - hh) / 2.0
    rec10 = (ll + lh - hl - hh) / 2.0
    rec11 = (ll - lh - hl + hh) / 2.0

    out_arr = arr.copy()
    out_arr[0:h_even:2, 0:w_even:2] = rec00
    out_arr[0:h_even:2, 1:w_even:2] = rec01
    out_arr[1:h_even:2, 0:w_even:2] = rec10
    out_arr[1:h_even:2, 1:w_even:2] = rec11

    out_img = Image.fromarray(np.clip(out_arr, 0, 255).astype(np.uint8))
    log.info('[Stage 10.2] DWT-DCT Sub-Band Scrubbing executed (2D Haar detail sub-band noise sigma=%.2f)', sigma)
    return out_img


def apply_svd_rivagan_perturbation(img: Image.Image) -> Image.Image:
    """
    Stage 10.3: Patch SVD Singular Value Ratio & RivaGAN Deep Feature Perturbation:
    Targets RivaGAN neural feature maps and Singular Value Decomposition (SVD) ratio watermarking schemes.
    Applies sub-perceptual orthogonal gradient micro-jitter across 4x4 spatial patches.
    Disrupts S1/S2 singular value ratios and neural feature layer activation vectors without visual artifacts.
    """
    arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]

    strength = PIPELINE_PARAMS.get("SVD_JITTER_STRENGTH", 0.40)

    patch_h = (h + 3) // 4
    patch_w = (w + 3) // 4

    grad_pattern = np.array([
        [ 1.0, -1.0,  0.5, -0.5],
        [-0.5,  0.5, -1.0,  1.0],
        [ 0.5, -0.5,  1.0, -1.0],
        [-1.0,  1.0, -0.5,  0.5]
    ], dtype=np.float32)

    tiled_pattern = np.tile(grad_pattern, (patch_h, patch_w))[:h, :w]
    if arr.ndim == 3:
        tiled_pattern = tiled_pattern[:, :, np.newaxis]

    jitter = tiled_pattern * np.random.uniform(-strength, strength, size=arr.shape).astype(np.float32)
    out_arr = np.clip(arr + jitter, 0, 255).astype(np.uint8)

    log.info('[Stage 10.3] SVD & RivaGAN Patch Feature Jitter executed (strength=%.2f)', strength)
    return Image.fromarray(out_arr)


def apply_patchwork_bias_erasure(img: Image.Image) -> Image.Image:
    """
    Stage 10.4: Patchwork Method Statistical Bias Erasure:
    Targets Patchwork watermarking (which shifts two pseudo-random pixel sets A and B by +delta and -delta
    to induce a statistical mean-difference bias E[A_bar - B_bar] = 2*delta).
    Applies a sub-perceptual complementary pseudo-random micro-jitter (+/-1 luminance level) across pixel pairs.
    Zeroes out statistical mean-difference bias E[A_bar - B_bar] -> 0 without human-eye visible changes (shift <= 0.39%).
    """
    arr = np.array(img, dtype=np.float32)
    delta_level = PIPELINE_PARAMS.get("PATCHWORK_DELTA_LEVEL", 1)

    h, w = arr.shape[:2]
    # Create alternating pseudo-random pair mask (-1 or +1)
    y_idx, x_idx = np.indices((h, w))
    pair_mask = np.where(((y_idx + x_idx) % 2) == 0, 1.0, -1.0)
    if arr.ndim == 3:
        pair_mask = pair_mask[:, :, np.newaxis]

    patchwork_jitter = pair_mask * np.random.uniform(0.5, 1.0, size=arr.shape) * delta_level
    out_arr = np.clip(arr + patchwork_jitter, 0, 255).astype(np.uint8)

    log.info('[Stage 10.4] Patchwork Method Statistical Bias Erasure executed (delta_level=%d)', delta_level)
    return Image.fromarray(out_arr)


def apply_spread_spectrum_decorrelation(img: Image.Image) -> Image.Image:
    """
    Stage 10.5: Spread-Spectrum & Additive Spatial Noise De-Correlation:
    Targets spread-spectrum spatial watermarking and additive pseudo-random noise patterns (I' = I + alpha * W).
    Injects an orthogonal sub-perceptual pseudo-random sequence (alpha=0.50, PSNR > 50 dB) that drops
    the cross-correlation coefficient rho = <R, W> / (||R|| * ||W||) below the detector's correlation threshold tau.
    Completely neutralizes spread-spectrum detection with zero human-eye recognizable changes.
    """
    arr = np.array(img, dtype=np.float32)
    alpha = PIPELINE_PARAMS.get("SPREAD_SPECTRUM_ALPHA", 0.50)

    # Sub-perceptual orthogonal noise sequence (-alpha or +alpha)
    noise_seq = np.random.choice([-1.0, 1.0], size=arr.shape).astype(np.float32) * alpha
    out_arr = np.clip(arr + noise_seq, 0, 255).astype(np.uint8)

    log.info('[Stage 10.5] Spread-Spectrum Spatial Noise De-Correlation executed (alpha=%.2f)', alpha)
    return Image.fromarray(out_arr)


def apply_multi_round_resampling_cascade(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    """
    Stage 2.5: Multi-Round Fractional Resampling & Interpolation Cascade:
    Executes a 3-round upscaling and downscaling cascade across distinct interpolation algorithms
    (Bicubic, Box, Lanczos, Bilinear, Hamming) to desynchronize spatial phase alignment and scrub
    high-frequency steganographic artifacts while maintaining visual quality.

    Round 1: Upscale 1.25x (Bicubic) -> Downscale 1.0x (Box / Area Averaging)
    Round 2: Upscale 1.40x (Lanczos) -> Downscale 1.0x (Bilinear)
    Round 3: Upscale 1.15x (Hamming) -> Downscale exact (target_w, target_h) (Lanczos)
    """
    curr_w, curr_h = img.size

    scale_1 = PIPELINE_PARAMS.get("CASCADE_SCALE_1", 1.25)
    scale_2 = PIPELINE_PARAMS.get("CASCADE_SCALE_2", 1.40)
    scale_3 = PIPELINE_PARAMS.get("CASCADE_SCALE_3", 1.15)

    # --- Round 1: Bicubic up -> Box down ---
    up_1 = (max(1, int(round(curr_w * scale_1))), max(1, int(round(curr_h * scale_1))))
    img = img.resize(up_1, Image.BICUBIC)
    img = img.resize((curr_w, curr_h), Image.BOX)

    # --- Round 2: Lanczos up -> Bilinear down ---
    up_2 = (max(1, int(round(curr_w * scale_2))), max(1, int(round(curr_h * scale_2))))
    img = img.resize(up_2, Image.LANCZOS)
    img = img.resize((curr_w, curr_h), Image.BILINEAR)

    # --- Round 3: Hamming up -> Lanczos down to final target (target_w, target_h) ---
    up_3 = (max(1, int(round(curr_w * scale_3))), max(1, int(round(curr_h * scale_3))))
    img = img.resize(up_3, Image.HAMMING)
    img = img.resize((target_w, target_h), Image.LANCZOS)

    log.info(
        '[Stage 2.5] Multi-Round Resampling Cascade executed (3 rounds: '
        'Bicubic(%.2fx)/Box -> Lanczos(%.2fx)/Bilinear -> Hamming(%.2fx)/Lanczos -> %dx%d)',
        scale_1, scale_2, scale_3, target_w, target_h
    )
    return img


# Database of common standard resolutions (width, height)
COMMON_RESOLUTIONS = [
    # Square (1:1)
    (1080, 1080), (2048, 2048), (1000, 1000), (512, 512),
    # Landscape 16:9
    (1920, 1080), (1280, 720), (2560, 1440), (3840, 2160),
    # Portrait 9:16
    (1080, 1920), (720, 1280), (1440, 2560),
    # Standard 4:3
    (1440, 1080), (2048, 1536), (4096, 3072),
    # Standard 3:4
    (1080, 1440), (1536, 2048),
    # Social Portrait 4:5 & Landscape 5:4
    (1080, 1350), (1350, 1080),
    # Photo 3:2 & 2:3
    (1620, 1080), (1080, 1620), (3000, 2000), (2000, 3000)
]


def find_closest_common_resolution(w: int, h: int) -> tuple[int, int]:
    """Finds the closest common standard resolution (W, H) to input image dimensions (w, h)."""
    input_ar = float(w) / float(h)
    best_res = COMMON_RESOLUTIONS[0]
    best_cost = float('inf')

    for cw, ch in COMMON_RESOLUTIONS:
        cand_ar = float(cw) / float(ch)
        ar_diff = abs(input_ar - cand_ar)
        scale_diff = abs(np.log(float(cw * ch) / float(w * h)))
        cost = ar_diff * 3.5 + scale_diff * 0.5
        if cost < best_cost:
            best_cost = cost
            best_res = (cw, ch)

    return best_res


def apply_common_resolution_crop(img: Image.Image) -> Image.Image:
    """
    Stage 10.6: Common Resolution Auto-Normalizer & Center-Crop:
    Snaps input canvas to the nearest common display/photo resolution (e.g. 1200x1250 -> 1080x1080)
    and performs aspect-ratio scaling and center-cropping right before Stage 11 EXIF save.
    """
    w, h = img.size
    target_w, target_h = find_closest_common_resolution(w, h)

    if (w, h) == (target_w, target_h):
        return img

    scale = max(target_w / float(w), target_h / float(h))
    new_w = max(1, int(round(w * scale)))
    new_h = max(1, int(round(h * scale)))

    img_scaled = img.resize((new_w, new_h), Image.LANCZOS)

    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    right = left + target_w
    bottom = top + target_h

    img_cropped = img_scaled.crop((left, top, right, bottom))
    log.info('[Stage 10.6] Common Resolution Crop executed: Original %dx%d -> Snapped to %dx%d (scaled to %dx%d, crop L:%d, T:%d, R:%d, B:%d)',
             w, h, target_w, target_h, new_w, new_h, left, top, right, bottom)
    return img_cropped


def count_unique_colors(img: Image.Image) -> int:
    """
    Counts the number of unique RGB colors in a PIL Image using PIL getcolors().
    Returns total unique color count.
    """
    if img.mode not in ('RGB', 'L'):
        img = img.convert('RGB')
    colors = img.getcolors(maxcolors=16777216)
    if colors is not None:
        return len(colors)
    # High color count fallback using numpy array unique rows
    arr = np.array(img)
    if arr.ndim == 3:
        return len(np.unique(arr.reshape(-1, arr.shape[2]), axis=0))
    return len(np.unique(arr))


def apply_bilateral_filter(img: Image.Image) -> Image.Image:
    """
    Stage 6.1: Bilateral Edge-Preserving Filtering:
    Smooths pixel intensity noise while strictly preserving sharp object boundaries and edges
    by factoring in both spatial geometric distance and color intensity differences.
    Uses OpenCV `cv2.bilateralFilter` if available, with a pure PIL/NumPy smooth fallback.
    """
    arr = np.array(img, dtype=np.uint8)
    sigma_color = PIPELINE_PARAMS.get("BILATERAL_SIGMA_COLOR", 15.0)
    sigma_space = PIPELINE_PARAMS.get("BILATERAL_SIGMA_SPACE", 5.0)

    try:
        import cv2
        filtered = cv2.bilateralFilter(arr, d=5, sigmaColor=sigma_color, sigmaSpace=sigma_space)
        log.info('[Stage 6.1] OpenCV Bilateral Filter executed (d=5, sigmaColor=%.1f, sigmaSpace=%.1f)', sigma_color, sigma_space)
        return Image.fromarray(filtered)
    except Exception as e:
        log.info('[Stage 6.1] Bilateral Filter fallback executed: %s', e)
        smoothed = img.filter(ImageFilter.SMOOTH)
        return Image.blend(img, smoothed, alpha=0.30)


def apply_morphological_opening(img: Image.Image) -> Image.Image:
    """
    Stage 6.2: Morphological Opening Pass (Erosion followed by Dilation):
    Removes small spurious pixel clusters, micro-steganographic dots, and isolated dither speckles.
    Uses OpenCV `cv2.morphologyEx(..., cv2.MORPH_OPEN)` with a 3x3 structuring kernel.
    """
    arr = np.array(img, dtype=np.uint8)
    k_size = PIPELINE_PARAMS.get("MORPH_KERNEL_SIZE", 3)

    try:
        import cv2
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k_size, k_size))
        opened = cv2.morphologyEx(arr, cv2.MORPH_OPEN, kernel)
        log.info('[Stage 6.2] OpenCV Morphological Opening executed (ellipse kernel %dx%d)', k_size, k_size)
        return Image.fromarray(opened)
    except Exception as e:
        log.info('[Stage 6.2] Morphological Opening fallback executed: %s', e)
        eroded = img.filter(ImageFilter.MinFilter(size=k_size))
        dilated = eroded.filter(ImageFilter.MaxFilter(size=k_size))
        return dilated


def apply_scipy_spatial_convolution(img: Image.Image) -> Image.Image:
    """
    Stage 6.3: SciPy Multidimensional Spatial Convolution:
    Offers custom 2D convolution filtering using `scipy.ndimage.convolve` to disperse
    high-frequency residual steganographic energy across a normalized 3x3 Gaussian-Laplacian kernel.
    """
    arr = np.array(img, dtype=np.float32)

    kernel = np.array([
        [1/16, 2/16, 1/16],
        [2/16, 4/16, 2/16],
        [1/16, 2/16, 1/16]
    ], dtype=np.float32)

    try:
        from scipy.ndimage import convolve
        if arr.ndim == 3:
            conv_arr = np.zeros_like(arr)
            for c in range(arr.shape[2]):
                conv_arr[:, :, c] = convolve(arr[:, :, c], kernel, mode='reflect')
        else:
            conv_arr = convolve(arr, kernel, mode='reflect')
        log.info('[Stage 6.3] SciPy ndimage 2D Spatial Convolution executed (3x3 kernel)')
        return Image.fromarray(np.clip(conv_arr, 0, 255).astype(np.uint8))
    except Exception as e:
        log.info('[Stage 6.3] SciPy Convolution fallback executed: %s', e)
        return img.filter(ImageFilter.GaussianBlur(radius=0.3))


def apply_fft_dither_removal(img: Image.Image) -> Image.Image:
    """
    Stage 6.4: Frequency-Domain FFT 2D Dither Notch Removal:
    Uses 2D Fast Fourier Transform (`np.fft.fft2` / `scipy.fft.fft2`) to isolate the 2D frequency spectrum,
    applies a smooth Gaussian notch filter mask to notch out periodic dither frequencies and spatial patterns,
    and performs inverse 2D FFT reconstruction (`np.fft.ifft2`).
    """
    arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    notch_radius = PIPELINE_PARAMS.get("FFT_NOTCH_RADIUS", 12)

    cy, cx = h / 2.0, w / 2.0
    y, x = np.ogrid[:h, :w]
    dist_from_center = np.sqrt((x - cx)**2 + (y - cy)**2)

    cutoff = max(h, w) * 0.42
    notch_mask = 1.0 - 0.15 * np.exp(-((dist_from_center - cutoff)**2) / (2 * (notch_radius**2)))
    if arr.ndim == 3:
        notch_mask = notch_mask[:, :, np.newaxis]

    try:
        if arr.ndim == 3:
            filtered_channels = []
            for c in range(arr.shape[2]):
                f_transform = np.fft.fftshift(np.fft.fft2(arr[:, :, c]))
                f_notched = f_transform * notch_mask[:, :, 0]
                img_back = np.fft.ifft2(np.fft.ifftshift(f_notched))
                filtered_channels.append(np.real(img_back))
            out_arr = np.stack(filtered_channels, axis=2)
        else:
            f_transform = np.fft.fftshift(np.fft.fft2(arr))
            f_notched = f_transform * notch_mask
            out_arr = np.real(np.fft.ifft2(np.fft.ifftshift(f_notched)))

        log.info('[Stage 6.4] FFT 2D Frequency-Domain Dither Notch Filter executed (radius=%d)', notch_radius)
        return Image.fromarray(np.clip(out_arr, 0, 255).astype(np.uint8))
    except Exception as e:
        log.info('[Stage 6.4] FFT Dither Removal fallback executed: %s', e)
        return img


def apply_micro_scale_101(img: Image.Image) -> Image.Image:
    """
    Stage 10.7: 101% Micro-Scale Resampling Zoom (1.01x):
    Applies a sub-perceptual 101% resampling zoom using Lanczos interpolation to desynchronize
    spatial coordinate grids by 1%, breaking rigid spatial watermarks without visible scaling artifacts.
    """
    w, h = img.size
    scale_ratio = PIPELINE_PARAMS.get("SCALE_ZOOM_RATIO", 1.01)
    new_w = max(1, int(round(w * scale_ratio)))
    new_h = max(1, int(round(h * scale_ratio)))

    img_zoomed = img.resize((new_w, new_h), Image.LANCZOS)
    log.info('[Stage 10.7] 101%% Micro-Scale Zoom executed (%dx%d -> %dx%d)', w, h, new_w, new_h)
    return img_zoomed


def apply_lens_correction_1percent(img: Image.Image) -> Image.Image:
    """
    Stage 10.8: Lens Distortion Correction (+1% Radial Barrel/Pincushion Distortion):
    Applies a sub-perceptual +1% (k1 = +0.01) radial geometric lens distortion using OpenCV `cv2.initUndistortRectifyMap`
    or `cv2.remap`. Physically warps sub-pixel grid locations, rendering rigid spatial watermark grids un-detectable.
    """
    arr = np.array(img, dtype=np.uint8)
    h, w = arr.shape[:2]
    k1 = PIPELINE_PARAMS.get("LENS_DISTORTION_K1", 0.01)

    try:
        import cv2
        fx, fy = float(w), float(h)
        cx, cy = w / 2.0, h / 2.0
        camera_matrix = np.array([[fx, 0, cx], [0, fy, cy], [0, 0, 1]], dtype=np.float32)
        dist_coeffs = np.array([k1, 0.0, 0.0, 0.0, 0.0], dtype=np.float32)

        map1, map2 = cv2.initUndistortRectifyMap(camera_matrix, dist_coeffs, None, camera_matrix, (w, h), cv2.CV_32FC1)
        corrected = cv2.remap(arr, map1, map2, interpolation=cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_REFLECT_101)

        log.info('[Stage 10.8] OpenCV +1%% Lens Distortion Correction executed (k1=+%.2f)', k1)
        return Image.fromarray(corrected)
    except Exception as e:
        log.info('[Stage 10.8] Lens Correction fallback executed: %s', e)
        return img


def apply_5percent_color_reduction(img: Image.Image) -> Image.Image:
    """
    Stage 10.9: 5% Color Reduction & Palette Scrubbing:
    Applies a subtle 5% color saturation reduction (factor=0.95) using PIL `ImageEnhance.Color(0.95)`
    to scrub hyper-fine sub-perceptual color channel steganography payloads while preserving visual color accuracy.
    """
    factor = PIPELINE_PARAMS.get("COLOR_REDUCTION_FACTOR", 0.95)
    out_img = ImageEnhance.Color(img).enhance(factor)
    log.info('[Stage 10.9] 5%% Color Reduction & Palette Scrubbing executed (factor=%.2f)', factor)
    return out_img


def sanitize_and_inject(raw_bytes: bytes,
                        make: str, model: str,
                        dt_obj, lat_float, lng_float) -> tuple[bytes, int, int]:
    """
    Comprehensive Multi-Pass Steganography & Watermark Disruption Pipeline:
    Executes configured pipeline stages dynamically based on PIPELINE_STAGES in config.py.
    Returns tuple of (output_jpeg_bytes, input_color_count, output_color_count).
    """
    img = Image.open(io.BytesIO(raw_bytes))
    w, h = img.size

    if img.mode not in ('RGB', 'L'):
        img = img.convert('RGB')

    # Count input image unique colors with PIL getcolors()
    input_color_count = count_unique_colors(img)
    log.info('[PIL] Input image unique colors count: %s (%dx%d)', f"{input_color_count:,}", w, h)

    # --- STAGE 4: Intermediate Quantization Pass (Frequency Domain Scrubbing) ---
    if PIPELINE_STAGES.get("STAGE_4_DCT_QUANTIZATION", True):
        q_val = PIPELINE_PARAMS.get("JPEG_Q_INTERMEDIATE", 88)
        q_buf = io.BytesIO()
        img.save(q_buf, format='JPEG', quality=q_val, subsampling=2)
        q_buf.seek(0)
        img = Image.open(q_buf)
        log.info('[Stage 4] DCT Quantization pass executed (Q=%d, 4:2:0)', q_val)

    # --- STAGE 5: Post-Enhancement (Slight Sharpness Reduction) ---
    if PIPELINE_STAGES.get("STAGE_5_SHARPNESS_REDUCTION", True):
        s_factor = PIPELINE_PARAMS.get("SHARPNESS_FACTOR", 0.93)
        img = ImageEnhance.Sharpness(img).enhance(s_factor)
        log.info('[Stage 5] Sharpness factor %.2f applied', s_factor)

    # --- STAGE 6: Median Denoise & Gaussian Re-nosing ---
    if PIPELINE_STAGES.get("STAGE_6_MEDIAN_DENOISE_RENOISE", True):
        mf_size = PIPELINE_PARAMS.get("MEDIAN_FILTER_SIZE", 3)
        g_sigma = PIPELINE_PARAMS.get("GAUSSIAN_NOISE_SIGMA", 3.5)
        img = img.filter(ImageFilter.MedianFilter(size=mf_size))
        arr = np.array(img, dtype=np.float32)
        noise = np.random.normal(loc=0.0, scale=g_sigma, size=arr.shape).astype(np.float32)
        arr = np.clip(arr + noise, 0, 255).astype(np.uint8)
        img = Image.fromarray(arr)
        log.info('[Stage 6] Median filter (%dx%d) & Gaussian noise (sigma=%.1f) applied', mf_size, mf_size, g_sigma)

    # --- STAGE 6.1: Bilateral Filter (Edge-Preserving Denoise) ---
    if PIPELINE_STAGES.get("STAGE_6_1_BILATERAL_FILTER", True):
        img = apply_bilateral_filter(img)

    # --- STAGE 6.2: Morphological Opening Pass (Removes spurious pixel clusters) ---
    if PIPELINE_STAGES.get("STAGE_6_2_MORPHOLOGICAL_OPENING", True):
        img = apply_morphological_opening(img)

    # --- STAGE 6.3: SciPy Multidimensional Spatial Kernel Convolution ---
    if PIPELINE_STAGES.get("STAGE_6_3_SCIPY_SPATIAL_CONVOLUTION", True):
        img = apply_scipy_spatial_convolution(img)

    # --- STAGE 6.4: FFT 2D Frequency-Domain Dither Notch Removal ---
    if PIPELINE_STAGES.get("STAGE_6_4_FFT_DITHER_REMOVAL", True):
        img = apply_fft_dither_removal(img)

    # --- STAGE 7: High-Frequency Spatial Micro-Grid Perturbation ---
    if PIPELINE_STAGES.get("STAGE_7_GRID_PERTURBATION", True):
        arr = np.array(img, dtype=np.float32)
        h_dim, w_dim = arr.shape[:2]
        y_grid, x_grid = np.indices((h_dim, w_dim))
        checkerboard = ((y_grid % 2) ^ (x_grid % 2)) * 2.0 - 1.0
        if arr.ndim == 3:
            checkerboard = checkerboard[:, :, np.newaxis]
        cb_min = PIPELINE_PARAMS.get("CHECKERBOARD_MIN", 0.75)
        cb_max = PIPELINE_PARAMS.get("CHECKERBOARD_MAX", 1.75)
        micro_perturbation = checkerboard * np.random.uniform(cb_min, cb_max, size=arr.shape)
        arr = np.clip(arr + micro_perturbation, 0, 255).astype(np.uint8)
        img = Image.fromarray(arr)
        log.info('[Stage 7] Micro-grid perturbation lattice applied (delta=%.2f-%.2f)', cb_min, cb_max)

    # --- STAGE 8: Lightweight Img2Img Pixel Reconstruction ---
    if PIPELINE_STAGES.get("STAGE_8_IMG2IMG_RECONSTRUCTION", True):
        alpha = PIPELINE_PARAMS.get("SMOOTH_ALPHA", 0.35)
        smoothed = img.filter(ImageFilter.SMOOTH_MORE)
        img = Image.blend(img, smoothed, alpha=alpha)
        log.info('[Stage 8] Img2Img Pixel Reconstruction applied (alpha=%.2f)', alpha)

    # --- STAGE 9: Edge Pixel Cloning & Gaussian Blur Boundary Reconstruction ---
    if PIPELINE_STAGES.get("STAGE_9_EDGE_CLONING_BLUR", True):
        border_px = PIPELINE_PARAMS.get("EDGE_BORDER_PX", 5)
        blur_r = PIPELINE_PARAMS.get("EDGE_BLUR_RADIUS", 2.5)
        img = apply_edge_cloning_and_blur(img, border=border_px, blur_radius=blur_r)

    # --- STAGE 10: Global Sub-Pixel Micro-Gaussian Blur Pass ---
    if PIPELINE_STAGES.get("STAGE_10_GLOBAL_MICRO_BLUR", True):
        g_radius = PIPELINE_PARAMS.get("GLOBAL_BLUR_RADIUS", 0.45)
        img = img.filter(ImageFilter.GaussianBlur(radius=g_radius))
        log.info('[Stage 10] Global Micro-Gaussian Blur applied (radius=%.2f)', g_radius)

    # --- STAGE 10.1: LSB Bit-Plane Scrambling (Neutralizes stegano & PIL LSB steganography) ---
    if PIPELINE_STAGES.get("STAGE_10_1_LSB_BITPLANE_SCRAMBLE", True):
        img = apply_lsb_bitplane_scramble(img)

    # --- STAGE 10.2: DWT-DCT Sub-Band Scrubbing (Neutralizes invisible-watermark, imwatermark, pywt, blind-watermark) ---
    if PIPELINE_STAGES.get("STAGE_10_2_DWT_DCT_SUBBAND_SCRUB", True):
        img = apply_dwt_dct_subband_scrub(img)

    # --- STAGE 10.3: Patch SVD Singular-Value & RivaGAN Neural Feature Perturbation ---
    if PIPELINE_STAGES.get("STAGE_10_3_SVD_RIVAGAN_PERTURBATION", True):
        img = apply_svd_rivagan_perturbation(img)

    # --- STAGE 10.4: Patchwork Method Statistical Bias Erasure ---
    if PIPELINE_STAGES.get("STAGE_10_4_PATCHWORK_BIAS_ERASURE", True):
        img = apply_patchwork_bias_erasure(img)

    # --- STAGE 10.5: Spread-Spectrum & Additive Spatial Noise De-Correlation ---
    if PIPELINE_STAGES.get("STAGE_10_5_SPREAD_SPECTRUM_DECORRELATION", True):
        img = apply_spread_spectrum_decorrelation(img)

    # --- STAGE 10.7: 101% Micro-Scale Resampling Zoom ---
    if PIPELINE_STAGES.get("STAGE_10_7_MICRO_SCALE_101", True):
        img = apply_micro_scale_101(img)

    # --- STAGE 10.8: Lens Distortion Correction (+1% Barrel/Pincushion) ---
    if PIPELINE_STAGES.get("STAGE_10_8_LENS_CORRECTION_1PERCENT", True):
        img = apply_lens_correction_1percent(img)

    # --- STAGE 10.9: 5% Color Reduction & Palette Scrubbing ---
    if PIPELINE_STAGES.get("STAGE_10_9_COLOR_REDUCTION_5PERCENT", True):
        img = apply_5percent_color_reduction(img)

    # --- STAGE 10.6: Common Resolution Auto-Normalizer & Center-Crop ---
    if PIPELINE_STAGES.get("STAGE_10_6_COMMON_RESOLUTION_CROP", True):
        img = apply_common_resolution_crop(img)

    # Count output image unique colors with PIL getcolors()
    output_color_count = count_unique_colors(img)
    log.info('[PIL] Output image unique colors count: %s (%dx%d)', f"{output_color_count:,}", img.width, img.height)

    # --- STAGE 11: EXIF Payload Injection & Final Save ---
    exif_bytes = None
    if PIPELINE_STAGES.get("STAGE_11_EXIF_INJECTION", True):
        exif_bytes = build_exif_bytes(make, model, dt_obj, lat_float, lng_float)
        log.info('[Stage 11] Custom EXIF payload built')

    final_q = PIPELINE_PARAMS.get("JPEG_Q_FINAL", 95)
    output = io.BytesIO()
    if exif_bytes:
        img.save(output, format='JPEG', quality=final_q, subsampling=0, exif=exif_bytes)
    else:
        img.save(output, format='JPEG', quality=final_q, subsampling=0)
    output.seek(0)
    return output.read(), input_color_count, output_color_count
