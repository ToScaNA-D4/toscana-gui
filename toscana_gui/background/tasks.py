from __future__ import annotations

import json
from contextlib import contextmanager
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from os import chdir, getcwd
from pathlib import Path
from typing import Any, Literal

from ntsa.io.running_params import getRunningParams
from ntsa.experiment.measurement import Measurement

BackgroundSourceMode = Literal["Select File", "Write Path"]
BACKGROUND_SOURCE_OPTIONS: tuple[BackgroundSourceMode, BackgroundSourceMode] = (
    "Select File",
    "Write Path",
)

BackgroundSubtractionMethod = Literal[
    "Linear Combination",
    "Monte Carlo Simulation",
]
BACKGROUND_SUBTRACTION_METHOD_OPTIONS: tuple[
    BackgroundSubtractionMethod,
    BackgroundSubtractionMethod,
] = (
    "Linear Combination",
    "Monte Carlo Simulation",
)

BackgroundMeasurementCacheEntry = dict[str, Any]


@dataclass(slots=True)
class BackgroundValidationResult:
    is_valid: bool
    selected_par_path: str
    file_accessible: bool = False
    error: str | None = None

    def to_state(self) -> dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "selected_par_path": self.selected_par_path,
            "file_accessible": self.file_accessible,
            "error": self.error,
        }


@dataclass(slots=True)
class BackgroundExtractionResult:
    run_id: str
    status: str
    stdout_file: str
    measurement_file: str | None
    generated_files: list[str]
    summary: str
    error: str | None = None


@contextmanager
def _working_directory(target: Path):
    original = Path(getcwd())
    chdir(str(target))
    try:
        yield
    finally:
        chdir(str(original))


def default_background_state() -> dict[str, Any]:
    return {
        "source_mode": BACKGROUND_SOURCE_OPTIONS[0],
        "selected_par_path": "",
        "validation": {
            "is_valid": False,
            "selected_par_path": "",
            "file_accessible": False,
            "error": None,
        },
        "latest_measurement_artifact": None,
        "measurements_by_par": {},
        "subtraction_method": BACKGROUND_SUBTRACTION_METHOD_OPTIONS[0],
        "linear_combination": {
            "t_start": -1.0,
            "t_stop": 2.0,
            "t_step": 0.05,
            "smoothing_factor": 0.01,
            "ignore_points": 25,
        },
        "vanadium_linear_settings": {
            "t_start": -1.0,
            "t_stop": 2.0,
            "t_step": 0.05,
            "smoothing_factor": 0.01,
            "ignore_points": 25,
        },
        "error_bars_enabled": False,
        "contexts": {
            "active_context_id": None,
            "entries": [],
        },
    }


