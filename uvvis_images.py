"""
uvvis_images.py - Bilder für uvvis_plot.py laden.

Küvettenfoto:  jedes Pillow-Format + HEIC/HEIF/AVIF (pillow-heif), EXIF-Drehung,
               Hintergrund entfernen (rembg -> GrabCut -> Randfarbe), zuschneiden.
Struktur:      SVG / PDF (bleibt im PDF-Export Vektor), CDXML (über RDKit neu gezeichnet),
               oder Rastergrafik (weißer Hintergrund -> transparent).

Pakete: pillow-heif (HEIC), onnxruntime (KI-Freistellung, ISNet-Modell wird beim ersten
        Mal geladen), opencv-python-headless (GrabCut), pymupdf (SVG/PDF), rdkit (CDXML)
"""
from __future__ import annotations

import hashlib
import os
import sys
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

from uvvis_i18n import T

LOG = print


def log(msg=""):
    LOG(msg)

RASTER_EXT = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".gif", ".webp",
              ".heic", ".heif", ".avif", ".hif"}
VECTOR_EXT = {".svg", ".pdf"}
CHEM_EXT = {".cdxml"}


# ----------------------------------------------------------------------------
# Rasterbilder
# ----------------------------------------------------------------------------
def _register_heif():
    try:
        import pillow_heif
        pillow_heif.register_heif_opener()
        if hasattr(pillow_heif, "register_avif_opener"):
            try:
                pillow_heif.register_avif_opener()
            except Exception:
                pass
        return True
    except ImportError:
        return False


def open_any_image(path) -> np.ndarray:
    """Beliebiges Rasterbild -> RGBA-Array, EXIF-Orientierung angewendet (iPhone!)."""
    path = Path(path)
    has_heif = _register_heif()
    try:
        im = Image.open(path)
    except Exception as e:
        if path.suffix.lower() in {".heic", ".heif", ".hif", ".avif"} and not has_heif:
            raise RuntimeError(T("need_heif", name=path.name)) from e
        raise RuntimeError(T("bad_image", name=path.name, e=e)) from e
    im = ImageOps.exif_transpose(im)
    return np.asarray(im.convert("RGBA")).copy()


def trim_alpha(arr, pad=4, thr=10):
    ys, xs = np.nonzero(arr[..., 3] > thr)
    if not len(xs):
        return arr
    return arr[max(0, ys.min() - pad):ys.max() + pad + 1, max(0, xs.min() - pad):xs.max() + pad + 1]


def white_to_alpha(arr, thr=245):
    arr = arr.copy()
    arr[(arr[..., :3] >= thr).all(-1), 3] = 0
    return arr


def trim_uniform(arr):
    """Rand in Farbe der linken oberen Ecke abschneiden (z. B. weißer ChemDraw-Hintergrund)."""
    bg = arr[0, 0].astype(int)
    if bg[3] <= 10:
        return trim_alpha(arr)
    mask = (np.abs(arr[..., :3].astype(int) - bg[:3]).max(-1) > 12) & (arr[..., 3] > 10)
    ys, xs = np.nonzero(mask)
    if not len(xs):
        return arr
    p = 4
    return arr[max(0, ys.min() - p):ys.max() + p + 1, max(0, xs.min() - p):xs.max() + p + 1]


# ----------------------------------------------------------------------------
# Hintergrund entfernen (Küvettenfoto)
# ----------------------------------------------------------------------------
def _downscale(arr, max_px=1600):
    h, w = arr.shape[:2]
    f = max_px / max(h, w)
    if f >= 1:
        return arr
    im = Image.fromarray(arr).resize((int(w * f), int(h * f)), Image.LANCZOS)
    return np.asarray(im).copy()


MODEL_URL = "https://github.com/danielgatis/rembg/releases/download/v0.0.0/isnet-general-use.onnx"
MODEL_NAME = "isnet-general-use.onnx"
MODEL_SIZE_MB = 179


