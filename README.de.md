[English](README.md) | **Deutsch** · [Änderungen](CHANGELOG.de.md)

# UVVisTool – UV-Vis-Auswertung von Verdünnungsreihen

UVVisTool bestimmt molare Absorptionskoeffizienten (ε) aus UV-Vis-Verdünnungsreihen
(Lambert-Beer: A/d gegen c) und erzeugt publikationsfertige Abbildungen im gewohnten Origin-Stil:
Spektren, λ/ε-Labels an den Banden, ein Inset mit den linearen Regressionen und R², die Struktur
(CDXML/SVG/PDF) und ein freigestelltes Foto der Küvette. Die Oberfläche gibt es auf Deutsch und
Englisch.

## Herunterladen und starten

Lade unter **Releases** (rechts auf der Repository-Seite) die Datei für dein System herunter und entpacke sie.

| System | Datei | Starten |
|---|---|---|
| Windows | `UVVisTool-windows-x64.zip` | `UVVisTool\UVVisTool.exe` |
| macOS (Apple Silicon) | `UVVisTool-macos-arm64.zip` | `UVVisTool.app` |
| Linux | `UVVisTool-linux-x64.tar.gz` | `UVVisTool/UVVisTool` |

Die App ist nicht signiert, deshalb warnt das Betriebssystem beim ersten Start:

- **Windows (SmartScreen):** „Weitere Informationen“ → „Trotzdem ausführen“.
- **macOS (Gatekeeper):** Rechtsklick auf `UVVisTool.app` → „Öffnen“ → „Öffnen“.

Unter Windows immer den ganzen Ordner `UVVisTool` zusammenlassen. Die `.exe` funktioniert nicht ohne den Ordner `_internal` daneben.

## Ablauf

1. **Daten öffnen:** Datei → Öffnen, oder Dateien ins Fenster ziehen. Unterstützt werden
   Cary-CSV/TXT-Exporte und die gerätenahen **.DSW/.BSW**-Dateien. **Mehrere Dateien auf einmal**
   (z. B. jede Konzentration einzeln gemessen) werden zu einem Datensatz zusammengeführt.
2. **Konzentrationen:** Die Konzentrationen werden aus den Probennamen gelesen, z. B.
   `ABC-1-0p5mgml_THF` → Serie `ABC-1`, 0,5 mg/mL. Erkannt werden
   `mgml`/`mg_ml`/`mg/ml`, `mM`, `uM`/`µM`; `p` steht für das Dezimalkomma.
   - Stehen keine Konzentrationen im Namen (z. B. `c0` … `c4`), öffnet sich eine Tabelle zum Eintragen.
     Die **Einheit** (mM, µM, mg/mL, M) muss ausdrücklich gewählt werden, es ist nichts vorbelegt.
   - „Verdünnungsreihe ausfüllen“ setzt in die markierten Zeilen (oder alle) von oben nach unten Start, Start/Faktor, … ein.
     Der Startwert gehört immer zur **obersten** markierten Zeile (meist die Stammlösung).
   - Proben ohne Wert, z. B. eine Blindprobe, werden ignoriert.
   - Über die Spalte „Serie“ lassen sich mehrere Verbindungen in einer Datei trennen.
   - Später ändern geht über den Knopf **Konzentrationen…**.
3. **Verbindung (je Serie):**
   - **Struktur:** CDXML, SVG, PDF oder eine Bilddatei. Bei CDXML wird die **Molmasse automatisch
     berechnet** (Isotope wie D eingeschlossen), die Summenformel wird zur Kontrolle angezeigt.
     Damit die Zeichnung **exakt wie in ChemDraw** aussieht, die Struktur in ChemDraw zusätzlich
     als SVG, PDF oder PNG mit gleichem Namen neben die CDXML speichern (z. B. `6g.cdxml` +
     `6g.svg`). Die Zeichnung kommt dann unverändert aus dieser Datei, die Molmasse aus der CDXML.
     Ohne eine solche Datei wird die Struktur neu gezeichnet (ACS-1996-Stil) und kann von ChemDraw
     abweichen.
   - **Küvettenfoto:** HEIC (iPhone), JPG, PNG und weitere. Der Hintergrund wird automatisch entfernt.
     Beim ersten Mal bietet die App einen einmaligen Download des KI-Modells an (~180 MB).
   - **Molmasse:** nur bei Konzentrationen in mg/mL nötig. Wird aus der CDXML übernommen, sonst von
     Hand eintragen. Ohne Molmasse gibt das Tool den spezifischen Absorptionskoeffizienten *a* in
     L g⁻¹ cm⁻¹ statt ε aus, und das Feld wird rot markiert. Bei mM/µM wird die Molmasse nicht verwendet.
