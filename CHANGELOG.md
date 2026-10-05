**English** | [Deutsch](CHANGELOG.de.md)

# Changelog

## 1.0.1 – 2026-10-05

**Please check:** concentrations entered with 1.0.0 via the concentration dialog may have been
saved in mM without anyone choosing that unit (see first fix). Open the file and check
**Concentrations…**.

### Fixed
- Concentration dialog: the unit (previously mM) and the start value of the dilution series
  (previously 1.0) are no longer pre-filled. The dialog cannot be confirmed with concentrations
  but without a unit.

### Added
- **File → Start over:** discards all saved inputs for the current CSV (concentrations, molar
  masses, structures, photos, settings, layout) and starts from scratch.
- Missing molar mass for concentrations in mg/mL is now highlighted in red, with a note that
  *a* [L g⁻¹ cm⁻¹] is reported instead of ε.
- Note below the molar mass field when concentrations are given in mM/µM and the molar mass
  is therefore not used.

## 1.0.0 – 2026-10-04

First release.

- Import of Cary multi-sample exports. Concentrations from sample names or entered in a table
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
