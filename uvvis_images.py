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
import re
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
    """Begrenzungsrechteck des sichtbaren Inhalts (weiße Hintergrundflächen ignoriert).
    Wichtig: exakt senkrechte/waagerechte Linien haben ein Rechteck der Breite bzw. Höhe 0, das
    PyMuPDF als „leer“ behandelt und bei „|=“ verwirft – deshalb über Koordinaten vereinigen."""
    import pymupdf
    xs, ys = [], []

    def add(rect, lw=0.0):
        xs.extend([rect.x0 - lw, rect.x1 + lw])
        ys.extend([rect.y0 - lw, rect.y1 + lw])

    for dr in page.get_drawings():
        fill, stroke = dr.get("fill"), dr.get("color")
        white = fill is not None and min(fill) > 0.97 and stroke is None
        if white and dr["rect"].get_area() > 0.5 * page.rect.get_area():
            continue
        add(dr["rect"], (dr.get("width") or 0) / 2)
    for b in page.get_text("dict")["blocks"]:
        add(pymupdf.Rect(b["bbox"]))
    for img in page.get_image_info():
        add(pymupdf.Rect(img["bbox"]))
    if not xs:
        return page.rect
    pad = 1.5
    r = pymupdf.Rect(min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad)
    return r & page.rect


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


_BLACK = re.compile(r"(#000000|#000(?![0-9a-fA-F])|\bblack\b|rgb\(\s*0\s*,\s*0\s*,\s*0\s*\)|"
                    r"rgb\(\s*0%\s*,\s*0%\s*,\s*0%\s*\))", re.I)


def recolor_svg(svg_text, color):
    """Schwarze Striche/Flächen/Schrift einer SVG in die gewünschte Farbe umfärben."""
    return _BLACK.sub(color, svg_text)


def tint_rgba(arr, color):
    """Rastergrafik einfärben: Form (Alpha) bleibt, Farbe wird ersetzt (für schwarze Strukturen)."""
    c = color.lstrip("#")
    rgb = np.array([int(c[i:i + 2], 16) for i in (0, 2, 4)], np.uint8)
    out = arr.copy()
    out[..., :3] = rgb
    return out


def _render_doc(doc, target_px, info):
    page = doc[0]
    clip = _content_rect(page)
    dpi = max(150, min(2400, int(target_px / max(clip.width, 1) * 72)))  # feste Pixelbreite
    pix = page.get_pixmap(clip=clip, dpi=dpi, alpha=True)
    rgba = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, pix.n).copy()
    if pix.n == 3:
        rgba = np.dstack([rgba, np.full(rgba.shape[:2], 255, np.uint8)])
    else:                                              # MuPDF liefert vormultipliertes Alpha
        a = rgba[..., 3:4].astype(np.float32)
        rgb = rgba[..., :3].astype(np.float32)
        rgba[..., :3] = np.where(a > 0, np.clip(rgb * 255.0 / np.maximum(a, 1), 0, 255), 0).astype(np.uint8)
    rgba = white_to_alpha(rgba, 250) if rgba[..., 3].min() == 255 else rgba
    return {"rgba": rgba, "pdf": doc.tobytes(), "clip": tuple(clip), **info}


def load_structure(path, target_px=2400, color=None):
    """-> dict(rgba=Vorschau, pdf=bytes|None, clip, mw, formula, warnings).
    color (z. B. '#e8231b'): Struktur einfärben – SVG/CDXML als Vektor, PDF/Raster als Bild."""
    path = Path(path)
    ext = path.suffix.lower()
    info = {"mw": None, "formula": None, "warnings": []}
    if ext in CHEM_EXT:
        import uvvis_chem
        chem = uvvis_chem.load_cdxml(path)
        svg = chem.pop("svg")
        info.update(chem)
        original = find_sibling_drawing(path)
        if original is not None:
            # Grafik unverändert aus der ChemDraw-Exportdatei, Molmasse aus der CDXML
            res = load_structure(original, target_px, color)
            res.update({k: info[k] for k in ("mw", "formula", "warnings")})
            res["n_fragments"] = info.get("n_fragments")
            res["drawing_from"] = original.name
            return res
        info["warnings"] = info["warnings"] + [T("cdxml_redrawn", name=path.stem)]
        if color:
            svg = recolor_svg(svg, color)
        return _render_doc(_vector_doc(path, svg), target_px, info)
    if ext == ".svg":
        svg = Path(path).read_text(encoding="utf-8", errors="replace")
        if color:
            svg = recolor_svg(svg, color)
        return _render_doc(_vector_doc(path, svg), target_px, info)
    if ext in VECTOR_EXT:                              # PDF: Vektor nur ungefärbt
        res = _render_doc(_vector_doc(path, None), target_px, info)
        if color:
            res.update(rgba=tint_rgba(res["rgba"], color), pdf=None, clip=None)
        return res
    if ext == ".cdx":
        raise RuntimeError(T("cdx_binary"))
    arr = open_any_image(path)
    arr = trim_alpha(white_to_alpha(trim_uniform(arr)))
    if color:
        arr = tint_rgba(arr, color)
    return {"rgba": arr, "pdf": None, "clip": None, **info}