4. **Auswertung:** Schichtdicke, Fit-Cutoff und bei Bedarf die Banden eintragen (leer = automatisch).
5. **Layout:**
   - **Mit der Maus ziehen:** Inset, Struktur, Küvette und jedes λ/ε-Label lassen sich verschieben.
   - **Mausrad bzw. Trackpad** über Inset oder Bild ändert die Größe. Alternativ die Felder „Größe [% Plotbreite]“ nutzen.
   - „Layout zurücksetzen“ stellt die automatische Anordnung wieder her.
6. **Exportieren:** Datei → Exportieren (oder der Knopf). Das schreibt die gewählten Formate (PDF/SVG/PNG)
   und `<name>_results.csv` für **alle** Serien in einen wählbaren Ordner.

Einstellungen, Konzentrationen und Layouts werden neben der CSV in `<name>.uvvis.yaml` gespeichert
und beim nächsten Öffnen wiederhergestellt. **Datei → Neu beginnen** verwirft all das für die aktuelle
Datei und startet von vorn (die CSV selbst bleibt unverändert).

**Sprache:** Menü **Sprache** → Deutsch / English. Die Umstellung gilt sofort. Auf dem Mac steht das
Menü in der Menüleiste oben am Bildschirm, nicht im Fenster. Die Achsenbeschriftungen der Abbildungen
sind immer englisch.

## Overlay-Tab

Mehrere Spektren in einer Abbildung vergleichen, gemessen und berechnet:

- **Messung…** fügt Spektren aus CSV/TXT/DSW/BSW-Dateien hinzu (ein Eintrag pro Probe);
  **TD-DFT…** fügt Ausgabedateien von ORCA (4–6) oder Gaussian hinzu.
- TD-DFT-Übergänge werden mit Gaußfunktionen in der Energie verbreitert (Breite FWHM und eine
  empirische Energieverschiebung pro Rechnung einstellbar, Standard 0,3 eV); ε folgt aus den
  Oszillatorstärken (ε(ν̃) = 1,306·10⁸ · Σ f/σ · exp(−((ν̃−ν̃ᵢ)/σ)²), wie in GaussView). Übergänge
  lassen sich als Striche anzeigen.
- **y-Achse:** *normiert auf Bande* – jedes Spektrum wird auf sein Maximum im Normierungsbereich
  skaliert (global oder pro Spektrum, z. B. wenn die berechnete Bande verschoben ist), oder
  **ε [10³ M⁻¹ cm⁻¹]** – gemessene Spektren brauchen dann Konzentration (bei mg/mL auch Molmasse)
  und Schichtdicke.
- Farben und Namen in der Tabelle; die Legende lässt sich verschieben.

## Fluoreszenz-Tab

Absorption und Emission in einer Abbildung, wie in Publikationen üblich:

- Absorption (beliebige UV-Vis-Datei) und Emission (Cary-Eclipse-CSV oder .FBSW), λex wird aus der
  Emissionsdatei übernommen; beide auf 1
  normiert; die Absorption auf das Maximum in der „Bande von Interesse“.
- Labels mit λ des Absorptionsmaximums (plus ε, wenn eingetragen) und λem des Emissionsmaximums.
- Streulicht bei λex und 2·λex optional ausblenden.
- Zwei Küvettenfotos (Tageslicht und unter UV) werden mit Pfeil und Anregungswellenlänge
  kombiniert; beim UV-Foto ist die Freistellung standardmäßig aus (dunkler Hintergrund bleibt).
