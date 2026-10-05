"""
uvvis_gui.py - Grafische Oberfläche der UV-Vis-Auswertung (Windows / macOS / Linux).

Start:      python uvvis_gui.py
Selbsttest: python uvvis_gui.py --selftest AUSGABEORDNER [--selftest-isnet]
"""
from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

APP_NAME = "UVVisTool"
APP_VERSION = "1.1.0"

if "--selftest" in sys.argv:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np  # noqa: E402
import yaml  # noqa: E402
import matplotlib  # noqa: E402

matplotlib.use("QtAgg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.backends.backend_agg import FigureCanvasAgg  # noqa: E402
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg  # noqa: E402
from matplotlib.figure import Figure as MplFigure  # noqa: E402
from PySide6.QtCore import QSettings, Qt, QThread, QTimer, Signal  # noqa: E402
from PySide6.QtGui import QAction, QActionGroup, QIcon, QImage, QPixmap  # noqa: E402
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QCheckBox, QComboBox,  # noqa: E402
                               QDialog, QDialogButtonBox, QDoubleSpinBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout,
                               QHeaderView, QLabel, QLineEdit, QMainWindow, QMessageBox,
                               QPlainTextEdit, QProgressDialog, QPushButton, QScrollArea,
                               QSpinBox, QSplitter, QTableWidget, QTableWidgetItem,
                               QTabWidget, QVBoxLayout, QWidget)

import uvvis_core as core  # noqa: E402
import uvvis_images as IMG  # noqa: E402
from uvvis_i18n import T, get_lang, set_lang  # noqa: E402
import uvvis_tabs  # noqa: E402

PREVIEW_DPI = 90
FIGSIZE = (8.0, 6.0)


def resource_path(rel):
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / rel


def rgba_to_pixmap(arr, max_h=110):
    arr = np.ascontiguousarray(arr)
    h, w = arr.shape[:2]
    img = QImage(arr.data, w, h, 4 * w, QImage.Format_RGBA8888).copy()
    return QPixmap.fromImage(img).scaledToHeight(max_h, Qt.SmoothTransformation)


def parse_float(txt):
    txt = (txt or "").strip().replace(",", ".")
    if not txt:
        return None
    v = float(txt)
    if v <= 0:
        raise ValueError
    return v


class Task(QThread):
    """Funktion im Hintergrund ausführen (Freistellung, CDXML), GUI bleibt bedienbar."""
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, fn, parent=None):
        super().__init__(parent)
        self.fn = fn

    def run(self):
        try:
            self.done.emit(self.fn())
        except Exception as e:
            self.failed.emit(f"{type(e).__name__}: {e}")


class GuiDragger(core.Dragger):
    """Wie core.Dragger, meldet aber jede Änderung (Ziehen von Inset/Bild/Label, Mausrad)
    an die GUI, damit Vorschau, Serienwechsel und Export dasselbe Layout verwenden."""

    def __init__(self, F, on_change):
        self.on_change = on_change
        super().__init__(F, None)

    def _report(self):
        # erst nach allen anderen Release-Handlern auslesen (Label-Drag von matplotlib)
        QTimer.singleShot(0, lambda: self.on_change(self.F.current_layout()))

    def release(self, ev):
        super().release(ev)
        self._report()

    def scroll(self, ev):
        if super().scroll(ev):
            self._report()

    def key(self, ev):
        pass


DEFAULT_GLOB = {"path_length": 1.0, "cutoff": 1.0, "min_points": 3, "bands": "",
                "baseline": "series", "bl_a": 1050.0, "bl_b": 1100.0, "ymax": 1.0,
                "r2": "legend", "show_err": False, "table": True,
                "size": "half_a4", "w_cm": 16.0, "h_cm": 11.0,
                "fmt_pdf": True, "fmt_svg": True, "fmt_png": True,
                "x_auto": True, "x_min": 200.0, "x_max": 1100.0}

UNITS = [("mM", "mM"), ("uM", "µM"), ("mg/mL", "mg/mL"), ("M", "M")]


