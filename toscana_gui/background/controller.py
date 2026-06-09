from __future__ import annotations

import json
import os
import pickle
import re
import subprocess
import sys
from datetime import datetime
from html import escape as html_escape
from pathlib import Path

import numpy as np
import panel as pn

from toscana_gui.background.tasks import (
    BACKGROUND_SOURCE_OPTIONS,
    BackgroundExtractionResult,
    BACKGROUND_SUBTRACTION_METHOD_OPTIONS,
    background_par_signature,
    background_sample_key,
    is_par_file_in_processed_parfiles,
    list_sample_par_files,
    normalize_background_state,
    validate_background_par_file,
)
from toscana_gui.paths import REPO_ROOT
from toscana_gui.contexts import context_manifest_relpath, project_relpath, write_context_manifest
from toscana_gui.persistence import OutputPaths, PARIS_TZ, RunRecord, now_iso
from toscana_gui.background.plots import build_raw_data_figure
from toscana_gui.background.plots import (
    build_final_background_subtracted_signals_figure,
    build_linear_combination_chi_figure,
    build_linear_combination_subtraction_figure,
    build_vanadium_chi_figure,
    build_vanadium_subtraction_figure,
)
from toscana_gui.background.tasks import _working_directory
from toscana_gui.ui.screens.background import refresh_background_section_state
from toscana.experiment.measurement import Measurement
from toscana.math.fitting import fit_and_find_extremum, get_chi
from toscana.io.saving import saveFile_xye
from toscana.math.operations import binary_sum
from toscana.math.signal_processing import smooth_curve

BACKGROUND_SUBPROCESS_WORKER = REPO_ROOT / "background_subprocess_worker.py"


