**English** | [Deutsch](README.de.md) · [Changelog](CHANGELOG.md)

# UVVisTool – UV-Vis analysis of dilution series

UVVisTool determines molar absorption coefficients (ε) from UV-Vis dilution series
(Beer–Lambert: A/d vs. c) and produces publication-ready figures in the classic Origin style:
spectra, λ/ε labels at the bands, an inset with the linear regressions and R², the chemical
structure (CDXML/SVG/PDF) and a photo of the cuvette with the background removed.
The user interface is available in German and English.

## Download and start

Download the file for your system from **Releases** (right-hand side of the repository page) and unzip it.

| System | File | Start |
|---|---|---|
| Windows | `UVVisTool-windows-x64.zip` | `UVVisTool\UVVisTool.exe` |
| macOS (Apple Silicon) | `UVVisTool-macos-arm64.zip` | `UVVisTool.app` |
| Linux | `UVVisTool-linux-x64.tar.gz` | `UVVisTool/UVVisTool` |

The app is not code-signed, so the operating system will warn you on first launch:

- **Windows (SmartScreen):** "More info" → "Run anyway".
- **macOS (Gatekeeper):** right-click `UVVisTool.app` → "Open" → "Open".

On Windows, always keep the whole `UVVisTool` folder together. The `.exe` does not work without the `_internal` folder next to it.

## Workflow

1. **Open data:** File → Open measurement data, or drag files onto the window. Cary CSV/TXT exports and the
   instrument's own **.DSW/.BSW** files are supported. **Several files at once** (e.g. each
   concentration measured separately) are combined into one data set.
2. **Concentrations:** Concentrations are read from the sample names, e.g.
   `ABC-1-0p5mgml_THF` → series `ABC-1`, 0.5 mg/mL. Recognised units are
   `mgml`/`mg_ml`/`mg/ml`, `mM`, `uM`/`µM`; `p` stands for the decimal point.
   - If the names contain no concentrations (e.g. `c0` … `c4`), a table opens where you enter them.
     Choose the **unit** explicitly (mM, µM, mg/mL, M) – nothing is pre-selected.
   - "Fill dilution series" fills the selected rows (or all of them) with start, start/factor, … from top to bottom.
     The start value always belongs to the **top** selected row (usually the stock solution).
   - Samples without a value, e.g. a blank, are ignored.
   - The "Series" column lets you split several compounds within one file.
   - You can change the values later with the **Concentrations…** button.
3. **Compound (per series):**
   - **Structure:** CDXML, SVG, PDF or an image file. With CDXML the **molar mass is calculated**
     automatically (isotopes such as D included); the formula is shown for checking. For the
     drawing to look **exactly as in ChemDraw**, also save the structure from ChemDraw as SVG, PDF
     or PNG with the same name next to the CDXML (e.g. `6g.cdxml` + `6g.svg`): the drawing is then
     taken unchanged from that file and the molar mass from the CDXML. Without such a file the
     drawing is regenerated (ACS 1996 style) and may differ from ChemDraw.
   - **Cuvette photo:** HEIC (iPhone), JPG, PNG and more. The background is removed automatically.
     On first use the app offers a one-time download (~180 MB) of the AI model.
   - **Molar mass:** only needed for concentrations in mg/mL. Filled in automatically from CDXML,
     otherwise enter it by hand. Without it the tool reports the specific absorption coefficient
     *a* in L g⁻¹ cm⁻¹ instead of ε, and the field is marked red. For mM/µM the molar mass is not used.
4. **Analysis:** set path length and fit cutoff. Bands are found automatically; additional bands
   (e.g. shoulders) can be entered as a list ("in addition to automatically found" keeps both), and
   **"Find shoulders automatically"** adds shoulders (in the figure optionally marked "(sh)").
   In the results table, the tick next to λ decides whether a band appears in the figure, and a
   double-click on **"Cutoff A"** sets an own cutoff for that band (e.g. to include a point just
   above A = 1). Bands with an own cutoff are highlighted; optionally, excluded points are shown as
   open symbols in the inset.
5. **Layout:**
   - **Drag** the inset, structure, cuvette and every λ/ε label with the mouse.
   - **Scroll** over the inset or an image to resize it, or use the "Size [% of plot width]" fields.
   - "Reset layout" restores the automatic arrangement.
6. **Export:** File → Export (or the button). This writes the chosen formats (PDF/SVG/PNG),
   `<series>_results.csv` and the Excel report for **all** series into the project (see below).

## Projects, export, undo

Everything happens in a **project folder**:

1. **File → New project…** – choose a folder or create a new one in the dialog.
2. Load measurements, structures, photos and TD-DFT files from anywhere – they are **copied into the
   project** (`data/`, `images/`; ChemDraw exports with the same name as a CDXML come along).
   Files that are already inside the project are not copied again.
3. Work as usual – the project is **saved automatically**. A backup `project.uvvis.bak` is made each
   time a project is opened.