SIBLING_DRAWING_EXT = (".svg", ".pdf", ".png", ".tif", ".tiff")


def find_sibling_drawing(cdxml_path):
    """Gleichnamige ChemDraw-Exportdatei neben der CDXML (SVG/PDF bevorzugt, sonst PNG/TIFF)."""
    p = Path(cdxml_path)
    candidates = {c.suffix.lower(): c for c in p.parent.glob(p.stem + ".*") if c.stem == p.stem}
    for ext in SIBLING_DRAWING_EXT:
        if ext in candidates:
            return candidates[ext]
    return None


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


def overlay_vectors_svg(svg_path, items):
    """Strukturen (PDF-Seite) als Vektor-Gruppe in eine matplotlib-SVG einsetzen.
    items: [(rect_pt (x0, y_top, x1, y_bottom), pdf_bytes, clip)]. matplotlib-SVG nutzt pt."""
    import re
    import pymupdf
    svg = Path(svg_path).read_text(encoding="utf-8")
    groups = []
    for k, (rect, pdf_bytes, clip) in enumerate(items):
        src = pymupdf.open("pdf", pdf_bytes)
        page = src[0]
        page.set_cropbox(pymupdf.Rect(*clip))
        sub = page.get_svg_image(text_as_path=True)
        m = re.search(r"<svg[^>]*>(.*)</svg>", sub, re.S)
        vb = re.search(r'viewBox="([-\d.]+) ([-\d.]+) ([\d.]+) ([\d.]+)"', sub)
        if not m or not vb:
            continue
        inner = m.group(1)
        pre = f"uvs{k}_"                                   # IDs eindeutig machen
        inner = re.sub(r'id="([^"]+)"', lambda mm: f'id="{pre}{mm.group(1)}"', inner)
        inner = re.sub(r"url\(#([^)]+)\)", lambda mm: f"url(#{pre}{mm.group(1)})", inner)
        inner = re.sub(r'href="#([^"]+)"', lambda mm: f'href="#{pre}{mm.group(1)}"', inner)
        vx, vy, vw, vh = map(float, vb.groups())
        x0, y0, x1, y1 = rect
        sc = min((x1 - x0) / vw, (y1 - y0) / vh)
        ox = x0 + ((x1 - x0) - vw * sc) / 2 - vx * sc
        oy = y0 + ((y1 - y0) - vh * sc) / 2 - vy * sc
        groups.append(f'<g id="structure_{k}" transform="translate({ox:.3f} {oy:.3f}) '
                      f'scale({sc:.5f})">{inner}</g>')
    if groups:
        i = svg.rfind("</svg>")
        svg = svg[:i] + "\n".join(groups) + "\n" + svg[i:]
        if "xmlns:xlink" not in svg[:500]:
            svg = svg.replace("<svg ", '<svg xmlns:xlink="http://www.w3.org/1999/xlink" ', 1)
        Path(svg_path).write_text(svg, encoding="utf-8")


def svg_defs_first(svg_path):
    """matplotlib schreibt die Clip-Pfade ans Dateiende. Einige Programme (MuPDF, evtl. Word)
    werten Vorwärtsverweise nicht aus -> Kurven ragen über die Achse. Block nach vorn ziehen."""
    import re
    svg = Path(svg_path).read_text(encoding="utf-8")
    m = None
    for m in re.finditer(r"\n <defs>\s*<clipPath.*?</defs>", svg, re.S):
        pass
    if not m:
        return
    block = m.group(0)
    svg = svg[:m.start()] + svg[m.end():]
    head = re.search(r"<svg[^>]*>", svg)
    svg = svg[:head.end()] + block + svg[head.end():]
    Path(svg_path).write_text(svg, encoding="utf-8")
