[English](README.md) | **Deutsch**

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

1. **Daten öffnen:** Datei → CSV öffnen, oder die CSV ins Fenster ziehen.
2. **Konzentrationen:** Die Konzentrationen werden aus den Probennamen gelesen, z. B.
   `RE-2-184-0p5mgml_THF` → Serie `RE-2-184`, 0,5 mg/mL. Erkannt werden
   `mgml`/`mg_ml`/`mg/ml`, `mM`, `uM`/`µM`; `p` steht für das Dezimalkomma.
   - Stehen keine Konzentrationen im Namen (z. B. `c0` … `c4`), öffnet sich eine Tabelle zum Eintragen.
   - „Verdünnungsreihe ausfüllen“ setzt in die markierten Zeilen (oder alle) von oben nach unten Start, Start/Faktor, … ein.
   - Proben ohne Wert, z. B. eine Blindprobe, werden ignoriert.
   - Über die Spalte „Serie“ lassen sich mehrere Verbindungen in einer Datei trennen.
   - Später ändern geht über den Knopf **Konzentrationen…**.
3. **Verbindung (je Serie):**
   - **Struktur:** CDXML, SVG, PDF oder eine Bilddatei. Bei CDXML wird die **Molmasse automatisch
     berechnet**, die Summenformel wird zur Kontrolle angezeigt.
   - **Küvettenfoto:** HEIC (iPhone), JPG, PNG und weitere. Der Hintergrund wird automatisch entfernt.
     Beim ersten Mal bietet die App einen einmaligen Download des KI-Modells an (~180 MB).
   - **Molmasse:** wird aus der CDXML übernommen, sonst von Hand eintragen. Bleibt das Feld leer, gibt
     das Tool den spezifischen Absorptionskoeffizienten *a* in L g⁻¹ cm⁻¹ statt ε aus.
4. **Auswertung:** Schichtdicke, Fit-Cutoff und bei Bedarf die Banden eintragen (leer = automatisch).
5. **Layout:**
   - **Mit der Maus ziehen:** Inset, Struktur, Küvette und jedes λ/ε-Label lassen sich verschieben.
   - **Mausrad bzw. Trackpad** über Inset oder Bild ändert die Größe. Alternativ die Felder „Größe [% Plotbreite]“ nutzen.
   - „Layout zurücksetzen“ stellt die automatische Anordnung wieder her.
6. **Exportieren:** Datei → Exportieren (oder der Knopf). Das schreibt die gewählten Formate (PDF/SVG/PNG)
   und `<name>_results.csv` für **alle** Serien in einen wählbaren Ordner.

Einstellungen, Konzentrationen und Layouts werden neben der CSV in `<name>.uvvis.yaml` gespeichert
und beim nächsten Öffnen wiederhergestellt.

**Sprache:** Menü **Sprache** → Deutsch / English. Die Umstellung gilt sofort. Auf dem Mac steht das
Menü in der Menüleiste oben am Bildschirm, nicht im Fenster. Die Achsenbeschriftungen der Abbildungen
sind immer englisch.

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
- **Rundung:** ε wird nach seiner Standardabweichung gerundet.
- **Warnungen** (Ergebnistabelle und Protokoll): weniger als 4 Fitpunkte, signifikanter
  Achsenabschnitt (> 2σ), R² < 0,98 (dann nicht im Bild), weniger als 3 Punkte (dann gar kein ε).

## Hinweise zu CDXML

- Die Orientierung der Struktur bleibt wie in ChemDraw. Gezeichnet wird im ACS-1996-Stil über RDKit.
  Für das exakte ChemDraw-Aussehen SVG oder PDF aus ChemDraw exportieren. Liegt daneben eine
  gleichnamige `.cdxml`, wird die Molmasse aus dieser Datei berechnet.
- Molmasse = Summe aller Fragmente (Gegenionen zählen mit).
- Lassen sich Abkürzungen wie Dipp oder Mes nicht auflösen, wird **keine** Molmasse gesetzt und eine
  Warnung angezeigt. Dann bitte die Molmasse von Hand eintragen.
- Binäre `.cdx`-Dateien werden nicht gelesen. In ChemDraw als `.cdxml` speichern.

## Unterstützte Daten

Cary-Mehrprobenexporte (Agilent Cary 60 u. a.): erste Zeile = Probennamen, zweite Zeile =
`Wavelength (nm),Abs` je Probe, danach die Daten. Dezimalkomma und -punkt werden beide erkannt,
die Gerätemetadaten am Dateiende werden ignoriert.

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
2. **Releases** → „Create a new release“ → bei „Choose a tag“ z. B. `v1.2.0` eintippen → „Create new tag“ → „Publish release“.
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
