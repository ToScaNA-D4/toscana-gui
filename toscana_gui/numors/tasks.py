from __future__ import annotations

import ntsa.io.parameters as parameters_module
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from dataclasses import dataclass
from os import PathLike, chdir, getcwd
from pathlib import Path
from typing import Any, Callable

from ntsa.io.parameters import readParam

NUMORS_SOURCE_OPTIONS = ("Select File", "Write Path")
NUMORS_PARFILES_DIR = Path("processed") / "parfiles"
DEFAULT_D4CREG_EXTENSIONS: tuple[str, str, str, str, str, str] = (
    ".reg",
    ".adat",
    ".qdat",
    ".cdat",
    ".nxs",
    ".log",
)
SPECIAL_PATH_TOKENS: dict[str, set[str]] = {
    "efffile": {"ones"},
    "decfile": {"zeros"},
}

_SEPARATOR_ONLY_COMMENT_CHARS = set("-=_*0123456789. ")


def _normalize_comment_title_line(raw: str) -> str | None:
    stripped = raw.strip()
    if not stripped or stripped[0] not in {"#", "!"}:
        return None
    content = stripped[1:].strip()
    if not content:
        return None
    if all(ch in _SEPARATOR_ONLY_COMMENT_CHARS for ch in content):
        return None
    return content


def _output_basename(file_base: str) -> str:
    try:
        return Path(file_base).name or str(file_base)
    except Exception:
        return str(file_base)


@dataclass(slots=True)
class NumorsValidationResult:
    is_valid: bool
    selected_par_path: str
    resolved_rawdata_path: str | None = None
    resolved_efffile_path: str | None = None
    resolved_decfile_path: str | None = None
    file_accessible: bool = False
    plot_enabled: bool = False
    error: str | None = None

    def to_state(self) -> dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "selected_par_path": self.selected_par_path,
            "resolved_rawdata_path": self.resolved_rawdata_path,
            "resolved_efffile_path": self.resolved_efffile_path,
            "resolved_decfile_path": self.resolved_decfile_path,
            "file_accessible": self.file_accessible,
            "plot_enabled": self.plot_enabled,
            "error": self.error,
        }


@dataclass(slots=True)
class NumorsExecutionResult:
    run_id: str
    status: str
    stdout_file: str
    logfile: str | None
    reg_file: str | None
    adat_file: str | None
    qdat_file: str | None
    run_blocks: list[dict[str, Any]]
    generated_files: list[str]
    plot_files: list[str]
    summary: str
    error: str | None = None


def default_numors_state() -> dict[str, Any]:
    return {
        "source_mode": NUMORS_SOURCE_OPTIONS[0],
        "selected_par_path": "",
        "validation": {
            "is_valid": False,
            "selected_par_path": "",
            "resolved_rawdata_path": None,
            "resolved_efffile_path": None,
            "resolved_decfile_path": None,
            "file_accessible": False,
            "plot_enabled": False,
            "error": None,
        },
        "last_viewed_output_index": 0,
        "selected_run_block_index": 0,
        "selected_run_block_plot_index": 0,
    }


def normalize_numors_state(payload: dict[str, Any] | None) -> dict[str, Any]:
    state = default_numors_state()
    if not isinstance(payload, dict):
        return state

    source_mode = payload.get("source_mode")
    if source_mode == "File Explorer":
        source_mode = "Select File"
    if source_mode in NUMORS_SOURCE_OPTIONS:
        state["source_mode"] = source_mode

    selected_par_path = payload.get("selected_par_path")
    if isinstance(selected_par_path, str):
        state["selected_par_path"] = selected_par_path

    last_viewed_output_index = payload.get("last_viewed_output_index")
    if isinstance(last_viewed_output_index, int) and last_viewed_output_index >= 0:
        state["last_viewed_output_index"] = last_viewed_output_index

    selected_run_block_index = payload.get("selected_run_block_index")
    if isinstance(selected_run_block_index, int) and selected_run_block_index >= 0:
        state["selected_run_block_index"] = selected_run_block_index

    selected_run_block_plot_index = payload.get("selected_run_block_plot_index")
    if isinstance(selected_run_block_plot_index, int) and selected_run_block_plot_index >= 0:
        state["selected_run_block_plot_index"] = selected_run_block_plot_index

    validation = payload.get("validation")
    if isinstance(validation, dict):
        normalized_validation = state["validation"]
        for key in normalized_validation:
            value = validation.get(key)
            if isinstance(normalized_validation[key], bool):
                if isinstance(value, bool):
                    normalized_validation[key] = value
            elif normalized_validation[key] is None:
                if isinstance(value, str) or value is None:
                    normalized_validation[key] = value
            elif isinstance(normalized_validation[key], str):
                if isinstance(value, str):
                    normalized_validation[key] = value
    return state


