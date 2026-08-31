import logging
import piexif

log = logging.getLogger('PixelBeam.EXIF')


def decimal_to_dms_rational(decimal_degrees: float):
    """Convert decimal degrees to a piexif rational DMS tuple ((deg, 1), (min, 1), (sec_num, 1000))."""
    dd = abs(decimal_degrees)
    d = int(dd)
    m = int((dd - d) * 60)
    s_num = int(round(((dd - d) * 60 - m) * 60 * 1000))
    return ((d, 1), (m, 1), (s_num, 1000))


def build_exif_bytes(make: str, model: str, dt_obj, lat_float, lng_float) -> bytes:
    """
    Build a complete piexif EXIF payload (IFD0 + ExifIFD + GPSIFD).
    Returns raw bytes suitable for PIL's exif= save parameter.
    """
    zeroth = {}
    exif   = {}
    gps    = {}

    if make:
        zeroth[piexif.ImageIFD.Make] = make.encode('utf-8')
        log.info('EXIF: Make    = %r', make)
    if model:
        zeroth[piexif.ImageIFD.Model] = model.encode('utf-8')
        log.info('EXIF: Model   = %r', model)

    if dt_obj is not None:
        dt_bytes = dt_obj.strftime('%Y:%m:%d %H:%M:%S').encode('utf-8')
        zeroth[piexif.ImageIFD.DateTime]       = dt_bytes
        exif[piexif.ExifIFD.DateTimeOriginal]  = dt_bytes
        exif[piexif.ExifIFD.DateTimeDigitized] = dt_bytes
        log.info('EXIF: DateTime = %r', dt_obj.strftime('%Y:%m:%d %H:%M:%S'))

    if lat_float is not None and lng_float is not None:
        gps[piexif.GPSIFD.GPSLatitudeRef]  = ('N' if lat_float >= 0 else 'S').encode()
        gps[piexif.GPSIFD.GPSLatitude]     = decimal_to_dms_rational(lat_float)
        gps[piexif.GPSIFD.GPSLongitudeRef] = ('E' if lng_float >= 0 else 'W').encode()
        gps[piexif.GPSIFD.GPSLongitude]    = decimal_to_dms_rational(lng_float)
        gps[piexif.GPSIFD.GPSAltitudeRef]  = b'\x00'
        gps[piexif.GPSIFD.GPSAltitude]     = (0, 1)
        log.info('EXIF: GPS     = (%.6f, %.6f)', lat_float, lng_float)

    return piexif.dump({'0th': zeroth, 'Exif': exif, 'GPS': gps, '1st': {}, 'thumbnail': None})
