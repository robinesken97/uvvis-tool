#!/usr/bin/env python3
"""
uvvis_core.py - Kern der UV-Vis-Auswertung (Lambert-Beer an Verdünnungsreihen).

Wird von der GUI (uvvis_gui.py) genutzt, läuft aber auch allein:
  python uvvis_core.py config.yaml            # rendern + auswerten
  python uvvis_core.py messung.csv            # Cary-CSV mit Standardeinstellungen
  python uvvis_core.py config.yaml -i         # Layout mit der Maus anpassen ('w' = speichern)
  python uvvis_core.py --demo ORDNER          # Beispieldaten erzeugen
"""
from __future__ import annotations

import argparse
import copy
import csv
import math
import os
import re
import sys
from pathlib import Path

import matplotlib
import numpy as np
import yaml
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import uvvis_images as IMG  # noqa: E402
from uvvis_i18n import T  # noqa: E402

LOG = print          # GUI ersetzt das durch ihr Protokollfenster


def log(msg=""):
    LOG(msg)

# ----------------------------------------------------------------------------
# Defaults
# ----------------------------------------------------------------------------
DEFAULTS = {
    "output": "uvvis.pdf",
    "extra_formats": ["png"],
    "dpi": 600,
    "figsize_in": [8.0, 6.0],
    "size_cm": None,                         # z. B. [16, 10.5]: exakte Exportgröße, Schrift skaliert
    "scale": 1.0,                            # wird aus size_cm berechnet
    "axes_rect": [0.12, 0.13, 0.85, 0.84],   # Position der Hauptachse in Figurkoordinaten
    "font": ["Arial", "Helvetica", "Liberation Sans", "DejaVu Sans"],
    "font_size": 16,
    "path_length_cm": 1.0,
    "conc_unit": "mM",                       # mM | uM | M | mg/mL
    "molar_mass_g_mol": None,                # nötig für ε bei mg/mL
    "cary_file": None,                       # Cary-Mehrprobenexport: Proben/Konz. aus Kopfzeile
    "groups": {},                            # Overrides je Probenserie (Präfix vor der Konz.)
    "select": None,                          # nur diese Serien rendern
    "baseline_nm": "auto",                   # auto | [a, b] | null
    "baseline_mode": "series",               # series: konz.-proportionalen Anteil behalten | simple
    "baseline_width_nm": 20,
    "baseline_search_nm": [300, None],       # wo das Basislinienfenster gesucht wird
    "avg_window_nm": 0.0,                    # A(λ) als Mittel über ±Fenster statt Interpolation
    "snap_window_nm": 0.0,                   # λ auf lokales Maximum ±Fenster schieben
    "max_abs_fit": 1.0,                      # Punkte mit A > Wert nicht fitten (Linearitäts-Cutoff)
    "fit_intercept": True,
    "min_fit_points": 3,                     # weniger Punkte -> kein ε
    "min_r2": 0.98,                          # schlechtere Fits: in CSV, aber nicht im Bild
    "wavelengths_nm": "auto",                # Liste oder auto (Peaksuche)
    "peak_range_nm": [230, None],            # Bereich der automatischen Peaksuche
    "peak_min_prominence": 0.05,             # relativ zur Peakhöhe
    "xlim": None,
    "ylim": None,                            # default: [0, max_abs_fit]
    "xlabel": "wavelength [nm]",
    "ylabel": "absorbance [a.u.]",
    "frame": False,                          # Rahmen oben/rechts
    "tick_direction": "out",
    "line_color": "black",
    "line_width": 1.0,
    "spectra": [],
    "r2_mode": "legend",                     # legend | label | off
    "labels": {
        "show": True,
        "show_error": False,
        "eps_digits": "auto",                # auto = nach Unsicherheit runden, oder int = sign. Stellen
        "eps_unit": r"cm$^{-1}$ M$^{-1}$",
        "font_size": 15,
        "pos": {},                           # optional fest: {336: [x, y]} in Achsenbruchteilen
    },
    "inset": {
        "show": True,
        "size": [0.36, 0.34],                # Breite/Höhe der Inset-Achse (Achsenbruchteile)
        "pos": "auto",
        "prefer": "top-right",
        "table": True,
        "font_size": 9,
        "table_font_size": 6.5,
        "show_excluded": False,
        "xlabel": None,                      # default: "c [<conc_unit>]"
        "ylabel": r"A/d [cm$^{-1}$]",
        "colors": ["#000000", "#e8231b", "#1764e8", "#1f9e4a", "#a35ce0", "#e08a00", "#00a0b0"],
    },
    "images": [],
    "layout_file": None,                     # default: <config>_layout.yaml
}

CONC_TO_M = {"mM": 1e-3, "uM": 1e-6, "µM": 1e-6, "M": 1.0, "mg/mL": None}


def conc_factor(cfg):
    """Faktor Konzentrationseinheit -> mol/L. None = keine Molmasse (spezifischer Koeff.)."""
    if cfg["conc_unit"] == "mg/mL":
        mw = cfg.get("molar_mass_g_mol")
        return (1.0 / float(mw)) if mw else None
    return CONC_TO_M[cfg["conc_unit"]]


def clip_polyline(x, y, xlim, ylim):
    """Linienzug auf das Rechteck xlim×ylim beschneiden: Schnittpunkte mit dem Rand
    einfügen, Teile außerhalb durch NaN-Lücken ersetzen."""
    x0, x1 = sorted(xlim)
    y0, y1 = sorted(ylim)
    sel = (x >= x0) & (x <= x1)
    x, y = np.asarray(x, float)[sel], np.asarray(y, float)[sel]
    if len(x) < 2:
        return x, y
    out_x, out_y = [x[0]], [y[0] if y0 <= y[0] <= y1 else np.nan]
    for i in range(1, len(x)):
        xa, ya, xb, yb = x[i - 1], y[i - 1], x[i], y[i]
        for lim in (y0, y1):                       # Grenzübergänge zwischen a und b
            if (ya - lim) * (yb - lim) < 0:
                t = (lim - ya) / (yb - ya)
                xc = xa + t * (xb - xa)
                entering = (y0 <= yb <= y1)
                if entering:
                    out_x += [xc, xc]
                    out_y += [np.nan, lim]
                else:
                    out_x += [xc, xc]
                    out_y += [lim, np.nan]
        out_x.append(xb)
        out_y.append(yb if y0 <= yb <= y1 else np.nan)
    return np.array(out_x), np.array(out_y)


def apply_export_size(cfg, w_cm, h_cm):
    """Figur exakt w×h cm groß machen; Schrift, Linien und Abstände mitskalieren.
    Referenz ist das Standardformat 8×6 Zoll (20.3×15.2 cm)."""
    w_in, h_in = w_cm / 2.54, h_cm / 2.54
    s = min(w_in / 8.0, h_in / 6.0)
    cfg["size_cm"] = [w_cm, h_cm]
    cfg["figsize_in"] = [w_in, h_in]
    cfg["scale"] = s
    cfg["font_size"] = DEFAULTS["font_size"] * s
    cfg["line_width"] = max(0.6, DEFAULTS["line_width"] * s)
    cfg["labels"]["font_size"] = DEFAULTS["labels"]["font_size"] * s
    cfg["inset"]["font_size"] = max(5.5, DEFAULTS["inset"]["font_size"] * s)
    cfg["inset"]["table_font_size"] = max(5.0, DEFAULTS["inset"]["table_font_size"] * s)
    return cfg


def eps_max_decimals(cfg):
    """ε in M⁻¹ cm⁻¹ grundsätzlich ganzzahlig; spezifisches a (L g⁻¹ cm⁻¹) normal gerundet."""
    return 0 if conc_factor(cfg) else None


def coeff_symbol_unit(cfg):
    if conc_factor(cfg) is None:
        return "a", r"L g$^{-1}$ cm$^{-1}$"
    return "ε", cfg["labels"]["eps_unit"]


def deep_merge(base, over):
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


