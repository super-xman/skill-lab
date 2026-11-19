"""Register artwork in guide coordinates, retaining the paint's native pixel density."""
import cv2 as cv
import numpy as np

from sphere import sample


def grey(rgb):
    return cv.cvtColor(rgb, cv.COLOR_RGB2GRAY)


def fit(reference, painted, mask=None, *, perspective=False):
    """Return reference-to-paint transform in analysis pixels and a diagnostic."""
    detector = cv.SIFT_create(5000, contrastThreshold=0.012)
    a, da = detector.detectAndCompute(reference, mask)
    b, db = detector.detectAndCompute(painted, None)
    identity = np.eye(3)
    if da is None or db is None or len(db) < 2:
        return identity, "few features; inspect alignment visually"
    pairs = [hits[0] for hits in cv.BFMatcher().knnMatch(da, db, k=2)
             if len(hits) == 2 and hits[0].distance < 0.76 * hits[1].distance]
    if len(pairs) < 12:
        return identity, "few feature matches; inspect alignment visually"
    src = np.float32([a[m.queryIdx].pt for m in pairs])
    dst = np.float32([b[m.trainIdx].pt for m in pairs])
    if perspective:
        matrix, inliers = cv.findHomography(src, dst, cv.RANSAC, 3)
    else:
        affine, inliers = cv.estimateAffine2D(src, dst, method=cv.RANSAC, ransacReprojThreshold=3)
        matrix = np.vstack([affine, [0, 0, 1]]) if affine is not None else None
    if matrix is None or inliers is None or np.count_nonzero(inliers) < 12:
        return identity, "unreliable feature fit; inspect alignment visually"
    h, w = reference.shape
    if mask is None:
        x, y, ww, hh = 0, 0, w, h
    else:
        x, y, ww, hh = cv.boundingRect(mask)
    anchors = np.float32([[[x,y],[x+ww-1,y],[x,y+hh-1],[x+ww-1,y+hh-1]]])
    drift = np.linalg.norm(cv.perspectiveTransform(anchors, matrix) - anchors, axis=2).max()
    if not np.isfinite(drift) or drift > 0.16 * max(ww, hh):
        raise ValueError(f"Artwork moved too far from its guide ({drift:.0f} analysis pixels). "
                         "Reframe or regenerate the painting before merging.")
    return matrix, f"{int(inliers.sum())} inliers, corner shift ≤{drift:.1f} analysis px"


def register_panel(guide, art):
    gh, gw = guide.shape[:2]
    ah, aw = art.shape[:2]
    if abs((aw / ah) / (gw / gh) - 1) > 0.025:
        raise ValueError(f"Paint is {aw}×{ah}, guide is {gw}×{gh}. Restore the guide framing.")
    w = min(900, gw, aw)
    h = round(w * gh / gw)
    if min(w, h) < 16:
        raise ValueError("The painted panel is too small to register.")
    ref = cv.resize(grey(guide), (w, h), interpolation=cv.INTER_AREA)
    moving = cv.resize(grey(art), (w, h), interpolation=cv.INTER_AREA)
    matrix, message = fit(ref, moving, perspective=True)
    aligned = cv.warpPerspective(moving, matrix, (w, h), flags=cv.WARP_INVERSE_MAP | cv.INTER_LINEAR,
                                 borderMode=cv.BORDER_REPLICATE)
    contrast = cv.createCLAHE(2, (8, 8))
    ref, aligned = [contrast.apply(cv.GaussianBlur(im, (0, 0), 1.5)) for im in (ref, aligned)]
    dis = cv.DISOpticalFlow_create(cv.DISOPTICAL_FLOW_PRESET_MEDIUM)
    # DIS requires at least one dimension >= 12 at its coarsest scale.
    dis.setFinestScale(1 if min(w, h) >= 32 else 0)
    flow = dis.calc(ref, aligned, None)
    flow = np.clip(cv.GaussianBlur(flow, (0, 0), 5), -0.035 * w, 0.035 * w)

    oh = round(aw * gh / gw)
    xx, yy = np.meshgrid((np.arange(aw, dtype=np.float32) + 0.5) * w / aw - 0.5,
                         (np.arange(oh, dtype=np.float32) + 0.5) * h / oh - 0.5)
    offsets = cv.remap(flow, xx, yy, cv.INTER_LINEAR, borderMode=cv.BORDER_REPLICATE)
    coords = np.stack((xx, yy), axis=-1) + offsets
    mapped = cv.perspectiveTransform(coords, matrix)
    registered = sample(art, (mapped[:,:,0] + 0.5) * aw / w - 0.5,
                        (mapped[:,:,1] + 0.5) * ah / h - 0.5)
    # Match only the low-frequency colour field, leaving small brush marks intact.
    target = cv.resize(guide, (aw, oh))
    sigma = max(3, 0.013 * aw)
    low_ref, low_art = [cv.GaussianBlur(im, (0, 0), sigma).astype(np.int16)
                        for im in (target, registered)]
    correction = np.clip(low_ref - low_art, -24, 24) * 0.85
    return np.clip(registered + correction, 0, 255).astype(np.uint8), message
