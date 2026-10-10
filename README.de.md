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
- **macOS (Gatekeeper):** `UVVisTool.app` in „Programme“ ziehen und einmal doppelklicken (wird blockiert).
  Dann Systemeinstellungen → Datenschutz & Sicherheit → ganz unten „Dennoch öffnen“ → mit Passwort/Touch ID
  bestätigen. Ab macOS 15 funktioniert der frühere Weg „Rechtsklick → Öffnen“ nicht mehr. Alternativ im
  Terminal: `xattr -dr com.apple.quarantine /Applications/UVVisTool.app`. Nur für Apple-Silicon-Macs (M1 und neuer).

Unter Windows immer den ganzen Ordner `UVVisTool` zusammenlassen. Die `.exe` funktioniert nicht ohne den Ordner `_internal` daneben.

## Ablauf

1. **Daten öffnen:** Datei → Messdaten öffnen, oder Dateien ins Fenster ziehen. Unterstützt werden
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
4. **Auswertung:** Schichtdicke und Fit-Cutoff eintragen. Banden werden automatisch gefunden;
   zusätzliche Banden (z. B. Schultern) lassen sich als Liste eintragen („zusätzlich zu den
   automatisch gefundenen“ behält beide), und **„Schultern automatisch suchen“** ergänzt Schultern
   (in der Abbildung optional mit „(sh)“ markiert). In der Ergebnistabelle entscheidet das Häkchen bei λ, ob eine Bande im Bild
   erscheint, und ein Doppelklick auf **„Cutoff A“** setzt einen eigenen Cutoff für diese Bande
   (z. B. um einen Punkt knapp über A = 1 mitzunehmen). Banden mit eigenem Cutoff sind farbig
   hinterlegt; optional zeigt das Inset ausgeschlossene Punkte als offene Symbole.
5. **Layout:**
   - **Mit der Maus ziehen:** Inset, Struktur, Küvette und jedes λ/ε-Label lassen sich verschieben.
   - **Mausrad bzw. Trackpad** über Inset oder Bild ändert die Größe. Alternativ die Felder „Größe [% Plotbreite]“ nutzen.
   - „Layout zurücksetzen“ stellt die automatische Anordnung wieder her.
6. **Exportieren:** Datei → Exportieren (oder der Knopf). Das schreibt die gewählten Formate (PDF/SVG/PNG),
   `<Serie>_results.csv` und den Excel-Report für **alle** Serien ins Projekt (siehe unten).

## Projekte, Export, Rückgängig

Alles passiert in einem **Projektordner**:

1. **Datei → Neues Projekt…** – einen Ordner wählen oder im Dialog neu anlegen.
2. Messdaten, Strukturen, Fotos und TD-DFT-Dateien von beliebigen Orten laden – sie werden **ins
   Projekt kopiert** (`data/`, `images/`; ChemDraw-Exporte mit gleichem Namen wie eine CDXML kommen
   mit). Dateien, die schon im Projekt liegen, werden nicht erneut kopiert.
3. Normal arbeiten – das Projekt wird **automatisch gespeichert**. Beim Öffnen eines Projekts wird
   jeweils eine Sicherung `project.uvvis.bak` angelegt.
4. **Exportieren** schreibt direkt ins Projekt (vorhandene Dateien werden überschrieben):

```
MeinProjekt/
  project.uvvis               Einstellungen (Pfade relativ zum Ordner)
  data/  images/              Kopien aller Eingabedateien
  exports/epsilon/<Serie>/    Abbildungen (PDF/SVG/PNG), <Serie>_results.csv, <Serie>_report.xlsx
  exports/overlay/            <Projekt>_overlay.*
  exports/fluorescence/       <Projekt>_fluorescence.*
```

Das Programm startet ohne Projekt. Projekte öffnen über **Datei → Projekt öffnen**, **Zuletzt
geöffnet** oder indem man den Ordner ins Fenster zieht. **Datei → Projekt als Kopie speichern** legt
eine vollständige Kopie an (z. B. als Zwischenstand). **Bearbeiten → Rückgängig / Wiederholen**
(⌘Z / ⌘⇧Z, Strg+Z / Strg+Y) gilt für alle Tabs.

## Excel-Report

Für jede Serie enthält `<Serie>_report.xlsx`:

- **Übersicht:** Parameter (Einheit, Molmasse, Schichtdicke, Cutoffs, Basislinienfenster und Offsets
  je Probe), Ergebnisse aller Banden (Steigung, Achsenabschnitt, Standardfehler, R², ε ± SE,
  **95 %-Konfidenzintervall** über die t-Verteilung) und die Methodik mit allen Formeln.