# ----------------------------------------------------------------------------
# Daten einlesen (CSV/TXT, Komma- oder Punkt-Dezimal, Header/Metadaten egal)
# ----------------------------------------------------------------------------
_MODES = [("\t", False), ("\t", True), (";", True), (";", False),
          (",", False), (None, False), (None, True)]


def _parse_line(s, delim, dec_comma):
    parts = s.split(delim) if delim else s.split()
    vals = []
    for p in parts:
        p = p.strip().strip('"').strip("'")
        if p == "":
            vals.append(np.nan)
            continue
        if dec_comma:
            p = p.replace(",", ".")
        try:
            vals.append(float(p))
        except ValueError:
            return None
    return vals


def read_table(path):
    lines = Path(path).read_text(encoding="utf-8-sig", errors="replace").splitlines()
    best = []
    for delim, dc in _MODES:
        rows = []
        for line in lines:
            s = line.strip()
            if not s:
                continue
            v = _parse_line(s, delim, dc)
            if v is not None and np.isfinite(v).sum() >= 2:
                rows.append(v)
        if len(rows) > len(best):
            best = rows
    if not best:
        raise ValueError(f"Keine numerischen Daten in {path} gefunden")
    width = max(len(r) for r in best)
    arr = np.full((len(best), width), np.nan)
    for i, r in enumerate(best):
        arr[i, :len(r)] = r
    return arr


def load_spectrum(entry, base_dir):
    path = Path(entry["file"])
    if not path.is_absolute():
        path = base_dir / path
    arr = read_table(path)
    xc, yc = entry.get("columns", [0, 1])
    return _clean_xy(arr[:, xc], arr[:, yc])


_CONC_RE = re.compile(r"(\d+(?:[p.]\d+)?)\s*(mg_?/?ml|mm|um|µm)(?![a-z])", re.I)
_UNIT_MAP = {"mgml": "mg/mL", "mg/ml": "mg/mL", "mg_ml": "mg/mL", "mm": "mM", "um": "uM", "µm": "uM"}


def parse_sample_name(name):
    m = _CONC_RE.search(name)
    if not m:
        return None
    conc = float(m.group(1).lower().replace("p", "."))
    unit = _UNIT_MAP.get(m.group(2).lower().replace(" ", ""), m.group(2))
    group = name[:m.start()].rstrip("-_ ") or "probe"
    return group, conc, unit


def read_cary_samples(path):
    """Cary-Export: Zeile 1 = Probennamen (je 2 Spalten), danach λ/Abs-Paare.
    -> Liste von dict(key, name, x, y, parsed=(serie, c, einheit) | None)."""
    text = Path(path).read_text(encoding="utf-8-sig", errors="replace")
    lines = [ln for ln in text.splitlines() if ln.strip()]      # Leerzeilen (z. B. \r\r\n) ignorieren
    first = lines[0] if lines else ""
    if len(lines) > 1 and "intensity" in first.lower() and lines[1].lstrip().startswith(","):
        # Cary-Eclipse-Export: Zeile 1 Spaltenköpfe, Zeile 2 Probennamen (je 2 Spalten)
        names = [n.strip() for n in lines[1].split(",")[1::2]]
    else:
        names = [n.strip() for n in first.split(",")[0::2]]
    ex_list = [float(v) for v in _EX_RE.findall(text)]
    arr = read_table(path)
    samples, seen = [], {}
    for k, name in enumerate(names):
        if 2 * k + 1 >= arr.shape[1]:
            continue
        name = name or f"#{k + 1}"
        seen[name] = seen.get(name, 0) + 1
        key = name if seen[name] == 1 else f"{name} ({seen[name]})"   # doppelte Namen
        x, y = _clean_xy(arr[:, 2 * k], arr[:, 2 * k + 1])
        if len(x) < 5:
            continue
        samples.append({"key": key, "name": name, "x": x, "y": y, "parsed": parse_sample_name(name),
                        "ex": ex_list[k] if k < len(ex_list) else None})
    return samples


_EX_RE = re.compile(r"Ex\. Wavelength \(nm\)\s+([\d.]+)")
BINARY_EXT = {".dsw", ".bsw", ".spc", ".fbsw", ".fdsw"}
_HEADERISH = re.compile(r"^(#?\d*|wave.*|.*\(nm\).*|abs.*|nm|x|y)$", re.I)


def read_binary_samples(path):
    """Cary WinUV .DSW/.BSW (und Shimadzu .SPC) über den mitgelieferten parseuv-Parser."""
    from parseuv_lite import CaryFile
    cf = CaryFile(str(path))
    raw = Path(path).read_bytes().decode("cp1252", errors="replace")
    ex_list = [float(v) for v in _EX_RE.findall(raw)]
    out = []
    spectra = [sp for sp in cf.spectra if not sp.title.lower().startswith("baseline")]  # Gerätebasislinien
    for k, sp in enumerate(spectra):
        x, y = _clean_xy(np.asarray(sp.wavelengths, float), np.asarray(sp.absorbances, float))
        if len(x) >= 5:
            out.append({"key": sp.title, "name": sp.title, "x": x, "y": y,
                        "parsed": parse_sample_name(sp.title),
                        "ex": ex_list[k] if len(ex_list) == len(spectra) else
                        (ex_list[0] if len(set(ex_list)) == 1 else None)})
    return out


def read_samples(paths):
    """Eine oder mehrere Dateien (Cary-CSV/TXT, .DSW, .BSW) -> gemeinsame Probenliste.
    Bei mehreren Dateien wird der Dateiname vorangestellt, damit Schlüssel eindeutig bleiben."""
    paths = [Path(p) for p in (paths if isinstance(paths, (list, tuple)) else [paths])]
    allsamples = []
    for p in paths:
        smp = read_binary_samples(p) if p.suffix.lower() in BINARY_EXT else read_cary_samples(p)
        if len(smp) == 1 and (not smp[0]["parsed"]) and _HEADERISH.match(smp[0]["name"].strip()):
            smp[0]["name"] = smp[0]["key"] = p.stem       # Einzelmessung ohne sinnvollen Namen
            smp[0]["parsed"] = parse_sample_name(p.stem)
        for s_ in smp:
            if len(paths) > 1:
                s_["key"] = f"{p.stem}: {s_['name']}"
            else:
                s_["key"] = s_.get("key") or s_["name"]
            s_["file"] = str(p)
        allsamples += smp
    seen = {}
    for s_ in allsamples:                                  # verbleibende Doppelungen
        seen[s_["key"]] = seen.get(s_["key"], 0) + 1
        if seen[s_["key"]] > 1:
            s_["key"] = f"{s_['key']} ({seen[s_['key']]})"
    return allsamples


def group_samples(samples, overrides=None, default_series="serie"):
    """Proben zu Serien. overrides: {key: {conc, unit, series}} hat Vorrang vor dem Namen.
    Proben ohne Konzentration werden ausgelassen. -> (groups, units, missing_keys)"""
    overrides = overrides or {}
    groups, missing = {}, []
    for s_ in samples:
        o = overrides.get(s_["key"]) or {}
        if o.get("conc"):
            g, c, u = o.get("series") or default_series, float(o["conc"]), o.get("unit", "mM")
        elif s_["parsed"] and not o.get("skip"):
            g, c, u = s_["parsed"]
        else:
            if not o.get("skip"):
                missing.append(s_["key"])
            continue
        groups.setdefault(g, []).append({"x": s_["x"], "y": s_["y"], "c": c, "unit": u,
                                         "name": s_["key"], "color": None})
    units = {}
    for g, sp in groups.items():
        us = {s_["unit"] for s_ in sp}
        if len(us) > 1:
            raise ValueError(T("mixed_units", g=g, u=us))
        units[g] = us.pop()
    return groups, units, missing


def load_cary(path):
    groups, _, missing = group_samples(read_samples([path]), default_series=Path(path).stem)
    for k in missing:
        log("  " + T("no_conc_in_name", name=k))
    return groups


def _clean_xy(x, y):
    m = np.isfinite(x) & np.isfinite(y)
    x, y = x[m], y[m]
    x, idx = np.unique(x, return_index=True)
    return x, y[idx]


