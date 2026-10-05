"""
uvvis_extra.py - Overlay- und Fluoreszenz-Abbildungen.

- TD-DFT-Ausgaben von ORCA (4–6) und Gaussian lesen, Oszillatorstärken zu ε(λ) verbreitern
- Fotopaar (Tageslicht -> UV) mit Pfeil und Anregungswellenlänge als ein Bildelement
- SimpleFigure: Linienplot mit Legende, Labels, Bildern; Layout/Export/Ziehen wie im Hauptplot
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import uvvis_core as core

EV_TO_CM = 8065.544          # 1 eV in cm⁻¹
EPS_CONST = 1.3062974e8      # L mol⁻¹ cm⁻² ; ε(ν̃) = C · Σ f/σ · exp(−((ν̃−ν̃ᵢ)/σ)²), σ in cm⁻¹

TDDFT_EXT = {".out", ".log", ".txt"}


# ----------------------------------------------------------------------------
# TD-DFT
# ----------------------------------------------------------------------------
_G_STATE = re.compile(r"Excited State\s+(\d+):\s+\S+\s+([-\d.]+)\s+eV\s+([-\d.]+)\s+nm\s+f=\s*([-\d.]+)")
_ORCA_HEAD = "ABSORPTION SPECTRUM VIA TRANSITION ELECTRIC DIPOLE MOMENTS"
_FLOAT = re.compile(r"-?\d+\.\d+(?:[eE][-+]?\d+)?")


def parse_tddft(path) -> dict:
    """-> dict(program, E [eV], f). Nimmt jeweils den letzten Block der Datei
    (z. B. nach einer Optimierung erneut berechnete Zustände)."""
    txt = Path(path).read_text(encoding="utf-8", errors="replace")
    # Gaussian
    ms = list(_G_STATE.finditer(txt))
    if ms:
        starts = [i for i, m in enumerate(ms) if m.group(1) == "1"]
        ms = ms[starts[-1]:] if starts else ms
        E = np.array([float(m.group(2)) for m in ms])
        f = np.array([float(m.group(4)) for m in ms])
        return {"program": "Gaussian", "E": E, "f": f}
    # ORCA
    i = txt.rfind(_ORCA_HEAD)
    if i >= 0:
        lines = txt[i:].splitlines()[1:]
        dashes, E, f = 0, [], []
        for ln in lines:
            s = ln.strip()
            if s.startswith("---"):
                dashes += 1
                if dashes >= 3:
                    break
                continue
            if dashes < 2:
                continue                       # Kopfzeilen
            if not s:
                break
            nums = [float(v) for v in _FLOAT.findall(s)]
            if len(nums) < 3:
                continue
            if nums[0] < 50:                   # ORCA 6: eV, cm-1, nm, fosc …
                E.append(nums[0])
                f.append(nums[3])
            else:                              # ORCA 4/5: cm-1, nm, fosc …
                E.append(nums[0] / EV_TO_CM)
                f.append(nums[2])
        if E:
            return {"program": "ORCA", "E": np.array(E), "f": np.array(f)}
    raise ValueError(f"{Path(path).name}: keine TD-DFT-Anregungen gefunden (ORCA/Gaussian)")


def broaden(E_ev, f, fwhm_ev=0.3, shift_ev=0.0, lam=None):
    """Gauß-Verbreiterung in der Energie. -> (λ-Gitter, ε(λ), Stick-λ, Stick-Höhen ε)."""
    if lam is None:
        lam = np.arange(150.0, 1200.01, 0.5)
    sigma_cm = fwhm_ev / (2 * np.sqrt(np.log(2))) * EV_TO_CM
    nu = 1e7 / lam
    nu_i = (np.asarray(E_ev) + shift_ev) * EV_TO_CM
    amp = EPS_CONST * np.asarray(f) / sigma_cm
    eps = (amp[:, None] * np.exp(-((nu[None, :] - nu_i[:, None]) / sigma_cm) ** 2)).sum(0)
    return lam, eps, 1e7 / nu_i, amp


# ----------------------------------------------------------------------------
# Fotopaar mit Pfeil
# ----------------------------------------------------------------------------
def _font(px):
    from matplotlib import font_manager as fm
    for fam in ("Arial", "Liberation Sans", "DejaVu Sans"):
        try:
            path = fm.findfont(fm.FontProperties(family=fam), fallback_to_default=False)
            return ImageFont.truetype(path, px)
        except Exception:
            continue
    return ImageFont.load_default()


def compose_photo_pair(day, uv, text, height=900):
    """Zwei Küvettenfotos nebeneinander, dazwischen Pfeil mit Beschriftung (z. B. '352 nm')."""
    def fit(a):
        im = Image.fromarray(a).convert("RGBA")
        return im.resize((max(1, int(im.width * height / im.height)), height), Image.LANCZOS)
    a, b = fit(day), fit(uv)
    gap = int(0.62 * height)
    W = a.width + gap + b.width
    out = Image.new("RGBA", (W, height), (0, 0, 0, 0))
    out.paste(a, (0, 0), a)
    out.paste(b, (a.width + gap, 0), b)
    d = ImageDraw.Draw(out)
    y = int(height * 0.58)
    x0, x1 = a.width + int(0.12 * gap), a.width + int(0.88 * gap)
    lw = max(2, height // 220)
    head = int(height * 0.035)
    d.line([(x0, y), (x1 - head, y)], fill=(0, 0, 0, 255), width=lw)
    d.polygon([(x1, y), (x1 - head, y - head // 2), (x1 - head, y + head // 2)], fill=(0, 0, 0, 255))
    if text:
        fnt = _font(int(height * 0.075))
        tb = d.textbbox((0, 0), text, font=fnt)
        d.text(((x0 + x1) / 2 - (tb[2] - tb[0]) / 2, y - (tb[3] - tb[1]) - int(height * 0.04)),
               text, font=fnt, fill=(0, 0, 0, 255))
    return np.asarray(out)


# ----------------------------------------------------------------------------
# Abbildung
# ----------------------------------------------------------------------------
class SimpleFigure(core.Figure):
    """Mehrere Kurven + Legende + verankerte Labels + Bilder.
    curves: [dict(x, y, color, label, ls, lw)], sticks: [dict(x, h, color)],
    labels: [dict(key, text, lam)]."""

    def __init__(self, plt, cfg, curves, labels, layout, fig=None, sticks=None, legend=True):
        self.plt, self.cfg, self.layout = plt, cfg, layout or {}
        self.results = []
        self.curves = curves
        self.spectra = [c for c in curves if len(c["x"])]
        if fig is None:
            fig = plt.figure(figsize=cfg["figsize_in"])
        else:
            fig.clear()
            fig.set_size_inches(cfg["figsize_in"], forward=False)
        self.fig = fig
        self.ax = fig.add_axes(cfg["axes_rect"])
        self.axes_items, self.tight_off, self.ann_items = {}, {}, {}
        self._inset_table = None
        self.legend = None
        self._plot(sticks or [])
        self._fit_axes(0.01 if cfg.get("size_cm") else 0.06)
        if legend:
            self._legend()
        self._make_labels(labels or [])
        self._images()
        self._place()

    def _plot(self, sticks):
        cfg, ax = self.cfg, self.ax
        xs = np.concatenate([c["x"] for c in self.curves]) if self.curves else np.array([200.0, 800.0])
        xlim = cfg["xlim"] or (float(np.nanmin(xs)), float(np.nanmax(xs)))
        ylim = cfg["ylim"] or (0, 1.1)
        for c in self.curves:
            cx, cy = core.clip_polyline(c["x"], c["y"], xlim, ylim)
            ax.plot(cx, cy, color=c.get("color") or "black", lw=c.get("lw", cfg["line_width"] * 1.3),
                    ls=c.get("ls", "-"), label=c.get("label"), solid_joinstyle="round")
        for st in sticks:
            sel = (st["x"] >= min(xlim)) & (st["x"] <= max(xlim))
            if sel.any():
                ax.vlines(st["x"][sel], ylim[0], np.minimum(st["h"][sel], ylim[1]),
                          color=st.get("color", "gray"), lw=max(0.6, cfg["line_width"]), alpha=0.8)
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

    def _legend(self):
        handles = [h for h in self.ax.get_lines() if h.get_label() and not h.get_label().startswith("_")]
        if not handles:
            return
        loc = self.layout.get("legend")
        self.legend = self.ax.legend(handles=handles, loc=tuple(loc) if loc else "best",
                                     fontsize=self.cfg["font_size"] * 0.8, frameon=False,
                                     handlelength=1.8)
        self.legend.set_draggable(True, update="loc")

    def _make_labels(self, labels):
        for lab in labels:
            ann = self.ax.annotate(lab["text"], xy=(lab["lam"], 0), xycoords="data",
                                   xytext=(0.5, 0.5), textcoords="axes fraction", ha="left",
                                   va="bottom", fontsize=self.cfg["labels"]["font_size"],
                                   linespacing=1.4, annotation_clip=False, zorder=5)
            self.ann_items[lab["key"]] = ann

    def current_layout(self):
        out = super().current_layout()
        if self.legend is not None and isinstance(self.legend._loc, tuple):
            out["legend"] = [round(float(v), 4) for v in self.legend._loc]
        elif "legend" in self.layout:
            out["legend"] = self.layout["legend"]
        return out


def normalize(x, y, lo, hi, min_signal=0.01):
    """Auf das Maximum im Fenster [lo, hi] normieren (Bande von Interesse).
    None, wenn dort kein Signal ist (Normieren von Rauschen wäre sinnlos)."""
    sel = (x >= min(lo, hi)) & (x <= max(lo, hi)) & np.isfinite(y)
    m = np.nanmax(y[sel]) if sel.any() else np.nan
    if not np.isfinite(m) or m <= 0:
        return None
    noise = np.nanmax(np.abs(y[np.isfinite(y)])) if np.isfinite(y).any() else 0
    if m < min_signal * noise and m < 0.005:
        return None
    return y / m


def peak_in(x, y, lo, hi):
    sel = (x >= min(lo, hi)) & (x <= max(lo, hi)) & np.isfinite(y)
    if not sel.any():
        return None
    return float(x[sel][np.nanargmax(y[sel])])