def app_data_dir() -> Path:
    if sys.platform.startswith("win"):
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    d = base / "UVVisTool"
    d.mkdir(parents=True, exist_ok=True)
    return d


def model_path(existing_only=False):
    for p in (app_data_dir() / "models" / MODEL_NAME,
              Path.home() / ".u2net" / MODEL_NAME,                       # rembg-Cache
              Path.home() / ".rembg" / "models" / "isnet-general-use" / MODEL_NAME):
        if p.exists() and p.stat().st_size > 1e6:
            return p
    return None if existing_only else app_data_dir() / "models" / MODEL_NAME


def download_model(progress=None):
    """Lädt das ISNet-Modell (~180 MB). progress(bytes_done, bytes_total) -> False bricht ab."""
    dst = model_path()
    if dst.exists() and dst.stat().st_size > 1e6:
        return dst
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(".part")
    with urllib.request.urlopen(MODEL_URL, timeout=60) as r, open(tmp, "wb") as f:
        total = int(r.headers.get("Content-Length") or MODEL_SIZE_MB * 2 ** 20)
        done = 0
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
            done += len(chunk)
            if progress and progress(done, total) is False:
                f.close()
                tmp.unlink(missing_ok=True)
                raise RuntimeError(T("download_cancelled"))
    tmp.replace(dst)
    return dst


_SESSION = None


def _bg_isnet(arr):
    """ISNet (wie rembg 'isnet-general-use'), direkt über onnxruntime."""
    global _SESSION
    import onnxruntime as ort
    mp = model_path(existing_only=True)
    if mp is None:
        raise RuntimeError(T("model_missing"))
    if _SESSION is None:
        _SESSION = ort.InferenceSession(str(mp), providers=["CPUExecutionProvider"])
    img = Image.fromarray(arr[..., :3])
    x = np.asarray(img.resize((1024, 1024), Image.LANCZOS)).astype(np.float32)
    x = x / max(float(x.max()), 1e-6) - 0.5
    x = x.transpose(2, 0, 1)[None]
    out = _SESSION.run(None, {_SESSION.get_inputs()[0].name: x})[0][0, 0]
    p = (out - out.min()) / max(float(out.max() - out.min()), 1e-6)
    mask = np.asarray(Image.fromarray((p * 255).astype(np.uint8)).resize(img.size, Image.LANCZOS))
    res = arr.copy()
    res[..., 3] = mask
    return res


def _bg_grabcut(arr, work_px=500):
    import cv2
    rgb = arr[..., :3]
    h, w = rgb.shape[:2]
    f = min(1.0, work_px / max(h, w))                 # GrabCut ist langsam -> verkleinert rechnen
    small = cv2.resize(rgb, (max(1, int(w * f)), max(1, int(h * f))), interpolation=cv2.INTER_AREA)
    sh, sw = small.shape[:2]
    mask = np.zeros((sh, sw), np.uint8)
    rect = (int(0.04 * sw), int(0.02 * sh), int(0.92 * sw), int(0.96 * sh))
    bgd, fgd = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
    cv2.grabCut(cv2.cvtColor(small, cv2.COLOR_RGB2BGR), mask, rect, bgd, fgd, 6, cv2.GC_INIT_WITH_RECT)
    fg = np.isin(mask, (cv2.GC_FGD, cv2.GC_PR_FGD)).astype(np.uint8)
    fg = cv2.resize(fg, (w, h), interpolation=cv2.INTER_NEAREST)
    out = arr.copy()
    out[..., 3] = fg * 255
    return out