def apply_baseline(spectra, cfg):
    """Automatische Basislinienkorrektur einer Verdünnungsreihe.

    Fenster: dort, wo die konzentrierteste Probe am wenigsten absorbiert.
    series-Modus: Messwert im Fenster = Offset_i + a_w * c_i. Der zu c proportionale Teil
    (echte Restabsorption, z. B. Bandenausläufer) bleibt erhalten, nur der Offset wird
    abgezogen. simple-Modus: kompletter Fensterwert wird abgezogen.
    """
    bl = cfg["baseline_nm"]
    if not bl:
        return None
    if bl == "auto":
        ref = max(spectra, key=lambda s_: s_["c"])
        lo, hi = cfg["baseline_search_nm"]
        xmin = max(max(s_["x"].min() for s_ in spectra), lo if lo is not None else -np.inf)
        xmax = min(min(s_["x"].max() for s_ in spectra), hi if hi is not None else np.inf)
        w = float(cfg["baseline_width_nm"])
        best = None
        for a in np.arange(xmin, xmax - w + 1e-9, 2.0):
            sel = (ref["x"] >= a) & (ref["x"] <= a + w)
            if sel.sum() < 5:
                continue
            v = float(np.median(ref["y"][sel]))
            if best is None or v < best[0]:
                best = (v, a)
        if best is None:
            log("  " + T("no_baseline_window"))
            return None
        bl = [best[1], best[1] + w]
    a, b = sorted(bl)
    vals = np.array([np.median(s_["y"][(s_["x"] >= a) & (s_["x"] <= b)]) for s_ in spectra])
    c = np.array([s_["c"] for s_ in spectra])
    offs, kept = vals.copy(), 0.0
    if cfg["baseline_mode"] == "series" and len(spectra) >= 3:
        ft = linfit(c, vals, True)
        if ft and np.isfinite(ft["se_slope"]) and ft["slope"] > 2 * ft["se_slope"] > 0:
            kept = ft["slope"]
            offs = vals - kept * c
    for s_, o in zip(spectra, offs):
        s_["y"] = s_["y"] - o
    log("  " + T("baseline_window", a=a, b=b, offs=", ".join(f"{o:+.4f}" for o in offs)))
    if kept:
        log("  " + T("baseline_kept", k=kept, u=cfg["conc_unit"]))
    return {"window": (a, b), "offsets": offs.tolist(), "kept_slope": kept}


def detect_peaks(spectra, cfg):
    """Peaksuche auf zusammengesetztem A/c-Spektrum (je λ höchste ungesättigte Konz.)."""
    xs = np.concatenate([s["x"] for s in spectra])
    lo, hi = cfg["peak_range_nm"]
    lo = max(lo if lo is not None else xs.min(), xs.min())
    hi = min(hi if hi is not None else xs.max(), xs.max())
    grid = np.arange(math.ceil(lo), math.floor(hi) + 1, 1.0)
    comp = np.full(grid.shape, np.nan)
    aref = np.full(grid.shape, np.nan)
    for s in sorted(spectra, key=lambda s: -s["c"]):
        yi = np.interp(grid, s["x"], s["y"])
        ok = np.isnan(comp) & (yi <= cfg["max_abs_fit"])
        comp[ok] = yi[ok] / s["c"]
        aref[ok] = yi[ok]
    comp = np.convolve(np.nan_to_num(comp), np.ones(7) / 7, mode="same")
    peaks = []
    n = len(comp)
    for i in range(5, n - 5):
        v = comp[i]
        if v <= 0 or v < comp[max(0, i - 8):i + 9].max():
            continue
        j = i
        while j > 0 and comp[j - 1] <= v:
            j -= 1
        k = i
        while k < n - 1 and comp[k + 1] <= v:
            k += 1
        prom = v - max(comp[j:i + 1].min(), comp[i:k + 1].min())
        if prom >= cfg["peak_min_prominence"] * v and aref[i] >= 0.02:
            peaks.append(float(grid[i]))
    return peaks


def abs_at(x, y, lam, win):
    if win and win > 0:
        sel = (x >= lam - win) & (x <= lam + win)
        if sel.any():
            return float(y[sel].mean())
    return float(np.interp(lam, x, y, left=np.nan, right=np.nan))


# ----------------------------------------------------------------------------
# Auswertung
# ----------------------------------------------------------------------------
def linfit(x, y, intercept=True):
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    n = len(x)
    if n < (2 if intercept else 1):
        return None
    if intercept:
        X = np.column_stack([x, np.ones(n)])
        (m, b), *_ = np.linalg.lstsq(X, y, rcond=None)
        res = y - (m * x + b)
        rss = float(res @ res)
        dof = n - 2
        if dof > 0:
            cov = rss / dof * np.linalg.inv(X.T @ X)
            se_m, se_b = np.sqrt(np.diag(cov))
        else:
            se_m = se_b = np.nan
    else:
        m = float(x @ y / (x @ x))
        b, se_b = 0.0, np.nan
        res = y - m * x
        rss = float(res @ res)
        dof = n - 1
        se_m = math.sqrt(rss / dof / (x @ x)) if dof > 0 else np.nan
    sst = float(((y - y.mean()) ** 2).sum())
    r2 = 1 - rss / sst if sst > 0 else np.nan
    return dict(slope=float(m), se_slope=float(se_m), intercept=float(b),
                se_intercept=float(se_b), rss=rss, r2=r2, n=n)


def _decimals_for(v, e, digits):
    if digits == "auto" and e is not None and np.isfinite(e) and e > 0:
        exp = math.floor(math.log10(e))
        lead = e / 10 ** exp
        nsig = 2 if lead < 3 else 1          # Fehler auf 1 (bzw. 2 bei führender 1/2) Stellen
        return nsig - 1 - exp
    n = 4 if digits == "auto" else int(digits)
    if v == 0 or not np.isfinite(v):
        return 0
    return n - 1 - math.floor(math.log10(abs(v)))


def fmt_ve(v, e=None, digits="auto", max_decimals=None):
    """Wert ± Fehler, gerundet nach Unsicherheit. max_decimals=0: nie Nachkommastellen (ε)."""
    d = _decimals_for(v, e, digits)
    if max_decimals is not None:
        d = min(d, max_decimals)
    vs = f"{round(v, d):.{max(d, 0)}f}"
    es = f"{round(e, d):.{max(d, 0)}f}" if (e is not None and np.isfinite(e)) else None
    return vs.replace("-", "\u2212"), es


def evaluate(cfg, spectra):
    d = float(cfg["path_length_cm"])
    fac = conc_factor(cfg) or 1.0         # ohne Molmasse: a in L g-1 cm-1 (mg/mL = g/L)
    results = []
    for lam0 in cfg["wavelengths_nm"]:
        lam = float(lam0)
        if cfg["snap_window_nm"] > 0:
            w = cfg["snap_window_nm"]
            cand = [s for s in spectra
                    if np.nanmax(s["y"][(s["x"] >= lam - w) & (s["x"] <= lam + w)], initial=np.inf)
                    <= cfg["max_abs_fit"]]
            if cand:
                s = max(cand, key=lambda s: s["c"])
                sel = (s["x"] >= lam - w) & (s["x"] <= lam + w)
                lam = float(s["x"][sel][np.argmax(s["y"][sel])])
        pts = []
        for s in spectra:
            A = abs_at(s["x"], s["y"], lam, cfg["avg_window_nm"])
            pts.append((s["c"], A, np.isfinite(A) and A <= cfg["max_abs_fit"]))
        used = [(c, A) for c, A, ok in pts if ok]
        excl = [(c, A) for c, A, ok in pts if not ok and np.isfinite(A)]
        fit = linfit([c for c, _ in used], [A / d for _, A in used], cfg["fit_intercept"]) \
            if len(used) >= cfg["min_fit_points"] else None
        r = dict(lam=lam, lam_requested=float(lam0), used=used, excluded=excl, fit=fit)
        if fit and fit["r2"] < cfg["min_r2"]:
            log("  " + T("r2_hidden", lam=lam, r2=fit["r2"], min=cfg["min_r2"]))
            r["hidden"] = True
        if fit:
            r["eps"] = fit["slope"] / fac
            r["eps_err"] = fit["se_slope"] / fac
            warn = []
            if fit["n"] < 4:
                warn.append(T("few_points", n=fit["n"]))
            if cfg["fit_intercept"] and np.isfinite(fit["se_intercept"]) and fit["se_intercept"] > 0 \
                    and abs(fit["intercept"]) > 2 * fit["se_intercept"]:
                warn.append(T("intercept_sig", b=fit["intercept"], e=fit["se_intercept"]))
            r["warnings"] = warn
        results.append(r)
    return results


