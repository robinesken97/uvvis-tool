"""
uvvis_tabs.py - Zusätzliche Tabs der GUI: Overlay (Messung + TD-DFT) und Fluoreszenz.
"""
from __future__ import annotations

import copy
import traceback
import uuid
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import yaml
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure as MplFigure
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QColorDialog, QComboBox,
                               QDoubleSpinBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout,
                               QHeaderView, QLabel, QLineEdit, QPushButton, QScrollArea,
                               QSplitter, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

import uvvis_core as core
import uvvis_extra as X
import uvvis_images as IMG
import uvvis_project as PRJ
from uvvis_i18n import T

PREVIEW_DPI = 90
PALETTE = ["#000000", "#e8231b", "#1764e8", "#1f9e4a", "#a35ce0", "#e08a00", "#00a0b0", "#8c564b"]
UNITS = [("mM", "mM"), ("uM", "µM"), ("mg/mL", "mg/mL"), ("M", "M")]


def parse_num(txt):
    txt = (txt or "").strip().replace(",", ".")
    if not txt:
        return None
    try:
        v = float(txt)
        return v if v > 0 else None
    except ValueError:
        return None


def color_button(color, on_pick):
    b = QPushButton()
    b.setFixedSize(44, 22)
    b.setStyleSheet(f"background-color: {color}; border: 1px solid #777;")

    def pick():
        c = QColorDialog.getColor(QColor(b.property("color") or color))
        if c.isValid():
            b.setProperty("color", c.name())
            b.setStyleSheet(f"background-color: {c.name()}; border: 1px solid #777;")
            on_pick(c.name())
    b.setProperty("color", color)
    b.clicked.connect(pick)
    return b


class TabDragger(core.Dragger):
    def __init__(self, F, cb):
        self.cb = cb
        super().__init__(F, None)

    def _report(self):
        QTimer.singleShot(0, lambda: self.cb(self.F.current_layout()))

    def release(self, ev):
        super().release(ev)
        self._report()

    def scroll(self, ev):
        if super().scroll(ev):
            self._report()

    def key(self, ev):
        pass