- Struktur wie im ε-Tab.

Overlay- und Fluoreszenz-Einstellungen bleiben zwischen den Sitzungen erhalten und lassen sich
als Datei speichern und laden.

## Abbildungsgröße für Word

Unter „Darstellung“ → „Größe“:

- **Word: halbe A4-Seite (16 × 11 cm)** (Standard). Die Abbildung wird exakt in dieser Größe gebaut,
  Schrift, Linien und Layout werden passend skaliert. Zwei Abbildungen mit einzeiliger
  Bildunterschrift passen bei Word-Standardrändern auf eine A4-Seite.
- **Benutzerdefiniert:** Breite und Höhe in cm, z. B. wenn eure Vorlage andere Ränder hat.
- **Standard:** größeres Format, eng zugeschnitten.

In Word: Einfügen → Bilder → SVG wählen, dann Rechtsklick → Beschriftung einfügen.
SVG funktioniert in Word 2019, 2021 und Microsoft 365. Bei älteren Versionen das PNG (600 dpi) nehmen.

In PDF und SVG bleibt die Struktur eine Vektorgrafik. Text steht im SVG als Pfade, sieht also
überall gleich aus, lässt sich in Word aber nicht bearbeiten.

## Was bei der Auswertung automatisch passiert

- **Basislinie** („automatisch (Reihe)“, Standard): Das Fenster liegt dort, wo die konzentrierteste
  Probe am wenigsten absorbiert. Abgezogen wird nur der Teil des Fensterwerts, der *nicht* mit der
  Konzentration skaliert (Geräte- bzw. Küvettenoffset). Ein zu c proportionaler Rest gilt als echte
  Absorption und bleibt erhalten. „automatisch (einfach)“ zieht den kompletten Fensterwert ab.
  Die Basislinie nutzt immer den vollen Datenbereich, unabhängig vom dargestellten λ-Bereich.
- **Fit-Cutoff:** Punkte oberhalb des Cutoffs (Standard A = 1,0) gehen nicht in den Fit ein.
- **Banden:** automatisch im dargestellten λ-Bereich gesucht oder als Liste vorgegeben.
- **Rundung:** ε (M⁻¹ cm⁻¹) erscheint nie mit Nachkommastellen; gerundet wird auf die Genauigkeit,
  die sein Standardfehler hergibt. Die Ergebnis-CSV enthält die vollen Werte.
- **Warnungen** (Ergebnistabelle und Protokoll): weniger als 4 Fitpunkte, signifikanter
  Achsenabschnitt (> 2σ), R² < 0,98 (dann nicht im Bild), weniger als 3 Punkte (dann gar kein ε).

## Hinweise zu CDXML

- Exaktes ChemDraw-Aussehen: einen SVG/PDF/PNG-Export mit gleichem Namen neben die CDXML legen
  (siehe oben). Sonst wird die Struktur über RDKit neu gezeichnet. Die Orientierung bleibt, Labels
  wie CD₃ oder N₂ können aber anders aussehen (z. B. als einzelne Atome).
- Molmasse = Summe aller Fragmente (Gegenionen zählen mit).
- Lassen sich Abkürzungen wie Dipp oder Mes nicht auflösen, wird **keine** Molmasse gesetzt und eine
  Warnung angezeigt. Dann bitte die Molmasse von Hand eintragen.
- Binäre `.cdx`-Dateien werden nicht gelesen. In ChemDraw als `.cdxml` speichern.

## Unterstützte Daten

- **Cary-CSV/TXT-Exporte** (Agilent Cary 60 u. a.): erste Zeile = Probennamen, zweite Zeile =
  `Wavelength (nm),Abs` je Probe, danach die Daten. Dezimalkomma und -punkt werden beide erkannt,
  die Gerätemetadaten am Dateiende werden ignoriert. Einfache zweispaltige Dateien gehen auch; dann
  dient der Dateiname als Probenname.