4. **Export** writes directly into the project (existing files are overwritten):

```
MyProject/
  project.uvvis               settings (paths relative to the folder)
  data/  images/              copies of all input files
  exports/epsilon/<series>/   figures (PDF/SVG/PNG), <series>_results.csv, <series>_report.xlsx
  exports/overlay/            <project>_overlay.*
  exports/fluorescence/       <project>_fluorescence.*
```

The program starts without a project. Open projects via **File → Open project**, **Recent projects**
or by dragging the folder onto the window. **File → Save project copy** writes a complete copy (e.g.
an intermediate state). **Edit → Undo / Redo** (⌘Z / ⌘⇧Z, Ctrl+Z / Ctrl+Y) covers all tabs.

## Excel report

For every series, `<series>_report.xlsx` contains:

- **Summary:** parameters (unit, molar mass, path length, cutoffs, baseline window and per-sample
  offsets), results of all bands (slope, intercept, standard errors, R², ε ± SE, **95 % confidence
  interval** from the t-distribution) and the method with all equations.
- **Spectra:** A(λ) of all samples, baseline-corrected and raw, with chart.
- **One sheet per band:** data points, "in fit" flag (1/0, editable), the complete regression as
  **Excel formulas** (x̄, ȳ, Sxx, Sxy, m, b, RSS, s, SE, R², ε, t, CI) next to the tool's values with
  their difference, residuals and a chart (A/d vs c with regression line).

Blue numbers are measured values or tool results, black cells are formulas. Changing a flag in "in
fit" recalculates the band in Excel.

## Overlay tab

Compare several spectra in one figure, measured and calculated:

- **Measurement…** adds spectra from CSV/TXT/DSW/BSW files (one entry per sample);
  **TD-DFT…** adds ORCA (4–6) or Gaussian output files.
- TD-DFT transitions are broadened with Gaussians in energy (FWHM and an empirical energy shift
  can be set per calculation, default 0.3 eV); ε follows from the oscillator strengths
  (ε(ν̃) = 1.306·10⁸ · Σ f/σ · exp(−((ν̃−ν̃ᵢ)/σ)²), as in GaussView). Transitions can be shown as sticks.
- **y axis:** *normalised to band* – every spectrum is scaled to its maximum within the
  normalisation range (globally or per spectrum, e.g. if the calculated band is shifted), or
  **ε [10³ M⁻¹ cm⁻¹]** – measured spectra then need concentration (and molar mass for mg/mL) and
  path length.
- Per spectrum: colour, name, **line style and width**, **scale factor and vertical offset**
  (e.g. for stacked spectra); **order** with ↑/↓ (also the legend order).
- ORCA calculations with **spin–orbit coupling**: choose "with SOC" or "without SOC" per calculation.
- **Stick height:** "strongest stick = band maximum", "height of individual band" or
  "oscillator strength f" on a separate right axis.
- Structure with adjustable size; the legend is placed in free space and can be dragged.

## Fluorescence tab

Absorption and emission in one figure, as commonly shown in papers:

- Absorption (any UV-Vis file) and emission (Cary Eclipse CSV or .FBSW), both normalised to 1;
  λex is filled in automatically from the emission file;
  the absorption to the maximum within the "band of interest".
- Labels with λ of the absorption maximum (plus ε, if entered) and λem of the emission maximum.
- Optionally hide scattered light at λex and 2·λex.
- Two cuvette photos (daylight and under UV) are combined with an arrow and the excitation
  wavelength; for the UV photo background removal is off by default (dark background stays).
- Structure as in the ε tab.


## Figure size for Word

Under "Plot" → "Size":

- **Word: half A4 page (16 × 11 cm)** (default). The figure is built at exactly this size, with fonts,
  lines and layout scaled to match. Two figures with one-line captions fit on one A4 page with
  Word's default margins.
- **Custom:** width and height in cm, e.g. if your template uses different margins.
- **Standard:** larger format, tightly cropped.

In Word: Insert → Pictures → choose the SVG, then right-click → Insert Caption.
SVG works in Word 2019, 2021 and Microsoft 365. For older versions use the PNG (600 dpi).

In PDF and SVG the structure remains vector graphics. Text in the SVG is stored as paths, so it
looks identical everywhere but cannot be edited in Word.

## What happens automatically during the analysis

- **Baseline** ("automatic (series)", default): the window is placed where the most concentrated
  sample absorbs least. Only the part of the window value that does *not* scale with concentration
  (instrument/cuvette offset) is subtracted. A residual proportional to c is treated as real
  absorption and kept. "automatic (simple)" subtracts the full window value. The baseline always
  uses the full data range, independent of the displayed λ range.
- **Fit cutoff:** points above the cutoff (default A = 1.0) are excluded from the fit.
- **Bands:** found automatically within the displayed λ range, or entered as a list.
- **Rounding:** ε (M⁻¹ cm⁻¹) is never shown with decimals; it is rounded to the precision its
  standard error supports. The results CSV keeps the full values.