def write_results(results, path, cfg):
    cu = cfg["conc_unit"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["lambda_nm", "n_used", "n_excluded", f"slope_cm-1_{cu}-1", "se_slope",
                    "intercept_cm-1", "se_intercept", "R2", "RSS",
                    "eps_M-1cm-1" if conc_factor(cfg) else "a_L_g-1_cm-1", "err", "warnings"])
        for r in results:
            ft = r["fit"]
            if not ft:
                w.writerow([r["lam"], len(r["used"]), len(r["excluded"])] + [""] * 8 + ["kein Fit"])
                continue
            w.writerow([r["lam"], ft["n"], len(r["excluded"]), ft["slope"], ft["se_slope"],
                        ft["intercept"], ft["se_intercept"], ft["r2"], ft["rss"],
                        r["eps"], r["eps_err"], " | ".join(r["warnings"])])


def print_results(results, cfg):
    head = "ε / M⁻¹cm⁻¹" if conc_factor(cfg) else "a / L g⁻¹cm⁻¹"
    log(f"\n{'λ/nm':>7} {'n':>3} {head:>20} {T('hdr_intercept'):>18} {'R²':>8}")
    for r in results:
        ft = r["fit"]
        if not ft:
            log(f"{r['lam']:7.1f}   –  " + T("no_fit", n=len(r["used"]), cut=cfg["max_abs_fit"],
                                                min=cfg["min_fit_points"]))
            continue
        v, e = fmt_ve(r["eps"], r["eps_err"], max_decimals=eps_max_decimals(cfg))
        b, be = fmt_ve(ft["intercept"], ft["se_intercept"])
        eps_s = f"{v} ± {e}" if e else v
        b_s = f"{b} ± {be}" if be else b
        log(f"{r['lam']:7.1f} {ft['n']:3d} {eps_s:>20} {b_s:>18} {ft['r2']:8.5f}")
        for wmsg in r["warnings"]:
            log(f"{'':12}⚠ {wmsg}")
    log()


# ----------------------------------------------------------------------------
# Freiflächen-Suche (Raster in Achsenbruchteilen)
# ----------------------------------------------------------------------------
class FreeSpace:
    def __init__(self, n=240, margin=0.01):
        self.n = n
        self.margin = margin
        self.curves = np.zeros((n, n), bool)         # [iy, ix] unter der Spektrenhülle
        self.elems = np.zeros((n, n), bool)          # platzierte Elemente
        self.c = (np.arange(n) + 0.5) / n

    def block_below(self, env):
        self.curves |= self.c[:, None] <= env[None, :]

    def block_rect(self, x0, y0, w, h, pad=0.012):
        n = self.n
        ix0, ix1 = int(max(0, math.floor((x0 - pad) * n))), int(min(n, math.ceil((x0 + w + pad) * n)))
        iy0, iy1 = int(max(0, math.floor((y0 - pad) * n))), int(min(n, math.ceil((y0 + h + pad) * n)))
        self.elems[iy0:iy1, ix0:ix1] = True

    def find(self, w, h, score_fn, over_curves=False):
        """over_curves=True: nur Überlappung mit anderen Elementen vermeiden (Notlösung)."""
        occ = self.elems if over_curves else (self.elems | self.curves)
        n = self.n
        wc, hc = int(math.ceil(w * n)), int(math.ceil(h * n))
        m = int(math.ceil(self.margin * n))
        if wc + 2 * m > n or hc + 2 * m > n:
            return None
        S = np.zeros((n + 1, n + 1))
        S[1:, 1:] = occ.cumsum(0).cumsum(1)
        A = S[hc:, wc:] - S[:n + 1 - hc, wc:] - S[hc:, :n + 1 - wc] + S[:n + 1 - hc, :n + 1 - wc]
        iy, ix = np.mgrid[0:A.shape[0], 0:A.shape[1]]
        ok = (A == 0) & (ix >= m) & (ix + wc <= n - m) & (iy >= m) & (iy + hc <= n - m)
        if not ok.any():
            return None
        X, Y = ix / n, iy / n
        sc = np.where(ok, score_fn(X, Y, wc / n, hc / n), np.inf)
        k = np.unravel_index(np.argmin(sc), sc.shape)
        return float(X[k]), float(Y[k])


def corner_score(prefer):
    return {
        "top-right": lambda X, Y, w, h: (1 - X - w) + (1 - Y - h),
        "top-left": lambda X, Y, w, h: X + (1 - Y - h),
        "top": lambda X, Y, w, h: abs(X + w / 2 - 0.5) + (1 - Y - h),
        "bottom-right": lambda X, Y, w, h: (1 - X - w) + Y,
        "right": lambda X, Y, w, h: (1 - X - w) + 0.5 * abs(Y + h / 2 - 0.5),
        "auto": lambda X, Y, w, h: 0.5 * (1 - Y - h) + 0.2 * abs(X + w / 2 - 0.5),
    }.get(prefer, None) or corner_score("auto")


def anchor_score(ax_, ay_):
    def f(X, Y, w, h):
        dx = np.maximum.reduce([X - ax_, np.zeros_like(X), ax_ - (X + w)])
        dy = np.maximum.reduce([Y - ay_, np.zeros_like(Y), ay_ - (Y + h)])
        below = (Y + h / 2 < ay_) * 0.3            # Labels lieber oberhalb der Bande
        return np.hypot(dx, dy) + 0.15 * np.abs(X + w / 2 - ax_) + below
    return f


# ----------------------------------------------------------------------------
# Bilder
# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
# Plot
# ----------------------------------------------------------------------------
def setup_fonts(plt, cfg):
    from matplotlib import font_manager as fm
    family = None
    for name in cfg["font"]:
        try:
            fm.findfont(fm.FontProperties(family=name), fallback_to_default=False)
            family = name
            break
        except Exception:
            continue
    family = family or "DejaVu Sans"
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": [family] + cfg["font"],
        "font.size": cfg["font_size"],
        "mathtext.fontset": "custom",
        "mathtext.rm": family,
        "mathtext.it": f"{family}:italic",
        "mathtext.bf": f"{family}:bold",
        "mathtext.sf": family, "mathtext.cal": family, "mathtext.tt": family,
        "pdf.fonttype": 42, "ps.fonttype": 42, "svg.fonttype": "none",
        "axes.linewidth": max(0.6, cfg.get("scale", 1.0)),
    })
    return family


