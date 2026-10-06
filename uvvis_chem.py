"""
uvvis_chem.py - CDXML lesen: Zeichnung (Orientierung wie in ChemDraw), Molmasse, Summenformel.

RDKit übernimmt die 2D-Koordinaten aus der CDXML, die Struktur wird also nicht neu
ausgerichtet, sondern nur im ACS-1996-Stil neu gezeichnet.
"""
from __future__ import annotations

from pathlib import Path

from uvvis_i18n import T


def _rdkit():
    try:
        from rdkit import Chem, RDLogger
        from rdkit.Chem import Descriptors, Draw, rdMolDescriptors
        from rdkit.Chem.Draw import rdMolDraw2D
        RDLogger.DisableLog("rdApp.*")
        return Chem, Descriptors, Draw, rdMolDescriptors, rdMolDraw2D
    except ImportError as e:
        raise RuntimeError(T("need_rdkit")) from e


def load_cdxml(path) -> dict:
    """-> dict(svg, mw, formula, n_fragments, warnings)."""
    Chem, Descriptors, Draw, rdMolDescriptors, rdMolDraw2D = _rdkit()
    path = Path(path)
    warnings = []
    mols = [m for m in Chem.MolsFromCDXMLFile(str(path), sanitize=True, removeHs=False) if m]
    sanitized = True
    if not mols:
        mols = [m for m in Chem.MolsFromCDXMLFile(str(path), sanitize=False, removeHs=False) if m]
        sanitized = False
        if mols:
            warnings.append(T("cdxml_unsanitized"))
    if not mols:
        raise RuntimeError(T("cdxml_empty", name=path.name))

    mol = mols[0]
    for m in mols[1:]:
        mol = Chem.CombineMols(mol, m)
    if len(mols) > 1:
        warnings.append(T("cdxml_fragments", n=len(mols)))

    dummies = [a for a in mol.GetAtoms() if a.GetAtomicNum() == 0]
    if dummies:
        warnings.append(T("cdxml_dummies", n=len(dummies)))

    mw = formula = None
    try:
        if sanitized:
            mw = float(Descriptors.MolWt(mol))
            formula = rdMolDescriptors.CalcMolFormula(mol, True, True)   # Isotope: D statt [2H]
        if dummies:
            mw = None        # Masse wäre zu klein -> lieber keine als eine falsche
    except Exception as e:  # pragma: no cover
        warnings.append(str(e))

    # Zeichnen: Koordinaten aus der CDXML behalten (auch gezeichnete H), ACS-1996-Stil
    dm = mol
    # Feste, großzügige Zeichenfläche (statt "flexicanvas"); Maßstab wie im ACS-1996-Stil
    # (Bindungslänge 14,4 pt), damit Linienstärke und Schrift zur Bindungslänge passen.
    # Der Rand wird beim Einlesen auf den tatsächlichen Inhalt zugeschnitten.
    bl = Draw.MeanBondLength(dm) or 1.0
    pos = dm.GetConformer().GetPositions() if dm.GetNumConformers() else None
    px_bl = 14.4
    if pos is not None and len(pos):
        w = int((pos[:, 0].max() - pos[:, 0].min()) / bl * px_bl + 10 * px_bl)
        h = int((pos[:, 1].max() - pos[:, 1].min()) / bl * px_bl + 10 * px_bl)
    else:
        w = h = int(14 * px_bl)
    d = rdMolDraw2D.MolDraw2DSVG(max(w, 100), max(h, 100))
    opts = d.drawOptions()
    Draw.SetACS1996Mode(opts, bl)
    opts.clearBackground = False
    opts.prepareMolsBeforeDrawing = sanitized
    d.DrawMolecule(dm)
    d.FinishDrawing()
    return {"svg": d.GetDrawingText(), "mw": mw, "formula": formula,
            "n_fragments": len(mols), "warnings": warnings}