- **Warnings** (results table and log): fewer than 4 fit points, significant intercept (> 2σ),
  R² < 0.98 (then not shown in the figure), fewer than 3 points (then no ε at all).

## Notes on CDXML

- Exact ChemDraw appearance: put an SVG/PDF/PNG export with the same name next to the CDXML (see
  above). Otherwise the structure is redrawn via RDKit with the orientation preserved, but labels
  such as CD₃ or N₂ may be drawn differently (e.g. as explicit atoms).
- Molar mass = sum of all fragments (counter-ions are included).
- If abbreviations such as Dipp or Mes cannot be resolved, **no** molar mass is set and a warning is
  shown. Please enter it by hand in that case.
- Binary `.cdx` files are not supported. Save them as `.cdxml` in ChemDraw.

## Supported data

- **Cary CSV/TXT exports** (Agilent Cary 60 and others): first row = sample names, second row =
  `Wavelength (nm),Abs` per sample, followed by the data. Decimal comma and point are both
  recognised, and the instrument metadata at the end of the file is ignored. Simple two-column
  files work too; the file name is then used as the sample name.
- **Cary WinUV .DSW / .BSW** (binary files from the instrument software), read with the parser
  from the open-source project [parseuv](https://pypi.org/project/parseuv/). Instrument baseline
  records ("Baseline 100%T/0%T") in batch files are skipped.
- **Cary Eclipse** fluorescence data: CSV export and .FBSW files. The excitation wavelength is
  taken from the file's metadata.
- **Several files** can be opened together; they form one data set.

## Troubleshooting

- **Crash:** the details are written to `crash.log`:
  - Windows: `%LOCALAPPDATA%\UVVisTool`
  - macOS: `~/Library/Application Support/UVVisTool`
  - Linux: `~/.local/share/UVVisTool`
- **Self-test:** `UVVisTool --selftest <folder>` checks reading, CDXML, background removal and export,
  and writes `selftest_report.txt`.

---

## For maintainers: building and releasing

The apps are built by GitHub Actions (`.github/workflows/build.yml`) for Windows, macOS and Linux.
After each build the finished app runs a self-test on every system.

**New version via the web interface:**

1. Upload the changed files: "Add file" → "Upload files" → "Commit changes".
2. Click **Releases** → "Create a new release" → "Choose a tag" and type e.g. `v1.0.0` → "Create new tag" → "Publish release".
3. After about 20–40 minutes the three app files are attached to the release.

**Test build without a release:** Actions → "Build UVVisTool" → "Run workflow". The results appear
at the bottom of the run under "Artifacts", which are deleted after 90 days.

**Local:**

```
pip install -r requirements.txt pyinstaller
python uvvis_gui.py                    # start directly from source
python uvvis_gui.py --selftest out     # self-test
python build.py                        # build the app -> dist/
```

**Without a GUI:** `python uvvis_core.py measurement.csv` runs the analysis with default settings.

**Files:**

| File | Content |
|---|---|
| `uvvis_gui.py` | User interface (PySide6), self-test |
| `uvvis_core.py` | Import, baseline, band search, fits, plot layout, export |
| `uvvis_images.py` | Images, HEIC, background removal (ISNet/ONNX, GrabCut), SVG/PDF embedding |
| `uvvis_chem.py` | CDXML: drawing and molar mass (RDKit) |
| `uvvis_i18n.py` | German/English texts |
| `uvvis_tabs.py` | Overlay and fluorescence tabs |
| `uvvis_extra.py` | TD-DFT reading/broadening, photo pair, figure for the extra tabs |
| `uvvis_project.py` | Project folders (save/load, copying input files) |
| `uvvis_report.py` | Excel report (openpyxl) |
| `parseuv_lite/` | Reader for Cary .DSW/.BSW/.FBSW (from parseuv, BSD-3-Clause) |

**Data protection:** `.gitignore` excludes CSV, HEIC and CDXML files so that no unpublished
measurement data ends up in the repository.

## License

UVVisTool is licensed under the **GNU Affero General Public License v3.0** (see `LICENSE`).
It comes without any warranty.

The app bundles the following libraries under their own licenses:
PySide6/Qt (LGPL-3.0), PyMuPDF (AGPL-3.0), RDKit (BSD-3-Clause), matplotlib (Matplotlib License),
NumPy (BSD-3-Clause), Pillow (MIT-CMU), pillow-heif (BSD-3-Clause, contains libheif, LGPL-3.0),
OpenCV (Apache-2.0), ONNX Runtime (MIT), PyYAML (MIT), olefile (BSD-2-Clause), openpyxl (MIT).
The reader for .DSW/.BSW files in `parseuv_lite/` is taken from parseuv 1.0.4
(© 2026 Ricardo J. Fernández-Terán, BSD-3-Clause, see `parseuv_lite/LICENSE`).
The ISNet model for background removal (Apache-2.0) is downloaded on first use from the
rembg project and is not part of this repository.