class Figure:
    def __init__(self, plt, cfg, spectra, results, layout, fig=None):
        self.plt, self.cfg, self.spectra, self.results, self.layout = plt, cfg, spectra, results, layout
        if fig is None:
            fig = plt.figure(figsize=cfg["figsize_in"])
        else:
            fig.clear()
            fig.set_size_inches(cfg["figsize_in"], forward=False)
        self.fig = fig
        self.ax = self.fig.add_axes(cfg["axes_rect"])
        self.axes_items = {}     # id -> Axes   (Inset, Bilder)
        self._inset_table = None
        self.tight_off = {}      # id -> (dx0, dy0, w, h) Tight-Box relativ zur Achsenposition
        self.ann_items = {}      # id -> Annotation
        self._main()
        self._fit_axes(0.01 if cfg.get("size_cm") else 0.06)
        self._inset()
        self._labels()
        self._images()
        self._place()

    # -- Hauptplot -----------------------------------------------------------
    def _main(self):
        cfg, ax = self.cfg, self.ax
        xs = np.concatenate([s["x"] for s in self.spectra])
        xlim = cfg["xlim"] or (xs.min(), xs.max())
        ylim = cfg["ylim"] or (0, cfg["max_abs_fit"])
        for s in self.spectra:
            # Kurven geometrisch an den Achsengrenzen kappen statt per Clip-Pfad:
            # manche SVG-Renderer (MuPDF, evtl. Word) ignorieren Clip-Pfade
            cx, cy = clip_polyline(s["x"], s["y"], xlim, ylim)
            ax.plot(cx, cy, color=s.get("color") or cfg["line_color"],
                    lw=cfg["line_width"], solid_joinstyle="round", solid_capstyle="butt")
        ax.set_xlim(xlim)
        ax.set_ylim(ylim)
        ax.set_xlabel(cfg["xlabel"], fontsize=cfg["font_size"] * 1.3)
        ax.set_ylabel(cfg["ylabel"], fontsize=cfg["font_size"] * 1.3)
        ax.minorticks_on()
        ax.tick_params(which="both", direction=cfg["tick_direction"], top=False, right=False)
        sc = cfg.get("scale", 1.0)
        ax.tick_params(which="major", length=6 * sc, width=max(0.6, sc))
        ax.tick_params(which="minor", length=3 * sc, width=max(0.5, 0.8 * sc))
        if not cfg["frame"]:
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)

    def _fit_axes(self, pad_in=0.06):
        """Achse so setzen, dass Achsenbeschriftungen exakt in die Figur passen
        (wichtig bei fester Exportgröße, da dann nicht zugeschnitten wird)."""
        rend = self._renderer()
        fw, fh = self.fig.get_size_inches() * self.fig.dpi
        tb = self.ax.get_tightbbox(rend)
        ab = self.ax.get_window_extent(rend)
        pad = pad_in * self.fig.dpi
        left = (ab.x0 - tb.x0 + pad) / fw
        bottom = (ab.y0 - tb.y0 + pad) / fh
        right = 1 - (tb.x1 - ab.x1 + pad) / fw
        top = 1 - (tb.y1 - ab.y1 + pad) / fh
        if right - left > 0.3 and top - bottom > 0.3:
            self.ax.set_position([left, bottom, right - left, top - bottom])

    def _af_to_fig(self, x, y):
        disp = self.ax.transAxes.transform((x, y))
        return self.fig.transFigure.inverted().transform(disp)

    def _fig_to_af(self, x, y):
        disp = self.fig.transFigure.transform((x, y))
        return self.ax.transAxes.inverted().transform(disp)

    def _set_axes_af(self, a, x, y, w, h):
        x0, y0 = self._af_to_fig(x, y)
        x1, y1 = self._af_to_fig(x + w, y + h)
        a.set_position([x0, y0, x1 - x0, y1 - y0])

    # -- Inset ---------------------------------------------------------------
    def _inset(self):
        icfg = self.cfg["inset"]
        if not icfg["show"]:
            return
        fits = [r for r in self.results if r["fit"] and not r.get("hidden")]
        if not fits:
            return
        iax = self.fig.add_axes([0, 0, 0.1, 0.1])
        self.inset_size = icfg["size"]
        self._set_axes_af(iax, 0.5, 0.5, *icfg["size"])
        fs = icfg["font_size"]
        cols = icfg["colors"]
        d = self.cfg["path_length_cm"]
        for i, r in enumerate(fits):
            col = cols[i % len(cols)]
            lbl = f"{r['lam']:g} nm"
            if self.cfg["r2_mode"] == "legend" and r["fit"]:
                lbl = f"{r['lam']:g} nm   $R^2$ = {r['fit']['r2']:.4f}"
            if r["used"]:
                c, A = np.array(r["used"]).T
                iax.plot(c, A / d, "s", color=col, ms=max(2.5, 4 * self.cfg.get("scale", 1.0)),
                         label=lbl, zorder=3)
            if icfg["show_excluded"] and r["excluded"]:
                c, A = np.array(r["excluded"]).T
                iax.plot(c, A / d, "s", mfc="none", color=col,
                         ms=max(2.5, 4 * self.cfg.get("scale", 1.0)), zorder=3)
            ft = r["fit"]
            if ft and r["used"]:
                cc = np.array([c for c, _ in r["used"]])
                xx = np.array([cc.min(), cc.max()])
                iax.plot(xx, ft["slope"] * xx + ft["intercept"], "-", color=col, lw=0.9, zorder=2)
        iax.set_xlabel(icfg["xlabel"] or f"c [{self.cfg['conc_unit']}]", fontsize=fs, labelpad=1)
        iax.set_ylabel(icfg["ylabel"], fontsize=fs, labelpad=1)
        iax.tick_params(labelsize=fs * 0.9, direction="out", length=3, pad=1.5)
        iax.set_ylim(bottom=0)
        iax.set_xlim(left=0)
        iax.legend(fontsize=fs * 0.8, loc="best", frameon=True, fancybox=False,
                   edgecolor="0.3", handletextpad=0.2, borderpad=0.3, labelspacing=0.2,
                   handlelength=1.0)
        if icfg["table"]:
            cu = self.cfg["conc_unit"]
            rows = []
            for r in fits:
                ft = r["fit"]
                s, se = fmt_ve(ft["slope"], ft["se_slope"])
                b, be = fmt_ve(ft["intercept"], ft["se_intercept"])
                rows.append([f"{r['lam']:g}", f"{s} ± {se}" if se else s,
                             f"{b} ± {be}" if be else b, f"{ft['r2']:.4f}"])
            cu_s = f"({cu})" if "/" in cu else cu
            header = ["λ [nm]", f"slope [cm$^{{-1}}$ {cu_s}$^{{-1}}$]", r"intercept [cm$^{-1}$]", "R$^2$"]
            tfs = icfg["table_font_size"]
            h_in = self.fig.get_size_inches()[1] * self.ax.get_position().height * icfg["size"][1]
            row_h = tfs * 1.55 / 72 / h_in
            nrow = len(rows) + 1
            tab = iax.table(cellText=rows, colLabels=header, cellLoc="center",
                            bbox=[0, 1.04, 1, nrow * row_h])
            tab.auto_set_font_size(False)
            tab.set_fontsize(tfs)
            for (ri, ci), cell in tab.get_celld().items():
                cell.set_linewidth(0.4)
                cell.PAD = 0.02
                if ri == 0:
                    cell.set_facecolor("#eeeeee")
            tab.auto_set_column_width(list(range(4)))
            self._inset_table = tab
        self.axes_items["inset"] = iax

    # -- Labels --------------------------------------------------------------
    def _labels(self):
        lcfg = self.cfg["labels"]
        if not lcfg["show"]:
            return
        lo, hi = self.ax.get_xlim()
        for r in self.results:
            if not r["fit"] or r.get("hidden") or not (lo <= r["lam"] <= hi):
                continue
            v, e = fmt_ve(r["eps"], r["eps_err"], lcfg["eps_digits"], eps_max_decimals(self.cfg))
            eps = f"({v} ± {e})" if (lcfg["show_error"] and e) else v
            sym, unit = coeff_symbol_unit(self.cfg)
            txt = f"λ =  {r['lam']:g} nm\n{sym} =  {eps} {unit}"
            if self.cfg["r2_mode"] == "label":
                txt += f"\n$R^2$ =  {r['fit']['r2']:.4f}"
            ann = self.ax.annotate(txt, xy=(r["lam"], 0), xycoords="data",
                                   xytext=(0.5, 0.5), textcoords="axes fraction",
                                   ha="left", va="bottom", fontsize=lcfg["font_size"],
                                   linespacing=1.4, annotation_clip=False, zorder=5)
            self.ann_items[f"label_{r['lam']:g}"] = ann

    # -- Bilder --------------------------------------------------------------
    def _images(self):
        ax_bb = self.ax.get_window_extent()
        for im in self.cfg["images"]:
            asset = im.get("_asset") or load_asset(im, self.cfg)
            arr = asset["rgba"]
            w = float(im.get("width", 0.18))
            h = w * arr.shape[0] / arr.shape[1] * ax_bb.width / ax_bb.height
            if "height" in im:
                h = float(im["height"])
                w = h * arr.shape[1] / arr.shape[0] * ax_bb.height / ax_bb.width
            a = self.fig.add_axes([0, 0, 0.1, 0.1])
            a.imshow(arr, interpolation="antialiased", interpolation_stage="rgba", aspect="auto")
            a.set_axis_off()
            a._img_wh = (w, h)
            a._vector = (asset["pdf"], asset["clip"]) if asset.get("pdf") else None
            self._set_axes_af(a, 0.5, 0.5, w, h)
            iid = im.get("id") or Path(im["file"]).stem
            self.axes_items[f"image_{iid}"] = a
            im["_id"] = f"image_{iid}"

    # -- automatische Platzierung --------------------------------------------
    def _envelope(self, n):
        x0, x1 = self.ax.get_xlim()
        y0, y1 = self.ax.get_ylim()
        fine = np.linspace(0, 1, 4 * n)
        xd = x0 + fine * (x1 - x0)
        env = np.full(fine.shape, -np.inf)
        for s in self.spectra:
            yi = np.interp(xd, s["x"], s["y"], left=-np.inf, right=-np.inf)
            env = np.maximum(env, (yi - y0) / (y1 - y0))
        env = np.clip(env, -1, 1).reshape(n, 4).max(1)
        env = np.maximum.reduce([env, np.roll(env, 1), np.roll(env, -1)])
        return env + 0.02

    def _measure_af(self, bb):
        inv = self.ax.transAxes.inverted()
        (x0, y0), (x1, y1) = inv.transform([[bb.x0, bb.y0], [bb.x1, bb.y1]])
        return x0, y0, x1 - x0, y1 - y0

    def _renderer(self):
        # eigener Agg-Renderer mit fig.dpi: unabhängig von GUI-Backend/HiDPI-Skalierung
        from matplotlib.backends.backend_agg import RendererAgg
        w, h = self.fig.get_size_inches() * self.fig.dpi
        return RendererAgg(int(w), int(h), self.fig.dpi)

    def _place(self):
        fig, ax = self.fig, self.ax
        rend = self._renderer()
        self._rend = rend
        fs = FreeSpace()
        env = self._envelope(fs.n)
        fs.block_below(env)
        lay = self.layout
        warn_over = []

        def find(key, w, h, score):
            hit = fs.find(w, h, score)
            if hit is None:
                hit = fs.find(w, h, score, over_curves=True)
                if hit is not None:
                    warn_over.append(key)
            return hit

        # 1) Labels zuerst: sie gehören an ihre Bande, alles andere ist verschiebbar
        x0, x1 = ax.get_xlim()
        fixed_lbl = {f"label_{float(k):g}": v for k, v in (self.cfg["labels"].get("pos") or {}).items()}
        for key, ann in self.ann_items.items():
            _, _, bw, bh = self._measure_af(ann.get_window_extent(rend))
            pos = lay.get(key) or fixed_lbl.get(key)
            if pos is None:
                lam = ann.xy[0]
                axn = (lam - x0) / (x1 - x0)
                ayn = min(1.0, float(env[min(fs.n - 1, max(0, int(axn * fs.n)))]))
                pos = find(key, bw, bh, anchor_score(axn, ayn)) or (min(axn, 1 - bw), 1 - bh)
            ann.set_position(tuple(pos))
            fs.block_rect(pos[0], pos[1], bw, bh)

        # 2) Inset: ggf. verkleinern, notfalls ohne Tabelle
        if "inset" in self.axes_items:
            iax = self.axes_items["inset"]
            icfg = self.cfg["inset"]
            fixed = icfg["pos"] if isinstance(icfg["pos"], (list, tuple)) else None
            pos = lay.get("inset") or fixed
            aw, ah = icfg["size"]
            if pos is None:
                tries = [(1.0, True), (1.0, False), (0.85, False), (0.7, False)]
                for f, tab in tries:
                    if not tab and self._inset_table is not None:
                        self._inset_table.set_visible(False)
                    self._set_axes_af(iax, 0.5, 0.5, aw * f, ah * f)
                    dx, dy, tw, th = self._axes_tight(iax, rend)
                    hit = fs.find(tw, th, corner_score(icfg["prefer"]))
                    if hit:
                        break
                if hit:
                    aw, ah = aw * f, ah * f
                    if f < 1 or not tab:
                        log("  " + T("inset_shrunk", f=f, tab="" if tab else T("without_table")))
                else:
                    if self._inset_table is not None:
                        self._inset_table.set_visible(icfg["table"])
                    self._set_axes_af(iax, 0.5, 0.5, aw, ah)
                    dx, dy, tw, th = self._axes_tight(iax, rend)
                    hit = find("inset", tw, th, corner_score(icfg["prefer"])) or (1 - tw, 1 - th)
                pos = (hit[0] - dx, hit[1] - dy)
            else:
                if len(pos) == 4:
                    aw, ah = pos[2], pos[3]
                self._set_axes_af(iax, 0.5, 0.5, aw, ah)
            dx, dy, tw, th = self._axes_tight(iax, rend)
            self._set_axes_af(iax, pos[0], pos[1], aw, ah)
            fs.block_rect(pos[0] + dx, pos[1] + dy, tw, th)

        # 3) Bilder (schrumpfen, falls nicht genug Platz)
        for im in self.cfg["images"]:
            key = im["_id"]
            a = self.axes_items[key]
            w, h = a._img_wh
            pos = lay.get(key) or (im.get("pos") if isinstance(im.get("pos"), (list, tuple)) else None)
            if pos is None:
                hit = None
                for f in (1.0, 0.9, 0.8, 0.7, 0.6, 0.5):
                    hit = fs.find(w * f, h * f, corner_score(im.get("prefer", "auto")))
                    if hit:
                        if f < 1:
                            log("  " + T("image_shrunk", key=key, f=f))
                        w, h = w * f, h * f
                        break
                pos = hit or find(key, w, h, corner_score(im.get("prefer", "auto"))) or (0.5, 0.5)
            else:
                if len(pos) == 4:
                    w, h = pos[2], pos[3]
                pos = pos[:2]
            self._set_axes_af(a, pos[0], pos[1], w, h)
            fs.block_rect(pos[0], pos[1], w, h)

        for k in warn_over:
            log("  " + T("no_space", key=k))
        self.check_overlaps()

    def _axes_tight(self, a, rend):
        p = a.get_position()
        px, py = self._fig_to_af(p.x0, p.y0)
        tx, ty, tw, th = self._measure_af(a.get_tightbbox(rend))
        return tx - px, ty - py, tw, th

    def check_overlaps(self):
        rend = self._renderer()
        boxes = {k: a.get_tightbbox(rend) for k, a in self.axes_items.items()}
        boxes.update({k: a.get_window_extent(rend) for k, a in self.ann_items.items()})
        keys = list(boxes)
        bad = []
        for i, k1 in enumerate(keys):
            for k2 in keys[i + 1:]:
                b1, b2 = boxes[k1], boxes[k2]
                ix = min(b1.x1, b2.x1) - max(b1.x0, b2.x0)
                iy = min(b1.y1, b2.y1) - max(b1.y0, b2.y0)
                if ix > 2 and iy > 2:
                    bad.append(f"{k1} ↔ {k2}")
        for b in bad:
            log("  " + T("overlap", pair=b))
        return bad

    # -- Layout sichern / exportieren ----------------------------------------
    def current_layout(self):
        out = {}
        for key, a in self.axes_items.items():
            p = a.get_position()
            (x0, y0), (x1, y1) = self._fig_to_af(p.x0, p.y0), self._fig_to_af(p.x1, p.y1)
            out[key] = [round(float(v), 4) for v in
                        (x0, y0, x1 - x0, y1 - y0)]
        for key, ann in self.ann_items.items():
            out[key] = [round(float(v), 4) for v in ann.xyann]
        return out

    def export(self):
        """PDF/SVG mit Struktur als Vektorgrafik, PNG gerastert.
        Mit size_cm: exakt diese Größe (kein Zuschnitt), sonst eng zugeschnitten."""
        out = Path(self.cfg["output"])
        if not out.is_absolute():
            out = self.cfg["_base_dir"] / out
        out.parent.mkdir(parents=True, exist_ok=True)
        paths = [out] + [out.with_suffix("." + e.lstrip(".")) for e in self.cfg["extra_formats"]]
        W, H = self.fig.get_size_inches()
        if self.cfg.get("size_cm"):
            from matplotlib.transforms import Bbox
            bb = Bbox.from_bounds(0, 0, W, H)
        else:
            bb = self.fig.get_tightbbox(self._renderer()).padded(0.05)    # in Zoll
        vec = [a for a in self.axes_items.values() if getattr(a, "_vector", None)]
        kw = dict(dpi=self.cfg["dpi"], bbox_inches=bb, facecolor="white")

        def rects():
            for a in vec:
                q = a.get_position()
                yield ((q.x0 * W - bb.x0) * 72, (bb.y1 - q.y1 * H) * 72,
                       (q.x1 * W - bb.x0) * 72, (bb.y1 - q.y0 * H) * 72), a._vector

        for p in dict.fromkeys(paths):
            ext = p.suffix.lower()
            if ext in (".pdf", ".svg") and vec:
                for a in vec:
                    a.set_visible(False)
                with matplotlib.rc_context({"svg.fonttype": "path"}):
                    self.fig.savefig(p, **kw)
                for a in vec:
                    a.set_visible(True)
                items = [(r, v[0], v[1]) for r, v in rects()]
                (IMG.overlay_vectors if ext == ".pdf" else IMG.overlay_vectors_svg)(p, items)
            elif ext == ".svg":
                with matplotlib.rc_context({"svg.fonttype": "path"}):
                    self.fig.savefig(p, **kw)
            else:
                self.fig.savefig(p, **kw)
            if ext == ".svg":
                IMG.svg_defs_first(p)
            log("  " + T("saved", p=p))