def normalize_background_state(payload: dict[str, Any] | None) -> dict[str, Any]:
    state = default_background_state()
    if not isinstance(payload, dict):
        return state

    source_mode = payload.get("source_mode")
    if source_mode in BACKGROUND_SOURCE_OPTIONS:
        state["source_mode"] = source_mode

    method = payload.get("subtraction_method")
    if method in BACKGROUND_SUBTRACTION_METHOD_OPTIONS:
        state["subtraction_method"] = method
    elif method == "Direct Sample Subtraction":
        state["subtraction_method"] = BACKGROUND_SUBTRACTION_METHOD_OPTIONS[0]

    selected_par_path = payload.get("selected_par_path")
    if isinstance(selected_par_path, str):
        state["selected_par_path"] = selected_par_path

    # Error bars are currently always disabled in the GUI; keep the persisted
    # field for backward compatibility but ignore incoming values.
    state["error_bars_enabled"] = False

    latest_artifact = payload.get("latest_measurement_artifact")
    if isinstance(latest_artifact, str) or latest_artifact is None:
        state["latest_measurement_artifact"] = latest_artifact

    cached = payload.get("measurements_by_par")
    if isinstance(cached, dict):
        normalized_cached: dict[str, BackgroundMeasurementCacheEntry] = {}
        for raw_key, raw_entry in cached.items():
            if not isinstance(raw_key, str) or not isinstance(raw_entry, dict):
                continue
            artifact = raw_entry.get("measurement_artifact")
            if not isinstance(artifact, str) or not artifact.strip():
                continue

            normalized_entry: BackgroundMeasurementCacheEntry = {
                "measurement_artifact": artifact,
            }
            run_id = raw_entry.get("run_id")
            if isinstance(run_id, str):
                normalized_entry["run_id"] = run_id
            extracted_at = raw_entry.get("extracted_at")
            if isinstance(extracted_at, str):
                normalized_entry["extracted_at"] = extracted_at
            par_mtime = raw_entry.get("par_mtime")
            if isinstance(par_mtime, (int, float)):
                normalized_entry["par_mtime"] = float(par_mtime)
            par_size = raw_entry.get("par_size")
            if isinstance(par_size, int):
                normalized_entry["par_size"] = par_size

            subtraction_view = raw_entry.get("sample_subtraction_view")
            if isinstance(subtraction_view, str) and subtraction_view in ("chi", "diffractogram"):
                normalized_entry["sample_subtraction_view"] = subtraction_view

            vanadium_view = raw_entry.get("vanadium_subtraction_view")
            if isinstance(vanadium_view, str) and vanadium_view in ("chi", "diffractogram"):
                normalized_entry["vanadium_subtraction_view"] = vanadium_view

            linear_combo = raw_entry.get("linear_combination")
            if isinstance(linear_combo, dict):
                normalized_linear: dict[str, Any] = {}
                trans = linear_combo.get("trans")
                chi = linear_combo.get("chi")
                fitted = linear_combo.get("fitted")
                best_t = linear_combo.get("best_t")
                if isinstance(trans, list) and all(isinstance(v, (int, float)) for v in trans):
                    normalized_linear["trans"] = [float(v) for v in trans]
                if isinstance(chi, list) and all(isinstance(v, (int, float)) for v in chi):
                    normalized_linear["chi"] = [float(v) for v in chi]
                if isinstance(fitted, list) and all(isinstance(v, (int, float)) for v in fitted):
                    normalized_linear["fitted"] = [float(v) for v in fitted]
                if isinstance(best_t, (int, float)):
                    normalized_linear["best_t"] = float(best_t)
                t_mode = linear_combo.get("t_mode")
                if isinstance(t_mode, str) and t_mode in ("computed", "custom"):
                    normalized_linear["t_mode"] = t_mode
                custom_t = linear_combo.get("custom_t")
                if isinstance(custom_t, (int, float)):
                    normalized_linear["custom_t"] = float(custom_t)
                effective_t = linear_combo.get("effective_t")
                if isinstance(effective_t, (int, float)):
                    normalized_linear["effective_t"] = float(effective_t)
                computed_at = linear_combo.get("computed_at")
                if isinstance(computed_at, str):
                    normalized_linear["computed_at"] = computed_at
                settings = linear_combo.get("settings")
                if isinstance(settings, dict):
                    normalized_linear["settings"] = dict(settings)
                if normalized_linear:
                    normalized_entry["linear_combination"] = normalized_linear

            vanadium_combo = raw_entry.get("vanadium_linear_combination")
            if isinstance(vanadium_combo, dict):
                normalized_vanadium: dict[str, Any] = {}
                trans = vanadium_combo.get("trans")
                chi = vanadium_combo.get("chi")
                fitted = vanadium_combo.get("fitted")
                best_t = vanadium_combo.get("best_t")
                if isinstance(trans, list) and all(isinstance(v, (int, float)) for v in trans):
                    normalized_vanadium["trans"] = [float(v) for v in trans]
                if isinstance(chi, list) and all(isinstance(v, (int, float)) for v in chi):
                    normalized_vanadium["chi"] = [float(v) for v in chi]
                if isinstance(fitted, list) and all(isinstance(v, (int, float)) for v in fitted):
                    normalized_vanadium["fitted"] = [float(v) for v in fitted]
                if isinstance(best_t, (int, float)):
                    normalized_vanadium["best_t"] = float(best_t)
                t_mode = vanadium_combo.get("t_mode")
                if isinstance(t_mode, str) and t_mode in ("computed", "custom"):
                    normalized_vanadium["t_mode"] = t_mode
                custom_t = vanadium_combo.get("custom_t")
                if isinstance(custom_t, (int, float)):
                    normalized_vanadium["custom_t"] = float(custom_t)
                effective_t = vanadium_combo.get("effective_t")
                if isinstance(effective_t, (int, float)):
                    normalized_vanadium["effective_t"] = float(effective_t)
                computed_at = vanadium_combo.get("computed_at")
                if isinstance(computed_at, str):
                    normalized_vanadium["computed_at"] = computed_at
                settings = vanadium_combo.get("settings")
                if isinstance(settings, dict):
                    normalized_vanadium["settings"] = dict(settings)
                if normalized_vanadium:
                    normalized_entry["vanadium_linear_combination"] = normalized_vanadium

            normalized_cached[raw_key] = normalized_entry

        state["measurements_by_par"] = normalized_cached

    linear_settings = payload.get("linear_combination")
    if isinstance(linear_settings, dict):
        normalized_settings = state["linear_combination"]
        for key in normalized_settings:
            value = linear_settings.get(key)
            if isinstance(normalized_settings[key], int):
                if isinstance(value, int):
                    normalized_settings[key] = value
                elif isinstance(value, float) and float(value).is_integer():
                    normalized_settings[key] = int(value)
            else:
                if isinstance(value, (int, float)):
                    normalized_settings[key] = float(value)

    vanadium_settings = payload.get("vanadium_linear_settings")
    if isinstance(vanadium_settings, dict):
        normalized_settings = state["vanadium_linear_settings"]
        for key in normalized_settings:
            value = vanadium_settings.get(key)
            if isinstance(normalized_settings[key], int):
                if isinstance(value, int):
                    normalized_settings[key] = value
                elif isinstance(value, float) and float(value).is_integer():
                    normalized_settings[key] = int(value)
            else:
                if isinstance(value, (int, float)):
                    normalized_settings[key] = float(value)

    validation = payload.get("validation")
    if isinstance(validation, dict):
        normalized = state["validation"]
        for key in normalized:
            value = validation.get(key)
            if isinstance(normalized[key], bool):
                if isinstance(value, bool):
                    normalized[key] = value
            elif normalized[key] is None:
                if isinstance(value, str) or value is None:
                    normalized[key] = value
            elif isinstance(normalized[key], str):
                if isinstance(value, str):
                    normalized[key] = value

    raw_contexts = payload.get("contexts")
    if isinstance(raw_contexts, dict):
        normalized_contexts = state["contexts"]
        active = raw_contexts.get("active_context_id")
        if isinstance(active, str) or active is None:
            normalized_contexts["active_context_id"] = active

        raw_entries = raw_contexts.get("entries")
        if isinstance(raw_entries, list):
            cleaned_entries: list[dict[str, Any]] = []
            for entry in raw_entries:
                if not isinstance(entry, dict):
                    continue
                context_id = entry.get("context_id")
                manifest = entry.get("manifest")
                if not isinstance(context_id, str) or not context_id.strip():
                    continue
                if not isinstance(manifest, str) or not manifest.strip():
                    continue
                cleaned: dict[str, Any] = {
                    "context_id": context_id,
                    "manifest": manifest,
                }
                created_at = entry.get("created_at")
                if isinstance(created_at, str):
                    cleaned["created_at"] = created_at
                sample_key = entry.get("sample_key")
                if isinstance(sample_key, str):
                    cleaned["sample_key"] = sample_key
                sample_title = entry.get("sample_title")
                if isinstance(sample_title, str):
                    cleaned["sample_title"] = sample_title
                status = entry.get("status")
                if isinstance(status, str):
                    cleaned["status"] = status
                cleaned_entries.append(cleaned)
            normalized_contexts["entries"] = cleaned_entries

    return state