def ensure_numors_parfiles_dir(project_root: Path) -> Path:
    target = project_root / NUMORS_PARFILES_DIR
    target.mkdir(parents=True, exist_ok=True)
    return target


def is_numors_par_file(path: Path) -> bool:
    try:
        name = path.name
    except Exception:
        return False
    if path.suffix.lower() != ".par":
        return False
    return name.lower().startswith("do_")


def list_numors_par_files(project_root: Path) -> list[Path]:
    par_dir = project_root / NUMORS_PARFILES_DIR
    if not par_dir.exists() or not par_dir.is_dir():
        return []
    paths = [candidate for candidate in par_dir.glob("*.par") if is_numors_par_file(candidate)]
    return sorted(paths, key=lambda p: p.name.lower())


def is_par_file_within_project(par_file: Path, project_root: Path) -> bool:
    return _is_within_project(par_file.resolve(strict=False), project_root)


def _parse_d4creg_par_metadata(par_file: Path) -> dict[str, Any]:
    settings: dict[str, Any] = {
        "path_raw": "rawdata/",
        "efffile": "effd4c.eff",
        "decfile": "dec.dec",
        "plotDiff": 0,
        "ext": DEFAULT_D4CREG_EXTENSIONS,
        "run_blocks": [],
    }
    current_output_base = "vanadium"
    current_num: str | None = None
    pending_comment_lines: list[str] = []
    last_comment_block: str | None = None

    lines = par_file.read_text(encoding="utf-8").splitlines()
    for line_number, raw in enumerate(lines, start=1):
        stripped = raw.strip()
        if not stripped:
            if pending_comment_lines:
                last_comment_block = " ".join(pending_comment_lines).strip()
                pending_comment_lines = []
            continue
        if stripped[0] in {"#", "!"}:
            comment_line = _normalize_comment_title_line(stripped)
            if comment_line is not None:
                pending_comment_lines.append(comment_line)
            continue
        if stripped[0] != "<" or len(stripped) < 5 or stripped[4] != ">":
            raise ValueError(f"Wrong input in line: {line_number} file: {par_file}")

        if pending_comment_lines:
            last_comment_block = " ".join(pending_comment_lines).strip()
            pending_comment_lines = []

        content = stripped.split("#", 1)[0].strip()
        tag = content[:5]
        rest = content[5:].strip()
        parts = [part for part in rest.split() if part]

        if tag == "<rdp>" and parts:
            settings["path_raw"] = parts[0]
        elif tag == "<ext>":
            if len(parts) < 6:
                raise ValueError(f"Wrong input in line: {line_number} file: {par_file}")
            settings["ext"] = tuple(parts[:6])
        elif tag == "<eff>" and parts:
            settings["efffile"] = parts[0]
        elif tag == "<dec>" and parts:
            settings["decfile"] = parts[0]
        elif tag == "<plo>" and parts:
            settings["plotDiff"] = 1 if parts[0].strip().lower() == "true" else 0
        elif tag == "<out>" and parts:
            current_output_base = parts[0]
            current_num = None
        elif tag == "<num>" and parts:
            current_num = parts[0]
        elif tag == "<run>":
            label = (last_comment_block or "").strip() or _output_basename(current_output_base)
            settings["run_blocks"].append(
                {
                    "index": len(settings["run_blocks"]),
                    "label": label,
                    "file_base": current_output_base,
                    "num": current_num,
                    "ext": tuple(settings["ext"]),
                }
            )
            last_comment_block = None

    return settings