# ----------------------------------------------------------------------------
class FigureTab(QWidget):
    """Gemeinsame Basis: Vorschau, Größe/Formate, Ziehen, Export, Speichern/Laden."""

    DEFAULT_STATE: dict = {}
    STATE_KEY = ""

    def __init__(self, main, state):
        super().__init__()
        self.main = main
        self.st = state
        for k, v in self.DEFAULT_STATE.items():
            self.st.setdefault(k, copy.deepcopy(v))
        self.F = None
        self.dragger = None
        self._loading = False
        self.timer = QTimer(self, singleShot=True, interval=350)
        self.timer.timeout.connect(self.render)
        self.fig = MplFigure(figsize=(8, 6), dpi=PREVIEW_DPI)
        self.canvas = FigureCanvasQTAgg(self.fig)
        left = QWidget()
        self.lv = QVBoxLayout(left)
        self.build_controls()
        self.lv.addWidget(self.common_box())
        row = QHBoxLayout()
        for txt, fn in ((T("tab_save"), self.save_setup), (T("tab_load"), self.load_setup),
                        (T("btn_reset_layout"), self.reset_layout)):
            b = QPushButton(txt)
            b.clicked.connect(fn)
            row.addWidget(b)
        self.lv.addLayout(row)
        b = QPushButton(T("btn_export"))
        b.setDefault(True)
        b.clicked.connect(self.export_dialog)
        self.lv.addWidget(b)
        hint = QLabel(T("drag_hint_tab"))
        hint.setWordWrap(True)
        hint.setStyleSheet("color: gray;")
        self.lv.addWidget(hint)
        self.lv.addStretch(1)
        ls = QScrollArea()
        ls.setWidget(left)
        ls.setWidgetResizable(True)
        ls.setMinimumWidth(480)
        cs = QScrollArea()
        holder = QWidget()
        hl = QHBoxLayout(holder)
        hl.addWidget(self.canvas, 0, Qt.AlignCenter)
        cs.setWidget(holder)
        cs.setWidgetResizable(True)
        split = QSplitter(Qt.Horizontal)
        split.addWidget(ls)
        split.addWidget(cs)
        split.setSizes([420, 900])
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(split)
        QTimer.singleShot(0, self.render)

    # -- Bausteine ------------------------------------------------------------
    def build_controls(self):
        raise NotImplementedError

    def common_box(self):
        g = QGroupBox(T("grp_plot"))
        f = QFormLayout(g)
        st = self.st
        row = QHBoxLayout()
        self.cb_xauto = QCheckBox(T("xrange_auto"))
        self.cb_xauto.setChecked(st["x_auto"])
        self.sp_xmin = QDoubleSpinBox(decimals=0, minimum=100, maximum=3500, singleStep=10, value=st["x_min"])
        self.sp_xmax = QDoubleSpinBox(decimals=0, minimum=100, maximum=3500, singleStep=10, value=st["x_max"])
        for w in (self.cb_xauto, self.sp_xmin, QLabel("–"), self.sp_xmax):
            row.addWidget(w)
        f.addRow(T("xrange"), row)
        self.sp_ymax = QDoubleSpinBox(decimals=2, minimum=0, maximum=1e6, singleStep=0.1, value=st["ymax"])
        self.sp_ymax.setSpecialValueText(T("auto"))
        f.addRow(T("ymax"), self.sp_ymax)
        self.cmb_size = QComboBox()
        for key in ("half_a4", "custom", "std"):
            self.cmb_size.addItem(T({"half_a4": "size_half_a4", "custom": "size_custom", "std": "size_std"}[key]), key)
        self.cmb_size.setCurrentIndex(self.cmb_size.findData(st["size"]))
        f.addRow(T("size"), self.cmb_size)
        row = QHBoxLayout()
        self.sp_w = QDoubleSpinBox(decimals=1, minimum=4, maximum=40, singleStep=0.5, suffix=" cm", value=st["w_cm"])
        self.sp_h = QDoubleSpinBox(decimals=1, minimum=3, maximum=40, singleStep=0.5, suffix=" cm", value=st["h_cm"])
        row.addWidget(self.sp_w)
        row.addWidget(QLabel("×"))
        row.addWidget(self.sp_h)
        f.addRow(T("size_wh"), row)
        row = QHBoxLayout()
        self.cb_fmt = {}
        for e in ("pdf", "svg", "png"):
            cb = QCheckBox(e.upper())
            cb.setChecked(st["fmt"].get(e, True))
            self.cb_fmt[e] = cb
            row.addWidget(cb)
        row.addStretch(1)
        f.addRow(T("formats"), row)
        for w in (self.sp_xmin, self.sp_xmax, self.sp_ymax, self.sp_w, self.sp_h):
            w.valueChanged.connect(self.changed)
        self.cb_xauto.toggled.connect(self.changed)
        self.cmb_size.currentIndexChanged.connect(self.changed)
        for cb in self.cb_fmt.values():
            cb.toggled.connect(self.changed)
        self._sync_common()
        return g

    def size_spin(self, form, key, layout_key, lo=3.0, hi=90.0):
        """Größenfeld (% der Plotbreite) für ein Bild; Mausrad im Plot hält es aktuell."""
        sp = QDoubleSpinBox(decimals=1, minimum=lo, maximum=hi, singleStep=1, suffix=" %",
                            value=self.st.get(key, 20.0))
        self._size_spins = getattr(self, "_size_spins", {})
        self._size_spins[layout_key] = (sp, key)

        def changed(v):
            if self._loading:
                return
            self.st[key] = v
            lay = self.layout()
            if layout_key in lay and len(lay[layout_key]) == 4:
                x, y, w, h = lay[layout_key]
                nw = v / 100
                nh = h * nw / w
                lay[layout_key] = [min(max(x + (w - nw) / 2, 0), max(0, 1 - nw)),
                                   min(max(y + (h - nh) / 2, 0), max(0, 1 - nh)), nw, nh]
            self.timer.start()
        sp.valueChanged.connect(changed)
        form.addRow(T("img_size"), sp)
        return sp

    def sync_sizes(self, layout):
        for lk, (sp, key) in getattr(self, "_size_spins", {}).items():
            if lk in layout and len(layout[lk]) == 4:
                self.st[key] = round(layout[lk][2] * 100, 1)
                sp.blockSignals(True)
                sp.setValue(self.st[key])
                sp.blockSignals(False)

    def _sync_common(self):
        auto = self.cb_xauto.isChecked()
        self.sp_xmin.setEnabled(not auto)
        self.sp_xmax.setEnabled(not auto)
        if self.cmb_size.currentData() == "half_a4":
            for sp, v in ((self.sp_w, 16.0), (self.sp_h, 11.0)):
                sp.blockSignals(True)
                sp.setValue(v)
                sp.blockSignals(False)
        custom = self.cmb_size.currentData() == "custom"
        self.sp_w.setEnabled(custom)
        self.sp_h.setEnabled(custom)

    def collect_common(self):
        st = self.st
        st.update(x_auto=self.cb_xauto.isChecked(), x_min=self.sp_xmin.value(), x_max=self.sp_xmax.value(),
                  ymax=self.sp_ymax.value(), size=self.cmb_size.currentData(), w_cm=self.sp_w.value(),
                  h_cm=self.sp_h.value(), fmt={e: cb.isChecked() for e, cb in self.cb_fmt.items()})

    def changed(self, *_):
        if self._loading:
            return
        self.collect_common()
        self._sync_common()
        self.collect()
        self.timer.start()

    def collect(self):
        pass

    # -- Daten-Cache (im Hauptfenster, übersteht Sprachwechsel) ------------------
    def cache(self, key, fn):
        c = self.main.extra_cache
        if key not in c:
            c[key] = fn()
        return c[key]

    def samples(self, path):
        return self.cache(("samples", path), lambda: core.read_samples([path]))

    def sample(self, path, key):
        for s_ in self.samples(path):
            if s_["key"] == key:
                return s_
        return None

    def structure_asset(self, path, color=None):
        return self.cache(("struct", path, color), lambda: IMG.load_structure(path, color=color))

    def photo_asset(self, path, method):
        if method in ("auto", "isnet") and not self.main.ensure_model():
            method = "grabcut" if method == "isnet" else "auto"
        cdir = Path(path).parent / ".uvvis_cache"
        return self.cache(("photo", path, method), lambda: IMG.load_photo(path, method, cdir))

    # -- Abbildung ----------------------------------------------------------------
    def base_cfg(self):
        st = self.st
        cfg = core.deep_merge(core.DEFAULTS, {})
        cfg["_base_dir"] = Path.home()
        if st["size"] != "std":
            core.apply_export_size(cfg, st["w_cm"], st["h_cm"])
        fmts = [e for e in ("pdf", "svg", "png") if st["fmt"].get(e)] or ["pdf"]
        cfg["_main_fmt"], cfg["extra_formats"] = fmts[0], fmts[1:]
        return cfg

    def size_key(self):
        return "std" if self.st["size"] == "std" else f"{self.st['w_cm']:g}x{self.st['h_cm']:g}"

    def layout(self):
        return self.st["layout"].setdefault(self.size_key(), {})

    def figure_spec(self):
        """-> (cfg, curves, labels, sticks) oder None."""
        raise NotImplementedError

    def build(self, fig):
        quiet = core.LOG
        core.LOG = IMG.LOG = lambda *a: None      # Basislinien-Meldungen nicht bei jedem Neuzeichnen
        try:
            spec = self.figure_spec()
        finally:
            core.LOG = IMG.LOG = quiet
        if spec is None:
            return None
        cfg, curves, labels, sticks = spec
        core.setup_fonts(plt, cfg)
        return X.SimpleFigure(plt, cfg, curves, labels, self.layout(), fig=fig, sticks=sticks)

    def render(self):
        try:
            if self.dragger:
                self.dragger.disconnect()
                self.dragger = None
            spec_cfg = self.base_cfg()
            w, h = (int(v * PREVIEW_DPI) for v in spec_cfg["figsize_in"])
            if (self.canvas.width(), self.canvas.height()) != (w, h):
                self.canvas.setFixedSize(w, h)
            self.F = self.build(self.fig)
            if self.F is None:
                self.fig.clear()
                self.fig.text(0.5, 0.5, T("tab_empty"), ha="center", va="center", color="gray")
            else:
                self.dragger = TabDragger(self.F, self.layout_changed)
                self.sync_sizes(self.F.current_layout())
            self.canvas.draw_idle()
            self.main.push_undo()
        except Exception as e:
            self.main.log_signal.emit(traceback.format_exc())
            self.main.statusBar().showMessage(f"{T('err_title')}: {e}", 8000)

    def layout_changed(self, layout):
        self.st["layout"][self.size_key()] = layout
        self.sync_sizes(layout)
        self.main.push_undo()

    def reset_layout(self):
        self.st["layout"][self.size_key()] = {}
        self.render()

    def export_dialog(self):
        """Direkt ins Projekt: exports/<overlay|fluorescence>/<Projekt>_<Tab>.* (wird überschrieben)."""
        if not self.main.ensure_project():
            return
        pdir = Path(self.main.project_dir)
        base = PRJ.export_dir(pdir, self.STATE_KEY) / f"{pdir.name}_{self.STATE_KEY}"
        try:
            out = self.export_to(base)
        except Exception as e:
            return self.main.error(str(e))
        self.main.info(T("exported_to", p=str(base.parent)))
        return out

    def export_to(self, base: Path):
        base = Path(base).resolve()
        fig = MplFigure(figsize=(8, 6), dpi=PREVIEW_DPI)
        FigureCanvasAgg(fig)
        F = self.build(fig)
        if F is None:
            raise RuntimeError(T("tab_empty"))
        F.cfg["output"] = str(base.with_suffix("." + F.cfg["_main_fmt"]))
        F.cfg["_base_dir"] = base.parent
        F.export()
        return [base.with_suffix("." + e) for e in [F.cfg["_main_fmt"]] + F.cfg["extra_formats"]]

    def save_setup(self):
        p, _ = QFileDialog.getSaveFileName(self, T("tab_save"), self.STATE_KEY + ".yaml", "YAML (*.yaml)")
        if p:
            Path(p).write_text(yaml.safe_dump(self.st, allow_unicode=True, sort_keys=False), encoding="utf-8")

    def load_setup(self):
        p, _ = QFileDialog.getOpenFileName(self, T("tab_load"), "", "YAML (*.yaml)")
        if p:
            data = yaml.safe_load(Path(p).read_text(encoding="utf-8")) or {}
            self.st.clear()
            self.st.update(copy.deepcopy(self.DEFAULT_STATE))
            self.st.update(data)
            self.main.rebuild_tabs()


