from __future__ import annotations

import json
import pickle
from contextlib import contextmanager
from datetime import datetime
from html import escape as html_escape
from os import chdir, getcwd
from pathlib import Path
from shutil import copy2

import numpy as np

import panel as pn

from toscana.io.loading import read_xye

from toscana_gui.contexts import (
    context_manifest_relpath,
    load_context_manifest,
    project_relpath,
    resolve_project_path,
    write_context_manifest,
)
from toscana_gui.normalization.plots import (
    build_sample_normalization_figure,
    build_vanadium_fit_selection_figure,
    build_vanadium_self_fit_preview_figure,
    update_sample_normalization_figure,
    update_vanadium_self_fit_preview_figure,
    update_vanadium_fit_selection_figure,
)
from toscana_gui.normalization.tasks import (
    ensure_qspdata_dir,
    is_qdat_within_project,
    list_sample_qdat_files,
    list_vanadium_qdat_files,
)
from toscana_gui.persistence import PARIS_TZ, now_iso


class NormalizationControllerMixin:
    _NORMALIZATION_FIT_PLATEAU_FRACTION = 0.10
    _NORMALIZATION_FIT_DATA_MODE_PERCENTILE = "percentile_band"
    _NORMALIZATION_FIT_DATA_MODE_MANUAL = "manual_window"

    @staticmethod
    def _normalization_range_value(widget, fallback: tuple[float, float]) -> tuple[float, float]:
        try:
            lower, upper = getattr(widget, "value", fallback)
            lower = float(lower)
            upper = float(upper)
        except Exception:
            return fallback
        if not np.isfinite(lower) or not np.isfinite(upper):
            return fallback
        return (lower, upper)

    @staticmethod
    def _set_normalization_range_value(widget, value: tuple[float, float]) -> None:
        try:
            widget.value = [float(value[0]), float(value[1])]
        except Exception:
            return

    def _normalize_normalization_fit_data_mode(self, raw_mode: object) -> str:
        mode = str(raw_mode or "").strip()
        if mode in ("Define selection parameters", self._NORMALIZATION_FIT_DATA_MODE_PERCENTILE, ""):
            return self._NORMALIZATION_FIT_DATA_MODE_PERCENTILE
        if mode in ("Hardcoded window", self._NORMALIZATION_FIT_DATA_MODE_MANUAL):
            return self._NORMALIZATION_FIT_DATA_MODE_MANUAL
        return self._NORMALIZATION_FIT_DATA_MODE_PERCENTILE

    def _is_normalization_fit_data_manual_mode(self, raw_mode: object) -> bool:
        return self._normalize_normalization_fit_data_mode(raw_mode) == self._NORMALIZATION_FIT_DATA_MODE_MANUAL

    def _normalization_fit_data_mode_label(self, raw_mode: object) -> str:
        return "Manual window" if self._is_normalization_fit_data_manual_mode(raw_mode) else "Percentile band"

    def _sync_normalization_fit_data_ui_summary(self) -> None:
        panes = []
        legacy_pane = getattr(self, "normalization_fit_data_ui_summary", None)
        if legacy_pane is not None:
            panes.append(legacy_pane)
        redesign_pane = getattr(self, "normalization_fit_data_redesign_mode_chips", None)
        if redesign_pane is not None:
            panes.append(redesign_pane)
        if not panes:
            return
        mode = self._normalize_normalization_fit_data_mode(
            getattr(getattr(self, "normalization_fit_data_selection_mode", None), "value", "")
        )
        use_sliders = bool(getattr(getattr(self, "normalization_fit_data_use_sliders", None), "value", False))
        mode_label = self._normalization_fit_data_mode_label(mode)
        input_label = "Axis sliders" if use_sliders else "Numeric inputs"
        mode_kind = "manual" if self._is_normalization_fit_data_manual_mode(mode) else "band"
        input_kind = "slider" if use_sliders else "input"
        html = (
            "<div class=\"toscana-normalization-fit-data-summary\">"
            f"<div class=\"toscana-normalization-fit-data-chip toscana-normalization-fit-data-chip--{mode_kind}\">{mode_label}</div>"
            f"<div class=\"toscana-normalization-fit-data-chip toscana-normalization-fit-data-chip--{input_kind}\">{input_label}</div>"
            "</div>"
        )
        for pane in panes:
            pane.object = html

    def _sync_normalization_fit_data_redesign_buttons(self) -> None:
        button_input_mode = getattr(self, "normalization_fit_data_redesign_switch_input_mode", None)
        button_method = getattr(self, "normalization_fit_data_redesign_switch_method", None)
        if button_input_mode is None and button_method is None:
            return
        mode = self._normalize_normalization_fit_data_mode(
            getattr(getattr(self, "normalization_fit_data_selection_mode", None), "value", "")
        )
        use_sliders = bool(getattr(getattr(self, "normalization_fit_data_use_sliders", None), "value", False))
        manual_mode = self._is_normalization_fit_data_manual_mode(mode)
        if button_input_mode is not None:
            # Mirror Normalization source switch: warning highlights the non-default alternative.
            button_input_mode.button_type = "warning" if use_sliders else "primary"
        if button_method is not None:
            button_method.button_type = "warning" if manual_mode else "primary"

    def _update_normalization_fit_data_redesign_value_labels(self) -> None:
        lower = getattr(self, "normalization_fit_data_redesign_vertical_lower_value", None)
        upper = getattr(self, "normalization_fit_data_redesign_vertical_upper_value", None)
        if lower is None or upper is None:
            return
        mode = self._normalize_normalization_fit_data_mode(
            getattr(getattr(self, "normalization_fit_data_selection_mode", None), "value", "")
        )
        manual_mode = self._is_normalization_fit_data_manual_mode(mode)
        use_sliders = bool(getattr(getattr(self, "normalization_fit_data_use_sliders", None), "value", False))

        vertical_lower_input = getattr(self, "normalization_fit_data_redesign_vertical_lower_input", None)
        vertical_upper_input = getattr(self, "normalization_fit_data_redesign_vertical_upper_input", None)
        q_input_row = getattr(self, "normalization_fit_data_redesign_q_input_row", None)
        q_start_input = getattr(self, "normalization_fit_data_redesign_q_start_input", None)
        q_end_input = getattr(self, "normalization_fit_data_redesign_q_end_input", None)
        q_range = getattr(self, "normalization_fit_data_redesign_q_range_slider", None)
        vertical_range = getattr(self, "normalization_fit_data_redesign_vertical_range_slider", None)

        # Redesign input-mode behavior: sliders remain visible but are disabled when using numeric inputs.
        if q_range is not None:
            try:
                q_range.disabled = not use_sliders
                q_range.label_display = "flex" if use_sliders else "none"
            except Exception:
                pass
        if q_start_input is not None and q_range is not None:
            try:
                q_start_input.start = float(q_range.start)
                q_start_input.end = float(q_range.end)
                q_start_input.step = float(q_range.step)
            except Exception:
                pass
        if q_end_input is not None and q_range is not None:
            try:
                q_end_input.start = float(q_range.start)
                q_end_input.end = float(q_range.end)
                q_end_input.step = float(q_range.step)
            except Exception:
                pass
        if vertical_range is not None:
            try:
                vertical_range.disabled = not use_sliders
            except Exception:
                pass
        if q_input_row is not None:
            q_input_row.visible = not use_sliders

        # Swap vertical value displays for numeric inputs.
        lower.visible = bool(use_sliders)
        upper.visible = bool(use_sliders)
        if vertical_lower_input is not None:
            vertical_lower_input.visible = not use_sliders
        if vertical_upper_input is not None:
            vertical_upper_input.visible = not use_sliders
        if manual_mode:
            y_min = float(getattr(getattr(self, "normalization_fit_data_y_min", None), "value", 0.0) or 0.0)
            y_max = float(getattr(getattr(self, "normalization_fit_data_y_max", None), "value", 0.0) or 0.0)
            lower.object = f"Intensity min: {y_min:.0f}"
            upper.object = f"Intensity max: {y_max:.0f}"
            if vertical_lower_input is not None:
                try:
                    vertical_lower_input.step = 1.0
                    if vertical_range is not None:
                        vertical_lower_input.start = float(vertical_range.start)
                        vertical_lower_input.end = float(vertical_range.end)
                    vertical_lower_input.value = y_min
                except Exception:
                    pass
            if vertical_upper_input is not None:
                try:
                    vertical_upper_input.step = 1.0
                    if vertical_range is not None:
                        vertical_upper_input.start = float(vertical_range.start)
                        vertical_upper_input.end = float(vertical_range.end)
                    vertical_upper_input.value = y_max
                except Exception:
                    pass
            q_start = float(getattr(getattr(self, "normalization_fit_data_q_tail_low", None), "value", 0.0) or 0.0)
            q_end = float(getattr(getattr(self, "normalization_fit_data_q_tail_high", None), "value", 0.0) or 0.0)
            if q_start_input is not None:
                try:
                    q_start_input.value = q_start
                except Exception:
                    pass
            if q_end_input is not None:
                try:
                    q_end_input.value = q_end
                except Exception:
                    pass
            return
        min_pct = int(getattr(getattr(self, "normalization_fit_data_min_percentile", None), "value", 0) or 0)
        max_pct = int(getattr(getattr(self, "normalization_fit_data_max_percentile", None), "value", 0) or 0)
        lower.object = f"Lower percentile: {min_pct:d}"
        upper.object = f"Upper percentile: {max_pct:d}"
        if vertical_lower_input is not None:
            try:
                vertical_lower_input.step = 1.0
                vertical_lower_input.start = 0.0
                vertical_lower_input.end = 100.0
                vertical_lower_input.value = float(min_pct)
            except Exception:
                pass
        if vertical_upper_input is not None:
            try:
                vertical_upper_input.step = 1.0
                vertical_upper_input.start = 0.0
                vertical_upper_input.end = 100.0
                vertical_upper_input.value = float(max_pct)
            except Exception:
                pass

        # Keep Q numeric inputs in sync (best-effort).
        q_start = float(getattr(getattr(self, "normalization_fit_data_q_tail_low", None), "value", 0.0) or 0.0)
        q_end = float(getattr(getattr(self, "normalization_fit_data_q_tail_high", None), "value", 0.0) or 0.0)
        if q_start_input is not None:
            try:
                q_start_input.value = q_start
            except Exception:
                pass
        if q_end_input is not None:
            try:
                q_end_input.value = q_end
            except Exception:
                pass

    def _on_normalization_fit_data_redesign_numeric_input_change(self, event=None) -> None:
        if getattr(self, "_suspend_normalization_events", False) or self.current_project_state is None:
            return
        # Only react when the redesign is in numeric-input mode (sliders visible but disabled).
        use_sliders = bool(getattr(getattr(self, "normalization_fit_data_use_sliders", None), "value", False))
        if use_sliders:
            return
        if event is None:
            return
        src = getattr(event, "obj", None)
        if src is None:
            return

        q_start_input = getattr(self, "normalization_fit_data_redesign_q_start_input", None)
        q_end_input = getattr(self, "normalization_fit_data_redesign_q_end_input", None)
        vertical_lower_input = getattr(self, "normalization_fit_data_redesign_vertical_lower_input", None)
        vertical_upper_input = getattr(self, "normalization_fit_data_redesign_vertical_upper_input", None)

        mode = self._normalize_normalization_fit_data_mode(
            getattr(getattr(self, "normalization_fit_data_selection_mode", None), "value", "")
        )
        manual_mode = self._is_normalization_fit_data_manual_mode(mode)

        def _to_float(value: object, fallback: float) -> float:
            try:
                val = float(value)
            except Exception:
                return fallback
            return val if np.isfinite(val) else fallback

        self._suspend_normalization_events = True
        try:
            if src is q_start_input and hasattr(self, "normalization_fit_data_q_tail_low"):
                current = float(getattr(self.normalization_fit_data_q_tail_low, "value", 0.0) or 0.0)
                self.normalization_fit_data_q_tail_low.value = _to_float(getattr(src, "value", None), current)
            elif src is q_end_input and hasattr(self, "normalization_fit_data_q_tail_high"):
                current = float(getattr(self.normalization_fit_data_q_tail_high, "value", 0.0) or 0.0)
                self.normalization_fit_data_q_tail_high.value = _to_float(getattr(src, "value", None), current)
            elif src in (vertical_lower_input, vertical_upper_input):
                raw = getattr(src, "value", None)
                if manual_mode:
                    if src is vertical_lower_input and hasattr(self, "normalization_fit_data_y_min"):
                        current = float(getattr(self.normalization_fit_data_y_min, "value", 0.0) or 0.0)
                        self.normalization_fit_data_y_min.value = _to_float(raw, current)
                    if src is vertical_upper_input and hasattr(self, "normalization_fit_data_y_max"):
                        current = float(getattr(self.normalization_fit_data_y_max, "value", 0.0) or 0.0)
                        self.normalization_fit_data_y_max.value = _to_float(raw, current)
                else:
                    if src is vertical_lower_input and hasattr(self, "normalization_fit_data_min_percentile"):
                        current = int(getattr(self.normalization_fit_data_min_percentile, "value", 0) or 0)
                        self.normalization_fit_data_min_percentile.value = int(_to_float(raw, float(current)))
                    if src is vertical_upper_input and hasattr(self, "normalization_fit_data_max_percentile"):
                        current = int(getattr(self.normalization_fit_data_max_percentile, "value", 0) or 0)
                        self.normalization_fit_data_max_percentile.value = int(_to_float(raw, float(current)))
        finally:
            self._suspend_normalization_events = False

        # Reuse the canonical sync pipeline (updates plot, persists, updates redesign widgets).
        self._on_normalization_fit_data_controls_change()

    def _reset_normalization_runtime_state(self) -> None:
        """
        Clear in-memory (non-persisted) normalization runtime state.

        This prevents cached fit/export results and Plotly view state from
        leaking across projects when switching between `toscana-project.json`
        files within the same running Panel session.
        """

        # Fit parameter runtime caches (never persisted).
        self._normalization_last_fit = None
        self._normalization_last_exported = None

        # Plot source tokens used to decide when to rebuild figures (stable Plotly "Home" view).
        self._normalization_fit_data_plot_source = None
        self._normalization_fit_params_plot_source = None

        # Best-effort: clear visible UI if it exists.
        if hasattr(self, "normalization_fit_params_plot_pane"):
            try:
                self.normalization_fit_params_plot_pane.object = None
            except Exception:
                pass
        if hasattr(self, "normalization_vanadium_self_fit_preview_plot_pane"):
            try:
                self.normalization_vanadium_self_fit_preview_plot_pane.object = None
            except Exception:
                pass
        if hasattr(self, "normalization_vanadium_self_fit_preview_fit_table"):
            try:
                self.normalization_vanadium_self_fit_preview_fit_table.object = ""
            except Exception:
                pass
        if hasattr(self, "normalization_fit_params_results"):
            try:
                self.normalization_fit_params_results.object = "No fit has been run yet."
            except Exception:
                pass

    def _set_normalization_fit_params_status(self, message: str) -> None:
        pane = getattr(self, "normalization_fit_params_status", None)
        if pane is None:
            return
        pane.object = f"**Status:** {str(message)}"

    def _normalization_current_last_fit(self) -> dict[str, object] | None:
        """
        Return the in-memory fit result if it matches the current project/context.

        This avoids stale fit results leaking across context/project switches.
        """
        context_id = str(getattr(getattr(self, "normalization_context_select", None), "value", "") or "").strip()
        project_token = str(getattr(self, "current_project_root", "") or "")
        fit = getattr(self, "_normalization_last_fit", None)
        if not isinstance(fit, dict):
            return None
        fit_context = str(fit.get("context_id") or "").strip()
        fit_project = str(fit.get("project_root") or "")
        if fit_context != context_id or fit_project != project_token:
            return None
        return fit  # type: ignore[return-value]

    def _normalization_fit_data_selection_snapshot_fit_relevant(self) -> dict[str, object]:
        # Fit-relevant means: only inputs that change the selected subset.
        # In Normalization, the code keeps the effective Q/Y window unified across
        # manual vs percentile UI modes, so the effective fit window is captured
        # purely by (q_min, q_max, y_min, y_max) regardless of mode/use_sliders.
        return {
            "q_min": float(getattr(getattr(self, "normalization_fit_data_q_min", None), "value", 0.0) or 0.0),
            "q_max": float(getattr(getattr(self, "normalization_fit_data_q_max", None), "value", 0.0) or 0.0),
            "y_min": float(getattr(getattr(self, "normalization_fit_data_y_min", None), "value", 0.0) or 0.0),
            "y_max": float(getattr(getattr(self, "normalization_fit_data_y_max", None), "value", 0.0) or 0.0),
        }

    def _normalization_fit_params_snapshot_fit_relevant(self) -> dict[str, object]:
        def _read_float(name: str, fallback: float) -> float:
            widget = getattr(self, name, None)
            try:
                value = float(getattr(widget, "value", fallback))
            except Exception:
                return float(fallback)
            return float(value)

        out: dict[str, object] = {
            "pinned_A": bool(getattr(getattr(self, "normalization_fit_params_A_pinned", None), "value", True)),
        }
        params: dict[str, dict[str, float]] = {}
        for key in ("a0", "a1", "a2", "A", "lowQ", "Q0", "dQ"):
            params[key] = {
                "value": _read_float(f"normalization_fit_params_{key}_value", 0.0),
                "min": _read_float(f"normalization_fit_params_{key}_min", -1e6),
                "max": _read_float(f"normalization_fit_params_{key}_max", 1e6),
            }
        out["params"] = params
        return out

    def _normalization_fit_is_stale(self, last_fit: dict[str, object]) -> bool:
        try:
            sel_snap = last_fit.get("selection_snapshot")
            if not isinstance(sel_snap, dict) or sel_snap != self._normalization_fit_data_selection_snapshot_fit_relevant():
                return True
            params_snap = last_fit.get("params_snapshot")
            if not isinstance(params_snap, dict) or params_snap != self._normalization_fit_params_snapshot_fit_relevant():
                return True
        except Exception:
            return True
        return False

    def _invalidate_normalization_fit_result(self, *, reason: str) -> None:
        # Clear last fit and all UI that depends on it (plot/table/export).
        self._normalization_last_fit = None

        if hasattr(self, "normalization_fit_params_plot_pane"):
            try:
                self.normalization_fit_params_plot_pane.object = None
            except Exception:
                pass
        if hasattr(self, "normalization_vanadium_self_fit_preview_plot_pane"):
            try:
                self.normalization_vanadium_self_fit_preview_plot_pane.object = None
            except Exception:
                pass
        if hasattr(self, "normalization_vanadium_self_fit_preview_fit_table"):
            try:
                self.normalization_vanadium_self_fit_preview_fit_table.object = ""
            except Exception:
                pass
        if hasattr(self, "normalization_fit_params_results"):
            try:
                self.normalization_fit_params_results.object = "Fit is stale. Run Fit again."
            except Exception:
                pass
        if hasattr(self, "normalization_fit_params_export_prompt"):
            try:
                self.normalization_fit_params_export_prompt.visible = False
                self.normalization_fit_params_export_prompt.object = ""
            except Exception:
                pass
        if hasattr(self, "_sync_normalization_fit_params_export_prompt_visibility"):
            try:
                self._sync_normalization_fit_params_export_prompt_visibility()
            except Exception:
                pass

        reason_map = {
            "fit_data_selection_changed": "Data selection changed.",
            "fit_data_selection_mode_changed": "Data selection changed.",
            "fit_params_changed": "Fit parameters changed.",
        }
        prefix = reason_map.get(str(reason), "Inputs changed.")
        self._set_normalization_fit_params_status(f"{prefix} Fit is stale. Run Fit again.")
        if hasattr(self, "_refresh_normalization_fit_params_button_states"):
            try:
                self._refresh_normalization_fit_params_button_states()
            except Exception:
                pass

    def _normalization_fit_params_can_suggest(self) -> bool:
        if self.current_project_root is None or self.current_project_state is None:
            return False
        if not hasattr(self, "_selected_normalization_manifest_ref"):
            return False
        manifest_ref = str(self._selected_normalization_manifest_ref() or "").strip()
        if not manifest_ref:
            return False
        payload = load_context_manifest(self.current_project_root, manifest_ref)
        artifacts = payload.get("artifacts") if isinstance(payload, dict) else {}
        van_ref = artifacts.get("vanadium_sub_qdat") if isinstance(artifacts, dict) else None
        if not isinstance(van_ref, str) or not van_ref.strip():
            return False
        try:
            van_path = resolve_project_path(self.current_project_root, van_ref)
        except Exception:
            return False
        return van_path.exists()

    def _normalization_fit_params_suggest_initial_guess(self, _event=None) -> None:
        if self.current_project_root is None or self.current_project_state is None:
            return
        if not hasattr(self, "normalization_fit_params_alert"):
            return

        self.normalization_fit_params_alert.visible = False
        self.normalization_fit_params_alert.object = ""

        if not hasattr(self, "_selected_normalization_manifest_ref"):
            self.normalization_fit_params_alert.object = "No normalization context is selected yet."
            self.normalization_fit_params_alert.alert_type = "warning"
            self.normalization_fit_params_alert.visible = True
            return

        manifest_ref = str(self._selected_normalization_manifest_ref() or "").strip()
        if not manifest_ref:
            self.normalization_fit_params_alert.object = "Selected context has no manifest reference."
            self.normalization_fit_params_alert.alert_type = "warning"
            self.normalization_fit_params_alert.visible = True
            return

        payload = load_context_manifest(self.current_project_root, manifest_ref)
        artifacts = payload.get("artifacts") if isinstance(payload, dict) else {}
        van_ref = artifacts.get("vanadium_sub_qdat") if isinstance(artifacts, dict) else None
        if not isinstance(van_ref, str) or not van_ref.strip():
            self.normalization_fit_params_alert.object = "Selected context has no `vanadium_sub_qdat` reference."
            self.normalization_fit_params_alert.alert_type = "warning"
            self.normalization_fit_params_alert.visible = True
            return

        try:
            van_path = resolve_project_path(self.current_project_root, van_ref)
        except Exception:
            self.normalization_fit_params_alert.object = "Vanadium qdat reference could not be resolved."
            self.normalization_fit_params_alert.alert_type = "warning"
            self.normalization_fit_params_alert.visible = True
            return

        if not van_path.exists():
            self.normalization_fit_params_alert.object = f"Missing data: `{van_path}`"
            self.normalization_fit_params_alert.alert_type = "warning"
            self.normalization_fit_params_alert.visible = True
            return

        try:
            q_all, y_all, _e_all = self._read_xye_cached(van_path)
        except Exception as exc:
            self.normalization_fit_params_alert.object = f"Could not load vanadium qdat: {exc}"
            self.normalization_fit_params_alert.alert_type = "danger"
            self.normalization_fit_params_alert.visible = True
            return

        q_all = np.asarray(q_all, dtype=float)
        y_all = np.asarray(y_all, dtype=float)
        finite = np.isfinite(q_all) & np.isfinite(y_all)
        q_all = q_all[finite]
        y_all = y_all[finite]
        if q_all.size < 5:
            self.normalization_fit_params_alert.object = "Not enough finite points in vanadium qdat to suggest parameters."
            self.normalization_fit_params_alert.alert_type = "warning"
            self.normalization_fit_params_alert.visible = True
            return

        order = np.argsort(q_all)
        q_sorted = q_all[order]
        y_sorted = y_all[order]

        q_min = float(np.nanmin(q_sorted))
        q_max = float(np.nanmax(q_sorted))
        if not np.isfinite(q_min) or not np.isfinite(q_max) or q_max <= q_min:
            self.normalization_fit_params_alert.object = "Invalid Q range; cannot suggest parameters."
            self.normalization_fit_params_alert.alert_type = "warning"
            self.normalization_fit_params_alert.visible = True
            return

        f = float(self._NORMALIZATION_FIT_PLATEAU_FRACTION)
        q_span = q_max - q_min
        q_low_max = q_min + f * q_span
        q_high_min = q_max - f * q_span

        low_mask = q_sorted <= q_low_max
        high_mask = q_sorted >= q_high_min
        if int(np.sum(low_mask)) < 3 or int(np.sum(high_mask)) < 3:
            self.normalization_fit_params_alert.object = (
                "Not enough points in the low/high-Q plateau regions to build a robust initial guess."
            )
            self.normalization_fit_params_alert.alert_type = "warning"
            self.normalization_fit_params_alert.visible = True

        lowQ_est = float(np.nanmedian(y_sorted[low_mask])) if int(np.sum(low_mask)) else float(np.nanmedian(y_sorted))
        highQ_est = float(np.nanmedian(y_sorted[high_mask])) if int(np.sum(high_mask)) else float(np.nanmedian(y_sorted))
        if not np.isfinite(lowQ_est) or not np.isfinite(highQ_est):
            self.normalization_fit_params_alert.object = "Could not estimate plateau levels from data."
            self.normalization_fit_params_alert.alert_type = "warning"
            self.normalization_fit_params_alert.visible = True
            return

        # Initial guess policy (updated): use the absolute midpoint in Q for Q0 and quarter-span for dQ.
        deltaQ = float(q_max - q_min)
        Q0_est = float(0.5 * (q_min + q_max))
        dQ_est = max(1e-3, float(deltaQ) / 4.0)

        pinned_A = bool(getattr(getattr(self, "normalization_fit_params_A_pinned", None), "value", True))

        def _r2(value: float) -> float:
            v = float(value)
            # Keep very small bounds readable/valid (e.g. 1e-3) instead of rounding to 0.00.
            if v != 0.0 and abs(v) < 0.01:
                return v
            return float(round(v, 2))

        self._suspend_normalization_events = True
        try:
            # Polynomial initial guess (confirmed).
            if hasattr(self, "normalization_fit_params_a0_value"):
                self.normalization_fit_params_a0_value.value = _r2(1.0)
            if hasattr(self, "normalization_fit_params_a1_value"):
                self.normalization_fit_params_a1_value.value = _r2(0.0)
            if hasattr(self, "normalization_fit_params_a2_value"):
                self.normalization_fit_params_a2_value.value = _r2(0.0)

            # Inelastic params from plateaus/crossings.
            if hasattr(self, "normalization_fit_params_lowQ_value"):
                self.normalization_fit_params_lowQ_value.value = _r2(lowQ_est)
            if hasattr(self, "normalization_fit_params_Q0_value"):
                self.normalization_fit_params_Q0_value.value = _r2(Q0_est)
            if hasattr(self, "normalization_fit_params_dQ_value"):
                self.normalization_fit_params_dQ_value.value = _r2(dQ_est)

            # A stays at 51 even when unpinned (confirmed).
            if hasattr(self, "normalization_fit_params_A_value"):
                self.normalization_fit_params_A_value.value = _r2(51.0)

            # Suggested bounds (defaults confirmed).
            bound_wide = 1e6
            for key in ("a0", "a1", "a2"):
                getattr(self, f"normalization_fit_params_{key}_min").value = _r2(-bound_wide)
                getattr(self, f"normalization_fit_params_{key}_max").value = _r2(bound_wide)

            if pinned_A:
                self.normalization_fit_params_A_min.value = _r2(51.0)
                self.normalization_fit_params_A_max.value = _r2(51.0)
            else:
                self.normalization_fit_params_A_min.value = _r2(1.0)
                self.normalization_fit_params_A_max.value = _r2(300.0)

            self.normalization_fit_params_lowQ_min.value = _r2(0.0)
            self.normalization_fit_params_lowQ_max.value = _r2(bound_wide)

            self.normalization_fit_params_Q0_min.value = _r2(q_min)
            self.normalization_fit_params_Q0_max.value = _r2(q_max)

            self.normalization_fit_params_dQ_min.value = _r2(1e-3)
            self.normalization_fit_params_dQ_max.value = _r2(max(1e-3, float(q_max - q_min)))
        finally:
            self._suspend_normalization_events = False

        self._apply_normalization_fit_params_A_pinned_state()
        self._persist_normalization_fit_params_to_context()

        current_snap = self._normalization_fit_params_snapshot_fit_relevant()
        last_seen = getattr(self, "_normalization_fit_last_seen_params_snapshot", None)
        if not isinstance(last_seen, dict):
            self._normalization_fit_last_seen_params_snapshot = current_snap
        elif last_seen != current_snap:
            self._normalization_fit_last_seen_params_snapshot = current_snap
            if self._normalization_current_last_fit() is not None:
                self._invalidate_normalization_fit_result(reason="fit_params_changed")
        if hasattr(self, "_show_success_toast"):
            self._show_success_toast("Suggested initial fit parameters from vanadium data.")

    def _schedule_normalization_fit_data_plot_refresh(self, *, delay_ms: int = 75) -> None:
        if self.current_project_state is None:
            return
        if not hasattr(self, "_refresh_normalization_fit_data_placeholder"):
            return

        doc = getattr(pn.state, "curdoc", None)
        if doc is None:
            self._refresh_normalization_fit_data_placeholder()
            return

        handle = getattr(self, "_normalization_fit_data_refresh_handle", None)
        if handle is not None:
            try:
                doc.remove_timeout_callback(handle)
            except Exception:
                pass
            self._normalization_fit_data_refresh_handle = None

        def _run() -> None:
            self._normalization_fit_data_refresh_handle = None
            self._refresh_normalization_fit_data_placeholder()

        try:
            self._normalization_fit_data_refresh_handle = doc.add_timeout_callback(_run, int(delay_ms))
        except Exception:
            self._normalization_fit_data_refresh_handle = None
            self._refresh_normalization_fit_data_placeholder()

    def _sync_normalization_fit_data_slider_limits(self, *, q_all: np.ndarray, y_all: np.ndarray) -> None:
        q_all = np.asarray(q_all, dtype=float)
        y_all = np.asarray(y_all, dtype=float)
        q_finite = q_all[np.isfinite(q_all)]
        y_finite = y_all[np.isfinite(y_all)]
        if q_finite.size == 0 or y_finite.size == 0:
            return

        q_min = float(np.nanmin(q_finite))
        q_max = float(np.nanmax(q_finite))
        if q_max <= q_min:
            return

        y_min = float(np.nanmin(y_finite))
        y_max = float(np.nanmax(y_finite))
        if not np.isfinite(y_min) or not np.isfinite(y_max) or y_max <= y_min:
            y_min, y_max = 0.0, 1.0

        def _nice_step(span: float, *, approx_steps: float, min_step: float) -> float:
            if not np.isfinite(span) or span <= 0:
                return min_step
            raw = max(span / max(approx_steps, 1.0), min_step)
            # round to 1-2 significant digits
            exp = np.floor(np.log10(raw))
            base = raw / (10**exp)
            if base <= 1:
                nice = 1
            elif base <= 2:
                nice = 2
            elif base <= 5:
                nice = 5
            else:
                nice = 10
            return float(nice * (10**exp))

        q_step = _nice_step(q_max - q_min, approx_steps=250, min_step=0.001)
        # Intensity spans can be large; use a finer default step so sliders feel responsive.
        y_step = _nice_step(y_max - y_min, approx_steps=1200, min_step=1.0)

        pairs = [
            ("normalization_fit_data_q_tail_low", "normalization_fit_data_q_tail_low_slider"),
            ("normalization_fit_data_q_tail_high", "normalization_fit_data_q_tail_high_slider"),
            ("normalization_fit_data_q_min", "normalization_fit_data_q_min_slider"),
            ("normalization_fit_data_q_max", "normalization_fit_data_q_max_slider"),
            ("normalization_fit_data_y_min", "normalization_fit_data_y_min_slider"),
            ("normalization_fit_data_y_max", "normalization_fit_data_y_max_slider"),
        ]

        self._suspend_normalization_events = True
        try:
            for input_name, slider_name in pairs:
                if not hasattr(self, slider_name):
                    continue
                slider = getattr(self, slider_name)
                if any(
                    token in slider_name
                    for token in (
                        "_q_tail_low_slider",
                        "_q_tail_high_slider",
                        "_q_min_slider",
                        "_q_max_slider",
                        "_redesign_q_start_slider",
                        "_redesign_q_end_slider",
                    )
                ):
                    slider.start = q_min
                    slider.end = q_max
                    slider.step = q_step
                else:
                    slider.start = y_min
                    slider.end = y_max
                    slider.step = y_step

                try:
                    clipped = float(np.clip(float(slider.value), float(slider.start), float(slider.end)))
                    slider.value = clipped
                    if hasattr(self, input_name):
                        getattr(self, input_name).value = clipped
                except Exception:
                    continue

            vertical_range = getattr(self, "normalization_fit_data_redesign_vertical_range_slider", None)
            if vertical_range is not None:
                mode = self._normalize_normalization_fit_data_mode(
                    getattr(getattr(self, "normalization_fit_data_selection_mode", None), "value", "")
                )
                manual_mode = self._is_normalization_fit_data_manual_mode(mode)
                if manual_mode:
                    vertical_range.start = y_min
                    vertical_range.end = y_max
                    vertical_range.step = y_step
                    lower_value = float(
                        getattr(getattr(self, "normalization_fit_data_y_min", None), "value", y_min) or y_min
                    )
                    upper_value = float(
                        getattr(getattr(self, "normalization_fit_data_y_max", None), "value", y_max) or y_max
                    )
                    lower_value = float(np.clip(lower_value, y_min, y_max))
                    upper_value = float(np.clip(upper_value, lower_value, y_max))
                    self._set_normalization_range_value(vertical_range, (lower_value, upper_value))
                else:
                    min_pct = int(
                        getattr(getattr(self, "normalization_fit_data_min_percentile", None), "value", 0) or 0
                    )
                    max_pct = int(
                        getattr(getattr(self, "normalization_fit_data_max_percentile", None), "value", 100) or 100
                    )
                    min_pct = int(np.clip(min_pct, 0, 100))
                    max_pct = int(np.clip(max_pct, min_pct, 100))
                    vertical_range.start = 0
                    vertical_range.end = 100
                    vertical_range.step = 1
                    self._set_normalization_range_value(vertical_range, (min_pct, max_pct))

            q_range = getattr(self, "normalization_fit_data_redesign_q_range_slider", None)
            if q_range is not None:
                q_range.start = q_min
                q_range.end = q_max
                q_range.step = q_step
                q_start = float(getattr(getattr(self, "normalization_fit_data_q_tail_low", None), "value", q_min) or q_min)
                q_end = float(getattr(getattr(self, "normalization_fit_data_q_tail_high", None), "value", q_max) or q_max)
                q_start = float(np.clip(q_start, q_min, q_max))
                q_end = float(np.clip(q_end, q_start, q_max))
                self._set_normalization_range_value(q_range, (q_start, q_end))
        finally:
            self._suspend_normalization_events = False

    def _read_xye_cached(self, path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        cache = getattr(self, "_xye_cache", None)
        if not isinstance(cache, dict):
            cache = {}
            self._xye_cache = cache

        try:
            stat = path.stat()
            mtime_ns = int(getattr(stat, "st_mtime_ns", int(stat.st_mtime * 1e9)))
            size = int(stat.st_size)
        except Exception:
            mtime_ns = -1
            size = -1

        key = str(path.resolve(strict=False))
        hit = cache.get(key)
        if (
            isinstance(hit, dict)
            and hit.get("mtime_ns") == mtime_ns
            and hit.get("size") == size
            and isinstance(hit.get("q"), np.ndarray)
            and isinstance(hit.get("y"), np.ndarray)
            and isinstance(hit.get("e"), np.ndarray)
        ):
            return hit["q"], hit["y"], hit["e"]

        q_all, y_all, e_all = read_xye(str(path))
        cache[key] = {
            "mtime_ns": mtime_ns,
            "size": size,
            "q": np.asarray(q_all, dtype=float),
            "y": np.asarray(y_all, dtype=float),
            "e": np.asarray(e_all, dtype=float),
        }
        return cache[key]["q"], cache[key]["y"], cache[key]["e"]

    @contextmanager
    def _working_directory(self, target: Path):
        original = Path(getcwd())
        chdir(str(target))
        try:
            yield
        finally:
            chdir(str(original))

    def _normalization_self_fit_series_for_context(self) -> dict[str, object] | None:
        fit = self._normalization_current_last_fit() or {}
        series = fit.get("series") if isinstance(fit, dict) else None
        if isinstance(series, dict) and series.get("q") is not None and series.get("norpoly") is not None:
            return series  # type: ignore[return-value]
        exported = getattr(self, "_normalization_last_exported", None)
        if isinstance(exported, dict):
            series = exported.get("series")
            if isinstance(series, dict) and series.get("q") is not None and series.get("norpoly") is not None:
                return series  # type: ignore[return-value]
        return None

    def _load_normalization_context_payload(self) -> dict[str, object] | None:
        if self.current_project_root is None or self.current_project_state is None:
            return None
        if not hasattr(self, "_selected_normalization_manifest_ref"):
            return None
        manifest_ref = str(self._selected_normalization_manifest_ref() or "").strip()
        if not manifest_ref:
            return None
        payload = load_context_manifest(self.current_project_root, manifest_ref)
        return payload if isinstance(payload, dict) else None

    def _load_measurement_for_normalization_context(self, payload: dict[str, object]) -> object | None:
        if self.current_project_root is None:
            return None
        sample = payload.get("sample")
        if not isinstance(sample, dict):
            return None
        artifact_ref = sample.get("measurement_artifact")
        if not isinstance(artifact_ref, str) or not artifact_ref.strip():
            return None
        try:
            artifact_path = resolve_project_path(self.current_project_root, artifact_ref)
        except Exception:
            return None
        if not artifact_path.exists() or not artifact_path.is_file():
            return None
        loaded: object
        try:
            if artifact_path.suffix.lower() == ".pkl":
                with artifact_path.open("rb") as handle:
                    loaded = pickle.load(handle)
            else:
                loaded = json.loads(artifact_path.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            return None

        if hasattr(loaded, "OuterDiam") and hasattr(loaded, "EffAtomicDensity"):
            return loaded

        # Some artifacts store raw params dicts; rebuild Measurement in the `.par` directory
        # to ensure relative paths resolve deterministically.
        if not isinstance(loaded, dict):
            return loaded

        par_ref = sample.get("par_path_rel") if isinstance(sample.get("par_path_rel"), str) else sample.get("par_path")
        if not isinstance(par_ref, str) or not par_ref.strip():
            return None
        try:
            par_path = resolve_project_path(self.current_project_root, par_ref)
        except Exception:
            return None
        base_dir = par_path.parent if par_path.parent.exists() else self.current_project_root

        try:
            from toscana.experiment.measurement import Measurement
        except Exception:
            return None
        try:
            with self._working_directory(base_dir):
                return Measurement(loaded)
        except Exception:
            return None

    @staticmethod
    def _sanitize_export_filename_stem(value: str) -> str:
        import re

        invalid = r'<>:"/\\|?*'
        cleaned = re.sub(f"[{re.escape(invalid)}]", "", str(value or "")).strip()
        cleaned = cleaned.strip().rstrip(" .")
        if not cleaned:
            return "sample"
        cleaned = re.sub(r"\s+", "_", cleaned)
        return cleaned[:120]

    def _compute_sample_normalization_series(self) -> dict[str, object]:
        """
        Compute dsdo (differential cross section per atom) for the selected context.

        Returns a dict containing the computed arrays plus metadata suitable for plotting/export.
        Raises on invalid/missing prerequisites.
        """
        if self.current_project_root is None or self.current_project_state is None:
            raise RuntimeError("Open a project first.")

        payload = self._load_normalization_context_payload()
        if not isinstance(payload, dict):
            raise RuntimeError("Select a background context first.")

        artifacts = payload.get("artifacts") if isinstance(payload.get("artifacts"), dict) else {}
        sample_ref = artifacts.get("sample_sub_qdat") if isinstance(artifacts.get("sample_sub_qdat"), str) else None
        if not isinstance(sample_ref, str) or not sample_ref.strip():
            raise RuntimeError("Selected context has no `sample_sub_qdat` reference.")
        sample_path = resolve_project_path(self.current_project_root, sample_ref)
        if not sample_path.exists():
            raise RuntimeError(f"Missing sample qdat: `{sample_path}`")

        measurement = self._load_measurement_for_normalization_context(payload)
        if measurement is None:
            raise RuntimeError(
                "Could not load the measurement artifact for this context. "
                "Re-extract the sample in Background and re-export the context."
            )

        series = self._normalization_self_fit_series_for_context()
        if not isinstance(series, dict):
            raise RuntimeError("No vanadium self-fit is available yet. Run Fit and/or export the self-fit qdat.")

        q_fit = np.asarray(series.get("q"), dtype=float)
        norpoly_fit = np.asarray(series.get("norpoly"), dtype=float)
        norsigm0 = series.get("norsigm0")
        if norsigm0 is None or not np.isfinite(float(norsigm0)) or float(norsigm0) == 0.0:
            raise RuntimeError("Vanadium self-fit is missing `norsigm0`. Rerun the fit.")
        norsigm0_f = float(norsigm0)

        q_s, y_s, e_s = self._read_xye_cached(sample_path)
        q_s = np.asarray(q_s, dtype=float)
        y_s = np.asarray(y_s, dtype=float)
        e_s = np.asarray(e_s, dtype=float)
        finite = np.isfinite(q_s) & np.isfinite(y_s)
        q_s = q_s[finite]
        y_s = y_s[finite]
        e_s = e_s[finite] if e_s.shape[0] == finite.shape[0] else np.zeros_like(y_s, dtype=float)

        if q_s.size == 0:
            raise RuntimeError("Sample qdat contains no finite points.")

        # Interpolate norpoly onto the sample q grid (deterministic alignment).
        q_fit = np.asarray(q_fit, dtype=float)
        norpoly_fit = np.asarray(norpoly_fit, dtype=float)
        finite_fit = np.isfinite(q_fit) & np.isfinite(norpoly_fit)
        q_fit = q_fit[finite_fit]
        norpoly_fit = norpoly_fit[finite_fit]
        if q_fit.size < 2:
            raise RuntimeError("Vanadium self-fit has insufficient points to normalize.")
        order_fit = np.argsort(q_fit)
        q_fit = q_fit[order_fit]
        norpoly_fit = norpoly_fit[order_fit]

        norpoly_on_sample = np.interp(q_s, q_fit, norpoly_fit, left=np.nan, right=np.nan)
        if not np.any(np.isfinite(norpoly_on_sample)):
            raise RuntimeError("Vanadium self-fit grid does not overlap the sample q grid.")

        # Compute the normalization factor from the Measurement geometry / densities.
        from math import pi

        from toscana.isotopes.core import elemento
        from toscana.physics.geometry import getCylVolume
        from toscana.physics.properties import getAtomicDensity

        outer_diam = float(getattr(measurement, "OuterDiam", 0.0) or 0.0)
        beam_height = float(getattr(measurement, "beamHeight", 0.0) or 0.0)
        eff_atomic_density = float(getattr(measurement, "EffAtomicDensity", 0.0) or 0.0)
        normaliser = getattr(measurement, "normaliser", None)

        if not np.isfinite(outer_diam) or outer_diam <= 0:
            raise RuntimeError("Sample OuterDiam is missing or invalid in the measurement.")
        if not np.isfinite(beam_height) or beam_height <= 0:
            raise RuntimeError("Sample beamHeight is missing or invalid in the measurement.")
        if not np.isfinite(eff_atomic_density) or eff_atomic_density <= 0:
            raise RuntimeError("Sample EffAtomicDensity is missing or invalid in the measurement.")
        if not isinstance(normaliser, (tuple, list)) or len(normaliser) < 4:
            raise RuntimeError("Sample normaliser geometry is missing in the measurement.")

        volume_in_beam_cm3 = float(getCylVolume(diameter=outer_diam, height=beam_height)) / 1000.0
        atoms_in_beam = volume_in_beam_cm3 * 1.0e24 * eff_atomic_density

        nor_density = 6.11  # g/cm3 (vanadium density)
        nor_atomic_density = float(getAtomicDensity(density=nor_density, molarMass=float(elemento("V").weight)))
        nor_diam = float(normaliser[3])
        nor_volume_cm3 = float(getCylVolume(diameter=nor_diam, height=beam_height)) / 1000.0
        nor_atoms_in_beam = nor_volume_cm3 * 1.0e24 * nor_atomic_density

        if not np.isfinite(atoms_in_beam) or atoms_in_beam <= 0:
            raise RuntimeError("Computed AtomsInBeam is invalid.")
        if not np.isfinite(nor_atoms_in_beam) or nor_atoms_in_beam <= 0:
            raise RuntimeError("Computed norAtomsInBeam is invalid.")

        norfactor = float(elemento("V").sig_sca) / (4.0 * float(pi)) * (nor_atoms_in_beam / atoms_in_beam) / norsigm0_f

        with np.errstate(divide="ignore", invalid="ignore"):
            dsdo_y = norfactor * y_s / norpoly_on_sample
            dsdo_e = norfactor * e_s / norpoly_on_sample

        return {
            "q": q_s,
            "dsdo_y": dsdo_y,
            "dsdo_e": dsdo_e,
            "norfactor": float(norfactor),
            "sample_qdat": sample_path,
            "measurement": measurement,
        }

    def _refresh_normalization_sample_normalization_plot(self) -> None:
        if not hasattr(self, "normalization_sample_norm_plot_pane"):
            return
        if self.current_project_root is None or self.current_project_state is None:
            self.normalization_sample_norm_plot_pane.object = None
            if hasattr(self, "_show_toast_once"):
                self._show_toast_once(
                    "normalization:sample_norm_status",
                    level="info",
                    message="Open a project first.",
                )
            return

        try:
            payload = self._load_normalization_context_payload()
            context_id = str(getattr(getattr(self, "normalization_context_select", None), "value", "") or "").strip()
            token = str(self.current_project_root)
            series = self._compute_sample_normalization_series()
            q = np.asarray(series["q"], dtype=float)
            dsdo_y = np.asarray(series["dsdo_y"], dtype=float)

            title = None
            if isinstance(payload, dict):
                sample = payload.get("sample") if isinstance(payload.get("sample"), dict) else {}
                title_raw = sample.get("title") if isinstance(sample.get("title"), str) else None
                if title_raw:
                    title = f"Differential cross section for {title_raw}"

            fig = (
                self.normalization_sample_norm_plot_pane.object
                if getattr(self.normalization_sample_norm_plot_pane, "object", None) is not None
                else None
            )
            if fig is None:
                fig = build_sample_normalization_figure(q=q, dsdo=dsdo_y, title=title, width=800, height=600)
            else:
                update_sample_normalization_figure(fig, q=q, dsdo=dsdo_y, title=title, width=800, height=600)

            self.normalization_sample_norm_plot_pane.object = fig
            self.normalization_sample_norm_plot_pane.param.trigger("object")
            if hasattr(self, "_show_toast_once"):
                self._show_toast_once(
                    "normalization:sample_norm_status",
                    level="success",
                    message="Sample normalization ready.",
                )

            self._normalization_last_sample_norm = {
                "project_root": token,
                "context_id": context_id,
                "series": {
                    "q": q,
                    "dsdo_y": dsdo_y,
                    "dsdo_e": np.asarray(series["dsdo_e"], dtype=float),
                    "norfactor": float(series["norfactor"]),
                },
                "sample_qdat": str(Path(series["sample_qdat"]).resolve(strict=False)),
            }
        except Exception as exc:
            self.normalization_sample_norm_plot_pane.object = None
            if hasattr(self, "_show_toast_once"):
                self._show_toast_once(
                    "normalization:sample_norm_status",
                    level="warning",
                    message=f"Sample normalization not ready: {exc}",
                )
            self._normalization_last_sample_norm = None

        if hasattr(self, "_refresh_normalization_sample_norm_button_states"):
            self._refresh_normalization_sample_norm_button_states()

    def _persist_normalization_fit_data_selection_to_context(self) -> None:
        if self.current_project_root is None or self.current_project_state is None:
            return
        if getattr(self, "_suspend_normalization_events", False):
            return
        if not hasattr(self, "normalization_fit_data_selection_mode"):
            return

        context_id = str(getattr(getattr(self, "normalization_context_select", None), "value", "") or "").strip()
        if not context_id:
            return

        manifest_ref = ""
        if hasattr(self, "_selected_normalization_manifest_ref"):
            manifest_ref = str(self._selected_normalization_manifest_ref() or "").strip()
        if not manifest_ref:
            return

        payload = load_context_manifest(self.current_project_root, manifest_ref)
        if not isinstance(payload, dict):
            return

        mode = self._normalize_normalization_fit_data_mode(
            getattr(self.normalization_fit_data_selection_mode, "value", "")
        )
        selection: dict[str, object] = {"mode": mode}
        if hasattr(self, "normalization_fit_data_use_sliders"):
            selection["use_sliders"] = bool(getattr(self.normalization_fit_data_use_sliders, "value", False))
        if self._is_normalization_fit_data_manual_mode(mode):
            selection["q_min"] = float(getattr(self.normalization_fit_data_q_min, "value", 0.0) or 0.0)
            selection["q_max"] = float(getattr(self.normalization_fit_data_q_max, "value", 0.0) or 0.0)
            selection["y_min"] = float(getattr(self.normalization_fit_data_y_min, "value", 0.0) or 0.0)
            selection["y_max"] = float(getattr(self.normalization_fit_data_y_max, "value", 0.0) or 0.0)
        else:
            selection["q_tail_low"] = float(getattr(self.normalization_fit_data_q_tail_low, "value", 0.0) or 0.0)
            selection["q_tail_high"] = float(
                getattr(self.normalization_fit_data_q_tail_high, "value", 0.0) or 0.0
            )
            selection["min_percentile"] = int(getattr(self.normalization_fit_data_min_percentile, "value", 0) or 0)
            selection["max_percentile"] = int(getattr(self.normalization_fit_data_max_percentile, "value", 0) or 0)

        decisions = payload.get("decisions") if isinstance(payload.get("decisions"), dict) else {}
        normalization = decisions.get("normalization") if isinstance(decisions.get("normalization"), dict) else {}
        normalization["vanadium_fit_data_selection"] = selection
        decisions["normalization"] = normalization
        payload["decisions"] = decisions

        target_context_id = str(payload.get("context_id") or context_id).strip() or context_id
        try:
            write_context_manifest(self.current_project_root, context_id=target_context_id, payload=payload)
        except Exception:
            return

    def _apply_normalization_fit_params_A_pinned_state(self) -> None:
        if not hasattr(self, "normalization_fit_params_A_pinned"):
            return
        pinned = bool(getattr(self.normalization_fit_params_A_pinned, "value", True))
        for attr in ("normalization_fit_params_A_value", "normalization_fit_params_A_min", "normalization_fit_params_A_max"):
            if hasattr(self, attr):
                getattr(self, attr).disabled = pinned

        if not pinned:
            return

        # When pinned, A is fixed at 51 (value and bounds).
        self._suspend_normalization_events = True
        try:
            if hasattr(self, "normalization_fit_params_A_value"):
                self.normalization_fit_params_A_value.value = 51.0
            if hasattr(self, "normalization_fit_params_A_min"):
                self.normalization_fit_params_A_min.value = 51.0
            if hasattr(self, "normalization_fit_params_A_max"):
                self.normalization_fit_params_A_max.value = 51.0
        finally:
            self._suspend_normalization_events = False

    def _persist_normalization_fit_params_to_context(self) -> None:
        if self.current_project_root is None or self.current_project_state is None:
            return
        if getattr(self, "_suspend_normalization_events", False):
            return
        if not hasattr(self, "normalization_fit_params_A_pinned"):
            return

        context_id = str(getattr(getattr(self, "normalization_context_select", None), "value", "") or "").strip()
        if not context_id:
            return

        manifest_ref = ""
        if hasattr(self, "_selected_normalization_manifest_ref"):
            manifest_ref = str(self._selected_normalization_manifest_ref() or "").strip()
        if not manifest_ref:
            return

        payload = load_context_manifest(self.current_project_root, manifest_ref)
        if not isinstance(payload, dict):
            return

        def _read_float(name: str, fallback: float) -> float:
            widget = getattr(self, name, None)
            value = getattr(widget, "value", fallback) if widget is not None else fallback
            try:
                return float(value)
            except Exception:
                return float(fallback)

        params: dict[str, dict[str, float]] = {}
        for key in ("a0", "a1", "a2", "A", "lowQ", "Q0", "dQ"):
            params[key] = {
                "value": _read_float(f"normalization_fit_params_{key}_value", 0.0),
                "min": _read_float(f"normalization_fit_params_{key}_min", -1e6),
                "max": _read_float(f"normalization_fit_params_{key}_max", 1e6),
            }

        fit_payload: dict[str, object] = {
            "pinned_A": bool(getattr(self.normalization_fit_params_A_pinned, "value", True)),
            "params": params,
        }

        decisions = payload.get("decisions") if isinstance(payload.get("decisions"), dict) else {}
        normalization = decisions.get("normalization") if isinstance(decisions.get("normalization"), dict) else {}
        normalization["vanadium_fit_params"] = fit_payload
        decisions["normalization"] = normalization
        payload["decisions"] = decisions

        target_context_id = str(payload.get("context_id") or context_id).strip() or context_id
        try:
            write_context_manifest(self.current_project_root, context_id=target_context_id, payload=payload)
        except Exception:
            return

        # Do not overwrite the Fit/Stable/Stale status line here.
        # Fit-relevant changes are handled by the stale detection pipeline.

    def _load_normalization_fit_params_from_context(self) -> None:
        if self.current_project_root is None or self.current_project_state is None:
            return
        if not hasattr(self, "normalization_fit_params_A_pinned"):
            return

        context_id = str(getattr(getattr(self, "normalization_context_select", None), "value", "") or "").strip()
        if not context_id:
            self._set_normalization_fit_params_status("Select a background context to configure fit parameters.")
            return

        manifest_ref = ""
        if hasattr(self, "_selected_normalization_manifest_ref"):
            manifest_ref = str(self._selected_normalization_manifest_ref() or "").strip()
        if not manifest_ref:
            return

        payload = load_context_manifest(self.current_project_root, manifest_ref)
        if not isinstance(payload, dict):
            return

        decisions = payload.get("decisions") if isinstance(payload.get("decisions"), dict) else {}
        normalization = decisions.get("normalization") if isinstance(decisions.get("normalization"), dict) else {}
        fit_payload = normalization.get("vanadium_fit_params")
        if not isinstance(fit_payload, dict):
            self._apply_normalization_fit_params_A_pinned_state()
            self._load_normalization_fit_params_exported_result()
            return

        params = fit_payload.get("params")
        if not isinstance(params, dict):
            self._apply_normalization_fit_params_A_pinned_state()
            self._load_normalization_fit_params_exported_result()
            return

        self._suspend_normalization_events = True
        try:
            pinned_A = bool(fit_payload.get("pinned_A", True))
            self.normalization_fit_params_A_pinned.value = pinned_A

            for key in ("a0", "a1", "a2", "A", "lowQ", "Q0", "dQ"):
                block = params.get(key)
                if not isinstance(block, dict):
                    continue
                for field in ("value", "min", "max"):
                    widget_name = f"normalization_fit_params_{key}_{field}"
                    if hasattr(self, widget_name) and isinstance(block.get(field), (int, float)):
                        v = float(block[field])
                        if v != 0.0 and abs(v) < 0.01:
                            getattr(self, widget_name).value = v
                        else:
                            getattr(self, widget_name).value = float(round(v, 2))
        finally:
            self._suspend_normalization_events = False

        self._apply_normalization_fit_params_A_pinned_state()
        self._set_normalization_fit_params_status("Fit parameters loaded.")

        if hasattr(self, "_refresh_normalization_fit_params_button_states"):
            self._refresh_normalization_fit_params_button_states()

        # Best-effort: if an exported self-fit exists for this context, load it for display.
        self._load_normalization_fit_params_exported_result()

    def _load_normalization_fit_last_from_context(self) -> None:
        if self.current_project_root is None or self.current_project_state is None:
            return
        context_id = str(getattr(getattr(self, "normalization_context_select", None), "value", "") or "").strip()
        if not context_id:
            return
        manifest_ref = (
            str(self._selected_normalization_manifest_ref() or "").strip()
            if hasattr(self, "_selected_normalization_manifest_ref")
            else ""
        )
        if not manifest_ref:
            return
        payload = load_context_manifest(self.current_project_root, manifest_ref)
        if not isinstance(payload, dict):
            return

        decisions = payload.get("decisions") if isinstance(payload.get("decisions"), dict) else {}
        normalization = decisions.get("normalization") if isinstance(decisions.get("normalization"), dict) else {}
        last_fit = normalization.get("vanadium_fit_last")
        if not isinstance(last_fit, dict):
            return

        popt = last_fit.get("popt")
        perr = last_fit.get("perr")
        if not isinstance(popt, list) or not isinstance(perr, list) or len(popt) != 7 or len(perr) != 7:
            return

        project_token = str(getattr(self, "current_project_root", "") or "")
        self._normalization_last_fit = {
            "context_id": context_id,
            "project_root": project_token,
            "computed_at": str(last_fit.get("computed_at") or ""),
            "popt": [float(v) for v in popt],
            "perr": [float(v) for v in perr],
            "n_points": int(last_fit.get("n_points") or 0),
            "warning": last_fit.get("warning"),
            "sigma_warning": last_fit.get("sigma_warning"),
            "selection_snapshot": last_fit.get("selection_snapshot") if isinstance(last_fit.get("selection_snapshot"), dict) else None,
            "params_snapshot": last_fit.get("params_snapshot") if isinstance(last_fit.get("params_snapshot"), dict) else None,
        }

        # Rebuild plot series from vanadium_sub_qdat (do not persist raw series).
        artifacts = payload.get("artifacts") if isinstance(payload.get("artifacts"), dict) else {}
        van_ref = artifacts.get("vanadium_sub_qdat") if isinstance(artifacts.get("vanadium_sub_qdat"), str) else None
        if isinstance(van_ref, str) and van_ref.strip():
            try:
                van_path = resolve_project_path(self.current_project_root, van_ref)
                if van_path.exists():
                    q_all, y_all, _e_all = self._read_xye_cached(van_path)
                    q_all_f = np.asarray(q_all, dtype=float)
                    y_all_f = np.asarray(y_all, dtype=float)
                    finite_all = np.isfinite(q_all_f) & np.isfinite(y_all_f)
                    q_all_f = q_all_f[finite_all]
                    y_all_f = y_all_f[finite_all]
                    order = np.argsort(q_all_f)
                    q_sorted = q_all_f[order]
                    y_sorted = y_all_f[order]

                    from toscana.models.scattering import vanaQdep

                    popt_arr = np.asarray(self._normalization_last_fit.get("popt"), dtype=float)
                    norSelf = vanaQdep(q_sorted, *popt_arr)
                    norsigm = vanaQdep(
                        q_sorted,
                        1.0,
                        0.0,
                        0.0,
                        float(popt_arr[3]),
                        float(popt_arr[4]),
                        float(popt_arr[5]),
                        float(popt_arr[6]),
                    )
                    norsigm0 = float(
                        vanaQdep(
                            0.0,
                            1.0,
                            0.0,
                            0.0,
                            float(popt_arr[3]),
                            float(popt_arr[4]),
                            float(popt_arr[5]),
                            float(popt_arr[6]),
                        )
                    )
                    with np.errstate(divide="ignore", invalid="ignore"):
                        norpoly = np.where(norsigm != 0, norSelf / norsigm, np.nan)

                    self._normalization_last_fit["series"] = {
                        "q": q_sorted,
                        "y": y_sorted,
                        "norSelf": norSelf,
                        "norsigm": norsigm,
                        "norpoly": norpoly,
                        "norsigm0": norsigm0,
                    }
            except Exception:
                pass

        # Render a results markdown matching the in-app fit output.
        results_pane = getattr(self, "normalization_fit_params_results", None)
        if results_pane is not None:
            try:
                names = ["a0", "a1", "a2", "A", "lowQ", "Q0", "dQ"]
                rows = ["| Param | Value | Â± |", "|---|---:|---:|"]
                for name, v, e in zip(
                    names,
                    self._normalization_last_fit.get("popt") or [],
                    self._normalization_last_fit.get("perr") or [],
                    strict=False,
                ):
                    rows.append(f"| {name} | {float(v):.6g} | {float(e):.3g} |")
                notes: list[str] = []
                warning = self._normalization_last_fit.get("warning")
                sigma_warning = self._normalization_last_fit.get("sigma_warning")
                if warning:
                    notes.append(f"- Window warning: {warning}")
                if sigma_warning:
                    notes.append(f"- Sigma: {sigma_warning}")
                n_points = int(self._normalization_last_fit.get("n_points") or 0)
                results_pane.object = "\n".join(["### Fit result", "", f"Selected points: **{n_points}**", "", *rows, "", *notes])
            except Exception:
                pass

        stale = self._normalization_fit_is_stale(self._normalization_last_fit)
        self._set_normalization_fit_params_status("Fit is stale. Run Fit again." if stale else "Fit complete.")

        # Keep snapshots in sync so UI-only toggles don't mark stale.
        self._normalization_fit_last_seen_selection_snapshot = self._normalization_fit_data_selection_snapshot_fit_relevant()
        self._normalization_fit_last_seen_params_snapshot = self._normalization_fit_params_snapshot_fit_relevant()

        try:
            self._refresh_normalization_fit_params_plot()
        except Exception:
            pass
        try:
            self._refresh_normalization_vanadium_self_fit_preview_fit_table()
        except Exception:
            pass
        if hasattr(self, "_refresh_normalization_fit_params_button_states"):
            try:
                self._refresh_normalization_fit_params_button_states()
            except Exception:
                pass

    def _refresh_normalization_fit_params_button_states(self) -> None:
        if not hasattr(self, "normalization_fit_params_suggest_button"):
            return
        can_suggest = self._normalization_fit_params_can_suggest()
        self.normalization_fit_params_suggest_button.disabled = not bool(can_suggest) or bool(
            getattr(self, "operation_in_progress", False)
        )
        if hasattr(self, "normalization_fit_params_run_button"):
            self.normalization_fit_params_run_button.disabled = not bool(can_suggest) or bool(
                getattr(self, "operation_in_progress", False)
            )
        if hasattr(self, "normalization_fit_params_export_button"):
            last_fit = self._normalization_current_last_fit()
            can_export = bool(can_suggest) and last_fit is not None and (not self._normalization_fit_is_stale(last_fit))
            self.normalization_fit_params_export_button.disabled = not can_export or bool(
                getattr(self, "operation_in_progress", False)
            )
        if hasattr(self, "normalization_fit_params_export_confirm_button"):
            self.normalization_fit_params_export_confirm_button.disabled = bool(
                getattr(self, "operation_in_progress", False)
            )
        if hasattr(self, "normalization_fit_params_export_cancel_button"):
            self.normalization_fit_params_export_cancel_button.disabled = bool(
                getattr(self, "operation_in_progress", False)
            )

    def _sync_normalization_fit_params_export_prompt_visibility(self) -> None:
        if not hasattr(self, "normalization_fit_params_export_prompt_card"):
            return
        visible = bool(getattr(getattr(self, "normalization_fit_params_export_prompt", None), "visible", False))
        self.normalization_fit_params_export_prompt_card.visible = visible

    def _prompt_normalization_fit_params_export(self, _event=None) -> None:
        if self.current_project_root is None or self.current_project_state is None:
            return
        if not hasattr(self, "normalization_fit_params_export_prompt"):
            return
        if bool(getattr(self.normalization_fit_params_export_prompt, "visible", False)):
            self.normalization_fit_params_export_prompt.visible = False
            self._sync_normalization_fit_params_export_prompt_visibility()
            return
        if self._normalization_current_last_fit() is None:
            self._show_warning_toast("Run a fit first to export the self-fit qdat.")
            return
        context_id = str(getattr(getattr(self, "normalization_context_select", None), "value", "") or "").strip()
        if not context_id:
            self._show_warning_toast("Select a background context first.")
            return

        target = self.current_project_root / "processed" / "normalization" / context_id / "vanadium_self_fit.qdat"
        rel_target = project_relpath(self.current_project_root, target)
        lines = [
            f"Export target: `{rel_target}`",
            "",
            "Proceeding will write (or overwrite) `vanadium_self_fit.qdat` for the selected context.\n",
        ]
        if target.exists():
            lines.append("Warning: the file already exists and will be overwritten.")
            self.normalization_fit_params_export_prompt.alert_type = "warning"
        else:
            self.normalization_fit_params_export_prompt.alert_type = "secondary"
        self.normalization_fit_params_export_prompt.object = "\n".join(lines)
        self.normalization_fit_params_export_prompt.visible = True
        self._sync_normalization_fit_params_export_prompt_visibility()

    def _cancel_normalization_fit_params_export(self, _event=None) -> None:
        if hasattr(self, "normalization_fit_params_export_prompt"):
            self.normalization_fit_params_export_prompt.visible = False
        self._sync_normalization_fit_params_export_prompt_visibility()

    def _confirm_normalization_fit_params_export(self, _event=None) -> None:
        self._perform_normalization_fit_params_export()

    def _perform_normalization_fit_params_export(self) -> None:
        if self.current_project_root is None or self.current_project_state is None:
            return
        if self._normalization_current_last_fit() is None:
            self._show_warning_toast("Run a fit first to export the self-fit qdat.")
            return
        context_id = str(getattr(getattr(self, "normalization_context_select", None), "value", "") or "").strip()
        if not context_id:
            self._show_warning_toast("Select a background context first.")
            return

        manifest_ref = str(self._selected_normalization_manifest_ref() or "").strip() if hasattr(self, "_selected_normalization_manifest_ref") else ""
        if not manifest_ref:
            self._show_warning_toast("Selected context has no manifest reference.")
            return

        payload = load_context_manifest(self.current_project_root, manifest_ref)
        artifacts = payload.get("artifacts") if isinstance(payload, dict) else {}
        van_ref = artifacts.get("vanadium_sub_qdat") if isinstance(artifacts, dict) else None
        if not isinstance(van_ref, str) or not van_ref.strip():
            self._show_warning_toast("Selected context has no `vanadium_sub_qdat` reference.")
            return

        try:
            van_path = resolve_project_path(self.current_project_root, van_ref)
        except Exception:
            self._show_warning_toast("Vanadium qdat reference could not be resolved.")
            return

        if not van_path.exists():
            self._show_warning_toast(f"Missing vanadium qdat: `{van_path}`")
            return

        # Record in run history (best-effort; don't break export in test harnesses).
        run_record = None
        try:
            from toscana_gui.persistence import OutputPaths, RunRecord

            run_id = None
            if hasattr(self, "_create_run_id"):
                try:
                    run_id = str(self._create_run_id())
                except Exception:
                    run_id = None
            run_id = run_id or datetime.now(tz=PARIS_TZ).strftime("%Y%m%d-%H%M%S")
            run_record = RunRecord(
                run_id=run_id,
                workflow="normalization_vanadium_self_fit_export",
                status="running",
                started_at=now_iso(),
                summary=f"Exporting vanadium self-fit qdat for context `{context_id}`",
                workflow_data={"context_id": context_id},
                output_paths=OutputPaths(generated_files=[]),
            )
            if hasattr(self.current_project_state, "runs"):
                self.current_project_state.runs.append(run_record)  # type: ignore[attr-defined]
            if hasattr(self.current_project_state, "project") and hasattr(self.current_project_state.project, "updated_at"):
                self.current_project_state.project.updated_at = now_iso()  # type: ignore[assignment]
            if hasattr(self, "_persist_current_project_state"):
                self._persist_current_project_state()
        except Exception:
            run_record = None

        self.operation_in_progress = True
        self._refresh_interaction_states()
        try:
            q_all, y_all, _e_all = self._read_xye_cached(van_path)
            q_all = np.asarray(q_all, dtype=float)
            y_all = np.asarray(y_all, dtype=float)
            finite = np.isfinite(q_all) & np.isfinite(y_all)
            q_all = q_all[finite]
            y_all = y_all[finite]
            order = np.argsort(q_all)
            q_sorted = q_all[order]
            y_sorted = y_all[order]

            fit = self._normalization_current_last_fit() or {}
            popt = fit.get("popt")
            if not isinstance(popt, list) or len(popt) != 7:
                raise RuntimeError("Fit parameters are not available; rerun the fit.")
            popt_arr = np.asarray(popt, dtype=float)
            if popt_arr.size != 7 or not np.all(np.isfinite(popt_arr)):
                raise RuntimeError("Fit parameters are invalid; rerun the fit.")

            from toscana.models.scattering import vanaQdep

            norSelf = vanaQdep(q_sorted, *popt_arr)
            # Pure sigmoid uses polynomial = 1.
            norsigm = vanaQdep(q_sorted, 1.0, 0.0, 0.0, float(popt_arr[3]), float(popt_arr[4]), float(popt_arr[5]), float(popt_arr[6]))
            with np.errstate(divide="ignore", invalid="ignore"):
                norpoly = np.where(norsigm != 0, norSelf / norsigm, np.nan)

            target_dir = self.current_project_root / "processed" / "normalization" / context_id
            target_dir.mkdir(parents=True, exist_ok=True)
            target = target_dir / "vanadium_self_fit.qdat"

            timestamp = now_iso()
            header = [
                f"# timestamp: {timestamp}",
                "# Q norSelf norsigm norpoly",
            ]
            lines = [*header]
            for qv, ns, ng, npv in zip(q_sorted, norSelf, norsigm, norpoly, strict=False):
                lines.append(f"{float(qv):.8g} {float(ns):.8g} {float(ng):.8g} {float(npv):.8g}")
            target.write_text("\n".join(lines) + "\n", encoding="utf-8")

            # Update manifest: store only the output file reference.
            manifest_written = None
            if isinstance(payload, dict):
                artifacts = payload.get("artifacts") if isinstance(payload.get("artifacts"), dict) else {}
                artifacts["vanadium_self_fit_qdat"] = project_relpath(self.current_project_root, target)
                payload["artifacts"] = artifacts
                try:
                    manifest_written = write_context_manifest(self.current_project_root, context_id=context_id, payload=payload)
                except Exception:
                    pass

            # Update run record.
            if run_record is not None:
                try:
                    run_record.status = "succeeded"
                    run_record.finished_at = now_iso()
                    run_record.summary = f"Exported `{project_relpath(self.current_project_root, target)}`"
                    generated = [project_relpath(self.current_project_root, target)]
                    if isinstance(manifest_written, Path):
                        generated.append(project_relpath(self.current_project_root, manifest_written))
                    run_record.output_paths.generated_files = generated
                    if hasattr(self.current_project_state, "project") and hasattr(self.current_project_state.project, "updated_at"):
                        self.current_project_state.project.updated_at = now_iso()  # type: ignore[assignment]
                    if hasattr(self, "_persist_current_project_state"):
                        self._persist_current_project_state()
                except Exception:
                    pass

            self._show_success_toast("Exported vanadium self-fit qdat.")
            if hasattr(self, "normalization_fit_params_export_prompt"):
                self.normalization_fit_params_export_prompt.visible = False
        except Exception as exc:
            if hasattr(self, "_show_error_toast"):
                self._show_error_toast(f"Export failed: {exc}")
            if run_record is not None:
                try:
                    run_record.status = "failed"
                    run_record.finished_at = now_iso()
                    run_record.summary = f"Export failed: {exc}"
                    if hasattr(self.current_project_state, "project") and hasattr(self.current_project_state.project, "updated_at"):
                        self.current_project_state.project.updated_at = now_iso()  # type: ignore[assignment]
                    if hasattr(self, "_persist_current_project_state"):
                        self._persist_current_project_state()
                except Exception:
                    pass
        finally:
            self.operation_in_progress = False
            try:
                self._refresh_interaction_states()
            except Exception:
                pass
            try:
                self._refresh_normalization_fit_params_button_states()
            except Exception:
                pass
            try:
                self._sync_normalization_fit_params_export_prompt_visibility()
            except Exception:
                pass
            try:
                if pn.state.curdoc is not None:
                    pn.state.curdoc.add_next_tick_callback(self._refresh_interaction_states)
            except Exception:
                pass

        self._load_normalization_fit_params_exported_result()
        self._refresh_normalization_sample_normalization_plot()

    def _normalization_current_last_sample_norm(self) -> dict[str, object] | None:
        context_id = str(getattr(getattr(self, "normalization_context_select", None), "value", "") or "").strip()
        project_token = str(getattr(self, "current_project_root", "") or "")
        cached = getattr(self, "_normalization_last_sample_norm", None)
        if not isinstance(cached, dict):
            return None
        if str(cached.get("context_id") or "").strip() != context_id:
            return None
        if str(cached.get("project_root") or "") != project_token:
            return None
        return cached  # type: ignore[return-value]

    def _refresh_normalization_sample_norm_button_states(self) -> None:
        if not hasattr(self, "normalization_sample_norm_export_button"):
            return
        can_export = self._normalization_current_last_sample_norm() is not None
        self.normalization_sample_norm_export_button.disabled = not bool(can_export) or bool(
            getattr(self, "operation_in_progress", False)
        )
        if hasattr(self, "normalization_sample_norm_export_confirm_button"):
            self.normalization_sample_norm_export_confirm_button.disabled = bool(getattr(self, "operation_in_progress", False))
        if hasattr(self, "normalization_sample_norm_export_cancel_button"):
            self.normalization_sample_norm_export_cancel_button.disabled = bool(getattr(self, "operation_in_progress", False))

    def _sync_normalization_sample_norm_export_prompt_visibility(self) -> None:
        if not hasattr(self, "normalization_sample_norm_export_prompt_card"):
            return
        visible = bool(getattr(getattr(self, "normalization_sample_norm_export_prompt", None), "visible", False))
        self.normalization_sample_norm_export_prompt_card.visible = visible

    def _prompt_normalization_sample_norm_export(self, _event=None) -> None:
        if self.current_project_root is None or self.current_project_state is None:
            return
        if not hasattr(self, "normalization_sample_norm_export_prompt"):
            return
        if bool(getattr(self.normalization_sample_norm_export_prompt, "visible", False)):
            self.normalization_sample_norm_export_prompt.visible = False
            self._sync_normalization_sample_norm_export_prompt_visibility()
            return

        cached = self._normalization_current_last_sample_norm()
        if cached is None:
            self._show_warning_toast("Compute sample normalization first (fix prerequisites above).")
            return

        context_id = str(getattr(getattr(self, "normalization_context_select", None), "value", "") or "").strip()
        payload = self._load_normalization_context_payload()
        sample_title = None
        if isinstance(payload, dict):
            sample = payload.get("sample") if isinstance(payload.get("sample"), dict) else {}
            if isinstance(sample.get("title"), str):
                sample_title = sample.get("title")

        # Determine deterministic filenames/targets.
        base = self._sanitize_export_filename_stem(str(sample_title or "sample"))
        if base.lower().endswith("_sub"):
            base = base[:-4] or base
        filename = f"{base}_dsdo.qdat"
        target_norm_dir = self.current_project_root / "processed" / "normalization" / context_id
        target_norm = target_norm_dir / filename
        target_qspdata = (self.current_project_root / "processed" / "qspdata") / filename

        rel_norm = project_relpath(self.current_project_root, target_norm)
        rel_qspdata = project_relpath(self.current_project_root, target_qspdata)
        lines = [
            "Proceeding will write (or overwrite) normalized sample qdat files:",
            "",
            f"Normalization: `{rel_norm}` \n",
            f"QSPData: `{rel_qspdata}`",
        ]

        overwrite = target_norm.exists() or target_qspdata.exists()
        self.normalization_sample_norm_export_prompt.alert_type = "warning" if overwrite else "secondary"
        if overwrite:
            lines.append("")
            lines.append("Warning: one or more targets already exist and will be overwritten.")
        self.normalization_sample_norm_export_prompt.object = "\n".join(lines)
        self.normalization_sample_norm_export_prompt.visible = True
        self._sync_normalization_sample_norm_export_prompt_visibility()

    def _cancel_normalization_sample_norm_export(self, _event=None) -> None:
        if hasattr(self, "normalization_sample_norm_export_prompt"):
            self.normalization_sample_norm_export_prompt.visible = False
        self._sync_normalization_sample_norm_export_prompt_visibility()

    def _confirm_normalization_sample_norm_export(self, _event=None) -> None:
        self._perform_normalization_sample_norm_export()

    def _perform_normalization_sample_norm_export(self) -> None:
        if self.current_project_root is None or self.current_project_state is None:
            return
        cached = self._normalization_current_last_sample_norm()
        if cached is None:
            self._show_warning_toast("Compute sample normalization first.")
            return

        context_id = str(getattr(getattr(self, "normalization_context_select", None), "value", "") or "").strip()
        if not context_id:
            self._show_warning_toast("Select a background context first.")
            return

        payload = self._load_normalization_context_payload()
        if not isinstance(payload, dict):
            self._show_warning_toast("Selected context has no manifest payload.")
            return

        sample_title = None
        sample = payload.get("sample") if isinstance(payload.get("sample"), dict) else {}
        if isinstance(sample.get("title"), str):
            sample_title = sample.get("title")

        base = self._sanitize_export_filename_stem(str(sample_title or "sample"))
        if base.lower().endswith("_sub"):
            base = base[:-4] or base
        filename = f"{base}_dsdo.qdat"

        target_norm_dir = self.current_project_root / "processed" / "normalization" / context_id
        target_norm_dir.mkdir(parents=True, exist_ok=True)
        target_norm = target_norm_dir / filename
        target_qspdata_dir = self.current_project_root / "processed" / "qspdata"
        target_qspdata_dir.mkdir(parents=True, exist_ok=True)
        target_qspdata = target_qspdata_dir / filename

        # Record in run history (best-effort).
        run_record = None
        try:
            from toscana_gui.persistence import OutputPaths, RunRecord

            run_id = None
            if hasattr(self, "_create_run_id"):
                try:
                    run_id = str(self._create_run_id())
                except Exception:
                    run_id = None
            run_id = run_id or datetime.now(tz=PARIS_TZ).strftime("normalization-%Y%m%d-%H%M%S-%f")

            run_record = RunRecord(
                run_id=run_id,
                workflow="normalization_sample_export",
                status="running",
                started_at=now_iso(),
                summary=f"Exporting `{filename}`",
                workflow_data={
                    "context_id": context_id,
                    "targets": {
                        "normalization": project_relpath(self.current_project_root, target_norm),
                        "qspdata": project_relpath(self.current_project_root, target_qspdata),
                    },
                },
                output_paths=OutputPaths(generated_files=[]),
            )
            self.current_project_state.runs.append(run_record)
            self.current_project_state.project.updated_at = now_iso()
            if hasattr(self, "_persist_current_project_state"):
                self._persist_current_project_state()
        except Exception:
            run_record = None

        self.operation_in_progress = True
        self._refresh_interaction_states()
        try:
            series = cached.get("series") if isinstance(cached.get("series"), dict) else {}
            q = np.asarray(series.get("q"), dtype=float)
            dsdo_y = np.asarray(series.get("dsdo_y"), dtype=float)
            dsdo_e = np.asarray(series.get("dsdo_e"), dtype=float)

            if q.size == 0 or dsdo_y.size == 0:
                raise RuntimeError("No normalized sample data is available to export.")
            if dsdo_e.shape != dsdo_y.shape:
                dsdo_e = np.zeros_like(dsdo_y, dtype=float)

            # Build qdat lines.
            header = [
                f"# timestamp: {now_iso()}",
                "# Q dsdo error",
            ]
            lines = [*header]
            for qv, yv, ev in zip(q, dsdo_y, dsdo_e, strict=False):
                lines.append(f"{float(qv):.8g} {float(yv):.8g} {float(ev):.8g}")
            text = "\n".join(lines) + "\n"

            target_norm.write_text(text, encoding="utf-8")
            target_qspdata.write_text(text, encoding="utf-8")

            # Update manifest artifacts.
            manifest_written = None
            artifacts = payload.get("artifacts") if isinstance(payload.get("artifacts"), dict) else {}
            artifacts["sample_dsdo_qdat"] = project_relpath(self.current_project_root, target_norm)
            artifacts["sample_dsdo_qdat_qspdata"] = project_relpath(self.current_project_root, target_qspdata)
            payload["artifacts"] = artifacts
            try:
                manifest_written = write_context_manifest(self.current_project_root, context_id=context_id, payload=payload)
            except Exception:
                manifest_written = None

            if run_record is not None:
                try:
                    run_record.status = "succeeded"
                    run_record.finished_at = now_iso()
                    run_record.summary = f"Exported `{filename}`"
                    generated = [
                        project_relpath(self.current_project_root, target_norm),
                        project_relpath(self.current_project_root, target_qspdata),
                    ]
                    if isinstance(manifest_written, Path):
                        generated.append(project_relpath(self.current_project_root, manifest_written))
                    run_record.output_paths.generated_files = generated
                    self.current_project_state.project.updated_at = now_iso()
                    if hasattr(self, "_persist_current_project_state"):
                        self._persist_current_project_state()
                except Exception:
                    pass

            self._show_success_toast("Exported normalized sample qdat.")
            if hasattr(self, "normalization_sample_norm_export_prompt"):
                self.normalization_sample_norm_export_prompt.visible = False
        except Exception as exc:
            if hasattr(self, "_show_error_toast"):
                self._show_error_toast(f"Export failed: {exc}")
            if run_record is not None:
                try:
                    run_record.status = "failed"
                    run_record.finished_at = now_iso()
                    run_record.summary = f"Export failed: {exc}"
                    self.current_project_state.project.updated_at = now_iso()
                    if hasattr(self, "_persist_current_project_state"):
                        self._persist_current_project_state()
                except Exception:
                    pass
        finally:
            self.operation_in_progress = False
            self._refresh_interaction_states()
            self._refresh_normalization_sample_norm_button_states()
            self._sync_normalization_sample_norm_export_prompt_visibility()

    def _refresh_normalization_vanadium_self_fit_preview_fit_table(self) -> None:
        pane = getattr(self, "normalization_vanadium_self_fit_preview_fit_table", None)
        if pane is None:
            return

        context_id = str(getattr(getattr(self, "normalization_context_select", None), "value", "") or "").strip()
        project_token = str(getattr(self, "current_project_root", "") or "")

        fit = getattr(self, "_normalization_last_fit", None)
        if isinstance(fit, dict):
            fit_context = str(fit.get("context_id") or "").strip()
            fit_project = str(fit.get("project_root") or "")
            if fit_context != context_id or fit_project != project_token:
                fit = None
        if not isinstance(fit, dict):
            fit = getattr(self, "_normalization_last_exported", None)
        if not isinstance(fit, dict):
            pane.object = ""
            return

        popt = fit.get("popt")
        perr = fit.get("perr")
        if not isinstance(popt, list) or not isinstance(perr, list) or len(popt) != 7 or len(perr) != 7:
            pane.object = ""
            return

        n_points = fit.get("n_points")
        try:
            n_points_int = int(n_points) if n_points is not None else None
        except Exception:
            n_points_int = None

        def _fmt_value(v: object) -> str:
            try:
                x = float(v)
            except Exception:
                return ""
            if not (x == x):  # NaN
                return ""
            if x == 0.0:
                return "0"
            if abs(x) < 1e-3:
                return f"{x:.3e}"
            return f"{x:.3f}".rstrip("0").rstrip(".")

        def _fmt_err(v: object) -> str:
            try:
                x = float(v)
            except Exception:
                return ""
            if not (x == x):  # NaN
                return ""
            if x == 0.0:
                return "0"
            if abs(x) < 1e-3:
                return f"{x:.3e}"
            return f"{x:.3f}".rstrip("0").rstrip(".")

        names = ["a0", "a1", "a2", "A", "lowQ", "Q0", "dQ"]
        rows_html = []
        for name, v, e in zip(names, popt, perr, strict=False):
            rows_html.append(
                "<tr>"
                f"<td class=\"toscana-fit-result-table__param\">{name}</td>"
                f"<td class=\"toscana-fit-result-table__value\">{_fmt_value(v)}</td>"
                f"<td class=\"toscana-fit-result-table__err\">{_fmt_err(e)}</td>"
                "</tr>"
            )

        meta_html = ""
        if n_points_int is not None and n_points_int >= 0:
            meta_html = f"<div class=\"toscana-fit-result-table__meta\">Selected points: <strong>{n_points_int}</strong></div>"

        pane.object = (
            "<div class=\"toscana-fit-window-table\">"
            "<div class=\"toscana-fit-result-table__title\">Fit result</div>"
            f"{meta_html}"
            "<table class=\"toscana-fit-result-table\">"
            "<thead><tr><th>Param</th><th>Value</th><th>±</th></tr></thead>"
            "<tbody>"
            + "".join(rows_html)
            + "</tbody>"
            "</table>"
            "</div>"
        )

    def _normalization_fit_data_current_subset(
        self,
        *,
        q_all: np.ndarray,
        y_all: np.ndarray,
        e_all: np.ndarray | None = None,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray | None, str | None]:
        mode = self._normalize_normalization_fit_data_mode(
            getattr(getattr(self, "normalization_fit_data_selection_mode", None), "value", "")
        )
        use_sliders = bool(getattr(getattr(self, "normalization_fit_data_use_sliders", None), "value", False))

        def _w(name: str):
            return getattr(self, name, None)

        q_all = np.asarray(q_all, dtype=float)
        y_all = np.asarray(y_all, dtype=float)
        e_arr = np.asarray(e_all, dtype=float) if e_all is not None else None

        warning: str | None = None
        if self._is_normalization_fit_data_manual_mode(mode):
            q_min_w = _w("normalization_fit_data_q_min_slider" if use_sliders else "normalization_fit_data_q_min")
            q_max_w = _w("normalization_fit_data_q_max_slider" if use_sliders else "normalization_fit_data_q_max")
            y_min_w = _w("normalization_fit_data_y_min_slider" if use_sliders else "normalization_fit_data_y_min")
            y_max_w = _w("normalization_fit_data_y_max_slider" if use_sliders else "normalization_fit_data_y_max")
            q_min = float(getattr(q_min_w, "value", 0.0) or 0.0)
            q_max = float(getattr(q_max_w, "value", 0.0) or 0.0)
            y_min = float(getattr(y_min_w, "value", 0.0) or 0.0)
            y_max = float(getattr(y_max_w, "value", 0.0) or 0.0)
            if q_max < q_min:
                warning = "Manual window has q_max < q_min."
            if y_max < y_min:
                warning = "Manual window has y_max < y_min."
            mask = (q_all >= q_min) & (q_all <= q_max) & (y_all >= y_min) & (y_all <= y_max)
        else:
            q_tail_low_w = _w("normalization_fit_data_q_tail_low_slider" if use_sliders else "normalization_fit_data_q_tail_low")
            q_tail_high_w = _w("normalization_fit_data_q_tail_high_slider" if use_sliders else "normalization_fit_data_q_tail_high")
            min_pct_w = _w("normalization_fit_data_min_percentile_slider" if use_sliders else "normalization_fit_data_min_percentile")
            max_pct_w = _w("normalization_fit_data_max_percentile_slider" if use_sliders else "normalization_fit_data_max_percentile")
            q_tail_low = float(getattr(q_tail_low_w, "value", 0.0) or 0.0)
            q_tail_high = float(getattr(q_tail_high_w, "value", 0.0) or 0.0)
            min_pct = int(getattr(min_pct_w, "value", 0) or 0)
            max_pct = int(getattr(max_pct_w, "value", 0) or 0)
            if q_tail_high < q_tail_low:
                warning = "Percentile band has Q end < Q start."
            if max_pct < min_pct:
                warning = "Percentile band has upper percentile < lower percentile."
            y_min = float(np.percentile(y_all[np.isfinite(y_all)], min_pct)) if np.any(np.isfinite(y_all)) else 0.0
            y_max = float(np.percentile(y_all[np.isfinite(y_all)], max_pct)) if np.any(np.isfinite(y_all)) else 0.0
            mask = (q_all >= q_tail_low) & (q_all <= q_tail_high) & (y_all >= y_min) & (y_all <= y_max)

        finite = np.isfinite(q_all) & np.isfinite(y_all)
        mask = mask & finite
        q_subset = q_all[mask]
        y_subset = y_all[mask]
        e_subset = e_arr[mask] if e_arr is not None and e_arr.shape == q_all.shape else None
        return q_subset, y_subset, e_subset, warning

    @staticmethod
    def _patch_sigma_values(sigma: np.ndarray) -> tuple[np.ndarray, str | None]:
        sigma = np.asarray(sigma, dtype=float)
        if sigma.size == 0:
            return sigma, None
        ok = np.isfinite(sigma) & (sigma > 0)
        if ok.all():
            return sigma, None
        if not ok.any():
            return sigma, "No valid uncertainties found; falling back to estimated weighting."

        out = sigma.copy()
        idx_bad = np.where(~ok)[0]
        for i in idx_bad:
            lo = max(0, i - 2)
            hi = min(out.size, i + 3)
            neigh = out[lo:hi]
            neigh_ok = neigh[np.isfinite(neigh) & (neigh > 0)]
            if neigh_ok.size:
                out[i] = float(np.median(neigh_ok))
            else:
                out[i] = float(np.median(out[ok]))
        return out, "Some uncertainties were invalid and were replaced with a local median."

    def _normalization_fit_params_run_fit(self, _event=None) -> None:
        if self.current_project_root is None or self.current_project_state is None:
            return
        if not hasattr(self, "normalization_fit_params_results"):
            return

        if getattr(self, "operation_in_progress", False):
            return

        context_id = str(getattr(getattr(self, "normalization_context_select", None), "value", "") or "").strip()
        if not context_id:
            if hasattr(self, "normalization_fit_params_alert"):
                self.normalization_fit_params_alert.object = "Select a background context first."
                self.normalization_fit_params_alert.alert_type = "warning"
                self.normalization_fit_params_alert.visible = True
            return

        manifest_ref = str(self._selected_normalization_manifest_ref() or "").strip() if hasattr(self, "_selected_normalization_manifest_ref") else ""
        if not manifest_ref:
            if hasattr(self, "normalization_fit_params_alert"):
                self.normalization_fit_params_alert.object = "Selected context has no manifest reference."
                self.normalization_fit_params_alert.alert_type = "warning"
                self.normalization_fit_params_alert.visible = True
            return

        payload = load_context_manifest(self.current_project_root, manifest_ref)
        artifacts = payload.get("artifacts") if isinstance(payload, dict) else {}
        van_ref = artifacts.get("vanadium_sub_qdat") if isinstance(artifacts, dict) else None
        if not isinstance(van_ref, str) or not van_ref.strip():
            if hasattr(self, "normalization_fit_params_alert"):
                self.normalization_fit_params_alert.object = "Selected context has no `vanadium_sub_qdat` reference."
                self.normalization_fit_params_alert.alert_type = "warning"
                self.normalization_fit_params_alert.visible = True
            return

        try:
            van_path = resolve_project_path(self.current_project_root, van_ref)
        except Exception:
            if hasattr(self, "normalization_fit_params_alert"):
                self.normalization_fit_params_alert.object = "Vanadium qdat reference could not be resolved."
                self.normalization_fit_params_alert.alert_type = "warning"
                self.normalization_fit_params_alert.visible = True
            return

        if not van_path.exists():
            if hasattr(self, "normalization_fit_params_alert"):
                self.normalization_fit_params_alert.object = f"Missing data: `{van_path}`"
                self.normalization_fit_params_alert.alert_type = "warning"
                self.normalization_fit_params_alert.visible = True
            return

        if hasattr(self, "normalization_fit_params_alert"):
            try:
                self.normalization_fit_params_alert.object = ""
                self.normalization_fit_params_alert.visible = False
                self.normalization_fit_params_alert.alert_type = "secondary"
            except Exception:
                pass
        self._set_normalization_fit_params_status("Running fit...")

        self.operation_in_progress = True
        self._refresh_interaction_states()
        try:
            q_all, y_all, e_all = self._read_xye_cached(van_path)
            q_subset, y_subset, e_subset, warning = self._normalization_fit_data_current_subset(
                q_all=q_all, y_all=y_all, e_all=e_all
            )
            if q_subset.size < 5:
                raise RuntimeError("Not enough points selected for fitting. Adjust the fitting-data window.")

            # Build p0 and bounds from the current widgets.
            def _p(name: str, default: float) -> float:
                w = getattr(self, f"normalization_fit_params_{name}_value", None)
                try:
                    return float(getattr(w, "value", default))
                except Exception:
                    return float(default)

            def _b(name: str, field: str, default: float) -> float:
                w = getattr(self, f"normalization_fit_params_{name}_{field}", None)
                try:
                    return float(getattr(w, "value", default))
                except Exception:
                    return float(default)

            pinned_A = bool(getattr(getattr(self, "normalization_fit_params_A_pinned", None), "value", True))
            a0, a1, a2 = _p("a0", 1.0), _p("a1", 0.0), _p("a2", 0.0)
            A = 51.0 if pinned_A else _p("A", 51.0)
            lowQ, Q0, dQ = _p("lowQ", 0.4), _p("Q0", 7.4), _p("dQ", 2.4)

            # Sigma policy.
            sigma_warning: str | None = None
            if e_subset is not None and e_subset.size == y_subset.size:
                patched, patch_warn = self._patch_sigma_values(e_subset)
                if np.isfinite(patched).any() and np.any(patched > 0):
                    sigma = patched
                    sigma_warning = patch_warn
                else:
                    sigma = None
            else:
                sigma = None

            if sigma is None:
                q_eps = 1e-3
                qq = np.maximum(np.abs(np.asarray(q_subset, dtype=float)), q_eps)
                sigma = 1.0 / (qq**2)
                sigma_warning = "Uncertainties missing; using estimated sigma = 1/q^2 weighting."

            from scipy.optimize import curve_fit
            from toscana.models.scattering import vanaQdep

            if pinned_A:
                # SciPy bounds require lower < upper; "pinning" is handled by removing A from the fit.
                def _vana_fixed_A(x, a0, a1, a2, lowQ, Q0, dQ):
                    return vanaQdep(x, a0, a1, a2, 51.0, lowQ, Q0, dQ)

                p0 = [a0, a1, a2, lowQ, Q0, dQ]
                bounds_lo = [
                    _b("a0", "min", -1e6),
                    _b("a1", "min", -1e6),
                    _b("a2", "min", -1e6),
                    _b("lowQ", "min", 0.0),
                    _b("Q0", "min", float(np.nanmin(q_all))),
                    _b("dQ", "min", 1e-3),
                ]
                bounds_hi = [
                    _b("a0", "max", 1e6),
                    _b("a1", "max", 1e6),
                    _b("a2", "max", 1e6),
                    _b("lowQ", "max", 1e6),
                    _b("Q0", "max", float(np.nanmax(q_all))),
                    _b("dQ", "max", float(np.nanmax(q_all) - np.nanmin(q_all))),
                ]

                popt6, pcov6 = curve_fit(
                    _vana_fixed_A,
                    q_subset,
                    y_subset,
                    p0=p0,
                    bounds=(bounds_lo, bounds_hi),
                    sigma=sigma,
                    absolute_sigma=True,
                    maxfev=20000,
                )
                perr6 = np.sqrt(np.diag(pcov6)) if pcov6 is not None else np.full(6, np.nan, dtype=float)
                popt = np.array([popt6[0], popt6[1], popt6[2], 51.0, popt6[3], popt6[4], popt6[5]], dtype=float)
                perr = np.array([perr6[0], perr6[1], perr6[2], 0.0, perr6[3], perr6[4], perr6[5]], dtype=float)
            else:
                p0 = [a0, a1, a2, A, lowQ, Q0, dQ]
                bounds_lo = [
                    _b("a0", "min", -1e6),
                    _b("a1", "min", -1e6),
                    _b("a2", "min", -1e6),
                    _b("A", "min", 1.0),
                    _b("lowQ", "min", 0.0),
                    _b("Q0", "min", float(np.nanmin(q_all))),
                    _b("dQ", "min", 1e-3),
                ]
                bounds_hi = [
                    _b("a0", "max", 1e6),
                    _b("a1", "max", 1e6),
                    _b("a2", "max", 1e6),
                    _b("A", "max", 300.0),
                    _b("lowQ", "max", 1e6),
                    _b("Q0", "max", float(np.nanmax(q_all))),
                    _b("dQ", "max", float(np.nanmax(q_all) - np.nanmin(q_all))),
                ]

                if any(float(lo) >= float(hi) for lo, hi in zip(bounds_lo, bounds_hi, strict=True)):
                    raise RuntimeError("Invalid bounds: each min must be strictly less than max.")

                popt, pcov = curve_fit(
                    vanaQdep,
                    q_subset,
                    y_subset,
                    p0=p0,
                    bounds=(bounds_lo, bounds_hi),
                    sigma=sigma,
                    absolute_sigma=True,
                    maxfev=20000,
                )
                perr = np.sqrt(np.diag(pcov)) if pcov is not None else np.full(7, np.nan, dtype=float)

            # Store last result in-memory only (not persisted).
            context_id = str(
                getattr(getattr(self, "normalization_context_select", None), "value", "") or ""
            ).strip()
            project_token = str(getattr(self, "current_project_root", "") or "")
            self._normalization_last_fit = {
                "context_id": context_id,
                "project_root": project_token,
                "popt": [float(v) for v in popt],
                "perr": [float(v) for v in perr],
                "warning": warning,
                "sigma_warning": sigma_warning,
                "n_points": int(q_subset.size),
            }

            # Update results markdown.
            names = ["a0", "a1", "a2", "A", "lowQ", "Q0", "dQ"]
            rows = ["| Param | Value | ± |", "|---|---:|---:|"]
            for name, v, e in zip(names, popt, perr, strict=False):
                rows.append(f"| {name} | {float(v):.6g} | {float(e):.3g} |")
            notes: list[str] = []
            if warning:
                notes.append(f"- Window warning: {warning}")
            if sigma_warning:
                notes.append(f"- Sigma: {sigma_warning}")
            self.normalization_fit_params_results.object = "\n".join(
                ["### Fit result", "", f"Selected points: **{int(q_subset.size)}**", "", *rows, "", *notes]
            )
            self._refresh_normalization_vanadium_self_fit_preview_fit_table()

            # Cache series for plotting/export without re-reading files.
            q_all_f = np.asarray(q_all, dtype=float)
            y_all_f = np.asarray(y_all, dtype=float)
            finite_all = np.isfinite(q_all_f) & np.isfinite(y_all_f)
            q_all_f = q_all_f[finite_all]
            y_all_f = y_all_f[finite_all]
            order = np.argsort(q_all_f)
            q_sorted = q_all_f[order]
            y_sorted = y_all_f[order]
            norSelf = vanaQdep(q_sorted, *popt)
            norsigm = vanaQdep(
                q_sorted,
                1.0,
                0.0,
                0.0,
                float(popt[3]),
                float(popt[4]),
                float(popt[5]),
                float(popt[6]),
            )
            norsigm0 = float(
                vanaQdep(
                    0.0,
                    1.0,
                    0.0,
                    0.0,
                    float(popt[3]),
                    float(popt[4]),
                    float(popt[5]),
                    float(popt[6]),
                )
            )
            with np.errstate(divide="ignore", invalid="ignore"):
                norpoly = np.where(norsigm != 0, norSelf / norsigm, np.nan)

            self._normalization_last_fit["series"] = {
                "q": q_sorted,
                "y": y_sorted,
                "norSelf": norSelf,
                "norsigm": norsigm,
                "norpoly": norpoly,
                "norsigm0": norsigm0,
            }
            self._normalization_last_fit["computed_at"] = now_iso()
            self._normalization_last_fit["selection_snapshot"] = self._normalization_fit_data_selection_snapshot_fit_relevant()
            self._normalization_last_fit["params_snapshot"] = self._normalization_fit_params_snapshot_fit_relevant()

            # Persist last-fit metadata for reload/staleness detection.
            try:
                if isinstance(payload, dict):
                    decisions = payload.get("decisions") if isinstance(payload.get("decisions"), dict) else {}
                    normalization = decisions.get("normalization") if isinstance(decisions.get("normalization"), dict) else {}
                    normalization["vanadium_fit_last"] = {
                        "computed_at": str(self._normalization_last_fit.get("computed_at") or ""),
                        "popt": list(self._normalization_last_fit.get("popt") or []),
                        "perr": list(self._normalization_last_fit.get("perr") or []),
                        "n_points": int(self._normalization_last_fit.get("n_points") or 0),
                        "warning": self._normalization_last_fit.get("warning"),
                        "sigma_warning": self._normalization_last_fit.get("sigma_warning"),
                        "selection_snapshot": dict(self._normalization_last_fit.get("selection_snapshot") or {}),
                        "params_snapshot": dict(self._normalization_last_fit.get("params_snapshot") or {}),
                    }
                    decisions["normalization"] = normalization
                    payload["decisions"] = decisions
                    write_context_manifest(self.current_project_root, context_id=context_id, payload=payload)
            except Exception:
                pass

            # Keep "last seen" snapshots in sync (so UI-only toggles don't mark stale).
            self._normalization_fit_last_seen_selection_snapshot = self._normalization_fit_data_selection_snapshot_fit_relevant()
            self._normalization_fit_last_seen_params_snapshot = self._normalization_fit_params_snapshot_fit_relevant()

            self._refresh_normalization_fit_params_plot()
            self._refresh_normalization_sample_normalization_plot()
            self._set_normalization_fit_params_status("Fit complete.")

            if hasattr(self, "_show_success_toast"):
                self._show_success_toast("Fit completed.")
        except Exception as exc:
            if hasattr(self, "_show_error_toast"):
                self._show_error_toast(f"Fit failed: {exc}")
            if hasattr(self, "normalization_fit_params_alert"):
                self.normalization_fit_params_alert.object = str(exc)
                self.normalization_fit_params_alert.alert_type = "warning"
                self.normalization_fit_params_alert.visible = True
            self._set_normalization_fit_params_status("Fit failed. See alert.")
        finally:
            self.operation_in_progress = False
            self._refresh_interaction_states()
            self._refresh_normalization_fit_params_button_states()
            self._sync_normalization_fit_params_export_prompt_visibility()

    def _on_normalization_fit_params_plot_mode_change(self, event=None) -> None:
        if getattr(self, "_suspend_normalization_events", False) or self.current_project_state is None:
            return
        self._refresh_normalization_fit_params_plot()

        view_switch = getattr(self, "normalization_vanadium_self_fit_preview_view_switch", None)
        if view_switch is not None:
            desired = str(getattr(self.normalization_fit_params_plot_mode, "value", "") or "").strip() == "Differential cross section"
            try:
                setattr(self, "_syncing_normalization_vanadium_preview_view", True)
                if bool(getattr(view_switch, "value", False)) != desired:
                    view_switch.value = desired
            finally:
                setattr(self, "_syncing_normalization_vanadium_preview_view", False)

    def _on_normalization_vanadium_self_fit_preview_view_change(self, event=None) -> None:
        if getattr(self, "_suspend_normalization_events", False) or self.current_project_state is None:
            return
        if bool(getattr(self, "_syncing_normalization_vanadium_preview_view", False)):
            return

        view_switch = getattr(self, "normalization_vanadium_self_fit_preview_view_switch", None)
        if view_switch is None:
            return
        desired_mode = "Differential cross section" if bool(getattr(view_switch, "value", False)) else "Fit overlay"
        plot_mode = getattr(self, "normalization_fit_params_plot_mode", None)
        if plot_mode is None:
            return
        current = str(getattr(plot_mode, "value", "") or "").strip()
        if desired_mode != current:
            plot_mode.value = desired_mode
        else:
            self._refresh_normalization_fit_params_plot()

    def _on_normalization_fit_params_bounds_toggle_change(self, event=None) -> None:
        if getattr(self, "_suspend_normalization_events", False) or self.current_project_state is None:
            return
        toggle = getattr(self, "normalization_fit_params_bounds_toggle", None)
        bounds_card = getattr(self, "normalization_fit_params_bounds_card", None)
        if toggle is None or bounds_card is None:
            return
        show = bool(getattr(toggle, "value", False))
        try:
            bounds_card.visible = show
        except Exception:
            return

    @staticmethod
    def _parse_timestamp_header(lines: list[str]) -> str | None:
        for line in lines[:5]:
            raw = str(line).strip()
            if raw.lower().startswith("# timestamp:"):
                return raw.split(":", 1)[1].strip() or None
        return None

    @staticmethod
    def _read_self_fit_qdat(path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, str | None]:
        text = path.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        ts = NormalizationControllerMixin._parse_timestamp_header(lines)
        rows: list[list[float]] = []
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) < 4:
                continue
            try:
                rows.append([float(parts[0]), float(parts[1]), float(parts[2]), float(parts[3])])
            except Exception:
                continue
        if not rows:
            raise RuntimeError("Self-fit qdat had no readable data rows.")
        arr = np.asarray(rows, dtype=float)
        q = arr[:, 0]
        norSelf = arr[:, 1]
        norsigm = arr[:, 2]
        norpoly = arr[:, 3]
        return q, norSelf, norsigm, norpoly, ts

    def _load_normalization_fit_params_exported_result(self) -> None:
        if self.current_project_root is None or self.current_project_state is None:
            return
        if not hasattr(self, "normalization_fit_params_results"):
            return

        # Clear any previously loaded exported result; we'll repopulate if available.
        self._normalization_last_exported = None

        context_id = str(getattr(getattr(self, "normalization_context_select", None), "value", "") or "").strip()
        if not context_id:
            return

        manifest_ref = str(self._selected_normalization_manifest_ref() or "").strip() if hasattr(self, "_selected_normalization_manifest_ref") else ""
        if not manifest_ref:
            return

        payload = load_context_manifest(self.current_project_root, manifest_ref)
        artifacts = payload.get("artifacts") if isinstance(payload, dict) else {}
        ref = artifacts.get("vanadium_self_fit_qdat") if isinstance(artifacts, dict) else None
        if not isinstance(ref, str) or not ref.strip():
            return

        try:
            path = resolve_project_path(self.current_project_root, ref)
        except Exception:
            return
        if not path.exists():
            return

        try:
            q, norSelf, norsigm, norpoly, ts = self._read_self_fit_qdat(path)
        except Exception:
            return

        # Also load the vanadium_sub_qdat for the data series if present.
        y_data = None
        norsigm0 = None
        van_ref = artifacts.get("vanadium_sub_qdat") if isinstance(artifacts, dict) else None
        if isinstance(van_ref, str) and van_ref.strip():
            try:
                van_path = resolve_project_path(self.current_project_root, van_ref)
                q_all, y_all, _e_all = self._read_xye_cached(van_path)
                q_all = np.asarray(q_all, dtype=float)
                y_all = np.asarray(y_all, dtype=float)
                finite = np.isfinite(q_all) & np.isfinite(y_all)
                q_all = q_all[finite]
                y_all = y_all[finite]
                order = np.argsort(q_all)
                q_all = q_all[order]
                y_all = y_all[order]
                # Interpolate data to the exported q grid to match shapes.
                y_data = np.interp(q, q_all, y_all, left=np.nan, right=np.nan)
            except Exception:
                y_data = None

        # If we don't have norsigm0 available, approximate from q=0 row if present.
        try:
            # norsigm0 is vanaQdep(0, poly=1, ...). We can approximate by interpolating norsigm at Q=0.
            norsigm0 = float(np.interp(0.0, q, norsigm))
        except Exception:
            norsigm0 = None

        self._normalization_last_exported = {
            "path": path,
            "timestamp": ts,
            "series": {
                "q": q,
                "y": y_data,
                "norSelf": norSelf,
                "norsigm": norsigm,
                "norpoly": norpoly,
                "norsigm0": norsigm0,
            },
        }

        ts_text = f"`{ts}`" if ts else "(timestamp missing)"
        self.normalization_fit_params_results.object = "\n".join(
            [
                "### Exported self fit found",
                "",
                f"File: `{path}`",
                f"Timestamp: {ts_text}",
                "",
                "_Loaded from disk. Run Fit to recompute and compare._",
            ]
        )
        self._refresh_normalization_fit_params_plot()
        self._refresh_normalization_vanadium_self_fit_preview_fit_table()
        self._refresh_normalization_sample_normalization_plot()

    def _refresh_normalization_fit_params_plot(self) -> None:
        if not hasattr(self, "normalization_fit_params_plot_pane") or not hasattr(self, "normalization_fit_params_plot_mode"):
            return
        context_id = str(getattr(getattr(self, "normalization_context_select", None), "value", "") or "").strip()
        project_token = str(getattr(self, "current_project_root", "") or "")

        series = None
        fit = getattr(self, "_normalization_last_fit", None)
        if isinstance(fit, dict):
            fit_context = str(fit.get("context_id") or "").strip()
            fit_project = str(fit.get("project_root") or "")
            if fit_context == context_id and fit_project == project_token:
                series = fit.get("series")
        if series is None and isinstance(getattr(self, "_normalization_last_exported", None), dict):
            series = self._normalization_last_exported.get("series")

        preview_pane = getattr(self, "normalization_vanadium_self_fit_preview_plot_pane", None)
        if not isinstance(series, dict):
            self.normalization_fit_params_plot_pane.object = None
            if preview_pane is not None:
                preview_pane.object = None
            self._refresh_normalization_vanadium_self_fit_preview_fit_table()
            return

        q = series.get("q")
        y = series.get("y")
        norSelf = series.get("norSelf")
        norsigm = series.get("norsigm")
        norpoly = series.get("norpoly")
        norsigm0 = series.get("norsigm0")
        if q is None or norSelf is None:
            self.normalization_fit_params_plot_pane.object = None
            if preview_pane is not None:
                preview_pane.object = None
            self._refresh_normalization_vanadium_self_fit_preview_fit_table()
            return

        try:
            import hashlib
            import plotly.graph_objects as go

            mode = str(getattr(self.normalization_fit_params_plot_mode, "value", "") or "").strip()

            project_token = str(getattr(self, "current_project_root", "") or "")
            project_hash = hashlib.sha1(project_token.encode("utf-8")).hexdigest()[:10] if project_token else "no-project"
            uirevision = f"normalization-fit-plot:{project_hash}:{context_id}:{mode}"

            source_bits: list[str] = [project_hash, context_id, mode]
            exported = getattr(self, "_normalization_last_exported", None)
            if isinstance(exported, dict):
                p = exported.get("path")
                try:
                    source_bits.append(str(Path(p).resolve()) if p is not None else "")
                except Exception:
                    pass
            source_token = "|".join([b for b in source_bits if b])

            current = self.normalization_fit_params_plot_pane.object
            previous_source = getattr(self, "_normalization_fit_params_plot_source", None)
            if not isinstance(previous_source, str):
                previous_source = None

            q_arr = np.asarray(q, dtype=float)
            y_arr = None if y is None else np.asarray(y, dtype=float)
            norSelf_arr = np.asarray(norSelf, dtype=float)
            norsigm_arr = None if norsigm is None else np.asarray(norsigm, dtype=float)
            norpoly_arr = None if norpoly is None else np.asarray(norpoly, dtype=float)

            if isinstance(current, go.Figure) and previous_source == source_token:
                fig = current
                update_vanadium_self_fit_preview_figure(
                    fig,
                    q=q_arr,
                    y=y_arr,
                    norSelf=norSelf_arr,
                    norsigm=norsigm_arr,
                    norpoly=norpoly_arr,
                    norsigm0=norsigm0,
                    mode=mode,
                    uirevision=uirevision,
                )
            else:
                fig = build_vanadium_self_fit_preview_figure(
                    q=q_arr,
                    y=y_arr,
                    norSelf=norSelf_arr,
                    norsigm=norsigm_arr,
                    norpoly=norpoly_arr,
                    norsigm0=norsigm0,
                    mode=mode,
                    uirevision=uirevision,
                )
                self._normalization_fit_params_plot_source = source_token

            if not isinstance(current, go.Figure) or previous_source != source_token:
                self.normalization_fit_params_plot_pane.object = fig
            else:
                self.normalization_fit_params_plot_pane.param.trigger("object")

            if preview_pane is not None:
                preview_current = preview_pane.object
                if not isinstance(preview_current, go.Figure) or preview_current is not fig:
                    preview_pane.object = fig
                else:
                    preview_pane.param.trigger("object")
        except Exception:
            return
        finally:
            # Keep the fit-result table in sync even when only the plot is refreshed.
            self._refresh_normalization_vanadium_self_fit_preview_fit_table()
    def _on_normalization_fit_params_change(self, event=None) -> None:
        if getattr(self, "_suspend_normalization_events", False) or self.current_project_state is None:
            return

        before_snap = self._normalization_fit_params_snapshot_fit_relevant()

        def _round_widget(name: str) -> None:
            widget = getattr(self, name, None)
            if widget is None:
                return
            raw = getattr(widget, "value", None)
            try:
                value = float(raw)
            except Exception:
                return
            if not np.isfinite(value):
                return
            if value != 0.0 and abs(value) < 0.01:
                return
            rounded = float(round(value, 2))
            if rounded == value:
                return
            try:
                widget.value = rounded
            except Exception:
                return

        # If A was unpinned, restore default bounds (once) when coming from the pinned state.
        if hasattr(self, "normalization_fit_params_A_pinned"):
            pinned = bool(getattr(self.normalization_fit_params_A_pinned, "value", True))
            if not pinned:
                try:
                    a_min = float(getattr(self.normalization_fit_params_A_min, "value", 51.0))
                    a_max = float(getattr(self.normalization_fit_params_A_max, "value", 51.0))
                    if a_min == 51.0 and a_max == 51.0:
                        self._suspend_normalization_events = True
                        try:
                            self.normalization_fit_params_A_min.value = 1.0
                            self.normalization_fit_params_A_max.value = 300.0
                        finally:
                            self._suspend_normalization_events = False
                except Exception:
                    pass

        # Keep numeric displays compact (max 2 decimals) across all value/bounds fields.
        self._suspend_normalization_events = True
        try:
            for key in ("a0", "a1", "a2", "A", "lowQ", "Q0", "dQ"):
                _round_widget(f"normalization_fit_params_{key}_value")
                _round_widget(f"normalization_fit_params_{key}_min")
                _round_widget(f"normalization_fit_params_{key}_max")
        finally:
            self._suspend_normalization_events = False

        self._apply_normalization_fit_params_A_pinned_state()
        self._persist_normalization_fit_params_to_context()

        after_snap = self._normalization_fit_params_snapshot_fit_relevant()
        last_seen = getattr(self, "_normalization_fit_last_seen_params_snapshot", None)
        if not isinstance(last_seen, dict):
            self._normalization_fit_last_seen_params_snapshot = after_snap
        else:
            # Use before/after to avoid false positives from internal rounding writes.
            changed = (before_snap != after_snap) or (last_seen != after_snap)
            if changed:
                self._normalization_fit_last_seen_params_snapshot = after_snap
                if self._normalization_current_last_fit() is not None:
                    self._invalidate_normalization_fit_result(reason="fit_params_changed")

    def _load_normalization_fit_data_selection_from_context(self) -> None:
        if self.current_project_root is None or self.current_project_state is None:
            return
        if not hasattr(self, "normalization_fit_data_selection_mode"):
            return

        context_id = str(getattr(getattr(self, "normalization_context_select", None), "value", "") or "").strip()
        if not context_id:
            return

        manifest_ref = ""
        if hasattr(self, "_selected_normalization_manifest_ref"):
            manifest_ref = str(self._selected_normalization_manifest_ref() or "").strip()
        if not manifest_ref:
            return

        payload = load_context_manifest(self.current_project_root, manifest_ref)
        if not isinstance(payload, dict):
            return

        decisions = payload.get("decisions") if isinstance(payload.get("decisions"), dict) else {}
        normalization = decisions.get("normalization") if isinstance(decisions.get("normalization"), dict) else {}
        selection = normalization.get("vanadium_fit_data_selection")
        if not isinstance(selection, dict):
            return

        mode = self._normalize_normalization_fit_data_mode(selection.get("mode"))

        self._suspend_normalization_events = True
        try:
            if hasattr(self, "normalization_fit_data_use_sliders") and isinstance(
                selection.get("use_sliders"), (bool, int, float)
            ):
                self.normalization_fit_data_use_sliders.value = bool(selection.get("use_sliders"))
            self.normalization_fit_data_selection_mode.value = mode
            if self._is_normalization_fit_data_manual_mode(mode):
                if hasattr(self, "normalization_fit_data_q_min") and isinstance(selection.get("q_min"), (int, float)):
                    self.normalization_fit_data_q_min.value = float(selection["q_min"])
                if hasattr(self, "normalization_fit_data_q_max") and isinstance(selection.get("q_max"), (int, float)):
                    self.normalization_fit_data_q_max.value = float(selection["q_max"])
                if hasattr(self, "normalization_fit_data_y_min") and isinstance(selection.get("y_min"), (int, float)):
                    self.normalization_fit_data_y_min.value = float(selection["y_min"])
                if hasattr(self, "normalization_fit_data_y_max") and isinstance(selection.get("y_max"), (int, float)):
                    self.normalization_fit_data_y_max.value = float(selection["y_max"])
            else:
                if hasattr(self, "normalization_fit_data_q_tail_low") and isinstance(
                    selection.get("q_tail_low"), (int, float)
                ):
                    self.normalization_fit_data_q_tail_low.value = float(selection["q_tail_low"])
                if hasattr(self, "normalization_fit_data_q_tail_high") and isinstance(
                    selection.get("q_tail_high"), (int, float)
                ):
                    self.normalization_fit_data_q_tail_high.value = float(selection["q_tail_high"])
                if hasattr(self, "normalization_fit_data_min_percentile") and isinstance(
                    selection.get("min_percentile"), (int, float)
                ):
                    self.normalization_fit_data_min_percentile.value = int(selection["min_percentile"])
                if hasattr(self, "normalization_fit_data_max_percentile") and isinstance(
                    selection.get("max_percentile"), (int, float)
                ):
                    self.normalization_fit_data_max_percentile.value = int(selection["max_percentile"])
        finally:
            self._suspend_normalization_events = False

        self._set_normalization_fit_data_controls_visibility()
        # Ensure the currently active controls (sliders or inputs) reflect the loaded values.
        self._on_normalization_fit_data_controls_change()

    def _set_normalization_fit_data_controls_visibility(self) -> None:
        if not hasattr(self, "normalization_fit_data_selection_mode"):
            return
        mode = self._normalize_normalization_fit_data_mode(
            getattr(self.normalization_fit_data_selection_mode, "value", "")
        )
        define_mode = not self._is_normalization_fit_data_manual_mode(mode)
        use_sliders = bool(getattr(getattr(self, "normalization_fit_data_use_sliders", None), "value", False))

        if hasattr(self, "normalization_fit_data_vertical_axis_controls"):
            self.normalization_fit_data_vertical_axis_controls.visible = bool(use_sliders)
        if hasattr(self, "normalization_fit_data_horizontal_axis_controls"):
            self.normalization_fit_data_horizontal_axis_controls.visible = bool(use_sliders)

        # Redesign visibility: one Q slider set for both methods.
        for name in (
            "normalization_fit_data_redesign_horizontal_axis_controls",
            "normalization_fit_data_redesign_vertical_axis_controls",
            "normalization_fit_data_redesign_q_range_slider",
        ):
            if hasattr(self, name):
                getattr(self, name).visible = True

        if hasattr(self, "normalization_fit_data_redesign_vertical_range_slider"):
            self.normalization_fit_data_redesign_vertical_range_slider.visible = True

        if hasattr(self, "normalization_fit_data_define_controls"):
            self.normalization_fit_data_define_controls.visible = bool(define_mode and not use_sliders)
        if hasattr(self, "normalization_fit_data_hardcoded_controls"):
            self.normalization_fit_data_hardcoded_controls.visible = bool((not define_mode) and not use_sliders)

        # Define mode: toggle inputs vs sliders
        for name in (
            "normalization_fit_data_q_tail_low",
            "normalization_fit_data_q_tail_high",
            "normalization_fit_data_min_percentile",
            "normalization_fit_data_max_percentile",
        ):
            if hasattr(self, name):
                getattr(self, name).visible = bool(define_mode and not use_sliders)
        for name in (
            "normalization_fit_data_q_tail_low_slider",
            "normalization_fit_data_q_tail_high_slider",
            "normalization_fit_data_min_percentile_slider",
            "normalization_fit_data_max_percentile_slider",
        ):
            if hasattr(self, name):
                getattr(self, name).visible = bool(define_mode and use_sliders)

        # Hardcoded mode: toggle inputs vs sliders
        for name in (
            "normalization_fit_data_q_min",
            "normalization_fit_data_q_max",
            "normalization_fit_data_y_min",
            "normalization_fit_data_y_max",
        ):
            if hasattr(self, name):
                getattr(self, name).visible = bool((not define_mode) and not use_sliders)
        for name in (
            "normalization_fit_data_q_min_slider",
            "normalization_fit_data_q_max_slider",
            "normalization_fit_data_y_min_slider",
            "normalization_fit_data_y_max_slider",
        ):
            if hasattr(self, name):
                getattr(self, name).visible = bool((not define_mode) and use_sliders)
        self._sync_normalization_fit_data_ui_summary()
        self._sync_normalization_fit_data_redesign_buttons()
        self._update_normalization_fit_data_redesign_value_labels()

    def _on_normalization_fit_data_use_sliders_change(self, event) -> None:
        if getattr(self, "_suspend_normalization_events", False) or self.current_project_state is None:
            return
        if event.new == event.old:
            return
        self._set_normalization_fit_data_controls_visibility()
        # Keep values consistent when switching modes.
        self._on_normalization_fit_data_controls_change()

    def _on_normalization_fit_data_selection_mode_change(self, event) -> None:
        if getattr(self, "_suspend_normalization_events", False) or self.current_project_state is None:
            return
        if event.new == event.old:
            return
        self._set_normalization_fit_data_controls_visibility()
        self._persist_normalization_fit_data_selection_to_context()
        self._refresh_normalization_fit_data_placeholder()

        current_snap = self._normalization_fit_data_selection_snapshot_fit_relevant()
        last_seen = getattr(self, "_normalization_fit_last_seen_selection_snapshot", None)
        if not isinstance(last_seen, dict):
            self._normalization_fit_last_seen_selection_snapshot = current_snap
        elif last_seen != current_snap:
            self._normalization_fit_last_seen_selection_snapshot = current_snap
            if self._normalization_current_last_fit() is not None:
                self._invalidate_normalization_fit_result(reason="fit_data_selection_mode_changed")

    def _toggle_normalization_fit_data_redesign_input_mode(self, _event=None) -> None:
        if self.current_project_state is None:
            return
        toggle = getattr(self, "normalization_fit_data_use_sliders", None)
        if toggle is None:
            return
        toggle.value = not bool(getattr(toggle, "value", False))

    def _toggle_normalization_fit_data_redesign_method(self, _event=None) -> None:
        if self.current_project_state is None:
            return
        selector = getattr(self, "normalization_fit_data_selection_mode", None)
        if selector is None:
            return
        mode = self._normalize_normalization_fit_data_mode(getattr(selector, "value", ""))
        selector.value = (
            self._NORMALIZATION_FIT_DATA_MODE_PERCENTILE
            if self._is_normalization_fit_data_manual_mode(mode)
            else self._NORMALIZATION_FIT_DATA_MODE_MANUAL
        )

    def _on_normalization_fit_data_controls_change(self, event=None) -> None:
        if getattr(self, "_suspend_normalization_events", False) or self.current_project_state is None:
            return
        use_sliders = bool(getattr(getattr(self, "normalization_fit_data_use_sliders", None), "value", False))

        pairs = [
            ("normalization_fit_data_q_tail_low", "normalization_fit_data_q_tail_low_slider"),
            ("normalization_fit_data_q_tail_high", "normalization_fit_data_q_tail_high_slider"),
            ("normalization_fit_data_min_percentile", "normalization_fit_data_min_percentile_slider"),
            ("normalization_fit_data_max_percentile", "normalization_fit_data_max_percentile_slider"),
            ("normalization_fit_data_q_min", "normalization_fit_data_q_min_slider"),
            ("normalization_fit_data_q_max", "normalization_fit_data_q_max_slider"),
            ("normalization_fit_data_y_min", "normalization_fit_data_y_min_slider"),
            ("normalization_fit_data_y_max", "normalization_fit_data_y_max_slider"),
        ]
        range_slider_names = (
            "normalization_fit_data_redesign_q_range_slider",
            "normalization_fit_data_redesign_vertical_range_slider",
        )
        range_slider_sources = tuple(
            getattr(self, name) for name in range_slider_names if hasattr(self, name)
        )
        src = getattr(event, "obj", None) if event is not None else None
        event_name = str(getattr(event, "name", "") or "") if event is not None else ""
        is_slider_value_event = bool(
            use_sliders
            and src is not None
            and event_name == "value"
            and (
                any(
                    hasattr(self, slider_name) and src is getattr(self, slider_name)
                    for _input_name, slider_name in pairs
                )
                or src in range_slider_sources
            )
        )

        self._suspend_normalization_events = True
        try:
            for input_name, slider_name in pairs:
                if not (hasattr(self, input_name) and hasattr(self, slider_name)):
                    continue
                input_widget = getattr(self, input_name)
                slider_widget = getattr(self, slider_name)

                # If sliders are active and the slider changed, propagate slider -> input.
                if use_sliders and src is slider_widget:
                    input_widget.value = slider_widget.value
                    continue
                # Otherwise keep slider in sync with the input.
                if src is input_widget or src is None:
                    slider_widget.value = input_widget.value

            vertical_range = getattr(self, "normalization_fit_data_redesign_vertical_range_slider", None)
            q_range = getattr(self, "normalization_fit_data_redesign_q_range_slider", None)

            if use_sliders and src is q_range:
                lower_value, upper_value = self._normalization_range_value(
                    q_range,
                    (
                        float(getattr(getattr(self, "normalization_fit_data_q_tail_low", None), "value", 0.0) or 0.0),
                        float(getattr(getattr(self, "normalization_fit_data_q_tail_high", None), "value", 0.0) or 0.0),
                    ),
                )
                if hasattr(self, "normalization_fit_data_q_tail_low"):
                    self.normalization_fit_data_q_tail_low.value = lower_value
                if hasattr(self, "normalization_fit_data_q_tail_high"):
                    self.normalization_fit_data_q_tail_high.value = upper_value

            if use_sliders and src is vertical_range:
                lower_value, upper_value = self._normalization_range_value(vertical_range, (0.0, 0.0))
                mode = self._normalize_normalization_fit_data_mode(
                    getattr(getattr(self, "normalization_fit_data_selection_mode", None), "value", "")
                )
                manual_mode = self._is_normalization_fit_data_manual_mode(mode)
                if manual_mode:
                    if hasattr(self, "normalization_fit_data_y_min"):
                        self.normalization_fit_data_y_min.value = float(lower_value)
                    if hasattr(self, "normalization_fit_data_y_max"):
                        self.normalization_fit_data_y_max.value = float(upper_value)
                else:
                    if hasattr(self, "normalization_fit_data_min_percentile"):
                        self.normalization_fit_data_min_percentile.value = int(lower_value)
                    if hasattr(self, "normalization_fit_data_max_percentile"):
                        self.normalization_fit_data_max_percentile.value = int(upper_value)

            if src in range_slider_sources:
                for input_name, slider_name in pairs:
                    if hasattr(self, input_name) and hasattr(self, slider_name):
                        getattr(self, slider_name).value = getattr(self, input_name).value

            if vertical_range is not None:
                mode = self._normalize_normalization_fit_data_mode(
                    getattr(getattr(self, "normalization_fit_data_selection_mode", None), "value", "")
                )
                manual_mode = self._is_normalization_fit_data_manual_mode(mode)
                if manual_mode:
                    lower_value = float(
                        getattr(getattr(self, "normalization_fit_data_y_min", None), "value", 0.0) or 0.0
                    )
                    upper_value = float(
                        getattr(getattr(self, "normalization_fit_data_y_max", None), "value", lower_value) or lower_value
                    )
                    lower_value = float(
                        np.clip(lower_value, float(vertical_range.start), float(vertical_range.end))
                    )
                    upper_value = float(np.clip(upper_value, lower_value, float(vertical_range.end)))
                    self._set_normalization_range_value(vertical_range, (lower_value, upper_value))
                else:
                    min_pct = int(
                        getattr(getattr(self, "normalization_fit_data_min_percentile", None), "value", 0) or 0
                    )
                    max_pct = int(
                        getattr(getattr(self, "normalization_fit_data_max_percentile", None), "value", 100) or 100
                    )
                    min_pct = int(np.clip(min_pct, 0, 100))
                    max_pct = int(np.clip(max_pct, min_pct, 100))
                    self._set_normalization_range_value(vertical_range, (min_pct, max_pct))

            # Keep legacy/manual Q window and percentile Q span unified.
            q_start_sources = (
                getattr(self, "normalization_fit_data_q_tail_low", None),
                getattr(self, "normalization_fit_data_q_tail_low_slider", None),
                q_range,
            )
            q_end_sources = (
                getattr(self, "normalization_fit_data_q_tail_high", None),
                getattr(self, "normalization_fit_data_q_tail_high_slider", None),
            )
            q_min_sources = (
                getattr(self, "normalization_fit_data_q_min", None),
                getattr(self, "normalization_fit_data_q_min_slider", None),
            )
            q_max_sources = (
                getattr(self, "normalization_fit_data_q_max", None),
                getattr(self, "normalization_fit_data_q_max_slider", None),
            )

            tail_changed = src is not None and (src in q_start_sources or src in q_end_sources)
            manual_changed = src is not None and (src in q_min_sources or src in q_max_sources)

            q_tail_start = float(getattr(getattr(self, "normalization_fit_data_q_tail_low", None), "value", 0.0) or 0.0)
            q_tail_end = float(getattr(getattr(self, "normalization_fit_data_q_tail_high", None), "value", 0.0) or 0.0)
            q_manual_start = float(getattr(getattr(self, "normalization_fit_data_q_min", None), "value", 0.0) or 0.0)
            q_manual_end = float(getattr(getattr(self, "normalization_fit_data_q_max", None), "value", 0.0) or 0.0)

            q_start_value = q_manual_start if (manual_changed and not tail_changed) else q_tail_start
            q_end_value = q_manual_end if (manual_changed and not tail_changed) else q_tail_end

            if hasattr(self, "normalization_fit_data_q_min"):
                self.normalization_fit_data_q_min.value = q_start_value
            if hasattr(self, "normalization_fit_data_q_min_slider"):
                self.normalization_fit_data_q_min_slider.value = q_start_value
            if hasattr(self, "normalization_fit_data_q_max"):
                self.normalization_fit_data_q_max.value = q_end_value
            if hasattr(self, "normalization_fit_data_q_max_slider"):
                self.normalization_fit_data_q_max_slider.value = q_end_value
            if hasattr(self, "normalization_fit_data_q_tail_low"):
                self.normalization_fit_data_q_tail_low.value = q_start_value
            if hasattr(self, "normalization_fit_data_q_tail_low_slider"):
                self.normalization_fit_data_q_tail_low_slider.value = q_start_value
            if hasattr(self, "normalization_fit_data_q_tail_high"):
                self.normalization_fit_data_q_tail_high.value = q_end_value
            if hasattr(self, "normalization_fit_data_q_tail_high_slider"):
                self.normalization_fit_data_q_tail_high_slider.value = q_end_value
            if q_range is not None:
                self._set_normalization_range_value(q_range, (q_start_value, q_end_value))
        finally:
            self._suspend_normalization_events = False

        # Avoid expensive redraw/layout churn while dragging sliders:
        # - keep widgets in sync live
        # - refresh the plot at a limited rate
        # - persist only on discrete changes or slider commit (value_throttled)
        if is_slider_value_event:
            current_snap = self._normalization_fit_data_selection_snapshot_fit_relevant()
            last_seen = getattr(self, "_normalization_fit_last_seen_selection_snapshot", None)
            if not isinstance(last_seen, dict):
                self._normalization_fit_last_seen_selection_snapshot = current_snap
            elif last_seen != current_snap:
                self._normalization_fit_last_seen_selection_snapshot = current_snap
                if self._normalization_current_last_fit() is not None:
                    self._invalidate_normalization_fit_result(reason="fit_data_selection_changed")
            self._update_normalization_fit_data_redesign_value_labels()
            self._schedule_normalization_fit_data_plot_refresh(delay_ms=75)
            return

        self._persist_normalization_fit_data_selection_to_context()
        self._refresh_normalization_fit_data_placeholder()
        self._sync_normalization_fit_data_redesign_buttons()
        self._update_normalization_fit_data_redesign_value_labels()

        current_snap = self._normalization_fit_data_selection_snapshot_fit_relevant()
        last_seen = getattr(self, "_normalization_fit_last_seen_selection_snapshot", None)
        if not isinstance(last_seen, dict):
            self._normalization_fit_last_seen_selection_snapshot = current_snap
        elif last_seen != current_snap:
            self._normalization_fit_last_seen_selection_snapshot = current_snap
            if self._normalization_current_last_fit() is not None:
                self._invalidate_normalization_fit_result(reason="fit_data_selection_changed")

    def _on_normalization_fit_data_controls_commit(self, event=None) -> None:
        if getattr(self, "_suspend_normalization_events", False) or self.current_project_state is None:
            return
        use_sliders = bool(getattr(getattr(self, "normalization_fit_data_use_sliders", None), "value", False))
        if not use_sliders or event is None:
            self._persist_normalization_fit_data_selection_to_context()
            return

        src = getattr(event, "obj", None)
        if src is None:
            self._persist_normalization_fit_data_selection_to_context()
            return

        pairs = [
            ("normalization_fit_data_q_tail_low", "normalization_fit_data_q_tail_low_slider"),
            ("normalization_fit_data_q_tail_high", "normalization_fit_data_q_tail_high_slider"),
            ("normalization_fit_data_min_percentile", "normalization_fit_data_min_percentile_slider"),
            ("normalization_fit_data_max_percentile", "normalization_fit_data_max_percentile_slider"),
            ("normalization_fit_data_q_min", "normalization_fit_data_q_min_slider"),
            ("normalization_fit_data_q_max", "normalization_fit_data_q_max_slider"),
            ("normalization_fit_data_y_min", "normalization_fit_data_y_min_slider"),
            ("normalization_fit_data_y_max", "normalization_fit_data_y_max_slider"),
        ]

        self._suspend_normalization_events = True
        try:
            vertical_range = getattr(self, "normalization_fit_data_redesign_vertical_range_slider", None)
            q_range = getattr(self, "normalization_fit_data_redesign_q_range_slider", None)

            if src is q_range:
                lower_value, upper_value = self._normalization_range_value(
                    q_range,
                    (
                        float(getattr(getattr(self, "normalization_fit_data_q_tail_low", None), "value", 0.0) or 0.0),
                        float(getattr(getattr(self, "normalization_fit_data_q_tail_high", None), "value", 0.0) or 0.0),
                    ),
                )
                if hasattr(self, "normalization_fit_data_q_tail_low"):
                    self.normalization_fit_data_q_tail_low.value = lower_value
                if hasattr(self, "normalization_fit_data_q_tail_high"):
                    self.normalization_fit_data_q_tail_high.value = upper_value

            if src is vertical_range:
                lower_value, upper_value = self._normalization_range_value(vertical_range, (0.0, 0.0))
                mode = self._normalize_normalization_fit_data_mode(
                    getattr(getattr(self, "normalization_fit_data_selection_mode", None), "value", "")
                )
                manual_mode = self._is_normalization_fit_data_manual_mode(mode)
                if manual_mode:
                    if hasattr(self, "normalization_fit_data_y_min"):
                        self.normalization_fit_data_y_min.value = float(lower_value)
                    if hasattr(self, "normalization_fit_data_y_max"):
                        self.normalization_fit_data_y_max.value = float(upper_value)
                else:
                    if hasattr(self, "normalization_fit_data_min_percentile"):
                        self.normalization_fit_data_min_percentile.value = int(lower_value)
                    if hasattr(self, "normalization_fit_data_max_percentile"):
                        self.normalization_fit_data_max_percentile.value = int(upper_value)

            for input_name, slider_name in pairs:
                if not (hasattr(self, input_name) and hasattr(self, slider_name)):
                    continue
                slider_widget = getattr(self, slider_name)
                if src is slider_widget:
                    getattr(self, input_name).value = getattr(slider_widget, "value", None)
                    break

            if vertical_range is not None:
                mode = self._normalize_normalization_fit_data_mode(
                    getattr(getattr(self, "normalization_fit_data_selection_mode", None), "value", "")
                )
                manual_mode = self._is_normalization_fit_data_manual_mode(mode)
                if manual_mode:
                    lower_value = float(
                        getattr(getattr(self, "normalization_fit_data_y_min", None), "value", 0.0) or 0.0
                    )
                    upper_value = float(
                        getattr(getattr(self, "normalization_fit_data_y_max", None), "value", lower_value) or lower_value
                    )
                    lower_value = float(
                        np.clip(lower_value, float(vertical_range.start), float(vertical_range.end))
                    )
                    upper_value = float(np.clip(upper_value, lower_value, float(vertical_range.end)))
                    self._set_normalization_range_value(vertical_range, (lower_value, upper_value))
                else:
                    min_pct = int(
                        getattr(getattr(self, "normalization_fit_data_min_percentile", None), "value", 0) or 0
                    )
                    max_pct = int(
                        getattr(getattr(self, "normalization_fit_data_max_percentile", None), "value", 100) or 100
                    )
                    min_pct = int(np.clip(min_pct, 0, 100))
                    max_pct = int(np.clip(max_pct, min_pct, 100))
                    self._set_normalization_range_value(vertical_range, (min_pct, max_pct))

            q_start_value = float(getattr(getattr(self, "normalization_fit_data_q_tail_low", None), "value", 0.0) or 0.0)
            q_end_value = float(getattr(getattr(self, "normalization_fit_data_q_tail_high", None), "value", 0.0) or 0.0)
            if hasattr(self, "normalization_fit_data_q_min"):
                self.normalization_fit_data_q_min.value = q_start_value
            if hasattr(self, "normalization_fit_data_q_min_slider"):
                self.normalization_fit_data_q_min_slider.value = q_start_value
            if hasattr(self, "normalization_fit_data_q_max"):
                self.normalization_fit_data_q_max.value = q_end_value
            if hasattr(self, "normalization_fit_data_q_max_slider"):
                self.normalization_fit_data_q_max_slider.value = q_end_value
            if hasattr(self, "normalization_fit_data_q_tail_low"):
                self.normalization_fit_data_q_tail_low.value = q_start_value
            if hasattr(self, "normalization_fit_data_q_tail_low_slider"):
                self.normalization_fit_data_q_tail_low_slider.value = q_start_value
            if hasattr(self, "normalization_fit_data_q_tail_high"):
                self.normalization_fit_data_q_tail_high.value = q_end_value
            if hasattr(self, "normalization_fit_data_q_tail_high_slider"):
                self.normalization_fit_data_q_tail_high_slider.value = q_end_value
            if q_range is not None:
                self._set_normalization_range_value(q_range, (q_start_value, q_end_value))
        finally:
            self._suspend_normalization_events = False

        self._persist_normalization_fit_data_selection_to_context()
        self._refresh_normalization_fit_data_placeholder()
        self._sync_normalization_fit_data_redesign_buttons()
        self._update_normalization_fit_data_redesign_value_labels()

    def _refresh_normalization_fit_data_placeholder(self) -> None:
        if self.current_project_root is None or self.current_project_state is None:
            return
        primary_plot_pane = getattr(self, "normalization_fit_data_plot_pane", None)
        redesign_plot_pane = getattr(self, "normalization_fit_data_redesign_plot_pane", None)

        # IMPORTANT: The redesign plot must be independent from the legacy
        # "Selection Workspace" plot. Do not read from or write to the legacy
        # plot when the redesign plot exists, otherwise its figure/layout can
        # leak into the redesign view (e.g. shrinking the fixed-size plot).
        if redesign_plot_pane is not None:
            plot_panes = [redesign_plot_pane]
        elif primary_plot_pane is not None:
            plot_panes = [primary_plot_pane]
        else:
            return

        status_pane = getattr(self, "normalization_fit_data_status", None)
        alert_pane = getattr(self, "normalization_fit_data_alert", None)
        legacy_pane = getattr(self, "normalization_fit_data_plot_placeholder", None)
        plot_pane = plot_panes[0]

        def _set_plot_object(value) -> None:
            for pane in plot_panes:
                pane.object = value

        def _trigger_plot_update() -> None:
            for pane in plot_panes:
                try:
                    pane.param.trigger("object")
                except Exception:
                    pass

        def _set_status(markdown: str) -> None:
            if status_pane is not None:
                status_pane.object = markdown
                return
            if legacy_pane is not None:
                legacy_pane.object = markdown
                try:
                    legacy_pane.alert_type = "secondary"
                except Exception:
                    pass

        window_table_pane = getattr(self, "normalization_fit_data_redesign_window_table", None)

        def _set_window_table(html: str) -> None:
            if window_table_pane is None:
                return
            window_table_pane.object = html

        def _set_alert(message: str, *, alert_type: str, visible: bool = True) -> None:
            if alert_pane is not None:
                alert_pane.visible = bool(visible)
                alert_pane.object = message if visible else ""
                alert_pane.alert_type = alert_type
                return
            if legacy_pane is not None:
                legacy_pane.object = message if visible else ""
                try:
                    legacy_pane.alert_type = alert_type
                except Exception:
                    pass
        context_id = str(getattr(getattr(self, "normalization_context_select", None), "value", "") or "").strip()
        if not context_id:
            _set_status("Select a background context to proceed.")
            _set_alert("", alert_type="secondary", visible=False)
            _set_plot_object(None)
            _set_window_table("")
            return

        manifest_ref = ""
        if hasattr(self, "_selected_normalization_manifest_ref"):
            manifest_ref = str(self._selected_normalization_manifest_ref() or "").strip()
        if not manifest_ref:
            _set_status("Selected context has no manifest path.")
            _set_alert("Selected context has no manifest path.", alert_type="danger", visible=True)
            _set_plot_object(None)
            _set_window_table("")
            return

        payload = load_context_manifest(self.current_project_root, manifest_ref)
        artifacts = payload.get("artifacts") if isinstance(payload, dict) else {}
        van_ref = artifacts.get("vanadium_sub_qdat") if isinstance(artifacts, dict) else None
        if not isinstance(van_ref, str) or not van_ref.strip():
            _set_status("Selected context has no `vanadium_sub_qdat` reference.")
            _set_alert("Selected context has no `vanadium_sub_qdat` reference.", alert_type="danger", visible=True)
            _set_plot_object(None)
            _set_window_table("")
            return

        try:
            van_path = resolve_project_path(self.current_project_root, van_ref)
        except Exception:
            _set_status("Vanadium qdat reference could not be resolved.")
            _set_alert("Vanadium qdat reference could not be resolved.", alert_type="danger", visible=True)
            _set_plot_object(None)
            _set_window_table("")
            return

        if not van_path.exists():
            message = f"Missing data: `vanadium_sub.qdat` not found at `{van_path}`"
            _set_status(message)
            _set_alert(message, alert_type="danger", visible=True)
            _set_plot_object(None)
            _set_window_table("")
            return

        try:
            q_all, y_all, _e_all = self._read_xye_cached(van_path)
        except Exception as exc:
            message = f"Could not load `vanadium_sub.qdat`: {exc}"
            _set_status(message)
            _set_alert(message, alert_type="danger", visible=True)
            _set_plot_object(None)
            _set_window_table("")
            return

        q_subset = None
        y_subset = None
        warning: str | None = None
        selection_summary_bits: list[str] = []
        q_focus_min: float | None = None
        q_focus_max: float | None = None
        y_axis_min: float | None = None
        y_axis_max: float | None = None

        try:
            self._sync_normalization_fit_data_slider_limits(q_all=q_all, y_all=y_all)
        except Exception:
            pass

        mode = self._normalize_normalization_fit_data_mode(
            getattr(self.normalization_fit_data_selection_mode, "value", "")
        )
        if self._is_normalization_fit_data_manual_mode(mode):
            q_min = float(getattr(getattr(self, "normalization_fit_data_q_min", None), "value", 0.0) or 0.0)
            q_max = float(getattr(getattr(self, "normalization_fit_data_q_max", None), "value", 0.0) or 0.0)
            y_min = float(getattr(getattr(self, "normalization_fit_data_y_min", None), "value", 0.0) or 0.0)
            y_max = float(getattr(getattr(self, "normalization_fit_data_y_max", None), "value", 0.0) or 0.0)
            q_focus_min = q_min
            q_focus_max = q_max
            y_axis_min = y_min
            y_axis_max = y_max
            if q_max < q_min:
                warning = "Manual window has `q_max < q_min`."
            if y_max < y_min:
                warning = "Manual window has `y_max < y_min`."
            mask = (q_all >= q_min) & (q_all <= q_max) & (y_all >= y_min) & (y_all <= y_max)
            q_subset = q_all[mask]
            y_subset = y_all[mask]
        else:
            q_tail_low = float(getattr(getattr(self, "normalization_fit_data_q_tail_low", None), "value", 0.0) or 0.0)
            q_tail_high = float(getattr(getattr(self, "normalization_fit_data_q_tail_high", None), "value", 0.0) or 0.0)
            min_pct = int(getattr(getattr(self, "normalization_fit_data_min_percentile", None), "value", 0) or 0)
            max_pct = int(getattr(getattr(self, "normalization_fit_data_max_percentile", None), "value", 0) or 0)
            q_focus_min = q_tail_low
            q_focus_max = q_tail_high
            if q_tail_high < q_tail_low:
                warning = "Percentile band has `Q end < Q start`."
            if max_pct < min_pct:
                warning = "Percentile band has `upper percentile < lower percentile`."
            try:
                y_min = float(np.percentile(y_all, min_pct))
                y_max = float(np.percentile(y_all, max_pct))
            except Exception as exc:
                message = f"Could not compute percentiles: {exc}"
                _set_status(message)
                _set_alert(message, alert_type="danger", visible=True)
                _set_plot_object(None)
                return
            y_axis_min = y_min
            y_axis_max = y_max
            mask = (q_all >= q_tail_low) & (q_all <= q_tail_high) & (y_all >= y_min) & (y_all <= y_max)
            q_subset = q_all[mask]
            y_subset = y_all[mask]
            selection_summary_bits.append(f"Q span: [{q_tail_low:.4g}, {q_tail_high:.4g}]")
            selection_summary_bits.append(f"Intensity percentile band: {min_pct}-{max_pct} -> [{y_min:.4g}, {y_max:.4g}]")

        try:
            import plotly.graph_objects as go

            current = plot_pane.object
            source_token = str(van_path)
            previous_source = getattr(self, "_normalization_fit_data_plot_source", None)
            if not isinstance(previous_source, str):
                previous_source = None

            # If the underlying dataset changes (e.g. the user selects a different context),
            # rebuild the figure so the Plotly "Home" view is recalculated from the new data.
            if isinstance(current, go.Figure) and previous_source == source_token:
                update_vanadium_fit_selection_figure(
                    current,
                    q_all=q_all,
                    y_all=y_all,
                    q_subset=q_subset,
                    y_subset=y_subset,
                    title=None, # keep this as None to avoid being redundant with table summary
                    q_focus_min=q_focus_min,
                    q_focus_max=q_focus_max,
                    y_axis_min=y_axis_min,
                    y_axis_max=y_axis_max,
                    width=int(getattr(plot_pane, "width", 0) or 0) or None,
                    height=int(getattr(plot_pane, "height", 0) or 0) or None,
                )
                _trigger_plot_update()
            else:
                fig = build_vanadium_fit_selection_figure(
                    q_all=q_all,
                    y_all=y_all,
                    q_subset=q_subset,
                    y_subset=y_subset,
                    title=None, # keep this as None to avoid being redundant with table summary
                    q_focus_min=q_focus_min,
                    q_focus_max=q_focus_max,
                    y_axis_min=y_axis_min,
                    y_axis_max=y_axis_max,
                    width=int(getattr(plot_pane, "width", 0) or 0) or None,
                    height=int(getattr(plot_pane, "height", 0) or 0) or None,
                )
                _set_plot_object(fig)
                self._normalization_fit_data_plot_source = source_token
        except Exception:
            _set_plot_object(build_vanadium_fit_selection_figure(
                q_all=q_all,
                y_all=y_all,
                q_subset=q_subset,
                y_subset=y_subset,
                title=None, # keep this as None to avoid being redundant with table summary
                q_focus_min=q_focus_min,
                q_focus_max=q_focus_max,
                y_axis_min=y_axis_min,
                y_axis_max=y_axis_max,
                width=int(getattr(plot_pane, "width", 0) or 0) or None,
                height=int(getattr(plot_pane, "height", 0) or 0) or None,
            ))

        n_total = int(np.size(q_all))
        n_selected = int(np.size(q_subset)) if q_subset is not None else 0
        frac = (float(n_selected) / float(n_total)) if n_total else 0.0

        def _fmt_float(value: float | None) -> str:
            if value is None or not np.isfinite(value):
                return "—"
            return f"{float(value):.2f}"
        
        def _fmt_path(path: str | None) -> str:

            _, keyword, after = path.partition("processed")
            if keyword:
                path = keyword + after
            else:
                path = path
            
            return path

        mode_label = self._normalization_fit_data_mode_label(mode)
        q_summary = f"[{_fmt_float(q_focus_min)}, {_fmt_float(q_focus_max)}]"
        if self._is_normalization_fit_data_manual_mode(mode):
            y_summary = f"[{_fmt_float(y_axis_min)}, {_fmt_float(y_axis_max)}]"
        else:
            y_summary = f"{min_pct}–{max_pct} → [{_fmt_float(y_axis_min)}, {_fmt_float(y_axis_max)}]"

        def _row(label: str, value: str) -> str:
            return (
                "<tr>"
                f"<td class=\"toscana-fit-result-table__param\">{html_escape(label)}</td>"
                f"<td class=\"toscana-fit-result-table__value\" style=\"text-align:left;\">{value}</td>"
                "</tr>"
            )

        def _fmt_compact_6g(value: float | None) -> str:
            if value is None or not np.isfinite(value):
                return "—"
            return f"{float(value):.6g}"

        rows = [
            _row("Mode", html_escape(mode_label)),
            _row("Q min", f"<code>{html_escape(_fmt_compact_6g(q_focus_min))}</code>"),
            _row("Q max", f"<code>{html_escape(_fmt_compact_6g(q_focus_max))}</code>"),
            _row("Y min", f"<code>{html_escape(_fmt_compact_6g(y_axis_min))}</code>"),
            _row("Y max", f"<code>{html_escape(_fmt_compact_6g(y_axis_max))}</code>"),
            _row("Fit points", f"<code>{n_selected}</code>"),
        ]

        _set_window_table(
            "<div class=\"toscana-fit-window-table\">"
            "<table class=\"toscana-fit-result-table\">"
            "<thead><tr><th>Field</th><th>Value</th></tr></thead>"
            "<tbody>"
            + "".join(rows)
            + "</tbody></table></div>"
        )

        safe_path = str(_fmt_path(str(van_path))).replace("`", "\\`")
        _set_status(
            "\n".join(
                [
                    "### Vanadium fitting window",
                    "",
                    "| Field | Value |",
                    "|---|---|",
                    f"| File | `{safe_path}` |",
                    f"| Selected points | **{n_selected} / {n_total}** ({frac:.1%}) |",
                    f"| Selection mode | {mode_label} |",
                    f"| Q window | {q_summary} |",
                    f"| Intensity window | {y_summary} |",
                ]
            )
        )

        if n_selected == 0:
            _set_alert("No points selected with the current window.", alert_type="warning", visible=True)
        elif warning:
            _set_alert(warning, alert_type="warning", visible=True)
        else:
            _set_alert("", alert_type="secondary", visible=False)

    @staticmethod
    def _format_context_timestamp(value: object) -> str:
        raw = str(value).strip() if value is not None else ""
        if not raw:
            return ""
        try:
            parsed = datetime.fromisoformat(raw)
            return parsed.strftime("%Y-%m-%d %H:%M")
        except Exception:
            return raw

    def _load_normalization_state_into_widgets(self) -> None:
        if self.current_project_state is None or self.current_project_root is None:
            return
        self._set_normalization_fit_data_controls_visibility()
        self._set_normalization_source_widget_visibility()
        self._refresh_normalization_qdat_dropdown_options()
        self._refresh_normalization_context_options(apply_selection=True)
        self._refresh_normalization_context_summary()
        self._load_normalization_fit_data_selection_from_context()
        self._load_normalization_fit_params_from_context()
        self._load_normalization_fit_last_from_context()
        self._refresh_normalization_fit_data_placeholder()
        self._refresh_normalization_fit_params_button_states()

    def _on_normalization_custom_files_switch_change(self, event) -> None:
        if getattr(self, "_suspend_normalization_events", False) or self.current_project_state is None:
            return
        if event.new == event.old:
            return
        self._clear_normalization_import_prompt()
        self._clear_normalization_adopt_prompt()
        try:
            enabled = bool(event.new)
            self._show_info_toast("Custom qdat selection enabled." if enabled else "Custom qdat selection disabled.")
        except Exception:
            pass

        self._sync_normalization_custom_files_ui()
        self._refresh_normalization_fit_data_placeholder()
        self._render_current_screen()

    def _toggle_normalization_custom_files_override(self, event=None) -> None:
        if self.current_project_state is None:
            return
        if getattr(getattr(self, "normalization_custom_files_toggle_button", None), "disabled", False):
            return
        if not hasattr(self, "normalization_custom_files_switch"):
            return
        current = bool(getattr(self.normalization_custom_files_switch, "value", False))
        self.normalization_custom_files_switch.value = not current

    def _sync_normalization_custom_files_ui(self) -> None:
        button = getattr(self, "normalization_custom_files_toggle_button", None)
        badge = getattr(self, "normalization_custom_files_state_badge", None)
        if button is None and badge is None:
            return
        enabled = bool(getattr(getattr(self, "normalization_custom_files_switch", None), "value", False))
        if button is not None:
            button.name = "Switch Mode"
            button.button_type = "warning" if enabled else "primary"
        if badge is not None:
            badge.object = (
                "<div class=\"toscana-normalization-source-state-list\">"
                f"<div class=\"toscana-normalization-source-state toscana-normalization-source-state--context {'toscana-normalization-source-state--active' if not enabled else 'toscana-normalization-source-state--inactive'}\">"
                "Resolved context source"
                "</div>"
                f"<div class=\"toscana-normalization-source-state toscana-normalization-source-state--override {'toscana-normalization-source-state--active' if enabled else 'toscana-normalization-source-state--inactive'}\">"
                "Custom Selection"
                "</div>"
                "</div>"
            )

    def _set_normalization_source_widget_visibility(self) -> None:
        if not hasattr(self, "normalization_source_mode"):
            return
        select_mode = getattr(self.normalization_source_mode, "value", "Select File") == "Select File"
        if hasattr(self, "normalization_dropdown_column"):
            self.normalization_dropdown_column.visible = bool(select_mode)
        if hasattr(self, "normalization_path_column"):
            self.normalization_path_column.visible = not bool(select_mode)

    def _on_normalization_source_mode_change(self, event) -> None:
        if getattr(self, "_suspend_normalization_events", False) or self.current_project_state is None:
            return
        if event.new == event.old:
            return
        self._clear_normalization_import_prompt()
        self._clear_normalization_adopt_prompt()
        self._set_normalization_source_widget_visibility()
        self._refresh_interaction_states()

    def _refresh_normalization_qdat_dropdown_options(self) -> None:
        if self.current_project_root is None:
            return
        if not hasattr(self, "normalization_sample_qdat_dropdown") or not hasattr(
            self, "normalization_vanadium_qdat_dropdown"
        ):
            return

        sample_files = list_sample_qdat_files(self.current_project_root)
        vanadium_files = list_vanadium_qdat_files(self.current_project_root)

        if sample_files:
            sample_options = {p.name: str(p.resolve(strict=False)) for p in sample_files}
        else:
            sample_options = {"No sample qdat files found in processed/qspdata/.": ""}
        if vanadium_files:
            vanadium_options = {p.name: str(p.resolve(strict=False)) for p in vanadium_files}
        else:
            vanadium_options = {"Missing `vanadium_sub.qdat` in processed/qspdata/.": ""}

        self._suspend_normalization_events = True
        try:
            self.normalization_sample_qdat_dropdown.options = sample_options
            self.normalization_vanadium_qdat_dropdown.options = vanadium_options
            if (
                not self.normalization_sample_qdat_dropdown.value
                or self.normalization_sample_qdat_dropdown.value not in sample_options.values()
            ):
                self.normalization_sample_qdat_dropdown.value = next(iter(sample_options.values()))
            if (
                not self.normalization_vanadium_qdat_dropdown.value
                or self.normalization_vanadium_qdat_dropdown.value not in vanadium_options.values()
            ):
                self.normalization_vanadium_qdat_dropdown.value = next(iter(vanadium_options.values()))
        finally:
            self._suspend_normalization_events = False

    def _validate_normalization_selection(self, _event=None) -> None:
        if self.operation_in_progress:
            self._show_workspace_blocked_message()
            return
        if self.current_project_root is None or self.current_project_state is None:
            return

        sample_path, vanadium_path = self._get_normalization_candidate_paths()
        if sample_path is None or vanadium_path is None:
            self.normalization_selection_message.object = "Select both sample and vanadium qdat files first."
            self.normalization_selection_message.alert_type = "danger"
            self._render_current_screen()
            return

        self._pending_normalization_adopt = None
        self._clear_normalization_adopt_prompt()

        if not sample_path.exists() or not sample_path.is_file():
            self.normalization_selection_message.object = f"Sample qdat not found: `{sample_path}`"
            self.normalization_selection_message.alert_type = "danger"
            self._render_current_screen()
            return
        if not vanadium_path.exists() or not vanadium_path.is_file():
            self.normalization_selection_message.object = f"Vanadium qdat not found: `{vanadium_path}`"
            self.normalization_selection_message.alert_type = "danger"
            self._render_current_screen()
            return

        outside = []
        if not is_qdat_within_project(sample_path, self.current_project_root):
            outside.append(("sample", sample_path))
        if not is_qdat_within_project(vanadium_path, self.current_project_root):
            outside.append(("vanadium", vanadium_path))

        if outside:
            self._prompt_normalization_import(outside)
            self._render_current_screen()
            return

        self._clear_normalization_import_prompt()
        self._apply_normalization_selection(sample_path, vanadium_path)
        self._render_current_screen()

    def _get_normalization_candidate_paths(self) -> tuple[Path | None, Path | None]:
        if not hasattr(self, "normalization_source_mode"):
            return (None, None)

        if self.normalization_source_mode.value == "Select File":
            sample_raw = str(self.normalization_sample_qdat_dropdown.value or "").strip()
            van_raw = str(self.normalization_vanadium_qdat_dropdown.value or "").strip()
        else:
            sample_raw = str(self.normalization_sample_qdat_path_input.value or "").strip()
            van_raw = str(self.normalization_vanadium_qdat_path_input.value or "").strip()

        sample_path = Path(sample_raw).expanduser() if sample_raw else None
        van_path = Path(van_raw).expanduser() if van_raw else None
        return (sample_path, van_path)

    def _prompt_normalization_import(self, outside: list[tuple[str, Path]]) -> None:
        if self.current_project_root is None:
            return
        self._pending_normalization_import_paths = {label: path.resolve(strict=False) for label, path in outside}
        lines = [
            "One or more selected `.qdat` files are outside the current project.",
            "Copy them into `processed/qspdata/` to continue:",
            "",
        ]
        for label, path in outside:
            lines.append(f"- {label}: `{path}`")
        self.normalization_import_prompt.object = "\n".join(lines)
        self.normalization_import_prompt.alert_type = "warning"
        self.normalization_import_prompt.visible = True
        self.normalization_import_card.visible = True
        self.normalization_selection_message.object = "Copy selected files into the project to validate them."
        self.normalization_selection_message.alert_type = "warning"

    def _copy_normalization_files_into_project(self, _event=None) -> None:
        if self.operation_in_progress:
            self._show_workspace_blocked_message()
            return
        if self.current_project_root is None or self._pending_normalization_import_paths is None:
            return

        pending = dict(self._pending_normalization_import_paths)
        target_dir = ensure_qspdata_dir(self.current_project_root)

        copied: dict[str, Path] = {}
        conflicts = []
        for label, source_path in pending.items():
            target_path = target_dir / source_path.name
            if target_path.exists():
                conflicts.append(str(target_path))
            else:
                copied[label] = target_path

        if conflicts:
            self.normalization_selection_message.object = (
                "Import blocked because a file with the same name already exists in `processed/qspdata/`."
            )
            self.normalization_selection_message.alert_type = "danger"
            self.normalization_import_prompt.alert_type = "danger"
            self.normalization_import_prompt.object = "Import blocked due to naming conflicts."
            self.normalization_import_prompt.visible = True
            self.normalization_import_card.visible = True
            self._refresh_interaction_states()
            return

        for label, source_path in pending.items():
            target_path = target_dir / source_path.name
            copy2(source_path, target_path)
            copied[label] = target_path

        self._clear_normalization_import_prompt()

        sample_old, van_old = self._get_normalization_candidate_paths()
        sample_path = copied.get("sample") or sample_old
        van_path = copied.get("vanadium") or van_old
        if sample_path is None or van_path is None:
            self.normalization_selection_message.object = "Could not determine copied qdat paths."
            self.normalization_selection_message.alert_type = "danger"
            self._render_current_screen()
            return
        resolved_sample = str(sample_path.resolve(strict=False))
        resolved_van = str(van_path.resolve(strict=False))
        self._suspend_normalization_events = True
        try:
            self._refresh_normalization_qdat_dropdown_options()
            self.normalization_sample_qdat_dropdown.value = resolved_sample
            self.normalization_vanadium_qdat_dropdown.value = resolved_van
            self.normalization_sample_qdat_path_input.value = resolved_sample
            self.normalization_vanadium_qdat_path_input.value = resolved_van
        finally:
            self._suspend_normalization_events = False

        self._show_success_toast("qdat files copied into the project.")
        self._apply_normalization_selection(Path(resolved_sample), Path(resolved_van))
        self._render_current_screen()

    def _cancel_normalization_import(self, _event=None) -> None:
        if self.operation_in_progress:
            self._show_workspace_blocked_message()
            return
        self._clear_normalization_import_prompt()
        self.normalization_selection_message.object = "Import cancelled."
        self.normalization_selection_message.alert_type = "secondary"
        self._refresh_interaction_states()

    def _clear_normalization_import_prompt(self) -> None:
        self._pending_normalization_import_paths = None
        self.normalization_import_prompt.object = ""
        self.normalization_import_prompt.visible = False
        self.normalization_import_prompt.alert_type = "warning"
        self.normalization_import_card.visible = False

    def _clear_normalization_adopt_prompt(self) -> None:
        self._pending_normalization_adopt = None
        self.normalization_adopt_prompt.object = ""
        self.normalization_adopt_prompt.visible = False
        self.normalization_adopt_prompt.alert_type = "warning"
        self.normalization_adopt_card.visible = False

    def _apply_normalization_selection(self, sample_qdat: Path, vanadium_qdat: Path) -> None:
        if self.current_project_root is None or self.current_project_state is None:
            return

        matched = self._match_existing_context_for_qdat(sample_qdat, vanadium_qdat)
        if matched:
            state = self._get_background_state()
            contexts = state.get("contexts") if isinstance(state.get("contexts"), dict) else {}
            contexts["active_context_id"] = matched
            state["contexts"] = contexts
            self._persist_background_state(state)
            self._refresh_normalization_context_options(apply_selection=True)
            self._refresh_normalization_context_summary()
            self.normalization_selection_message.object = f"Matched existing context `{matched}`."
            self.normalization_selection_message.alert_type = "success"
            return

        self._pending_normalization_adopt = {
            "sample_qdat": str(sample_qdat.resolve(strict=False)),
            "vanadium_qdat": str(vanadium_qdat.resolve(strict=False)),
        }
        self.normalization_adopt_prompt.object = (
            "Selected qdat files do not match an existing context. "
            "Create a new context entry (no recomputation) to proceed."
        )
        self.normalization_adopt_prompt.alert_type = "warning"
        self.normalization_adopt_prompt.visible = True
        self.normalization_adopt_card.visible = True
        self.normalization_selection_message.object = "Context not found. Confirm to create one."
        self.normalization_selection_message.alert_type = "warning"

    def _match_existing_context_for_qdat(self, sample_qdat: Path, vanadium_qdat: Path) -> str | None:
        if self.current_project_root is None:
            return None
        state = self._get_background_state()
        contexts = state.get("contexts") if isinstance(state.get("contexts"), dict) else {}
        entries = contexts.get("entries") if isinstance(contexts.get("entries"), list) else []

        try:
            sample_abs = sample_qdat.expanduser().resolve(strict=False)
            van_abs = vanadium_qdat.expanduser().resolve(strict=False)
        except Exception:
            return None

        for entry in entries:
            if not isinstance(entry, dict):
                continue
            context_id = str(entry.get("context_id") or "").strip()
            manifest_ref = str(entry.get("manifest") or "").strip()
            if not context_id or not manifest_ref:
                continue
            payload = load_context_manifest(self.current_project_root, manifest_ref)
            if not isinstance(payload, dict):
                continue
            artifacts = payload.get("artifacts") if isinstance(payload.get("artifacts"), dict) else {}
            sample_ref = artifacts.get("sample_sub_qdat")
            van_ref = artifacts.get("vanadium_sub_qdat")
            if not isinstance(sample_ref, str) or not isinstance(van_ref, str):
                continue
            try:
                sample_ctx = resolve_project_path(self.current_project_root, sample_ref)
                van_ctx = resolve_project_path(self.current_project_root, van_ref)
            except Exception:
                continue
            if sample_ctx.resolve(strict=False) == sample_abs and van_ctx.resolve(strict=False) == van_abs:
                return context_id
        return None

    def _confirm_normalization_adopt(self, _event=None) -> None:
        if self.operation_in_progress:
            self._show_workspace_blocked_message()
            return
        if self.current_project_root is None or self.current_project_state is None:
            return
        pending = self._pending_normalization_adopt
        if not isinstance(pending, dict):
            return

        sample_qdat = str(pending.get("sample_qdat") or "").strip()
        vanadium_qdat = str(pending.get("vanadium_qdat") or "").strip()
        if not sample_qdat or not vanadium_qdat:
            return

        context_id = datetime.now(tz=PARIS_TZ).strftime("manual-%Y%m%d-%H%M%S-%f")
        payload: dict[str, object] = {
            "schema_version": 1,
            "context_id": context_id,
            "workflow": "background",
            "created_at": now_iso(),
            "source": {"kind": "manual_qdat_selection"},
            "sample": {},
            "decisions": {},
            "artifacts": {
                "sample_sub_qdat": project_relpath(self.current_project_root, Path(sample_qdat)),
                "vanadium_sub_qdat": project_relpath(self.current_project_root, Path(vanadium_qdat)),
            },
        }

        manifest_file = write_context_manifest(self.current_project_root, context_id=context_id, payload=payload)
        manifest_rel = context_manifest_relpath(self.current_project_root, manifest_file)

        state = self._get_background_state()
        contexts = state.get("contexts") if isinstance(state.get("contexts"), dict) else {}
        entries = contexts.get("entries") if isinstance(contexts.get("entries"), list) else []
        new_entry = {
            "context_id": context_id,
            "manifest": manifest_rel,
            "created_at": now_iso(),
            "sample_title": Path(sample_qdat).stem,
            "status": "ok",
        }
        contexts["active_context_id"] = context_id
        contexts["entries"] = [new_entry, *entries]
        state["contexts"] = contexts
        self._persist_background_state(state)

        self._clear_normalization_adopt_prompt()
        self._refresh_normalization_context_options(apply_selection=True)
        self._refresh_normalization_context_summary()
        self.normalization_selection_message.object = f"Created new context `{context_id}`."
        self.normalization_selection_message.alert_type = "success"
        self._show_success_toast("Created a new context from selected qdat files.")
        self._render_current_screen()

    def _cancel_normalization_adopt(self, _event=None) -> None:
        if self.operation_in_progress:
            self._show_workspace_blocked_message()
            return
        self._clear_normalization_adopt_prompt()
        self.normalization_selection_message.object = "Context creation cancelled."
        self.normalization_selection_message.alert_type = "secondary"
        self._refresh_interaction_states()

    def _refresh_normalization_context_options(self, *, apply_selection: bool) -> None:
        if self.current_project_state is None or self.current_project_root is None:
            return
        if not hasattr(self, "normalization_context_select"):
            return

        state = self._get_background_state() if hasattr(self, "_get_background_state") else {}
        contexts = state.get("contexts") if isinstance(state.get("contexts"), dict) else {}
        entries = contexts.get("entries") if isinstance(contexts.get("entries"), list) else []

        options: dict[str, str] = {}
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            context_id = str(entry.get("context_id") or "").strip()
            manifest = str(entry.get("manifest") or "").strip()
            if not context_id or not manifest:
                continue
            created_at = self._format_context_timestamp(entry.get("created_at"))
            sample_title = str(entry.get("sample_title") or "").strip()
            label = " — ".join([v for v in (created_at, sample_title, context_id) if v])
            options[label] = context_id

        if not options:
            options = {"No exported background contexts yet.": ""}
            self.normalization_context_select.options = options
            self.normalization_context_select.value = ""
            self.normalization_context_select.disabled = True
            if hasattr(self, "normalization_context_message"):
                self.normalization_context_message.object = (
                    "No background contexts are available yet. Run **Background → Export Data** first."
                )
                self.normalization_context_message.alert_type = "warning"
            return

        self.normalization_context_select.disabled = False
        self.normalization_context_select.options = options

        if not apply_selection:
            return

        active = str(contexts.get("active_context_id") or "").strip()
        if active and active in options.values():
            selected = active
        else:
            selected = next(iter(options.values()))

        self._suspend_normalization_events = True
        try:
            self.normalization_context_select.value = selected
        finally:
            self._suspend_normalization_events = False

    def _on_normalization_context_change(self, event) -> None:
        if getattr(self, "_suspend_normalization_events", False) or self.current_project_state is None:
            return
        if event.new == event.old:
            return

        context_id = str(event.new or "").strip()
        if not context_id:
            return

        state = self._get_background_state()
        contexts = state.get("contexts") if isinstance(state.get("contexts"), dict) else {}
        contexts["active_context_id"] = context_id
        state["contexts"] = contexts
        self._persist_background_state(state)

        self._refresh_normalization_context_summary()
        self._load_normalization_fit_data_selection_from_context()
        self._load_normalization_fit_params_from_context()
        self._refresh_normalization_fit_params_plot()
        self._refresh_normalization_fit_params_button_states()
        self._refresh_normalization_sample_normalization_plot()
        self._refresh_interaction_states()

        # Best-effort: sync the qdat selectors to match the chosen context.
        try:
            payload = load_context_manifest(self.current_project_root, self._selected_normalization_manifest_ref())
            artifacts = payload.get("artifacts") if isinstance(payload, dict) else {}
            sample_ref = artifacts.get("sample_sub_qdat") if isinstance(artifacts, dict) else None
            van_ref = artifacts.get("vanadium_sub_qdat") if isinstance(artifacts, dict) else None
            if isinstance(sample_ref, str) and isinstance(van_ref, str):
                sample_path = str(resolve_project_path(self.current_project_root, sample_ref))
                van_path = str(resolve_project_path(self.current_project_root, van_ref))
                self._suspend_normalization_events = True
                try:
                    if hasattr(self, "normalization_sample_qdat_path_input"):
                        self.normalization_sample_qdat_path_input.value = sample_path
                    if hasattr(self, "normalization_vanadium_qdat_path_input"):
                        self.normalization_vanadium_qdat_path_input.value = van_path
                    if hasattr(self, "normalization_sample_qdat_dropdown") and sample_path in getattr(
                        self.normalization_sample_qdat_dropdown, "options", {}
                    ).values():
                        self.normalization_sample_qdat_dropdown.value = sample_path
                    if hasattr(self, "normalization_vanadium_qdat_dropdown") and van_path in getattr(
                        self.normalization_vanadium_qdat_dropdown, "options", {}
                    ).values():
                        self.normalization_vanadium_qdat_dropdown.value = van_path
                finally:
                    self._suspend_normalization_events = False
        except Exception:
            pass

    def _selected_normalization_manifest_ref(self) -> str:
        state = self._get_background_state()
        contexts = state.get("contexts") if isinstance(state.get("contexts"), dict) else {}
        entries = contexts.get("entries") if isinstance(contexts.get("entries"), list) else []
        selected = str(getattr(self.normalization_context_select, "value", "") or "").strip()
        entry = next((e for e in entries if isinstance(e, dict) and e.get("context_id") == selected), None)
        if not isinstance(entry, dict):
            return ""
        return str(entry.get("manifest") or "").strip()

    def _refresh_normalization_context_summary(self) -> None:
        if self.current_project_root is None:
            return
        if (
            not hasattr(self, "normalization_context_summary")
            or not hasattr(self, "normalization_context_message")
            or not hasattr(self, "normalization_context_info_hover")
        ):
            return

        state = self._get_background_state()
        contexts = state.get("contexts") if isinstance(state.get("contexts"), dict) else {}
        entries = contexts.get("entries") if isinstance(contexts.get("entries"), list) else []
        selected = str(getattr(self.normalization_context_select, "value", "") or "").strip()
        if not selected:
            self.normalization_context_summary.object = ""
            self.normalization_context_info_hover.value = ""
            self.normalization_context_message.object = (
                "Select a background context to proceed. Contexts are created by **Background → Export Data**."
            )
            self.normalization_context_message.alert_type = "secondary"
            return

        entry = next((e for e in entries if isinstance(e, dict) and e.get("context_id") == selected), None)
        if not isinstance(entry, dict):
            self.normalization_context_summary.object = ""
            self.normalization_context_info_hover.value = ""
            self.normalization_context_message.object = "Selected context is not available in project state."
            self.normalization_context_message.alert_type = "danger"
            return

        manifest_ref = str(entry.get("manifest") or "").strip()
        if not manifest_ref:
            self.normalization_context_summary.object = ""
            self.normalization_context_info_hover.value = ""
            self.normalization_context_message.object = "Selected context has no manifest path."
            self.normalization_context_message.alert_type = "danger"
            return

        payload = load_context_manifest(self.current_project_root, manifest_ref)
        if payload is None:
            manifest_path = resolve_project_path(self.current_project_root, manifest_ref)
            self.normalization_context_summary.object = ""
            self.normalization_context_info_hover.value = ""
            self.normalization_context_message.object = (
                f"Context manifest could not be loaded: `{manifest_path}`"
            )
            self.normalization_context_message.alert_type = "danger"
            return

        sample = payload.get("sample") if isinstance(payload.get("sample"), dict) else {}
        decisions = payload.get("decisions") if isinstance(payload.get("decisions"), dict) else {}
        artifacts = payload.get("artifacts") if isinstance(payload.get("artifacts"), dict) else {}

        sample_title = str(sample.get("title") or entry.get("sample_title") or "").strip()
        sample_name = str(sample.get("name") or "").strip()
        sample_key = str(sample.get("sample_key") or entry.get("sample_key") or "").strip()
        par_rel = str(sample.get("par_path_rel") or "").strip()
        measurement_artifact = str(sample.get("measurement_artifact") or "").strip()
        t_sample = decisions.get("t_sample")
        t_vanadium = decisions.get("t_vanadium")

        sample_qdat = str(artifacts.get("sample_sub_qdat") or "").strip()
        van_qdat = str(artifacts.get("vanadium_sub_qdat") or "").strip()

        warnings: list[str] = []
        for label, raw_path in (("Sample qdat", sample_qdat), ("Vanadium qdat", van_qdat)):
            if not raw_path:
                warnings.append(f"{label} path is missing.")
                continue
            try:
                path = Path(raw_path).expanduser()
            except Exception:
                warnings.append(f"{label} path is invalid.")
                continue
            if not path.is_absolute():
                path = (self.current_project_root / path).resolve(strict=False)
            if not path.exists():
                warnings.append(f"{label} file not found: {path}")

        warn_html = ""
        if warnings:
            warn_lines = "".join(f"<li>{html_escape(str(w))}</li>" for w in warnings)
            warn_html = f"""
            <div style="margin-top: 10px;">
              <strong>Warnings</strong>
              <ul style="margin: 6px 0 0 18px;">{warn_lines}</ul>
            </div>
            """.strip()
            self.normalization_context_message.object = "Context loaded with warnings. Fix them before proceeding."
            self.normalization_context_message.alert_type = "warning"
        else:
            self.normalization_context_message.object = "Context loaded."
            self.normalization_context_message.alert_type = "success"

        def _code(value: object) -> str:
            raw = str(value).strip() if value is not None else ""
            if not raw:
                return "<em>Not available</em>"
            return (
                "<code style=\"white-space: normal; overflow-wrap: anywhere; "
                "word-break: break-word;\">"
                f"{html_escape(raw)}"
                "</code>"
            )

        def _text(value: object) -> str:
            raw = str(value).strip() if value is not None else ""
            if not raw:
                return ""
            return html_escape(raw)

        health_label = "Warnings" if warnings else "Ready"
        health_class = "warning" if warnings else "ready"
        title_text = ""
        subtitle_parts: list[str] = []
        summary_html = f"""
        <div class="toscana-normalization-context-summary">
          <div class="toscana-normalization-context-summary__status toscana-normalization-context-summary__status--{health_class}">
            {health_label}
          </div>
          <div class="toscana-normalization-context-summary__title">{_text(title_text)}</div>
          <div class="toscana-normalization-context-summary__meta">{' <span class="toscana-normalization-context-summary__dot">•</span> '.join(subtitle_parts)}</div>
          {warn_html}
        </div>
        """.strip()

        self.normalization_context_summary.object = summary_html
        self._refresh_normalization_context_hovercard(
            context_id=selected,
            sample_title=sample_title,
            par_path_rel=par_rel,
            measurement_artifact=measurement_artifact,
            t_sample=t_sample,
            t_vanadium=t_vanadium,
            sample_qdat=sample_qdat,
            vanadium_qdat=van_qdat,
        )

    def _refresh_normalization_context_hovercard(
        self,
        *,
        context_id: str,
        sample_title: str,
        par_path_rel: str,
        measurement_artifact: str,
        t_sample: object,
        t_vanadium: object,
        sample_qdat: str,
        vanadium_qdat: str,
    ) -> None:
        if not hasattr(self, "normalization_context_info_hover"):
            return

        def _code(value: object) -> str:
            raw = str(value).strip() if value is not None else ""
            if not raw:
                return "<em>Not available</em>"
            return f"<code>{html_escape(raw)}</code>"

        def _text(value: object) -> str:
            raw = str(value).strip() if value is not None else ""
            if not raw:
                return "<em>Not available</em>"
            return html_escape(raw)

        body_lines = [
            f"<div><strong>Context id:</strong> {_code(context_id)}</div>",
            f"<div><strong>Sample title:</strong> {_text(sample_title)}</div>",
            f"<div><strong>Par (rel):</strong> {_code(par_path_rel)}</div>",
            f"<div><strong>Measurement artifact:</strong> {_code(measurement_artifact)}</div>",
            f"<div><strong>t sample:</strong> {_code(t_sample)}</div>",
            f"<div><strong>t vanadium:</strong> {_code(t_vanadium)}</div>",
            f"<div><strong>Sample qdat:</strong> {_code(sample_qdat)}</div>",
            f"<div><strong>Vanadium qdat:</strong> {_code(vanadium_qdat)}</div>",
        ]

        self.normalization_context_info_hover.value = (
            "<div style=\"max-width: 320px; line-height: 1.6; white-space: normal; overflow-wrap: anywhere; word-break: break-word;\">"
            + "".join(body_lines)
            + "</div>"
        )
