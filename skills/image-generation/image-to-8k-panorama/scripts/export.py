#!/usr/bin/env python3
"""Export an equirectangular master as a GPano JPEG and, optionally, a mobile web viewer."""
import argparse
import html
import json
import math
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory

import cv2 as cv
from PIL import Image

from sphere import read_atlas, view

FACES = (("f",0,0), ("r",90,0), ("b",180,0), ("l",-90,0), ("u",0,90), ("d",0,-90))
TILE = 512


def gpano(width, height):
    attrs = {"ProjectionType":"equirectangular", "UsePanoramaViewer":"True",
             "FullPanoWidthPixels":width, "FullPanoHeightPixels":height,
             "CroppedAreaImageWidthPixels":width, "CroppedAreaImageHeightPixels":height,
             "CroppedAreaLeftPixels":0, "CroppedAreaTopPixels":0}
    fields = " ".join(f'GPano:{key}="{value}"' for key,value in attrs.items())
    return (f'<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
            f'<rdf:Description rdf:about="" xmlns:GPano="http://ns.google.com/photos/1.0/panorama/" {fields}/>'
            f'</rdf:RDF></x:xmpmeta>').encode()


def tiles(atlas, root):
    # Choose the first power-of-two face at or above the atlas's equatorial centre density.
    levels = max(1, 1 + math.ceil(math.log2(atlas.shape[1] / (math.pi * TILE))))
    size = TILE * (2 ** (levels - 1))
    for level in list(range(1, levels + 1)) + ["fallback"]:
        (root / str(level)).mkdir(parents=True)
    count = 0
    for face, yaw, pitch in FACES:
        full = Image.fromarray(view(atlas, size, size, yaw, pitch, 90))
        small = min(1280, size)
        full.resize((small,small), Image.Resampling.LANCZOS).save(root/"fallback"/f"{face}.jpg", quality=88)
        count += 1
        for level in range(1, levels + 1):
            n = 2 ** (level - 1)
            image = full if level == levels else full.resize((n*TILE, n*TILE), Image.Resampling.LANCZOS)
            for row in range(n):
                for col in range(n):
                    box = (col*TILE, row*TILE, (col+1)*TILE, (row+1)*TILE)
                    image.crop(box).save(root/str(level)/f"{face}{row}_{col}.jpg", quality=90, subsampling=0)
                    count += 1
    return dict(basePath="./tiles", path="/%l/%s%y_%x", fallbackPath="/fallback/%s",
                extension="jpg", tileResolution=TILE, cubeResolution=size, maxLevel=levels), count


def export(args):
    atlas = read_atlas(args.atlas)
    h, w = atlas.shape[:2]
    dest = args.dest.resolve()
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and (not dest.is_dir() or any(dest.iterdir())):
        raise ValueError("Choose a new or empty export directory for this release.")
    with TemporaryDirectory(prefix=".pano-", dir=dest.parent) as tmp:
        bundle = Path(tmp) / "bundle"
        bundle.mkdir()
        xml = gpano(w, h)
        jpg = bundle / "panorama.jpg"
        Image.fromarray(atlas).save(jpg, quality=93, subsampling=0, progressive=True, xmp=xml)
        with Image.open(jpg) as saved:
            if saved.size != (w, h) or saved.info.get("xmp") != xml:
                raise ValueError("JPEG exporter did not retain the full GPano XMP. Check your Pillow version.")
        if args.web:
            template = Path(__file__).resolve().parents[1] / "assets" / "viewer"
            shutil.copytree(template / "vendor", bundle / "vendor")
            config, count = tiles(atlas, bundle / "tiles")
            page = (template / "index.html").read_text(encoding="utf-8")
            page = page.replace("{{MULTIRES}}", json.dumps(config)).replace("{{TITLE}}", html.escape(args.title))
            (bundle / "index.html").write_text(page, encoding="utf-8")
            print(f"{config['maxLevel']} levels, {config['cubeResolution']} px faces, {count} JPEG tiles incl. fallbacks.")
        bundle.replace(dest)
    print(f"{w}×{h} GPano JPEG: {dest/'panorama.jpg'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("atlas", type=Path)
    parser.add_argument("dest", type=Path, help="new or empty export directory")
    parser.add_argument("--web", action="store_true", help="also build a self-hosted touch viewer and tiles")
    parser.add_argument("--title", default="360° 全景")
    try:
        export(parser.parse_args())
    except (ValueError, OSError, cv.error) as error:
        parser.exit(1, f"export: {error}\n")