def load_asset(im, cfg):
    p = Path(im["file"]).expanduser()
    if not p.is_absolute():
        p = cfg["_base_dir"] / p
    ext = p.suffix.lower()
    kind = im.get("kind") or ("structure" if ext in IMG.VECTOR_EXT | IMG.CHEM_EXT
                              else "photo" if im.get("remove_bg") else "raster")
    if kind == "structure":
        return IMG.load_structure(p)
    if kind == "photo":
        return IMG.load_photo(p, im.get("remove_bg", "auto"), cfg["_base_dir"] / ".uvvis_cache")
    arr = IMG.open_any_image(p)
    if im.get("white_to_alpha"):
        arr = IMG.white_to_alpha(arr)
    if im.get("trim", True):
        arr = IMG.trim_uniform(arr)
    return {"rgba": arr, "pdf": None, "clip": None}


class Dragger:
    """Maus: Inset/Bilder/Labels verschieben (linke Taste), Inset/Bilder skalieren (Mausrad).
    'w' = Layout speichern + exportieren (nur Kommandozeile)."""

    def __init__(self, F, layout_path):
        self.F, self.layout_path, self.drag = F, layout_path, None
        self._cursor = None
        for ann in F.ann_items.values():
            ann.draggable(True)
        c = F.fig.canvas
        self.cids = [c.mpl_connect("button_press_event", self.press),
                     c.mpl_connect("motion_notify_event", self.move),
                     c.mpl_connect("button_release_event", self.release),
                     c.mpl_connect("scroll_event", self.scroll),
                     c.mpl_connect("key_press_event", self.key)]

    def disconnect(self):
        for cid in self.cids:
            self.F.fig.canvas.mpl_disconnect(cid)
        for ann in self.F.ann_items.values():
            try:
                ann.draggable(False)
            except Exception:
                pass

    def _axes_at(self, ev):
        for a in reversed(list(self.F.axes_items.values())):
            if a.get_window_extent().contains(ev.x, ev.y):
                return a
        return None

    def _over_label(self, ev):
        leg = getattr(self.F, "legend", None)
        if leg is not None and leg.contains(ev)[0]:
            return True
        return any(a.contains(ev)[0] for a in self.F.ann_items.values())

    def _set_cursor(self, kind):
        if kind == self._cursor:
            return
        self._cursor = kind
        try:
            from matplotlib.backend_tools import Cursors
            self.F.fig.canvas.set_cursor(Cursors.MOVE if kind else Cursors.POINTER)
        except Exception:
            pass

    def press(self, ev):
        if ev.button != 1 or ev.x is None or self._over_label(ev):
            return
        a = self._axes_at(ev)
        if a is not None:
            self.drag = (a, ev.x, ev.y, a.get_position().frozen())

    def move(self, ev):
        if ev.x is None:
            return
        if not self.drag:
            self._set_cursor(self._over_label(ev) or self._axes_at(ev) is not None)
            return
        a, x0, y0, p = self.drag
        fb = self.F.fig.bbox
        a.set_position([p.x0 + (ev.x - x0) / fb.width, p.y0 + (ev.y - y0) / fb.height,
                        p.width, p.height])
        self.F.fig.canvas.draw_idle()

    def release(self, ev):
        self.drag = None

    def scroll(self, ev):
        """Mausrad: Inset oder Bild um seinen Mittelpunkt vergrößern/verkleinern."""
        if ev.x is None:
            return False
        a = self._axes_at(ev)
        if a is None:
            return False
        # Mausrad: ein Schritt pro Raste. Trackpads (v. a. macOS) liefern Pixel-Deltas und sehr
        # viele Ereignisse -> pro Ereignis kleiner fester Schritt und Zeitdrossel.
        import time
        now = time.monotonic()
        if now - getattr(self, "_last_scroll", 0) < 0.05:
            return False
        self._last_scroll = now
        up = (ev.step > 0) if ev.step else (ev.button == "up")
        f = 1.03 if up else 1 / 1.03
        p = a.get_position()
        w, h = p.width * f, p.height * f
        if not (0.03 < w < 0.95 and 0.03 < h < 0.95):
            return False
        cx, cy = p.x0 + p.width / 2, p.y0 + p.height / 2
        x0, y0 = cx - w / 2, cy - h / 2
        ap = self.F.ax.get_position()                 # innerhalb der Hauptachse halten
        x0 = min(max(x0, ap.x0), ap.x1 - w)
        y0 = min(max(y0, ap.y0), ap.y1 - h)
        a.set_position([x0, y0, w, h])
        self.F.fig.canvas.draw_idle()
        return True

    def key(self, ev):
        if ev.key == "w" and self.layout_path:
            lay = self.F.current_layout()
            self.layout_path.write_text(yaml.safe_dump(lay, sort_keys=True), encoding="utf-8")
            log("  " + T("saved", p=self.layout_path))
            self.F.export()


