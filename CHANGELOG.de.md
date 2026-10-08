[English](CHANGELOG.md) | **Deutsch**

# Änderungen

## 1.2.4 – 08.10.2026

### Neu
- Das minimale R², ab dem eine Bande im Bild erscheint, ist einstellbar (Auswertung → „min. R² fürs
  Bild“, Standard 0,98; 0 = alle Banden mit Fit zeigen). Banden unter der Schwelle bleiben in
  Ergebnistabelle, CSV und Excel-Report; ihre R²-Zelle ist rot markiert (mit Tooltip). Der Wert wird im
  Projekt gespeichert.

## 1.2.3 – 06.10.2026

### Korrigiert
- Bei mehreren Banden konnten zwei Labels exakt übereinander liegen: Ein neu hinzugekommenes
  Bandenlabel (z. B. weil die Bande nach einer Cutoff-Änderung genug Fitpunkte hatte) wurde platziert,
  bevor die gespeicherten Positionen der anderen Labels berücksichtigt waren. Gespeicherte Positionen
  von Labels, Inset und Bildern werden jetzt zuerst reserviert. Labels, die in einem gespeicherten
  Projekt bereits übereinanderliegen, bleiben dort – eines wegziehen oder „Layout zurücksetzen“.

## 1.2.2 – 06.10.2026

### Geändert
- Die Vorschau füllt in allen Tabs den verfügbaren Platz und wächst mit dem Fenster; sie bleibt
  maßstabsgetreu (nur die Anzeigegröße ändert sich, die exportierte Abbildung bleibt gleich).

### Korrigiert
- Sehr kleine Fehler von ε wurden als „± 0“ angezeigt (z. B. 51 ± 0 bei SE = 0,65); sie werden jetzt
  aufgerundet („51 ± 1“).

## 1.2.1 – 06.10.2026

### Neu
- **Overlay:** Struktur pro Spektrum, optional in der Kurvenfarbe (SVG/CDXML als Vektorgrafik,
  PNG/PDF als Bild).

### Geändert
- **TD-DFT-Normierung:** Kurve und Striche haben jetzt immer denselben Skalierungsfaktor (jeder Strich =
  Höhe seiner eigenen Gaußbande, die Kurve ist deren Summe). Bezug „Kurvenmaximum = 1“ (neuer Standard)
  oder „stärkster Übergang = 1“; alternativ Striche als Oszillatorstärke f auf rechter Achse. In 1.2.0
  wurden die Striche im Modus „stärkster Strich = Bandenmaximum“ unabhängig von der Kurve skaliert.

### Korrigiert
- Strukturen (CDXML, SVG, PDF) wurden zu knapp zugeschnitten: exakt senkrechte oder waagerechte
  Bindungen am Rand (z. B. =CH₂, CH₃) fehlten in Abbildungen und Exporten.
- Strukturen wurden verzerrt, wenn sich ihr Seitenverhältnis oder die Achsengröße änderte (z. B. f-Achse
  zugeschaltet); gespeichert wird jetzt nur die Breite, die Höhe folgt immer aus dem Bild. Bestehende
  Projekte werden automatisch korrigiert.
- Aus CDXML ohne Export gezeichnete Strukturen hatten zu dünne Linien und zu kleine Beschriftungen.
- Eingefärbte Strukturen hatten dunkle Kanten.

## 1.2.0 – 06.10.2026

### Neu
- **Projektordner:** zuerst Ordner wählen oder anlegen; jede geladene Datei wird hineinkopiert, das
  Projekt wird automatisch gespeichert (Sicherung `project.uvvis.bak` beim Öffnen), und Exporte landen
  direkt in `exports/epsilon/<Serie>/`, `exports/overlay/`, `exports/fluorescence/`. Datei → Neu /
  Öffnen / Zuletzt geöffnet / Projekt als Kopie speichern / Projektordner anzeigen. Das Programm
  startet ohne Projekt.
- **Excel-Report** pro Serie: Parameter, alle Ergebnisse inkl. 95 %-Konfidenzintervall, Methodik mit
  Formeln, Spektren und je Bande ein Blatt mit der vollständigen Regression als Excel-Formeln neben
  den Tool-Werten, Residuen und nativen Diagrammen.
- **Rückgängig / Wiederholen** (⌘Z / ⌘⇧Z, Strg+Z / Strg+Y) über alle Tabs.
- **Overlay:** Linienart und -stärke, Skalierungsfaktor und vertikaler Versatz pro Spektrum,
  Reihenfolge (↑/↓), Strukturgröße in %, Legende in freier Fläche.
- **TD-DFT-Striche:** „stärkster Strich = Bandenmaximum“ (Standard), „Höhe der Einzelbande“ oder
  Oszillatorstärke f auf eigener rechter Achse.
- ORCA-Spektren mit **Spin-Bahn-Kopplung**; „mit SOC“ / „ohne SOC“ pro Rechnung wählbar.
- ε-Tab: Regressions-Inset abschaltbar (zusätzlich zu seiner Tabelle).
- Fluoreszenz-Tab: Größenfelder für Struktur und Fotos.
- Kennzeichnung „(sh)“ an Schultern in der Abbildung ist optional (standardmäßig aus); Tabelle und Excel-Report behalten sie.

