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
APP_VERSION = "1.0.0"

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
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDoubleSpinBox,  # noqa: E402
                               QFileDialog, QFormLayout, QGroupBox, QHBoxLayout,
                               QHeaderView, QLabel, QLineEdit, QMainWindow, QMessageBox,
                               QPlainTextEdit, QProgressDialog, QPushButton, QScrollArea,
                               QSpinBox, QSplitter, QTableWidget, QTableWidgetItem,
                               QTabWidget, QVBoxLayout, QWidget)

import uvvis_core as core  # noqa: E402
import uvvis_images as IMG  # noqa: E402
from uvvis_i18n import T, get_lang, set_lang  # noqa: E402

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
    def __init__(self, F, on_change):
        self.on_change = on_change
        super().__init__(F, None)

    def release(self, ev):
        moved = self.drag is not None
        super().release(ev)
        self.on_change(self.F.current_layout(), moved)

    def key(self, ev):
        pass


class MainWindow(QMainWindow):
    log_signal = Signal(str)

    def __init__(self):
        super().__init__()
        self.settings = QSettings(APP_NAME, APP_NAME)
        set_lang(self.settings.value("lang", "de"))
        self.csv_path = None
        self.groups, self.units = {}, {}
        self.series = {}               # je Serie: mw, structure, photo, bg, layout, assets
        self.current = None
        self.F = None
        self.dragger = None
        self._tasks = []
        self._loading = False
        self.glob = {"path_length": 1.0, "cutoff": 1.0, "min_points": 3, "bands": "",
                     "baseline": "series", "bl_a": 1050.0, "bl_b": 1100.0, "ymax": 1.0,
                     "r2": "legend", "show_err": False, "table": True}

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
        m.addAction(QAction(T("act_export"), self, shortcut="Ctrl+E", triggered=self.export_dialog))
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
        self.lbl_file = QLabel(Path(self.csv_path).name if self.csv_path else T("no_file"))
        self.lbl_file.setWordWrap(True)
        row.addWidget(self.lbl_file, 1)
        f.addRow(row)
        self.cmb_series = QComboBox()
        self.cmb_series.addItems(list(self.groups))
        if self.current:
            self.cmb_series.setCurrentText(self.current)
        self.cmb_series.currentTextChanged.connect(self.series_changed)
        f.addRow(T("series"), self.cmb_series)
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
        self.cmb_r2 = QComboBox()
        for key in ("legend", "label", "off"):
            self.cmb_r2.addItem(T({"legend": "r2_legend", "label": "r2_label", "off": "r2_off"}[key]), key)
        f.addRow(T("r2_mode"), self.cmb_r2)
        self.cb_err = QCheckBox(T("show_err"))
        self.cb_tab = QCheckBox(T("inset_table"))
        f.addRow(self.cb_err)
        f.addRow(self.cb_tab)
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
        self.setCentralWidget(split)

        self.apply_globals()
        self.apply_series_widgets()
        for w in (self.sp_d, self.sp_cut, self.sp_ymax, self.sp_bla, self.sp_blb):
            w.valueChanged.connect(self.changed)
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
                         table=self.cb_tab.isChecked())

    def apply_series_widgets(self):
        self._loading = True
        st = self.series.get(self.current)
        self.ed_mw.setText(f"{st['mw']:g}" if st and st["mw"] else "")
        self.lbl_struct.setText(Path(st["structure"]).name if st and st["structure"] else "–")
        self.lbl_photo.setText(Path(st["photo"]).name if st and st["photo"] else "–")
        self.cmb_bg.setCurrentIndex(self.cmb_bg.findData(st["bg"] if st else "auto"))
        self.lbl_chem.setText(st.get("chem_info", "") if st else "")
        self.lbl_chem.setStyleSheet("color: #b35900;" if st and st.get("chem_warn") else "")
        pa = st.get("photo_asset") if st else None
        self.lbl_thumb.setPixmap(rgba_to_pixmap(pa["rgba"]) if pa else QPixmap())
        self._loading = False

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
        p, _ = QFileDialog.getOpenFileName(self, T("dlg_open_csv"), start,
                                           f"{T('flt_csv')};;{T('flt_all')}")
        if p:
            self.open_csv(p)

    def open_csv(self, path):
        path = str(Path(path).resolve())
        try:
            groups, units = core.load_series(path)
        except Exception as e:
            self.error(str(e))
            return
        if not groups:
            self.error(T("no_conc_in_name", name=Path(path).name))
            return
        self.save_project()
        self.csv_path, self.groups, self.units = path, groups, units
        self.settings.setValue("last_dir", str(Path(path).parent))
        self.series = {g: {"mw": None, "structure": None, "photo": None, "bg": "auto", "layout": {},
                           "structure_asset": None, "photo_asset": None, "chem_info": "",
                           "chem_warn": False} for g in groups}
        self.load_project()
        self.lbl_file.setText(Path(path).name)
        self.current = next(iter(groups))
        self.cmb_series.blockSignals(True)
        self.cmb_series.clear()
        self.cmb_series.addItems(list(groups))
        self.cmb_series.blockSignals(False)
        self.apply_globals()
        self.apply_series_widgets()
        self.render()

    def project_file(self):
        return Path(self.csv_path).with_suffix(".uvvis.yaml") if self.csv_path else None

    def save_project(self):
        pf = self.project_file()
        if not pf:
            return
        self.collect_globals()
        data = {"global": self.glob,
                "series": {g: {k: st[k] for k in ("mw", "structure", "photo", "bg", "layout")}
                           for g, st in self.series.items()}}
        try:
            pf.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
        except OSError:
            pass

    def load_project(self):
        pf = self.project_file()
        if not pf or not pf.exists():
            return
        try:
            data = yaml.safe_load(pf.read_text(encoding="utf-8")) or {}
        except Exception:
            return
        self.glob.update(data.get("global") or {})
        for g, sd in (data.get("series") or {}).items():
            if g not in self.series:
                continue
            st = self.series[g]
            st.update({k: sd.get(k, st[k]) for k in ("mw", "bg", "layout")})
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
        cfg["r2_mode"] = gl["r2"]
        cfg["labels"]["show_error"] = gl["show_err"]
        cfg["inset"]["table"] = gl["table"]
        cfg["figsize_in"] = list(FIGSIZE)
        imgs = []
        if st["structure_asset"]:
            imgs.append({"file": st["structure"], "id": "struktur", "width": 0.17, "prefer": "top",
                         "_asset": st["structure_asset"]})
        if st["photo_asset"]:
            imgs.append({"file": st["photo"], "id": "kuevette", "width": 0.09, "prefer": "right",
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
            self.F = core.build_figure(plt, cfg2, spectra, results, self.series[g]["layout"], fig=self.fig)
            self.dragger = GuiDragger(self.F, self.layout_changed)
            self.canvas.draw_idle()
            self.fill_table(results, cfg2)
            self._last = (cfg2, results)
        except Exception as e:
            self.log_signal.emit(traceback.format_exc())
            self.statusBar().showMessage(f"{T('err_title')}: {e}", 8000)

    def layout_changed(self, layout, moved):
        if self.current and moved:
            self.series[self.current]["layout"] = layout

    def reset_layout(self):
        if self.current:
            self.series[self.current]["layout"] = {}
            self.render()

    def fill_table(self, results, cfg):
        sym = "ε [M⁻¹ cm⁻¹]" if core.conc_factor(cfg) else "a [L g⁻¹ cm⁻¹]"
        self.table.setHorizontalHeaderLabels([T("col_lam"), T("col_n"), sym, T("col_intercept"),
                                              T("col_r2"), T("col_warn")])
        self.table.setRowCount(len(results))
        for i, r in enumerate(results):
            ft = r["fit"]
            if ft:
                v, e = core.fmt_ve(r["eps"], r["eps_err"])
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
            cfg2["output"] = str(folder / f"{name}.pdf")
            fig = MplFigure(figsize=FIGSIZE, dpi=PREVIEW_DPI)
            FigureCanvasAgg(fig)
            F = core.build_figure(plt, cfg2, spectra, results, self.series[g]["layout"], fig=fig)
            F.export()
            core.write_results(results, folder / f"{name}_results.csv", cfg2)
            written += [folder / f"{name}.pdf", folder / f"{name}.png", folder / f"{name}_results.csv"]
        self.save_project()
        return written

    # ------------------------------------------------------------ Drag & Drop
    def dragEnterEvent(self, ev):
        if ev.mimeData().hasUrls():
            ev.acceptProposedAction()

    def dropEvent(self, ev):
        for url in ev.mimeData().urls():
            p = url.toLocalFile()
            ext = Path(p).suffix.lower()
            if ext in (".csv", ".txt"):
                self.open_csv(p)
            elif not self.current:
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

    def closeEvent(self, ev):
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
    (d / "selftest.csv").write_text("\r\n".join(lines), encoding="utf-8")
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