class ConcDialog(QDialog):
    """Konzentrationen je Probe eintragen (wenn sie nicht im Probennamen stehen)."""

    def __init__(self, parent, samples, overrides, default_series):
        super().__init__(parent)
        self.setWindowTitle(T("conc_title"))
        self.samples = samples
        lay = QVBoxLayout(self)
        intro = QLabel(T("conc_intro"))
        intro.setWordWrap(True)
        lay.addWidget(intro)

        unit0 = None
        for s_ in samples:
            o = overrides.get(s_["key"]) or {}
            unit0 = unit0 or o.get("unit") or (s_["parsed"][2] if s_["parsed"] else None)
        row = QHBoxLayout()
        row.addWidget(QLabel(T("unit")))
        self.cmb_unit = QComboBox()
        self.cmb_unit.addItem(T("unit_choose"), None)          # keine stille Vorbelegung
        for key, label in UNITS:
            self.cmb_unit.addItem(label, key)
        self.cmb_unit.setCurrentIndex(max(0, self.cmb_unit.findData(unit0)) if unit0 else 0)
        row.addWidget(self.cmb_unit)
        row.addStretch(1)
        lay.addLayout(row)

        self.table = QTableWidget(len(samples), 3)
        self.table.setHorizontalHeaderLabels([T("col_sample"), T("col_series"), T("col_conc")])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        for i, s_ in enumerate(samples):
            o = overrides.get(s_["key"]) or {}
            it = QTableWidgetItem(s_["key"])
            it.setFlags(it.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(i, 0, it)
            series = o.get("series") or (s_["parsed"][0] if s_["parsed"] else default_series)
            self.table.setItem(i, 1, QTableWidgetItem(series))
            c = o.get("conc") or (s_["parsed"][1] if s_["parsed"] and not o.get("skip") else None)
            self.table.setItem(i, 2, QTableWidgetItem(f"{c:g}" if c else ""))
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.resizeColumnsToContents()
        lay.addWidget(self.table)

        row = QHBoxLayout()
        row.addWidget(QLabel(T("dil_start")))
        self.sp_start = QDoubleSpinBox(decimals=4, minimum=0.0, maximum=1e6, value=0.0)
        row.addWidget(self.sp_start)
        row.addWidget(QLabel(T("dil_factor")))
        self.sp_fac = QDoubleSpinBox(decimals=3, minimum=1.0, maximum=1000, value=2.0)
        row.addWidget(self.sp_fac)
        b = QPushButton(T("dil_fill"))
        b.clicked.connect(self.fill_dilution)
        row.addWidget(b)
        row.addStretch(1)
        lay.addLayout(row)
        hint = QLabel(T("dil_hint"))
        hint.setStyleSheet("color: gray;")
        lay.addWidget(hint)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.try_accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self.table.setMinimumHeight(36 + 30 * min(len(samples), 12))
        self.resize(600, 300 + 30 * min(len(samples), 12))

    def fill_dilution(self):
        if self.sp_start.value() <= 0:
            QMessageBox.warning(self, T("conc_title"), T("start_missing"))
            return
        rows = sorted({i.row() for i in self.table.selectedIndexes()}) or list(range(self.table.rowCount()))
        c = self.sp_start.value()
        for r in rows:
            self.table.item(r, 2).setText(f"{c:.6g}")
            c /= self.sp_fac.value()

    def try_accept(self):
        any_conc = any((self.table.item(i, 2).text() or "").strip() for i in range(self.table.rowCount()))
        if any_conc and self.cmb_unit.currentData() is None:
            QMessageBox.warning(self, T("conc_title"), T("unit_missing"))
            return
        self.accept()

    def overrides(self):
        unit = self.cmb_unit.currentData()
        out = {}
        for i, s_ in enumerate(self.samples):
            series = (self.table.item(i, 1).text() or "").strip()
            try:
                c = parse_float(self.table.item(i, 2).text())
            except ValueError:
                c = None
            out[s_["key"]] = {"conc": c, "unit": unit, "series": series} if c else {"skip": True}
        return out


class MainWindow(QMainWindow):
    log_signal = Signal(str)

    def __init__(self):
        super().__init__()
        self.settings = QSettings(APP_NAME, APP_NAME)
        set_lang(self.settings.value("lang", "de"))
        self.csv_path = None
        self.groups, self.units = {}, {}
        self.samples, self.conc, self.csv_paths = [], {}, []          # Rohproben und Konzentrations-Overrides
        self.series = {}               # je Serie: mw, structure, photo, bg, layout, assets
        self.current = None
        self.F = None
        self.dragger = None
        self._tasks = []
        self._loading = False
        self.glob = dict(DEFAULT_GLOB)
        self.extra_cache = {}
        self.ov_state = self._load_state("overlay_state")
        self.fl_state = self._load_state("fluo_state")
        self._tab_index = 0

        self.fig = MplFigure(figsize=FIGSIZE, dpi=PREVIEW_DPI)
        self.canvas = FigureCanvasQTAgg(self.fig)
        self.canvas.setFixedSize(int(FIGSIZE[0] * PREVIEW_DPI), int(FIGSIZE[1] * PREVIEW_DPI))
        self.timer = QTimer(self, singleShot=True, interval=400)
        self.timer.timeout.connect(self.render)

        self.log_signal.connect(self._append_log)
        core.LOG = IMG.LOG = lambda m="": self.log_signal.emit(str(m))
        icon = resource_path("assets/icon.png")
        if icon.exists():
            self.setWindowIcon(QIcon(str(icon)))
        self.build_ui()
        self.setAcceptDrops(True)
        geo = self.settings.value("geometry")
        if geo:
            self.restoreGeometry(geo)
        else:
            self.resize(1320, 900)

    # ------------------------------------------------------------------ UI
    def build_ui(self):
        self.setWindowTitle(f"{T('app_title')} {APP_VERSION}")
        mb = self.menuBar()
        mb.clear()
        m = mb.addMenu(T("menu_file"))
        a = QAction(T("act_open"), self, shortcut="Ctrl+O", triggered=self.choose_csv)
        m.addAction(a)
        m.addAction(QAction(T("act_conc"), self, triggered=self.edit_concentrations))
        m.addAction(QAction(T("act_restart"), self, triggered=self.restart_file))
        m.addAction(QAction(T("act_export"), self, shortcut="Ctrl+E", triggered=self.export_current))
        m.addSeparator()
        m.addAction(QAction(T("act_quit"), self, shortcut="Ctrl+Q", triggered=self.close))
        ml = mb.addMenu(T("menu_lang"))
        grp = QActionGroup(self)
        for code, name in (("de", "Deutsch"), ("en", "English")):
            act = QAction(name, self, checkable=True, checked=get_lang() == code)
            act.triggered.connect(lambda _=False, c=code: self.switch_lang(c))
            grp.addAction(act)
            ml.addAction(act)
        mh = mb.addMenu(T("menu_help"))
        mh.addAction(QAction(T("act_about"), self, triggered=lambda: QMessageBox.about(
            self, T("act_about"), T("about", v=APP_VERSION))))

        # ---- linke Spalte
        left = QWidget()
        lv = QVBoxLayout(left)

        g = QGroupBox(T("grp_data"))
        f = QFormLayout(g)
        row = QHBoxLayout()
        self.btn_open = QPushButton(T("act_open"))
        self.btn_open.clicked.connect(self.choose_csv)
        row.addWidget(self.btn_open)
        self.lbl_file = QLabel(self.files_label() if self.csv_path else T("no_file"))
        self.lbl_file.setWordWrap(True)
        row.addWidget(self.lbl_file, 1)
        f.addRow(row)
        self.cmb_series = QComboBox()
        self.cmb_series.addItems(list(self.groups))
        if self.current:
            self.cmb_series.setCurrentText(self.current)
        self.cmb_series.currentTextChanged.connect(self.series_changed)
        row = QHBoxLayout()
        row.addWidget(self.cmb_series, 1)
        b = QPushButton(T("act_conc"))
        b.clicked.connect(self.edit_concentrations)
        row.addWidget(b)
        f.addRow(T("series"), row)
        lv.addWidget(g)

        g = QGroupBox(T("grp_compound"))
        f = QFormLayout(g)
        self.ed_mw = QLineEdit()
        self.ed_mw.setPlaceholderText(T("mw_hint_none"))
        self.ed_mw.editingFinished.connect(self.mw_edited)
        f.addRow(T("molar_mass"), self.ed_mw)
        self.lbl_chem = QLabel("")
        self.lbl_chem.setWordWrap(True)
        f.addRow("", self.lbl_chem)
        row = QHBoxLayout()
        self.lbl_struct = QLabel("–")
        b1 = QPushButton(T("choose"))
        b1.clicked.connect(self.choose_structure)
        b2 = QPushButton(T("remove"))
        b2.clicked.connect(lambda: self.set_structure(None))
        row.addWidget(self.lbl_struct, 1)
        row.addWidget(b1)
        row.addWidget(b2)
        f.addRow(T("structure"), row)
        self.sp_struct_w = QDoubleSpinBox(decimals=1, minimum=3, maximum=90, singleStep=1, suffix=" %")
        self.sp_struct_w.valueChanged.connect(lambda v: self.image_size_changed("struktur", v))
        f.addRow(T("img_size"), self.sp_struct_w)
        row = QHBoxLayout()
        self.lbl_photo = QLabel("–")
        b1 = QPushButton(T("choose"))
        b1.clicked.connect(self.choose_photo)
        b2 = QPushButton(T("remove"))
        b2.clicked.connect(lambda: self.set_photo(None))
        row.addWidget(self.lbl_photo, 1)
        row.addWidget(b1)
        row.addWidget(b2)
        f.addRow(T("photo"), row)
        self.sp_photo_w = QDoubleSpinBox(decimals=1, minimum=2, maximum=60, singleStep=0.5, suffix=" %")
        self.sp_photo_w.valueChanged.connect(lambda v: self.image_size_changed("kuevette", v))
        f.addRow(T("img_size"), self.sp_photo_w)
        self.cmb_bg = QComboBox()
        for key in ("auto", "isnet", "grabcut", "border", "none"):
            self.cmb_bg.addItem(T({"auto": "bg_auto", "isnet": "bg_isnet", "grabcut": "bg_grabcut",
                                   "border": "bg_border", "none": "bg_off"}[key]), key)
        self.cmb_bg.currentIndexChanged.connect(self.bg_changed)
        f.addRow(T("bg_method"), self.cmb_bg)
        self.lbl_thumb = QLabel()
        self.lbl_thumb.setAlignment(Qt.AlignCenter)
        f.addRow("", self.lbl_thumb)
        lv.addWidget(g)

        g = QGroupBox(T("grp_eval"))
        f = QFormLayout(g)
        self.sp_d = QDoubleSpinBox(decimals=3, minimum=0.001, maximum=100, singleStep=0.1)
        f.addRow(T("path_length"), self.sp_d)
        self.sp_cut = QDoubleSpinBox(decimals=2, minimum=0.05, maximum=5, singleStep=0.1)
        f.addRow(T("cutoff"), self.sp_cut)
        self.sp_min = QSpinBox(minimum=2, maximum=20)
        f.addRow(T("min_points"), self.sp_min)
        self.ed_bands = QLineEdit()
        self.ed_bands.setPlaceholderText(T("wavelengths_ph"))
        f.addRow(T("wavelengths"), self.ed_bands)
        self.cmb_bl = QComboBox()
        for key in ("series", "simple", "manual", "off"):
            self.cmb_bl.addItem(T({"series": "bl_series", "simple": "bl_simple", "manual": "bl_manual",
                                   "off": "bl_off"}[key]), key)
        f.addRow(T("baseline"), self.cmb_bl)
        row = QHBoxLayout()
        self.sp_bla = QDoubleSpinBox(decimals=0, minimum=100, maximum=3500, suffix=" nm")
        self.sp_blb = QDoubleSpinBox(decimals=0, minimum=100, maximum=3500, suffix=" nm")
        row.addWidget(self.sp_bla)
        row.addWidget(QLabel("–"))
        row.addWidget(self.sp_blb)
        f.addRow("", row)
        lv.addWidget(g)

        g = QGroupBox(T("grp_plot"))
        f = QFormLayout(g)
        self.sp_ymax = QDoubleSpinBox(decimals=2, minimum=0.05, maximum=10, singleStep=0.1)
        f.addRow(T("ymax"), self.sp_ymax)
        row = QHBoxLayout()
        self.cb_xauto = QCheckBox(T("xrange_auto"))
        self.sp_xmin = QDoubleSpinBox(decimals=0, minimum=100, maximum=3500, singleStep=10)
        self.sp_xmax = QDoubleSpinBox(decimals=0, minimum=100, maximum=3500, singleStep=10)
        row.addWidget(self.cb_xauto)
        row.addWidget(self.sp_xmin)
        row.addWidget(QLabel("–"))
        row.addWidget(self.sp_xmax)
        f.addRow(T("xrange"), row)
        self.cmb_r2 = QComboBox()
        for key in ("legend", "label", "off"):
            self.cmb_r2.addItem(T({"legend": "r2_legend", "label": "r2_label", "off": "r2_off"}[key]), key)
        f.addRow(T("r2_mode"), self.cmb_r2)
        self.cb_err = QCheckBox(T("show_err"))
        self.cb_tab = QCheckBox(T("inset_table"))
        f.addRow(self.cb_err)
        f.addRow(self.cb_tab)
        self.cmb_size = QComboBox()
        for key in ("half_a4", "custom", "std"):
            self.cmb_size.addItem(T({"half_a4": "size_half_a4", "custom": "size_custom",
                                     "std": "size_std"}[key]), key)
        f.addRow(T("size"), self.cmb_size)
        row = QHBoxLayout()
        self.sp_w = QDoubleSpinBox(decimals=1, minimum=4, maximum=40, singleStep=0.5, suffix=" cm")
        self.sp_h = QDoubleSpinBox(decimals=1, minimum=3, maximum=40, singleStep=0.5, suffix=" cm")
        row.addWidget(self.sp_w)
        row.addWidget(QLabel("×"))
        row.addWidget(self.sp_h)
        f.addRow(T("size_wh"), row)
        row = QHBoxLayout()
        self.cb_pdf, self.cb_svg, self.cb_png = QCheckBox("PDF"), QCheckBox("SVG"), QCheckBox("PNG")
        for cb in (self.cb_pdf, self.cb_svg, self.cb_png):
            row.addWidget(cb)
        row.addStretch(1)
        f.addRow(T("formats"), row)
        lv.addWidget(g)

        row = QHBoxLayout()
        b = QPushButton(T("btn_reset_layout"))
        b.clicked.connect(self.reset_layout)
        row.addWidget(b)
        self.btn_export = QPushButton(T("btn_export"))
        self.btn_export.clicked.connect(self.export_dialog)
        self.btn_export.setDefault(True)
        row.addWidget(self.btn_export)
        lv.addLayout(row)
        hint = QLabel(T("drag_hint"))
        hint.setWordWrap(True)
        hint.setStyleSheet("color: gray;")
        lv.addWidget(hint)
        lv.addStretch(1)

        lscroll = QScrollArea()
        lscroll.setWidget(left)
        lscroll.setWidgetResizable(True)
        lscroll.setMinimumWidth(380)

        # ---- rechte Seite
        cscroll = QScrollArea()
        holder = QWidget()
        hl = QHBoxLayout(holder)
        hl.addWidget(self.canvas, 0, Qt.AlignCenter)
        cscroll.setWidget(holder)
        cscroll.setWidgetResizable(True)
        self.tabs = QTabWidget()
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels([T("col_lam"), T("col_n"), T("col_coeff"),
                                              T("col_intercept"), T("col_r2"), T("col_warn")])
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        old_log = self.log.toPlainText() if hasattr(self, "log") else ""
        self.log = QPlainTextEdit(readOnly=True)
        self.log.setPlainText(old_log)
        self.tabs.addTab(self.table, T("tab_results"))
        self.tabs.addTab(self.log, T("tab_log"))
        right = QSplitter(Qt.Vertical)
        right.addWidget(cscroll)
        right.addWidget(self.tabs)
        right.setSizes([650, 220])
        split = QSplitter(Qt.Horizontal)
        split.addWidget(lscroll)
        split.addWidget(right)
        split.setSizes([400, 920])
        self.main_tabs = QTabWidget()
        self.main_tabs.addTab(split, T("tab_eps"))
        self.ov_tab = uvvis_tabs.OverlayTab(self, self.ov_state)
        self.fl_tab = uvvis_tabs.FluoTab(self, self.fl_state)
        self.main_tabs.addTab(self.ov_tab, T("tab_overlay"))
        self.main_tabs.addTab(self.fl_tab, T("tab_fluo"))
        self.main_tabs.setCurrentIndex(self._tab_index)
        self.main_tabs.currentChanged.connect(lambda i: setattr(self, "_tab_index", i))
        self.setCentralWidget(self.main_tabs)

        self.apply_globals()
        self.apply_series_widgets()
        for w in (self.sp_d, self.sp_cut, self.sp_ymax, self.sp_bla, self.sp_blb, self.sp_w, self.sp_h,
                  self.sp_xmin, self.sp_xmax):
            w.valueChanged.connect(self.changed)
        self.cb_xauto.toggled.connect(self._xauto_toggled)
        self.cmb_size.currentIndexChanged.connect(self._size_changed)
        for cb in (self.cb_pdf, self.cb_svg, self.cb_png):
            cb.toggled.connect(lambda *_: self.collect_globals())
        self.sp_min.valueChanged.connect(self.changed)
        self.ed_bands.editingFinished.connect(self.changed)
        for w in (self.cmb_bl, self.cmb_r2):
            w.currentIndexChanged.connect(self.changed)
        for w in (self.cb_err, self.cb_tab):
            w.toggled.connect(self.changed)

    def apply_globals(self):
        self._loading = True
        gl = self.glob
        self.sp_d.setValue(gl["path_length"])
        self.sp_cut.setValue(gl["cutoff"])
        self.sp_min.setValue(gl["min_points"])
        self.ed_bands.setText(gl["bands"])
        self.cmb_bl.setCurrentIndex(self.cmb_bl.findData(gl["baseline"]))
        self.sp_bla.setValue(gl["bl_a"])
        self.sp_blb.setValue(gl["bl_b"])
        self.sp_ymax.setValue(gl["ymax"])
        self.cmb_r2.setCurrentIndex(self.cmb_r2.findData(gl["r2"]))
        self.cb_err.setChecked(gl["show_err"])
        self.cb_tab.setChecked(gl["table"])
        self.cmb_size.setCurrentIndex(max(0, self.cmb_size.findData(gl["size"])))
        self.sp_w.setValue(gl["w_cm"])
        self.sp_h.setValue(gl["h_cm"])
        self.cb_pdf.setChecked(gl["fmt_pdf"])
        self.cb_svg.setChecked(gl["fmt_svg"])
        self.cb_png.setChecked(gl["fmt_png"])
        self.cb_xauto.setChecked(gl["x_auto"])
        self.sp_xmin.setValue(gl["x_min"])
        self.sp_xmax.setValue(gl["x_max"])
        self.sp_xmin.setEnabled(not gl["x_auto"])
        self.sp_xmax.setEnabled(not gl["x_auto"])
        self._update_size_widgets()
        manual = gl["baseline"] == "manual"
        self.sp_bla.setEnabled(manual)
        self.sp_blb.setEnabled(manual)
        self._loading = False

    def collect_globals(self):
        self.glob.update(path_length=self.sp_d.value(), cutoff=self.sp_cut.value(),
                         min_points=self.sp_min.value(), bands=self.ed_bands.text().strip(),
                         baseline=self.cmb_bl.currentData(), bl_a=self.sp_bla.value(),
                         bl_b=self.sp_blb.value(), ymax=self.sp_ymax.value(),
                         r2=self.cmb_r2.currentData(), show_err=self.cb_err.isChecked(),
                         table=self.cb_tab.isChecked(), size=self.cmb_size.currentData(),
                         w_cm=self.sp_w.value(), h_cm=self.sp_h.value(),
                         fmt_pdf=self.cb_pdf.isChecked(), fmt_svg=self.cb_svg.isChecked(),
                         fmt_png=self.cb_png.isChecked(), x_auto=self.cb_xauto.isChecked(),
                         x_min=self.sp_xmin.value(), x_max=self.sp_xmax.value())

    def _update_size_widgets(self):
        key = self.cmb_size.currentData()
        if key == "half_a4":
            self.sp_w.blockSignals(True)
            self.sp_h.blockSignals(True)
            self.sp_w.setValue(16.0)
            self.sp_h.setValue(11.0)
            self.sp_w.blockSignals(False)
            self.sp_h.blockSignals(False)
        custom = key == "custom"
        self.sp_w.setEnabled(custom)
        self.sp_h.setEnabled(custom)

    def apply_series_widgets(self):
        self._loading = True
        st = self.series.get(self.current)
        self.ed_mw.setText(f"{st['mw']:g}" if st and st["mw"] else "")
        self.lbl_struct.setText(Path(st["structure"]).name if st and st["structure"] else "–")
        self.lbl_photo.setText(Path(st["photo"]).name if st and st["photo"] else "–")
        self.cmb_bg.setCurrentIndex(self.cmb_bg.findData(st["bg"] if st else "auto"))
        info = st.get("chem_info", "") if st else ""
        unit = self.units.get(self.current) if st else None
        warn = bool(st and st.get("chem_warn"))
        if unit and unit != "mg/mL":
            info = (info + "\n" if info else "") + T("mw_unused", u="µM" if unit == "uM" else unit)
        mw_missing = unit == "mg/mL" and not (st and st["mw"])
        if mw_missing:
            info = (info + "\n" if info else "") + T("mw_needed")
            warn = True
        self.ed_mw.setStyleSheet("border: 2px solid #d9534f;" if mw_missing else "")
        self.lbl_chem.setText(info)
        self.lbl_chem.setStyleSheet("color: #d9534f;" if warn else "")
        pa = st.get("photo_asset") if st else None
        self.lbl_thumb.setPixmap(rgba_to_pixmap(pa["rgba"]) if pa else QPixmap())
        self.sp_struct_w.setValue(st.get("struct_w", 17.0) if st else 17.0)
        self.sp_photo_w.setValue(st.get("photo_w", 9.0) if st else 9.0)
        self.sp_struct_w.setEnabled(bool(st and st["structure"]))
        self.sp_photo_w.setEnabled(bool(st and st["photo"]))
        self._loading = False

    def _xauto_toggled(self, on):
        if self._loading:
            return
        self.sp_xmin.setEnabled(not on)
        self.sp_xmax.setEnabled(not on)
        if not on and self.current in self.groups:       # mit dem Datenbereich vorbelegen
            xs = np.concatenate([s_["x"] for s_ in self.groups[self.current]])
            self._loading = True
            if self.sp_xmin.value() <= xs.min() or self.sp_xmin.value() >= xs.max():
                self.sp_xmin.setValue(float(np.floor(xs.min())))
            if self.sp_xmax.value() >= xs.max() or self.sp_xmax.value() <= self.sp_xmin.value():
                self.sp_xmax.setValue(float(np.ceil(xs.max())))
            self._loading = False
        self.changed()

    def _size_changed(self, *_):
        if self._loading:
            return
        self._update_size_widgets()
        self.changed()

    def switch_lang(self, code):
        self.collect_globals()
        set_lang(code)
        self.settings.setValue("lang", code)
        self.build_ui()
        self.render()

    def _append_log(self, msg):
        self.log.appendPlainText(msg)

    # ------------------------------------------------------------ Daten
    def choose_csv(self):
        start = self.settings.value("last_dir", str(Path.home()))
        ps, _ = QFileDialog.getOpenFileNames(self, T("dlg_open_csv"), start,
                                             f"{T('flt_csv')};;{T('flt_all')}")
        if ps:
            self.open_files(ps)

    def open_csv(self, path, ask=True):
        return self.open_files([path], ask)

    def files_label(self):
        names = [Path(p).name for p in self.csv_paths]
        if len(names) == 1:
            return names[0]
        short = ", ".join(names[:3]) + (", …" if len(names) > 3 else "")
        return T("files_loaded", n=len(names), names=short)

    def open_files(self, paths, ask=True):
        """Eine oder mehrere Messdateien (CSV/TXT/DSW/BSW) gemeinsam öffnen,
        z. B. wenn jede Konzentration einzeln gemessen wurde."""
        paths = sorted(str(Path(p).resolve()) for p in paths)
        path = paths[0]
        try:
            samples = core.read_samples(paths)
        except Exception as e:
            self.error(f"{type(e).__name__}: {e}")
            return False
        if not samples:
            self.error(T("conc_none"))
            return False
        self.save_project()
        self.csv_path, self.csv_paths, self.samples = path, paths, samples
        self.settings.setValue("last_dir", str(Path(path).parent))
        self.groups, self.units, self.series, self.conc = {}, {}, {}, {}
        data = self.read_project()
        self.conc = (data.get("concentrations") or {}) if data else {}
        _, _, missing = core.group_samples(samples, self.conc, Path(path).stem)
        if missing and ask and not self.edit_concentrations(rebuild=False):
            pass
        if not self.rebuild_groups():
            self.lbl_file.setText(self.files_label())
            self.error(T("conc_none"))
            return False
        self.load_project(data)
        self.lbl_file.setText(self.files_label())
        self.apply_globals()
        self.apply_series_widgets()
        self.render()
        return True

    def edit_concentrations(self, rebuild=True):
        if not self.samples:
            self.error(T("load_first"))
            return False
        dlg = ConcDialog(self, self.samples, self.conc, Path(self.csv_path).stem)
        if dlg.exec() != QDialog.Accepted:
            return False
        self.conc = dlg.overrides()
        if rebuild:
            self.rebuild_groups()
            self.apply_series_widgets()
            self.render()
            self.save_project()
        return True

    def rebuild_groups(self):
        """Serien aus Proben + Konzentrationen neu bilden; Einstellungen je Serie bleiben."""
        try:
            groups, units, missing = core.group_samples(self.samples, self.conc, Path(self.csv_path).stem)
        except ValueError as e:
            self.error(str(e))
            return False
        for k in missing:
            self.log_signal.emit("  " + T("no_conc_in_name", name=k))
        self.groups, self.units = groups, units
        for g in groups:
            self.series.setdefault(g, {"mw": None, "structure": None, "photo": None, "bg": "auto",
                                       "layout": {}, "structure_asset": None, "photo_asset": None,
                                       "chem_info": "", "chem_warn": False,
                                       "struct_w": 17.0, "photo_w": 9.0})
        if self.current not in groups:
            self.current = next(iter(groups), None)
        self.cmb_series.blockSignals(True)
        self.cmb_series.clear()
        self.cmb_series.addItems(list(groups))
        if self.current:
            self.cmb_series.setCurrentText(self.current)
        self.cmb_series.blockSignals(False)
        log_names = ", ".join(groups) or "–"
        self.log_signal.emit(T("cary_series", name=Path(self.csv_path).name, s=log_names))
        return bool(groups)

    def restart_file(self):
        """Alle gespeicherten Eingaben zur aktuellen CSV verwerfen und frisch beginnen."""
        if not self.csv_path:
            return self.error(T("load_first"))
        if os.environ.get("QT_QPA_PLATFORM") != "offscreen":
            ans = QMessageBox.question(self, T("act_restart").rstrip("…"),
                                       T("restart_q", name=Path(self.csv_path).name))
            if ans != QMessageBox.Yes:
                return False
        pf = self.project_file()
        paths = list(self.csv_paths)
        self.csv_path = None                      # verhindert, dass open_csv vorher noch speichert
        try:
            if pf and pf.exists():
                pf.unlink()
        except OSError as e:
            self.error(str(e))
        self.glob = dict(DEFAULT_GLOB)
        self.series, self.conc, self.current = {}, {}, None
        return self.open_files(paths)

    def project_file(self):
        if not self.csv_path:
            return None
        n = len(getattr(self, "csv_paths", [])) or 1
        p = Path(self.csv_path)
        return p.with_name(f"{p.stem}+{n - 1}.uvvis.yaml") if n > 1 else p.with_suffix(".uvvis.yaml")

    def save_project(self):
        pf = self.project_file()
        if not pf:
            return
        self.collect_globals()
        data = {"global": self.glob,
                "concentrations": self.conc,
                "series": {g: {k: st.get(k) for k in ("mw", "structure", "photo", "bg", "layout",
                                                       "struct_w", "photo_w")}
                           for g, st in self.series.items()}}
        try:
            pf.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
        except OSError:
            pass

    def read_project(self):
        pf = self.project_file()
        if not pf or not pf.exists():
            return {}
        try:
            return yaml.safe_load(pf.read_text(encoding="utf-8")) or {}
        except Exception:
            return {}

    def load_project(self, data=None):
        data = data if data is not None else self.read_project()
        if not data:
            return
        self.glob.update(data.get("global") or {})
        for g, sd in (data.get("series") or {}).items():
            if g not in self.series:
                continue
            st = self.series[g]
            st.update({k: sd.get(k) or st.get(k) for k in ("mw", "bg", "layout", "struct_w", "photo_w")})
            st["layout"] = st["layout"] or {}
            if sd.get("structure") and Path(sd["structure"]).exists():
                self.set_structure(sd["structure"], g, render=False, sync=True, autofill_mw=False)
            if sd.get("photo") and Path(sd["photo"]).exists():
                self.set_photo(sd["photo"], g, render=False, sync=True)

    def series_changed(self, g):
        if not g or g not in self.series:
            return
        self.current = g
        self.apply_series_widgets()
        self.render()

    def changed(self, *_):
        if self._loading:
            return
        self.collect_globals()
        manual = self.glob["baseline"] == "manual"
        self.sp_bla.setEnabled(manual)
        self.sp_blb.setEnabled(manual)
        self.timer.start()

    def mw_edited(self):
        if self._loading or not self.current:
            return
        try:
            self.series[self.current]["mw"] = parse_float(self.ed_mw.text())
        except ValueError:
            self.ed_mw.setText("")
            self.series[self.current]["mw"] = None
        self.apply_series_widgets()                 # Warnung zur Molmasse sofort aktualisieren
        self.timer.start()

    # ------------------------------------------------------- Struktur/Foto
    def choose_structure(self):
        if not self.current:
            return self.error(T("load_first"))
        p, _ = QFileDialog.getOpenFileName(self, T("dlg_structure"), self.settings.value("last_img_dir", ""),
                                           f"{T('flt_struct')};;{T('flt_all')}")
        if p:
            self.settings.setValue("last_img_dir", str(Path(p).parent))
            self.set_structure(p)

    def set_structure(self, path, g=None, render=True, sync=False, autofill_mw=True):
        g = g or self.current
        st = self.series[g]
        if path is None:
            st.update(structure=None, structure_asset=None, chem_info="", chem_warn=False)
            self.apply_series_widgets()
            return self.render()

        def work():
            asset = IMG.load_structure(path)
            p = Path(path)
            if asset["mw"] is None and p.suffix.lower() != ".cdxml":
                sib = p.with_suffix(".cdxml")            # gleichnamige CDXML neben SVG/PDF
                if sib.exists():
                    import uvvis_chem
                    chem = uvvis_chem.load_cdxml(sib)
                    asset.update(mw=chem["mw"], formula=chem["formula"], warnings=chem["warnings"])
            return asset

        def done(asset):
            st["structure"], st["structure_asset"] = str(path), asset
            info = []
            if asset.get("formula") and asset.get("mw"):
                info.append(T("mw_formula", f=asset["formula"], mw=asset["mw"]))
                if autofill_mw:
                    st["mw"] = round(asset["mw"], 2)
            if asset.get("drawing_from"):
                info.append(T("drawing_from", name=asset["drawing_from"]))
            info += asset.get("warnings") or []
            st["chem_info"] = "\n".join(info)
            st["chem_warn"] = bool(asset.get("warnings"))
            if g == self.current:
                self.apply_series_widgets()
            if render:
                self.render()

        self.run(work, done, sync)

    def choose_photo(self):
        if not self.current:
            return self.error(T("load_first"))
        p, _ = QFileDialog.getOpenFileName(self, T("dlg_photo"), self.settings.value("last_img_dir", ""),
                                           f"{T('flt_photo')};;{T('flt_all')}")
        if p:
            self.settings.setValue("last_img_dir", str(Path(p).parent))
            self.set_photo(p)

    def bg_changed(self):
        if self._loading or not self.current:
            return
        st = self.series[self.current]
        st["bg"] = self.cmb_bg.currentData()
        if st["photo"]:
            self.set_photo(st["photo"])

    def ensure_model(self):
        """Fragt nach dem Modell-Download. True = ISNet nutzbar."""
        if IMG.model_path(existing_only=True):
            return True
        try:
            import onnxruntime  # noqa: F401
        except ImportError:
            return False
        if os.environ.get("QT_QPA_PLATFORM") == "offscreen" and not getattr(self, "_allow_download", False):
            return False
        if not getattr(self, "_allow_download", False):
            ans = QMessageBox.question(self, T("model_q_title"), T("model_q", mb=IMG.MODEL_SIZE_MB))
            if ans != QMessageBox.Yes:
                return False
        dlg = QProgressDialog(T("downloading"), T("cancel"), 0, 100, self)
        dlg.setWindowModality(Qt.WindowModal)
        dlg.show()

        def prog(done, total):
            dlg.setValue(int(100 * done / max(total, 1)))
            QApplication.processEvents()
            return not dlg.wasCanceled()
        try:
            IMG.download_model(prog)
            return True
        except Exception as e:
            self.log_signal.emit(str(e))
            return False
        finally:
            dlg.close()

    def set_photo(self, path, g=None, render=True, sync=False):
        g = g or self.current
        st = self.series[g]
        if path is None:
            st.update(photo=None, photo_asset=None)
            self.apply_series_widgets()
            return self.render()
        method = st["bg"]
        if method in ("auto", "isnet") and not self.ensure_model():
            method = "grabcut" if method == "isnet" else "auto"
        cache = Path(self.csv_path).parent / ".uvvis_cache" if self.csv_path else None

        def done(asset):
            st["photo"], st["photo_asset"] = str(path), asset
            self.log_signal.emit(f"  {Path(path).name}: {asset.get('bg_method')}")
            if g == self.current:
                self.apply_series_widgets()
            if render:
                self.render()

        self.run(lambda: IMG.load_photo(path, method, cache), done, sync)

    def run(self, fn, done, sync=False):
        if sync:
            try:
                done(fn())
            except Exception as e:
                self.error(str(e))
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        self.statusBar().showMessage(T("working"))
        t = Task(fn, self)
        self._tasks.append(t)

        def fin():
            QApplication.restoreOverrideCursor()
            self.statusBar().clearMessage()
            self._tasks.remove(t)
        t.done.connect(done)
        t.failed.connect(self.error)
        t.finished.connect(fin)
        t.start()

    # ------------------------------------------------------------ Plot
    def make_cfg(self, g):
        gl = self.glob
        st = self.series[g]
        cfg = core.deep_merge(core.DEFAULTS, {})
        cfg["_base_dir"] = Path(self.csv_path).parent
        cfg["conc_unit"] = self.units[g]
        cfg["molar_mass_g_mol"] = st["mw"]
        cfg["path_length_cm"] = gl["path_length"]
        cfg["max_abs_fit"] = gl["cutoff"]
        cfg["min_fit_points"] = gl["min_points"]
        try:
            bands = [float(x) for x in gl["bands"].replace(";", ",").split(",") if x.strip()]
        except ValueError:
            bands = []
        cfg["wavelengths_nm"] = bands or "auto"
        if gl["baseline"] == "off":
            cfg["baseline_nm"] = None
        elif gl["baseline"] == "manual":
            cfg["baseline_nm"] = [gl["bl_a"], gl["bl_b"]]
        else:
            cfg["baseline_nm"] = "auto"
            cfg["baseline_mode"] = gl["baseline"]
        cfg["ylim"] = [0, gl["ymax"]]
        if not gl["x_auto"] and gl["x_max"] > gl["x_min"]:
            cfg["xlim"] = [gl["x_min"], gl["x_max"]]
        cfg["r2_mode"] = gl["r2"]
        cfg["labels"]["show_error"] = gl["show_err"]
        cfg["inset"]["table"] = gl["table"]
        cfg["figsize_in"] = list(FIGSIZE)
        if gl["size"] != "std":
            core.apply_export_size(cfg, gl["w_cm"], gl["h_cm"])
        fmts = [e for e, on in (("pdf", gl["fmt_pdf"]), ("svg", gl["fmt_svg"]), ("png", gl["fmt_png"])) if on]
        cfg["extra_formats"] = fmts[1:]
        cfg["_main_fmt"] = fmts[0] if fmts else "pdf"
        imgs = []
        if st["structure_asset"]:
            imgs.append({"file": st["structure"], "id": "struktur", "width": st.get("struct_w", 17) / 100,
                         "prefer": "top",
                         "_asset": st["structure_asset"]})
        if st["photo_asset"]:
            imgs.append({"file": st["photo"], "id": "kuevette", "width": st.get("photo_w", 9) / 100,
                         "prefer": "right",
                         "_asset": st["photo_asset"]})
        cfg["images"] = imgs
        return cfg

    def render(self):
        if not self.current or self.current not in self.groups:
            return
        g = self.current
        try:
            cfg = self.make_cfg(g)
            core.setup_fonts(plt, cfg)
            cfg2, spectra, results = core.prepare_series(cfg, self.groups[g], g)
            if self.dragger:
                self.dragger.disconnect()
                self.dragger = None
            wpx, hpx = int(cfg2["figsize_in"][0] * PREVIEW_DPI), int(cfg2["figsize_in"][1] * PREVIEW_DPI)
            if (self.canvas.width(), self.canvas.height()) != (wpx, hpx):
                self.canvas.setFixedSize(wpx, hpx)
                QApplication.processEvents()
            self.F = core.build_figure(plt, cfg2, spectra, results, self.get_layout(g), fig=self.fig)
            self.dragger = GuiDragger(self.F, self.layout_changed)
            self.sync_image_sizes(self.F.current_layout())
            self.canvas.draw_idle()
            self.fill_table(results, cfg2)
            self._last = (cfg2, results)
        except Exception as e:
            self.log_signal.emit(traceback.format_exc())
            self.statusBar().showMessage(f"{T('err_title')}: {e}", 8000)

    def size_key(self):
        gl = self.glob
        return "std" if gl["size"] == "std" else f"{gl['w_cm']:g}x{gl['h_cm']:g}"

    def get_layout(self, g):
        lay = self.series[g]["layout"] or {}
        if lay and not all(isinstance(v, dict) for v in lay.values()):
            lay = {"std": lay}                       # altes Format (eine Größe)
            self.series[g]["layout"] = lay
        return lay.setdefault(self.size_key(), {})

    def layout_changed(self, layout):
        if not self.current or self.F is None:
            return
        stored = self.get_layout(self.current)
        if layout != stored:
            self.series[self.current]["layout"][self.size_key()] = layout
        self.sync_image_sizes(layout)

    def sync_image_sizes(self, layout):
        """Größenfelder an die tatsächliche Bildgröße anpassen (Mausrad, automatisches Verkleinern)."""
        st = self.series.get(self.current)
        if not st:
            return
        self._loading = True
        for key, field, spin in (("image_struktur", "struct_w", self.sp_struct_w),
                                 ("image_kuevette", "photo_w", self.sp_photo_w)):
            if key in layout and len(layout[key]) == 4:
                st[field] = round(layout[key][2] * 100, 1)
                spin.setValue(st[field])
        self._loading = False

    def image_size_changed(self, iid, value):
        """Größe aus dem Zahlenfeld: Breite setzen, Mittelpunkt und Seitenverhältnis behalten."""
        if self._loading or not self.current:
            return
        st = self.series[self.current]
        st["struct_w" if iid == "struktur" else "photo_w"] = value
        lay = self.get_layout(self.current)
        key = f"image_{iid}"
        if key in lay and len(lay[key]) == 4:
            x, y, w, h = lay[key]
            nw = value / 100
            nh = h * nw / w
            nx = min(max(x + (w - nw) / 2, 0.0), max(0.0, 1 - nw))     # in der Achse halten
            ny = min(max(y + (h - nh) / 2, 0.0), max(0.0, 1 - nh))
            lay[key] = [nx, ny, nw, nh]
        self.timer.start()

    def reset_layout(self):
        if self.current:
            self.get_layout(self.current)
            self.series[self.current]["layout"][self.size_key()] = {}
            self.render()

    def fill_table(self, results, cfg):
        sym = "ε [M⁻¹ cm⁻¹]" if core.conc_factor(cfg) else "a [L g⁻¹ cm⁻¹]"
        self.table.setHorizontalHeaderLabels([T("col_lam"), T("col_n"), sym, T("col_intercept"),
                                              T("col_r2"), T("col_warn")])
        self.table.setRowCount(len(results))
        for i, r in enumerate(results):
            ft = r["fit"]
            if ft:
                v, e = core.fmt_ve(r["eps"], r["eps_err"], max_decimals=core.eps_max_decimals(cfg))
                b, be = core.fmt_ve(ft["intercept"], ft["se_intercept"])
                cells = [f"{r['lam']:g}", str(ft["n"]), f"{v} ± {e}" if e else v,
                         f"{b} ± {be}" if be else b, f"{ft['r2']:.5f}", "; ".join(r["warnings"])]
            else:
                cells = [f"{r['lam']:g}", str(len(r["used"])), "–", "–", "–",
                         T("no_fit", n=len(r["used"]), cut=cfg["max_abs_fit"], min=cfg["min_fit_points"])]
            for j, c in enumerate(cells):
                it = QTableWidgetItem(c)
                if j < 5:
                    it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(i, j, it)
        self.table.resizeColumnsToContents()

    # ------------------------------------------------------------ Export
    def export_dialog(self):
        if not self.csv_path:
            return self.error(T("load_first"))
        start = self.settings.value("last_export_dir", str(Path(self.csv_path).parent))
        d = QFileDialog.getExistingDirectory(self, T("dlg_export"), start)
        if d:
            self.settings.setValue("last_export_dir", d)
            out = self.export_all(Path(d))
            QMessageBox.information(self, T("btn_export"), T("exported_to", p="\n".join(map(str, out))))

    def export_all(self, folder: Path):
        """Alle Serien mit ihren Einstellungen/Layouts exportieren (PDF, PNG, CSV)."""
        self.collect_globals()
        stem = Path(self.csv_path).stem
        written = []
        for g in self.groups:
            cfg = self.make_cfg(g)
            core.setup_fonts(plt, cfg)
            cfg2, spectra, results = core.prepare_series(cfg, self.groups[g], g)
            name = f"{stem}_{g}" if len(self.groups) > 1 else stem
            cfg2["output"] = str(folder / f"{name}.{cfg2['_main_fmt']}")
            fig = MplFigure(figsize=cfg2["figsize_in"], dpi=PREVIEW_DPI)
            FigureCanvasAgg(fig)
            F = core.build_figure(plt, cfg2, spectra, results, self.get_layout(g), fig=fig)
            F.export()
            core.write_results(results, folder / f"{name}_results.csv", cfg2)
            written += [folder / f"{name}.{e}" for e in [cfg2["_main_fmt"]] + cfg2["extra_formats"]]
            written.append(folder / f"{name}_results.csv")
        self.save_project()
        return written

    # ------------------------------------------------------------ Drag & Drop
    def dragEnterEvent(self, ev):
        if ev.mimeData().hasUrls():
            ev.acceptProposedAction()

    def dropEvent(self, ev):
        files = [u.toLocalFile() for u in ev.mimeData().urls()]
        data = [p for p in files if Path(p).suffix.lower() in {".csv", ".txt"} | core.BINARY_EXT]
        if data:
            self.open_files(data)                     # mehrere Messdateien = ein Datensatz
        for p in files:
            ext = Path(p).suffix.lower()
            if p in data:
                continue
            if not self.current:
                self.error(T("load_first"))
            elif ext in IMG.CHEM_EXT | IMG.VECTOR_EXT:
                self.set_structure(p)
            elif ext in IMG.RASTER_EXT:
                self.set_photo(p)

    # ------------------------------------------------------------ Diverses
    def error(self, msg):
        self.log_signal.emit(f"{T('err_title')}: {msg}")
        if os.environ.get("QT_QPA_PLATFORM") != "offscreen":
            QMessageBox.critical(self, T("err_title"), str(msg))

    def _load_state(self, key):
        try:
            return yaml.safe_load(self.settings.value(key, "") or "") or {}
        except Exception:
            return {}

    def rebuild_tabs(self):
        self.build_ui()
        self.render()

    def export_current(self):
        i = self.main_tabs.currentIndex()
        if i == 1:
            return self.ov_tab.export_dialog()
        if i == 2:
            return self.fl_tab.export_dialog()
        return self.export_dialog()

    def info(self, msg):
        self.log_signal.emit(msg)
        if os.environ.get("QT_QPA_PLATFORM") != "offscreen":
            QMessageBox.information(self, T("app_title"), msg)

    def closeEvent(self, ev):
        for key, st in (("overlay_state", self.ov_state), ("fluo_state", self.fl_state)):
            self.settings.setValue(key, yaml.safe_dump(st, allow_unicode=True))
        self.save_project()
        self.settings.setValue("geometry", self.saveGeometry())
        super().closeEvent(ev)


# ----------------------------------------------------------------------------
# Selbsttest (für CI und nach der Installation)
# ----------------------------------------------------------------------------
def make_selftest_inputs(d: Path):
    """Synthetische Cary-CSV (2 Serien), CDXML und Küvettenfoto (HEIC, falls möglich)."""
    from PIL import Image, ImageDraw
    d.mkdir(parents=True, exist_ok=True)
    wl = np.arange(1100.0, 199.0, -1.0)
    bands = {"TEST-A": [(262, 6.8, 20), (484, 1.6, 30), (732, 0.25, 40), (816, 0.24, 40)],
             "TEST-B": [(255, 7.3, 18), (351, 2.7, 20), (444, 3.5, 12), (719, 0.42, 35), (804, 0.41, 35)]}
    concs = [("1", 1.0), ("0p5", 0.5), ("0p25", 0.25), ("0p125", 0.125), ("0p0625", 0.0625)]
    rng = np.random.default_rng(0)
    cols, names = [], []
    for ser, bl in bands.items():
        a = sum(h * np.exp(-0.5 * ((wl - l) / w) ** 2) for l, h, w in bl)
        for tag, c in concs:
            names.append(f"{ser}-{tag}mgml_THF")
            y = np.minimum(a * c, 4.0) - 0.03 + rng.normal(0, 0.002, wl.size)
            cols.append(y)
    lines = ["".join(f"{n},," for n in names), "".join("Wavelength (nm),Abs," for _ in names)]
    for i, x in enumerate(wl):
        lines.append("".join(f"{x:.6f},{y[i]:.8f}," for y in cols))
    lines += ["", "TEST-A-1mgml_THF", "Instrument  Cary 60"]
    (d / "selftest.csv").write_text("\r\n".join(lines), encoding="utf-8", newline="")
    nodes = [(1, 100, 100, 6), (2, 112.5, 92.8, 6), (3, 125, 100, 6), (4, 125, 114.4, 6),
             (5, 112.5, 121.6, 6), (6, 100, 114.4, 7), (7, 112.5, 78.4, 8)]
    bonds = [(1, 2, 2), (2, 3, 1), (3, 4, 2), (4, 5, 1), (5, 6, 2), (6, 1, 1), (2, 7, 1)]
    xml = ['<?xml version="1.0" encoding="UTF-8" ?><CDXML BondLength="14.40"><page id="1"><fragment id="99">']
    xml += [f'<n id="{i}" p="{x} {y}"' + (f' Element="{e}"' if e != 6 else "") + "/>" for i, x, y, e in nodes]
    xml += [f'<b id="{20 + k}" B="{b}" E="{e}"' + (' Order="2"' if o == 2 else "") + "/>"
            for k, (b, e, o) in enumerate(bonds)]
    xml += ["</fragment></page></CDXML>"]
    (d / "pyridinol.cdxml").write_text("".join(xml), encoding="utf-8")
    im = Image.new("RGB", (600, 900), (190, 185, 175))
    dr = ImageDraw.Draw(im)
    dr.rectangle([240, 100, 360, 200], fill=(25, 25, 25))
    dr.rectangle([220, 200, 380, 820], fill=(215, 220, 228))
    dr.rectangle([235, 420, 365, 805], fill=(195, 90, 35))
    photo = d / "kuevette.png"
    try:
        import pillow_heif
        pillow_heif.register_heif_opener()
        im.save(d / "kuevette.heic", quality=90)
        photo = d / "kuevette.heic"
    except Exception:
        im.save(photo)
    return d / "selftest.csv", d / "pyridinol.cdxml", photo


def selftest(outdir, with_isnet=False):
    out = Path(outdir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    report = [f"{APP_NAME} {APP_VERSION} selftest", f"python {sys.version.split()[0]}, {sys.platform}"]
    ok = True
    app = QApplication.instance() or QApplication(sys.argv[:1])  # noqa: F841
    try:
        csv, cdxml, photo = make_selftest_inputs(out / "input")
        report.append(f"photo format: {photo.suffix}")
        w = MainWindow()
        w._allow_download = with_isnet
        w.open_csv(csv)
        assert set(w.groups) == {"TEST-A", "TEST-B"}, w.groups
        w.set_structure(str(cdxml), "TEST-A", render=False, sync=True)
        st = w.series["TEST-A"]
        report.append(f"CDXML: {st['chem_info']!r}")
        assert st["mw"] and abs(st["mw"] - 95.10) < 0.05, st["mw"]      # 3-Hydroxypyridin C5H5NO
        w.series["TEST-A"]["bg"] = "isnet" if with_isnet else "grabcut"
        w.set_photo(str(photo), "TEST-A", render=False, sync=True)
        bgm = st["photo_asset"]["bg_method"]
        report.append(f"background: {bgm}")
        if with_isnet:
            assert bgm == "isnet", bgm
        w.render()
        files = w.export_all(out)
        for f in files:
            assert f.exists() and f.stat().st_size > 200, f
        import pymupdf
        page = pymupdf.open(str(out / "selftest_TEST-A.pdf"))[0]
        report.append(f"pdf: {len(page.get_drawings())} vector paths, {len(page.get_images())} images")
        assert page.get_images(), "photo missing in PDF"
        svg = (out / "selftest_TEST-A.svg").read_text(encoding="utf-8")
        assert "structure_0" in svg and "<image" in svg, "SVG ohne Struktur/Foto"
        report.append(f"pdf size: {page.rect.width / 72 * 2.54:.2f} x {page.rect.height / 72 * 2.54:.2f} cm")
        # Probennamen ohne Konzentration (z. B. c0..c4) -> Overrides wie aus dem Dialog
        txt = csv.read_text(encoding="utf-8").splitlines()
        n_samples = len([n for n in txt[0].split(",") if n])
        txt[0] = "".join(f"c{i},," for i in range(n_samples))
        plain = out / "input" / "unnamed.csv"
        plain.write_text("\r\n".join(txt), encoding="utf-8", newline="")
        assert w.open_csv(plain, ask=False) is False                 # ohne Angaben: nichts
        w.conc = {f"c{i}": {"conc": 1.0 / 2 ** i, "unit": "mg/mL", "series": "unbenannt"}
                  for i in range(5)}
        assert w.rebuild_groups() and "unbenannt" in w.groups, w.groups
        assert len(w.groups["unbenannt"]) == 5
        w.render()
        w.save_project()
        assert w.open_csv(plain, ask=False) and "unbenannt" in w.groups   # aus Projekt geladen
        report.append("unnamed samples: OK")
        # Einzelmessungen in getrennten Dateien + Cary-Binärdatei (.DSW)
        import struct
        singles = []
        for i, s_ in enumerate(core.read_samples([csv])[:5]):
            f = out / "input" / f"single_{i}.csv"
            f.write_text("\r\n".join([f"{s_['name']},,", "Wavelength (nm),Abs,"] +
                                      [f"{a:.4f},{b:.6f}," for a, b in zip(s_["x"], s_["y"])]),
                         encoding="utf-8", newline="")
            singles.append(f)
        assert w.open_files(singles, ask=False) and len(w.groups["TEST-A"]) == 5, w.groups
        magic = b"Varian UV-VIS Spectrophotometer"
        blob = bytearray([len(magic)]) + magic
        blob += bytes(0x400 - len(blob))
        for k in range(3):
            blk = bytearray(256)
            t = f"DSW-T-{0.5 / 2 ** k:g}".replace(".", "p").encode() + b"mgml"
            blk[:len(t)] = t
            blob += blk
            for x in np.arange(800.0, 249.0, -1.0):
                blob += struct.pack("<ff", x, 0.4 / 2 ** k * np.exp(-((x - 450) / 40) ** 2))
            blob += bytes(64)
        dsw = out / "input" / "test.DSW"
        dsw.write_bytes(bytes(blob))
        assert w.open_files([dsw], ask=False) and len(w.groups.get("DSW-T", [])) == 3, w.groups
        report.append("multiple files + DSW: OK")
        # Overlay (Messung + TD-DFT) und Fluoreszenz
        orca = out / "input" / "orca.out"
        orca.write_text("\n".join([
            "-" * 77, "         ABSORPTION SPECTRUM VIA TRANSITION ELECTRIC DIPOLE MOMENTS", "-" * 77,
            "State   Energy    Wavelength  fosc         T2        TX        TY        TZ",
            "        (cm-1)      (nm)                 (au**2)    (au)      (au)      (au)", "-" * 77,
            "   1   20660.0    484.0   0.150000000   1.00000   1.00000   0.00000   0.00000",
            "   2   38168.0    262.0   0.600000000   3.00000   1.70000   0.00000   0.00000", ""]),
            encoding="utf-8")
        assert len(__import__("uvvis_extra").parse_tddft(orca)["E"]) == 2
        w.ov_state["entries"] = [
            {"kind": "exp", "file": str(csv), "sample": "TEST-A-0p25mgml_THF", "label": "exp", "color": "#000000",
             "visible": True, "own_norm": False, "nlo": 450, "nhi": 520, "conc": 0.25, "unit": "mg/mL",
             "mw": 95.1, "d": 1.0},
            {"kind": "calc", "file": str(orca), "label": "calc", "color": "#1764e8", "visible": True,
             "own_norm": False, "nlo": 450, "nhi": 520, "fwhm": 0.3, "shift": 0.0}]
        w.ov_state.update(nlo=450, nhi=520)
        for mode in ("norm", "eps"):
            w.ov_state["mode"] = mode
            files = w.ov_tab.export_to(out / f"overlay_{mode}")
            assert all(f.exists() for f in files), files
        em = out / "input" / "emission.csv"
        xs = np.arange(400.0, 701.0, 1.0)
        em.write_text("\r\n".join(["EM ex352,,", "Wavelength (nm),Intensity (a.u.),"] +
                                    [f"{x:.1f},{500 * np.exp(-((x - 520) / 30) ** 2):.3f}," for x in xs]),
                      encoding="utf-8", newline="")
        w.fl_state.update(abs_file=str(csv), abs_sample="TEST-A-0p25mgml_THF", em_file=str(em),
                          em_sample="EM ex352", ex=352.0, alo=450, ahi=520, eps="1234",
                          photo_day=str(photo), bg_day="grabcut", photo_uv=str(photo), bg_uv="none")
        files = w.fl_tab.export_to(out / "fluorescence")
        assert all(f.exists() for f in files), files
        # Cary-Eclipse-CSV (Name in Zeile 2, λex aus den Metadaten)
        ecl = out / "input" / "eclipse.csv"
        ecl.write_text("\r\n".join(["Wavelength (nm),Intensity (a.u.),Z Axis,", ",PROBE-1-45p3µM", ",1"] +
                                     [f"{x:g},{300 * np.exp(-((x - 480) / 25) ** 2):.4f}" for x in xs] +
                                     ["", "PROBE-1-45p3µM", "Ex. Wavelength (nm)               387.00"]),
                       encoding="utf-8", newline="")
        es = core.read_samples([ecl])
        assert len(es) == 1 and es[0]["name"] == "PROBE-1-45p3µM" and es[0]["ex"] == 387.0, es[0]["name"]
        report.append("overlay + fluorescence + Eclipse CSV: OK")
        for lang in ("en", "de"):
            w.switch_lang(lang)
        report.append("OK")
    except Exception:
        ok = False
        report.append("FAILED\n" + traceback.format_exc())
    (out / "selftest_report.txt").write_text("\n".join(report), encoding="utf-8")
    print("\n".join(report))
    return 0 if ok else 1


# ----------------------------------------------------------------------------
def install_crash_handler():
    def hook(t, v, tb):
        msg = "".join(traceback.format_exception(t, v, tb))
        try:
            (IMG.app_data_dir() / "crash.log").write_text(msg, encoding="utf-8")
        except Exception:
            pass
        if QApplication.instance() and os.environ.get("QT_QPA_PLATFORM") != "offscreen":
            QMessageBox.critical(None, "Error", msg[-2000:])
        sys.__excepthook__(t, v, tb)
    sys.excepthook = hook


def main():
    if "--selftest" in sys.argv:
        i = sys.argv.index("--selftest")
        outdir = sys.argv[i + 1] if len(sys.argv) > i + 1 and not sys.argv[i + 1].startswith("--") \
            else "selftest_out"
        sys.exit(selftest(outdir, "--selftest-isnet" in sys.argv))
    install_crash_handler()
    QApplication.setApplicationName(APP_NAME)
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if args and Path(args[0]).exists():
        w.open_csv(args[0])          # Datei per Doppelklick / Drag auf das Programmsymbol
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