### Geändert
- Die Ergebnis-CSV hat eine zusätzliche Spalte `ci95` (95 %-Konfidenzintervall von ε).
- Einstellungen werden nicht mehr als `.uvvis.yaml` neben den Messdateien gespeichert, und Overlay-/
  Fluoreszenz-Tab werden beim Start nicht mehr automatisch wiederhergestellt – dafür gibt es Projektordner.

### Korrigiert
- ORCA-Ausgaben mit Spin-Bahn-Kopplung wurden falsch gelesen (Zustandsnamen wie „0-1.0A“ wurden als
  Zahlen interpretiert, mit falschen Energien und Oszillatorstärken). Solche Rechnungen bitte neu laden.

## 1.1.0 – 05.10.2026

**Bitte prüfen:** Konzentrationen, die mit 1.0.0 über den Konzentrationsdialog eingegeben wurden,
können in mM gespeichert sein, ohne dass jemand diese Einheit gewählt hat. Datei öffnen und unter
**Konzentrationen…** kontrollieren.

### Neu
- **Overlay-Tab:** mehrere gemessene Spektren und TD-DFT-Spektren (ORCA 4–6, Gaussian) in einer
  Abbildung, in eigenen Farben; normiert auf eine Bande von Interesse (global oder pro Spektrum)
  oder als ε [10³ M⁻¹ cm⁻¹]. TD-DFT: Gauß-Verbreiterung (FWHM, Energieverschiebung), optional Striche.
- **Fluoreszenz-Tab:** Absorption und Emission normiert in einer Abbildung, mit λ/ε- und
  λem-Labels, optionalem Ausblenden von Streulicht und einem Fotopaar Tageslicht/UV mit Pfeil und
  Anregungswellenlänge. Die Einstellungen beider neuen Tabs bleiben zwischen Sitzungen erhalten und
  lassen sich speichern/laden.
- Einlesen von Cary-WinUV-Dateien **.DSW/.BSW** und Cary-Eclipse-Dateien **.FBSW** (Parser aus
  parseuv, BSD-3-Clause) sowie von Cary-Eclipse-CSV-Exporten; λex wird aus den Metadaten übernommen.
- **Mehrere Messdateien auf einmal** (z. B. jede Konzentration einzeln gemessen) bilden einen
  Datensatz, auch per Drag & Drop.
- Strukturzeichnung **unverändert aus ChemDraw**: Ein gleichnamiger SVG/PDF/PNG-Export neben der
  CDXML wird für die Zeichnung verwendet, die CDXML für die Molmasse.
- **Schultern:** optionale automatische Suche (markiert mit „(sh)“); manuell eingetragene Banden
  lassen sich zusätzlich zu den automatisch gefundenen auswerten.
- **Pro Bande:** eigener Fit-Cutoff (z. B. um einen Punkt knapp über A = 1 mitzunehmen) und Auswahl,
  ob die Bande im Bild erscheint – beides in der Ergebnistabelle. Ausgeschlossene Punkte lassen sich
  im Inset als offene Symbole zeigen.
- **Datei → Neu beginnen** verwirft alle gespeicherten Eingaben zur aktuellen Datei.
- Fehlende Molmasse bei Konzentrationen in mg/mL wird rot markiert; ein Hinweis erklärt, wenn die
  Molmasse nicht verwendet wird (mM/µM).

### Geändert
- ε (M⁻¹ cm⁻¹) wird nie mit Nachkommastellen angezeigt.
- R² steht nur dann in der Inset-Legende, wenn die Inset-Tabelle nicht angezeigt wird (dort steht es bereits).
- Die Summenformel zeigt Isotope (z. B. D für Deuterium); die Molmasse hat sie bereits berücksichtigt.

### Korrigiert
- Konzentrationsdialog: Einheit und Startwert sind nicht mehr vorbelegt (bisher mM und 1,0).
- Spektren ohne Signal im Normierungsbereich werden mit Hinweis ausgelassen, statt aus Rauschen
  hochskaliert zu werden.

## 1.0.0 – 04.10.2026

Erste Version.

- Einlesen von Cary-Mehrproben-CSV-Exporten. Konzentrationen aus den Probennamen oder per Tabelle
  (mit Hilfe für Verdünnungsreihen).
- Automatische Basislinienkorrektur, Bandensuche, Lambert-Beer-Fits mit ε ± Standardfehler, R²
  und Warnungen.
- Abbildungen im Origin-Stil mit Inset (Regressionen, R²), Struktur (CDXML/SVG/PDF; Molmasse aus
  CDXML) und Küvettenfoto (HEIC/JPG/PNG, automatische Freistellung).
- Inset, Bilder und Labels mit der Maus verschiebbar, Größe per Mausrad oder Größenfeld.
  Wählbarer Wellenlängenbereich.
- Export als PDF/SVG (Struktur als Vektorgrafik) und PNG. Feste Größe für Word
  (16 × 11 cm = zwei Abbildungen pro A4-Seite).
- Oberfläche auf Deutsch und Englisch. Apps für Windows, macOS und Linux.