def background_sample_key(par_file: Path, project_root: Path) -> str | None:
    """
    Stable key for a sample `.par` file within a project.

    On Windows, path comparisons are case-insensitive but pathlib's `relative_to`
    is case-sensitive, so we compute the relative path using normalized strings.
    """
    try:
        resolved_par = par_file.expanduser().resolve(strict=False)
        resolved_project = project_root.expanduser().resolve(strict=False)
    except Exception:
        return None

    # Use normalized paths for the containment check, but compute the relative path
    # from the *original* resolved paths to preserve casing in the stored key.
    try:
        import os

        par_norm = os.path.normcase(str(resolved_par))
        project_norm = os.path.normcase(str(resolved_project))
        common = os.path.commonpath([par_norm, project_norm])
        if os.path.normcase(common) != os.path.normcase(project_norm):
            return None

        rel = os.path.relpath(str(resolved_par), str(resolved_project))
        return Path(rel).as_posix()
    except Exception:
        return None


def background_par_signature(par_file: Path) -> tuple[float, int] | None:
    try:
        stat = par_file.expanduser().resolve(strict=False).stat()
    except Exception:
        return None
    return (float(stat.st_mtime), int(stat.st_size))


def is_sample_par_file(path: Path) -> bool:
    try:
        name = path.name
    except Exception:
        return False
    if path.suffix.lower() != ".par":
        return False
    return not name.lower().startswith("do_")


