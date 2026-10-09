# CLAUDE.md – UVVisTool

PySide6-Desktop-App (Windows wichtigste Plattform, dazu macOS arm64 und Linux) für UV-Vis-Verdünnungsreihen:
Lambert-Beer-Auswertung (ε bzw. a) und Abbildung im Origin-Stil (Spektren, λ/ε-Labels, Inset mit Regression
und Tabelle, ChemDraw-Struktur, Küvettenfoto). Dazu Tabs für Overlay (gemessen + TD-DFT) und Fluoreszenz.
Öffentliches Repo, AGPL-3.0. Maintainer: Robin (Chemiker, kein Softwareentwickler; Git-Einsteiger).

## Zusammenarbeit
- Antworten auf Deutsch, direkt und technisch präzise. Aussagen mit [Certain]/[Likely]/[Guessing] kennzeichnen.
- Keine Zustimmungsfloskeln. Wenn ein Wunsch fachlich fragwürdig ist (z. B. Statistik), das zuerst sagen,
  dann umsetzen.
- Git-Schritte (commit, tag, push, Release) kurz erklären und vor dem Push bestätigen lassen.
- Testdaten des Nutzers sind unveröffentlicht oder gehören Studierenden: **nie** CSV/DSW/BSW/HEIC/CDXML/ORCA-Ausgaben
  committen (siehe `.gitignore`). Keine Probennummern in README/CHANGELOG.

## Fachliche Regeln (nicht ändern ohne Rückfrage)
- ε (M⁻¹ cm⁻¹) **nie mit Nachkommastellen** anzeigen; Rundung auf die Genauigkeit des Standardfehlers
  (`core.fmt_ve`, `eps_max_decimals`). Sehr kleine Fehler auf 1 Einheit aufrunden, nie „± 0“.
- Fit: A/d = m·c + b (OLS); ε = m / f_c (f_c: mM 1e-3, µM 1e-6, M 1; mg/mL über die Molmasse; ohne Molmasse
  spezifischer Koeffizient a in L g⁻¹ cm⁻¹). 95-%-KI = t(0,975; n−2)·SE (eigene `t_quantile`).
- Cutoff global (Standard A = 1) und pro Bande; Banden mit R² < `min_r2` (einstellbar, Standard 0,98) stehen in
  Tabelle/CSV/Excel, aber nicht im Bild. Bei 4 Punkten ist R² wenig aussagekräftig, KI zählt.
- Konzentrationsdialog: **keine** vorbelegte Einheit/Startkonzentration (führte früher zu falschem ε).
- ChemDraw-Struktur **unverändert** übernehmen: gleichnamige SVG/PDF/PNG neben der CDXML hat Vorrang; RDKit
  (ACS1996-Modus, keine eigene Bindungslänge) nur als Fallback. Bilder behalten immer ihr Seitenverhältnis
  (gespeichert wird nur die Breite).
- „(sh)“ für Schultern ist abschaltbar; Molmasse aus CDXML inkl. Isotopen.
- TD-DFT: Gauß-Verbreiterung in Energie; Kurve und Sticks teilen **immer einen** Skalierungsfaktor
  (Modi `band` Standard, `max`, `faxis`). ORCA 5/6-Zustandslabels („0-1A -> 1-1A“) nach „->“ splitten; SOC-Tabelle.
- Export: Standard 16 × 11 cm (halbe A4-Seite in Word, zwei Abbildungen pro Seite), minimale Ränder; PDF/SVG
  vektoriell, Text in SVG als Pfade. Exporte überschreiben im Projektordner unter `exports/…`.
- UI zweisprachig: jeder sichtbare Text über `uvvis_i18n.T(key)` mit DE **und** EN-Eintrag.

