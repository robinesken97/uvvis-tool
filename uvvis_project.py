"""
uvvis_project.py - Projektordner: alle drei Tabs in einer Datei, Eingabedateien als Kopie.

<Projekt>/
    project.uvvis      Zustand (YAML), Pfade relativ zum Projektordner
    data/              Messdaten und TD-DFT-Ausgaben
    images/            Strukturen (inkl. gleichnamiger ChemDraw-Exporte) und Fotos
    exports/           Standardziel für Exporte
"""
from __future__ import annotations

import copy
import hashlib
import shutil
from pathlib import Path

import yaml

PROJECT_FILE = "project.uvvis"
FORMAT_VERSION = 1


def is_project(path) -> Path | None:
    """Projektordner oder project.uvvis -> Projektordner, sonst None."""
    p = Path(path)
    if p.is_file() and p.name == PROJECT_FILE:
        return p.parent
    if p.is_dir() and (p / PROJECT_FILE).exists():
        return p
    return None


def _path_slots(state):
    """Alle Stellen im Zustand, an denen ein Dateipfad steht: (Container, Schlüssel, Unterordner)."""
    slots = []
    eps = state.get("eps") or {}
    files = eps.get("files") or []
    for i in range(len(files)):
        slots.append((files, i, "data"))
    for st in (eps.get("series") or {}).values():
        slots += [(st, "structure", "images"), (st, "photo", "images")]
    ov = state.get("overlay") or {}
    for e in ov.get("entries") or []:
        slots.append((e, "file", "data"))
        slots.append((e, "structure", "images"))
    slots.append((ov, "structure", "images"))
    fl = state.get("fluo") or {}
    slots += [(fl, "abs_file", "data"), (fl, "em_file", "data"), (fl, "structure", "images"),
              (fl, "photo_day", "images"), (fl, "photo_uv", "images")]
    return slots


def _get(cont, key):
    try:
        return cont[key]
    except (KeyError, IndexError, TypeError):
        return None


def _digest(p: Path):
    h = hashlib.sha1()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def save(project_dir, state) -> dict:
    """Kopiert alle referenzierten Dateien in den Projektordner und schreibt project.uvvis.
    Gibt den Zustand mit absoluten Pfaden auf die Kopien zurück."""
    pdir = Path(project_dir).resolve()
    for sub in ("data", "images", "exports"):
        (pdir / sub).mkdir(parents=True, exist_ok=True)
    abs_state = copy.deepcopy(state)
    copied = {}                                        # Quelle -> Ziel (gleiche Datei nur einmal)
    for cont, key, sub in _path_slots(abs_state):
        src = _get(cont, key)
        if not src:
            continue
        src = Path(src).resolve()
        if not src.exists():
            continue
        if pdir in src.parents:                        # liegt schon im Projekt
            cont[key] = str(src)
            continue
        if str(src) not in copied:
            copied[str(src)] = str(_copy_unique(src, pdir / sub))
            # zur CDXML gehörige ChemDraw-Exporte (gleicher Name) mitnehmen
            if src.suffix.lower() == ".cdxml":
                target = Path(copied[str(src)])
                for sib in src.parent.glob(src.stem + ".*"):
                    if sib.stem == src.stem and sib.suffix.lower() in (".svg", ".pdf", ".png", ".tif", ".tiff"):
                        shutil.copy2(sib, target.with_suffix(sib.suffix))
        cont[key] = copied[str(src)]
    rel_state = copy.deepcopy(abs_state)
    for cont, key, _ in _path_slots(rel_state):
        v = _get(cont, key)
        if v and Path(v).is_absolute() and pdir in Path(v).parents:
            cont[key] = Path(v).relative_to(pdir).as_posix()
    rel_state["format_version"] = FORMAT_VERSION
    (pdir / PROJECT_FILE).write_text(yaml.safe_dump(rel_state, allow_unicode=True, sort_keys=False),
                                     encoding="utf-8")
    return abs_state


def _copy_unique(src: Path, dest_dir: Path) -> Path:
    target = dest_dir / src.name
    n = 2
    while target.exists():
        if target.stat().st_size == src.stat().st_size and _digest(target) == _digest(src):
            return target                              # identische Datei bereits vorhanden
        target = dest_dir / f"{src.stem}_{n}{src.suffix}"
        n += 1
    shutil.copy2(src, target)
    return target


def load(project_dir) -> dict:
    """project.uvvis lesen, relative Pfade auf den Projektordner beziehen."""
    pdir = Path(project_dir).resolve()
    state = yaml.safe_load((pdir / PROJECT_FILE).read_text(encoding="utf-8")) or {}
    for cont, key, _ in _path_slots(state):
        v = _get(cont, key)
        if v and not Path(v).is_absolute():
            cont[key] = str((pdir / v).resolve())
    return state


def missing_files(state) -> list:
    return [_get(c, k) for c, k, _ in _path_slots(state) if _get(c, k) and not Path(_get(c, k)).exists()]


def import_file(project_dir, src, sub) -> str:
    """Datei ins Projekt übernehmen (Kopie nach data/ bzw. images/), falls sie nicht schon darin liegt.
    Bei CDXML werden gleichnamige ChemDraw-Exporte (SVG/PDF/PNG/TIFF) mitkopiert."""
    pdir = Path(project_dir).resolve()
    src = Path(src).resolve()
    if pdir == src.parent or pdir in src.parents:
        return str(src)
    dest_dir = pdir / sub
    dest_dir.mkdir(parents=True, exist_ok=True)
    target = _copy_unique(src, dest_dir)
    if src.suffix.lower() == ".cdxml":
        for sib in src.parent.glob(src.stem + ".*"):
            if sib.stem == src.stem and sib.suffix.lower() in (".svg", ".pdf", ".png", ".tif", ".tiff"):
                shutil.copy2(sib, target.with_suffix(sib.suffix))
    return str(target)


def write(project_dir, state):
    """Zustand speichern (automatisch). Dateien außerhalb des Projekts werden dabei noch übernommen."""
    return save(project_dir, state)


def create(project_dir):
    """Projektordner anlegen bzw. einen vorhandenen Ordner zum Projekt machen."""
    pdir = Path(project_dir).resolve()
    for sub in ("data", "images", "exports"):
        (pdir / sub).mkdir(parents=True, exist_ok=True)
    if not (pdir / PROJECT_FILE).exists():
        save(pdir, {})
    return pdir


def backup(project_dir):
    pf = Path(project_dir) / PROJECT_FILE
    if pf.exists():
        shutil.copy2(pf, pf.with_suffix(".uvvis.bak"))


def export_dir(project_dir, *parts) -> Path:
    d = Path(project_dir).joinpath("exports", *parts)
    d.mkdir(parents=True, exist_ok=True)
    return d