def validate_numors_par_file(par_file: Path, project_root: Path) -> NumorsValidationResult:
    resolved_par_file = par_file.expanduser().resolve(strict=False)
    if not resolved_par_file.exists():
        return NumorsValidationResult(
            is_valid=False,
            selected_par_path=str(resolved_par_file),
            error="Selected `.par` file was not found.",
        )
    if not resolved_par_file.is_file():
        return NumorsValidationResult(
            is_valid=False,
            selected_par_path=str(resolved_par_file),
            error="Selected path is not a file.",
        )
    if resolved_par_file.suffix.lower() != ".par":
        return NumorsValidationResult(
            is_valid=False,
            selected_par_path=str(resolved_par_file),
            error="Selected file must use the `.par` extension.",
        )

    try:
        parsed_settings = _parse_d4creg_par_metadata(resolved_par_file)
    except Exception as exc:
        return NumorsValidationResult(
            is_valid=False,
            selected_par_path=str(resolved_par_file),
            error=f"Could not parse `.par` file: {exc}",
        )

    try:
        rawdata_path = _resolve_required_path(
            resolved_par_file,
            project_root,
            str(parsed_settings["path_raw"]),
            "rawdata",
            must_be_dir=True,
        )
        efffile_path = _resolve_required_path(
            resolved_par_file,
            project_root,
            str(parsed_settings["efffile"]),
            "efffile",
            special_tokens=SPECIAL_PATH_TOKENS["efffile"],
        )
        decfile_path = _resolve_required_path(
            resolved_par_file,
            project_root,
            str(parsed_settings["decfile"]),
            "decfile",
            special_tokens=SPECIAL_PATH_TOKENS["decfile"],
        )
    except ValueError as exc:
        return NumorsValidationResult(
            is_valid=False,
            selected_par_path=str(resolved_par_file),
            file_accessible=True,
            error=str(exc),
        )

    return NumorsValidationResult(
        is_valid=True,
        selected_par_path=str(resolved_par_file),
        resolved_rawdata_path=rawdata_path,
        resolved_efffile_path=efffile_path,
        resolved_decfile_path=decfile_path,
        file_accessible=True,
        plot_enabled=bool(parsed_settings.get("plotDiff", 0)),
        error=None,
    )


def build_numors_summary_markdown(validation_state: dict[str, Any]) -> str:
    selected_par_path = validation_state.get("selected_par_path") or "Not selected"
    file_accessible = "Yes" if validation_state.get("file_accessible") else "No"
    lines = [
        f"**Selected file:** `{selected_par_path}`",
        f"**File accessible:** {file_accessible}",
    ]
    if validation_state.get("resolved_rawdata_path"):
        lines.append(f"**Resolved rawdata path:** `{validation_state['resolved_rawdata_path']}`")
    if validation_state.get("resolved_efffile_path"):
        lines.append(f"**Resolved efficiency path:** `{validation_state['resolved_efffile_path']}`")
    if validation_state.get("resolved_decfile_path"):
        lines.append(f"**Resolved shifts path:** `{validation_state['resolved_decfile_path']}`")
    return "\n".join(lines)


