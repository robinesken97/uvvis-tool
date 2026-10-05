[English](CHANGELOG.md) | **Deutsch**

# Änderungen

## 1.0.1 – 05.10.2026

**Bitte prüfen:** Konzentrationen, die mit 1.0.0 über den Konzentrationsdialog eingegeben wurden,
können in mM gespeichert sein, ohne dass jemand diese Einheit gewählt hat (siehe erste Korrektur).
Datei öffnen und unter **Konzentrationen…** kontrollieren.

### Korrigiert
- Konzentrationsdialog: Einheit (bisher mM) und Startwert der Verdünnungsreihe (bisher 1,0) sind
  nicht mehr vorbelegt. Mit Konzentrationen, aber ohne Einheit, lässt sich der Dialog nicht
  bestätigen.

### Neu
- **Datei → Neu beginnen:** verwirft alle gespeicherten Eingaben zur aktuellen CSV
  (Konzentrationen, Molmassen, Strukturen, Fotos, Einstellungen, Layout) und startet von vorn.
- Fehlt bei Konzentrationen in mg/mL die Molmasse, wird das rot markiert, mit dem Hinweis, dass
  *a* [L g⁻¹ cm⁻¹] statt ε ausgegeben wird.
- Hinweis unter dem Molmasse-Feld, wenn die Konzentrationen in mM/µM angegeben sind und die
  Molmasse deshalb nicht verwendet wird.

## 1.0.0 – 04.10.2026

Erste Version.

- Einlesen von Cary-Mehrprobenexporten. Konzentrationen aus den Probennamen oder per Tabelle
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
