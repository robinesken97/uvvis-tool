# UVVisTool – UV-Vis-Auswertung von Verdünnungsreihen

Lambert-Beer-Auswertung (ε aus A/d gegen c), Plot im Origin-Stil mit Inset, Bandenlabels,
Struktur (CDXML/SVG/PDF) und freigestelltem Küvettenfoto (HEIC/JPG/PNG …). GUI auf Deutsch/Englisch.

## Benutzen (fertige App)
1. Unter **Releases** die Datei für dein System laden und entpacken:
   - Windows: `UVVisTool-windows-x64.zip` → `UVVisTool\UVVisTool.exe`
     (SmartScreen: „Weitere Informationen“ → „Trotzdem ausführen“ – die App ist nicht signiert)
   - macOS (Apple Silicon): `UVVisTool-macos-arm64.zip` → Rechtsklick auf `UVVisTool.app` → „Öffnen“
   - Linux: `UVVisTool-linux-x64.tar.gz` → `UVVisTool/UVVisTool`
2. Cary-CSV öffnen oder ins Fenster ziehen. Proben und Konzentrationen werden aus den
   Probennamen gelesen (`…-0p5mgml_…` = 0.5 mg/mL; mM/µM gehen auch).
3. Je Serie: Struktur (CDXML → Molmasse wird berechnet) und Küvettenfoto wählen oder hineinziehen.
   Beim ersten Foto fragt die App, ob das KI-Freistellungsmodell (~180 MB) geladen werden soll.
4. Inset, Bilder und Labels mit der Maus zurechtschieben → **Exportieren** schreibt
   PDF (Struktur als Vektor), PNG (600 dpi) und `_results.csv` für alle Serien.

Einstellungen und Layout werden neben der CSV in `<name>.uvvis.yaml` gespeichert.

## Auswertung – was automatisch passiert
- **Basislinie** (Standard „automatisch (Reihe)“): Fenster dort, wo die konzentrierteste Probe am
  wenigsten absorbiert. Vom Wert im Fenster wird nur der Teil abgezogen, der *nicht* mit c skaliert
  (Geräte-/Küvettenoffset); ein c-proportionaler Rest gilt als echte Absorption und bleibt.
  „automatisch (einfach)“ zieht den kompletten Fensterwert ab.
- **Fit-Cutoff**: Punkte mit A über dem Cutoff (Standard 1.0) gehen nicht in den Fit.
- **Banden**: automatisch gesucht oder als Liste vorgegeben.
- **Rundung**: ε wird nach seiner Standardabweichung gerundet.
- **Warnungen**: < 4 Fitpunkte, signifikanter Achsenabschnitt (> 2σ), R² < 0.98 (nicht im Bild).

## CDXML
- Orientierung bleibt wie in ChemDraw; gezeichnet wird im ACS-1996-Stil über RDKit.
  Für das exakte ChemDraw-Aussehen SVG oder PDF aus ChemDraw verwenden – liegt daneben eine
  gleichnamige `.cdxml`, wird die Molmasse daraus berechnet.
- Molmasse = Summe aller Fragmente (Gegenionen zählen mit). Bei nicht aufgelösten Abkürzungen
  (Platzhalteratome) wird **keine** Molmasse gesetzt – dann bitte von Hand eingeben.

## Bauen
GitHub: Tag pushen (`git tag v1.0.0 && git push --tags`) → Actions baut Windows, macOS und Linux,
führt auf jedem System einen Selbsttest der fertigen App aus und hängt die Dateien an ein Release.

Lokal:
```
pip install -r requirements.txt pyinstaller
python uvvis_gui.py                  # direkt starten
python uvvis_gui.py --selftest out   # Selbsttest
python build.py                      # App bauen -> dist/
```
Ohne GUI: `python uvvis_core.py messung.csv` (Einstellungen per YAML, siehe Quelltext).

**Hinweis:** `.gitignore` schließt CSV-, HEIC- und CDXML-Dateien aus, damit keine
unveröffentlichten Messdaten in ein (öffentliches) Repository gelangen.