def execute_numors_workflow(
    par_file: Path,
    project_root: Path,
    run_id: str,
    workflow_runner: Callable[[dict[str, Any]], None] | None = None,
) -> NumorsExecutionResult:
    workflow_runner = parameters_module.d4creg if workflow_runner is None else workflow_runner
    resolved_par_file = par_file.expanduser().resolve(strict=False)
    project_root = project_root.resolve(strict=False)
    parsed_metadata = _parse_d4creg_par_metadata(resolved_par_file)
    parsed_run_blocks: list[dict[str, Any]] = list(parsed_metadata.get("run_blocks", []))

    processed_dir = resolved_par_file.parent.parent
    logfiles_dir = processed_dir / "logfiles"
    plots_dir = logfiles_dir / "plots" / run_id
    logfiles_dir.mkdir(parents=True, exist_ok=True)
    stdout_file = logfiles_dir / f"{run_id}-stdout.txt"

    status = "succeeded"
    error: str | None = None
    plot_files: list[str] = []
    plots_by_run_index: dict[int, list[str]] = {}
    logfile_path: str | None = None
    reg_file: str | None = None
    adat_file: str | None = None
    qdat_file: str | None = None
    run_block_results: list[dict[str, Any]] = []
    generated_files: list[str] = []
    file_base: str | None = None
    run_info: dict[str, Any] | None = None

    with stdout_file.open("w", encoding="utf-8") as stdout_handle:
        with _working_directory(resolved_par_file.parent):
            with redirect_stdout(stdout_handle), redirect_stderr(stdout_handle):
                try:
                    if not parsed_run_blocks:
                        raise ValueError("No `<run>` blocks were found in the selected `.par` file.")

                    _ensure_output_directories(resolved_par_file, project_root, parsed_run_blocks)

                    run_info_holder: dict[str, Any] = {}

                    def _execute_param_file() -> None:
                        import matplotlib.pyplot as plt

                        run_index = 0

                        def _runner_with_plot_tracking(run_info: dict[str, Any]) -> None:
                            nonlocal run_index
                            before = len(plot_files)
                            workflow_runner(run_info)
                            after = len(plot_files)
                            plots_by_run_index[run_index] = plot_files[before:after]
                            run_index += 1
                            plt.close("all")

                        with _patched_parameters_runner(_runner_with_plot_tracking):
                            run_info_holder["run_info"] = _sanitize_run_info(
                                readParam(str(resolved_par_file))
                            )

                    _capture_backend_plots(plots_dir, _execute_param_file, plot_files)
                    run_info = run_info_holder.get("run_info")
                    if run_info is not None:
                        file_base = str(run_info["file"])
                except Exception as exc:
                    status = "failed"
                    error = str(exc)
                    print(f"Numors execution failed: {exc}")
                finally:
                    if parsed_run_blocks:
                        (
                            logfile_path,
                            reg_file,
                            adat_file,
                            qdat_file,
                            generated_files,
                        ) = _discover_batch_run_outputs(
                            resolved_par_file,
                            parsed_run_blocks,
                            project_root,
                        )
                        run_block_results = _resolve_run_block_outputs(
                            resolved_par_file,
                            parsed_run_blocks,
                            project_root,
                            plots_by_run_index,
                        )

    summary_parts = [
        f"Processed `{resolved_par_file.name}`",
        f"status: `{status}`",
    ]
    summary_parts.append(f"run blocks: `{len(parsed_run_blocks)}`")
    if file_base:
        summary_parts.append(f"last output base: `{file_base}`")
    if generated_files:
        summary_parts.append(f"generated files: `{len(generated_files)}`")
    if plot_files:
        summary_parts.append(f"plots: `{len(plot_files)}`")
    if error:
        summary_parts.append(f"error: {error}")

    return NumorsExecutionResult(
        run_id=run_id,
        status=status,
        stdout_file=str(stdout_file),
        logfile=logfile_path,
        reg_file=reg_file,
        adat_file=adat_file,
        qdat_file=qdat_file,
        run_blocks=run_block_results,
        generated_files=generated_files,
        plot_files=plot_files,
        summary=", ".join(summary_parts),
        error=error,
    )


def _resolve_required_path(
    par_file: Path,
    project_root: Path,
    path_value: str,
    label: str,
    *,
    special_tokens: set[str] | None = None,
    must_be_dir: bool = False,
) -> str:
    normalized_value = path_value.strip()
    lowered_value = normalized_value.lower()
    if special_tokens and lowered_value in special_tokens:
        return lowered_value

    candidate = Path(normalized_value).expanduser()
    resolved_candidate = (
        candidate.resolve(strict=False)
        if candidate.is_absolute()
        else (par_file.parent / candidate).resolve(strict=False)
    )
    if not _is_within_project(resolved_candidate, project_root):
        raise ValueError(f"Resolved {label} path must stay inside the project.")
    if not resolved_candidate.exists():
        raise ValueError(f"Resolved {label} path does not exist.")
    if must_be_dir and not resolved_candidate.is_dir():
        raise ValueError(f"Resolved {label} path must be a directory.")
    if not must_be_dir and not resolved_candidate.is_file():
        raise ValueError(f"Resolved {label} path must be a file.")
    return str(resolved_candidate)


def _is_within_project(candidate: Path, project_root: Path) -> bool:
    try:
        candidate.relative_to(project_root.resolve(strict=False))
        return True
    except ValueError:
        return False


def _ensure_output_directories(
    par_file: Path,
    project_root: Path,
    run_blocks: list[dict[str, Any]],
) -> None:
    for run_block in run_blocks:
        output_base_path = (par_file.parent / str(run_block["file_base"])).resolve(strict=False)
        if not _is_within_project(output_base_path.parent, project_root):
            raise ValueError(
                "Resolved output path must stay inside the project. "
                f"Got: {output_base_path.parent}"
            )
        output_base_path.parent.mkdir(parents=True, exist_ok=True)