# ----------------------------------------------------------------------------
# Demo
# ----------------------------------------------------------------------------
def make_demo(d: Path):
    from PIL import ImageDraw
    d.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(1)
    wl = np.arange(220, 1101, 1.0)
    bands = [(225, 18000, 12), (250, 9000, 20), (336, 9620, 14), (290, 2500, 15), (395, 4200, 12),
             (418, 4300, 10), (498, 1000, 35), (540, 600, 25), (669, 134.5, 9),
             (747, 161, 10), (850, 93.7, 12)]
    eps = sum(e * np.exp(-0.5 * ((wl - l) / s) ** 2) for l, e, s in bands)
    concs = [0.390625, 0.78125, 1.5625, 3.125, 6.25]
    entries = []
    for i, c in enumerate(concs):
        A = eps * c * 1e-3 * 0.1
        A = np.where(A > 3.5, 3.5 + rng.normal(0, 0.4, A.shape), A)
        A += rng.normal(0, 0.0015, A.shape) * (1 + 6 * (wl > 1050))
        f = d / f"probe_{i+1}.csv"
        if i == 0:   # deutsches Format zum Testen des Parsers
            lines = ["Probe 1;;", "Wellenlänge (nm);Abs"] + \
                    [f"{x:.1f};{y:.5f}".replace(".", ",") for x, y in zip(wl, A)]
        else:
            lines = ["Wavelength (nm),Abs"] + [f"{x:.1f},{y:.5f}" for x, y in zip(wl, A)]
        f.write_text("\n".join(lines), encoding="utf-8")
        entries.append({"file": f.name, "conc": c})
    # Platzhalterbilder
    im = Image.new("RGBA", (600, 420), (255, 255, 255, 0))
    dr = ImageDraw.Draw(im)
    pts = [(150, 120), (230, 70), (310, 120), (310, 210), (230, 260), (150, 210), (150, 120)]
    dr.line(pts, fill="black", width=8)
    dr.line([(310, 120), (400, 95), (440, 170), (380, 235), (310, 210)], fill="black", width=8)
    dr.line([(380, 235), (380, 360)], fill="black", width=8)
    dr.line([(440, 170), (540, 170)], fill="black", width=8)
    im.save(d / "struktur.png")
    im = Image.new("RGB", (300, 700), "white")
    dr = ImageDraw.Draw(im)
    dr.rectangle([110, 20, 190, 120], fill=(90, 90, 90))
    dr.rectangle([60, 120, 240, 680], fill=(200, 200, 205))
    dr.rectangle([75, 300, 225, 670], fill=(190, 95, 45))
    im.save(d / "kuevette.png")
    cfg = {
        "output": "demo_uvvis.pdf",
        "path_length_cm": 0.1,
        "conc_unit": "mM",
        "baseline_nm": [1000, 1080],
        "max_abs_fit": 1.6,
        "wavelengths_nm": [336, 498, 669, 747, 850],
        "xlim": [220, 1100],
        "ylim": [0, 2.0],
        "spectra": entries,
        "images": [
            {"file": "struktur.png", "width": 0.17, "prefer": "top"},
            {"file": "kuevette.png", "width": 0.09, "prefer": "right"},
        ],
    }
    (d / "config.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True),
                                   encoding="utf-8")
    log(f"Demo: {d}/config.yaml")


