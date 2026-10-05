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

1. **Open data:** File → Open CSV, or drag the CSV onto the window.
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
     automatically. The formula is shown for checking.
   - **Cuvette photo:** HEIC (iPhone), JPG, PNG and more. The background is removed automatically.
     On first use the app offers a one-time download (~180 MB) of the AI model.
   - **Molar mass:** only needed for concentrations in mg/mL. Filled in automatically from CDXML,
     otherwise enter it by hand. Without it the tool reports the specific absorption coefficient
     *a* in L g⁻¹ cm⁻¹ instead of ε, and the field is marked red. For mM/µM the molar mass is not used.
4. **Analysis:** set path length, fit cutoff and, if needed, the bands (empty = automatic).
5. **Layout:**
   - **Drag** the inset, structure, cuvette and every λ/ε label with the mouse.
   - **Scroll** over the inset or an image to resize it, or use the "Size [% of plot width]" fields.
   - "Reset layout" restores the automatic arrangement.
6. **Export:** File → Export (or the button). This writes the chosen formats (PDF/SVG/PNG) and
   `<name>_results.csv` for **all** series into a folder of your choice.

Settings, concentrations and layouts are stored next to the CSV in `<name>.uvvis.yaml` and
restored the next time you open the file. **File → Start over** discards all of them for the current
file and begins from scratch (the CSV itself is not changed).

**Language:** menu **Language** → Deutsch / English. The change takes effect immediately.
On macOS the menu is in the menu bar at the top of the screen, not in the window.
Axis labels in the figures are always English.

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
- **Rounding:** ε is rounded according to its standard error.
- **Warnings** (results table and log): fewer than 4 fit points, significant intercept (> 2σ),
  R² < 0.98 (then not shown in the figure), fewer than 3 points (then no ε at all).

## Notes on CDXML

- The orientation of the structure is preserved as in ChemDraw. It is redrawn in ACS 1996 style
  via RDKit. For the exact ChemDraw appearance export SVG or PDF from ChemDraw. If a `.cdxml` with
  the same name sits next to it, the molar mass is taken from that file.
- Molar mass = sum of all fragments (counter-ions are included).
- If abbreviations such as Dipp or Mes cannot be resolved, **no** molar mass is set and a warning is
  shown. Please enter it by hand in that case.
- Binary `.cdx` files are not supported. Save them as `.cdxml` in ChemDraw.

## Supported data

Cary multi-sample exports (Agilent Cary 60 and others): first row = sample names, second row =
`Wavelength (nm),Abs` per sample, followed by the data. Decimal comma and point are both recognised,
and the instrument metadata at the end of the file is ignored.

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

**Data protection:** `.gitignore` excludes CSV, HEIC and CDXML files so that no unpublished
measurement data ends up in the repository.

## License

UVVisTool is licensed under the **GNU Affero General Public License v3.0** (see `LICENSE`).
It comes without any warranty.

The app bundles the following libraries under their own licenses:
PySide6/Qt (LGPL-3.0), PyMuPDF (AGPL-3.0), RDKit (BSD-3-Clause), matplotlib (Matplotlib License),
NumPy (BSD-3-Clause), Pillow (MIT-CMU), pillow-heif (BSD-3-Clause, contains libheif, LGPL-3.0),
OpenCV (Apache-2.0), ONNX Runtime (MIT), PyYAML (MIT).
The ISNet model for background removal (Apache-2.0) is downloaded on first use from the
rembg project and is not part of this repository.