def _discover_batch_run_outputs(
    par_file: Path,
    run_blocks: list[dict[str, Any]],
    project_root: Path,
) -> tuple[str | None, str | None, str | None, str | None, list[str]]:
    generated_files: list[str] = []
    seen_files: set[str] = set()
    reg_file: str | None = None
    adat_file: str | None = None
    qdat_file: str | None = None

    for run_block in run_blocks:
        ext = tuple(run_block["ext"])
        base_path = (par_file.parent / str(run_block["file_base"])).resolve(strict=False)

        reg_candidate = _existing_project_file(base_path.with_suffix(ext[0]), project_root)
        adat_candidate = _existing_project_file(base_path.with_suffix(ext[1]), project_root)
        qdat_candidate = _existing_project_file(base_path.with_suffix(ext[2]), project_root)

        for candidate in (reg_candidate, adat_candidate, qdat_candidate):
            if candidate is not None and candidate not in seen_files:
                generated_files.append(candidate)
                seen_files.add(candidate)

        if reg_candidate is not None:
            reg_file = reg_candidate
        if adat_candidate is not None:
            adat_file = adat_candidate
        if qdat_candidate is not None:
            qdat_file = qdat_candidate

    logfile = _existing_project_file(
        (par_file.parent / ".." / "logfiles" / "d4creg.log").resolve(strict=False),
        project_root,
    )

    return logfile, reg_file, adat_file, qdat_file, generated_files


def _resolve_run_block_outputs(
    par_file: Path,
    run_blocks: list[dict[str, Any]],
    project_root: Path,
    plots_by_run_index: dict[int, list[str]] | None = None,
) -> list[dict[str, Any]]:
    resolved_blocks: list[dict[str, Any]] = []
    for run_block in run_blocks:
        ext = tuple(run_block["ext"])
        base_path = (par_file.parent / str(run_block["file_base"])).resolve(strict=False)
        adat_path = _existing_project_file(base_path.with_suffix(ext[1]), project_root)
        qdat_path = _existing_project_file(base_path.with_suffix(ext[2]), project_root)
        status = "succeeded" if adat_path and qdat_path else "failed"
        index = int(run_block.get("index", len(resolved_blocks)))
        plot_paths = (
            list((plots_by_run_index or {}).get(index, []))
            if plots_by_run_index is not None
            else []
        )
        resolved_blocks.append(
            {
                "index": index,
                "label": str(run_block.get("label") or _output_basename(str(run_block["file_base"]))),
                "file_base": str(run_block["file_base"]),
                "num": run_block.get("num"),
                "adat_file": adat_path,
                "qdat_file": qdat_path,
                "status": status,
                "plot_files": plot_paths,
            }
        )
    return resolved_blocks


def _existing_project_file(candidate: Path, project_root: Path) -> str | None:
    resolved_candidate = candidate.resolve(strict=False)
    if not _is_within_project(resolved_candidate, project_root):
        return None
    if not resolved_candidate.exists() or not resolved_candidate.is_file():
        return None
    return str(resolved_candidate)


def _sanitize_run_info(run_info: dict[str, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, value in run_info.items():
        if isinstance(value, str):
            sanitized[key] = value.strip()
        elif isinstance(value, list):
            sanitized[key] = [item.strip() if isinstance(item, str) else item for item in value]
        elif isinstance(value, tuple):
            sanitized[key] = tuple(
                item.strip() if isinstance(item, str) else item for item in value
            )
        else:
            sanitized[key] = value
    return sanitized


@contextmanager
def _patched_parameters_runner(workflow_runner: Callable[[dict[str, Any]], None]):
    original_runner = parameters_module.d4creg
    parameters_module.d4creg = workflow_runner
    try:
        yield
    finally:
        parameters_module.d4creg = original_runner


def _capture_backend_plots(
    plots_dir: Path,
    workflow: Callable[[], None],
    saved_plot_files: list[str] | None = None,
) -> list[str]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plots_dir.mkdir(parents=True, exist_ok=True)
    saved_plot_files = [] if saved_plot_files is None else saved_plot_files
    original_show = plt.show

    def _save_current_figure(*_args, **_kwargs) -> None:
        figure = plt.gcf()
        plot_path = plots_dir / f"plot-{len(saved_plot_files) + 1:03d}.png"
        figure.savefig(plot_path, dpi=150, bbox_inches="tight")
        saved_plot_files.append(str(plot_path))
        plt.close(figure)

    plt.show = _save_current_figure
    try:
        workflow()
    finally:
        plt.show = original_show
        plt.close("all")

    return saved_plot_files


@contextmanager
def _working_directory(target: str | PathLike[str]):
    previous = Path(getcwd())
    target_path = Path(target)
    try:
        chdir(target_path)
        yield
    finally:
        chdir(previous)
