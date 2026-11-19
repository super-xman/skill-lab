"""Pixel-centred spherical sampling. Yaw increases rightward; pitch increases upward."""
from io import BytesIO

import cv2 as cv
import numpy as np
from PIL import Image, ImageCms, ImageOps


def read_rgb(path):
    with Image.open(path) as image:
        oriented = ImageOps.exif_transpose(image)
        if profile := oriented.info.get("icc_profile"):
            try:
                oriented = ImageCms.profileToProfile(oriented, BytesIO(profile),
                                                     ImageCms.createProfile("sRGB"), outputMode="RGB")
            except (ImageCms.PyCMSError, OSError):
                # Some encoders attach a malformed profile. Preserve the decoded pixel values.
                pass
        return np.array(oriented.convert("RGB"))


def save_png(path, rgb):
    Image.fromarray(rgb).save(path, format="PNG", compress_level=2)


def read_atlas(path):
    rgb = read_rgb(path)
    height, width = rgb.shape[:2]
    if width != 2 * height:
        raise ValueError(f"{path}: expected a 2:1 equirectangular image, got {width}×{height}")
    return rgb


def angles(width, top, bottom):
    lon = ((np.arange(width, dtype=np.float32)[None, :] + 0.5) / width - 0.5) * (2 * np.pi)
    lat = (0.5 - (np.arange(top, bottom, dtype=np.float32)[:, None] + 0.5) / (width / 2)) * np.pi
    return lon, lat


def sample(rgb, x, y, wrap=False):
    height, width = rgb.shape[:2]
    x, y = np.broadcast_arrays(x, np.clip(y, 0, height - 1))
    border = cv.BORDER_WRAP if wrap else cv.BORDER_REPLICATE
    return cv.remap(rgb, x.astype(np.float32, copy=False), y.astype(np.float32, copy=False),
                    cv.INTER_LINEAR, borderMode=border)


def view(rgb, width, height, yaw, pitch, hfov):
    """Rectilinear view of an atlas; yaw=0 faces the centre of the atlas."""
    ih, iw = rgb.shape[:2]
    yaw, pitch = np.radians([yaw, pitch])
    scale = 2 * np.tan(np.radians(hfov / 2)) / width
    u = (np.arange(width, dtype=np.float32)[None, :] + 0.5 - width / 2) * scale
    result = np.empty((height, width, 3), np.uint8)
    for top in range(0, height, 128):
        bottom = min(top + 128, height)
        v = (height / 2 - np.arange(top, bottom, dtype=np.float32)[:, None] - 0.5) * scale
        up = np.sin(pitch) + v * np.cos(pitch)
        forward = np.cos(pitch) - v * np.sin(pitch)
        lon = np.arctan2(u, forward) + yaw
        lat = np.arctan2(up, np.hypot(u, forward))
        result[top:bottom] = sample(rgb, (0.5 + lon / (2 * np.pi)) * iw - 0.5,
                                    (0.5 - lat / np.pi) * ih - 0.5, wrap=True)
    return result


def ease(x):
    t = np.clip(x, 0, 1)
    return t * t * (3 - 2 * t)


def original_map(lon, lat, shape, settings):
    h, w = shape[:2]
    span = np.radians(settings["hfov"])
    if settings["projection"] == "cylindrical":
        f = w / span
        x = w / 2 + lon * f - 0.5
        y = h * settings["horizon"] - np.tan(lat) * f - 0.5
    else:
        f = w / (2 * np.tan(span / 2))
        x = w / 2 + np.tan(lon) * f - 0.5
        y = h * settings["horizon"] - np.tan(lat) * f / np.maximum(np.cos(lon), 1e-5) - 0.5
    inside = (np.abs(lon) <= span / 2) & (x >= 0) & (x <= w - 1) & (y >= 0) & (y <= h - 1)
    # Feather only the outer few percent. Interior landmark pixels come from the original.
    alpha = ease(np.minimum(x, w - 1 - x) / max(1, 0.035 * w))
    alpha = alpha * ease(np.minimum(y, h - 1 - y) / max(1, 0.05 * h)) * inside
    return x, y, alpha, inside


def panel_map(lon, lat, panel, shape):
    h, w = shape[:2]
    pitch, yaw = np.radians([panel["pitch"], panel["yaw"]])
    side = np.cos(lat) * np.sin(lon - yaw)
    forward = np.cos(lat) * np.cos(lon - yaw)
    depth = forward * np.cos(pitch) + np.sin(lat) * np.sin(pitch)
    vertical = np.sin(lat) * np.cos(pitch) - forward * np.sin(pitch)
    tan_h = np.tan(np.radians(panel["hfov"] / 2))
    denom = np.maximum(depth, 1e-5) * tan_h
    u, v = side / denom, vertical / (denom * panel["height"] / panel["width"])
    margin = 1 - np.maximum(np.abs(u), np.abs(v))
    alpha = ease(margin / 0.19) * (depth > 0)
    return (u + 1) * w / 2 - 0.5, (1 - v) * h / 2 - 0.5, alpha


def blend(canvas, layer, x, y, alpha):
    rows = np.flatnonzero(np.any(alpha > 0, axis=1))
    cols = np.flatnonzero(np.any(alpha > 0, axis=0))
    if not rows.size or not cols.size:
        return
    area = np.s_[rows[0]:rows[-1]+1, cols[0]:cols[-1]+1]
    x, y = np.broadcast_arrays(x, y)
    pixels = sample(layer, x[area], y[area])
    weight = alpha[area][..., None].astype(np.float32)
    dest = canvas[area]
    dest[:] = np.rint(dest * (1 - weight) + pixels * weight).astype(np.uint8)


def check_camera(p):
    if not (-90 <= p["pitch"] <= 90 and np.isfinite(p["yaw"]) and 1 < p["hfov"] < 175):
        raise ValueError(f"Invalid camera angles: {p}")
    if any(type(p[k]) is not int or not 16 <= p[k] <= 16384 for k in ("width", "height")):
        raise ValueError(f"Invalid view dimensions: {p}")