COMMON_DEFAULTS = {"x_auto": True, "x_min": 200.0, "x_max": 800.0, "size": "half_a4", "w_cm": 16.0,
                   "h_cm": 11.0, "fmt": {"pdf": True, "svg": True, "png": True}, "layout": {}}


# ----------------------------------------------------------------------------
class OverlayTab(FigureTab):
    STATE_KEY = "overlay"
    DEFAULT_STATE = dict(COMMON_DEFAULTS, entries=[], mode="norm", nlo=300.0, nhi=500.0, ymax=0.0,
                         baseline=True, sticks=True, stick_mode="band", structure=None, struct_w=20.0)

    def build_controls(self):
        st = self.st
        g = QGroupBox(T("ov_curves"))
        v = QVBoxLayout(g)
        row = QHBoxLayout()
        for txt, fn in ((T("ov_add_exp"), self.add_exp), (T("ov_add_calc"), self.add_calc),
                        ("↑", lambda: self.move_selected(-1)), ("↓", lambda: self.move_selected(1)),
                        (T("remove"), self.remove_selected)):
            b = QPushButton(txt)
            b.clicked.connect(fn)
            row.addWidget(b)
        v.addLayout(row)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["", T("ov_name"), T("ov_color"), T("ov_type")])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setMinimumHeight(150)
        self.table.itemChanged.connect(self.table_edited)
        self.table.itemSelectionChanged.connect(self.show_details)
        v.addWidget(self.table)
        lay = self.lv
        lay.addWidget(g)

        # Details der gewählten Kurve
        self.det = QGroupBox(T("ov_details"))
        f = QFormLayout(self.det)
        self.cb_own = QCheckBox(T("ov_own_norm"))
        row = QHBoxLayout()
        self.sp_elo = QDoubleSpinBox(decimals=0, minimum=100, maximum=3500, value=300)
        self.sp_ehi = QDoubleSpinBox(decimals=0, minimum=100, maximum=3500, value=500)
        for w in (self.cb_own, self.sp_elo, QLabel("–"), self.sp_ehi):
            row.addWidget(w)
        f.addRow(T("ov_norm_window"), row)
        self.ed_conc = QLineEdit()
        self.cmb_unit = QComboBox()
        for key, label in UNITS:
            self.cmb_unit.addItem(label, key)
        row = QHBoxLayout()
        row.addWidget(self.ed_conc, 1)
        row.addWidget(self.cmb_unit)
        self.lbl_conc = QLabel(T("col_conc"))
        f.addRow(self.lbl_conc, row)
        self.ed_mw = QLineEdit()
        self.lbl_mw = QLabel(T("molar_mass"))
        f.addRow(self.lbl_mw, self.ed_mw)
        self.sp_d = QDoubleSpinBox(decimals=3, minimum=0.001, maximum=100, value=1.0, singleStep=0.1)
        self.lbl_d = QLabel(T("path_length"))
        f.addRow(self.lbl_d, self.sp_d)
        self.sp_fwhm = QDoubleSpinBox(decimals=2, minimum=0.02, maximum=3, singleStep=0.05, value=0.3, suffix=" eV")
        self.lbl_fwhm = QLabel(T("ov_fwhm"))
        f.addRow(self.lbl_fwhm, self.sp_fwhm)
        self.sp_shift = QDoubleSpinBox(decimals=2, minimum=-3, maximum=3, singleStep=0.05, value=0.0, suffix=" eV")
        self.lbl_shift = QLabel(T("ov_shift"))
        f.addRow(self.lbl_shift, self.sp_shift)
        self.cmb_soc = QComboBox()
        self.lbl_soc = QLabel(T("ov_soc"))
        f.addRow(self.lbl_soc, self.cmb_soc)
        row = QHBoxLayout()
        self.sp_scale = QDoubleSpinBox(decimals=3, minimum=0.001, maximum=1000, singleStep=0.05, value=1.0)
        self.sp_offset = QDoubleSpinBox(decimals=3, minimum=-1000, maximum=1000, singleStep=0.05, value=0.0)
        row.addWidget(QLabel("×"))
        row.addWidget(self.sp_scale)
        row.addWidget(QLabel("+"))
        row.addWidget(self.sp_offset)
        f.addRow(T("ov_scale_offset"), row)
        row = QHBoxLayout()
        self.cmb_ls = QComboBox()
        for key in ("solid", "dashed", "dotted", "dashdot"):
            self.cmb_ls.addItem(T("ls_" + key), key)
        self.sp_lw = QDoubleSpinBox(decimals=1, minimum=0.0, maximum=6, singleStep=0.25, value=0.0, suffix=" pt")
        self.sp_lw.setSpecialValueText(T("auto"))
        row.addWidget(self.cmb_ls, 1)
        row.addWidget(self.sp_lw)
        f.addRow(T("ov_line"), row)
        row = QHBoxLayout()
        self.lbl_estruct = QLabel("–")
        b1, b2 = QPushButton(T("choose")), QPushButton(T("remove"))
        b1.clicked.connect(self.choose_entry_structure)
        b2.clicked.connect(lambda: self.set_entry_structure(None))
        row.addWidget(self.lbl_estruct, 1)
        row.addWidget(b1)
        row.addWidget(b2)
        f.addRow(T("structure"), row)
        self.cb_ecolor = QCheckBox(T("ov_struct_color"))
        self.cb_ecolor.toggled.connect(self.detail_changed)
        f.addRow(self.cb_ecolor)
        for w in (self.sp_elo, self.sp_ehi, self.sp_d, self.sp_fwhm, self.sp_shift, self.sp_scale,
                  self.sp_offset, self.sp_lw):
            w.valueChanged.connect(self.detail_changed)
        self.cmb_ls.currentIndexChanged.connect(self.detail_changed)
        self.cmb_soc.currentIndexChanged.connect(self.detail_changed)
        self.cb_own.toggled.connect(self.detail_changed)
        self.cmb_unit.currentIndexChanged.connect(self.detail_changed)
        self.ed_conc.editingFinished.connect(self.detail_changed)
        self.ed_mw.editingFinished.connect(self.detail_changed)
        lay.addWidget(self.det)

        g = QGroupBox(T("ov_display"))
        f = QFormLayout(g)
        self.cmb_mode = QComboBox()
        self.cmb_mode.addItem(T("ov_mode_norm"), "norm")
        self.cmb_mode.addItem(T("ov_mode_eps"), "eps")
        self.cmb_mode.setCurrentIndex(self.cmb_mode.findData(st["mode"]))
        f.addRow(T("ov_mode"), self.cmb_mode)
        row = QHBoxLayout()
        self.sp_nlo = QDoubleSpinBox(decimals=0, minimum=100, maximum=3500, value=st["nlo"])
        self.sp_nhi = QDoubleSpinBox(decimals=0, minimum=100, maximum=3500, value=st["nhi"])
        for w in (self.sp_nlo, QLabel("–"), self.sp_nhi):
            row.addWidget(w)
        f.addRow(T("ov_norm_window"), row)
        self.cb_base = QCheckBox(T("ov_baseline"))
        self.cb_base.setChecked(st["baseline"])
        self.cb_sticks = QCheckBox(T("ov_sticks"))
        self.cb_sticks.setChecked(st["sticks"])
        f.addRow(self.cb_base)
        f.addRow(self.cb_sticks)
        self.cmb_stick = QComboBox()
        for key in ("band", "max", "faxis"):
            self.cmb_stick.addItem(T("stick_" + key), key)
        self.cmb_stick.setCurrentIndex(max(0, self.cmb_stick.findData(st.get("stick_mode", "band"))))
        f.addRow(T("stick_mode"), self.cmb_stick)
        self.cmb_stick.currentIndexChanged.connect(self.changed)
        row = QHBoxLayout()
        self.lbl_struct = QLabel(Path(st["structure"]).name if st["structure"] else "–")
        b1 = QPushButton(T("choose"))
        b1.clicked.connect(self.choose_structure)
        b2 = QPushButton(T("remove"))
        b2.clicked.connect(lambda: self.set_structure(None))
        row.addWidget(self.lbl_struct, 1)
        row.addWidget(b1)
        row.addWidget(b2)
        f.addRow(T("structure"), row)
        self.sp_struct_w = self.size_spin(f, "struct_w", "image_struktur")
        self.cmb_mode.currentIndexChanged.connect(self.changed)
        for w in (self.sp_nlo, self.sp_nhi):
            w.valueChanged.connect(self.changed)
        for w in (self.cb_base, self.cb_sticks):
            w.toggled.connect(self.changed)
        lay.addWidget(g)
        self.fill_table()
        self.show_details()

    # -- Kurvenliste ------------------------------------------------------------
    def next_color(self):
        used = {e["color"] for e in self.st["entries"]}
        for c in PALETTE:
            if c not in used:
                return c
        return PALETTE[len(self.st["entries"]) % len(PALETTE)]

    def add_exp(self):
        if not self.main.ensure_project():
            return
        ps, _ = QFileDialog.getOpenFileNames(self, T("ov_add_exp"), self.main.settings.value("last_dir", ""),
                                             f"{T('flt_csv')};;{T('flt_all')}")
        for p in ps:
            try:
                p = self.main.import_file(p, "data")
                for s_ in self.samples(p):
                    self.st["entries"].append({
                        "kind": "exp", "file": p, "sample": s_["key"], "label": s_["name"],
                        "color": self.next_color(), "visible": True, "own_norm": False,
                        "nlo": self.st["nlo"], "nhi": self.st["nhi"], "conc": None, "unit": "mM",
                        "mw": None, "d": 1.0})
            except Exception as e:
                self.main.error(f"{Path(p).name}: {e}")
        self.fill_table()
        self.timer.start()

    def add_calc(self):
        if not self.main.ensure_project():
            return
        ps, _ = QFileDialog.getOpenFileNames(self, T("ov_add_calc"), self.main.settings.value("last_dir", ""),
                                             "ORCA / Gaussian (*.out *.log *.txt);;" + T("flt_all"))
        for p in ps:
            try:
                p = self.main.import_file(p, "data")
                r = self.cache(("tddft", p), lambda p=p: X.parse_tddft(p))
                self.main.log_signal.emit(f"  {Path(p).name}: {r['program']}, {len(r['E'])} {T('ov_states')}")
                self.st["entries"].append({
                    "kind": "calc", "file": p, "label": f"{Path(p).stem} (TD-DFT)", "color": self.next_color(),
                    "visible": True, "own_norm": False, "nlo": self.st["nlo"], "nhi": self.st["nhi"],
                    "fwhm": 0.3, "shift": 0.0})
            except Exception as e:
                self.main.error(str(e))
        self.fill_table()
        self.timer.start()

    def move_selected(self, d):
        r = self.table.currentRow()
        ents = self.st["entries"]
        if 0 <= r < len(ents) and 0 <= r + d < len(ents):
            ents[r], ents[r + d] = ents[r + d], ents[r]
            self.fill_table()
            self.table.selectRow(r + d)
            self.timer.start()

    def remove_selected(self):
        r = self.table.currentRow()
        if 0 <= r < len(self.st["entries"]):
            del self.st["entries"][r]
            self.fill_table()
            self.timer.start()

    def fill_table(self):
        for e in self.st["entries"]:
            e.setdefault("uid", uuid.uuid4().hex[:8])     # stabiler Schlüssel fürs Layout (Reihenfolge änderbar)
        self._loading = True
        self.table.setRowCount(len(self.st["entries"]))
        for i, e in enumerate(self.st["entries"]):
            it = QTableWidgetItem()
            it.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            it.setCheckState(Qt.Checked if e["visible"] else Qt.Unchecked)
            self.table.setItem(i, 0, it)
            self.table.setItem(i, 1, QTableWidgetItem(e["label"]))
            self.table.setCellWidget(i, 2, color_button(e["color"], lambda c, e=e: self._set_color(e, c)))
            it = QTableWidgetItem(T("ov_exp") if e["kind"] == "exp" else "TD-DFT")
            it.setFlags(it.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(i, 3, it)
        self.table.resizeColumnToContents(0)
        self._loading = False

    def _set_color(self, e, c):
        e["color"] = c
        self.timer.start()

    def table_edited(self, item):
        if self._loading:
            return
        e = self.st["entries"][item.row()]
        if item.column() == 0:
            e["visible"] = item.checkState() == Qt.Checked
        elif item.column() == 1:
            e["label"] = item.text()
        self.timer.start()

    def current_entry(self):
        r = self.table.currentRow()
        return self.st["entries"][r] if 0 <= r < len(self.st["entries"]) else None

    def show_details(self):
        e = self.current_entry()
        self.det.setEnabled(e is not None)
        self._loading = True
        exp = e is not None and e["kind"] == "exp"
        for w in (self.lbl_conc, self.ed_conc, self.cmb_unit, self.lbl_mw, self.ed_mw, self.lbl_d, self.sp_d):
            w.setVisible(exp or e is None)
        for w in (self.lbl_fwhm, self.sp_fwhm, self.lbl_shift, self.sp_shift, self.lbl_soc, self.cmb_soc):
            w.setVisible(e is not None and not exp)
        if e:
            self.lbl_estruct.setText(Path(e["structure"]).name if e.get("structure") else "–")
            self.cb_ecolor.setChecked(e.get("struct_color", True))
            self.sp_scale.setValue(e.get("scale", 1.0))
            self.sp_offset.setValue(e.get("offset", 0.0))
            self.cmb_ls.setCurrentIndex(max(0, self.cmb_ls.findData(
                e.get("ls", "dashed" if e["kind"] == "calc" else "solid"))))
            self.sp_lw.setValue(e.get("lw") or 0.0)
            self.cb_own.setChecked(e["own_norm"])
            self.sp_elo.setValue(e["nlo"])
            self.sp_ehi.setValue(e["nhi"])
            if exp:
                self.ed_conc.setText(f"{e['conc']:g}" if e.get("conc") else "")
                self.cmb_unit.setCurrentIndex(max(0, self.cmb_unit.findData(e.get("unit", "mM"))))
                self.ed_mw.setText(f"{e['mw']:g}" if e.get("mw") else "")
                self.sp_d.setValue(e.get("d", 1.0))
            else:
                self.sp_fwhm.setValue(e.get("fwhm", 0.3))
                self.sp_shift.setValue(e.get("shift", 0.0))
                self.cmb_soc.clear()
                try:
                    variants = self.cache(("tdv", e["file"]), lambda: X.tddft_variants(e["file"]))
                except Exception:
                    variants = []
                for v in variants or ["nosoc"]:
                    self.cmb_soc.addItem(T("soc_" + v), v)
                cur = e.get("variant") or (variants[0] if variants else "nosoc")
                self.cmb_soc.setCurrentIndex(max(0, self.cmb_soc.findData(cur)))
                self.cmb_soc.setEnabled(len(variants) > 1)
        self._loading = False

    def detail_changed(self, *_):
        e = self.current_entry()
        if self._loading or e is None:
            return
        e.update(struct_color=self.cb_ecolor.isChecked())
        e.update(own_norm=self.cb_own.isChecked(), nlo=self.sp_elo.value(), nhi=self.sp_ehi.value(),
                 scale=self.sp_scale.value(), offset=self.sp_offset.value(),
                 ls=self.cmb_ls.currentData(), lw=self.sp_lw.value() or None)
        if e["kind"] == "exp":
            e.update(conc=parse_num(self.ed_conc.text()), unit=self.cmb_unit.currentData(),
                     mw=parse_num(self.ed_mw.text()), d=self.sp_d.value())
        else:
            e.update(fwhm=self.sp_fwhm.value(), shift=self.sp_shift.value())
            if self.cmb_soc.currentData():
                e["variant"] = self.cmb_soc.currentData()
        self.timer.start()

    def collect(self):
        self.st.update(mode=self.cmb_mode.currentData(), nlo=self.sp_nlo.value(), nhi=self.sp_nhi.value(),
                       baseline=self.cb_base.isChecked(), sticks=self.cb_sticks.isChecked(),
                       stick_mode=self.cmb_stick.currentData())

    def choose_entry_structure(self):
        e = self.current_entry()
        if e is None or not self.main.ensure_project():
            return
        p, _ = QFileDialog.getOpenFileName(self, T("dlg_structure"), self.main.settings.value("last_img_dir", ""),
                                           f"{T('flt_struct')};;{T('flt_all')}")
        if p:
            self.main.settings.setValue("last_img_dir", str(Path(p).parent))
            self.set_entry_structure(self.main.import_file(p, "images"))

    def set_entry_structure(self, p):
        e = self.current_entry()
        if e is None:
            return
        e["structure"] = p
        self.lbl_estruct.setText(Path(p).name if p else "–")
        self.timer.start()

    def choose_structure(self):
        if not self.main.ensure_project():
            return
        p, _ = QFileDialog.getOpenFileName(self, T("dlg_structure"), self.main.settings.value("last_img_dir", ""),
                                           f"{T('flt_struct')};;{T('flt_all')}")
        if p:
            self.set_structure(self.main.import_file(p, "images"))

    def set_structure(self, p):
        self.st["structure"] = p
        self.lbl_struct.setText(Path(p).name if p else "–")
        self.timer.start()

    # -- Abbildung --------------------------------------------------------------
    LS = {"solid": "-", "dashed": "--", "dotted": ":", "dashdot": "-."}

    def figure_spec(self):
        st = self.st
        vis = [e for e in st["entries"] if e["visible"]]
        if not vis:
            return None
        cfg = self.base_cfg()
        eps_mode = st["mode"] == "eps"
        mode = st.get("stick_mode", "max")
        curves, sticks, exp_x = [], [], []
        for e in vis:
            lo, hi = (e["nlo"], e["nhi"]) if e["own_norm"] else (st["nlo"], st["nhi"])
            sc, off = e.get("scale", 1.0), e.get("offset", 0.0)
            ls = self.LS.get(e.get("ls") or ("dashed" if e["kind"] == "calc" else "solid"), "-")
            if e["kind"] == "exp":
                s_ = self.sample(e["file"], e["sample"])
                if s_ is None:
                    continue
                x, y = s_["x"].copy(), s_["y"].copy()
                if st["baseline"]:
                    tmp = [{"x": x, "y": y, "c": 1.0}]
                    bcfg = dict(cfg, baseline_nm="auto", baseline_mode="simple", conc_unit="mM")
                    core.apply_baseline(tmp, bcfg)
                    y = tmp[0]["y"]
                if eps_mode:
                    fac = (1 / e["mw"] if e.get("mw") else None) if e.get("unit") == "mg/mL" \
                        else core.CONC_TO_M.get(e.get("unit", "mM"))
                    if not (e.get("conc") and fac):
                        self.main.log_signal.emit("  " + T("ov_need_conc", name=e["label"]))
                        continue
                    y = y / (e["conc"] * fac * e.get("d", 1.0)) / 1000.0
                else:
                    y = X.normalize(x, y, lo, hi)
                    if y is None:
                        self.main.log_signal.emit("  " + T("ov_no_signal", name=e["label"], lo=lo, hi=hi))
                        continue
                exp_x.append(x)
                c = {"x": x, "y": y * sc + off, "color": e["color"], "label": e["label"], "ls": ls}
            else:
                key = ("tddft", e["file"], e.get("variant"))
                r = self.cache(key, lambda e=e: X.parse_tddft(e["file"], e.get("variant")))
                lam, eps, sl, sh = X.broaden(r["E"], r["f"], e.get("fwhm", 0.3), e.get("shift", 0.0))
                # Kurve und Striche immer mit DEMSELBEN Faktor: jeder Strich = Höhe seiner eigenen
                # Gaußbande, die Kurve ist deren Summe. Gewählt wird nur die Bezugsgröße.
                if eps_mode:
                    k = 1 / 1000.0                       # ε in 10³ M⁻¹ cm⁻¹
                else:
                    sel = (lam >= min(lo, hi)) & (lam <= max(lo, hi))
                    band_max = eps[sel].max() if sel.any() and eps[sel].max() > 0 else eps.max()
                    ssel = (sl >= min(lo, hi)) & (sl <= max(lo, hi))
                    stick_max = sh[ssel].max() if ssel.any() and sh[ssel].max() > 0 else sh.max()
                    k = 1 / (stick_max if mode == "max" else band_max)
                y, h = eps * k, sh * k
                c = {"x": lam, "y": y * sc + off, "color": e["color"], "label": e["label"], "ls": ls}
                if st["sticks"]:
                    if mode == "faxis":                 # Oszillatorstärken auf rechter Achse
                        sticks.append({"x": sl, "h": np.asarray(r["f"], float), "color": e["color"],
                                       "axis2": True})
                    else:
                        sticks.append({"x": sl, "h": h * sc, "color": e["color"], "base": off})
            if e.get("lw"):
                c["lw"] = e["lw"]
            curves.append(c)
        if not curves:
            return None
        if st["x_auto"]:
            if exp_x:
                xs = np.concatenate(exp_x)
                cfg["xlim"] = [float(xs.min()), float(xs.max())]
            else:
                sx = np.concatenate([s_["x"] for s_ in sticks]) if sticks else np.array([300.0, 600.0])
                cfg["xlim"] = [max(150.0, sx.min() - 80), sx.max() + 120]
        else:
            cfg["xlim"] = [st["x_min"], st["x_max"]]
        lo_x, hi_x = cfg["xlim"]
        ymin = min(0.0, min(float(np.nanmin(c["y"][(c["x"] >= lo_x) & (c["x"] <= hi_x)], initial=0))
                            for c in curves))
        if st["ymax"] > 0:
            cfg["ylim"] = [ymin, st["ymax"]]
        elif eps_mode:
            mx = max(np.nanmax(c["y"][(c["x"] >= lo_x) & (c["x"] <= hi_x)], initial=0) for c in curves)
            cfg["ylim"] = [ymin, 1.1 * mx if mx > 0 else 1]
        else:                                    # normiert: Platz für skalierte/versetzte Kurven
            cfg["ylim"] = [ymin, max(1.1, max(1.1 * e.get("scale", 1.0) + e.get("offset", 0.0) for e in vis))]
        cfg["ylabel"] = r"$\varepsilon$ [10$^3$ M$^{-1}$ cm$^{-1}$]" if eps_mode else "normalized absorbance [a.u.]"
        imgs = []
        if st.get("structure") and Path(st["structure"]).exists():
            imgs.append({"file": st["structure"], "id": "struktur", "width": st.get("struct_w", 20) / 100,
                         "prefer": "top", "_asset": self.structure_asset(st["structure"])})
        for e in vis:                                   # Struktur pro Spektrum, optional in Kurvenfarbe
            p = e.get("structure")
            if p and Path(p).exists():
                color = e["color"] if e.get("struct_color", True) else None
                try:
                    asset = self.structure_asset(p, color)
                except Exception as ex:
                    self.main.log_signal.emit(f"  {Path(p).name}: {ex}")
                    continue
                imgs.append({"file": p, "id": "struktur_" + e.get("uid", "x"),
                             "width": st.get("struct_w", 20) / 100, "prefer": "top", "_asset": asset})
        cfg["images"] = imgs
        return cfg, curves, [], sticks


# ----------------------------------------------------------------------------
class FluoTab(FigureTab):
    STATE_KEY = "fluorescence"
    DEFAULT_STATE = dict(COMMON_DEFAULTS, abs_file=None, abs_sample=None, em_file=None, em_sample=None,
                         ex=350.0, alo=300.0, ahi=500.0, eps="", mask=False, c_abs="#1f9bff",
                         c_em="#e8231b", structure=None, photo_day=None, bg_day="auto", photo_uv=None,
                         bg_uv="none", ymax=1.2, struct_w=20.0, photo_w=30.0)

    def build_controls(self):
        st = self.st
        g = QGroupBox(T("fl_data"))
        f = QFormLayout(g)
        self.w_abs = self._file_row(f, T("fl_abs"), "abs")
        self.w_em = self._file_row(f, T("fl_em"), "em")
        self.sp_ex = QDoubleSpinBox(decimals=0, minimum=150, maximum=1500, value=st["ex"], suffix=" nm")
        f.addRow(T("fl_ex"), self.sp_ex)
        self.cb_mask = QCheckBox(T("fl_mask"))
        self.cb_mask.setChecked(st["mask"])
        f.addRow(self.cb_mask)
        row = QHBoxLayout()
        self.sp_alo = QDoubleSpinBox(decimals=0, minimum=100, maximum=3500, value=st["alo"])
        self.sp_ahi = QDoubleSpinBox(decimals=0, minimum=100, maximum=3500, value=st["ahi"])
        for w in (self.sp_alo, QLabel("–"), self.sp_ahi):
            row.addWidget(w)
        f.addRow(T("fl_abs_window"), row)
        self.ed_eps = QLineEdit(st["eps"])
        self.ed_eps.setPlaceholderText(T("fl_eps_ph"))
        f.addRow("ε [M⁻¹ cm⁻¹]", self.ed_eps)
        row = QHBoxLayout()
        row.addWidget(QLabel(T("fl_abs")))
        row.addWidget(color_button(st["c_abs"], lambda c: self._set("c_abs", c)))
        row.addWidget(QLabel(T("fl_em")))
        row.addWidget(color_button(st["c_em"], lambda c: self._set("c_em", c)))
        row.addStretch(1)
        f.addRow(T("ov_color"), row)
        self.lv.addWidget(g)

        g = QGroupBox(T("fl_images"))
        f = QFormLayout(g)
        self.lbl_struct = self._img_row(f, T("structure"), "structure", T("flt_struct"))
        self.size_spin(f, "struct_w", "image_struktur")
        self.lbl_day = self._img_row(f, T("fl_photo_day"), "photo_day", T("flt_photo"))
        self.cmb_bg_day = self._bg_combo(f, "bg_day")
        self.lbl_uv = self._img_row(f, T("fl_photo_uv"), "photo_uv", T("flt_photo"))
        self.cmb_bg_uv = self._bg_combo(f, "bg_uv")
        self.size_spin(f, "photo_w", "image_fotos")
        self.lv.addWidget(g)
        for w in (self.sp_ex, self.sp_alo, self.sp_ahi):
            w.valueChanged.connect(self.changed)
        self.cb_mask.toggled.connect(self.changed)
        self.ed_eps.editingFinished.connect(self.changed)

    def _set(self, k, v):
        self.st[k] = v
        self.timer.start()

    def _file_row(self, form, label, which):
        row = QHBoxLayout()
        lbl = QLabel(Path(self.st[f"{which}_file"]).name if self.st[f"{which}_file"] else "–")
        b = QPushButton(T("choose"))
        cmb = QComboBox()
        row.addWidget(lbl, 1)
        row.addWidget(b)
        form.addRow(label, row)
        form.addRow("", cmb)

        def fill():
            cmb.blockSignals(True)
            cmb.clear()
            p = self.st[f"{which}_file"]
            if p and Path(p).exists():
                for s_ in self.samples(p):
                    cmb.addItem(s_["name"], s_["key"])
                i = cmb.findData(self.st[f"{which}_sample"])
                cmb.setCurrentIndex(max(0, i))
                self.st[f"{which}_sample"] = cmb.currentData()
            cmb.blockSignals(False)

        def choose():
            if not self.main.ensure_project():
                return
            p, _ = QFileDialog.getOpenFileName(self, label, self.main.settings.value("last_dir", ""),
                                               f"{T('flt_csv')};;{T('flt_all')}")
            if p:
                try:
                    p = self.main.import_file(p, "data")
                    self.samples(p)
                except Exception as e:
                    return self.main.error(f"{Path(p).name}: {e}")
                self.st[f"{which}_file"], self.st[f"{which}_sample"] = p, None
                lbl.setText(Path(p).name)
                fill()
                self._auto_ex(which)
                self.timer.start()

        def picked(_):
            self.st[f"{which}_sample"] = cmb.currentData()
            self._auto_ex(which)
            self.timer.start()
        b.clicked.connect(choose)
        cmb.currentIndexChanged.connect(picked)
        fill()
        return lbl, cmb

    def _auto_ex(self, which):
        """λex aus den Gerätemetadaten der Emissionsmessung übernehmen (Eclipse CSV/FBSW)."""
        if which != "em" or not self.st.get("em_file"):
            return
        s_ = self.sample(self.st["em_file"], self.st["em_sample"])
        if s_ and s_.get("ex") and hasattr(self, "sp_ex"):
            self.st["ex"] = float(s_["ex"])
            self.sp_ex.blockSignals(True)
            self.sp_ex.setValue(self.st["ex"])
            self.sp_ex.blockSignals(False)

    def _img_row(self, form, label, key, flt):
        row = QHBoxLayout()
        lbl = QLabel(Path(self.st[key]).name if self.st[key] else "–")
        b1, b2 = QPushButton(T("choose")), QPushButton(T("remove"))

        def choose():
            if not self.main.ensure_project():
                return
            p, _ = QFileDialog.getOpenFileName(self, label, self.main.settings.value("last_img_dir", ""),
                                               f"{flt};;{T('flt_all')}")
            if p:
                self.main.settings.setValue("last_img_dir", str(Path(p).parent))
                p = self.main.import_file(p, "images")
                self.st[key] = p
                lbl.setText(Path(p).name)
                self.timer.start()

        def remove():
            self.st[key] = None
            lbl.setText("–")
            self.timer.start()
        b1.clicked.connect(choose)
        b2.clicked.connect(remove)
        row.addWidget(lbl, 1)
        row.addWidget(b1)
        row.addWidget(b2)
        form.addRow(label, row)
        return lbl

    def _bg_combo(self, form, key):
        cmb = QComboBox()
        for k in ("auto", "isnet", "grabcut", "border", "none"):
            cmb.addItem(T({"auto": "bg_auto", "isnet": "bg_isnet", "grabcut": "bg_grabcut",
                           "border": "bg_border", "none": "bg_off"}[k]), k)
        cmb.setCurrentIndex(cmb.findData(self.st[key]))
        cmb.currentIndexChanged.connect(lambda _: self._set(key, cmb.currentData()))
        form.addRow(T("bg_method"), cmb)
        return cmb

    def collect(self):
        self.st.update(ex=self.sp_ex.value(), mask=self.cb_mask.isChecked(), alo=self.sp_alo.value(),
                       ahi=self.sp_ahi.value(), eps=self.ed_eps.text().strip())

    def figure_spec(self):
        st = self.st
        a = self.sample(st["abs_file"], st["abs_sample"]) if st["abs_file"] else None
        em = self.sample(st["em_file"], st["em_sample"]) if st["em_file"] else None
        if a is None and em is None:
            return None
        cfg = self.base_cfg()
        curves, labels = [], []
        if a is not None:
            ya = X.normalize(a["x"], a["y"], st["alo"], st["ahi"])
            if ya is None:
                self.main.log_signal.emit("  " + T("ov_no_signal", name=a["name"], lo=st["alo"], hi=st["ahi"]))
                a = None
        if a is not None:
            curves.append({"x": a["x"], "y": ya, "color": st["c_abs"], "label": None})
            pa = X.peak_in(a["x"], ya, st["alo"], st["ahi"])
            if pa:
                txt = f"λ =  {pa:.0f} nm"
                eps = parse_num(st["eps"])
                if eps:
                    txt += f"\nε =  {eps:.0f} cm$^{{-1}}$ M$^{{-1}}$"
                labels.append({"key": "label_abs", "text": txt, "lam": pa})
        if em is not None:
            y = em["y"].astype(float).copy()
            if st["mask"]:
                for c in (st["ex"], 2 * st["ex"]):
                    y[np.abs(em["x"] - c) <= 12] = np.nan
            ye = X.normalize(em["x"], y, float(np.nanmin(em["x"])), float(np.nanmax(em["x"])))
            if ye is None:
                ye = y
            curves.append({"x": em["x"], "y": ye, "color": st["c_em"], "label": None})
            pe = X.peak_in(em["x"], ye, float(np.nanmin(em["x"])), float(np.nanmax(em["x"])))
            if pe:
                labels.append({"key": "label_em", "text": f"λ$_{{\\mathrm{{em}}}}$ =  {pe:.0f} nm", "lam": pe})
        xs = np.concatenate([c["x"] for c in curves])
        cfg["xlim"] = [float(xs.min()), float(xs.max())] if st["x_auto"] else [st["x_min"], st["x_max"]]
        cfg["ylim"] = [0, st["ymax"] if st["ymax"] > 0 else 1.2]
        cfg["ylabel"] = "normalized intensity [a.u.]"
        imgs = []
        if st.get("structure") and Path(st["structure"]).exists():
            imgs.append({"file": st["structure"], "id": "struktur", "width": st.get("struct_w", 20) / 100,
                         "prefer": "top", "_asset": self.structure_asset(st["structure"])})
        day = self.photo_asset(st["photo_day"], st["bg_day"]) if st.get("photo_day") else None
        uv = self.photo_asset(st["photo_uv"], st["bg_uv"]) if st.get("photo_uv") else None
        if day and uv:
            pair = X.compose_photo_pair(day["rgba"], uv["rgba"], f"{st['ex']:g} nm")
            imgs.append({"file": "pair", "id": "fotos", "width": st.get("photo_w", 30) / 100, "prefer": "bottom-right",
                         "_asset": {"rgba": pair, "pdf": None, "clip": None}})
        elif day or uv:
            one = day or uv
            imgs.append({"file": "photo", "id": "fotos", "width": st.get("photo_w", 30) / 300, "prefer": "bottom-right",
                         "_asset": {"rgba": one["rgba"], "pdf": None, "clip": None}})
        cfg["images"] = imgs
        return cfg, curves, labels, []
