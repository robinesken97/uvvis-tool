**English** | [Deutsch](CHANGELOG.de.md)

# Changelog

## 1.2.1 – 2026-10-06

### Added
- **Overlay:** a structure per spectrum, optionally drawn in the curve colour (SVG/CDXML as vector
  graphics, PNG/PDF as image).

### Changed
- **TD-DFT normalisation:** curve and sticks now always share one scale factor (each stick = height of
  its own Gaussian, the curve is their sum). Reference "curve maximum = 1" (new default) or "strongest
  transition = 1"; alternatively sticks as oscillator strength f on a right axis. In 1.2.0, the
  sticks were scaled independently of the curve in "strongest stick = band maximum" mode.

### Fixed
- Structures (CDXML, SVG, PDF) were cropped too tightly: bonds running exactly vertically or
  horizontally at the edge (e.g. =CH₂, CH₃) were cut off in figures and exports.
- Structures were distorted when their aspect ratio or the axes size changed (e.g. f axis switched on);
  only the width is stored now, the height always follows the image. Existing projects are corrected
  automatically.
- Structures drawn from CDXML without an export had too thin lines and too small labels.
- Coloured structures had dark edges.

## 1.2.0 – 2026-10-06

### Added
- **Project folders:** choose or create a folder first; every loaded file is copied into it, the project
  is saved automatically (backup `project.uvvis.bak` on opening), and exports go directly to
  `exports/epsilon/<series>/`, `exports/overlay/`, `exports/fluorescence/`. File → New / Open / Recent
  projects / Save project copy / Show project folder. The program starts without a project.
- **Excel report** per series: parameters, all results incl. 95 % confidence interval, method with
  equations, spectra, and one sheet per band with the full regression as Excel formulas next to the
  tool's values, residuals and native charts.
- **Undo / Redo** (⌘Z / ⌘⇧Z, Ctrl+Z / Ctrl+Y) across all tabs.
- **Overlay:** line style and width, scale factor and vertical offset per spectrum, order (↑/↓),
  structure size in %, legend placed in free space.
- **TD-DFT sticks:** "strongest stick = band maximum" (default), "height of individual band", or
  oscillator strength f on a separate right axis.
- ORCA **spin–orbit coupling** spectra; "with SOC" / "without SOC" selectable per calculation.
- ε tab: regression inset can be switched off (in addition to its table).
- Fluorescence tab: size fields for structure and photos.
- "(sh)" marking of shoulders in the figure is optional (off by default); table and Excel report keep it.

### Changed
- Results CSV has an additional column `ci95` (95 % confidence interval of ε).
- Settings are no longer stored as `.uvvis.yaml` files next to the measurement files, and the overlay/
  fluorescence tabs are no longer restored automatically at start – use project folders instead.

### Fixed
- ORCA output with spin–orbit coupling was read incorrectly (state labels such as "0-1.0A" were taken
  as numbers, giving wrong energies and oscillator strengths). Please reload such calculations.

## 1.1.0 – 2026-10-05

**Please check:** concentrations entered with 1.0.0 via the concentration dialog may have been
saved in mM without anyone choosing that unit. Open the file and check **Concentrations…**.

### Added
- **Overlay tab:** several measured spectra and TD-DFT spectra (ORCA 4–6, Gaussian) in one figure,
  in individual colours; normalised to a band of interest (globally or per spectrum) or as
  ε [10³ M⁻¹ cm⁻¹]. TD-DFT: Gaussian broadening (FWHM, energy shift), optional sticks.
- **Fluorescence tab:** absorption and emission normalised in one figure, with λ/ε and λem labels,
  optional masking of scattered light, and a daylight/UV photo pair with arrow and excitation
  wavelength. Set-ups of both new tabs are kept between sessions and can be saved/loaded.
- Reading of Cary WinUV **.DSW/.BSW** files and Cary Eclipse **.FBSW** files (parser from parseuv,
  BSD-3-Clause) and of Cary Eclipse CSV exports; λex is taken from the metadata.
- **Several data files at once** (e.g. each concentration measured separately) form one data set,
  also via drag & drop.
- Structure drawing **unchanged from ChemDraw**: an SVG/PDF/PNG export with the same name next to
  the CDXML is used for the drawing, the CDXML for the molar mass.
- **Shoulders:** optional automatic search (marked "(sh)"); manually entered bands can be added to
  the automatically found ones.
- **Per band:** own fit cutoff (e.g. to include a point just above A = 1) and choice whether the
  band appears in the figure – both in the results table. Excluded points can be shown as open
  symbols in the inset.
- **File → Start over** discards all saved inputs for the current file.
- Missing molar mass for concentrations in mg/mL is highlighted in red; a note explains when the
  molar mass is not used (mM/µM).

### Changed
- ε (M⁻¹ cm⁻¹) is never displayed with decimals.
- R² appears in the inset legend only if the inset table is not shown (the table already lists it).
- The molecular formula shows isotopes (e.g. D for deuterium); the molar mass already included them.

### Fixed
- Concentration dialog: unit and start value are no longer pre-filled (previously mM and 1.0).
- Spectra without signal in the normalisation range are skipped with a note instead of being
  scaled up from noise.

## 1.0.0 – 2026-10-04

First release.

- Import of Cary multi-sample CSV exports. Concentrations from sample names or entered in a table
  (with dilution-series helper).
- Automatic baseline correction, band search, Beer–Lambert fits with ε ± standard error, R²
  and warnings.
- Figures in Origin style with inset (regressions, R²), structure (CDXML/SVG/PDF; molar mass
  from CDXML) and cuvette photo (HEIC/JPG/PNG, automatic background removal).
- Inset, images and labels can be moved with the mouse and resized with the scroll wheel or
  size fields. Selectable wavelength range.
- Export as PDF/SVG (structure as vector graphics) and PNG. Fixed size for Word
  (16 × 11 cm = two figures per A4 page).
- User interface in German and English. Apps for Windows, macOS and Linux.