def _bg_border(arr, tol=28):
    """Hintergrundfarbe vom Bildrand schätzen, zusammenhängend vom Rand aus entfernen."""
    import cv2
    rgb = np.ascontiguousarray(arr[..., :3])
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB).astype(np.float32)
    border = np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]])
    bg = np.median(border, 0)
    close = (np.linalg.norm(lab - bg, axis=-1) < tol).astype(np.uint8)
    n, lbl = cv2.connectedComponents(close)
    edge = set(np.unique(np.concatenate([lbl[0], lbl[-1], lbl[:, 0], lbl[:, -1]]))) - {0}
    bgmask = np.isin(lbl, list(edge)) & (close > 0)
    out = arr.copy()
    out[..., 3] = np.where(bgmask, 0, 255).astype(np.uint8)
    return out


def _clean_alpha(arr):
    """Größtes Objekt behalten, Löcher füllen (Glas!), Kante leicht weichzeichnen."""
    try:
        import cv2
    except ImportError:
        return arr
    a = (arr[..., 3] > 127).astype(np.uint8)
    n, lbl, stats, _ = cv2.connectedComponentsWithStats(a)
    if n > 1:
        k = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        a = (lbl == k).astype(np.uint8)
    # Löcher füllen: Hintergrund, der nicht mit dem Rand verbunden ist, gehört zum Objekt
    inv = (1 - a).astype(np.uint8)
    n, lbl = cv2.connectedComponents(inv)
    edge = set(np.unique(np.concatenate([lbl[0], lbl[-1], lbl[:, 0], lbl[:, -1]])))
    holes = (inv > 0) & ~np.isin(lbl, list(edge))
    a[holes] = 1
    soft = cv2.GaussianBlur(a.astype(np.float32), (0, 0), 1.0)   # weiche Kante
    out = arr.copy()
    out[..., 3] = (np.clip(np.where(a > 0, np.maximum(soft, 0.5), soft), 0, 1) * 255).astype(np.uint8)
    out[..., 3][a > 0] = np.maximum(out[..., 3][a > 0], (soft[a > 0] * 255).astype(np.uint8))
    return out


BG_METHODS = ["isnet", "grabcut", "border"]


def available_bg_methods(include_undownloaded=False):
    ok = []
    try:
        import onnxruntime  # noqa: F401
        if include_undownloaded or model_path(existing_only=True):
            ok.append("isnet")
    except ImportError:
        pass
    try:
        import cv2  # noqa: F401
        ok += ["grabcut", "border"]
    except ImportError:
        pass
    return ok


def remove_background(arr, method="auto", cache_dir=None, src_path=None):
    """Gibt (RGBA, verwendete Methode) zurück. Ergebnis wird gecacht (ISNet braucht Sekunden)."""
    arr = _downscale(arr)
    avail = available_bg_methods()
    order = [m for m in BG_METHODS if m in avail] if method == "auto" else [method]
    if not order:
        log("  " + T("bg_none"))
        return arr, "none"
    key = None
    if cache_dir and src_path:
        h = hashlib.sha1(Path(src_path).read_bytes()).hexdigest()[:16]
        key = Path(cache_dir) / f"{h}_{order[0]}.png"
        if key.exists():
            return np.asarray(Image.open(key).convert("RGBA")).copy(), order[0]
    last = None
    for m in order:
        try:
            fn = {"isnet": _bg_isnet, "grabcut": _bg_grabcut, "border": _bg_border}[m]
            out = _clean_alpha(fn(arr))
            frac = (out[..., 3] > 127).mean()
            if not 0.02 < frac < 0.95:      # nichts oder alles freigestellt -> nächste Methode
                log("  " + T("bg_implausible", m=m, f=frac))
                continue
            out = trim_alpha(out)
            if key:
                key.parent.mkdir(parents=True, exist_ok=True)
                Image.fromarray(out).save(key)
            return out, m
        except Exception as e:      # Modell-Download fehlgeschlagen etc.
            last = e
            log("  " + T("bg_failed", m=m, e=e))
    log("  " + T("bg_giveup", e=last))
    return arr, "none"


