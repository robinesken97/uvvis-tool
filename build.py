"""Baut UVVisTool mit PyInstaller für das aktuelle Betriebssystem.

    pip install -r requirements.txt pyinstaller
    python build.py

Ergebnis: dist/UVVisTool/ (Windows/Linux) bzw. dist/UVVisTool.app (macOS).
"""
import subprocess
import sys

args = [
    sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
    "--name", "UVVisTool",
    "--windowed",
    "--icon", "assets/icon.png",
    "--add-data", f"assets{';' if sys.platform.startswith('win') else ':'}assets",
    "--collect-all", "rdkit",
    "--collect-all", "pymupdf",
    "--collect-all", "pillow_heif",
    "--collect-all", "onnxruntime",
    "--hidden-import", "matplotlib.backends.backend_qtagg",
    "--hidden-import", "matplotlib.backends.backend_agg",
    "--hidden-import", "matplotlib.backends.backend_pdf",
    "--hidden-import", "matplotlib.backends.backend_svg",
    "--exclude-module", "tkinter",
    "--exclude-module", "PySide6.QtWebEngineCore",
    "--exclude-module", "PySide6.Qt3DCore",
    "--exclude-module", "PySide6.QtQuick",
    "--exclude-module", "PySide6.QtQml",
    "--exclude-module", "PySide6.QtMultimedia",
    "--exclude-module", "PySide6.QtCharts",
    "--exclude-module", "PySide6.QtDataVisualization",
    "uvvis_gui.py",
]
if sys.platform == "darwin":
    args[4:4] = ["--osx-bundle-identifier", "de.uvvistool.app"]
print(" ".join(args))
sys.exit(subprocess.call(args))