def list_sample_par_files(project_root: Path) -> list[Path]:
    par_dir = project_root / "processed" / "parfiles"
    if not par_dir.exists() or not par_dir.is_dir():
        return []
    paths = [candidate for candidate in par_dir.glob("*.par") if is_sample_par_file(candidate)]
    return sorted(paths, key=lambda p: p.name.lower())


def is_par_file_in_processed_parfiles(par_file: Path, project_root: Path) -> bool:
    try:
        resolved = par_file.expanduser().resolve(strict=False)
    except Exception:
        return False
    expected_dir = (project_root / "processed" / "parfiles").resolve(strict=False)
    return resolved.parent == expected_dir


def validate_background_par_file(par_file: Path) -> BackgroundValidationResult:
    resolved_par_file = par_file.expanduser().resolve(strict=False)
    if not resolved_par_file.exists():
        return BackgroundValidationResult(
            is_valid=False,
            selected_par_path=str(resolved_par_file),
            error="Selected `.par` file was not found.",
        )
    if not resolved_par_file.is_file():
        return BackgroundValidationResult(
            is_valid=False,
            selected_par_path=str(resolved_par_file),
            error="Selected path is not a file.",
        )
    if resolved_par_file.suffix.lower() != ".par":
        return BackgroundValidationResult(
            is_valid=False,
            selected_par_path=str(resolved_par_file),
            error="Selected file must use the `.par` extension.",
        )
    if not is_sample_par_file(resolved_par_file):
        return BackgroundValidationResult(
            is_valid=False,
            selected_par_path=str(resolved_par_file),
            file_accessible=True,
            error="Selected `.par` file must not start with `do_`.",
        )

    try:
        getRunningParams(str(resolved_par_file))
    except Exception as exc:
        return BackgroundValidationResult(
            is_valid=False,
            selected_par_path=str(resolved_par_file),
            file_accessible=True,
            error=f"Could not parse `.par` file: {exc}",
        )

    return BackgroundValidationResult(
        is_valid=True,
        selected_par_path=str(resolved_par_file),
        file_accessible=True,
        error=None,
    )


def execute_background_extraction(
    par_file: Path,
    project_root: Path,
    run_id: str,
) -> BackgroundExtractionResult:
    resolved_par_file = par_file.expanduser().resolve(strict=False)
    project_root = project_root.resolve(strict=False)

    processed_dir = project_root / "processed"
    logfiles_dir = processed_dir / "logfiles"
    artifacts_dir = processed_dir / "background" / run_id
    logfiles_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    stdout_file = logfiles_dir / f"{run_id}-stdout.txt"
    measurement_file = artifacts_dir / "measurement.json"

    status = "succeeded"
    error: str | None = None
    summary = f"Extracted sample measurement from `{resolved_par_file.name}`"
    generated_files: list[str] = []

    with stdout_file.open("w", encoding="utf-8") as stdout_handle:
        with redirect_stdout(stdout_handle), redirect_stderr(stdout_handle):
            try:
                params = getRunningParams(str(resolved_par_file))
                with _working_directory(resolved_par_file.parent):
                    Measurement(params)
                measurement_file.write_text(
                    json.dumps(dict(params), indent=2),
                    encoding="utf-8",
                )
                generated_files.append(str(measurement_file))
            except Exception as exc:
                status = "failed"
                error = str(exc)
                summary = f"Extraction failed for `{resolved_par_file.name}`: {exc}"
                print(f"Background extraction failed: {exc}")

    return BackgroundExtractionResult(
        run_id=run_id,
        status=status,
        stdout_file=str(stdout_file),
        measurement_file=str(measurement_file) if status == "succeeded" else None,
        generated_files=generated_files,
        summary=summary,
        error=error,
    )