## Architektur
| Datei | Inhalt |
|---|---|
| `uvvis_gui.py` | Hauptfenster, ε-Tab, Projektlogik, Undo/Redo (JSON-Snapshots von `get_state`), Autosave, `selftest()`. `APP_VERSION` steht hier. |
| `uvvis_core.py` | `DEFAULTS`, Reader (Cary CSV, DSW/BSW/FBSW via `parseuv_lite`, Eclipse CSV), Basislinie, Peak-/Schultersuche, `linfit`, `evaluate`, `Figure` (Platzierung über FreeSpace-Raster, gespeicherte Positionen zuerst reservieren), Export, `Dragger`. |
| `uvvis_tabs.py` | `CanvasHost` (Vorschau maßstabsgetreu, dynamische DPI), Overlay- und Fluoreszenz-Tab. |
| `uvvis_extra.py` | TD-DFT-Parser (ORCA/Gaussian), Verbreiterung, `SimpleFigure`, Fotopaar mit Pfeil. |
| `uvvis_images.py` | Bilder laden (HEIC, EXIF), Hintergrund entfernen (ISNet-ONNX → GrabCut → Rand), Struktur-Rendering (PyMuPDF), Vektor-Overlay in PDF/SVG. |
| `uvvis_chem.py` | CDXML über RDKit: Formel, Molmasse, Ersatzzeichnung. |
| `uvvis_project.py` | Projektordner (`project.uvvis`, `data/`, `exports/`), relative Pfade, Backup. |
| `uvvis_report.py` | Excel-Report (openpyxl): Werte blau, Kontrollformeln schwarz, native Diagramme; Sprache = Programmsprache. |
| `uvvis_i18n.py` | Texte DE/EN; `T(_key, **kw)` (Parameter heißt `_key`, damit `key=` als Format-Argument geht). |
| `parseuv_lite/` | Vendorte parseuv-1.0.4-Version (BSD-3), angepasst. |

## Befehle
```bash
pip install -r requirements.txt                       # Python 3.12 (wie CI)
python uvvis_gui.py                                   # App starten
QT_QPA_PLATFORM=offscreen python uvvis_gui.py --selftest selftest_out   # MUSS vor jedem Commit „OK“ melden
python build.py                                       # PyInstaller-Build (braucht: pip install pyinstaller)
```
- Neue Funktion → eigener Abschnitt im `selftest()` (Muster: `report.append("…: OK")`).
- Der Selbsttest läuft in CI auch mit der **fertig gebauten** App auf allen drei Systemen.

## Release-Ablauf
1. `APP_VERSION` in `uvvis_gui.py` erhöhen.
2. `CHANGELOG.md` **und** `CHANGELOG.de.md` ergänzen; bei sichtbaren Änderungen `README.md` **und** `README.de.md`.
3. Selbsttest, commit, dann `git tag vX.Y.Z && git push && git push --tags` → GitHub Actions baut und erstellt
   das Release. Kurze zweisprachige Release Notes (EN/DE) zum Reinkopieren liefern.

## Bekannte Fallen
- **Windows-Zeilenenden:** CSVs in Tests mit `newline=""` schreiben; Reader überspringt leere Zeilen
  (früher Windows-CI-Abbruch durch `\r\r\n`).
- **PyInstaller:** neue Imports, die nur lazy geladen werden, als `--hidden-import` in `build.py` eintragen.
- **MuPDF:** ignoriert SVG-Clip-Pfade → Kurven geometrisch clippen (`clip_polyline`); Rechtecke mit Breite 0
  fallen bei `|=` weg → Koordinaten-Union; Alpha ist premultipliziert → beim Einfärben un-premultiplizieren.
- **Label-Kollisionen:** gespeicherte Positionen von Labels, Inset und Bildern vor neuen Elementen reservieren.
- **Undo:** während `set_state` greift `_restoring`; Änderungen über `QTimer` verzögert erfassen.
- macOS-Build ist unsigniert (Gatekeeper: Systemeinstellungen → Datenschutz & Sicherheit → „Dennoch öffnen“).
  Trackpad-Zoom und HiDPI-Vorschau auf echter Mac-Hardware sind noch nicht verifiziert.

## Offene Punkte
- BSW-Datei mit Sprung in Spektrum 60 (CSV-Export zum Vergleich fehlt).
- Echte Gaussian-TD-DFT-Ausgabe noch nicht getestet (nur ORCA inkl. SOC).
