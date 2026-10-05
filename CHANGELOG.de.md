[English](CHANGELOG.md) | **Deutsch**

# Änderungen

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
- **Datei → Neu beginnen** verwirft alle gespeicherten Eingaben zur aktuellen Datei.
- Fehlende Molmasse bei Konzentrationen in mg/mL wird rot markiert; ein Hinweis erklärt, wenn die
  Molmasse nicht verwendet wird (mM/µM).

### Geändert
- ε (M⁻¹ cm⁻¹) wird nie mit Nachkommastellen angezeigt.
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