- **Spektren:** A(λ) aller Proben, basislinienkorrigiert und roh, mit Diagramm.
- **Ein Blatt pro Bande:** Messpunkte, Kennzeichen „im Fit“ (1/0, änderbar), die vollständige Regression
  als **Excel-Formeln** (x̄, ȳ, Sxx, Sxy, m, b, RSS, s, SE, R², ε, t, KI) neben den Werten des Tools
  samt Abweichung, Residuen und Diagramm (A/d gegen c mit Regressionsgerade).

Blaue Zahlen sind Messwerte bzw. Tool-Ergebnisse, schwarze Zellen sind Formeln. Ändert man ein
Kennzeichen in „im Fit“, rechnet Excel die Bande neu.

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
- Pro Spektrum: Farbe, Name, **Linienart und -stärke**, **Skalierungsfaktor und vertikaler Versatz**
  (z. B. für gestapelte Spektren); **Reihenfolge** mit ↑/↓ (auch die der Legende).
- ORCA-Rechnungen mit **Spin-Bahn-Kopplung**: pro Rechnung „mit SOC“ oder „ohne SOC“ wählbar.
- **TD-DFT-Normierung:** Kurve und Striche haben immer denselben Skalierungsfaktor (jeder Strich ist
  die Höhe seiner eigenen Gaußbande, die Kurve ist deren Summe). Bezug: „Kurvenmaximum = 1“ oder
  „stärkster Übergang = 1“; alternativ zeigen die Striche die Oszillatorstärke f auf einer rechten Achse.
- Eine **Struktur pro Spektrum**, optional in der Kurvenfarbe.
- Struktur mit einstellbarer Größe; die Legende wird in freie Fläche gesetzt und lässt sich verschieben.

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

## Schrift und Rahmen

Format → „Schrift und Rahmen…“ gilt für alle Tabs und wird im Projekt gespeichert:

- **Textschrift** und **Symbolschrift**. λ und ε stehen standardmäßig in der Symbolschrift
  (Times New Roman), wie in Origin; abschaltbar.
- **Bandenlabels:** Schriftgröße (standardmäßig automatisch), fett, kursiv, Farbe.
- **Rahmen:** geschlossener Rahmen um den Plot (auch oben und rechts) und abgerundeter Rahmen um die
  Strukturformel.

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
  Achsenabschnitt (> 2σ), R² unter der Schwelle (Standard 0,98, einstellbar unter Auswertung →
  „min. R² fürs Bild“; 0 = alle zeigen; die Bande bleibt in Tabelle – R²-Zelle rot markiert –, CSV und
  Excel-Report, erscheint aber nicht im Bild), weniger als 3 Punkte (dann gar kein ε). Bei 4 Punkten
  sagt R² allein wenig: vor dem Absenken der Schwelle das 95-%-Konfidenzintervall im Excel-Report prüfen.

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
| `uvvis_tabs.py` | Overlay- und Fluoreszenz-Tab |
| `uvvis_extra.py` | TD-DFT einlesen/verbreitern, Fotopaar, Abbildung für die Zusatz-Tabs |
| `uvvis_project.py` | Projektordner (Speichern/Laden, Kopieren der Eingabedateien) |
| `uvvis_report.py` | Excel-Report (openpyxl) |
| `parseuv_lite/` | Leser für Cary .DSW/.BSW/.FBSW (aus parseuv, BSD-3-Clause) |

**Datenschutz:** Die `.gitignore` schließt CSV-, HEIC- und CDXML-Dateien aus, damit keine
unveröffentlichten Messdaten im Repository landen.

## Lizenz

UVVisTool steht unter der **GNU Affero General Public License v3.0** (siehe `LICENSE`).
Es gibt keine Gewährleistung.

Die App enthält folgende Bibliotheken unter ihren eigenen Lizenzen:
PySide6/Qt (LGPL-3.0), PyMuPDF (AGPL-3.0), RDKit (BSD-3-Clause), matplotlib (Matplotlib License),
NumPy (BSD-3-Clause), Pillow (MIT-CMU), pillow-heif (BSD-3-Clause, enthält libheif, LGPL-3.0),
OpenCV (Apache-2.0), ONNX Runtime (MIT), PyYAML (MIT), olefile (BSD-2-Clause), openpyxl (MIT).
Der Leser für .DSW/.BSW-Dateien in `parseuv_lite/` stammt aus parseuv 1.0.4
(© 2026 Ricardo J. Fernández-Terán, BSD-3-Clause, siehe `parseuv_lite/LICENSE`).
Das ISNet-Modell für die Freistellung (Apache-2.0) wird beim ersten Gebrauch aus dem
rembg-Projekt heruntergeladen und ist nicht Teil dieses Repositorys.
