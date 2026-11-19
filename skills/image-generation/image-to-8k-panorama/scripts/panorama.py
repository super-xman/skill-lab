#!/usr/bin/env python3
"""Prepare a single-image outpaint, register perspective paintings and render the sphere."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil

import cv2 as cv
import numpy as np
from PIL import Image

from registration import fit, grey, register_panel
from sphere import (angles, blend, check_camera, ease, original_map, panel_map, read_atlas,
                    read_rgb, sample, save_png, view)


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def digest(path):
    with path.open("rb") as fh:
        return hashlib.file_digest(fh, "sha256").hexdigest()


def width_2to1(width):
    if not 64 <= width <= 16384 or width % 2:
        raise ValueError("Atlas width must be even, between 64 and 16384.")
    return width


def scene_at(work):
    cfg = json.loads((work / "scene.json").read_text(encoding="utf-8"))
    core = cfg["original"]
    max_span = {"perspective": 175, "cylindrical": 360}[core["projection"]]
    if not (1 < core["hfov"] < max_span and np.isfinite(core["horizon"])):
        raise ValueError("Check the source horizontal FOV and horizon in scene.json.")
    ids = set()
    for p in cfg["panels"]:
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]*", p["id"]) or p["id"] in ids:
            raise ValueError(f"Invalid or repeated panel ID: {p['id']}")
        ids.add(p["id"])
        check_camera(p)
    return cfg


def layout(original, settings, width):
    lon, lat = angles(width, 0, width // 2)
    x, y, _, inside = original_map(lon, lat, original.shape, settings)
    rgb = sample(original, x, y)
    rgb[~inside] = 139
    return rgb, inside.astype(np.uint8) * 255


def init(args):
    width = width_2to1(args.guide_width)
    source = args.source.resolve()
    original = read_rgb(source)
    work = args.work
    work.mkdir(parents=True, exist_ok=True)
    if any(work.iterdir()):
        raise ValueError("Choose an empty work directory for init. Resume existing work with guides or assemble.")
    panels = []
    for name, yaw, pitch in (("front",0,0), ("right",90,0), ("back",180,0), ("left",-90,0),
                             ("up",0,90), ("down",0,-90)):
        panels.append(dict(id=name, yaw=yaw, pitch=pitch, hfov=106, width=1536, height=1536))
    filename = "original" + source.suffix.lower()
    core = dict(file=filename, projection=args.projection, hfov=args.hfov, horizon=args.horizon)
    if not 1 < args.hfov < (175 if args.projection == "perspective" else 360) or not np.isfinite(args.horizon):
        raise ValueError("Check source projection, HFOV and horizon before init.")
    guide, _ = layout(original, core, width)
    shutil.copyfile(source, work / filename)
    save_png(work / "layout.png", guide)
    write_json(work / "scene.json", dict(original=core, panels=panels))
    print(f"Use {work/'layout.png'} and the original to paint {work/'base.png'} at 2:1.")


def build_scaffold(base, original, core):
    ih, iw = base.shape[:2]
    w = min(1600, iw)
    ref, mask = layout(original, core, w)
    moving = cv.resize(base, (w, w // 2), interpolation=cv.INTER_AREA)
    feature_mask = cv.erode(mask, np.ones((5,5), np.uint8))
    matrix, message = fit(grey(ref), grey(moving), feature_mask)
    print(f"Base registration: {message}", flush=True)
    # Taper the estimated shift beyond the original footprint so the back seam stays periodic.
    distance = cv.distanceTransform((mask == 0).astype(np.uint8), cv.DIST_L2, 5)
    influence = cv.resize((1 - ease(distance / (0.14 * w))).astype(np.float32), (iw, ih))
    aligned = np.empty_like(base)
    scale = iw / w
    for top in range(0, ih, 96):
        bottom = min(top + 96, ih)
        xx = np.arange(iw, dtype=np.float32)[None,:]
        yy = np.arange(top, bottom, dtype=np.float32)[:,None]
        u, v = (xx + 0.5) / scale - 0.5, (yy + 0.5) / scale - 0.5
        dx = (matrix[0,0] - 1) * u + matrix[0,1] * v + matrix[0,2]
        dy = matrix[1,0] * u + (matrix[1,1] - 1) * v + matrix[1,2]
        weight = influence[top:bottom] * scale
        strip = sample(base, xx + dx * weight, yy + dy * weight, wrap=True)
        lon, lat = angles(iw, top, bottom)
        x, y, alpha, _ = original_map(lon, lat, original.shape, core)
        blend(strip, original, x, y, alpha)
        aligned[top:bottom] = strip
    return aligned


def inputs(work, cfg):
    path = work / cfg["original"]["file"]
    return {"original": cfg["original"], "original_sha256": digest(path),
            "base_sha256": digest(work / "base.png")}


def guides(args):
    work = args.work
    cfg = scene_at(work)
    state_path = work / "guide-state.json"
    state = {"inputs": inputs(work, cfg), "panels": {p["id"]: p for p in cfg["panels"]}}
    previous = json.loads(state_path.read_text()) if state_path.exists() else {}
    for pid, p in state["panels"].items():
        changed = previous.get("inputs") != state["inputs"] or previous.get("panels", {}).get(pid) != p
        if changed and (work / "panels" / pid / "paint.png").exists():
            raise ValueError(f"Guide for {pid} changed. Give the revised panel a fresh ID, "
                             "or move its old paint.png aside before rebuilding its guide.")
    base = read_atlas(work / "base.png")
    original = read_rgb(work / cfg["original"]["file"])
    assembled = build_scaffold(base, original, cfg["original"])
    save_png(work / "scaffold.png", assembled)
    for p in cfg["panels"]:
        folder = work / "panels" / p["id"]
        folder.mkdir(parents=True, exist_ok=True)
        save_png(folder / "guide.png", view(assembled, p["width"], p["height"], p["yaw"], p["pitch"], p["hfov"]))
    write_json(state_path, state)
    print(f"Prepared {len(cfg['panels'])} perspective guides in {work/'panels'}.")


def coverage(original, cfg, paintings, path):
    w = 1024
    lon, lat = angles(w, 0, w // 2)
    density = np.zeros((w // 2, w), np.float32)
    for p, art in paintings:
        _, _, a = panel_map(lon, lat, p, art.shape)
        density = density * (1 - a) + a * (art.shape[1] / p["hfov"])
    _, _, core, _ = original_map(lon, lat, original.shape, cfg["original"])
    rgb = np.zeros((w // 2, w, 3), np.uint8)
    rgb[:] = (175,65,60)
    rgb[density > 1] = (240,179,67)
    rgb[density >= 0.8 * 8192 / 360] = (51,146,201)
    rgb[core >= 0.95] = (62,165,113)
    save_png(path, rgb)


def assemble(args):
    work, width = args.work, width_2to1(args.width)
    cfg = scene_at(work)
    state = json.loads((work / "guide-state.json").read_text())
    if state["inputs"] != inputs(work, cfg) or state["panels"] != {p["id"]: p for p in cfg["panels"]}:
        raise ValueError("The source, base, or panel cameras changed. Run guides for the updated scene.")
    missing = [p["id"] for p in cfg["panels"] if not (work/"panels"/p["id"]/"paint.png").is_file()]
    if missing:
        raise ValueError("Paint the following guides before assembly: " + ", ".join(missing))
    scaffold = read_atlas(work / "scaffold.png")
    original = read_rgb(work / cfg["original"]["file"])
    paintings = []
    for p in cfg["panels"]:
        folder = work / "panels" / p["id"]
        registered, msg = register_panel(read_rgb(folder / "guide.png"), read_rgb(folder / "paint.png"))
        print(f"{p['id']}: {msg}", flush=True)
        paintings.append((p, registered))
    height = width // 2
    result = np.empty((height, width, 3), np.uint8)
    sh, sw = scaffold.shape[:2]
    for top in range(0, height, 96):
        bottom = min(top + 96, height)
        lon, lat = angles(width, top, bottom)
        xx = (np.arange(width, dtype=np.float32)[None,:] + 0.5) * sw / width - 0.5
        yy = (np.arange(top, bottom, dtype=np.float32)[:,None] + 0.5) * sh / height - 0.5
        strip = sample(scaffold, xx, yy, wrap=True)
        for p, art in paintings:
            blend(strip, art, *panel_map(lon, lat, p, art.shape))
        x, y, alpha, _ = original_map(lon, lat, original.shape, cfg["original"])
        blend(strip, original, x, y, alpha)
        result[top:bottom] = strip
    save_png(args.out or work / "master.png", result)
    coverage(original, cfg, paintings, work / "coverage.png")
    print(f"Rendered {width}×{height}; inspect {work/'coverage.png'} and matching perspective views.")


def extract(args):
    check_camera(vars(args))
    rgb = view(read_atlas(args.atlas), args.width, args.height, args.yaw, args.pitch, args.hfov)
    Image.fromarray(rgb).save(args.out)


def main():
    cv.setRNGSeed(42)
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("init", help="project one original into a grey 2:1 layout")
    p.add_argument("source", type=Path)
    p.add_argument("work", type=Path)
    p.add_argument("--projection", choices=["perspective","cylindrical"], default="perspective")
    p.add_argument("--hfov", type=float, required=True, help="horizontal angular span of the source in degrees")
    p.add_argument("--horizon", type=float, default=0.5, help="distance from top / image height")
    p.add_argument("--guide-width", type=int, default=2048)
    p = sub.add_parser("guides", help="align the base and export planned perspective guides")
    p.add_argument("work", type=Path)
    p = sub.add_parser("assemble", help="register native painted panels and lock the original over them")
    p.add_argument("work", type=Path)
    p.add_argument("--width", type=int, default=8192)
    p.add_argument("--out", type=Path)
    p = sub.add_parser("view", help="extract a matched camera view for inspection")
    p.add_argument("atlas", type=Path)
    p.add_argument("out", type=Path)
    for key, value in (("yaw",0.0),("pitch",0.0),("hfov",80.0),("width",1500),("height",1000)):
        p.add_argument("--" + key, type=type(value), default=value)
    args = parser.parse_args()
    try:
        {"init":init, "guides":guides, "assemble":assemble, "view":extract}[args.command](args)
    except (OSError, ValueError, KeyError, cv.error) as error:
        parser.exit(1, f"panorama: {error}\n")


if __name__ == "__main__":
    main()