# ----------------------------------------------------------------------------
# main
# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
# API für GUI und Kommandozeile
# ----------------------------------------------------------------------------
def load_series(path, overrides=None):
    """Datei(en) -> ({serie: [spektren]}, {serie: einheit}, [proben ohne Konzentration])."""
    paths = path if isinstance(path, (list, tuple)) else [path]
    groups, units, missing = group_samples(read_samples(paths), overrides, Path(paths[0]).stem)
    log(T("cary_series", name=", ".join(Path(p).name for p in paths), s=", ".join(groups) or "–"))
    return groups, units, missing


def prepare_series(cfg, spectra, tag=""):
    """Basislinie, Banden, Fits. Arbeitet auf Kopien -> beliebig oft aufrufbar.
    Gibt (cfg, spectra, results) zurück."""
    cfg = copy.deepcopy(cfg)
    spectra = [dict(s_, y=s_["y"].copy()) for s_ in spectra]
    log("\n" + T("series_head", tag=tag or "–", n=len(spectra), d=cfg["path_length_cm"],
                 u=cfg["conc_unit"]))
    for s_ in sorted(spectra, key=lambda s_: -s_["c"]):
        log(f"  {s_.get('name', ''):30s} c = {s_['c']:g} {cfg['conc_unit']}")
    if cfg["conc_unit"] == "mg/mL" and not cfg.get("molar_mass_g_mol"):
        log("  " + T("no_mw"))
    bl = apply_baseline(spectra, cfg)                 # Basislinie immer aus dem vollen Datenbereich
    lo, hi = cfg["peak_range_nm"]
    if bl:
        hi = min(hi if hi is not None else np.inf, bl["window"][0] - 10)
    if cfg.get("xlim"):                                # Peaksuche nur im dargestellten Bereich
        lo = max(lo if lo is not None else -np.inf, min(cfg["xlim"]))
        hi = min(hi if hi is not None else np.inf, max(cfg["xlim"]))
    cfg["peak_range_nm"] = [None if lo in (None, -np.inf) else float(lo),
                            None if hi in (None, np.inf) else float(hi)]
    if cfg["wavelengths_nm"] in ("auto", None, []):
        cfg["wavelengths_nm"] = detect_peaks(spectra, cfg)
        log("  " + T("peaks_found", l=", ".join(f"{l_:g}" for l_ in cfg["wavelengths_nm"])))
    results = evaluate(cfg, spectra)
    print_results(results, cfg)
    return cfg, spectra, results


def build_figure(plt, cfg, spectra, results, layout=None, fig=None):
    return Figure(plt, cfg, spectra, results, layout or {}, fig=fig)


def run_group(plt, cfg, spectra, cpath, tag, relayout):
    cfg, spectra, results = prepare_series(cfg, spectra, tag)
    out = Path(cfg["output"])
    out = out if out.is_absolute() else cpath.parent / out
    if tag:
        out = out.with_name(f"{out.stem}_{tag}{out.suffix}")
    cfg["output"] = str(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    write_results(results, out.with_name(out.stem + "_results.csv"), cfg)
    lpath = Path(cfg["layout_file"]) if cfg["layout_file"] else \
        cpath.with_name(cpath.stem + (f"_layout_{tag}" if tag else "_layout") + ".yaml")
    layout = {}
    if lpath.exists() and not relayout:
        layout = yaml.safe_load(lpath.read_text(encoding="utf-8")) or {}
    return build_figure(plt, cfg, spectra, results, layout), lpath


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("config", nargs="?", help="config.yaml oder direkt eine Cary-CSV")
    ap.add_argument("--interactive", "-i", action="store_true")
    ap.add_argument("--relayout", action="store_true")
    ap.add_argument("--demo", metavar="ORDNER")
    args = ap.parse_args()
    if args.demo:
        make_demo(Path(args.demo))
        return
    if not args.config:
        ap.error("config.yaml / CSV")

    import matplotlib
    if not args.interactive:
        matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    cpath = Path(args.config).resolve()
    if cpath.suffix.lower() in (".csv", ".txt"):
        user = {"cary_file": cpath.name, "output": f"{cpath.stem}.pdf"}
    else:
        user = yaml.safe_load(cpath.read_text(encoding="utf-8")) or {}
    base = deep_merge(DEFAULTS, {k: v for k, v in user.items() if k != "groups"})
    base["_base_dir"] = cpath.parent
    setup_fonts(plt, base)

    jobs = []
    if base["cary_file"]:
        cf = Path(base["cary_file"])
        cf = cf if cf.is_absolute() else cpath.parent / cf
        groups, units, missing = load_series(cf, user.get("concentrations"))
        for k in missing:
            log("  " + T("no_conc_in_name", name=k))
        for g, sp in groups.items():
            if base["select"] and g not in base["select"]:
                continue
            gcfg = deep_merge(base, (user.get("groups") or {}).get(g, {}))
            gcfg["_base_dir"] = cpath.parent
            gcfg["conc_unit"] = units[g]
            jobs.append((g if len(groups) > 1 else "", gcfg, sp))
    else:
        sp = []
        for e in base["spectra"]:
            x, y = load_spectrum(e, cpath.parent)
            sp.append({"x": x, "y": y, "c": float(e["conc"]), "color": e.get("color"),
                       "name": Path(e["file"]).name})
        jobs.append(("", base, sp))

    figs = []
    for tag, cfg, sp in jobs:
        F, lpath = run_group(plt, cfg, sp, cpath, tag, args.relayout)
        figs.append((F, lpath))
        if not args.interactive:
            F.export()
    if args.interactive:
        draggers = [Dragger(F, lp) for F, lp in figs]   # noqa: F841
        plt.show()


if __name__ == "__main__":
    main()
