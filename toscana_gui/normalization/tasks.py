from __future__ import annotations

from pathlib import Path

QSPDATA_DIR = Path("processed") / "qspdata"


def ensure_qspdata_dir(project_root: Path) -> Path:
    target = project_root / QSPDATA_DIR
    target.mkdir(parents=True, exist_ok=True)
    return target


def _is_within_project(candidate: Path, project_root: Path) -> bool:
    try:
        candidate.relative_to(project_root.resolve(strict=False))
        return True
    except Exception:
        return False


def is_qdat_within_project(qdat_file: Path, project_root: Path) -> bool:
    return _is_within_project(qdat_file.resolve(strict=False), project_root)


def list_qspdata_qdat_files(project_root: Path) -> list[Path]:
    qsp_dir = project_root / QSPDATA_DIR
    if not qsp_dir.exists() or not qsp_dir.is_dir():
        return []
    paths = [candidate for candidate in qsp_dir.glob("*_sub.qdat") if candidate.is_file()]
    return sorted(paths, key=lambda p: p.name.lower())


def list_sample_qdat_files(project_root: Path) -> list[Path]:
    return [p for p in list_qspdata_qdat_files(project_root) if p.name.lower() != "vanadium_sub.qdat"]


def list_vanadium_qdat_files(project_root: Path) -> list[Path]:
    paths = list_qspdata_qdat_files(project_root)
    return [p for p in paths if p.name.lower() == "vanadium_sub.qdat"]
