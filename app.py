import io
import logging
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file

from config import (
    MAX_CONTENT_LENGTH,
    ALLOWED_EXTENSIONS,
    DEFAULT_PORT,
    DEFAULT_DEBUG
)
from image_pipeline import sanitize_and_inject

# ── LOGGING & APP INITIALIZATION ─────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s in %(module)s: %(message)s'
)
log = logging.getLogger('PixelBeam')

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH


def allowed_file(filename: str) -> bool:
    """Validate upload file extension against configured whitelist."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/')
def index():
    """Render the main glassmorphism single-page UI."""
    return render_template('index.html')


@app.route('/process', methods=['POST'])
def process():
    """
    Process image through configured 11-stage steganography disruption pipeline
    and inject user-specified EXIF metadata.
    """
    if 'image' not in request.files:
        return jsonify({'error': 'No image file uploaded.'}), 400

    file = request.files['image']
    if not file or file.filename == '':
        return jsonify({'error': 'No file selected.'}), 400

    if not allowed_file(file.filename):
        return jsonify({'error': 'Unsupported file type. Only JPEG and PNG are allowed.'}), 400

    try:
        raw_bytes = file.read()
        if not raw_bytes:
            return jsonify({'error': 'Uploaded file is empty.'}), 400

        # Form fields
        make = request.form.get('make', '').strip()
        model = request.form.get('model', '').strip()
        dt_str = request.form.get('datetime', '').strip()
        lat_str = request.form.get('lat', '').strip()
        lng_str = request.form.get('lng', '').strip()

        # Parse datetime
        dt_obj = None
        if dt_str:
            try:
                dt_obj = datetime.fromisoformat(dt_str)
            except ValueError:
                log.warning('Could not parse ISO datetime string: %r', dt_str)

        # Parse GPS coordinates
        lat_float = None
        lng_float = None
        if lat_str and lng_str:
            try:
                lat_float = float(lat_str)
                lng_float = float(lng_str)
            except ValueError:
                log.warning('Could not parse GPS floats: lat=%r, lng=%r', lat_str, lng_str)

        log.info('Processing %s (%d bytes) — Make: %r, Model: %r', file.filename, len(raw_bytes), make, model)

        # Execute in-memory image processing pipeline
        out_bytes, in_colors, out_colors = sanitize_and_inject(raw_bytes, make, model, dt_obj, lat_float, lng_float)

        response = send_file(
            io.BytesIO(out_bytes),
            mimetype='image/jpeg',
            as_attachment=True,
            download_name='pixelbeam_processed.jpg'
        )
        response.headers['X-Input-Colors'] = str(in_colors)
        response.headers['X-Output-Colors'] = str(out_colors)
        return response

    except Exception as exc:
        log.exception('Error during image processing: %s', exc)
        return jsonify({'error': f'Processing failed: {str(exc)}'}), 500


@app.errorhandler(413)
def request_entity_too_large(error):
    """Handle upload size limit exceed error."""
    return jsonify({'error': f'File size exceeds maximum allowed limit ({app.config["MAX_CONTENT_LENGTH"] // (1024*1024)} MB).'}), 413


if __name__ == '__main__':
    log.info('Starting PixelBeam server on port %d (debug=%s)', DEFAULT_PORT, DEFAULT_DEBUG)
    app.run(host='0.0.0.0', port=DEFAULT_PORT, debug=DEFAULT_DEBUG)