class BackgroundControllerMixin:
    _BACKGROUND_READY_TO_EXTRACT_MESSAGE = "Selected sample .par file is ready to extract."
    _BACKGROUND_EXPORT_NO_DATA_MESSAGE = "No data found to export. Run the background subtraction process."

    def _clear_background_cached_measurement_state(self) -> None:
        self._background_cached_measurement = None
        self._background_cached_artifact_path = None
        self._background_cached_artifact_mtime = None
        self._background_cached_par_filename = None
        self._background_cached_par_path = None
        self._background_plot_signature_cache = None

    def _show_background_ready_to_extract_toast(self) -> None:
        # Success state should not linger as an inline alert (it reads like a stale banner).
        self._show_success_toast(self._BACKGROUND_READY_TO_EXTRACT_MESSAGE)
        if hasattr(self, "background_message"):
            self.background_message.visible = False
            self.background_message.object = ""
            self.background_message.alert_type = "secondary"

    def _set_background_toast_notification(self, message: str, *, alert_type: str) -> None:
        if not hasattr(self, "background_message"):
            return
        self.background_message.object = message
        self.background_message.alert_type = alert_type
        self.background_message.visible = False

        if alert_type == "danger":
            self._show_error_toast(self.background_message.object)
        elif alert_type == "success":
            self._show_success_toast(self.background_message.object)
        elif alert_type == "warning":
            self._show_warning_toast(self.background_message.object)
        # we don't show info toast here since it is redundant

    def _sync_background_export_prompt_visibility(self) -> None:
        if not hasattr(self, "background_export_prompt_card"):
            return
        visible = bool(getattr(self.background_export_prompt, "visible", False))
        self.background_export_prompt_card.visible = visible

    def _sanitize_export_filename_stem(self, value: str) -> str:
        invalid = r'<>:"/\\|?*'
        cleaned = re.sub(f"[{re.escape(invalid)}]", "", str(value or "")).strip()
        cleaned = cleaned.strip().rstrip(" .")
        if not cleaned:
            return "sample"
        cleaned = re.sub(r"\s+", "_", cleaned)
        return cleaned[:120]

    def _resolve_background_export_dir(self) -> Path | None:
        if self.current_project_root is None:
            return None
        raw = str(getattr(self, "background_export_folder_input", None).value or "").strip() if hasattr(
            self, "background_export_folder_input"
        ) else ""
        if not raw:
            raw = "qspdata"
        candidate = Path(raw).expanduser()
        if not candidate.is_absolute():
            candidate = (self.current_project_root / candidate).resolve(strict=False)
        return candidate

    def _background_export_snapshot(self) -> dict[str, object]:
        snapshot: dict[str, object] = {
            "ready": False,
            "sample_name": None,
            "sample_t": None,
            "vanadium_t": None,
            "sample_qdat": None,
            "vanadium_qdat": None,
            "export_dir": None,
            "reason": None,
        }

        if self.current_project_state is None or self.current_project_root is None:
            snapshot["reason"] = "Open a project first."
            return snapshot

        export_dir = self._resolve_background_export_dir()
        snapshot["export_dir"] = str(export_dir) if export_dir is not None else None

        state = self._get_background_state()
        par_path_str = str(state.get("selected_par_path") or "").strip() or str(
            state.get("validation", {}).get("selected_par_path") or ""
        ).strip()
        if not par_path_str:
            snapshot["reason"] = "Select and extract a sample first."
            return snapshot

        sample_name = None
        measurement = self._background_export_measurement_snapshot().get("measurement")
        if measurement is not None:
            sample_name = getattr(measurement, "Title", None)
        if not sample_name:
            sample_name = Path(par_path_str).stem
        snapshot["sample_name"] = str(sample_name)

        sample_key = background_sample_key(Path(par_path_str), self.current_project_root)
        cached = state.get("measurements_by_par")
        if not sample_key or not isinstance(cached, dict):
            snapshot["reason"] = "Extract a sample first."
            return snapshot
        entry = cached.get(sample_key)
        if not isinstance(entry, dict):
            snapshot["reason"] = "Extract a sample first."
            return snapshot
        artifact_ref = entry.get("measurement_artifact")
        if not isinstance(artifact_ref, str) or not artifact_ref.strip():
            snapshot["reason"] = "Extract a sample first (measurement artifact missing)."
            return snapshot
        artifact_path = Path(artifact_ref).expanduser()
        if not artifact_path.is_absolute():
            artifact_path = (self.current_project_root / artifact_path).resolve(strict=False)
        if not artifact_path.exists():
            snapshot["reason"] = "Extract a sample first (measurement artifact missing)."
            return snapshot

        linear = entry.get("linear_combination")
        vanadium = entry.get("vanadium_linear_combination")
        if not isinstance(linear, dict) or not isinstance(vanadium, dict):
            snapshot["reason"] = "Compute both Sample and Vanadium linear combinations first."
            return snapshot

        sample_t = linear.get("effective_t")
        vanadium_t = vanadium.get("effective_t")
        if not isinstance(sample_t, (int, float)) or not isinstance(vanadium_t, (int, float)):
            snapshot["reason"] = "Compute both Sample and Vanadium linear combinations first."
            return snapshot

        snapshot["sample_t"] = float(sample_t)
        snapshot["vanadium_t"] = float(vanadium_t)

        if export_dir is None:
            snapshot["reason"] = "Choose an export folder."
            return snapshot

        stem = self._sanitize_export_filename_stem(str(sample_name))
        sample_qdat = export_dir / f"{stem}_sub.qdat"
        vanadium_qdat = export_dir / "vanadium_sub.qdat"
        snapshot["sample_qdat"] = str(sample_qdat)
        snapshot["vanadium_qdat"] = str(vanadium_qdat)

        measurement_snapshot = self._background_export_measurement_snapshot()
        if not measurement_snapshot.get("ready", False):
            snapshot["reason"] = str(
                measurement_snapshot.get("reason") or self._BACKGROUND_EXPORT_NO_DATA_MESSAGE
            )
            return snapshot

        snapshot["ready"] = True
        snapshot["reason"] = None
        return snapshot

    def _background_export_measurement_snapshot(self) -> dict[str, object]:
        snapshot: dict[str, object] = {
            "ready": False,
            "measurement": None,
            "sample_data": None,
            "container_data": None,
            "environment_data": None,
            "vanadium_data": None,
            "reason": None,
        }

        measurement = None
        # Deterministic behavior: tie export to the currently selected .par file cache entry.
        try:
            state = self._get_background_state()
            par_path_str = str(state.get("selected_par_path") or "").strip() or str(
                state.get("validation", {}).get("selected_par_path") or ""
            ).strip()
            if self.current_project_root is not None and par_path_str:
                sample_key = background_sample_key(Path(par_path_str), self.current_project_root)
            else:
                sample_key = None

            cached = state.get("measurements_by_par") if isinstance(state.get("measurements_by_par"), dict) else {}
            entry = cached.get(sample_key) if sample_key else None
            artifact_ref = entry.get("measurement_artifact") if isinstance(entry, dict) else None
            if isinstance(artifact_ref, str) and artifact_ref.strip() and self.current_project_root is not None:
                artifact_path = Path(artifact_ref).expanduser()
                if not artifact_path.is_absolute():
                    artifact_path = (self.current_project_root / artifact_path).resolve(strict=False)
                if artifact_path.exists() and artifact_path.is_file():
                    if artifact_path.suffix.lower() == ".pkl":
                        with artifact_path.open("rb") as handle:
                            measurement = pickle.load(handle)
                    else:
                        payload = json.loads(artifact_path.read_text(encoding="utf-8"))
                        if isinstance(payload, dict):
                            base_dir = Path(str(par_path_str)).expanduser().parent if par_path_str else artifact_path.parent
                            with _working_directory(base_dir):
                                measurement = Measurement(payload)
        except Exception:
            measurement = None

        if measurement is None:
            snapshot["reason"] = "No extracted measurement artifact is available for the selected .par file."
            return snapshot

        arrays: dict[str, np.ndarray] = {}
        required_sources = {
            "sample_data": ("Data", "sample"),
            "container_data": ("conData", "container"),
            "environment_data": ("envData", "environment"),
            "vanadium_data": ("norData", "vanadium"),
        }
        for key, (attribute_name, label) in required_sources.items():
            raw_value = getattr(measurement, attribute_name, None)
            if raw_value is None:
                snapshot["reason"] = self._BACKGROUND_EXPORT_NO_DATA_MESSAGE
                snapshot["measurement"] = measurement
                return snapshot
            array = np.asarray(raw_value)
            if array.ndim != 2 or array.shape[0] == 0 or array.shape[1] < 2:
                snapshot["reason"] = self._BACKGROUND_EXPORT_NO_DATA_MESSAGE
                snapshot["measurement"] = measurement
                return snapshot
            arrays[key] = array

        sample_data = arrays["sample_data"]
        container_data = arrays["container_data"]
        environment_data = arrays["environment_data"]
        vanadium_data = arrays["vanadium_data"]

        if sample_data.shape[0] != container_data.shape[0] or sample_data.shape[0] != environment_data.shape[0]:
            snapshot["reason"] = self._BACKGROUND_EXPORT_NO_DATA_MESSAGE
            snapshot["measurement"] = measurement
            return snapshot
        if vanadium_data.shape[0] != environment_data.shape[0]:
            snapshot["reason"] = self._BACKGROUND_EXPORT_NO_DATA_MESSAGE
            snapshot["measurement"] = measurement
            return snapshot

        snapshot["ready"] = True
        snapshot["measurement"] = measurement
        snapshot["sample_data"] = sample_data
        snapshot["container_data"] = container_data
        snapshot["environment_data"] = environment_data
        snapshot["vanadium_data"] = vanadium_data
        snapshot["reason"] = None
        return snapshot

    def _refresh_background_export_hovercard(self) -> None:
        if not hasattr(self, "background_export_info_hover"):
            return

        snap = self._background_export_snapshot()
        ready = bool(snap.get("ready", False))
        status = "Ready" if ready else "Not ready"
        reason = html_escape(str(snap.get("reason") or ""))

        body_lines = [
            f"<div><strong>Status:</strong> {html_escape(status)}</div>",
        ]
        if ready:
            sample_name = html_escape(str(snap.get("sample_name") or ""))
            sample_t = snap.get("sample_t")
            vanadium_t = snap.get("vanadium_t")
            sample_t_text = "missing" if sample_t is None else f"{float(sample_t):.5f}"
            vanadium_t_text = "missing" if vanadium_t is None else f"{float(vanadium_t):.5f}"
            sample_qdat = html_escape(str(snap.get("sample_qdat") or ""))
            van_qdat = html_escape(str(snap.get("vanadium_qdat") or ""))
            if sample_name:
                body_lines.append(f"<div><strong>Sample:</strong> {sample_name}</div>")
            body_lines.append(
                "<div><strong>t sample:</strong> "
                f"<code style=\"white-space: normal; overflow-wrap: anywhere; word-break: break-word;\">{html_escape(sample_t_text)}</code>"
                "</div>"
            )
            if sample_qdat:
                body_lines.append(
                    "<div><strong>Qdat sample:</strong> "
                    f"<code style=\"white-space: normal; overflow-wrap: anywhere; word-break: break-word;\">{sample_qdat}</code>"
                    "</div>"
                )
            body_lines.append(f"<div><strong>Normalisation:</strong> Vanadium</div>")
            body_lines.append(
                "<div><strong>t normalisation:</strong> "
                f"<code style=\"white-space: normal; overflow-wrap: anywhere; word-break: break-word;\">{html_escape(vanadium_t_text)}</code>"
                "</div>"
            )
            if van_qdat:
                body_lines.append(
                    "<div><strong>Qdat vanadium:</strong> "
                    f"<code style=\"white-space: normal; overflow-wrap: anywhere; word-break: break-word;\">{van_qdat}</code>"
                    "</div>"
                )
        elif reason:
            body_lines.append(f"<div style=\"margin-top: 8px;\"><em>{reason}</em></div>")

        self.background_export_info_hover.value = (
            "<div style=\"max-width: 320px; line-height: 1.6; white-space: normal; overflow-wrap: anywhere; word-break: break-word;\">"
            + "\n".join(body_lines)
            + "</div>"
        )

    def _background_export_is_ready(self) -> bool:
        return bool(self._background_export_snapshot().get("ready", False))

    def _on_background_export_folder_change(self, event) -> None:
        if getattr(self, "_suspend_background_events", False) or self.current_project_state is None:
            return
        if event.new == event.old:
            return
        # Changing the folder invalidates any pending confirmation prompt.
        self._pending_background_export = None
        if hasattr(self, "background_export_prompt"):
            self.background_export_prompt.visible = False
        self._sync_background_export_prompt_visibility()
        self._refresh_background_export_hovercard()
        self._refresh_interaction_states()

    def _prompt_background_export(self, _event=None) -> None:
        if self.operation_in_progress:
            self._show_workspace_blocked_message()
            return
        if self.current_project_state is None or self.current_project_root is None:
            self._show_warning_toast("Open a project first.")
            return
        if bool(getattr(getattr(self, "background_export_prompt", None), "visible", False)):
            self._cancel_background_export()
            return

        snap = self._background_export_snapshot()
        if not snap.get("ready", False):
            self._show_warning_toast(str(snap.get("reason") or "Export is not ready yet."))
            return

        export_dir = Path(str(snap["export_dir"]))
        sample_qdat = Path(str(snap["sample_qdat"]))
        vanadium_qdat = Path(str(snap["vanadium_qdat"]))

        measurement_snapshot = self._background_export_measurement_snapshot()
        if not measurement_snapshot.get("ready", False):
            self._show_warning_toast(
                str(measurement_snapshot.get("reason") or "No extracted data is available to export yet.")
            )
            return
        dat_arr = np.asarray(measurement_snapshot["sample_data"])
        con_arr = np.asarray(measurement_snapshot["container_data"])
        env_arr = np.asarray(measurement_snapshot["environment_data"])
        nor_arr = np.asarray(measurement_snapshot["vanadium_data"])

        def _has_err(a: np.ndarray) -> bool:
            return isinstance(a, np.ndarray) and a.ndim == 2 and a.shape[1] >= 3

        missing_sample_error = not (_has_err(dat_arr) and _has_err(con_arr) and _has_err(env_arr))
        missing_van_error = not (_has_err(nor_arr) and _has_err(env_arr))
        missing_error_any = bool(missing_sample_error or missing_van_error)

        overwrite_targets: list[str] = []
        if sample_qdat.exists():
            overwrite_targets.append(str(sample_qdat))
        if vanadium_qdat.exists():
            overwrite_targets.append(str(vanadium_qdat))

        self._pending_background_export = {
            "export_dir": export_dir,
            "sample_qdat": sample_qdat,
            "vanadium_qdat": vanadium_qdat,
            "write_zero_errors": bool(missing_error_any),
        }

        if overwrite_targets or missing_error_any:
            lines: list[str] = [
                f"Export folder: `{export_dir}`",
                "",
                f"Will write sample: `{sample_qdat.name}`",
                f"Will write vanadium: `{vanadium_qdat.name}`",
            ]
            if overwrite_targets:
                lines.extend(["", "**Overwrite warning:**", *[f"- `{p}`" for p in overwrite_targets]])
            if missing_error_any:
                missing_parts = []
                if missing_sample_error:
                    missing_parts.append("sample")
                if missing_van_error:
                    missing_parts.append("vanadium")
                lines.extend(
                    [
                        "",
                        "**Missing error column:**",
                        f"Error bars are missing for: {', '.join(missing_parts)}.",
                        "Proceeding will write zeros in the error column for those exports.",
                    ]
                )

            self.background_export_prompt.object = "\n".join(lines)
            self.background_export_prompt.alert_type = "warning" if missing_error_any else "danger"
            self.background_export_prompt.visible = True
            self._sync_background_export_prompt_visibility()
            self._refresh_interaction_states()
            return

        self._perform_background_export()

    def _cancel_background_export(self, _event=None) -> None:
        self._pending_background_export = None
        if hasattr(self, "background_export_prompt"):
            self.background_export_prompt.visible = False
        self._sync_background_export_prompt_visibility()
        self._refresh_interaction_states()

    def _confirm_background_export(self, _event=None) -> None:
        if self.operation_in_progress:
            self._show_workspace_blocked_message()
            return
        if self._pending_background_export is None:
            return
        self._perform_background_export()

    def _perform_background_export(self) -> None:
        snap = self._background_export_snapshot()
        if not snap.get("ready", False):
            self._show_warning_toast(str(snap.get("reason") or "Export is not ready yet."))
            return
        if self.current_project_root is None or self.current_project_state is None:
            return

        export_dir = Path(str(snap["export_dir"]))
        sample_qdat = Path(str(snap["sample_qdat"]))
        vanadium_qdat = Path(str(snap["vanadium_qdat"]))
        pending = getattr(self, "_pending_background_export", None)
        write_zero_errors = bool(pending.get("write_zero_errors", False)) if isinstance(pending, dict) else False

        measurement_snapshot = self._background_export_measurement_snapshot()
        if not measurement_snapshot.get("ready", False):
            self._show_warning_toast(
                str(measurement_snapshot.get("reason") or "No extracted data is available to export yet.")
            )
            return
        sample_t = float(snap["sample_t"])
        vanadium_t = float(snap["vanadium_t"])
        background_state = self._get_background_state()
        par_path_str = str(background_state.get("selected_par_path") or "").strip() or str(
            background_state.get("validation", {}).get("selected_par_path") or ""
        ).strip()

        run_id = self._create_run_id()
        record = RunRecord(
            run_id=run_id,
            workflow="background_export",
            status="running",
            started_at=now_iso(),
            summary=f"Exporting qdat files to `{export_dir}`",
            workflow_data={
                "export_dir": str(export_dir),
                "sample_qdat": str(sample_qdat),
                "vanadium_qdat": str(vanadium_qdat),
                "t_sample": sample_t,
                "t_vanadium": vanadium_t,
                "write_zero_errors": write_zero_errors,
            },
            output_paths=OutputPaths(generated_files=[]),
        )
        self.current_project_state.runs.append(record)
        self.current_project_state.project.updated_at = now_iso()
        self._persist_current_project_state()

        try:
            dat_arr = np.asarray(measurement_snapshot["sample_data"])
            con_arr = np.asarray(measurement_snapshot["container_data"])
            env_arr = np.asarray(measurement_snapshot["environment_data"])
            nor_arr = np.asarray(measurement_snapshot["vanadium_data"])

            export_dir.mkdir(parents=True, exist_ok=True)

            # Build exported series.
            x = dat_arr[:, 0]
            sample_y = dat_arr[:, 1] - (sample_t * con_arr[:, 1] + (1.0 - sample_t) * env_arr[:, 1])
            sample_e = np.zeros_like(sample_y, dtype=float)
            if dat_arr.shape[1] >= 3 and con_arr.shape[1] >= 3 and env_arr.shape[1] >= 3:
                bckgt = binary_sum(sample_t, con_arr, 1.0 - sample_t, env_arr)
                subt = binary_sum(1.0, dat_arr, -1.0, bckgt) if bckgt is not None else None
                if subt is not None and subt.shape[1] >= 3:
                    sample_y = subt[:, 1]
                    sample_e = subt[:, 2]
            elif not write_zero_errors:
                raise RuntimeError("Missing error columns for sample export.")

            vx = nor_arr[:, 0]
            van_y = nor_arr[:, 1] - vanadium_t * env_arr[:, 1]
            van_e = np.zeros_like(van_y, dtype=float)
            if nor_arr.shape[1] >= 3 and env_arr.shape[1] >= 3:
                subt = binary_sum(1.0, nor_arr, -vanadium_t, env_arr)
                if subt is not None and subt.shape[1] >= 3:
                    van_y = subt[:, 1]
                    van_e = subt[:, 2]
            elif not write_zero_errors:
                raise RuntimeError("Missing error columns for vanadium export.")

            sample_heading, van_heading = self._background_export_headings(
                par_path_str=par_path_str,
                sample_t=sample_t,
                vanadium_t=vanadium_t,
            )

            saveFile_xye(str(sample_qdat), x, sample_y, sample_e, sample_heading)
            saveFile_xye(str(vanadium_qdat), vx, van_y, van_e, van_heading)

            manifest_payload: dict[str, object] = {
                "schema_version": 1,
                "context_id": run_id,
                "workflow": "background",
                "created_at": now_iso(),
                "source": {
                    "kind": "background_export",
                    "run_id": run_id,
                },
                "sample": {},
                "decisions": {
                    "t_sample": float(sample_t),
                    "t_vanadium": float(vanadium_t),
                },
                "artifacts": {},
            }

            try:
                sample_key = (
                    background_sample_key(Path(par_path_str), self.current_project_root)
                    if par_path_str and self.current_project_root is not None
                    else None
                )
                signature = background_par_signature(Path(par_path_str)) if par_path_str else None

                measurement = measurement_snapshot.get("measurement")
                title = getattr(measurement, "Title", None) if measurement is not None else None
                name = getattr(measurement, "Name", None) if measurement is not None else None

                sample_block: dict[str, object] = {}
                if sample_key:
                    sample_block["sample_key"] = sample_key
                if par_path_str:
                    sample_block["par_path"] = par_path_str
                    try:
                        resolved = Path(par_path_str).expanduser().resolve(strict=False)
                        if self.current_project_root is not None:
                            sample_block["par_path_rel"] = project_relpath(self.current_project_root, resolved)
                    except Exception:
                        pass
                if signature is not None:
                    sample_block["par_signature"] = {"mtime": float(signature[0]), "size": int(signature[1])}
                if title:
                    sample_block["title"] = str(title)
                if name:
                    sample_block["name"] = str(name)

                if sample_key and isinstance(background_state.get("measurements_by_par"), dict):
                    entry = background_state["measurements_by_par"].get(sample_key)
                else:
                    entry = None
                if isinstance(entry, dict):
                    artifact = entry.get("measurement_artifact")
                    if isinstance(artifact, str) and artifact.strip():
                        sample_block["measurement_artifact"] = artifact
                    linear = entry.get("linear_combination")
                    if isinstance(linear, dict):
                        manifest_payload["decisions"] = {
                            **dict(manifest_payload.get("decisions") or {}),
                            "linear_combination": {
                                k: linear.get(k)
                                for k in (
                                    "best_t",
                                    "t_mode",
                                    "custom_t",
                                    "effective_t",
                                    "computed_at",
                                    "settings",
                                )
                                if k in linear
                            },
                        }
                    vanadium = entry.get("vanadium_linear_combination")
                    if isinstance(vanadium, dict):
                        manifest_payload["decisions"] = {
                            **dict(manifest_payload.get("decisions") or {}),
                            "vanadium_linear_combination": {
                                k: vanadium.get(k)
                                for k in (
                                    "best_t",
                                    "t_mode",
                                    "custom_t",
                                    "effective_t",
                                    "computed_at",
                                    "settings",
                                )
                                if k in vanadium
                            },
                        }

                manifest_payload["sample"] = sample_block
                manifest_payload["artifacts"] = {
                    "export_dir": str(export_dir),
                    "sample_sub_qdat": str(sample_qdat),
                    "vanadium_sub_qdat": str(vanadium_qdat),
                }
            except Exception:
                # Manifest is best-effort: do not fail export if provenance capture fails.
                pass

            manifest_file = None
            try:
                manifest_file = write_context_manifest(
                    self.current_project_root,
                    context_id=run_id,
                    payload=manifest_payload,
                )
                record.workflow_data["context_manifest"] = context_manifest_relpath(
                    self.current_project_root,
                    manifest_file,
                )
            except Exception:
                manifest_file = None

            if manifest_file is not None:
                try:
                    manifest_rel = str(record.workflow_data.get("context_manifest") or "").strip()
                    if manifest_rel:
                        background_state = self._get_background_state()
                        contexts = background_state.get("contexts") if isinstance(background_state.get("contexts"), dict) else {}
                        entries = contexts.get("entries") if isinstance(contexts.get("entries"), list) else []
                        sample_block = manifest_payload.get("sample") if isinstance(manifest_payload.get("sample"), dict) else {}
                        sample_key = sample_block.get("sample_key") if isinstance(sample_block.get("sample_key"), str) else None
                        sample_title = (
                            sample_block.get("title")
                            if isinstance(sample_block.get("title"), str)
                            else str(snap.get("sample_name") or "")
                        )

                        new_entry: dict[str, object] = {
                            "context_id": run_id,
                            "manifest": manifest_rel,
                            "created_at": now_iso(),
                            "sample_title": sample_title,
                            "status": "ok",
                        }
                        if sample_key:
                            new_entry["sample_key"] = sample_key
                        contexts["active_context_id"] = run_id
                        contexts["entries"] = [new_entry, *[e for e in entries if e.get("context_id") != run_id]]
                        background_state["contexts"] = contexts
                        self._persist_background_state(background_state)
                except Exception:
                    pass

            record.status = "succeeded"
            record.finished_at = now_iso()
            record.summary = "Exported qdat files."
            generated_files = [
                str(sample_qdat.resolve(strict=False)),
                str(vanadium_qdat.resolve(strict=False)),
            ]
            if manifest_file is not None:
                generated_files.append(str(manifest_file.resolve(strict=False)))
            record.output_paths.generated_files = generated_files
            self.current_project_state.project.updated_at = now_iso()
            self._persist_current_project_state()
            self._show_success_toast("Exported qdat files.")
        except Exception as exc:
            record.status = "failed"
            record.finished_at = now_iso()
            record.error = str(exc)
            self.current_project_state.project.updated_at = now_iso()
            self._persist_current_project_state()
            self._show_error_toast(f"Export failed: {exc}")
        finally:
            self._pending_background_export = None
            if hasattr(self, "background_export_prompt"):
                self.background_export_prompt.visible = False
            self._sync_background_export_prompt_visibility()
            self._refresh_interaction_states()
            self._refresh_background_export_hovercard()

    def _background_export_headings(
        self,
        *,
        par_path_str: str,
        sample_t: float,
        vanadium_t: float,
    ) -> tuple[list[str], list[str]]:
        origin_path = Path(par_path_str).expanduser()
        if not origin_path.is_absolute() and self.current_project_root is not None:
            origin_path = (self.current_project_root / origin_path).resolve(strict=False)
        else:
            origin_path = origin_path.resolve(strict=False)
        origin_line = f"Origin of data {origin_path}"

        sample_heading = [
            "Background subtracted diffractogram",
            "Subtraction method: sample - (t*cell+(1-t)*env)",
            origin_line,
            f"t = {sample_t:.5f}",
            " ",
            " Q (1/Å)         Intensity              Error",
        ]
        van_heading = [
            "Background subtracted diffractogram",
            "Subtraction method: vanadium - (t*env)",
            origin_line,
            f"t = {vanadium_t:.5f}",
            " ",
            " Q (1/Å)         Intensity              Error",
        ]
        return sample_heading, van_heading

    def _clear_background_linear_and_vanadium_plot_cards(self) -> None:
        if hasattr(self, "background_linear_chi_plot_pane"):
            self.background_linear_chi_plot_pane.object = None
        if hasattr(self, "background_linear_subtraction_plot_pane"):
            self.background_linear_subtraction_plot_pane.object = None
        if hasattr(self, "background_vanadium_chi_plot_pane"):
            self.background_vanadium_chi_plot_pane.object = None
        if hasattr(self, "background_vanadium_subtraction_plot_pane"):
            self.background_vanadium_subtraction_plot_pane.object = None
        if hasattr(self, "background_final_signals_plot_pane"):
            self.background_final_signals_plot_pane.object = None

    def _reset_background_t_controls_ui(self) -> None:
        self._suspend_background_events = True
        try:
            self.background_linear_t_mode.value = "Use computed t"
            self.background_linear_custom_t.value = 0.8
            self.background_linear_custom_t.disabled = True
            self.background_vanadium_t_mode.value = "Use computed t"
            self.background_vanadium_custom_t.value = 0.8
            self.background_vanadium_custom_t.disabled = True
        finally:
            self._suspend_background_events = False

    def _set_background_source_widget_visibility(self) -> None:
        mode = str(getattr(self.background_source_mode, "value", "") or BACKGROUND_SOURCE_OPTIONS[0])
        is_select_mode = mode == "Select File"
        if hasattr(self, "background_par_dropdown"):
            self.background_par_dropdown.visible = is_select_mode
        if hasattr(self, "background_manual_path_input"):
            self.background_manual_path_input.visible = not is_select_mode
        if is_select_mode:
            self._suspend_background_events = True
            try:
                self._refresh_background_par_dropdown_options()
            finally:
                self._suspend_background_events = False

    def _sync_background_method_cards_visibility(self) -> None:
        selected_method = str(getattr(self.background_subtraction_method, "value", "") or "")
        show_linear = selected_method == BACKGROUND_SUBTRACTION_METHOD_OPTIONS[0]
        show_monte_carlo = selected_method == BACKGROUND_SUBTRACTION_METHOD_OPTIONS[1]
        if hasattr(self, "background_linear_controls_card"):
            self.background_linear_controls_card.visible = bool(show_linear)
        if hasattr(self, "background_vanadium_controls_card"):
            self.background_vanadium_controls_card.visible = bool(show_linear)
        if hasattr(self, "background_monte_carlo_card"):
            self.background_monte_carlo_card.visible = bool(show_monte_carlo)

    def _sync_background_import_visibility(self) -> None:
        if hasattr(self, "background_import_card"):
            self.background_import_card.visible = bool(getattr(self.background_import_prompt, "visible", False))

    def _sync_background_import_prompt_from_selection(self) -> None:
        if not hasattr(self, "background_import_prompt"):
            return
        if self.current_project_state is None or self.current_project_root is None:
            self._clear_background_import_prompt()
            return

        state = self._get_background_state()
        selected = str(state.get("selected_par_path") or state.get("validation", {}).get("selected_par_path") or "").strip()
        if not selected:
            self._clear_background_import_prompt()
            return

        try:
            selected_path = Path(selected).expanduser().resolve(strict=False)
        except Exception:
            self._clear_background_import_prompt()
            return

        if not selected_path.exists() or not selected_path.is_file():
            self._clear_background_import_prompt()
            return

        if is_par_file_in_processed_parfiles(selected_path, self.current_project_root):
            self._clear_background_import_prompt()
            return

        self._pending_background_import_path = selected_path
        self.background_import_prompt.object = (
            "The selected .par file is outside `parfiles/`. "
            "Copy it into `parfiles/` to continue."
        )
        self.background_import_prompt.alert_type = "warning"
        self.background_import_prompt.visible = True
        self._sync_background_import_visibility()

    def _refresh_background_selection_section_state(self) -> None:
        refresh_background_section_state(self)
        self._sync_background_import_prompt_from_selection()

    def _sync_background_linear_controls_from_cache(self, sample_key: str) -> None:
        if self.current_project_state is None:
            return
        state = self._get_background_state()
        cached = state.get("measurements_by_par")
        if not isinstance(cached, dict):
            return
        entry = cached.get(sample_key)
        if not isinstance(entry, dict):
            return

        def _apply_mode_to_widgets(mode_value: str, *, mode_widget, custom_widget) -> None:
            if mode_value == "custom":
                mode_widget.value = "Use custom t"
                custom_widget.disabled = False
            else:
                mode_widget.value = "Use computed t"
                custom_widget.disabled = True

        self._suspend_background_events = True
        try:
            linear = entry.get("linear_combination")
            if isinstance(linear, dict):
                custom_t = linear.get("custom_t")
                if isinstance(custom_t, (int, float)):
                    self.background_linear_custom_t.value = float(custom_t)
                mode_value = str(linear.get("t_mode") or "computed")
                _apply_mode_to_widgets(
                    mode_value,
                    mode_widget=self.background_linear_t_mode,
                    custom_widget=self.background_linear_custom_t,
                )
            else:
                _apply_mode_to_widgets(
                    "computed",
                    mode_widget=self.background_linear_t_mode,
                    custom_widget=self.background_linear_custom_t,
                )

            if hasattr(self, "background_sample_custom_t_input") and isinstance(linear, dict):
                custom_t = linear.get("custom_t")
                if isinstance(custom_t, (int, float)) and np.isfinite(float(custom_t)):
                    self.background_sample_custom_t_input.value = float(custom_t)
            if hasattr(self, "background_sample_use_custom_t_toggle"):
                is_custom = isinstance(linear, dict) and str(linear.get("t_mode") or "computed") == "custom"
                self.background_sample_use_custom_t_toggle.value = bool(is_custom)
            if hasattr(self, "background_sample_use_custom_t_button") and hasattr(
                self, "background_sample_use_computed_t_button"
            ):
                is_custom = isinstance(linear, dict) and str(linear.get("t_mode") or "computed") == "custom"
                if is_custom:
                    self.background_sample_use_custom_t_button.button_type = "primary"
                    self.background_sample_use_computed_t_button.button_type = "light"
                else:
                    self.background_sample_use_computed_t_button.button_type = "primary"
                    self.background_sample_use_custom_t_button.button_type = "light"

            vanadium = entry.get("vanadium_linear_combination")
            if isinstance(vanadium, dict):
                custom_t = vanadium.get("custom_t")
                if isinstance(custom_t, (int, float)):
                    self.background_vanadium_custom_t.value = float(custom_t)
                mode_value = str(vanadium.get("t_mode") or "computed")
                _apply_mode_to_widgets(
                    mode_value,
                    mode_widget=self.background_vanadium_t_mode,
                    custom_widget=self.background_vanadium_custom_t,
                )
            else:
                _apply_mode_to_widgets(
                    "computed",
                    mode_widget=self.background_vanadium_t_mode,
                    custom_widget=self.background_vanadium_custom_t,
                )

            if hasattr(self, "background_vanadium_custom_t_input") and isinstance(vanadium, dict):
                custom_t = vanadium.get("custom_t")
                if isinstance(custom_t, (int, float)) and np.isfinite(float(custom_t)):
                    self.background_vanadium_custom_t_input.value = float(custom_t)
            if hasattr(self, "background_vanadium_use_custom_t_toggle"):
                is_custom = isinstance(vanadium, dict) and str(vanadium.get("t_mode") or "computed") == "custom"
                self.background_vanadium_use_custom_t_toggle.value = bool(is_custom)
            if hasattr(self, "background_vanadium_use_custom_t_button") and hasattr(
                self, "background_vanadium_use_computed_t_button"
            ):
                is_custom = isinstance(vanadium, dict) and str(vanadium.get("t_mode") or "computed") == "custom"
                if is_custom:
                    self.background_vanadium_use_custom_t_button.button_type = "primary"
                    self.background_vanadium_use_computed_t_button.button_type = "light"
                else:
                    self.background_vanadium_use_computed_t_button.button_type = "primary"
                    self.background_vanadium_use_custom_t_button.button_type = "light"
        finally:
            self._suspend_background_events = False

    def _persist_background_vanadium_settings(self) -> None:
        if self.current_project_state is None:
            return
        state = self._get_background_state()
        state["vanadium_linear_settings"] = {
            "t_start": float(self.background_vanadium_t_start.value),
            "t_stop": float(self.background_vanadium_t_stop.value),
            "t_step": float(self.background_vanadium_t_step.value),
            "smoothing_factor": float(self.background_vanadium_smoothing.value),
            "ignore_points": int(self.background_vanadium_ignore_points.value),
        }
        self._persist_background_state(state)

    def _on_background_vanadium_settings_change(self, event) -> None:
        if getattr(self, "_suspend_background_events", False) or self.current_project_state is None:
            return
        if event.new == event.old:
            return
        self._persist_background_vanadium_settings()

    def _apply_background_vanadium_t_override(self) -> None:
        if self.current_project_state is None or self.current_project_root is None:
            return
        par_path_str = getattr(self, "_background_cached_par_path", None)
        if not par_path_str:
            return
        sample_key = background_sample_key(Path(par_path_str), self.current_project_root)
        if not sample_key:
            return
        state = self._get_background_state()
        cached = state.get("measurements_by_par")
        if not isinstance(cached, dict):
            return
        entry = cached.get(sample_key)
        if not isinstance(entry, dict):
            return
        vanadium = entry.get("vanadium_linear_combination")
        if not isinstance(vanadium, dict):
            return

        mode = str(self.background_vanadium_t_mode.value or "Use computed t")
        best_t = vanadium.get("best_t")
        custom_t = float(self.background_vanadium_custom_t.value)
        if mode == "Use custom t":
            vanadium["t_mode"] = "custom"
            vanadium["custom_t"] = custom_t
            vanadium["effective_t"] = custom_t
            self.background_vanadium_message.object = f"Using custom t = {custom_t:.5f}"
            self.background_vanadium_message.alert_type = "warning"
        else:
            vanadium["t_mode"] = "computed"
            if isinstance(best_t, (int, float)):
                vanadium["effective_t"] = float(best_t)
                self.background_vanadium_message.object = f"Using computed t = {float(best_t):.5f}"
                self.background_vanadium_message.alert_type = "success"
            else:
                self.background_vanadium_message.object = (
                    "No computed t is available yet. Click Compute."
                )
                self.background_vanadium_message.alert_type = "danger"

        entry["vanadium_linear_combination"] = vanadium
        cached[sample_key] = entry
        self._persist_background_state(state)
        self._refresh_background_plots()
        self._refresh_interaction_states()

    def _on_background_vanadium_t_selection_change(self, event) -> None:
        if getattr(self, "_suspend_background_events", False) or self.current_project_state is None:
            return
        if event.new == event.old:
            return
        mode = str(self.background_vanadium_t_mode.value or "Use computed t")
        self.background_vanadium_custom_t.disabled = mode != "Use custom t"
        self._apply_background_vanadium_t_override()

    def _compute_background_vanadium_linear_combination(self, _event=None) -> None:
        if getattr(self, "_suspend_background_events", False) or self.current_project_state is None:
            return

        measurement = self._load_latest_measurement()
        if measurement is None:
            self.background_vanadium_message.object = "Extract a sample measurement first."
            self.background_vanadium_message.alert_type = "danger"
            self._refresh_interaction_states()
            return

        if self.current_project_root is None:
            self.background_vanadium_message.object = "Open a project first."
            self.background_vanadium_message.alert_type = "danger"
            self._refresh_interaction_states()
            return

        state = self._get_background_state()
        self._persist_background_vanadium_settings()
        settings = dict(state.get("vanadium_linear_settings") or {})
        try:
            result = self._run_vanadium_linear_combination(measurement, settings=settings)
        except Exception as exc:
            self.background_vanadium_message.object = f"Vanadium background computation failed: {exc}"
            self.background_vanadium_message.alert_type = "danger"
            self._refresh_interaction_states()
            return

        par_path_str = getattr(self, "_background_cached_par_path", None)
        if not par_path_str:
            par_path_str = str(state.get("validation", {}).get("selected_par_path") or "").strip()
        sample_key = background_sample_key(Path(par_path_str), self.current_project_root) if par_path_str else None
        if not sample_key:
            self.background_vanadium_message.object = "Could not determine which sample .par this result belongs to."
            self.background_vanadium_message.alert_type = "danger"
            self._refresh_interaction_states()
            return

        cached = state.get("measurements_by_par")
        if not isinstance(cached, dict) or sample_key not in cached:
            self.background_vanadium_message.object = "This sample is not present in the extraction cache yet."
            self.background_vanadium_message.alert_type = "danger"
            self._refresh_interaction_states()
            return

        cached_entry = cached.get(sample_key, {})
        if not isinstance(cached_entry, dict):
            cached_entry = {}

        best_t = result.get("best_t")
        custom_t = float(getattr(self.background_vanadium_custom_t, "value", 0.8))
        result["t_mode"] = "computed"
        result["custom_t"] = custom_t
        if isinstance(best_t, (int, float)):
            result["effective_t"] = float(best_t)

        cached_entry["vanadium_linear_combination"] = result
        cached[sample_key] = cached_entry
        self._persist_background_state(state)

        self._suspend_background_events = True
        self.background_vanadium_t_mode.value = "Use computed t"
        self.background_vanadium_custom_t.disabled = True
        self._suspend_background_events = False

        if isinstance(best_t, float):
            self.background_vanadium_message.object = f"Computed best t = {best_t:.5f}"
            self.background_vanadium_message.alert_type = "success"
        else:
            self.background_vanadium_message.object = "Computed best t."
            self.background_vanadium_message.alert_type = "success"
        self._refresh_background_plots()
        self._refresh_interaction_states()

    def _run_vanadium_linear_combination(self, measurement, *, settings: dict) -> dict:

        vanadium = getattr(measurement, "norData", None)
        environment = getattr(measurement, "envData", None)
        if vanadium is None or environment is None:
            raise ValueError("Vanadium and Environment data are required for Vanadium background computation.")

        t_start = float(settings.get("t_start", -1.0))
        t_stop = float(settings.get("t_stop", 2.0))
        t_step = float(settings.get("t_step", 0.05))
        smoothing_factor = float(settings.get("smoothing_factor", 0.01))
        ignore_points = int(settings.get("ignore_points", 25))
        if t_step <= 0:
            raise ValueError("t step must be > 0.")
        if t_stop <= t_start:
            raise ValueError("t stop must be greater than t start.")
        if ignore_points < 0:
            raise ValueError("Ignore points must be >= 0.")

        trans_arr = np.arange(t_start, t_stop, t_step, dtype=float)
        if trans_arr.size < 3:
            raise ValueError("t range must include at least 3 values.")

        x_v = np.asarray(vanadium)[:, 0]
        y_v = np.asarray(vanadium)[:, 1]
        x_env = np.asarray(environment)[:, 0]
        y_env = np.asarray(environment)[:, 1]
        if y_v.shape != y_env.shape:
            raise ValueError("Vanadium and environment arrays must have the same length.")
        if not np.array_equal(x_v, x_env):
            raise ValueError("Vanadium and environment x-grids do not match.")

        chi_values: list[float] = []
        for t in trans_arr.tolist():
            background_y = float(t) * y_env
            y = y_v - background_y
            smooth_y = smooth_curve(x_v, y, smoothing_factor)
            start_idx = min(ignore_points, len(y))
            chi_values.append(get_chi(y[start_idx:], smooth_y[start_idx:]))

        try:
            extremum_x, _extremum_y, fitted = fit_and_find_extremum(trans_arr, chi_values)
            best_t = float(extremum_x[0])
        except Exception:
            fitted = np.asarray([], dtype=float)
            best_t = float(trans_arr[int(np.argmin(np.asarray(chi_values, dtype=float)))])

        if not np.isfinite(best_t):
            best_t = float(trans_arr[int(np.argmin(np.asarray(chi_values, dtype=float)))])
        
        return {
            "trans": [float(v) for v in trans_arr.tolist()],
            "chi": [float(v) for v in chi_values],
            "fitted": [float(v) for v in fitted.tolist()] if getattr(fitted, "size", 0) else [],
            "best_t": float(best_t),
            "computed_at": now_iso(),
            "settings": {
                "t_start": t_start,
                "t_stop": t_stop,
                "t_step": t_step,
                "smoothing_factor": smoothing_factor,
                "ignore_points": ignore_points,
            },
        }

    def _get_background_state(self) -> dict:
        if self.current_project_state is None:
            return normalize_background_state(None)
        normalized = normalize_background_state(getattr(self.current_project_state, "background", None))
        self.current_project_state.background = normalized
        return normalized

    def _persist_background_state(self, state: dict | None = None) -> None:
        if self.current_project_state is None:
            return
        self.current_project_state.background = normalize_background_state(
            self._get_background_state() if state is None else state
        )
        self.current_project_state.project.updated_at = now_iso()
        self._persist_current_project_state()

    def _refresh_background_par_dropdown_options(self) -> None:
        if self.current_project_root is None:
            self.background_par_dropdown.options = {"Open a project first.": ""}
            self.background_par_dropdown.value = ""
            return

        sample_pars = list_sample_par_files(self.current_project_root)
        if not sample_pars:
            self.background_par_dropdown.options = {"No sample .par files found in parfiles/.": ""}
            self.background_par_dropdown.value = ""
            return

        options = {par_path.name: str(par_path.resolve(strict=False)) for par_path in sample_pars}
        self.background_par_dropdown.options = options

        state = self._get_background_state()
        remembered = str(state.get("selected_par_path") or "").strip()
        if remembered and remembered in options.values():
            selected_value = remembered
            self.background_par_dropdown.value = selected_value
            self.background_manual_path_input.value = selected_value
        else:
            selected_value = next(iter(options.values()), "")
            self.background_par_dropdown.value = selected_value if not remembered else ""
            if not remembered:
                self.background_manual_path_input.value = selected_value

    def _load_background_state_into_widgets(self) -> None:
        if self.current_project_state is None:
            return

        self._clear_background_cached_measurement_state()
        state = self._get_background_state()
        self._suspend_background_events = True
        self.background_source_mode.value = state["source_mode"]
        self.background_manual_path_input.value = str(state.get("selected_par_path") or "")
        self.background_subtraction_method.value = state.get(
            "subtraction_method",
            BACKGROUND_SUBTRACTION_METHOD_OPTIONS[0],
        )
        if hasattr(self, "background_sample_method_select"):
            self.background_sample_method_select.value = self.background_subtraction_method.value
        linear_settings = state.get("linear_combination") if isinstance(state.get("linear_combination"), dict) else {}
        self.background_linear_t_start.value = float(linear_settings.get("t_start", -1.0))
        self.background_linear_t_stop.value = float(linear_settings.get("t_stop", 2.0))
        self.background_linear_t_step.value = float(linear_settings.get("t_step", 0.05))
        self.background_linear_smoothing.value = float(linear_settings.get("smoothing_factor", 0.01))
        self.background_linear_ignore_points.value = int(linear_settings.get("ignore_points", 25))
        self.background_linear_custom_t.value = 0.8
        self.background_linear_t_mode.value = "Use computed t"
        self.background_linear_custom_t.disabled = True
        vanadium_settings = (
            state.get("vanadium_linear_settings")
            if isinstance(state.get("vanadium_linear_settings"), dict)
            else {}
        )
        self.background_vanadium_t_start.value = float(vanadium_settings.get("t_start", -1.0))
        self.background_vanadium_t_stop.value = float(vanadium_settings.get("t_stop", 2.0))
        self.background_vanadium_t_step.value = float(vanadium_settings.get("t_step", 0.05))
        self.background_vanadium_smoothing.value = float(vanadium_settings.get("smoothing_factor", 0.01))
        self.background_vanadium_ignore_points.value = int(vanadium_settings.get("ignore_points", 25))
        self.background_vanadium_custom_t.value = 0.8
        self.background_vanadium_t_mode.value = "Use computed t"
        self.background_vanadium_custom_t.disabled = True
        self._refresh_background_par_dropdown_options()
        self._suspend_background_events = False
        self._set_background_source_widget_visibility()
        self._sync_background_method_cards_visibility()
        self._sync_background_import_visibility()

        self._pending_background_import_path = None
        self.background_import_prompt.visible = False

        selected = str(self._get_background_state().get("selected_par_path") or "").strip()
        if selected and self.current_project_root is not None:
            self._apply_cached_background_measurement(
                Path(selected),
                update_message=False,
                refresh_plots=True,
            )

        state = self._get_background_state()
        validation_state = state["validation"]
        self.background_extract_button.disabled = not bool(validation_state.get("is_valid", False))
        self._refresh_background_plots()
        self._refresh_background_selection_section_state()

        if validation_state.get("is_valid"):
            self._show_background_ready_to_extract_toast()
        elif state.get("selected_par_path"):
            self._set_background_toast_notification(
                (
                validation_state.get("error")
                or "The remembered sample .par selection needs validation."
                ),
                alert_type="warning",
            )
        else:
            self._set_background_toast_notification(
                "Select a sample .par file to get started.",
                alert_type="secondary",
            )

    def _on_background_subtraction_method_change(self, event) -> None:
        if getattr(self, "_suspend_background_events", False) or self.current_project_state is None:
            return
        if event.new == event.old:
            return

        state = self._get_background_state()
        if event.new in BACKGROUND_SUBTRACTION_METHOD_OPTIONS:
            state["subtraction_method"] = event.new
            self._persist_background_state(state)

        self._refresh_background_plots()
        self._sync_background_method_cards_visibility()
        self._apply_background_subtraction_sample_visibility()
        self._refresh_background_subtraction_sample_summary()
        self._apply_background_subtraction_vanadium_visibility()
        self._refresh_background_subtraction_vanadium_summary()
        self._refresh_interaction_states()

    def _on_background_error_bars_toggle(self, event) -> None:
        # Deprecated: error bars are currently always disabled in the GUI.
        return

    def _on_background_sample_method_select_change(self, event) -> None:
        if getattr(self, "_suspend_background_events", False) or self.current_project_state is None:
            return
        if event.new == event.old:
            return
        if not hasattr(self, "background_subtraction_method"):
            return
        if event.new in BACKGROUND_SUBTRACTION_METHOD_OPTIONS:
            self.background_subtraction_method.value = event.new

    def _on_background_vanadium_method_select_change(self, event) -> None:
        if getattr(self, "_suspend_background_events", False) or self.current_project_state is None:
            return
        if event.new == event.old:
            return
        if not hasattr(self, "background_subtraction_method"):
            return
        if event.new in BACKGROUND_SUBTRACTION_METHOD_OPTIONS:
            self.background_subtraction_method.value = event.new

    def _current_background_sample_key(self) -> str | None:
        if self.current_project_root is None:
            return None
        par_path_str = str(getattr(self, "_background_cached_par_path", None) or "").strip()
        if not par_path_str:
            par_path_str = str(self._get_background_state().get("validation", {}).get("selected_par_path") or "").strip()
        if not par_path_str:
            return None
        return background_sample_key(Path(par_path_str), self.current_project_root)

    def _on_background_sample_view_switch_change(self, event) -> None:
        if getattr(self, "_suspend_background_events", False) or self.current_project_state is None:
            return
        if event.new == event.old:
            return

        sample_key = self._current_background_sample_key()
        if not sample_key:
            return

        state = self._get_background_state()
        cached = state.get("measurements_by_par")
        if not isinstance(cached, dict):
            return
        entry = cached.get(sample_key)
        if not isinstance(entry, dict):
            return

        entry["sample_subtraction_view"] = "diffractogram" if bool(event.new) else "chi"
        cached[sample_key] = entry
        state["measurements_by_par"] = cached
        self._persist_background_state(state)

        self._apply_background_subtraction_sample_visibility()
        self._refresh_background_subtraction_sample_summary()
        self._refresh_interaction_states()

    def _on_background_vanadium_view_switch_change(self, event) -> None:
        if getattr(self, "_suspend_background_events", False) or self.current_project_state is None:
            return
        if event.new == event.old:
            return

        sample_key = self._current_background_sample_key()
        if not sample_key:
            return

        state = self._get_background_state()
        cached = state.get("measurements_by_par")
        if not isinstance(cached, dict):
            return
        entry = cached.get(sample_key)
        if not isinstance(entry, dict):
            return

        entry["vanadium_subtraction_view"] = "diffractogram" if bool(event.new) else "chi"
        cached[sample_key] = entry
        state["measurements_by_par"] = cached
        self._persist_background_state(state)

        self._apply_background_subtraction_vanadium_visibility()
        self._refresh_background_subtraction_vanadium_summary()
        self._refresh_interaction_states()

    def _on_background_sample_use_custom_t_click(self, _event=None) -> None:
        if self.operation_in_progress:
            self._show_workspace_blocked_message()
            return
        if self.current_project_state is None:
            return

        if not bool(getattr(self.background_sample_use_custom_t_toggle, "value", False)):
            self._show_warning_toast("Enable `Use Custom t` to apply a custom t value.")
            return

        raw_custom = getattr(self.background_sample_custom_t_input, "value", None)
        try:
            custom_t = float(raw_custom)
        except Exception:
            self._show_warning_toast("Enter a valid numeric `Custom t` value first.")
            return
        if not np.isfinite(custom_t):
            self._show_warning_toast("Enter a finite `Custom t` value first.")
            return

        sample_key = self._current_background_sample_key()
        if not sample_key:
            return
        state = self._get_background_state()
        cached = state.get("measurements_by_par")
        if not isinstance(cached, dict) or sample_key not in cached:
            return

        entry = cached.get(sample_key, {})
        if not isinstance(entry, dict):
            entry = {}

        linear = entry.get("linear_combination")
        if not isinstance(linear, dict):
            linear = {}

        linear["t_mode"] = "custom"
        linear["custom_t"] = custom_t
        linear["effective_t"] = custom_t
        entry["linear_combination"] = linear
        cached[sample_key] = entry
        state["measurements_by_par"] = cached
        self._persist_background_state(state)

        self.background_sample_use_custom_t_button.button_type = "primary"
        self.background_sample_use_computed_t_button.button_type = "light"

        self._refresh_background_plots()
        self._sync_background_linear_controls_from_cache(sample_key)
        self._apply_background_subtraction_sample_visibility()
        self._refresh_background_subtraction_sample_summary()
        self._refresh_interaction_states()

    def _on_background_sample_use_computed_t_click(self, _event=None) -> None:
        if self.operation_in_progress:
            self._show_workspace_blocked_message()
            return
        if self.current_project_state is None:
            return

        sample_key = self._current_background_sample_key()
        if not sample_key:
            return
        state = self._get_background_state()
        cached = state.get("measurements_by_par")
        if not isinstance(cached, dict):
            return
        entry = cached.get(sample_key)
        if not isinstance(entry, dict):
            return
        linear = entry.get("linear_combination")
        if not isinstance(linear, dict):
            return

        best_t = linear.get("best_t")
        if not isinstance(best_t, (int, float)) or not np.isfinite(float(best_t)):
            self._show_warning_toast("Compute a linear combination first to get a computed t.")
            return

        linear["t_mode"] = "computed"
        linear["effective_t"] = float(best_t)
        entry["linear_combination"] = linear
        cached[sample_key] = entry
        state["measurements_by_par"] = cached
        self._persist_background_state(state)

        self._suspend_background_events = True
        try:
            self.background_sample_use_custom_t_toggle.value = False
        finally:
            self._suspend_background_events = False

        self.background_sample_use_computed_t_button.button_type = "primary"
        self.background_sample_use_custom_t_button.button_type = "light"

        self._refresh_background_plots()
        self._sync_background_linear_controls_from_cache(sample_key)
        self._apply_background_subtraction_sample_visibility()
        self._refresh_background_subtraction_sample_summary()
        self._apply_background_subtraction_vanadium_visibility()
        self._refresh_background_subtraction_vanadium_summary()
        self._refresh_background_selection_section_state()
        self._refresh_interaction_states()

    def _on_background_vanadium_use_custom_t_click(self, _event=None) -> None:
        if self.operation_in_progress:
            self._show_workspace_blocked_message()
            return
        if self.current_project_state is None:
            return

        if not bool(getattr(self.background_vanadium_use_custom_t_toggle, "value", False)):
            self._show_warning_toast("Enable `Use Custom t` to apply a custom t value.")
            return

        raw_custom = getattr(self.background_vanadium_custom_t_input, "value", None)
        try:
            custom_t = float(raw_custom)
        except Exception:
            self._show_warning_toast("Enter a valid numeric `Custom t` value first.")
            return
        if not np.isfinite(custom_t):
            self._show_warning_toast("Enter a finite `Custom t` value first.")
            return

        sample_key = self._current_background_sample_key()
        if not sample_key:
            return
        state = self._get_background_state()
        cached = state.get("measurements_by_par")
        if not isinstance(cached, dict) or sample_key not in cached:
            return

        entry = cached.get(sample_key, {})
        if not isinstance(entry, dict):
            entry = {}

        vanadium = entry.get("vanadium_linear_combination")
        if not isinstance(vanadium, dict):
            vanadium = {}

        vanadium["t_mode"] = "custom"
        vanadium["custom_t"] = custom_t
        vanadium["effective_t"] = custom_t
        entry["vanadium_linear_combination"] = vanadium
        cached[sample_key] = entry
        state["measurements_by_par"] = cached
        self._persist_background_state(state)

        self.background_vanadium_use_custom_t_button.button_type = "primary"
        self.background_vanadium_use_computed_t_button.button_type = "light"

        self._refresh_background_plots()
        self._sync_background_linear_controls_from_cache(sample_key)
        self._apply_background_subtraction_vanadium_visibility()
        self._refresh_background_subtraction_vanadium_summary()
        self._refresh_interaction_states()

    def _on_background_vanadium_use_computed_t_click(self, _event=None) -> None:
        if self.operation_in_progress:
            self._show_workspace_blocked_message()
            return
        if self.current_project_state is None:
            return

        sample_key = self._current_background_sample_key()
        if not sample_key:
            return
        state = self._get_background_state()
        cached = state.get("measurements_by_par")
        if not isinstance(cached, dict):
            return
        entry = cached.get(sample_key)
        if not isinstance(entry, dict):
            return
        vanadium = entry.get("vanadium_linear_combination")
        if not isinstance(vanadium, dict):
            return

        best_t = vanadium.get("best_t")
        if not isinstance(best_t, (int, float)) or not np.isfinite(float(best_t)):
            self._show_warning_toast("Compute a vanadium linear combination first to get a computed t.")
            return

        current_mode = str(vanadium.get("t_mode") or "computed")
        current_effective = vanadium.get("effective_t")
        if (
            current_mode == "computed"
            and isinstance(current_effective, (int, float))
            and np.isfinite(float(current_effective))
            and np.isclose(float(current_effective), float(best_t))
        ):
            return

        vanadium["t_mode"] = "computed"
        vanadium["effective_t"] = float(best_t)
        entry["vanadium_linear_combination"] = vanadium
        cached[sample_key] = entry
        state["measurements_by_par"] = cached
        self._persist_background_state(state)

        self._suspend_background_events = True
        try:
            self.background_vanadium_use_custom_t_toggle.value = False
        finally:
            self._suspend_background_events = False

        self.background_vanadium_use_computed_t_button.button_type = "primary"
        self.background_vanadium_use_custom_t_button.button_type = "light"

        self._refresh_background_plots()
        self._sync_background_linear_controls_from_cache(sample_key)
        self._apply_background_subtraction_sample_visibility()
        self._refresh_background_subtraction_sample_summary()
        self._apply_background_subtraction_vanadium_visibility()
        self._refresh_background_subtraction_vanadium_summary()
        self._refresh_interaction_states()

    def _apply_cached_background_measurement(
        self,
        selected_par_path: Path,
        *,
        update_message: bool,
        refresh_plots: bool = True,
    ) -> bool:
        if self.current_project_state is None or self.current_project_root is None:
            return False

        state = self._get_background_state()
        sample_key = background_sample_key(selected_par_path, self.current_project_root)
        if not sample_key:
            return False

        cached = state.get("measurements_by_par")
        if not isinstance(cached, dict):
            return False

        entry = cached.get(sample_key)
        if not isinstance(entry, dict):
            return False

        artifact = entry.get("measurement_artifact")
        if not isinstance(artifact, str) or not artifact.strip():
            return False

        try:
            artifact_path = Path(artifact).expanduser()
        except (TypeError, ValueError):
            return False
        if not artifact_path.is_absolute():
            artifact_path = self.current_project_root / artifact_path
        artifact_path = artifact_path.resolve(strict=False)
        if not artifact_path.exists() or not artifact_path.is_file():
            return False

        stale = False
        signature = background_par_signature(selected_par_path)
        stored_mtime = entry.get("par_mtime")
        stored_size = entry.get("par_size")
        if signature is None:
            stale = True
        elif isinstance(stored_mtime, (int, float)) and isinstance(stored_size, int):
            stale = (float(stored_mtime) != signature[0]) or (int(stored_size) != signature[1])

        try:
            artifact_for_state = artifact_path.relative_to(self.current_project_root).as_posix()
        except Exception:
            artifact_for_state = str(artifact_path)

        state["latest_measurement_artifact"] = artifact_for_state
        state["validation"]["selected_par_path"] = str(selected_par_path.resolve(strict=False))
        if signature is None:
            state["validation"]["file_accessible"] = False
            state["validation"]["is_valid"] = False
            state["validation"]["error"] = "Sample .par file is missing."
        else:
            state["validation"]["file_accessible"] = True
            state["validation"]["is_valid"] = True
            state["validation"]["error"] = None
        self._persist_background_state(state)
        self._sync_background_import_visibility()
        self._sync_background_method_cards_visibility()
        if refresh_plots:
            self._refresh_background_plots()
        self.background_extract_button.disabled = signature is None
        self._sync_background_linear_controls_from_cache(sample_key)
        self._apply_background_subtraction_sample_visibility()
        self._refresh_background_subtraction_sample_summary()
        self._apply_background_subtraction_vanadium_visibility()
        self._refresh_background_subtraction_vanadium_summary()
        self._refresh_interaction_states()

        if update_message:
            if signature is None:
                self._set_background_toast_notification(
                    (
                        "Loaded cached extraction, but the sample .par file is missing. "
                        "Re-extract is unavailable until the file is restored."
                    ),
                    alert_type="warning",
                )
            elif stale:
                self._set_background_toast_notification(
                    (
                        "Loaded cached extraction. The .par file has changed since extraction; "
                        "re-extract is recommended."
                    ),
                    alert_type="warning",
                )
            else:
                self._set_background_toast_notification(
                    "Loaded cached extraction for this sample.",
                    alert_type="success",
                )

        return True

    def _load_latest_measurement(self):
        state = self._get_background_state()
        artifact = state.get("latest_measurement_artifact")
        if not artifact:
            return None
        artifact_str = str(artifact)
        try:
            path = Path(artifact_str).expanduser()
        except (TypeError, ValueError):
            return None
        if not path.is_absolute() and self.current_project_root is not None:
            path = (self.current_project_root / path).resolve(strict=False)
        if not path.exists() or not path.is_file():
            return None

        try:
            mtime = path.stat().st_mtime
        except Exception:
            mtime = None

        cached_path = getattr(self, "_background_cached_artifact_path", None)
        cached_mtime = getattr(self, "_background_cached_artifact_mtime", None)
        cached_measurement = getattr(self, "_background_cached_measurement", None)
        if cached_measurement is not None and cached_path == artifact_str and cached_mtime == mtime:
            return cached_measurement

        measurement = None
        par_filename: str | None = None
        par_path_str: str | None = None
        try:
            if path.suffix.lower() == ".pkl":
                with path.open("rb") as handle:
                    measurement = pickle.load(handle)
            else:
                payload = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(payload, dict):
                    return None
                par_path = None
                try:
                    par_path = payload.get("<par>")[1]
                except Exception:
                    par_path = None
                if par_path:
                    try:
                        par_filename = Path(str(par_path)).name
                        par_path_str = str(par_path)
                    except Exception:
                        par_filename = None
                base_dir = Path(str(par_path)).expanduser().parent if par_path else path.parent
                with _working_directory(base_dir):
                    measurement = Measurement(payload)
        except Exception:
            measurement = None

        self._background_cached_artifact_path = artifact_str
        self._background_cached_artifact_mtime = mtime
        self._background_cached_measurement = measurement
        self._background_cached_par_filename = par_filename
        self._background_cached_par_path = par_path_str
        return measurement
    
    def _background_has_latest_measurement_artifact(self) -> bool:
        state = self._get_background_state()
        artifact = state.get("latest_measurement_artifact")

        if not artifact:
            return False
        try:
            path = Path(str(artifact)).expanduser()
        except Exception:
            return False
        
        if not path.is_absolute() and self.current_project_root is not None:
            path = (self.current_project_root / path).resolve(strict=False)
        return path.exists() and path.is_file()

    def _on_background_linear_settings_change(self, event) -> None:
        if getattr(self, "_suspend_background_events", False) or self.current_project_state is None:
            return
        if event.new == event.old:
            return
        self._persist_background_linear_settings()
        self.background_linear_message.object = "Settings updated. Click **Compute Linear Combination** to refresh."
        self.background_linear_message.alert_type = "secondary"
        self._refresh_interaction_states()

    def _on_background_linear_t_selection_change(self, event) -> None:
        if getattr(self, "_suspend_background_events", False) or self.current_project_state is None:
            return
        if event.new == event.old:
            return

        mode = str(self.background_linear_t_mode.value or "Use computed t")
        self.background_linear_custom_t.disabled = mode != "Use custom t"
        self._apply_background_linear_t_override()

    def _persist_background_linear_settings(self) -> None:
        if self.current_project_state is None:
            return
        state = self._get_background_state()
        state["linear_combination"] = {
            "t_start": float(self.background_linear_t_start.value),
            "t_stop": float(self.background_linear_t_stop.value),
            "t_step": float(self.background_linear_t_step.value),
            "smoothing_factor": float(self.background_linear_smoothing.value),
            "ignore_points": int(self.background_linear_ignore_points.value),
        }
        self._persist_background_state(state)

    def _apply_background_linear_t_override(self) -> None:
        if self.current_project_state is None or self.current_project_root is None:
            return
        par_path_str = getattr(self, "_background_cached_par_path", None)
        if not par_path_str:
            return
        sample_key = background_sample_key(Path(par_path_str), self.current_project_root)
        if not sample_key:
            return
        state = self._get_background_state()
        cached = state.get("measurements_by_par")
        if not isinstance(cached, dict):
            return
        entry = cached.get(sample_key)
        if not isinstance(entry, dict):
            return
        linear = entry.get("linear_combination")
        if not isinstance(linear, dict):
            return

        mode = str(self.background_linear_t_mode.value or "Use computed t")
        best_t = linear.get("best_t")
        custom_t = float(self.background_linear_custom_t.value)
        if mode == "Use custom t":
            linear["t_mode"] = "custom"
            linear["custom_t"] = custom_t
            linear["effective_t"] = custom_t
            self.background_linear_message.object = f"Using custom t = {custom_t:.5f}"
            self.background_linear_message.alert_type = "warning"
        else:
            linear["t_mode"] = "computed"
            if isinstance(best_t, (int, float)):
                linear["effective_t"] = float(best_t)
                self.background_linear_message.object = f"Using computed t = {float(best_t):.5f}"
                self.background_linear_message.alert_type = "success"
            else:
                self.background_linear_message.object = "No computed t is available yet. Click Compute."
                self.background_linear_message.alert_type = "danger"

        entry["linear_combination"] = linear
        cached[sample_key] = entry
        self._persist_background_state(state)
        self._refresh_background_plots()
        self._refresh_interaction_states()

    def _compute_background_linear_combination(self, _event=None) -> None:
        if self.operation_in_progress:
            self._show_workspace_blocked_message()
            return
        if self.current_project_state is None or self.current_project_root is None:
            return

        measurement = self._load_latest_measurement()
        if measurement is None:
            self.background_linear_message.object = "Extract a sample measurement first."
            self.background_linear_message.alert_type = "danger"
            self._refresh_interaction_states()
            return

        self._persist_background_linear_settings()
        state = self._get_background_state()
        settings = dict(state.get("linear_combination") or {})

        try:
            result = self._run_linear_combination(measurement, settings=settings)
        except Exception as exc:
            self.background_linear_message.object = f"Linear combination failed: {exc}"
            self.background_linear_message.alert_type = "danger"
            self._refresh_interaction_states()
            return

        par_path_str = getattr(self, "_background_cached_par_path", None)
        if not par_path_str:
            par_path_str = str(state.get("validation", {}).get("selected_par_path") or "").strip()
        sample_key = background_sample_key(Path(par_path_str), self.current_project_root) if par_path_str else None
        if not sample_key:
            self.background_linear_message.object = "Could not determine which sample .par this result belongs to."
            self.background_linear_message.alert_type = "danger"
            self._refresh_interaction_states()
            return

        cached = state.get("measurements_by_par")
        if not isinstance(cached, dict) or sample_key not in cached:
            self.background_linear_message.object = "This sample is not present in the extraction cache yet."
            self.background_linear_message.alert_type = "danger"
            self._refresh_interaction_states()
            return

        cached_entry = cached.get(sample_key, {})
        if not isinstance(cached_entry, dict):
            cached_entry = {}

        best_t = result.get("best_t")
        custom_t = float(getattr(self.background_linear_custom_t, "value", 0.8))
        result["t_mode"] = "computed"
        result["custom_t"] = custom_t
        if isinstance(best_t, (int, float)):
            result["effective_t"] = float(best_t)

        cached_entry["linear_combination"] = result
        cached[sample_key] = cached_entry
        self._persist_background_state(state)

        self._suspend_background_events = True
        self.background_linear_t_mode.value = "Use computed t"
        self.background_linear_custom_t.disabled = True
        self._suspend_background_events = False

        if isinstance(best_t, float):
            self.background_linear_message.object = f"Computed best t = {best_t:.5f}"
            self.background_linear_message.alert_type = "success"
        else:
            self.background_linear_message.object = "Computed best t."
            self.background_linear_message.alert_type = "success"
        self._refresh_background_plots()
        self._sync_background_linear_controls_from_cache(sample_key)
        self._refresh_interaction_states()

    def _run_linear_combination(self, measurement, *, settings: dict) -> dict:
        data = getattr(measurement, "Data", None)
        container = getattr(measurement, "conData", None)
        environment = getattr(measurement, "envData", None)
        if data is None or container is None or environment is None:
            raise ValueError("Sample, Container, and Environment data are required for Linear Combination.")

        t_start = float(settings.get("t_start", -1.0))
        t_stop = float(settings.get("t_stop", 2.0))
        t_step = float(settings.get("t_step", 0.05))
        smoothing_factor = float(settings.get("smoothing_factor", 0.01))
        ignore_points = int(settings.get("ignore_points", 25))
        if t_step <= 0:
            raise ValueError("t step must be > 0.")
        if t_stop <= t_start:
            raise ValueError("t stop must be greater than t start.")
        if ignore_points < 0:
            raise ValueError("Ignore points must be >= 0.")

        trans_arr = np.arange(t_start, t_stop, t_step, dtype=float)
        if trans_arr.size < 3:
            raise ValueError("t range must include at least 3 values.")

        x = np.asarray(data)[:, 0]
        y_sample = np.asarray(data)[:, 1]
        y_con = np.asarray(container)[:, 1]
        y_env = np.asarray(environment)[:, 1]
        if y_con.shape != y_env.shape or y_sample.shape != y_con.shape:
            raise ValueError("Sample, container, and environment arrays must have the same length.")

        chi_values: list[float] = []
        for t in trans_arr.tolist():
            background_y = float(t) * y_con + (1.0 - float(t)) * y_env
            y = y_sample - background_y
            smooth_y = smooth_curve(x, y, smoothing_factor)
            start_idx = min(ignore_points, len(y))
            chi_values.append(get_chi(y[start_idx:], smooth_y[start_idx:]))

        try:
            extremum_x, _extremum_y, fitted = fit_and_find_extremum(trans_arr, chi_values)
            best_t = float(extremum_x[0])
        except Exception:
            fitted = np.asarray([], dtype=float)
            best_t = float(trans_arr[int(np.argmin(np.asarray(chi_values, dtype=float)))])

        if not np.isfinite(best_t):
            best_t = float(trans_arr[int(np.argmin(np.asarray(chi_values, dtype=float)))])

        return {
            "trans": [float(v) for v in trans_arr.tolist()],
            "chi": [float(v) for v in chi_values],
            "fitted": [float(v) for v in fitted.tolist()] if getattr(fitted, "size", 0) else [],
            "best_t": float(best_t),
            "computed_at": now_iso(),
            "settings": {
                "t_start": t_start,
                "t_stop": t_stop,
                "t_step": t_step,
                "smoothing_factor": smoothing_factor,
                "ignore_points": ignore_points,
            },
        }

    def _set_background_plot_visibility(
        self,
        *,
        has_measurement: bool,
        show_linear_combination: bool,
        raw_ok: bool,
    ) -> None:
        self.background_no_data_pane.visible = not has_measurement
        self.background_raw_plot_card.visible = has_measurement and raw_ok
        self.background_raw_plot_alert.visible = has_measurement and not raw_ok
        self.background_subtraction_plot_card.visible = False
        self.background_subtraction_plot_alert.visible = False
        if hasattr(self, "background_final_signals_plot_card"):
            self.background_final_signals_plot_card.visible = has_measurement and show_linear_combination and bool(
                getattr(self.background_final_signals_plot_pane, "object", None)
            )

    def _refresh_background_plots(self) -> None:

        signature = self._background_plot_signature()
        if getattr(self, "_background_plot_signature_cache", None) == signature:
            self._set_background_plot_visibility(
                has_measurement=self.background_raw_plot_pane.object is not None, 
                show_linear_combination=(
                    self.background_subtraction_method.value == BACKGROUND_SUBTRACTION_METHOD_OPTIONS[0]
                ),
                raw_ok=self.background_raw_plot_pane.object is not None, 
            )
            return
        
        if self.current_project_state is None:
            return

        measurement = self._load_latest_measurement()
        if measurement is None:
            self.background_raw_plot_pane.object = None
            self.background_subtraction_plot_pane.object = None
            self._clear_background_linear_and_vanadium_plot_cards()
            self.background_raw_plot_alert.object = ""
            self.background_subtraction_plot_alert.object = ""
            self._set_background_plot_visibility(
                has_measurement=False,
                show_linear_combination=False,
                raw_ok=False,
            )
            self._sync_background_method_cards_visibility()
            self._apply_background_subtraction_sample_visibility()
            self._refresh_background_subtraction_sample_summary()
            self._apply_background_subtraction_vanadium_visibility()
            self._refresh_background_subtraction_vanadium_summary()
            return

        show_error_bars = False
        selected_method = str(
            getattr(self, "background_subtraction_method", None).value
            if hasattr(self, "background_subtraction_method")
            else self._get_background_state().get("subtraction_method", BACKGROUND_SUBTRACTION_METHOD_OPTIONS[0])
        )
        show_linear_combination = selected_method == BACKGROUND_SUBTRACTION_METHOD_OPTIONS[0]
        self._sync_background_method_cards_visibility()
        raw_title = getattr(self, "_background_cached_par_filename", None)

        raw_ok = True
        try:
            self.background_raw_plot_pane.object = build_raw_data_figure(
                measurement,
                show_error_bars=show_error_bars,
                title=raw_title,
            )
            self.background_raw_plot_alert.object = ""
        except Exception as exc:
            raw_ok = False
            self.background_raw_plot_pane.object = None
            self.background_raw_plot_alert.object = f"Could not build raw data plot: {exc}"

        self.background_subtraction_plot_pane.object = None
        self.background_subtraction_plot_alert.object = ""

        if show_linear_combination:
            self._refresh_background_linear_combination_plots(measurement, show_error_bars=show_error_bars)
            self._refresh_background_vanadium_plots(measurement, show_error_bars=show_error_bars)
            self._refresh_background_final_signals_plot(measurement, show_error_bars=show_error_bars)
        else:
            self._clear_background_linear_and_vanadium_plot_cards()

        self._set_background_plot_visibility(
            has_measurement=True,
            show_linear_combination=show_linear_combination,
            raw_ok=raw_ok,
        )
        self._apply_background_subtraction_sample_visibility()
        self._refresh_background_subtraction_sample_summary()
        self._apply_background_subtraction_vanadium_visibility()
        self._refresh_background_subtraction_vanadium_summary()

        self._background_plot_signature_cache = signature
    
    def _background_plot_signature(self) -> tuple:
        state = self._get_background_state()
        sample_key = self._current_background_sample_key()
        entry = {}
        cached = state.get("measurements_by_par")
        if sample_key and isinstance(cached, dict):
            entry = cached.get(sample_key) or {}
        
        return (
            state.get("latest_measurement_artifact"),
            getattr(self, "_background_cached_artifact_mtime", None), 
            self.background_subtraction_method.value, 
            entry.get("sample_subtraction_view"),
            entry.get("vanadium_subtraction_view"),
            repr(entry.get("linear_combination")),
            repr(entry.get("vanadium_linear_combination"))
        )

    def _apply_background_subtraction_sample_visibility(self) -> None:
        if not hasattr(self, "background_subtraction_sample_card"):
            return

        has_measurement = self._background_has_latest_measurement_artifact()
        self.background_subtraction_sample_card.visible = bool(has_measurement)
        if not has_measurement:
            if hasattr(self, "background_subtraction_plot_pane"):
                self.background_subtraction_plot_pane.visible = False
            if hasattr(self, "background_linear_chi_plot_pane"):
                self.background_linear_chi_plot_pane.visible = False
            if hasattr(self, "background_linear_subtraction_plot_pane"):
                self.background_linear_subtraction_plot_pane.visible = False
            if hasattr(self, "background_sample_monte_carlo_placeholder_pane"):
                self.background_sample_monte_carlo_placeholder_pane.visible = False
            if hasattr(self, "background_sample_view_selector"):
                self.background_sample_view_selector.visible = False
            return

        selected_method = str(
            getattr(self.background_subtraction_method, "value", "") if hasattr(self, "background_subtraction_method") else ""
        )
        if selected_method not in BACKGROUND_SUBTRACTION_METHOD_OPTIONS:
            selected_method = BACKGROUND_SUBTRACTION_METHOD_OPTIONS[0]

        if hasattr(self, "background_sample_method_select") and self.background_sample_method_select.value != selected_method:
            self._suspend_background_events = True
            try:
                self.background_sample_method_select.value = selected_method
            finally:
                self._suspend_background_events = False

        show_linear = selected_method == BACKGROUND_SUBTRACTION_METHOD_OPTIONS[0]
        show_monte_carlo = selected_method == BACKGROUND_SUBTRACTION_METHOD_OPTIONS[1]

        for widget_name in (
            "background_linear_t_start",
            "background_linear_t_stop",
            "background_linear_t_step",
            "background_linear_smoothing",
            "background_linear_ignore_points",
            "background_sample_use_custom_t_toggle",
            "background_linear_compute_button",
            "background_sample_use_computed_t_button",
            "background_sample_use_custom_t_button",
        ):
            if hasattr(self, widget_name):
                getattr(self, widget_name).visible = bool(show_linear)

        if hasattr(self, "background_sample_view_selector"):
            self.background_sample_view_selector.visible = bool(show_linear)

        if hasattr(self, "background_sample_custom_t_input"):
            self.background_sample_custom_t_input.visible = True

        view = "chi"
        if show_linear:
            sample_key = self._current_background_sample_key()
            state = self._get_background_state()
            cached = state.get("measurements_by_par")
            entry = cached.get(sample_key) if sample_key and isinstance(cached, dict) else None
            stored = entry.get("sample_subtraction_view") if isinstance(entry, dict) else None
            if stored in ("chi", "diffractogram"):
                view = stored

        if hasattr(self, "background_sample_view_switch"):
            desired = view == "diffractogram"
            if bool(self.background_sample_view_switch.value) != desired:
                self._suspend_background_events = True
                try:
                    self.background_sample_view_switch.value = desired
                finally:
                    self._suspend_background_events = False

        if hasattr(self, "background_subtraction_plot_pane"):
            self.background_subtraction_plot_pane.visible = False
        if hasattr(self, "background_sample_monte_carlo_placeholder_pane"):
            self.background_sample_monte_carlo_placeholder_pane.visible = bool(show_monte_carlo)

        if hasattr(self, "background_linear_chi_plot_pane"):
            self.background_linear_chi_plot_pane.visible = bool(show_linear and view == "chi")
        if hasattr(self, "background_linear_subtraction_plot_pane"):
            self.background_linear_subtraction_plot_pane.visible = bool(show_linear and view == "diffractogram")

    def _refresh_background_subtraction_sample_summary(self) -> None:
        if not hasattr(self, "background_sample_summary_table"):
            return
        if self.current_project_state is None:
            self.background_sample_summary_table.object = ""
            return

        measurement = self._load_latest_measurement()
        sample_name = ""
        try:
            sample_name = str(getattr(measurement, "Title", "") or "").strip() if measurement is not None else ""
        except Exception:
            sample_name = ""
        if not sample_name:
            sample_name = str(getattr(self, "_background_cached_par_filename", "") or "").strip()
        if not sample_name:
            sample_name = "—"

        selected_method = str(getattr(self.background_subtraction_method, "value", "") or "")
        method_label = {
            BACKGROUND_SUBTRACTION_METHOD_OPTIONS[0]: "Linear Combination",
            BACKGROUND_SUBTRACTION_METHOD_OPTIONS[1]: "Monte Carlo Simulation",
        }.get(selected_method, selected_method or "—")

        view_label = "—"
        sample_key = self._current_background_sample_key()
        state = self._get_background_state()
        cached = state.get("measurements_by_par")
        entry = cached.get(sample_key) if sample_key and isinstance(cached, dict) else None
        if selected_method == BACKGROUND_SUBTRACTION_METHOD_OPTIONS[0]:
            stored = entry.get("sample_subtraction_view") if isinstance(entry, dict) else None
            if stored == "diffractogram":
                view_label = "Background-subtracted diffractogram"
            else:
                view_label = "χ vs t"

        t_source = "—"
        t_value = "—"
        settings_text = "—"
        if isinstance(entry, dict):
            linear = entry.get("linear_combination")
        else:
            linear = None
        if selected_method == BACKGROUND_SUBTRACTION_METHOD_OPTIONS[0] and isinstance(linear, dict):
            mode = str(linear.get("t_mode") or "").strip()
            if mode in ("computed", "custom"):
                t_source = mode
            effective = linear.get("effective_t")
            if isinstance(effective, (int, float)) and np.isfinite(float(effective)):
                t_value = f"{float(effective):.6g}"
            if t_source == "computed":
                settings = linear.get("settings")
                if isinstance(settings, dict) and settings:
                    parts = []
                    for key in ("t_start", "t_stop", "t_step", "smoothing_factor", "ignore_points"):
                        if key not in settings:
                            continue
                        parts.append(f"{key}={settings.get(key)}")
                    settings_text = "<br>".join(parts) if parts else "—"

        self.background_sample_summary_table.object = (
            "<div class=\"toscana-fit-window-table\">"
            "<div class=\"toscana-fit-result-table__title\">Summary</div>"
            f"<div class=\"toscana-fit-result-table__meta\">Method: <strong>{html_escape(method_label)}</strong></div>"
            f"<div class=\"toscana-fit-result-table__meta\">View: <strong>{html_escape(view_label)}</strong></div>"
            f"<div class=\"toscana-fit-result-table__meta\">t source: <strong>{html_escape(t_source)}</strong></div>"
            f"<div class=\"toscana-fit-result-table__meta\">t value: <strong>{html_escape(t_value)}</strong></div>"
            f"<div class=\"toscana-fit-result-table__meta\">Sample: <strong>{html_escape(sample_name)}</strong></div>"
            f"<div class=\"toscana-fit-result-table__meta\">Computed settings:<br><strong>{settings_text}</strong></div>"
            "</div>"
        )

    def _apply_background_subtraction_vanadium_visibility(self) -> None:
        if not hasattr(self, "background_subtraction_vanadium_card"):
            return

        has_measurement = self._background_has_latest_measurement_artifact()
        self.background_subtraction_vanadium_card.visible = bool(has_measurement)
        if not has_measurement:
            for widget_name in (
                "background_vanadium_chi_plot_pane",
                "background_vanadium_subtraction_plot_pane",
                "background_vanadium_monte_carlo_placeholder_pane",
            ):
                if hasattr(self, widget_name):
                    getattr(self, widget_name).visible = False
            if hasattr(self, "background_vanadium_view_selector"):
                self.background_vanadium_view_selector.visible = False
            return

        selected_method = str(
            getattr(self.background_subtraction_method, "value", "") if hasattr(self, "background_subtraction_method") else ""
        )
        if selected_method not in BACKGROUND_SUBTRACTION_METHOD_OPTIONS:
            selected_method = BACKGROUND_SUBTRACTION_METHOD_OPTIONS[0]

        if hasattr(self, "background_vanadium_method_select") and self.background_vanadium_method_select.value != selected_method:
            self._suspend_background_events = True
            try:
                self.background_vanadium_method_select.value = selected_method
            finally:
                self._suspend_background_events = False

        show_linear = selected_method == BACKGROUND_SUBTRACTION_METHOD_OPTIONS[0]
        show_monte_carlo = selected_method == BACKGROUND_SUBTRACTION_METHOD_OPTIONS[1]

        for widget_name in (
            "background_vanadium_t_start",
            "background_vanadium_t_stop",
            "background_vanadium_t_step",
            "background_vanadium_smoothing",
            "background_vanadium_ignore_points",
            "background_vanadium_use_custom_t_toggle",
            "background_vanadium_custom_t_input",
            "background_vanadium_compute_button",
            "background_vanadium_use_computed_t_button",
            "background_vanadium_use_custom_t_button",
        ):
            if hasattr(self, widget_name):
                getattr(self, widget_name).visible = bool(show_linear)

        if hasattr(self, "background_vanadium_view_selector"):
            self.background_vanadium_view_selector.visible = bool(show_linear)

        if hasattr(self, "background_vanadium_custom_t_input"):
            self.background_vanadium_custom_t_input.visible = True

        view = "chi"
        if show_linear:
            sample_key = self._current_background_sample_key()
            state = self._get_background_state()
            cached = state.get("measurements_by_par")
            entry = cached.get(sample_key) if sample_key and isinstance(cached, dict) else None
            stored = entry.get("vanadium_subtraction_view") if isinstance(entry, dict) else None
            if stored in ("chi", "diffractogram"):
                view = stored

        if hasattr(self, "background_vanadium_view_switch"):
            desired = view == "diffractogram"
            if bool(self.background_vanadium_view_switch.value) != desired:
                self._suspend_background_events = True
                try:
                    self.background_vanadium_view_switch.value = desired
                finally:
                    self._suspend_background_events = False

        if hasattr(self, "background_vanadium_monte_carlo_placeholder_pane"):
            self.background_vanadium_monte_carlo_placeholder_pane.visible = bool(show_monte_carlo)

        if hasattr(self, "background_vanadium_chi_plot_pane"):
            self.background_vanadium_chi_plot_pane.visible = bool(show_linear and view == "chi")
        if hasattr(self, "background_vanadium_subtraction_plot_pane"):
            self.background_vanadium_subtraction_plot_pane.visible = bool(show_linear and view == "diffractogram")

        if hasattr(self, "background_vanadium_message"):
            monte_carlo_message = "Monte Carlo Simulation for vanadium will be implemented in a future iteration."
            current_message = str(getattr(self.background_vanadium_message, "object", "") or "").strip()
            if show_monte_carlo:
                self.background_vanadium_message.object = monte_carlo_message
                self.background_vanadium_message.alert_type = "secondary"
                self.background_vanadium_message.visible = True
            elif current_message == monte_carlo_message:
                self.background_vanadium_message.object = (
                    "Compute a vanadium background model to estimate the best t parameter."
                )
                self.background_vanadium_message.alert_type = "secondary"
                self.background_vanadium_message.visible = True

    def _refresh_background_subtraction_vanadium_summary(self) -> None:
        if not hasattr(self, "background_vanadium_summary_table"):
            return
        if self.current_project_state is None:
            self.background_vanadium_summary_table.object = ""
            return

        measurement = self._load_latest_measurement()
        if measurement is None:
            self.background_vanadium_summary_table.object = ""
            return

        selected_method = str(
            getattr(self.background_subtraction_method, "value", "") if hasattr(self, "background_subtraction_method") else ""
        )
        if selected_method not in BACKGROUND_SUBTRACTION_METHOD_OPTIONS:
            selected_method = BACKGROUND_SUBTRACTION_METHOD_OPTIONS[0]

        sample_name = str(getattr(measurement, "Title", "") or "").strip() or str(
            getattr(self, "_background_cached_par_filename", None) or "—"
        )

        method_label = {
            BACKGROUND_SUBTRACTION_METHOD_OPTIONS[0]: "Linear Combination",
            BACKGROUND_SUBTRACTION_METHOD_OPTIONS[1]: "Monte Carlo Simulation",
        }.get(selected_method, selected_method or "—")

        view_label = "—"
        sample_key = self._current_background_sample_key()
        state = self._get_background_state()
        cached = state.get("measurements_by_par")
        entry = cached.get(sample_key) if sample_key and isinstance(cached, dict) else None
        if selected_method == BACKGROUND_SUBTRACTION_METHOD_OPTIONS[0]:
            stored = entry.get("vanadium_subtraction_view") if isinstance(entry, dict) else None
            if stored == "diffractogram":
                view_label = "Background-subtracted diffractogram"
            else:
                view_label = "χ vs t"

        t_source = "—"
        t_value = "—"
        settings_text = "—"
        if isinstance(entry, dict):
            vanadium = entry.get("vanadium_linear_combination")
        else:
            vanadium = None

        if selected_method == BACKGROUND_SUBTRACTION_METHOD_OPTIONS[0] and isinstance(vanadium, dict):
            mode = str(vanadium.get("t_mode") or "").strip()
            if mode in ("computed", "custom"):
                t_source = mode
            effective = vanadium.get("effective_t")
            if isinstance(effective, (int, float)) and np.isfinite(float(effective)):
                t_value = f"{float(effective):.6g}"
            if t_source == "computed":
                settings = vanadium.get("settings")
                if isinstance(settings, dict) and settings:
                    parts = []
                    for key in ("t_start", "t_stop", "t_step", "smoothing_factor", "ignore_points"):
                        if key not in settings:
                            continue
                        parts.append(f"{key}={settings.get(key)}")
                    settings_text = "<br>".join(parts) if parts else "—"

        self.background_vanadium_summary_table.object = (
            "<div class=\"toscana-fit-window-table\">"
            "<div class=\"toscana-fit-result-table__title\">Summary</div>"
            f"<div class=\"toscana-fit-result-table__meta\">Method: <strong>{html_escape(method_label)}</strong></div>"
            f"<div class=\"toscana-fit-result-table__meta\">View: <strong>{html_escape(view_label)}</strong></div>"
            f"<div class=\"toscana-fit-result-table__meta\">t source: <strong>{html_escape(t_source)}</strong></div>"
            f"<div class=\"toscana-fit-result-table__meta\">t value: <strong>{html_escape(t_value)}</strong></div>"
            f"<div class=\"toscana-fit-result-table__meta\">Sample: <strong>{html_escape(sample_name)}</strong></div>"
            f"<div class=\"toscana-fit-result-table__meta\">Computed settings:<br><strong>{settings_text}</strong></div>"
            "</div>"
        )

    def _refresh_background_linear_combination_plots(self, measurement, *, show_error_bars: bool) -> None:
        if self.current_project_state is None or self.current_project_root is None:
            return
        state = self._get_background_state()
        par_path_str = getattr(self, "_background_cached_par_path", None)
        if not par_path_str:
            return
        sample_key = background_sample_key(Path(par_path_str), self.current_project_root)
        if not sample_key:
            return
        cached = state.get("measurements_by_par")
        if not isinstance(cached, dict):
            return
        entry = cached.get(sample_key)
        if not isinstance(entry, dict):
            return
        linear = entry.get("linear_combination")
        if not isinstance(linear, dict):
            self.background_linear_message.object = "No linear-combination result for this sample yet. Click Compute."
            self.background_linear_message.alert_type = "secondary"
            return

        trans = list(linear.get("trans") or [])
        chi = list(linear.get("chi") or [])
        fitted = list(linear.get("fitted") or [])
        best_t = linear.get("best_t")
        best_t_val = float(best_t) if isinstance(best_t, (int, float)) else None
        effective_t_raw = linear.get("effective_t", best_t_val)
        effective_t_val = float(effective_t_raw) if isinstance(effective_t_raw, (int, float)) else None
        t_mode = linear.get("t_mode")
        custom_t_raw = linear.get("custom_t", 0.8)
        custom_t_val = float(custom_t_raw) if isinstance(custom_t_raw, (int, float)) else 0.8

        self._suspend_background_events = True
        if t_mode == "custom":
            self.background_linear_t_mode.value = "Use custom t"
            self.background_linear_custom_t.disabled = False
            self.background_linear_custom_t.value = custom_t_val
        else:
            self.background_linear_t_mode.value = "Use computed t"
            self.background_linear_custom_t.disabled = True
            self.background_linear_custom_t.value = custom_t_val
        self._suspend_background_events = False

        self.background_linear_chi_plot_pane.object = build_linear_combination_chi_figure(
            trans,
            chi,
            fitted,
            best_t=best_t_val if t_mode == "computed" else None,
            effective_t=effective_t_val if t_mode == "custom" else None,
            t_mode=str(t_mode or "computed"),
        )

        data = getattr(measurement, "Data", None)
        container = getattr(measurement, "conData", None)
        environment = getattr(measurement, "envData", None)
        if data is None or container is None or environment is None or effective_t_val is None:
            return
        dat = np.asarray(data)
        con = np.asarray(container)
        env = np.asarray(environment)
        if dat.ndim != 2 or con.ndim != 2 or env.ndim != 2:
            return
        if dat.shape[0] != con.shape[0] or dat.shape[0] != env.shape[0]:
            return

        x = dat[:, 0]
        sample_y = dat[:, 1]
        if con.shape[1] >= 2 and env.shape[1] >= 2:
            background_y = effective_t_val * con[:, 1] + (1.0 - effective_t_val) * env[:, 1]
        else:
            return
        subtracted_y = sample_y - background_y
        direct_sub_y = sample_y - con[:, 1]

        error_y = None
        if show_error_bars and dat.shape[1] >= 3 and con.shape[1] >= 3 and env.shape[1] >= 3:
            bckgt = binary_sum(effective_t_val, con, 1.0 - effective_t_val, env)
            subt = binary_sum(1.0, dat, -1.0, bckgt) if bckgt is not None else None
            if subt is not None and subt.shape[1] >= 3:
                subtracted_y = subt[:, 1]
                error_y = subt[:, 2]
            if bckgt is not None:
                background_y = bckgt[:, 1]
            direct = binary_sum(1.0, dat, -1.0, con)
            if direct is not None:
                direct_sub_y = direct[:, 1]

        sample_name = str(getattr(measurement, "Title", "") or "").strip() or str(
            getattr(self, "_background_cached_par_filename", None) or "—"
        )
        title = f"Linear Combination for {sample_name} (t = {effective_t_val:.2f})"
        self.background_linear_subtraction_plot_pane.object = build_linear_combination_subtraction_figure(
            x=x,
            sample_y=sample_y,
            background_y=background_y,
            subtracted_y=subtracted_y,
            direct_subtracted_y=direct_sub_y,
            title=title,
            error_y=error_y,
        )

    def _refresh_background_vanadium_plots(self, measurement, *, show_error_bars: bool) -> None:
        if (
            self.current_project_state is None
            or self.current_project_root is None
            or not hasattr(self, "background_vanadium_chi_plot_pane")
            or not hasattr(self, "background_vanadium_subtraction_plot_pane")
        ):
            return

        state = self._get_background_state()
        par_path_str = getattr(self, "_background_cached_par_path", None)
        if not par_path_str:
            return
        sample_key = background_sample_key(Path(par_path_str), self.current_project_root)
        if not sample_key:
            return
        cached = state.get("measurements_by_par")
        if not isinstance(cached, dict):
            return
        entry = cached.get(sample_key)
        if not isinstance(entry, dict):
            return

        vanadium = entry.get("vanadium_linear_combination")
        if not isinstance(vanadium, dict):
            self.background_vanadium_chi_plot_pane.object = None
            self.background_vanadium_subtraction_plot_pane.object = None
            return

        trans = list(vanadium.get("trans") or [])
        chi = list(vanadium.get("chi") or [])
        fitted = list(vanadium.get("fitted") or [])
        best_t_raw = vanadium.get("best_t")
        best_t = float(best_t_raw) if isinstance(best_t_raw, (int, float)) else None
        effective_raw = vanadium.get("effective_t")
        effective_t = float(effective_raw) if isinstance(effective_raw, (int, float)) else best_t
        t_mode = str(vanadium.get("t_mode") or "computed")

        self.background_vanadium_chi_plot_pane.object = build_vanadium_chi_figure(
            trans,
            chi,
            fitted,
            best_t=best_t,
            effective_t=effective_t,
            t_mode=t_mode,
        )

        nor = getattr(measurement, "norData", None)
        env = getattr(measurement, "envData", None)
        if nor is None or env is None or effective_t is None:
            self.background_vanadium_subtraction_plot_pane.object = None
            return
        nor_arr = np.asarray(nor)
        env_arr = np.asarray(env)
        if nor_arr.ndim != 2 or env_arr.ndim != 2:
            self.background_vanadium_subtraction_plot_pane.object = None
            return

        x = nor_arr[:, 0]
        vanadium_y = nor_arr[:, 1]
        env_x = env_arr[:, 0]
        env_y = env_arr[:, 1]
        same_grid = nor_arr.shape[0] == env_arr.shape[0] and np.array_equal(x, env_x)

        if same_grid:
            background_y = float(effective_t) * env_y
            subtracted_y = vanadium_y - background_y
        else:
            env_order = np.argsort(env_x)
            sorted_env_x = env_x[env_order]
            sorted_env_y = env_y[env_order]
            interpolated_env_y = np.interp(x, sorted_env_x, sorted_env_y)
            background_y = float(effective_t) * interpolated_env_y
            subtracted_y = vanadium_y - background_y

        error_y = None

        if show_error_bars and nor_arr.shape[1] >= 3 and env_arr.shape[1] >= 3:
            if same_grid:
                subt = binary_sum(1.0, nor_arr, -float(effective_t), env_arr)
                if subt is not None and getattr(subt, "ndim", 0) == 2 and subt.shape[1] >= 3:
                    subtracted_y = subt[:, 1]
                    error_y = subt[:, 2]
            else:
                env_order = np.argsort(env_x)
                sorted_env_x = env_x[env_order]
                sorted_env_y = env_y[env_order]
                sorted_env_err = env_arr[env_order, 2]
                interpolated_env_y = np.interp(x, sorted_env_x, sorted_env_y)
                interpolated_env_err = np.interp(x, sorted_env_x, sorted_env_err)
                background_y = float(effective_t) * interpolated_env_y
                subtracted_y = vanadium_y - background_y
                error_y = np.sqrt(np.square(nor_arr[:, 2]) + np.square(float(effective_t) * interpolated_env_err))

        title = f"Vanadium subtraction (t = {float(effective_t):.2f})"
        self.background_vanadium_subtraction_plot_pane.object = build_vanadium_subtraction_figure(
            x=x,
            vanadium_y=vanadium_y,
            background_y=background_y,
            subtracted_y=subtracted_y,
            title=title,
            error_y=error_y,
        )

    def _refresh_background_final_signals_plot(self, measurement, *, show_error_bars: bool) -> None:
        if (
            self.current_project_state is None
            or self.current_project_root is None
            or not hasattr(self, "background_final_signals_plot_pane")
        ):
            return

        state = self._get_background_state()
        par_path_str = getattr(self, "_background_cached_par_path", None)
        if not par_path_str:
            self.background_final_signals_plot_pane.object = None
            return
        sample_key = background_sample_key(Path(par_path_str), self.current_project_root)
        if not sample_key:
            self.background_final_signals_plot_pane.object = None
            return
        cached = state.get("measurements_by_par")
        if not isinstance(cached, dict):
            self.background_final_signals_plot_pane.object = None
            return
        entry = cached.get(sample_key)
        if not isinstance(entry, dict):
            self.background_final_signals_plot_pane.object = None
            return

        linear = entry.get("linear_combination")
        vanadium = entry.get("vanadium_linear_combination")
        if not isinstance(linear, dict) or not isinstance(vanadium, dict):
            self.background_final_signals_plot_pane.object = None
            return

        sample_t_raw = linear.get("effective_t")
        van_t_raw = vanadium.get("effective_t")
        if not isinstance(sample_t_raw, (int, float)) or not isinstance(van_t_raw, (int, float)):
            self.background_final_signals_plot_pane.object = None
            return
        sample_t = float(sample_t_raw)
        van_t = float(van_t_raw)

        dat = getattr(measurement, "Data", None)
        con = getattr(measurement, "conData", None)
        env = getattr(measurement, "envData", None)
        nor = getattr(measurement, "norData", None)
        if dat is None or con is None or env is None or nor is None:
            self.background_final_signals_plot_pane.object = None
            return

        dat_arr = np.asarray(dat)
        con_arr = np.asarray(con)
        env_arr = np.asarray(env)
        nor_arr = np.asarray(nor)
        if dat_arr.ndim != 2 or con_arr.ndim != 2 or env_arr.ndim != 2 or nor_arr.ndim != 2:
            self.background_final_signals_plot_pane.object = None
            return
        if dat_arr.shape[0] != con_arr.shape[0] or dat_arr.shape[0] != env_arr.shape[0]:
            self.background_final_signals_plot_pane.object = None
            return
        if nor_arr.shape[0] != env_arr.shape[0]:
            self.background_final_signals_plot_pane.object = None
            return
        if not np.array_equal(dat_arr[:, 0], con_arr[:, 0]) or not np.array_equal(dat_arr[:, 0], env_arr[:, 0]):
            self.background_final_signals_plot_pane.object = None
            return
        if not np.array_equal(nor_arr[:, 0], env_arr[:, 0]):
            self.background_final_signals_plot_pane.object = None
            return

        bckgt = binary_sum(sample_t, con_arr, 1.0 - sample_t, env_arr)
        sample_sub = dat_arr[:, 1] - (sample_t * con_arr[:, 1] + (1.0 - sample_t) * env_arr[:, 1])
        sample_err = None
        if show_error_bars and bckgt is not None:
            subt = binary_sum(1.0, dat_arr, -1.0, bckgt)
            if subt is not None and getattr(subt, "ndim", 0) == 2 and subt.shape[1] >= 3:
                sample_sub = subt[:, 1]
                sample_err = subt[:, 2]

        van_sub = nor_arr[:, 1] - van_t * env_arr[:, 1]
        van_err = None
        if show_error_bars and nor_arr.shape[1] >= 3 and env_arr.shape[1] >= 3:
            subt = binary_sum(1.0, nor_arr, -van_t, env_arr)
            if subt is not None and getattr(subt, "ndim", 0) == 2 and subt.shape[1] >= 3:
                van_sub = subt[:, 1]
                van_err = subt[:, 2]

        title = f"Background-subtracted signals (sample t={sample_t:.2f}, vanadium t={van_t:.2f})"
        self.background_final_signals_plot_pane.object = build_final_background_subtracted_signals_figure(
            x=dat_arr[:, 0],
            sample_subtracted_y=sample_sub,
            vanadium_subtracted_y=van_sub,
            title=title,
            sample_error_y=sample_err,
            vanadium_error_y=van_err,
        )

    def _set_background_selected_path(self, path: str) -> None:
        if self.current_project_state is None:
            return
        self._clear_background_cached_measurement_state()
        state = self._get_background_state()
        state["selected_par_path"] = str(path or "").strip()
        state["latest_measurement_artifact"] = None
        state["validation"]["is_valid"] = False
        state["validation"]["selected_par_path"] = str(path or "").strip()
        state["validation"]["file_accessible"] = False
        state["validation"]["error"] = None
        self._persist_background_state(state)

    def _on_background_source_mode_change(self, event) -> None:
        if getattr(self, "_suspend_background_events", False) or event.new == event.old:
            return
        self._clear_background_import_prompt()
        state = self._get_background_state()
        state["source_mode"] = event.new
        self._persist_background_state(state)
        self._set_background_toast_notification(
            "Input mode changed. Choose a sample .par file.",
            alert_type="secondary",
        )
        self.background_extract_button.disabled = True
        self._set_background_source_widget_visibility()
        self._sync_background_import_visibility()
        self._refresh_interaction_states()

    def _on_background_par_dropdown_change(self, event) -> None:
        if getattr(self, "_suspend_background_events", False) or self.current_project_state is None:
            return
        if event.new == event.old:
            return
        self._clear_background_import_prompt()
        selected_path = str(event.new or "").strip()
        self.background_manual_path_input.value = selected_path
        self._set_background_selected_path(selected_path)
        self._refresh_background_selection_section_state()
        if selected_path and self._apply_cached_background_measurement(Path(selected_path), update_message=True):
            return
        self._reset_background_t_controls_ui()
        self._refresh_background_plots()

        self._set_background_toast_notification(
            "Selection changed. Validate it to continue.",
            alert_type="secondary",
        )
        self.background_extract_button.disabled = True
        self._sync_background_import_visibility()
        self._refresh_interaction_states()

    def _on_background_manual_path_change(self, event) -> None:
        if getattr(self, "_suspend_background_events", False) or self.current_project_state is None:
            return
        if event.new == event.old:
            return
        self._clear_background_import_prompt()
        selected_path = str(event.new or "").strip()
        self._set_background_selected_path(selected_path)
        self._refresh_background_selection_section_state()
        if selected_path and self.current_project_root is not None:
            if self._apply_cached_background_measurement(Path(selected_path), update_message=True):
                return
        self._reset_background_t_controls_ui()
        self._refresh_background_plots()

        self._set_background_toast_notification(
            "Path changed. Validate it to continue.",
            alert_type="secondary",
        )
        self.background_extract_button.disabled = True
        self._sync_background_import_visibility()
        self._refresh_interaction_states()

    def _get_background_candidate_path(self) -> Path | None:
        if self.background_source_mode.value == "Select File":
            candidate = str(self.background_par_dropdown.value or "").strip()
            if not candidate:
                return None
            return Path(candidate).expanduser()

        candidate = str(self.background_manual_path_input.value or "").strip()
        if not candidate:
            return None
        return Path(candidate).expanduser()

    def _validate_background_selection(self, _event=None) -> None:
        if self.operation_in_progress:
            self._show_workspace_blocked_message()
            return
        if self.current_project_root is None or self.current_project_state is None:
            return

        candidate_path = self._get_background_candidate_path()
        if candidate_path is None:
            self.background_message.object = "Select a .par file path first."
            self.background_message.alert_type = "danger"
            self.background_message.visible = False
            self._show_error_toast("Select a .par file path first.")
            self._refresh_interaction_states()
            # self._render_current_screen()
            return

        self.background_manual_path_input.value = str(candidate_path)
        self._set_background_selected_path(str(candidate_path))
        self._refresh_background_selection_section_state()
        self._refresh_background_plots()

        if not is_par_file_in_processed_parfiles(candidate_path, self.current_project_root):
            self._prompt_background_import(candidate_path)
            self._sync_background_import_visibility()
            self._refresh_background_selection_section_state()
            self._refresh_interaction_states()
            # self._render_current_screen()
            return

        self._clear_background_import_prompt()
        self._apply_background_validation(candidate_path)
        self._sync_background_import_visibility()
        self._refresh_background_selection_section_state()
        self._refresh_interaction_states()
        # self._render_current_screen()

    def _apply_background_validation(self, par_file: Path) -> None:
        validation_result = validate_background_par_file(par_file)
        state = self._get_background_state()
        state["selected_par_path"] = str(par_file.resolve(strict=False))
        state["validation"] = validation_result.to_state()
        self._persist_background_state(state)
        self._refresh_background_selection_section_state()

        self.background_extract_button.disabled = not validation_result.is_valid
        if validation_result.is_valid:
            self._show_background_ready_to_extract_toast()
            return

        self._set_background_toast_notification(
            validation_result.error or "Validation failed.",
            alert_type="danger",
        )

    def _prompt_background_import(self, candidate_path: Path) -> None:
        self._pending_background_import_path = candidate_path.resolve(strict=False)
        self.background_import_prompt.object = (
            "The selected .par file is outside `parfiles/`. "
            "Copy it into `parfiles/` to continue."
        )
        self.background_import_prompt.alert_type = "warning"
        self.background_import_prompt.visible = True
        self._sync_background_import_visibility()
        self._set_background_toast_notification(
            "Copy the selected .par file into the project to validate it.",
            alert_type="warning",
        )
        self.background_extract_button.disabled = True

    def _clear_background_import_prompt(self) -> None:
        self._pending_background_import_path = None
        self.background_import_prompt.visible = False
        self.background_import_prompt.object = ""
        self.background_import_prompt.alert_type = "warning"
        self._sync_background_import_visibility()

    def _cancel_background_import(self, _event=None) -> None:
        self._clear_background_import_prompt()
        self._set_background_toast_notification("Import cancelled.", alert_type="secondary")
        self._refresh_interaction_states()

    def _copy_background_file_into_project(self, _event=None) -> None:
        if self.operation_in_progress:
            self._show_workspace_blocked_message()
            return
        if self.current_project_root is None or self._pending_background_import_path is None:
            return

        source_path = self._pending_background_import_path
        target_dir = self._project_data_path("parfiles")
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / source_path.name
        if target_path.exists():
            self._set_background_toast_notification(
                (
                    "A .par file with the same name already exists in parfiles/. "
                    "Rename the source file manually and try again."
                ),
                alert_type="danger",
            )
            self.background_import_prompt.alert_type = "danger"
            self.background_import_prompt.object = (
                "Import blocked because a file with the same name already exists."
            )
            self.background_import_prompt.visible = True
            # self._render_current_screen()
            return

        from shutil import copy2
        try:
            copy2(source_path, target_path)
            self._clear_background_import_prompt()
            self.background_manual_path_input.value = str(target_path)
            self._set_background_selected_path(str(target_path))
            self._refresh_background_par_dropdown_options()
            self._apply_background_validation(target_path)
            self._refresh_background_selection_section_state()
            self._show_success_toast("Parameter file copied into the project.")
        except Exception as e:
            self._clear_background_import_prompt()
            self._show_error_toast(f"Could not copy file into project: {str(e)}")

    def _notify_background_extraction_pending(self, _event=None) -> None:
        if self.operation_in_progress:
            self._show_workspace_blocked_message()
            return
        if self.background_extract_button.disabled:
            return
        self._start_background_extraction()

    def _start_background_extraction(self) -> None:
        if self.current_project_root is None or self.current_project_state is None:
            return

        validation_state = self._get_background_state()["validation"]
        selected_par_path = validation_state.get("selected_par_path")
        if not validation_state.get("is_valid") or not selected_par_path:
            self._show_error_toast("Validate a sample .par file before extracting.")
            self._refresh_interaction_states()
            return

        run_id = self._create_run_id()
        stdout_file = self._project_data_path("logfiles", f"{run_id}-stdout.txt")
        run_record = RunRecord(
            run_id=run_id,
            workflow="background_extract",
            status="running",
            started_at=now_iso(),
            summary=f"Extracting `{Path(selected_par_path).name}`",
            workflow_data={"par_file": str(Path(selected_par_path).resolve(strict=False))},
            output_paths=OutputPaths(stdout_file=str(stdout_file)),
        )
        self.current_project_state.runs.append(run_record)
        self.current_project_state.project.updated_at = now_iso()
        self._persist_current_project_state()

        self.operation_in_progress = True
        self._background_active_run_id = run_id
        self._background_result_file = (
            self._project_data_path("logfiles", f"{run_id}-background-result.json")
        )
        self._clear_workspace_message()
        self._set_background_toast_notification(
            "Extracting sample measurement. Workspace interactions are blocked until it finishes.",
            alert_type="warning",
        )
        self._begin_workspace_loading("Extracting sample measurement...")

        par_file = Path(selected_par_path)
        if self._background_result_file.exists():
            self._background_result_file.unlink()

        command = [
            sys.executable,
            str(BACKGROUND_SUBPROCESS_WORKER),
            str(par_file),
            str(self.current_project_root),
            run_id,
            str(self._background_result_file),
        ]
        env = os.environ.copy()

        try:
            self._background_run_process = subprocess.Popen(
                command,
                cwd=str(REPO_ROOT),
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except Exception as exc:
            failure = self._build_background_failure_result(
                run_id,
                stdout_file,
                f"Could not start the extraction subprocess: {exc}",
            )
            self._background_run_process = None
            self._finalize_background_run(failure)
            return

        self._start_background_run_poll()
        self._refresh_interaction_states()

    def _start_background_run_poll(self) -> None:
        if self._background_run_poll is not None:
            self._background_run_poll.stop()
            self._background_run_poll = None

        if pn.state.curdoc is not None:
            self._background_run_poll = pn.state.add_periodic_callback(
                self._finalize_background_run_if_ready,
                period=500,
                start=True,
            )

    def _finalize_background_run_if_ready(self) -> None:
        if self._background_run_process is None or self._background_run_process.poll() is None:
            return

        if self._background_run_poll is not None:
            self._background_run_poll.stop()
            self._background_run_poll = None

        result = self._load_background_subprocess_result(self._background_run_process.returncode)
        self._background_run_process = None
        self._background_result_file = None
        self._finalize_background_run(result)

    def _load_background_subprocess_result(
        self,
        returncode: int | None,
    ) -> BackgroundExtractionResult:
        if self._background_result_file is None:
            return self._build_background_failure_result(
                self._background_active_run_id or "unknown",
                self._expected_background_stdout_file(),
                "No background result file location was configured.",
            )
        if self._background_result_file.exists():
            try:
                payload = json.loads(self._background_result_file.read_text(encoding="utf-8"))
                return BackgroundExtractionResult(
                    run_id=str(payload["run_id"]),
                    status=str(payload["status"]),
                    stdout_file=str(payload["stdout_file"]),
                    measurement_file=payload.get("measurement_file"),
                    generated_files=list(payload.get("generated_files", [])),
                    summary=str(payload.get("summary", "")),
                    error=payload.get("error"),
                )
            except Exception as exc:
                return self._build_background_failure_result(
                    self._background_active_run_id or "unknown",
                    self._expected_background_stdout_file(),
                    f"Could not read the extraction subprocess result: {exc}",
                )

        return self._build_background_failure_result(
            self._background_active_run_id or "unknown",
            self._expected_background_stdout_file(),
            f"Extraction subprocess exited with code {returncode} without producing a result file.",
        )

    def _expected_background_stdout_file(self) -> str:
        if self.current_project_root is None or self._background_active_run_id is None:
            return ""
        return str(
            self._project_data_path("logfiles", f"{self._background_active_run_id}-stdout.txt")
        )

    def _build_background_failure_result(
        self,
        run_id: str,
        stdout_file: str | Path,
        error_message: str,
    ) -> BackgroundExtractionResult:
        return BackgroundExtractionResult(
            run_id=run_id,
            status="failed",
            stdout_file=str(stdout_file),
            measurement_file=None,
            generated_files=[],
            summary=f"Processed run `{run_id}`, status: `failed`, error: {error_message}",
            error=error_message,
        )

    def _finalize_background_run(self, result: BackgroundExtractionResult | None) -> None:
        self.operation_in_progress = False
        try:
            if self.current_project_state is None or self._background_active_run_id is None:
                self._refresh_interaction_states()
                return

            run_record = next(
                (
                    record
                    for record in reversed(self.current_project_state.runs)
                    if record.run_id == self._background_active_run_id
                ),
                None,
            )
            if run_record is not None and result is not None:
                run_record.status = result.status
                run_record.finished_at = now_iso()
                run_record.summary = result.summary
                run_record.error = result.error
                run_record.output_paths.stdout_file = result.stdout_file
                run_record.output_paths.generated_files = list(result.generated_files)
                self.current_project_state.project.updated_at = now_iso()
                self._persist_current_project_state()

            self._background_active_run_id = None
            if result is None:
                self._set_background_toast_notification(
                    "Sample extraction finished without a result payload.",
                    alert_type="danger",
                )
                self._refresh_interaction_states()
                return

            if result.status == "succeeded" and result.measurement_file:
                state = self._get_background_state()
                artifact_path = Path(str(result.measurement_file)).expanduser()
                if self.current_project_root is not None:
                    try:
                        artifact_for_state = (
                            artifact_path.resolve(strict=False)
                            .relative_to(self.current_project_root.resolve(strict=False))
                            .as_posix()
                        )
                    except Exception:
                        artifact_for_state = str(artifact_path)
                else:
                    artifact_for_state = str(artifact_path)

                state["latest_measurement_artifact"] = artifact_for_state
                self._background_plot_signature_cache = None

                par_path_str = None
                if run_record is not None:
                    par_path_str = run_record.workflow_data.get("par_file")
                if isinstance(par_path_str, str) and self.current_project_root is not None:
                    par_path = Path(par_path_str).expanduser()
                    sample_key = background_sample_key(par_path, self.current_project_root)
                    if sample_key:
                        cached = state.get("measurements_by_par")
                        if not isinstance(cached, dict):
                            cached = {}
                            state["measurements_by_par"] = cached
                        signature = background_par_signature(par_path)
                        cached_entry = {
                            "measurement_artifact": artifact_for_state,
                            "run_id": result.run_id,
                            "extracted_at": now_iso(),
                        }
                        if signature is not None:
                            cached_entry["par_mtime"] = signature[0]
                            cached_entry["par_size"] = signature[1]
                        cached[sample_key] = cached_entry

                self._persist_background_state(state)
                self._refresh_background_plots()
                self._show_success_toast("Sample extraction finished successfully.")

            else:
                self._show_error_toast(f"Sample extraction finished with errors. {result.error}")

            self._refresh_interaction_states()
        finally:
            self._end_workspace_loading(defer=True)

    def _create_run_id(self) -> str:
        return datetime.now(tz=PARIS_TZ).strftime("%Y%m%d-%H%M%S")