# ----------------------------------------------------------------------------
# Strukturen: SVG/PDF als Vektor, CDXML über RDKit
# ----------------------------------------------------------------------------
def _content_rect(page):
    """Begrenzungsrechteck des sichtbaren Inhalts (weiße Hintergrundflächen ignoriert)."""
    import pymupdf
    r = pymupdf.Rect()
    for dr in page.get_drawings():
        fill, stroke = dr.get("fill"), dr.get("color")
        white = fill is not None and min(fill) > 0.97 and stroke is None
        if white and dr["rect"].get_area() > 0.5 * page.rect.get_area():
            continue
        r |= dr["rect"]
    for b in page.get_text("dict")["blocks"]:
        r |= pymupdf.Rect(b["bbox"])
    for img in page.get_image_info():
        r |= pymupdf.Rect(img["bbox"])
    if r.is_empty:
        return page.rect
    pad = 2
    return (r + (-pad, -pad, pad, pad)) & page.rect


def _vector_doc(path, svg_text=None):
    try:
        import pymupdf
    except ImportError as e:
        raise RuntimeError(T("need_pymupdf")) from e
    if svg_text is not None:
        src = pymupdf.open(stream=svg_text.encode("utf-8"), filetype="svg")
    else:
        src = pymupdf.open(str(path))
    if src.is_pdf:
        return pymupdf.open("pdf", src.tobytes())
    return pymupdf.open("pdf", src.convert_to_pdf())


def load_structure(path, target_px=2400):
    """-> dict(rgba=Vorschau, pdf=bytes|None, clip, mw, formula, warnings)."""
    path = Path(path)
    ext = path.suffix.lower()
    info = {"mw": None, "formula": None, "warnings": []}
    if ext in CHEM_EXT or ext in VECTOR_EXT:
        svg = None
        if ext in CHEM_EXT:
            import uvvis_chem
            chem = uvvis_chem.load_cdxml(path)
            svg = chem.pop("svg")
            info.update(chem)
        doc = _vector_doc(path, svg)
        page = doc[0]
        clip = _content_rect(page)
        dpi = max(150, min(2400, int(target_px / max(clip.width, 1) * 72)))  # feste Pixelbreite
        pix = page.get_pixmap(clip=clip, dpi=dpi, alpha=True)
        rgba = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, pix.n).copy()
        if pix.n == 3:
            rgba = np.dstack([rgba, np.full(rgba.shape[:2], 255, np.uint8)])
        rgba = white_to_alpha(rgba, 250) if rgba[..., 3].min() == 255 else rgba
        return {"rgba": rgba, "pdf": doc.tobytes(), "clip": tuple(clip), **info}
    if ext == ".cdx":
        raise RuntimeError(T("cdx_binary"))
    arr = open_any_image(path)
    return {"rgba": trim_alpha(white_to_alpha(trim_uniform(arr))), "pdf": None, "clip": None, **info}


def load_photo(path, remove_bg="auto", cache_dir=None):
    arr = open_any_image(path)
    if remove_bg in (False, None, "none", "false"):
        return {"rgba": trim_uniform(arr), "pdf": None, "clip": None, "bg_method": "none"}
    out, m = remove_background(arr, remove_bg, cache_dir, path)
    return {"rgba": out, "pdf": None, "clip": None, "bg_method": m}


def overlay_vectors(pdf_path, items):
    """items: [(rect_in_pt (x0, y_top, x1, y_bottom), pdf_bytes, clip)] -> in PDF einsetzen."""
    import pymupdf
    doc = pymupdf.open(str(pdf_path))
    page = doc[0]
    for rect, pdf_bytes, clip in items:
        src = pymupdf.open("pdf", pdf_bytes)
        page.show_pdf_page(pymupdf.Rect(*rect), src, 0, clip=pymupdf.Rect(*clip),
                           keep_proportion=True, overlay=True)
    data = doc.tobytes(garbage=3, deflate=True)
    doc.close()
    Path(pdf_path).write_bytes(data)