- **Cary WinUV .DSW / .BSW** (Binärdateien der Gerätesoftware), gelesen mit dem Parser aus dem
  Open-Source-Projekt [parseuv](https://pypi.org/project/parseuv/). Gerätebasislinien
  („Baseline 100%T/0%T“) in Batch-Dateien werden übersprungen.
- **Cary Eclipse** Fluoreszenzdaten: CSV-Export und .FBSW-Dateien. Die Anregungswellenlänge wird
  aus den Metadaten der Datei übernommen.
- **Mehrere Dateien** lassen sich zusammen öffnen und bilden einen Datensatz.

## Probleme

- **Absturz:** Die Details stehen in `crash.log`:
  - Windows: `%LOCALAPPDATA%\UVVisTool`
  - macOS: `~/Library/Application Support/UVVisTool`
  - Linux: `~/.local/share/UVVisTool`
- **Selbsttest:** `UVVisTool --selftest <ordner>` prüft Einlesen, CDXML, Freistellung und Export und
  schreibt `selftest_report.txt`.

---

## Für Betreuer: Bauen und veröffentlichen

Die Apps baut GitHub Actions (`.github/workflows/build.yml`) für Windows, macOS und Linux.
Nach jedem Build läuft auf jedem System ein Selbsttest der fertigen App.

**Neue Version über die Weboberfläche:**

1. Geänderte Dateien hochladen: „Add file“ → „Upload files“ → „Commit changes“.
2. **Releases** → „Create a new release“ → bei „Choose a tag“ z. B. `v1.0.0` eintippen → „Create new tag“ → „Publish release“.
3. Nach etwa 20–40 Minuten hängen die drei App-Dateien am Release.

**Testbuild ohne Release:** Actions → „Build UVVisTool“ → „Run workflow“. Das Ergebnis liegt unten
im Lauf unter „Artifacts“ und wird nach 90 Tagen gelöscht.

**Lokal:**

```
pip install -r requirements.txt pyinstaller
python uvvis_gui.py                    # direkt aus dem Quellcode starten
python uvvis_gui.py --selftest out     # Selbsttest
python build.py                        # App bauen -> dist/
```

**Ohne GUI:** `python uvvis_core.py messung.csv` wertet mit Standardeinstellungen aus.

**Dateien:**

| Datei | Inhalt |
|---|---|
| `uvvis_gui.py` | Oberfläche (PySide6), Selbsttest |
| `uvvis_core.py` | Einlesen, Basislinie, Bandensuche, Fits, Plot-Layout, Export |
| `uvvis_images.py` | Bilder, HEIC, Freistellung (ISNet/ONNX, GrabCut), SVG/PDF-Einbettung |
| `uvvis_chem.py` | CDXML: Zeichnung und Molmasse (RDKit) |
| `uvvis_i18n.py` | Texte Deutsch/Englisch |

**Datenschutz:** Die `.gitignore` schließt CSV-, HEIC- und CDXML-Dateien aus, damit keine
unveröffentlichten Messdaten im Repository landen.

## Lizenz

UVVisTool steht unter der **GNU Affero General Public License v3.0** (siehe `LICENSE`).
Es gibt keine Gewährleistung.

Die App enthält folgende Bibliotheken unter ihren eigenen Lizenzen:
PySide6/Qt (LGPL-3.0), PyMuPDF (AGPL-3.0), RDKit (BSD-3-Clause), matplotlib (Matplotlib License),
NumPy (BSD-3-Clause), Pillow (MIT-CMU), pillow-heif (BSD-3-Clause, enthält libheif, LGPL-3.0),
OpenCV (Apache-2.0), ONNX Runtime (MIT), PyYAML (MIT), olefile (BSD-2-Clause).
Der Leser für .DSW/.BSW-Dateien in `parseuv_lite/` stammt aus parseuv 1.0.4
(© 2026 Ricardo J. Fernández-Terán, BSD-3-Clause, siehe `parseuv_lite/LICENSE`).
Das ISNet-Modell für die Freistellung (Apache-2.0) wird beim ersten Gebrauch aus dem
rembg-Projekt heruntergeladen und ist nicht Teil dieses Repositorys.
