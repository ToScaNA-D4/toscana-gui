from __future__ import annotations

import json
import pickle
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from os import chdir, getcwd
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import panel as pn

from toscana_gui.contexts import (
    context_manifest_relpath,
    load_context_manifest,
    project_relpath,
    resolve_project_path,
    write_context_manifest,
)
from toscana_gui.persistence import PARIS_TZ, now_iso
from toscana_gui.self_scattering.plots import (
    build_self_fit_model_figure,
    build_self_lowq_figure,
    build_static_structure_factor_figure,
    update_self_fit_model_figure,
    update_self_lowq_figure,
    update_static_structure_factor_figure,
)


def html_escape(value: object) -> str:
    import html

    return html.escape(str(value), quote=True)


@dataclass(frozen=True, slots=True)
class LowQSelection:
    mode: str
    q_min: float
    q_max: float
    y_min: float
    y_max: float
    q_subset: np.ndarray
    y_subset: np.ndarray
    warnings: list[str]


def beam_stop_correct(
    *,
    q: np.ndarray,
    y_raw: np.ndarray,
    y_lowq: np.ndarray,
    q_min: float,
    q_max: float,
) -> np.ndarray:
    """
    Apply the beam-stop correction blending used in the legacy notebook.

    - q < q_min: replace by y_lowq
    - q_min <= q <= q_max: linear blend raw->lowq across the window
    - q > q_max: keep raw
    """
    q = np.asarray(q, dtype=float)
    y_raw = np.asarray(y_raw, dtype=float)
    y_lowq = np.asarray(y_lowq, dtype=float)
    if q.shape != y_raw.shape or q.shape != y_lowq.shape:
        raise ValueError("q, y_raw, and y_lowq must have the same shape.")
    if not np.isfinite(float(q_min)) or not np.isfinite(float(q_max)):
        raise ValueError("q_min and q_max must be finite.")
    if float(q_max) <= float(q_min):
        raise ValueError("q_max must be greater than q_min.")

    q_min_f = float(q_min)
    q_max_f = float(q_max)
    out = np.array(y_raw, copy=True, dtype=float)

    below = q < q_min_f
    in_window = (q >= q_min_f) & (q <= q_max_f)
    out[below] = y_lowq[below]
    if np.any(in_window):
        w = (q[in_window] - q_min_f) / (q_max_f - q_min_f)
        out[in_window] = (w * y_raw[in_window]) + ((1.0 - w) * y_lowq[in_window])
    return out


class SelfScatteringControllerMixin:
    @contextmanager
    def _working_directory(self, target: Path):
        original = Path(getcwd())
        chdir(str(target))
        try:
            yield
        finally:
            chdir(str(original))

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
    _SELF_LOWQ_MODE_PERCENTILE = "percentile_band"
    _SELF_LOWQ_MODE_MANUAL = "manual_window"
    _SELF_FIT_MODEL_VANA = "vanaQdep"
    _SELF_FIT_MODEL_POLY = "polyQ4"
    _SELF_FIT_MODEL_LORGAU = "LorGau"

    @staticmethod
    def _self_range_value(widget, fallback: tuple[float, float]) -> tuple[float, float]:
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
    def _set_self_range_value(widget, value: tuple[float, float]) -> None:
        try:
            widget.value = [float(value[0]), float(value[1])]
        except Exception:
            return

    def _normalize_self_lowq_mode(self, raw_mode: object) -> str:
        mode = str(raw_mode or "").strip()
        if mode in (self._SELF_LOWQ_MODE_MANUAL, "Manual window"):
            return self._SELF_LOWQ_MODE_MANUAL
        if mode in (self._SELF_LOWQ_MODE_PERCENTILE, "Percentile band", ""):
            return self._SELF_LOWQ_MODE_PERCENTILE
        return self._SELF_LOWQ_MODE_MANUAL

    def _is_self_lowq_manual_mode(self, raw_mode: object) -> bool:
        return self._normalize_self_lowq_mode(raw_mode) == self._SELF_LOWQ_MODE_MANUAL

    def _self_lowq_mode_label(self, raw_mode: object) -> str:
        return "Manual window" if self._is_self_lowq_manual_mode(raw_mode) else "Percentile band"

    def _sync_self_lowq_ui_summary(self) -> None:
        panes = []
        redesign_pane = getattr(self, "self_lowq_redesign_mode_chips", None)
        if redesign_pane is not None:
            panes.append(redesign_pane)
        if not panes:
            return
        mode = self._normalize_self_lowq_mode(getattr(getattr(self, "self_lowq_selection_mode", None), "value", ""))
        use_sliders = bool(getattr(getattr(self, "self_lowq_use_sliders", None), "value", False))
        mode_label = self._self_lowq_mode_label(mode)
        input_label = "Axis sliders" if use_sliders else "Numeric inputs"
        mode_kind = "manual" if self._is_self_lowq_manual_mode(mode) else "band"
        input_kind = "slider" if use_sliders else "input"
        html = (
            "<div class=\"toscana-normalization-fit-data-summary\">"
            f"<div class=\"toscana-normalization-fit-data-chip toscana-normalization-fit-data-chip--{mode_kind}\">{mode_label}</div>"
            f"<div class=\"toscana-normalization-fit-data-chip toscana-normalization-fit-data-chip--{input_kind}\">{input_label}</div>"
            "</div>"
        )
        for pane in panes:
            pane.object = html

    def _sync_self_lowq_buttons(self) -> None:
        button_input_mode = getattr(self, "self_lowq_redesign_switch_input_mode", None)
        button_method = getattr(self, "self_lowq_redesign_switch_method", None)
        if button_input_mode is None and button_method is None:
            return
        mode = self._normalize_self_lowq_mode(getattr(getattr(self, "self_lowq_selection_mode", None), "value", ""))
        use_sliders = bool(getattr(getattr(self, "self_lowq_use_sliders", None), "value", False))
        manual_mode = self._is_self_lowq_manual_mode(mode)
        if button_input_mode is not None:
            button_input_mode.button_type = "warning" if use_sliders else "primary"
        if button_method is not None:
            button_method.button_type = "warning" if manual_mode else "primary"

    def _update_self_lowq_value_labels(self) -> None:
        lower = getattr(self, "self_lowq_redesign_vertical_lower_value", None)
        upper = getattr(self, "self_lowq_redesign_vertical_upper_value", None)
        if lower is None or upper is None:
            return
        mode = self._normalize_self_lowq_mode(getattr(getattr(self, "self_lowq_selection_mode", None), "value", ""))
        manual_mode = self._is_self_lowq_manual_mode(mode)
        use_sliders = bool(getattr(getattr(self, "self_lowq_use_sliders", None), "value", False))

        vertical_lower_input = getattr(self, "self_lowq_redesign_vertical_lower_input", None)
        vertical_upper_input = getattr(self, "self_lowq_redesign_vertical_upper_input", None)
        q_input_row = getattr(self, "self_lowq_redesign_q_input_row", None)
        q_start_input = getattr(self, "self_lowq_redesign_q_start_input", None)
        q_end_input = getattr(self, "self_lowq_redesign_q_end_input", None)
        q_range = getattr(self, "self_lowq_redesign_q_range_slider", None)
        vertical_range = getattr(self, "self_lowq_redesign_vertical_range_slider", None)

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

        lower.visible = bool(use_sliders)
        upper.visible = bool(use_sliders)
        if vertical_lower_input is not None:
            vertical_lower_input.visible = not use_sliders
        if vertical_upper_input is not None:
            vertical_upper_input.visible = not use_sliders

        if manual_mode:
            y_min = float(getattr(getattr(self, "self_lowq_y_min", None), "value", 0.0) or 0.0)
            y_max = float(getattr(getattr(self, "self_lowq_y_max", None), "value", 0.0) or 0.0)
            lower.object = f"Intensity min: {y_min:.4g}"
            upper.object = f"Intensity max: {y_max:.4g}"
            if vertical_lower_input is not None:
                try:
                    vertical_lower_input.step = float(getattr(getattr(self, "self_lowq_y_min", None), "step", 0.01) or 0.01)
                    if vertical_range is not None:
                        vertical_lower_input.start = float(vertical_range.start)
                        vertical_lower_input.end = float(vertical_range.end)
                    vertical_lower_input.value = y_min
                except Exception:
                    pass
            if vertical_upper_input is not None:
                try:
                    vertical_upper_input.step = float(getattr(getattr(self, "self_lowq_y_max", None), "step", 0.01) or 0.01)
                    if vertical_range is not None:
                        vertical_upper_input.start = float(vertical_range.start)
                        vertical_upper_input.end = float(vertical_range.end)
                    vertical_upper_input.value = y_max
                except Exception:
                    pass
            q_start = float(getattr(getattr(self, "self_lowq_q_min", None), "value", 0.0) or 0.0)
            q_end = float(getattr(getattr(self, "self_lowq_q_max", None), "value", 0.0) or 0.0)
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

        min_pct = int(getattr(getattr(self, "self_lowq_min_percentile", None), "value", 0) or 0)
        max_pct = int(getattr(getattr(self, "self_lowq_max_percentile", None), "value", 0) or 0)
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

        q_start = float(getattr(getattr(self, "self_lowq_q_tail_low", None), "value", 0.0) or 0.0)
        q_end = float(getattr(getattr(self, "self_lowq_q_tail_high", None), "value", 0.0) or 0.0)
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

    def _on_self_lowq_redesign_numeric_input_change(self, event=None) -> None:
        if getattr(self, "_suspend_self_scattering_events", False) or self.current_project_state is None:
            return
        use_sliders = bool(getattr(getattr(self, "self_lowq_use_sliders", None), "value", False))
        if use_sliders:
            return
        if event is None:
            return
        src = getattr(event, "obj", None)
        if src is None:
            return

        q_start_input = getattr(self, "self_lowq_redesign_q_start_input", None)
        q_end_input = getattr(self, "self_lowq_redesign_q_end_input", None)
        vertical_lower_input = getattr(self, "self_lowq_redesign_vertical_lower_input", None)
        vertical_upper_input = getattr(self, "self_lowq_redesign_vertical_upper_input", None)

        mode = self._normalize_self_lowq_mode(getattr(getattr(self, "self_lowq_selection_mode", None), "value", ""))
        manual_mode = self._is_self_lowq_manual_mode(mode)

        def _to_float(value: object, fallback: float) -> float:
            try:
                val = float(value)
            except Exception:
                return fallback
            return val if np.isfinite(val) else fallback

        self._suspend_self_scattering_events = True
        try:
            if manual_mode:
                if src is q_start_input and hasattr(self, "self_lowq_q_min"):
                    current = float(getattr(self.self_lowq_q_min, "value", 0.0) or 0.0)
                    self.self_lowq_q_min.value = _to_float(getattr(src, "value", None), current)
                elif src is q_end_input and hasattr(self, "self_lowq_q_max"):
                    current = float(getattr(self.self_lowq_q_max, "value", 0.0) or 0.0)
                    self.self_lowq_q_max.value = _to_float(getattr(src, "value", None), current)
            else:
                if src is q_start_input and hasattr(self, "self_lowq_q_tail_low"):
                    current = float(getattr(self.self_lowq_q_tail_low, "value", 0.0) or 0.0)
                    self.self_lowq_q_tail_low.value = _to_float(getattr(src, "value", None), current)
                elif src is q_end_input and hasattr(self, "self_lowq_q_tail_high"):
                    current = float(getattr(self.self_lowq_q_tail_high, "value", 0.0) or 0.0)
                    self.self_lowq_q_tail_high.value = _to_float(getattr(src, "value", None), current)

            if src in (vertical_lower_input, vertical_upper_input):
                raw = getattr(src, "value", None)
                if manual_mode:
                    if src is vertical_lower_input and hasattr(self, "self_lowq_y_min"):
                        current = float(getattr(self.self_lowq_y_min, "value", 0.0) or 0.0)
                        self.self_lowq_y_min.value = _to_float(raw, current)
                    if src is vertical_upper_input and hasattr(self, "self_lowq_y_max"):
                        current = float(getattr(self.self_lowq_y_max, "value", 0.0) or 0.0)
                        self.self_lowq_y_max.value = _to_float(raw, current)
                else:
                    if src is vertical_lower_input and hasattr(self, "self_lowq_min_percentile"):
                        current = int(getattr(self.self_lowq_min_percentile, "value", 0) or 0)
                        self.self_lowq_min_percentile.value = int(_to_float(raw, float(current)))
                    if src is vertical_upper_input and hasattr(self, "self_lowq_max_percentile"):
                        current = int(getattr(self.self_lowq_max_percentile, "value", 0) or 0)
                        self.self_lowq_max_percentile.value = int(_to_float(raw, float(current)))
        finally:
            self._suspend_self_scattering_events = False

        self._on_self_lowq_controls_change()

    def _schedule_self_lowq_plot_refresh(self, *, delay_ms: int = 75) -> None:
        if self.current_project_state is None:
            return
        if not hasattr(self, "_refresh_self_lowq_panel"):
            return
        doc = getattr(pn.state, "curdoc", None)
        if doc is None:
            self._refresh_self_lowq_panel()
            return

        handle = getattr(self, "_self_lowq_refresh_handle", None)
        if handle is not None:
            try:
                doc.remove_timeout_callback(handle)
            except Exception:
                pass
            self._self_lowq_refresh_handle = None

        def _run() -> None:
            self._self_lowq_refresh_handle = None
            self._refresh_self_lowq_panel()

        try:
            self._self_lowq_refresh_handle = doc.add_timeout_callback(_run, int(delay_ms))
        except Exception:
            self._self_lowq_refresh_handle = None
            self._refresh_self_lowq_panel()

    def _reset_self_scattering_runtime_state(self) -> None:
        self._self_dsdo_cache = None
        self._self_lowq_last = None
        self._self_lowq_plot_source = None
        self._self_data_selection_last = None
        self._self_data_selection_plot_source = None
        self._self_fit_last = None
        self._self_fit_plot_source = None
        self._self_static_structure_factor_last = None
        if hasattr(self, "self_lowq_redesign_plot_pane"):
            try:
                self.self_lowq_redesign_plot_pane.object = None
            except Exception:
                pass
        if hasattr(self, "self_lowq_redesign_window_table"):
            try:
                self.self_lowq_redesign_window_table.object = ""
            except Exception:
                pass
        if hasattr(self, "self_data_selection_redesign_plot_pane"):
            try:
                self.self_data_selection_redesign_plot_pane.object = None
            except Exception:
                pass
        if hasattr(self, "self_data_selection_redesign_window_table"):
            try:
                self.self_data_selection_redesign_window_table.object = ""
            except Exception:
                pass
        if hasattr(self, "self_fit_plot_pane"):
            try:
                self.self_fit_plot_pane.object = None
            except Exception:
                pass
        if hasattr(self, "self_fit_result_table"):
            try:
                self.self_fit_result_table.object = ""
            except Exception:
                pass
        if hasattr(self, "self_static_structure_factor_plot_pane"):
            try:
                self.self_static_structure_factor_plot_pane.object = None
            except Exception:
                pass
        if hasattr(self, "self_static_structure_factor_summary_table"):
            try:
                self.self_static_structure_factor_summary_table.object = ""
            except Exception:
                pass
        if hasattr(self, "self_export_prompt"):
            try:
                self.self_export_prompt.visible = False
                self.self_export_prompt.object = ""
            except Exception:
                pass
        self._pending_self_export = None

    def _load_self_scattering_state_into_widgets(self) -> None:
        if self.current_project_state is None or self.current_project_root is None:
            return
        if not hasattr(self, "self_context_select"):
            return
        self._set_self_lowq_controls_visibility()
        if hasattr(self, "_set_self_data_selection_controls_visibility"):
            self._set_self_data_selection_controls_visibility()
        self._refresh_self_context_options(apply_selection=True)
        self._refresh_self_context_summary()
        self._load_self_lowq_from_context()
        self._sync_self_lowq_ui_summary()
        self._sync_self_lowq_buttons()
        self._update_self_lowq_value_labels()
        self._refresh_self_lowq_panel()
        if hasattr(self, "_load_self_data_selection_from_context"):
            self._load_self_data_selection_from_context()
        if hasattr(self, "_on_self_data_selection_controls_change"):
            self._on_self_data_selection_controls_change()
        if hasattr(self, "_refresh_self_data_selection_panel"):
            self._refresh_self_data_selection_panel()
        if hasattr(self, "_load_self_fit_model_from_context"):
            self._load_self_fit_model_from_context()
        if hasattr(self, "_refresh_self_fit_panel"):
            self._refresh_self_fit_panel()
        if hasattr(self, "_refresh_self_static_structure_factor_panel"):
            self._refresh_self_static_structure_factor_panel()
        if hasattr(self, "_refresh_self_export_hovercard"):
            self._refresh_self_export_hovercard()
        if hasattr(self, "_refresh_self_export_button_states"):
            self._refresh_self_export_button_states()

    def _get_self_context_entries(self) -> list[dict[str, Any]]:
        if self.current_project_state is None:
            return []
        if hasattr(self, "_get_background_state"):
            state = self._get_background_state()
        else:
            state = getattr(self.current_project_state, "background", {}) or {}
        contexts = state.get("contexts") if isinstance(state.get("contexts"), dict) else {}
        entries = contexts.get("entries") if isinstance(contexts.get("entries"), list) else []
        return [e for e in entries if isinstance(e, dict)]

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

    def _selected_self_manifest_ref(self) -> str:
        selected = str(getattr(getattr(self, "self_context_select", None), "value", "") or "").strip()
        if not selected:
            return ""
        entry = next((e for e in self._get_self_context_entries() if str(e.get("context_id") or "").strip() == selected), None)
        if not isinstance(entry, dict):
            return ""
        return str(entry.get("manifest") or "").strip()

    def _refresh_self_context_options(self, *, apply_selection: bool) -> None:
        if self.current_project_state is None or self.current_project_root is None:
            return
        if not hasattr(self, "self_context_select"):
            return

        entries = self._get_self_context_entries()
        options: dict[str, str] = {}
        for entry in entries:
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
            self.self_context_select.options = options
            self.self_context_select.value = ""
            self.self_context_select.disabled = True
            if hasattr(self, "self_context_message"):
                self.self_context_message.object = "No background contexts are available yet. Run **Background → Export Data** first."
                self.self_context_message.alert_type = "warning"
            return

        self.self_context_select.disabled = False
        self.self_context_select.options = options

        if not apply_selection:
            return

        if hasattr(self, "_get_background_state"):
            state = self._get_background_state()
            contexts = state.get("contexts") if isinstance(state.get("contexts"), dict) else {}
            active = str(contexts.get("active_context_id") or "").strip()
        else:
            active = ""

        if active and active in options.values():
            selected = active
        else:
            selected = next(iter(options.values()))

        self._suspend_self_scattering_events = True
        try:
            self.self_context_select.value = selected
        finally:
            self._suspend_self_scattering_events = False

    def _refresh_self_context_summary(self) -> None:
        if self.current_project_root is None:
            return
        if not hasattr(self, "self_context_summary") or not hasattr(self, "self_context_message") or not hasattr(self, "self_context_info_hover"):
            return

        selected = str(getattr(getattr(self, "self_context_select", None), "value", "") or "").strip()
        if not selected:
            self.self_context_summary.object = ""
            self.self_context_info_hover.value = ""
            self.self_context_message.object = "Select a background context to proceed. Contexts are created by **Background → Export Data**."
            self.self_context_message.alert_type = "secondary"
            return

        manifest_ref = self._selected_self_manifest_ref()
        if not manifest_ref:
            self.self_context_summary.object = ""
            self.self_context_info_hover.value = ""
            self.self_context_message.object = "Selected context has no manifest path."
            self.self_context_message.alert_type = "danger"
            return

        payload = load_context_manifest(self.current_project_root, manifest_ref)
        if payload is None:
            manifest_path = resolve_project_path(self.current_project_root, manifest_ref)
            self.self_context_summary.object = ""
            self.self_context_info_hover.value = ""
            self.self_context_message.object = f"Context manifest could not be loaded: `{manifest_path}`"
            self.self_context_message.alert_type = "danger"
            return

        artifacts = payload.get("artifacts") if isinstance(payload.get("artifacts"), dict) else {}
        dsdo_ref = artifacts.get("sample_dsdo_qdat") if isinstance(artifacts.get("sample_dsdo_qdat"), str) else None
        if not isinstance(dsdo_ref, str) or not dsdo_ref.strip():
            self.self_context_message.object = "This context has no `sample_dsdo_qdat`. Run **Normalization → Export Data** for this context."
            self.self_context_message.alert_type = "warning"
            dsdo_path = None
        else:
            try:
                dsdo_path = resolve_project_path(self.current_project_root, dsdo_ref)
            except Exception:
                dsdo_path = None
                self.self_context_message.object = "The `sample_dsdo_qdat` reference could not be resolved."
                self.self_context_message.alert_type = "danger"

        # Keep the surface clean: do not show sample/path lines under the selector.
        self.self_context_summary.object = ""

        def _code(val: object) -> str:
            return f"<code style=\"overflow-wrap:anywhere; word-break:break-word;\">{html_escape(val)}</code>"

        sample = payload.get("sample") if isinstance(payload.get("sample"), dict) else {}
        sample_title = str(sample.get("title") or "").strip()
        par_rel = str(sample.get("par_path_rel") or "").strip()
        body_lines = [
            f"<div><strong>Context id:</strong> {_code(selected)}</div>",
            f"<div><strong>Sample title:</strong> {html_escape(sample_title) if sample_title else _code('')}</div>",
            f"<div><strong>Par (rel):</strong> {_code(par_rel)}</div>",
            f"<div><strong>sample_dsdo_qdat:</strong> {_code(project_relpath(self.current_project_root, dsdo_path) if isinstance(dsdo_path, Path) else '')}</div>",
        ]
        self.self_context_info_hover.value = (
            "<div style=\"max-width: 420px; line-height: 1.6; overflow-wrap:anywhere; word-break:break-word;\">"
            + "".join(body_lines)
            + "</div>"
        )

        if dsdo_path is not None:
            exists = dsdo_path.exists()
            if exists:
                self.self_context_message.object = "Context ready for Self scattering."
                self.self_context_message.alert_type = "success"

        if hasattr(self, "self_lowq_extrapolate_button"):
            self.self_lowq_extrapolate_button.disabled = not (dsdo_path is not None and dsdo_path.exists())

    def _on_self_context_change(self, _event=None) -> None:
        if getattr(self, "_suspend_self_scattering_events", False) or self.current_project_state is None:
            return
        self._refresh_self_context_summary()
        self._load_self_lowq_from_context()
        self._load_self_data_selection_from_context()
        self._on_self_lowq_controls_change()
        self._on_self_data_selection_controls_change()
        if hasattr(self, "_load_self_fit_model_from_context"):
            self._load_self_fit_model_from_context()
        if hasattr(self, "_refresh_self_fit_panel"):
            self._refresh_self_fit_panel()
        if hasattr(self, "_refresh_self_static_structure_factor_panel"):
            self._refresh_self_static_structure_factor_panel()
        if hasattr(self, "_refresh_self_export_hovercard"):
            self._refresh_self_export_hovercard()
        if hasattr(self, "_refresh_self_export_button_states"):
            self._refresh_self_export_button_states()

    def _toggle_self_lowq_input_mode(self, _event=None) -> None:
        if self.current_project_state is None or getattr(self, "_suspend_self_scattering_events", False):
            return
        toggle = getattr(self, "self_lowq_use_sliders", None)
        if toggle is None:
            return
        self._suspend_self_scattering_events = True
        try:
            toggle.value = not bool(getattr(toggle, "value", False))
        finally:
            self._suspend_self_scattering_events = False
        self._on_self_lowq_controls_change()

    def _toggle_self_lowq_method(self, _event=None) -> None:
        if self.current_project_state is None or getattr(self, "_suspend_self_scattering_events", False):
            return
        mode_widget = getattr(self, "self_lowq_selection_mode", None)
        if mode_widget is None:
            return
        current = self._normalize_self_lowq_mode(getattr(mode_widget, "value", ""))
        next_mode = self._SELF_LOWQ_MODE_PERCENTILE if current == self._SELF_LOWQ_MODE_MANUAL else self._SELF_LOWQ_MODE_MANUAL
        self._suspend_self_scattering_events = True
        try:
            mode_widget.value = next_mode
        finally:
            self._suspend_self_scattering_events = False
        self._on_self_lowq_controls_change()

    def _on_self_lowq_view_change(self, _event=None) -> None:
        self._refresh_self_lowq_panel()

    def _read_qdat_xye_cached(self, path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        cache = getattr(self, "_self_dsdo_cache", None)
        if not isinstance(cache, dict):
            cache = {}
            self._self_dsdo_cache = cache
        token = (str(path.resolve(strict=False)), float(path.stat().st_mtime) if path.exists() else 0.0)
        if token in cache:
            return cache[token]

        text = path.read_text(encoding="utf-8", errors="replace")
        rows: list[list[float]] = []
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            try:
                qv = float(parts[0])
                yv = float(parts[1])
                ev = float(parts[2]) if len(parts) >= 3 else 0.0
            except Exception:
                continue
            rows.append([qv, yv, ev])
        if not rows:
            raise RuntimeError("qdat had no readable data rows.")
        arr = np.asarray(rows, dtype=float)
        q = arr[:, 0]
        y = arr[:, 1]
        e = arr[:, 2] if arr.shape[1] >= 3 else np.zeros_like(y, dtype=float)
        cache[token] = (q, y, e)
        return q, y, e

    def _load_self_dsdo_series(self) -> tuple[np.ndarray, np.ndarray, np.ndarray, Path] | None:
        if self.current_project_root is None:
            return None
        context_id = str(getattr(getattr(self, "self_context_select", None), "value", "") or "").strip()
        if not context_id:
            return None
        manifest_ref = self._selected_self_manifest_ref()
        if not manifest_ref:
            return None
        payload = load_context_manifest(self.current_project_root, manifest_ref)
        artifacts = payload.get("artifacts") if isinstance(payload, dict) else {}
        ref = artifacts.get("sample_dsdo_qdat") if isinstance(artifacts.get("sample_dsdo_qdat"), str) else None
        if not isinstance(ref, str) or not ref.strip():
            return None
        path = resolve_project_path(self.current_project_root, ref)
        if not path.exists():
            return None
        q, y, e = self._read_qdat_xye_cached(path)
        q = np.asarray(q, dtype=float)
        y = np.asarray(y, dtype=float)
        e = np.asarray(e, dtype=float)
        finite = np.isfinite(q) & np.isfinite(y)
        q = q[finite]
        y = y[finite]
        e = e[finite] if e.shape[0] == finite.shape[0] else np.zeros_like(y, dtype=float)
        order = np.argsort(q)
        return q[order], y[order], e[order], path

    def _self_lowq_select_points(self, *, q: np.ndarray, y: np.ndarray) -> LowQSelection:
        mode = self._normalize_self_lowq_mode(getattr(getattr(self, "self_lowq_selection_mode", None), "value", ""))
        warnings: list[str] = []
        if self._is_self_lowq_manual_mode(mode):
            q_min = float(getattr(getattr(self, "self_lowq_q_min", None), "value", 0.0) or 0.0)
            q_max = float(getattr(getattr(self, "self_lowq_q_max", None), "value", 0.0) or 0.0)
            y_min = float(getattr(getattr(self, "self_lowq_y_min", None), "value", 0.0) or 0.0)
            y_max = float(getattr(getattr(self, "self_lowq_y_max", None), "value", 0.0) or 0.0)
            if q_max < q_min:
                warnings.append("Manual window has `q_max < q_min`.")
            if y_max < y_min:
                warnings.append("Manual window has `y_max < y_min`.")
            mask = (q >= q_min) & (q <= q_max) & (y >= y_min) & (y <= y_max)
            return LowQSelection(
                mode=mode,
                q_min=q_min,
                q_max=q_max,
                y_min=y_min,
                y_max=y_max,
                q_subset=q[mask],
                y_subset=y[mask],
                warnings=warnings,
            )

        q_min = float(getattr(getattr(self, "self_lowq_q_tail_low", None), "value", 0.0) or 0.0)
        q_max = float(getattr(getattr(self, "self_lowq_q_tail_high", None), "value", 0.0) or 0.0)
        min_pct = int(getattr(getattr(self, "self_lowq_min_percentile", None), "value", 0) or 0)
        max_pct = int(getattr(getattr(self, "self_lowq_max_percentile", None), "value", 0) or 0)
        if q_max < q_min:
            warnings.append("Percentile band has `Q end < Q start`.")
        if max_pct < min_pct:
            warnings.append("Percentile band has `upper percentile < lower percentile`.")

        # Match Normalization percentile-band behavior:
        # percentiles are computed from the full intensity distribution (not restricted by Q).
        finite_y = y[np.isfinite(y)]
        if finite_y.size == 0:
            y_min = float("nan")
            y_max = float("nan")
        else:
            y_min = float(np.percentile(finite_y, min_pct))
            y_max = float(np.percentile(finite_y, max_pct))

        mask = (q >= q_min) & (q <= q_max) & (y >= y_min) & (y <= y_max)
        return LowQSelection(
            mode=mode,
            q_min=q_min,
            q_max=q_max,
            y_min=y_min,
            y_max=y_max,
            q_subset=q[mask],
            y_subset=y[mask],
            warnings=warnings,
        )

    def _set_self_lowq_controls_visibility(self) -> None:
        for name in (
            "self_lowq_redesign_horizontal_axis_controls",
            "self_lowq_redesign_vertical_axis_controls",
            "self_lowq_redesign_q_range_slider",
            "self_lowq_redesign_vertical_range_slider",
        ):
            if hasattr(self, name):
                getattr(self, name).visible = True

    def _set_self_data_selection_controls_visibility(self) -> None:
        # Mirror Normalization "Select Fitting Data" redesign: axis controls are always present
        # (sliders are disabled when using numeric inputs).
        for name in (
            "self_data_selection_redesign_horizontal_axis_controls",
            "self_data_selection_redesign_vertical_axis_controls",
            "self_data_selection_redesign_q_range_slider",
            "self_data_selection_redesign_vertical_range_slider",
        ):
            if hasattr(self, name):
                getattr(self, name).visible = True

    def _on_self_lowq_controls_change(self, event=None) -> None:
        if getattr(self, "_suspend_self_scattering_events", False) or self.current_project_state is None:
            return

        use_sliders = bool(getattr(getattr(self, "self_lowq_use_sliders", None), "value", False))
        src = getattr(event, "obj", None) if event is not None else None
        event_name = str(getattr(event, "name", "") or "") if event is not None else ""

        range_slider_names = ("self_lowq_redesign_q_range_slider", "self_lowq_redesign_vertical_range_slider")
        range_slider_sources = tuple(getattr(self, name) for name in range_slider_names if hasattr(self, name))
        is_slider_value_event = bool(use_sliders and src is not None and event_name == "value" and src in range_slider_sources)

        self._suspend_self_scattering_events = True
        try:
            vertical_range = getattr(self, "self_lowq_redesign_vertical_range_slider", None)
            q_range = getattr(self, "self_lowq_redesign_q_range_slider", None)

            mode = self._normalize_self_lowq_mode(getattr(getattr(self, "self_lowq_selection_mode", None), "value", ""))
            manual_mode = self._is_self_lowq_manual_mode(mode)

            if use_sliders and src is q_range:
                lower_value, upper_value = self._self_range_value(
                    q_range,
                    (
                        float(getattr(getattr(self, "self_lowq_q_min" if manual_mode else "self_lowq_q_tail_low", None), "value", 0.0) or 0.0),
                        float(getattr(getattr(self, "self_lowq_q_max" if manual_mode else "self_lowq_q_tail_high", None), "value", 0.0) or 0.0),
                    ),
                )
                if manual_mode:
                    self.self_lowq_q_min.value = lower_value
                    self.self_lowq_q_max.value = upper_value
                else:
                    self.self_lowq_q_tail_low.value = lower_value
                    self.self_lowq_q_tail_high.value = upper_value

            if use_sliders and src is vertical_range:
                lower_value, upper_value = self._self_range_value(vertical_range, (0.0, 0.0))
                if manual_mode:
                    self.self_lowq_y_min.value = float(lower_value)
                    self.self_lowq_y_max.value = float(upper_value)
                else:
                    self.self_lowq_min_percentile.value = int(lower_value)
                    self.self_lowq_max_percentile.value = int(upper_value)

            # Adjust vertical slider bounds depending on mode before syncing values.
            if vertical_range is not None:
                if manual_mode:
                    series = self._load_self_dsdo_series()
                    if series is not None:
                        _q, y, _e, _path = series
                        finite = y[np.isfinite(y)]
                        if finite.size:
                            y_min = float(np.nanmin(finite))
                            y_max = float(np.nanmax(finite))
                            if np.isfinite(y_min) and np.isfinite(y_max) and y_max > y_min:
                                pad = 0.04 * (y_max - y_min)
                                vertical_range.start = float(y_min - pad)
                                vertical_range.end = float(y_max + pad)
                                vertical_range.step = max(float((y_max - y_min) / 800.0), 1e-6)
                else:
                    vertical_range.start = 0.0
                    vertical_range.end = 100.0
                    vertical_range.step = 1.0

            # Keep redesign sliders synced with canonical values when switching modes or using numeric inputs.
            if q_range is not None and (src is None or src is not q_range):
                if manual_mode:
                    self._set_self_range_value(
                        q_range,
                        (
                            float(self.self_lowq_q_min.value),
                            float(self.self_lowq_q_max.value),
                        ),
                    )
                else:
                    self._set_self_range_value(
                        q_range,
                        (
                            float(self.self_lowq_q_tail_low.value),
                            float(self.self_lowq_q_tail_high.value),
                        ),
                    )

            if vertical_range is not None and (src is None or src is not vertical_range):
                if manual_mode:
                    lower_value = float(getattr(self.self_lowq_y_min, "value", 0.0) or 0.0)
                    upper_value = float(getattr(self.self_lowq_y_max, "value", lower_value) or lower_value)
                    lower_value = float(np.clip(lower_value, float(vertical_range.start), float(vertical_range.end)))
                    upper_value = float(np.clip(upper_value, lower_value, float(vertical_range.end)))
                    self._set_self_range_value(vertical_range, (lower_value, upper_value))
                else:
                    lower_value = float(getattr(self.self_lowq_min_percentile, "value", 0) or 0)
                    upper_value = float(getattr(self.self_lowq_max_percentile, "value", lower_value) or lower_value)
                    lower_value = float(np.clip(lower_value, 0.0, 100.0))
                    upper_value = float(np.clip(upper_value, lower_value, 100.0))
                    self._set_self_range_value(vertical_range, (lower_value, upper_value))
        finally:
            self._suspend_self_scattering_events = False

        if not is_slider_value_event:
            self._persist_self_lowq_selection_to_context()
        self._sync_self_lowq_ui_summary()
        self._sync_self_lowq_buttons()
        self._update_self_lowq_value_labels()
        self._set_self_lowq_controls_visibility()
        self._schedule_self_lowq_plot_refresh(delay_ms=40 if is_slider_value_event else 0)

    def _on_self_lowq_controls_commit(self, event=None) -> None:
        if getattr(self, "_suspend_self_scattering_events", False) or self.current_project_state is None:
            return
        self._persist_self_lowq_selection_to_context()

    def _persist_self_lowq_selection_to_context(self) -> None:
        if self.current_project_root is None or self.current_project_state is None:
            return
        context_id = str(getattr(getattr(self, "self_context_select", None), "value", "") or "").strip()
        if not context_id:
            return
        manifest_ref = self._selected_self_manifest_ref()
        if not manifest_ref:
            return
        payload = load_context_manifest(self.current_project_root, manifest_ref)
        if not isinstance(payload, dict):
            return

        mode = self._normalize_self_lowq_mode(getattr(getattr(self, "self_lowq_selection_mode", None), "value", ""))
        selection: dict[str, object] = {"mode": mode, "use_sliders": bool(getattr(getattr(self, "self_lowq_use_sliders", None), "value", False))}
        if self._is_self_lowq_manual_mode(mode):
            selection.update(
                {
                    "q_min": float(getattr(self.self_lowq_q_min, "value", 0.0) or 0.0),
                    "q_max": float(getattr(self.self_lowq_q_max, "value", 0.0) or 0.0),
                    "y_min": float(getattr(self.self_lowq_y_min, "value", 0.0) or 0.0),
                    "y_max": float(getattr(self.self_lowq_y_max, "value", 0.0) or 0.0),
                }
            )
        else:
            selection.update(
                {
                    "q_start": float(getattr(self.self_lowq_q_tail_low, "value", 0.0) or 0.0),
                    "q_end": float(getattr(self.self_lowq_q_tail_high, "value", 0.0) or 0.0),
                    "min_percentile": int(getattr(self.self_lowq_min_percentile, "value", 0) or 0),
                    "max_percentile": int(getattr(self.self_lowq_max_percentile, "value", 0) or 0),
                }
            )

        decisions = payload.get("decisions") if isinstance(payload.get("decisions"), dict) else {}
        self_block = decisions.get("self_scattering") if isinstance(decisions.get("self_scattering"), dict) else {}
        lowq = self_block.get("lowq") if isinstance(self_block.get("lowq"), dict) else {}
        lowq["selection"] = selection
        self_block["lowq"] = lowq
        decisions["self_scattering"] = self_block
        payload["decisions"] = decisions
        try:
            write_context_manifest(self.current_project_root, context_id=context_id, payload=payload)
        except Exception:
            return

    def _load_self_lowq_from_context(self) -> None:
        if self.current_project_root is None or self.current_project_state is None:
            return
        context_id = str(getattr(getattr(self, "self_context_select", None), "value", "") or "").strip()
        if not context_id:
            return
        manifest_ref = self._selected_self_manifest_ref()
        if not manifest_ref:
            return
        payload = load_context_manifest(self.current_project_root, manifest_ref)
        if not isinstance(payload, dict):
            return
        decisions = payload.get("decisions") if isinstance(payload.get("decisions"), dict) else {}
        self_block = decisions.get("self_scattering") if isinstance(decisions.get("self_scattering"), dict) else {}
        lowq = self_block.get("lowq") if isinstance(self_block.get("lowq"), dict) else {}
        selection = lowq.get("selection") if isinstance(lowq.get("selection"), dict) else {}
        fit = lowq.get("fit") if isinstance(lowq.get("fit"), dict) else {}
        if not selection:
            selection = {}

        self._suspend_self_scattering_events = True
        try:
            mode = self._normalize_self_lowq_mode(selection.get("mode"))
            if hasattr(self, "self_lowq_selection_mode"):
                self.self_lowq_selection_mode.value = mode
            if hasattr(self, "self_lowq_use_sliders") and isinstance(selection.get("use_sliders"), bool):
                self.self_lowq_use_sliders.value = bool(selection["use_sliders"])
            if self._is_self_lowq_manual_mode(mode):
                for key, attr in (("q_min", "self_lowq_q_min"), ("q_max", "self_lowq_q_max"), ("y_min", "self_lowq_y_min"), ("y_max", "self_lowq_y_max")):
                    if hasattr(self, attr) and isinstance(selection.get(key), (int, float)):
                        getattr(self, attr).value = float(selection[key])
            else:
                for key, attr in (("q_start", "self_lowq_q_tail_low"), ("q_end", "self_lowq_q_tail_high")):
                    if hasattr(self, attr) and isinstance(selection.get(key), (int, float)):
                        getattr(self, attr).value = float(selection[key])
                for key, attr in (("min_percentile", "self_lowq_min_percentile"), ("max_percentile", "self_lowq_max_percentile")):
                    if hasattr(self, attr) and isinstance(selection.get(key), (int, float)):
                        getattr(self, attr).value = int(selection[key])
        finally:
            self._suspend_self_scattering_events = False

        # Best-effort: if a previous fit is persisted, keep it around for the table.
        if isinstance(fit, dict) and any(k in fit for k in ("q0", "q2", "q4")):
            self._self_lowq_last = {
                "project_root": str(getattr(self, "current_project_root", "") or ""),
                "context_id": context_id,
                "fit": {
                    k: float(fit[k])
                    for k in ("q0", "q2", "q4", "q0_e", "q2_e", "q4_e")
                    if k in fit and isinstance(fit.get(k), (int, float))
                },
                "window_used": fit.get("window_used") if isinstance(fit.get("window_used"), dict) else None,
            }

    def _refresh_self_lowq_panel(self) -> None:
        if self.current_project_root is None or self.current_project_state is None:
            return

        plot_pane = getattr(self, "self_lowq_redesign_plot_pane", None)
        if plot_pane is None:
            return
        alert_pane = getattr(self, "self_lowq_alert", None)
        window_table = getattr(self, "self_lowq_redesign_window_table", None)

        def _set_alert(message: str, *, alert_type: str, visible: bool = True) -> None:
            if alert_pane is None:
                return
            alert_pane.visible = bool(visible)
            alert_pane.object = message if visible else ""
            alert_pane.alert_type = alert_type

        def _set_window_table(html: str) -> None:
            if window_table is not None:
                window_table.object = html

        series = self._load_self_dsdo_series()
        if series is None:
            _set_alert("", alert_type="secondary", visible=False)
            plot_pane.object = None
            _set_window_table("")
            return

        q_all, y_all, _e_all, path = series
        selection = self._self_lowq_select_points(q=q_all, y=y_all)
        if selection.warnings:
            _set_alert(" ".join(selection.warnings), alert_type="warning", visible=True)
        else:
            _set_alert("", alert_type="secondary", visible=False)

        context_id = str(getattr(getattr(self, "self_context_select", None), "value", "") or "").strip()
        show_corrected = bool(getattr(getattr(self, "self_lowq_view_switch", None), "value", False))
        corrected = None
        fit = getattr(self, "_self_lowq_last", None)
        if isinstance(fit, dict):
            if str(fit.get("project_root") or "") == str(getattr(self, "current_project_root", "") or "") and str(fit.get("context_id") or "") == context_id:
                corrected = fit.get("corrected")
        if show_corrected and not isinstance(corrected, np.ndarray):
            corrected = None
            # Best-effort recompute from persisted fit params if available.
            if isinstance(fit, dict) and isinstance(fit.get("fit"), dict):
                try:
                    from toscana.models.scattering import self024

                    fr = fit["fit"]
                    q0 = float(fr.get("q0"))
                    q2 = float(fr.get("q2"))
                    q4 = float(fr.get("q4"))
                    y_lowq = np.asarray(self024(q_all, q0, q2, q4), dtype=float)
                    window_used = fit.get("window_used") if isinstance(fit.get("window_used"), dict) else {}
                    q_min = float(window_used.get("q_min")) if isinstance(window_used.get("q_min"), (int, float)) else float(selection.q_min)
                    q_max = float(window_used.get("q_max")) if isinstance(window_used.get("q_max"), (int, float)) else float(selection.q_max)
                    corrected = beam_stop_correct(q=q_all, y_raw=y_all, y_lowq=y_lowq, q_min=q_min, q_max=q_max)
                except Exception:
                    corrected = None

        title = f"dsdo (Low-Q) — {path.name}"
        fig = plot_pane.object if getattr(plot_pane, "object", None) is not None else None
        if fig is None:
            fig = build_self_lowq_figure(
                q=q_all,
                dsdo=y_all,
                q_subset=selection.q_subset,
                dsdo_subset=selection.y_subset,
                corrected=corrected,
                show_corrected=bool(show_corrected and corrected is not None),
                title=title,
                width=800,
                height=600,
                uirevision=f"self-lowq:{context_id}",
            )
        else:
            update_self_lowq_figure(
                fig,
                q=q_all,
                dsdo=y_all,
                q_subset=selection.q_subset,
                dsdo_subset=selection.y_subset,
                corrected=corrected,
                show_corrected=bool(show_corrected and corrected is not None),
                title=title,
                width=800,
                height=600,
                uirevision=f"self-lowq:{context_id}",
            )
        plot_pane.object = fig
        try:
            plot_pane.param.trigger("object")
        except Exception:
            pass

        _set_window_table(self._render_self_lowq_window_table(selection=selection, fit=fit))

    def _render_self_lowq_window_table(self, *, selection: LowQSelection, fit: dict | None) -> str:
        def _row(label: str, value: str) -> str:
            return f"<tr><td>{html_escape(label)}</td><td><code>{html_escape(value)}</code></td></tr>"

        lines = [
            "<div class=\"toscana-fit-window-table\">",
            "<table class=\"toscana-fit-result-table\">",
            "<thead><tr><th>Field</th><th>Value</th></tr></thead>",
            "<tbody>",
            f"<tr><td class=\"toscana-fit-result-table__param\">Mode</td><td class=\"toscana-fit-result-table__value\" style=\"text-align:left;\">{html_escape(self._self_lowq_mode_label(selection.mode))}</td></tr>",
            f"<tr><td class=\"toscana-fit-result-table__param\">Q min</td><td class=\"toscana-fit-result-table__value\" style=\"text-align:left;\"><code>{html_escape(f'{selection.q_min:.6g}')}</code></td></tr>",
            f"<tr><td class=\"toscana-fit-result-table__param\">Q max</td><td class=\"toscana-fit-result-table__value\" style=\"text-align:left;\"><code>{html_escape(f'{selection.q_max:.6g}')}</code></td></tr>",
            f"<tr><td class=\"toscana-fit-result-table__param\">Y min</td><td class=\"toscana-fit-result-table__value\" style=\"text-align:left;\"><code>{html_escape(f'{selection.y_min:.6g}')}</code></td></tr>",
            f"<tr><td class=\"toscana-fit-result-table__param\">Y max</td><td class=\"toscana-fit-result-table__value\" style=\"text-align:left;\"><code>{html_escape(f'{selection.y_max:.6g}')}</code></td></tr>",
            f"<tr><td class=\"toscana-fit-result-table__param\">Fit points</td><td class=\"toscana-fit-result-table__value\" style=\"text-align:left;\"><code>{int(selection.q_subset.size)}</code></td></tr>",
            "</tbody></table></div>",
        ]
        summary_html = "\n".join(lines)

        if not (isinstance(fit, dict) and isinstance(fit.get("fit"), dict)):
            return summary_html

        fr = fit["fit"]

        def _fmt_compact(v: object) -> str:
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

        param_rows = []
        for key in ("q0", "q2", "q4"):
            if key not in fr:
                continue
            err_key = f"{key}_e"
            param_rows.append(
                "<tr>"
                f"<td class=\"toscana-fit-result-table__param\">{html_escape(key)}</td>"
                f"<td class=\"toscana-fit-result-table__value\">{html_escape(_fmt_compact(fr.get(key)))}</td>"
                f"<td class=\"toscana-fit-result-table__err\">{html_escape(_fmt_compact(fr.get(err_key)))}</td>"
                "</tr>"
            )

        n_points = int(selection.q_subset.size)
        meta_html = (
            "<div class=\"toscana-fit-result-table__meta\">Selected points: "
            f"<strong>{n_points}</strong></div>"
        )

        fit_html = (
            "<div class=\"toscana-fit-window-table\">"
            "<div class=\"toscana-fit-result-table__title\">Fit result</div>"
            f"{meta_html}"
            "<table class=\"toscana-fit-result-table\">"
            "<thead><tr><th>Param</th><th>Value</th><th>±</th></tr></thead>"
            "<tbody>"
            + "".join(param_rows)
            + "</tbody>"
            "</table>"
            "</div>"
        )

        return summary_html + "\n<div style=\"height: 12px;\"></div>\n" + fit_html

    def _run_self_lowq_extrapolate(self, _event=None) -> None:
        if self.current_project_root is None or self.current_project_state is None:
            return
        series = self._load_self_dsdo_series()
        if series is None:
            if hasattr(self, "_show_warning_toast"):
                self._show_warning_toast("Select a context with `sample_dsdo_qdat` first.")
            return
        q_all, y_all, _e_all, _path = series
        selection = self._self_lowq_select_points(q=q_all, y=y_all)
        # Ensure the current selection is persisted alongside the fit results.
        self._persist_self_lowq_selection_to_context()
        if selection.q_subset.size < 3:
            if hasattr(self, "_show_warning_toast"):
                self._show_warning_toast("Not enough fit points. Widen the window.")
            return

        try:
            from toscana.models.scattering import self024
        except Exception as exc:
            if hasattr(self, "_show_error_toast"):
                self._show_error_toast(f"Could not import `toscana.models.scattering.self024`: {exc}")
            return

        try:
            from scipy.optimize import curve_fit
        except Exception as exc:
            if hasattr(self, "_show_error_toast"):
                self._show_error_toast(f"Could not import SciPy curve_fit: {exc}")
            return

        q_subset = np.asarray(selection.q_subset, dtype=float)
        y_subset = np.asarray(selection.y_subset, dtype=float)
        finite = np.isfinite(q_subset) & np.isfinite(y_subset)
        q_subset = q_subset[finite]
        y_subset = y_subset[finite]
        if q_subset.size < 3:
            if hasattr(self, "_show_warning_toast"):
                self._show_warning_toast("Not enough finite fit points. Adjust the window.")
            return

        # Bounds enforce monotonic increase for self024 (q2 <= 0 and q4 <= 0).
        p0 = [float(np.nanmax([np.nanmedian(y_subset), 1e-12])), -0.01, -0.001]
        lower = [0.0, -np.inf, -np.inf]
        upper = [np.inf, 0.0, 0.0]

        try:
            popt, pcov = curve_fit(self024, q_subset, y_subset, p0=p0, bounds=(lower, upper), maxfev=20000)
            q0, q2, q4 = [float(v) for v in popt]
            diag = np.diag(pcov) if pcov is not None else np.array([np.nan, np.nan, np.nan])
            errs = np.sqrt(np.maximum(diag, 0.0))
            q0_e, q2_e, q4_e = [float(v) if np.isfinite(v) else float("nan") for v in errs]
        except Exception as exc:
            if hasattr(self, "_show_error_toast"):
                self._show_error_toast(f"Low-Q fit failed: {exc}")
            return

        y_lowq = np.asarray(self024(q_all, q0, q2, q4), dtype=float)
        try:
            y_corrected = beam_stop_correct(q=q_all, y_raw=y_all, y_lowq=y_lowq, q_min=selection.q_min, q_max=selection.q_max)
        except Exception as exc:
            if hasattr(self, "_show_error_toast"):
                self._show_error_toast(f"Low-Q correction failed: {exc}")
            return

        context_id = str(getattr(getattr(self, "self_context_select", None), "value", "") or "").strip()
        self._self_lowq_last = {
            "project_root": str(getattr(self, "current_project_root", "") or ""),
            "context_id": context_id,
            "fit": {"q0": q0, "q2": q2, "q4": q4, "q0_e": q0_e, "q2_e": q2_e, "q4_e": q4_e},
            "corrected": y_corrected,
            "computed_at": now_iso(),
            "window_used": {"q_min": float(selection.q_min), "q_max": float(selection.q_max)},
        }

        self._persist_self_lowq_fit_to_context(selection=selection, fit=self._self_lowq_last["fit"])
        if hasattr(self, "_show_success_toast"):
            self._show_success_toast("Computed Low-Q extrapolation (in-memory).")
        self._refresh_self_lowq_panel()
        if hasattr(self, "_invalidate_self_fit_result"):
            self._invalidate_self_fit_result(reason="Low-Q extrapolation updated.")
        if hasattr(self, "_refresh_self_fit_button_states"):
            self._refresh_self_fit_button_states()

    def _persist_self_lowq_fit_to_context(self, *, selection: LowQSelection, fit: dict[str, float]) -> None:
        if self.current_project_root is None or self.current_project_state is None:
            return
        context_id = str(getattr(getattr(self, "self_context_select", None), "value", "") or "").strip()
        if not context_id:
            return
        manifest_ref = self._selected_self_manifest_ref()
        if not manifest_ref:
            return
        payload = load_context_manifest(self.current_project_root, manifest_ref)
        if not isinstance(payload, dict):
            return
        decisions = payload.get("decisions") if isinstance(payload.get("decisions"), dict) else {}
        self_block = decisions.get("self_scattering") if isinstance(decisions.get("self_scattering"), dict) else {}
        lowq = self_block.get("lowq") if isinstance(self_block.get("lowq"), dict) else {}
        lowq["fit"] = {
            **{k: float(v) for k, v in fit.items() if isinstance(v, (int, float))},
            "computed_at": now_iso(),
            "window_used": {
                "q_min": float(selection.q_min),
                "q_max": float(selection.q_max),
                "y_min": float(selection.y_min),
                "y_max": float(selection.y_max),
                "mode": str(selection.mode),
            },
        }
        self_block["lowq"] = lowq
        decisions["self_scattering"] = self_block
        payload["decisions"] = decisions
        try:
            write_context_manifest(self.current_project_root, context_id=context_id, payload=payload)
        except Exception:
            return

    # ---------------------------------------------------------------------
    # Self scattering: Data selection (ROI)
    # ---------------------------------------------------------------------

    def _toggle_self_data_selection_input_mode(self, _event=None) -> None:
        if self.current_project_state is None or getattr(self, "_suspend_self_scattering_events", False):
            return
        toggle = getattr(self, "self_data_selection_use_sliders", None)
        if toggle is None:
            return
        self._suspend_self_scattering_events = True
        try:
            toggle.value = not bool(getattr(toggle, "value", False))
        finally:
            self._suspend_self_scattering_events = False
        self._on_self_data_selection_controls_change()

    def _toggle_self_data_selection_method(self, _event=None) -> None:
        if self.current_project_state is None or getattr(self, "_suspend_self_scattering_events", False):
            return
        mode_widget = getattr(self, "self_data_selection_selection_mode", None)
        if mode_widget is None:
            return
        current = self._normalize_self_lowq_mode(getattr(mode_widget, "value", ""))
        next_mode = self._SELF_LOWQ_MODE_PERCENTILE if current == self._SELF_LOWQ_MODE_MANUAL else self._SELF_LOWQ_MODE_MANUAL
        self._suspend_self_scattering_events = True
        try:
            mode_widget.value = next_mode
        finally:
            self._suspend_self_scattering_events = False
        self._on_self_data_selection_controls_change()

    def _sync_self_data_selection_ui_summary(self) -> None:
        pane = getattr(self, "self_data_selection_redesign_mode_chips", None)
        if pane is None:
            return
        mode = self._normalize_self_lowq_mode(
            getattr(getattr(self, "self_data_selection_selection_mode", None), "value", "")
        )
        use_sliders = bool(getattr(getattr(self, "self_data_selection_use_sliders", None), "value", False))
        mode_label = "Manual window" if mode == self._SELF_LOWQ_MODE_MANUAL else "Percentile band"
        input_label = "Axis sliders" if use_sliders else "Numeric inputs"
        mode_kind = "manual" if mode == self._SELF_LOWQ_MODE_MANUAL else "band"
        input_kind = "slider" if use_sliders else "input"
        pane.object = (
            "<div class=\"toscana-normalization-fit-data-summary\">"
            f"<div class=\"toscana-normalization-fit-data-chip toscana-normalization-fit-data-chip--{mode_kind}\">{mode_label}</div>"
            f"<div class=\"toscana-normalization-fit-data-chip toscana-normalization-fit-data-chip--{input_kind}\">{input_label}</div>"
            "</div>"
        )

    def _sync_self_data_selection_buttons(self) -> None:
        button_input_mode = getattr(self, "self_data_selection_redesign_switch_input_mode", None)
        button_method = getattr(self, "self_data_selection_redesign_switch_method", None)
        if button_input_mode is None and button_method is None:
            return
        mode = self._normalize_self_lowq_mode(
            getattr(getattr(self, "self_data_selection_selection_mode", None), "value", "")
        )
        use_sliders = bool(getattr(getattr(self, "self_data_selection_use_sliders", None), "value", False))
        manual_mode = mode == self._SELF_LOWQ_MODE_MANUAL
        if button_input_mode is not None:
            button_input_mode.button_type = "warning" if use_sliders else "primary"
        if button_method is not None:
            button_method.button_type = "warning" if manual_mode else "primary"

    def _update_self_data_selection_value_labels(self) -> None:
        lower = getattr(self, "self_data_selection_redesign_vertical_lower_value", None)
        upper = getattr(self, "self_data_selection_redesign_vertical_upper_value", None)
        if lower is None or upper is None:
            return
        mode = self._normalize_self_lowq_mode(
            getattr(getattr(self, "self_data_selection_selection_mode", None), "value", "")
        )
        manual_mode = mode == self._SELF_LOWQ_MODE_MANUAL
        use_sliders = bool(getattr(getattr(self, "self_data_selection_use_sliders", None), "value", False))

        vertical_lower_input = getattr(self, "self_data_selection_redesign_vertical_lower_input", None)
        vertical_upper_input = getattr(self, "self_data_selection_redesign_vertical_upper_input", None)
        q_input_row = getattr(self, "self_data_selection_redesign_q_input_row", None)
        q_start_input = getattr(self, "self_data_selection_redesign_q_start_input", None)
        q_end_input = getattr(self, "self_data_selection_redesign_q_end_input", None)
        q_range = getattr(self, "self_data_selection_redesign_q_range_slider", None)
        vertical_range = getattr(self, "self_data_selection_redesign_vertical_range_slider", None)

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
        lower.visible = bool(use_sliders)
        upper.visible = bool(use_sliders)
        if vertical_lower_input is not None:
            vertical_lower_input.visible = not use_sliders
        if vertical_upper_input is not None:
            vertical_upper_input.visible = not use_sliders

        if manual_mode:
            y_min = float(getattr(getattr(self, "self_data_selection_y_min", None), "value", 0.0) or 0.0)
            y_max = float(getattr(getattr(self, "self_data_selection_y_max", None), "value", 0.0) or 0.0)
            lower.object = f"Intensity min: {y_min:.4g}"
            upper.object = f"Intensity max: {y_max:.4g}"
            if vertical_lower_input is not None:
                try:
                    if vertical_range is not None:
                        vertical_lower_input.start = float(vertical_range.start)
                        vertical_lower_input.end = float(vertical_range.end)
                    vertical_lower_input.step = 1e-6
                    vertical_lower_input.value = y_min
                except Exception:
                    pass
            if vertical_upper_input is not None:
                try:
                    if vertical_range is not None:
                        vertical_upper_input.start = float(vertical_range.start)
                        vertical_upper_input.end = float(vertical_range.end)
                    vertical_upper_input.step = 1e-6
                    vertical_upper_input.value = y_max
                except Exception:
                    pass
        else:
            min_pct = int(getattr(getattr(self, "self_data_selection_min_percentile", None), "value", 0) or 0)
            max_pct = int(getattr(getattr(self, "self_data_selection_max_percentile", None), "value", 0) or 0)
            lower.object = f"Lower percentile: {min_pct:d}"
            upper.object = f"Upper percentile: {max_pct:d}"
            if vertical_lower_input is not None:
                try:
                    vertical_lower_input.start = 0
                    vertical_lower_input.end = 100
                    vertical_lower_input.step = 1
                    vertical_lower_input.value = min_pct
                except Exception:
                    pass
            if vertical_upper_input is not None:
                try:
                    vertical_upper_input.start = 0
                    vertical_upper_input.end = 100
                    vertical_upper_input.step = 1
                    vertical_upper_input.value = max_pct
                except Exception:
                    pass

        # Keep numeric inputs in sync.
        if q_start_input is not None:
            try:
                q_start_input.value = float(
                    getattr(
                        getattr(self, "self_data_selection_q_min" if manual_mode else "self_data_selection_q_tail_low", None),
                        "value",
                        0.0,
                    )
                    or 0.0
                )
            except Exception:
                pass
        if q_end_input is not None:
            try:
                q_end_input.value = float(
                    getattr(
                        getattr(self, "self_data_selection_q_max" if manual_mode else "self_data_selection_q_tail_high", None),
                        "value",
                        0.0,
                    )
                    or 0.0
                )
            except Exception:
                pass

    def _on_self_data_selection_redesign_numeric_input_change(self, event=None) -> None:
        if getattr(self, "_suspend_self_scattering_events", False) or self.current_project_state is None:
            return
        use_sliders = bool(getattr(getattr(self, "self_data_selection_use_sliders", None), "value", False))
        if use_sliders or event is None:
            return
        src = getattr(event, "obj", None)
        if src is None:
            return
        mode = self._normalize_self_lowq_mode(getattr(getattr(self, "self_data_selection_selection_mode", None), "value", ""))
        manual_mode = mode == self._SELF_LOWQ_MODE_MANUAL

        q_start_input = getattr(self, "self_data_selection_redesign_q_start_input", None)
        q_end_input = getattr(self, "self_data_selection_redesign_q_end_input", None)
        vertical_lower_input = getattr(self, "self_data_selection_redesign_vertical_lower_input", None)
        vertical_upper_input = getattr(self, "self_data_selection_redesign_vertical_upper_input", None)

        def _to_float(value: object, fallback: float) -> float:
            try:
                val = float(value)
            except Exception:
                return fallback
            return val if np.isfinite(val) else fallback

        self._suspend_self_scattering_events = True
        try:
            if src is q_start_input:
                if manual_mode:
                    current = float(getattr(self.self_data_selection_q_min, "value", 0.0) or 0.0)
                    self.self_data_selection_q_min.value = _to_float(getattr(src, "value", None), current)
                else:
                    current = float(getattr(self.self_data_selection_q_tail_low, "value", 0.0) or 0.0)
                    self.self_data_selection_q_tail_low.value = _to_float(getattr(src, "value", None), current)
            elif src is q_end_input:
                if manual_mode:
                    current = float(getattr(self.self_data_selection_q_max, "value", 0.0) or 0.0)
                    self.self_data_selection_q_max.value = _to_float(getattr(src, "value", None), current)
                else:
                    current = float(getattr(self.self_data_selection_q_tail_high, "value", 0.0) or 0.0)
                    self.self_data_selection_q_tail_high.value = _to_float(getattr(src, "value", None), current)
            elif src in (vertical_lower_input, vertical_upper_input):
                raw = getattr(src, "value", None)
                if manual_mode:
                    if src is vertical_lower_input:
                        current = float(getattr(self.self_data_selection_y_min, "value", 0.0) or 0.0)
                        self.self_data_selection_y_min.value = _to_float(raw, current)
                    if src is vertical_upper_input:
                        current = float(getattr(self.self_data_selection_y_max, "value", 0.0) or 0.0)
                        self.self_data_selection_y_max.value = _to_float(raw, current)
                else:
                    if src is vertical_lower_input:
                        current = int(getattr(self.self_data_selection_min_percentile, "value", 0) or 0)
                        self.self_data_selection_min_percentile.value = int(_to_float(raw, float(current)))
                    if src is vertical_upper_input:
                        current = int(getattr(self.self_data_selection_max_percentile, "value", 0) or 0)
                        self.self_data_selection_max_percentile.value = int(_to_float(raw, float(current)))
        finally:
            self._suspend_self_scattering_events = False

        self._on_self_data_selection_controls_change()

    def _load_self_dsdo_for_data_selection(self) -> tuple[np.ndarray, np.ndarray, np.ndarray, str] | None:
        series = self._load_self_dsdo_series()
        if series is None:
            return None
        q_all, y_all, e_all, _path = series

        # Prefer corrected dsdo (extrapolated) if available from the previous subsection.
        corrected = None
        context_id = str(getattr(getattr(self, "self_context_select", None), "value", "") or "").strip()
        fit = getattr(self, "_self_lowq_last", None)
        if isinstance(fit, dict):
            if str(fit.get("project_root") or "") == str(getattr(self, "current_project_root", "") or "") and str(
                fit.get("context_id") or ""
            ) == context_id:
                corrected = fit.get("corrected")
            if not isinstance(corrected, np.ndarray) and isinstance(fit.get("fit"), dict):
                try:
                    from toscana.models.scattering import self024

                    fr = fit["fit"]
                    q0 = float(fr.get("q0"))
                    q2 = float(fr.get("q2"))
                    q4 = float(fr.get("q4"))
                    y_lowq = np.asarray(self024(q_all, q0, q2, q4), dtype=float)
                    window_used = fit.get("window_used") if isinstance(fit.get("window_used"), dict) else {}
                    if isinstance(window_used.get("q_min"), (int, float)) and isinstance(window_used.get("q_max"), (int, float)):
                        q_min = float(window_used["q_min"])
                        q_max = float(window_used["q_max"])
                    else:
                        # Fall back to the currently configured Low-Q selection window (best-effort).
                        try:
                            sel = self._self_lowq_select_points(q=q_all, y=y_all)
                            q_min = float(sel.q_min)
                            q_max = float(sel.q_max)
                        except Exception:
                            q_min = 0.45
                            q_max = 2.0
                    corrected = beam_stop_correct(q=q_all, y_raw=y_all, y_lowq=y_lowq, q_min=q_min, q_max=q_max)
                except Exception:
                    corrected = None

        if isinstance(corrected, np.ndarray) and corrected.shape == y_all.shape:
            return q_all, corrected, e_all, "corrected"
        return q_all, y_all, e_all, "raw"

    def _self_data_selection_select_points(self, *, q: np.ndarray, y: np.ndarray) -> LowQSelection:
        mode = self._normalize_self_lowq_mode(
            getattr(getattr(self, "self_data_selection_selection_mode", None), "value", "")
        )
        warnings: list[str] = []
        if mode == self._SELF_LOWQ_MODE_MANUAL:
            q_min = float(getattr(self.self_data_selection_q_min, "value", 0.0) or 0.0)
            q_max = float(getattr(self.self_data_selection_q_max, "value", 0.0) or 0.0)
            y_min = float(getattr(self.self_data_selection_y_min, "value", 0.0) or 0.0)
            y_max = float(getattr(self.self_data_selection_y_max, "value", 0.0) or 0.0)
            if q_max < q_min:
                warnings.append("Manual window has `q_max < q_min`.")
            if y_max < y_min:
                warnings.append("Manual window has `y_max < y_min`.")
            mask = (q >= q_min) & (q <= q_max) & (y >= y_min) & (y <= y_max)
            return LowQSelection(mode=mode, q_min=q_min, q_max=q_max, y_min=y_min, y_max=y_max, q_subset=q[mask], y_subset=y[mask], warnings=warnings)

        q_min = float(getattr(self.self_data_selection_q_tail_low, "value", 0.0) or 0.0)
        q_max = float(getattr(self.self_data_selection_q_tail_high, "value", 0.0) or 0.0)
        min_pct = int(getattr(self.self_data_selection_min_percentile, "value", 0) or 0)
        max_pct = int(getattr(self.self_data_selection_max_percentile, "value", 0) or 0)
        if q_max < q_min:
            warnings.append("Percentile band has `Q end < Q start`.")
        if max_pct < min_pct:
            warnings.append("Percentile band has `upper percentile < lower percentile`.")

        # Match Normalization percentile-band behavior:
        # percentiles are computed from the full intensity distribution (not restricted by Q).
        finite_y = y[np.isfinite(y)]
        if finite_y.size == 0:
            y_min = float("nan")
            y_max = float("nan")
        else:
            y_min = float(np.percentile(finite_y, min_pct))
            y_max = float(np.percentile(finite_y, max_pct))
        mask = (q >= q_min) & (q <= q_max) & (y >= y_min) & (y <= y_max)
        return LowQSelection(mode=mode, q_min=q_min, q_max=q_max, y_min=y_min, y_max=y_max, q_subset=q[mask], y_subset=y[mask], warnings=warnings)

    def _persist_self_data_selection_to_context(self) -> None:
        if self.current_project_root is None or self.current_project_state is None:
            return
        context_id = str(getattr(getattr(self, "self_context_select", None), "value", "") or "").strip()
        if not context_id:
            return
        manifest_ref = self._selected_self_manifest_ref()
        if not manifest_ref:
            return
        payload = load_context_manifest(self.current_project_root, manifest_ref)
        if not isinstance(payload, dict):
            return

        mode = self._normalize_self_lowq_mode(getattr(self.self_data_selection_selection_mode, "value", ""))
        selection: dict[str, object] = {"mode": mode, "use_sliders": bool(getattr(self.self_data_selection_use_sliders, "value", False))}
        if mode == self._SELF_LOWQ_MODE_MANUAL:
            selection.update(
                {
                    "q_min": float(getattr(self.self_data_selection_q_min, "value", 0.0) or 0.0),
                    "q_max": float(getattr(self.self_data_selection_q_max, "value", 0.0) or 0.0),
                    "y_min": float(getattr(self.self_data_selection_y_min, "value", 0.0) or 0.0),
                    "y_max": float(getattr(self.self_data_selection_y_max, "value", 0.0) or 0.0),
                }
            )
        else:
            selection.update(
                {
                    "q_start": float(getattr(self.self_data_selection_q_tail_low, "value", 0.0) or 0.0),
                    "q_end": float(getattr(self.self_data_selection_q_tail_high, "value", 0.0) or 0.0),
                    "min_percentile": int(getattr(self.self_data_selection_min_percentile, "value", 0) or 0),
                    "max_percentile": int(getattr(self.self_data_selection_max_percentile, "value", 0) or 0),
                }
            )

        decisions = payload.get("decisions") if isinstance(payload.get("decisions"), dict) else {}
        self_block = decisions.get("self_scattering") if isinstance(decisions.get("self_scattering"), dict) else {}
        self_block["data_selection"] = selection
        decisions["self_scattering"] = self_block
        payload["decisions"] = decisions
        try:
            write_context_manifest(self.current_project_root, context_id=context_id, payload=payload)
        except Exception:
            return

    def _load_self_data_selection_from_context(self) -> None:
        if self.current_project_root is None or self.current_project_state is None:
            return
        context_id = str(getattr(getattr(self, "self_context_select", None), "value", "") or "").strip()
        if not context_id:
            return
        manifest_ref = self._selected_self_manifest_ref()
        if not manifest_ref:
            return
        payload = load_context_manifest(self.current_project_root, manifest_ref)
        if not isinstance(payload, dict):
            return
        decisions = payload.get("decisions") if isinstance(payload.get("decisions"), dict) else {}
        self_block = decisions.get("self_scattering") if isinstance(decisions.get("self_scattering"), dict) else {}
        selection = self_block.get("data_selection") if isinstance(self_block.get("data_selection"), dict) else {}
        if not selection:
            return

        self._suspend_self_scattering_events = True
        try:
            mode = self._normalize_self_lowq_mode(selection.get("mode"))
            self.self_data_selection_selection_mode.value = mode
            if isinstance(selection.get("use_sliders"), bool):
                self.self_data_selection_use_sliders.value = bool(selection["use_sliders"])
            if mode == self._SELF_LOWQ_MODE_MANUAL:
                for key, attr in (("q_min", "self_data_selection_q_min"), ("q_max", "self_data_selection_q_max"), ("y_min", "self_data_selection_y_min"), ("y_max", "self_data_selection_y_max")):
                    if isinstance(selection.get(key), (int, float)):
                        getattr(self, attr).value = float(selection[key])
            else:
                for key, attr in (("q_start", "self_data_selection_q_tail_low"), ("q_end", "self_data_selection_q_tail_high")):
                    if isinstance(selection.get(key), (int, float)):
                        getattr(self, attr).value = float(selection[key])
                for key, attr in (("min_percentile", "self_data_selection_min_percentile"), ("max_percentile", "self_data_selection_max_percentile")):
                    if isinstance(selection.get(key), (int, float)):
                        getattr(self, attr).value = int(selection[key])
        finally:
            self._suspend_self_scattering_events = False

    def _on_self_data_selection_controls_change(self, event=None) -> None:
        if getattr(self, "_suspend_self_scattering_events", False) or self.current_project_state is None:
            return
        if hasattr(self, "_set_self_data_selection_controls_visibility"):
            self._set_self_data_selection_controls_visibility()
        use_sliders = bool(getattr(self.self_data_selection_use_sliders, "value", False))
        src = getattr(event, "obj", None) if event is not None else None
        event_name = str(getattr(event, "name", "") or "") if event is not None else ""
        range_slider_sources = tuple(
            getattr(self, name)
            for name in ("self_data_selection_redesign_q_range_slider", "self_data_selection_redesign_vertical_range_slider")
            if hasattr(self, name)
        )
        is_slider_value_event = bool(use_sliders and src is not None and event_name == "value" and src in range_slider_sources)

        self._suspend_self_scattering_events = True
        try:
            mode = self._normalize_self_lowq_mode(getattr(self.self_data_selection_selection_mode, "value", ""))
            manual_mode = mode == self._SELF_LOWQ_MODE_MANUAL
            q_range = getattr(self, "self_data_selection_redesign_q_range_slider", None)
            vertical_range = getattr(self, "self_data_selection_redesign_vertical_range_slider", None)

            # Adjust vertical slider bounds depending on mode before syncing values.
            if vertical_range is not None:
                if manual_mode:
                    try:
                        series = self._load_self_dsdo_for_data_selection()
                    except Exception:
                        series = None
                    if series is not None:
                        _q, y, _e, _mode_used = series
                        finite = y[np.isfinite(y)]
                        if finite.size:
                            y_min = float(np.nanmin(finite))
                            y_max = float(np.nanmax(finite))
                            if np.isfinite(y_min) and np.isfinite(y_max) and y_max > y_min:
                                pad = 0.04 * (y_max - y_min)
                                vertical_range.start = float(y_min - pad)
                                vertical_range.end = float(y_max + pad)
                                vertical_range.step = max(float((y_max - y_min) / 800.0), 1e-6)
                else:
                    vertical_range.start = 0.0
                    vertical_range.end = 100.0
                    vertical_range.step = 1.0

            if use_sliders and src is q_range and q_range is not None:
                lower_value, upper_value = self._self_range_value(q_range, (0.0, 0.0))
                if manual_mode:
                    self.self_data_selection_q_min.value = lower_value
                    self.self_data_selection_q_max.value = upper_value
                else:
                    self.self_data_selection_q_tail_low.value = lower_value
                    self.self_data_selection_q_tail_high.value = upper_value

            if use_sliders and src is vertical_range and vertical_range is not None:
                lower_value, upper_value = self._self_range_value(vertical_range, (0.0, 0.0))
                if manual_mode:
                    self.self_data_selection_y_min.value = float(lower_value)
                    self.self_data_selection_y_max.value = float(upper_value)
                else:
                    self.self_data_selection_min_percentile.value = int(lower_value)
                    self.self_data_selection_max_percentile.value = int(upper_value)

            # Sync redesign sliders to current values.
            if q_range is not None and (src is None or src is not q_range):
                if manual_mode:
                    self._set_self_range_value(q_range, (float(self.self_data_selection_q_min.value), float(self.self_data_selection_q_max.value)))
                else:
                    self._set_self_range_value(q_range, (float(self.self_data_selection_q_tail_low.value), float(self.self_data_selection_q_tail_high.value)))

            if vertical_range is not None and (src is None or src is not vertical_range):
                if manual_mode:
                    self._set_self_range_value(vertical_range, (float(self.self_data_selection_y_min.value), float(self.self_data_selection_y_max.value)))
                else:
                    self._set_self_range_value(vertical_range, (float(self.self_data_selection_min_percentile.value), float(self.self_data_selection_max_percentile.value)))
        finally:
            self._suspend_self_scattering_events = False

        if not is_slider_value_event:
            self._persist_self_data_selection_to_context()
        self._sync_self_data_selection_ui_summary()
        self._sync_self_data_selection_buttons()
        self._update_self_data_selection_value_labels()
        self._schedule_self_data_selection_plot_refresh(delay_ms=40 if is_slider_value_event else 0)
        if hasattr(self, "_invalidate_self_fit_result"):
            current_snap = self._self_fit_selection_snapshot()
            last_seen = getattr(self, "_self_fit_last_seen_selection_snapshot", None)
            if not isinstance(last_seen, dict):
                self._self_fit_last_seen_selection_snapshot = current_snap
            elif last_seen != current_snap:
                self._self_fit_last_seen_selection_snapshot = current_snap
                self._invalidate_self_fit_result(reason="Data selection changed.")

    def _on_self_data_selection_controls_commit(self, event=None) -> None:
        if getattr(self, "_suspend_self_scattering_events", False) or self.current_project_state is None:
            return
        self._persist_self_data_selection_to_context()

    def _schedule_self_data_selection_plot_refresh(self, *, delay_ms: int = 75) -> None:
        if self.current_project_state is None:
            return
        if not hasattr(self, "_refresh_self_data_selection_panel"):
            return
        doc = getattr(pn.state, "curdoc", None)
        if doc is None:
            self._refresh_self_data_selection_panel()
            return
        handle = getattr(self, "_self_data_selection_refresh_handle", None)
        if handle is not None:
            try:
                doc.remove_timeout_callback(handle)
            except Exception:
                pass
            self._self_data_selection_refresh_handle = None

        def _run() -> None:
            self._self_data_selection_refresh_handle = None
            self._refresh_self_data_selection_panel()

        try:
            self._self_data_selection_refresh_handle = doc.add_timeout_callback(_run, int(delay_ms))
        except Exception:
            self._self_data_selection_refresh_handle = None
            self._refresh_self_data_selection_panel()

    def _refresh_self_data_selection_panel(self) -> None:
        if self.current_project_root is None or self.current_project_state is None:
            return
        pane = getattr(self, "self_data_selection_redesign_plot_pane", None)
        table = getattr(self, "self_data_selection_redesign_window_table", None)
        alert_pane = getattr(self, "self_data_selection_alert", None)
        if pane is None:
            return

        def _set_alert(message: str, *, alert_type: str, visible: bool = True) -> None:
            if alert_pane is None:
                return
            alert_pane.visible = bool(visible)
            alert_pane.object = message if visible else ""
            alert_pane.alert_type = alert_type

        series = self._load_self_dsdo_for_data_selection()
        if series is None:
            pane.object = None
            if table is not None:
                table.object = ""
            _set_alert("", alert_type="secondary", visible=False)
            return
        q_all, y_all, _e, mode_used = series
        selection = self._self_data_selection_select_points(q=q_all, y=y_all)
        if selection.warnings:
            _set_alert(" ".join(selection.warnings), alert_type="warning", visible=True)
        else:
            _set_alert("", alert_type="secondary", visible=False)

        context_id = str(getattr(getattr(self, "self_context_select", None), "value", "") or "").strip()
        fig = pane.object if getattr(pane, "object", None) is not None else None
        title = f"dsdo — {'Corrected' if mode_used == 'corrected' else 'Raw'}"
        if fig is None:
            fig = build_self_lowq_figure(
                q=q_all,
                dsdo=y_all,
                q_subset=selection.q_subset,
                dsdo_subset=selection.y_subset,
                corrected=None,
                show_corrected=False,
                title=title,
                width=800,
                height=600,
                uirevision=f"self-data-selection:{context_id}",
            )
        else:
            update_self_lowq_figure(
                fig,
                q=q_all,
                dsdo=y_all,
                q_subset=selection.q_subset,
                dsdo_subset=selection.y_subset,
                corrected=None,
                show_corrected=False,
                title=title,
                width=800,
                height=600,
                uirevision=f"self-data-selection:{context_id}",
            )
        pane.object = fig
        try:
            pane.param.trigger("object")
        except Exception:
            pass
        if table is not None:
            table.object = self._render_self_lowq_window_table(selection=selection, fit=None)

    # ------------------------------
    # Self scattering (Fit model)
    # ------------------------------

    def _normalize_self_fit_model(self, raw: object) -> str:
        model = str(raw or "").strip()
        if model in (self._SELF_FIT_MODEL_VANA, "vanaQdep", "VanaQdep"):
            return self._SELF_FIT_MODEL_VANA
        if model in (self._SELF_FIT_MODEL_POLY, "polyQ4", "PolyQ4"):
            return self._SELF_FIT_MODEL_POLY
        if model in (self._SELF_FIT_MODEL_LORGAU, "LorGau", "lorgau"):
            return self._SELF_FIT_MODEL_LORGAU
        return self._SELF_FIT_MODEL_VANA

    def _self_fit_param_keys(self, model: str) -> list[str]:
        model = self._normalize_self_fit_model(model)
        if model == self._SELF_FIT_MODEL_POLY:
            return ["a0", "a1", "a2", "a3", "a4"]
        if model == self._SELF_FIT_MODEL_LORGAU:
            return ["f0", "eta", "sigma", "gamma", "bckg"]
        return ["a0", "a1", "a2", "A", "lowQ", "Q0", "dQ"]

    def _self_fit_widget_prefix(self, model: str) -> str:
        model = self._normalize_self_fit_model(model)
        if model == self._SELF_FIT_MODEL_POLY:
            return "self_fit_params_poly"
        if model == self._SELF_FIT_MODEL_LORGAU:
            return "self_fit_params_lorgau"
        return "self_fit_params_vana"

    def _self_fit_active_model(self) -> str:
        raw = getattr(getattr(self, "self_fit_model_selector", None), "value", "")
        return self._normalize_self_fit_model(raw)

    def _self_fit_set_model_visibility(self, model: str) -> None:
        model = self._normalize_self_fit_model(model)
        for attr in ("self_fit_params_vana_section", "self_fit_params_poly_section", "self_fit_params_lorgau_section"):
            if hasattr(self, attr):
                getattr(self, attr).visible = False
        for attr in ("self_fit_params_vana_bounds_grid", "self_fit_params_poly_bounds_grid", "self_fit_params_lorgau_bounds_grid"):
            if hasattr(self, attr):
                getattr(self, attr).visible = False

        if model == self._SELF_FIT_MODEL_POLY:
            if hasattr(self, "self_fit_params_poly_section"):
                self.self_fit_params_poly_section.visible = True
            if hasattr(self, "self_fit_params_poly_bounds_grid"):
                self.self_fit_params_poly_bounds_grid.visible = True
            return
        if model == self._SELF_FIT_MODEL_LORGAU:
            if hasattr(self, "self_fit_params_lorgau_section"):
                self.self_fit_params_lorgau_section.visible = True
            if hasattr(self, "self_fit_params_lorgau_bounds_grid"):
                self.self_fit_params_lorgau_bounds_grid.visible = True
            return

        if hasattr(self, "self_fit_params_vana_section"):
            self.self_fit_params_vana_section.visible = True
        if hasattr(self, "self_fit_params_vana_bounds_grid"):
            self.self_fit_params_vana_bounds_grid.visible = True

    def _self_fit_clear_alert(self) -> None:
        pane = getattr(self, "self_fit_params_alert", None)
        if pane is None:
            return
        pane.object = ""
        pane.alert_type = "secondary"
        pane.visible = False

    def _self_fit_set_alert(self, message: str, *, alert_type: str = "warning") -> None:
        pane = getattr(self, "self_fit_params_alert", None)
        if pane is None:
            return
        pane.object = str(message)
        pane.alert_type = str(alert_type)
        pane.visible = bool(message)

    def _sync_self_export_prompt_visibility(self) -> None:
        card = getattr(self, "self_export_prompt_card", None)
        pane = getattr(self, "self_export_prompt", None)
        if card is None or pane is None:
            return
        card.visible = bool(getattr(pane, "visible", False))

    def _resolve_self_export_dir(self) -> Path | None:
        if self.current_project_root is None:
            return None
        raw = str(getattr(getattr(self, "self_export_folder_input", None), "value", "") or "").strip()
        if not raw:
            raw = "self_scattering/"
        candidate = Path(raw).expanduser()
        if not candidate.is_absolute():
            candidate = (self.current_project_root / candidate).resolve(strict=False)
        return candidate

    def _self_export_snapshot(self) -> dict[str, object]:
        snapshot: dict[str, object] = {
            "ready": False,
            "context_id": None,
            "export_root": None,
            "user_target_dir": None,
            "canonical_target_dir": None,
            "qspdata_target_dir": None,
            "fit_model": None,
            "sample_title": None,
            "filename_q": None,
            "filename_a": None,
            "filename_fit": None,
            "reason": None,
        }

        if self.current_project_root is None or self.current_project_state is None:
            snapshot["reason"] = "Open a project first."
            return snapshot

        context_id = str(getattr(getattr(self, "self_context_select", None), "value", "") or "").strip()
        if not context_id:
            snapshot["reason"] = "Select a context first."
            return snapshot
        snapshot["context_id"] = context_id

        fit_payload = self._self_static_structure_factor_current_fit_payload()
        if not isinstance(fit_payload, dict):
            snapshot["reason"] = "Run Fit first."
            return snapshot
        if self._self_static_structure_factor_is_stale(fit_payload):
            snapshot["reason"] = "Fit is stale. Run Fit again."
            return snapshot

        export_root = self._resolve_self_export_dir()
        snapshot["export_root"] = str(export_root) if export_root is not None else None
        if export_root is None:
            snapshot["reason"] = "Choose an export folder."
            return snapshot

        manifest_ref = self._selected_self_manifest_ref()
        payload = load_context_manifest(self.current_project_root, manifest_ref) if manifest_ref else None
        payload = payload if isinstance(payload, dict) else None
        measurement = self._load_measurement_for_self_context(payload) if isinstance(payload, dict) else None
        if measurement is None or not hasattr(measurement, "wavelength"):
            snapshot["reason"] = "Measurement/wavelength missing."
            return snapshot
        try:
            wl = float(getattr(measurement, "wavelength"))
        except Exception:
            wl = float("nan")
        if not np.isfinite(wl) or wl <= 0:
            snapshot["reason"] = "Invalid wavelength."
            return snapshot

        series = self._compute_self_static_structure_factor_series()
        if series is None:
            snapshot["reason"] = "Static Structure Factor not ready."
            return snapshot

        q = series.get("q")
        soq = series.get("soq")
        soq_err = series.get("soq_err")
        if q is None or soq is None or soq_err is None:
            snapshot["reason"] = "No S(Q) series available."
            return snapshot

        sample_title = None
        try:
            if hasattr(measurement, "Title"):
                sample_title = str(getattr(measurement, "Title") or "").strip()
        except Exception:
            sample_title = None
        if not sample_title and isinstance(payload, dict):
            sample = payload.get("sample") if isinstance(payload.get("sample"), dict) else {}
            if isinstance(sample.get("title"), str):
                sample_title = sample.get("title")
        stem = self._sanitize_export_filename_stem(str(sample_title or context_id))
        filename_q = f"{stem}_SOQ.qdat"
        filename_a = f"{stem}_SOQ.adat"

        user_target_dir = export_root / context_id
        canonical_target_dir = self._project_data_path("self_scattering", context_id)
        qspdata_target_dir = self._project_data_path("qspdata")
        snapshot["user_target_dir"] = str(user_target_dir)
        snapshot["canonical_target_dir"] = str(canonical_target_dir)
        snapshot["qspdata_target_dir"] = str(qspdata_target_dir)
        snapshot["fit_model"] = self._normalize_self_fit_model(fit_payload.get("model"))
        snapshot["sample_title"] = sample_title or ""
        snapshot["filename_q"] = filename_q
        snapshot["filename_a"] = filename_a
        snapshot["filename_fit"] = "self_fit.qdat"
        snapshot["ready"] = True
        return snapshot

    def _refresh_self_export_hovercard(self) -> None:
        if not hasattr(self, "self_export_info_hover"):
            return

        snap = self._self_export_snapshot()
        ready = bool(snap.get("ready", False))
        status = "Ready" if ready else "Not ready"
        reason = html_escape(str(snap.get("reason") or ""))

        body_lines = [f"<div><strong>Status:</strong> {html_escape(status)}</div>"]
        if ready:
            context_id = html_escape(str(snap.get("context_id") or ""))
            export_root = html_escape(str(snap.get("export_root") or ""))
            user_target_dir = html_escape(str(snap.get("user_target_dir") or ""))
            canonical_target_dir = html_escape(str(snap.get("canonical_target_dir") or ""))
            qspdata_target_dir = html_escape(str(snap.get("qspdata_target_dir") or ""))
            fit_model = html_escape(str(snap.get("fit_model") or ""))
            filename_q = html_escape(str(snap.get("filename_q") or ""))
            filename_a = html_escape(str(snap.get("filename_a") or ""))
            filename_fit = html_escape(str(snap.get("filename_fit") or ""))
            if context_id:
                body_lines.append(f"<div><strong>Context:</strong> {context_id}</div>")
            if fit_model:
                body_lines.append(f"<div><strong>Fit model:</strong> {fit_model}</div>")
            if export_root:
                body_lines.append(f"<div><strong>Export root:</strong> {export_root}</div>")
            if user_target_dir and user_target_dir != canonical_target_dir:
                body_lines.append(f"<div><strong>User export:</strong> {user_target_dir}</div>")
            if canonical_target_dir:
                body_lines.append(f"<div><strong>Canonical export:</strong> {canonical_target_dir}</div>")
            if qspdata_target_dir:
                body_lines.append(f"<div><strong>QSPData mirror:</strong> {qspdata_target_dir}</div>")
            if filename_q or filename_a or filename_fit:
                body_lines.append(
                    "<div><strong>Files:</strong> "
                    f"{filename_q or ''}"
                    + (f", {filename_a}" if filename_a else "")
                    + (f", {filename_fit}" if filename_fit else "")
                    + "</div>"
                )
        elif reason:
            body_lines.append(f"<div style=\"margin-top: 8px;\"><em>{reason}</em></div>")

        self.self_export_info_hover.value = (
            "<div style=\"max-width: 320px; line-height: 1.6; white-space: normal; overflow-wrap: anywhere; word-break: break-word;\">"
            + "\n".join(body_lines)
            + "</div>"
        )

    def _refresh_self_export_button_states(self) -> None:
        if not hasattr(self, "self_export_button"):
            return
        can_export = bool(self._self_export_snapshot().get("ready", False))
        disabled = bool(getattr(self, "operation_in_progress", False))
        self.self_export_button.disabled = disabled or not can_export
        if hasattr(self, "self_export_confirm_button"):
            self.self_export_confirm_button.disabled = disabled
        if hasattr(self, "self_export_cancel_button"):
            self.self_export_cancel_button.disabled = disabled
        self._refresh_self_export_hovercard()

    def _write_self_fit_qdat(self, path: Path, fit_payload: dict[str, object], *, timestamp: str | None = None) -> None:
        series = fit_payload.get("series") if isinstance(fit_payload, dict) else None
        if not isinstance(series, dict):
            raise RuntimeError("Self fit series is missing.")

        q = np.asarray(series.get("q"), dtype=float)
        y = np.asarray(series.get("y"), dtype=float)
        y_fit = np.asarray(series.get("y_fit"), dtype=float)
        finite = np.isfinite(q) & np.isfinite(y) & np.isfinite(y_fit)
        if not np.any(finite):
            raise RuntimeError("Self fit series has no readable rows.")

        q = q[finite]
        y = y[finite]
        y_fit = y_fit[finite]

        lines = [
            f"# timestamp: {timestamp or now_iso()}",
            f"# model: {self._normalize_self_fit_model(fit_payload.get('model'))}",
            "# Q data fit",
        ]
        for qv, yv, yfv in zip(q, y, y_fit, strict=False):
            lines.append(f"{float(qv):.8g} {float(yv):.8g} {float(yfv):.8g}")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _on_self_export_folder_change(self, event) -> None:
        if getattr(self, "_suspend_self_scattering_events", False) or self.current_project_state is None:
            return
        if event.new == event.old:
            return
        if hasattr(self, "self_export_prompt"):
            self.self_export_prompt.visible = False
            self.self_export_prompt.object = ""
        self._sync_self_export_prompt_visibility()
        if hasattr(self, "_refresh_self_export_hovercard"):
            self._refresh_self_export_hovercard()
        if hasattr(self, "_refresh_self_export_button_states"):
            self._refresh_self_export_button_states()

    def _prompt_self_export(self, _event=None) -> None:
        if self.operation_in_progress:
            self._show_workspace_blocked_message()
            return
        if self.current_project_root is None or self.current_project_state is None:
            self._show_warning_toast("Open a project first.")
            return
        prompt = getattr(self, "self_export_prompt", None)
        if prompt is not None and bool(getattr(prompt, "visible", False)):
            self._cancel_self_export()
            return

        snap = self._self_export_snapshot()
        if not snap.get("ready", False):
            self._show_warning_toast(str(snap.get("reason") or "Export is not ready yet."))
            return

        user_target_dir = Path(str(snap["user_target_dir"]))
        canonical_target_dir = Path(str(snap["canonical_target_dir"]))
        qspdata_target_dir = Path(str(snap["qspdata_target_dir"]))
        filename_q = str(snap.get("filename_q") or "SOQ.qdat")
        filename_a = str(snap.get("filename_a") or "SOQ.adat")
        filename_fit = str(snap.get("filename_fit") or "self_fit.qdat")

        overwrite_targets: list[str] = []
        for path in (
            user_target_dir / filename_q,
            user_target_dir / filename_a,
            user_target_dir / filename_fit,
            canonical_target_dir / filename_q,
            canonical_target_dir / filename_a,
            canonical_target_dir / filename_fit,
            qspdata_target_dir / filename_q,
            qspdata_target_dir / filename_a,
        ):
            if path.exists():
                overwrite_targets.append(str(path))

        self._pending_self_export = {
            "user_target_dir": user_target_dir,
            "canonical_target_dir": canonical_target_dir,
            "qspdata_target_dir": qspdata_target_dir,
            "filename_q": filename_q,
            "filename_a": filename_a,
            "filename_fit": filename_fit,
            "overwrite_targets": overwrite_targets,
        }

        lines = [
            f"Export folder: `{snap['export_root']}`",
            "",
            f"User export: `{project_relpath(self.current_project_root, user_target_dir)}`",
            f"Canonical export: `{project_relpath(self.current_project_root, canonical_target_dir)}`",
            f"QSPData mirror: `{project_relpath(self.current_project_root, qspdata_target_dir)}`",
            "",
            f"Will write: `{filename_q}`",
            f"Will write: `{filename_a}`",
            f"Will write: `{filename_fit}`",
        ]
        if overwrite_targets:
            lines.extend(["", "**Overwrite warning:**", *[f"- `{p}`" for p in overwrite_targets]])

        prompt = getattr(self, "self_export_prompt", None)
        if prompt is not None:
            prompt.object = "\n".join(lines)
            prompt.alert_type = "warning" if overwrite_targets else "secondary"
            prompt.visible = True
        self._sync_self_export_prompt_visibility()
        self._refresh_interaction_states()

    def _cancel_self_export(self, _event=None) -> None:
        self._pending_self_export = None
        if hasattr(self, "self_export_prompt"):
            self.self_export_prompt.visible = False
            self.self_export_prompt.object = ""
        self._sync_self_export_prompt_visibility()
        self._refresh_interaction_states()

    def _confirm_self_export(self, _event=None) -> None:
        if self.operation_in_progress:
            self._show_workspace_blocked_message()
            return
        if getattr(self, "_pending_self_export", None) is None:
            return
        self._perform_self_export()

    def _perform_self_export(self) -> None:
        if self.current_project_root is None or self.current_project_state is None:
            return
        if getattr(self, "operation_in_progress", False):
            return

        snap = self._self_export_snapshot()
        if not snap.get("ready", False):
            self._show_warning_toast(str(snap.get("reason") or "Export is not ready yet."))
            return

        context_id = str(snap.get("context_id") or "").strip()
        if not context_id:
            self._show_warning_toast("Select a context first.")
            return

        series = self._compute_self_static_structure_factor_series()
        if series is None:
            self._show_warning_toast("Static Structure Factor not ready. Check prerequisites.")
            return
        q = series.get("q")
        soq = series.get("soq")
        soq_err = series.get("soq_err")
        if q is None or soq is None or soq_err is None:
            self._show_warning_toast("No S(Q) series available to export.")
            return

        manifest_ref = self._selected_self_manifest_ref()
        payload = load_context_manifest(self.current_project_root, manifest_ref) if manifest_ref else None
        payload = payload if isinstance(payload, dict) else None
        measurement = self._load_measurement_for_self_context(payload) if isinstance(payload, dict) else None
        if measurement is None or not hasattr(measurement, "wavelength"):
            self._show_warning_toast("Measurement/wavelength missing; cannot export angle data.")
            return
        try:
            wl = float(getattr(measurement, "wavelength"))
        except Exception:
            wl = float("nan")
        if not np.isfinite(wl) or wl <= 0:
            self._show_warning_toast("Invalid wavelength; cannot export angle data.")
            return

        sample_title = None
        try:
            if hasattr(measurement, "Title"):
                sample_title = str(getattr(measurement, "Title") or "").strip()
        except Exception:
            sample_title = None
        if not sample_title and isinstance(payload, dict):
            sample = payload.get("sample") if isinstance(payload.get("sample"), dict) else {}
            if isinstance(sample.get("title"), str):
                sample_title = sample.get("title")
        stem = self._sanitize_export_filename_stem(str(sample_title or context_id))
        filename_q = f"{stem}_SOQ.qdat"
        filename_a = f"{stem}_SOQ.adat"

        pending = getattr(self, "_pending_self_export", None)
        user_target_dir = Path(str(snap["user_target_dir"]))
        canonical_target_dir = Path(str(snap["canonical_target_dir"]))
        qspdata_target_dir = Path(str(snap["qspdata_target_dir"]))
        filename_fit = str(snap.get("filename_fit") or "self_fit.qdat")
        if isinstance(pending, dict):
            user_target_dir = Path(str(pending.get("user_target_dir") or user_target_dir))
            canonical_target_dir = Path(str(pending.get("canonical_target_dir") or canonical_target_dir))
            qspdata_target_dir = Path(str(pending.get("qspdata_target_dir") or qspdata_target_dir))
            filename_q = str(pending.get("filename_q") or filename_q)
            filename_a = str(pending.get("filename_a") or filename_a)
            filename_fit = str(pending.get("filename_fit") or "self_fit.qdat")

        run_record = None
        try:
            from toscana_gui.persistence import OutputPaths, RunRecord

            run_id = None
            if hasattr(self, "_create_run_id"):
                run_id = str(self._create_run_id())
            run_record = RunRecord(
                run_id=run_id or f"self-soq-{now_iso()}",
                workflow="self_static_structure_factor_export",
                status="running",
                started_at=now_iso(),
                summary=f"Exporting Static Structure Factor for context `{context_id}`",
                output_paths=OutputPaths(),
            )
            if hasattr(self.current_project_state, "runs") and isinstance(self.current_project_state.runs, list):
                self.current_project_state.runs.append(run_record)
                if hasattr(self, "_persist_current_project_state"):
                    self._persist_current_project_state()
        except Exception:
            run_record = None

        self.operation_in_progress = True
        try:
            if hasattr(self, "_refresh_interaction_states"):
                self._refresh_interaction_states()

            user_target_dir.mkdir(parents=True, exist_ok=True)
            canonical_target_dir.mkdir(parents=True, exist_ok=True)
            qspdata_target_dir.mkdir(parents=True, exist_ok=True)

            user_target_q = user_target_dir / filename_q
            user_target_a = user_target_dir / filename_a
            user_target_fit = user_target_dir / filename_fit
            canonical_target_q = canonical_target_dir / filename_q
            canonical_target_a = canonical_target_dir / filename_a
            canonical_target_fit = canonical_target_dir / filename_fit
            qspdata_target_q = qspdata_target_dir / filename_q
            qspdata_target_a = qspdata_target_dir / filename_a

            from toscana.io.saving import saveFile_xye
            from toscana.physics.conversions import q2ang

            timestamp = now_iso()
            fit_payload_live = self._self_fit_current_last_fit_payload()
            if not isinstance(fit_payload_live, dict):
                self._show_warning_toast("Fit payload missing; cannot export self fit.")
                return
            fit_payload = self._self_static_structure_factor_current_fit_payload()
            fit_model = self._normalize_self_fit_model(fit_payload.get("model")) if isinstance(fit_payload, dict) else ""

            artifacts = payload.get("artifacts") if isinstance(payload, dict) else {}
            dsdo_ref = artifacts.get("sample_dsdo_qdat") if isinstance(artifacts, dict) else None
            dsdo_rel = ""
            if isinstance(dsdo_ref, str) and dsdo_ref.strip():
                try:
                    dsdo_path = resolve_project_path(self.current_project_root, dsdo_ref)
                    dsdo_rel = project_relpath(self.current_project_root, dsdo_path)
                except Exception:
                    dsdo_rel = dsdo_ref

            popt = fit_payload.get("popt_full") if isinstance(fit_payload, dict) and isinstance(fit_payload.get("popt_full"), dict) else {}
            try:
                _base, keys = self._self_fit_model_function(fit_model)
            except Exception:
                keys = []
            params_compact = ", ".join([f"{k}={popt.get(k)}" for k in keys if k in popt])

            heading_common = [
                f"timestamp: {timestamp}",
                f"context_id: {context_id}",
                f"sample_title: {sample_title or ''}",
                f"fit_model: {fit_model}",
                f"fit_params: {params_compact}",
                f"source_sample_dsdo_qdat: {dsdo_rel}",
                "Static structure factor",
            ]
            heading_q = [*heading_common, " Q (1/Ã…)         Intensity              Error"]
            heading_a = [*heading_common, " A (deg)         Intensity              Error"]

            q_arr = np.asarray(q, dtype=float)
            y_arr = np.asarray(soq, dtype=float)
            e_arr = np.asarray(soq_err, dtype=float)
            ang_arr = np.asarray(q2ang(q_arr, wl), dtype=float)
            self._write_self_fit_qdat(user_target_fit, fit_payload_live, timestamp=timestamp)
            self._write_self_fit_qdat(canonical_target_fit, fit_payload_live, timestamp=timestamp)

            for path in (user_target_q, canonical_target_q, qspdata_target_q):
                saveFile_xye(str(path), q_arr, y_arr, e_arr, heading_q)
            for path in (user_target_a, canonical_target_a, qspdata_target_a):
                saveFile_xye(str(path), ang_arr, y_arr, e_arr, heading_a)

            if isinstance(payload, dict):
                artifacts = payload.get("artifacts") if isinstance(payload.get("artifacts"), dict) else {}
                artifacts["static_structure_factor_qdat"] = project_relpath(self.current_project_root, canonical_target_q)
                artifacts["static_structure_factor_adat"] = project_relpath(self.current_project_root, canonical_target_a)
                artifacts["static_structure_factor_qdat_qspdata"] = project_relpath(self.current_project_root, qspdata_target_q)
                artifacts["static_structure_factor_adat_qspdata"] = project_relpath(self.current_project_root, qspdata_target_a)
                artifacts["self_fit_qdat"] = project_relpath(self.current_project_root, canonical_target_fit)
                payload["artifacts"] = artifacts
                try:
                    write_context_manifest(self.current_project_root, context_id=context_id, payload=payload)
                except Exception:
                    pass

            if run_record is not None:
                try:
                    run_record.status = "succeeded"
                    run_record.finished_at = now_iso()
                    run_record.summary = f"Exported `{filename_q}` / `{filename_a}` / `{filename_fit}`"
                    run_record.output_paths.generated_files = [
                        project_relpath(self.current_project_root, canonical_target_q),
                        project_relpath(self.current_project_root, canonical_target_a),
                        project_relpath(self.current_project_root, qspdata_target_q),
                        project_relpath(self.current_project_root, qspdata_target_a),
                        project_relpath(self.current_project_root, user_target_fit),
                        project_relpath(self.current_project_root, canonical_target_fit),
                    ]
                    if hasattr(self.current_project_state, "project") and hasattr(self.current_project_state.project, "updated_at"):
                        self.current_project_state.project.updated_at = now_iso()  # type: ignore[assignment]
                    if hasattr(self, "_persist_current_project_state"):
                        self._persist_current_project_state()
                except Exception:
                    pass

            if hasattr(self, "_show_success_toast"):
                self._show_success_toast("Exported Static Structure Factor files and self fit.")
            if hasattr(self, "self_export_prompt"):
                self.self_export_prompt.visible = False
                self.self_export_prompt.object = ""
                self._sync_self_export_prompt_visibility()
        except Exception as exc:
            if hasattr(self, "_show_error_toast"):
                self._show_error_toast(f"Export failed: {exc}")
            if run_record is not None:
                try:
                    run_record.status = "failed"
                    run_record.finished_at = now_iso()
                    run_record.summary = f"Export failed: {exc}"
                    if hasattr(self, "_persist_current_project_state"):
                        self._persist_current_project_state()
                except Exception:
                    pass
        finally:
            self._pending_self_export = None
            self.operation_in_progress = False
            if hasattr(self, "_refresh_interaction_states"):
                try:
                    self._refresh_interaction_states()
                except Exception:
                    pass
            if hasattr(self, "_refresh_self_export_hovercard"):
                try:
                    self._refresh_self_export_hovercard()
                except Exception:
                    pass
            if hasattr(self, "_refresh_self_export_button_states"):
                try:
                    self._refresh_self_export_button_states()
                except Exception:
                    pass

    def _invalidate_self_fit_result(self, *, reason: str | None = None) -> None:
        self._self_fit_last = None
        if hasattr(self, "self_fit_plot_pane"):
            try:
                self.self_fit_plot_pane.object = None
            except Exception:
                pass
        if hasattr(self, "self_fit_result_table"):
            try:
                self.self_fit_result_table.object = ""
            except Exception:
                pass
        if reason and hasattr(self, "self_fit_params_status"):
            self.self_fit_params_status.object = f"**Status:** {reason}"
        if hasattr(self, "_invalidate_self_static_structure_factor_result"):
            try:
                self._invalidate_self_static_structure_factor_result(reason=reason)
            except Exception:
                pass
        if hasattr(self, "_refresh_self_export_hovercard"):
            try:
                self._refresh_self_export_hovercard()
            except Exception:
                pass
        if hasattr(self, "_refresh_self_export_button_states"):
            try:
                self._refresh_self_export_button_states()
            except Exception:
                pass

    def _invalidate_self_static_structure_factor_result(self, *, reason: str | None = None) -> None:
        self._self_static_structure_factor_last = None
        if hasattr(self, "self_static_structure_factor_plot_pane"):
            try:
                self.self_static_structure_factor_plot_pane.object = None
            except Exception:
                pass
        if hasattr(self, "self_static_structure_factor_summary_table"):
            try:
                self.self_static_structure_factor_summary_table.object = ""
            except Exception:
                pass
        if hasattr(self, "_refresh_self_export_hovercard"):
            try:
                self._refresh_self_export_hovercard()
            except Exception:
                pass
        if hasattr(self, "_refresh_self_export_button_states"):
            try:
                self._refresh_self_export_button_states()
            except Exception:
                pass

    def _load_measurement_for_self_context(self, payload: dict[str, object]) -> object | None:
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

    def _self_fit_model_function(self, model: str):
        model = self._normalize_self_fit_model(model)
        if model == self._SELF_FIT_MODEL_POLY:
            from toscana.math.polynomials import polyQ4 as base_func

            return base_func, ["a0", "a1", "a2", "a3", "a4"]
        if model == self._SELF_FIT_MODEL_LORGAU:
            from toscana.math.line_shapes import LorGau as base_func

            return base_func, ["f0", "eta", "sigma", "gamma", "bckg"]
        from toscana.models.scattering import vanaQdep as base_func

        return base_func, ["a0", "a1", "a2", "A", "lowQ", "Q0", "dQ"]

    def _self_static_structure_factor_current_fit_payload(self) -> dict[str, object] | None:
        return self._self_fit_current_last_fit_payload()

    def _self_static_structure_factor_is_stale(self, fit_payload: dict[str, object]) -> bool:
        return self._self_fit_is_last_fit_stale(fit_payload)

    def _compute_self_static_structure_factor_series(self) -> dict[str, object] | None:
        if self.current_project_root is None or self.current_project_state is None:
            return None
        context_id = str(getattr(getattr(self, "self_context_select", None), "value", "") or "").strip()
        if not context_id:
            return None

        fit_payload = self._self_static_structure_factor_current_fit_payload()
        if not isinstance(fit_payload, dict):
            return None
        if self._self_static_structure_factor_is_stale(fit_payload):
            return None

        data = self._load_self_dsdo_corrected_required()
        if data is None:
            return None
        q_all, dsdo_corr, e_all = data

        model = self._normalize_self_fit_model(fit_payload.get("model"))
        popt_full = fit_payload.get("popt_full")
        if not isinstance(popt_full, dict):
            return None

        try:
            base_func, keys = self._self_fit_model_function(model)
        except Exception:
            return None
        try:
            theta = [float(popt_full.get(k)) for k in keys]
        except Exception:
            return None
        self_fit = np.asarray(base_func(np.asarray(q_all, dtype=float), *theta), dtype=float)

        q = np.asarray(q_all, dtype=float)
        dsdo_corr = np.asarray(dsdo_corr, dtype=float)
        e = np.asarray(e_all, dtype=float)

        with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
            soq = dsdo_corr / self_fit
            # Legacy-implied: self_err == dsdo_err
            rel_dsdo = np.where(dsdo_corr != 0, e / dsdo_corr, np.nan)
            rel_self = np.where(self_fit != 0, e / self_fit, np.nan)
            soq_err = np.abs(soq) * np.sqrt(rel_dsdo**2 + rel_self**2)
            bad = ~np.isfinite(soq) | ~np.isfinite(soq_err)
            soq = np.where(bad, np.nan, soq)
            soq_err = np.where(bad, np.nan, soq_err)

        return {
            "context_id": context_id,
            "q": q,
            "soq": soq,
            "soq_err": soq_err,
            "fit_model": model,
            "fit_payload": fit_payload,
        }

    def _render_self_static_structure_factor_summary_table(
        self,
        *,
        payload: dict[str, object] | None,
        fit_payload: dict[str, object] | None,
        measurement: object | None,
        stale: bool,
        reason: str | None = None,
    ) -> None:
        pane = getattr(self, "self_static_structure_factor_summary_table", None)
        if pane is None:
            return

        def _fmt(v: object) -> str:
            try:
                x = float(v)
            except Exception:
                return ""
            if not np.isfinite(x):
                return ""
            if x == 0.0:
                return "0"
            if abs(x) < 1e-3:
                return f"{x:.3e}"
            return f"{x:.3f}".rstrip("0").rstrip(".")

        status_label = "Not ready"
        status_detail = html_escape(str(reason or "").strip())
        if stale:
            status_label = "Stale"
        else:
            # Ready requires corrected dsdo + fit + measurement wavelength.
            if fit_payload is not None and measurement is not None and hasattr(measurement, "wavelength"):
                try:
                    wl = float(getattr(measurement, "wavelength"))
                except Exception:
                    wl = float("nan")
                if np.isfinite(wl) and wl > 0:
                    status_label = "Ready to Export"
                    status_detail = ""
                else:
                    status_detail = "Missing wavelength."
            elif fit_payload is None:
                status_detail = "No fit available."
            elif measurement is None:
                status_detail = "Missing measurement / wavelength."

        # Window summary (from selection snapshot if available).
        q_window = ""
        y_window = ""
        if isinstance(fit_payload, dict):
            snap = fit_payload.get("selection_snapshot")
            if isinstance(snap, dict):
                mode = str(snap.get("mode") or "")
                if mode == self._SELF_LOWQ_MODE_MANUAL:
                    q_window = f"{_fmt(snap.get('q_min'))} – {_fmt(snap.get('q_max'))}"
                    y_window = f"{_fmt(snap.get('y_min'))} – {_fmt(snap.get('y_max'))}"
                else:
                    q_window = f"{_fmt(snap.get('q_start'))} – {_fmt(snap.get('q_end'))}"
                    y_window = f"pct {int(snap.get('min_percentile') or 0)} – {int(snap.get('max_percentile') or 0)}"

        model_display = self._self_fit_model_display_name(fit_payload.get("model") if isinstance(fit_payload, dict) else "")

        params_html = ""
        if isinstance(fit_payload, dict):
            popt = fit_payload.get("popt_full") if isinstance(fit_payload.get("popt_full"), dict) else {}
            perr = fit_payload.get("perr_full") if isinstance(fit_payload.get("perr_full"), dict) else {}
            try:
                _base_func, keys = self._self_fit_model_function(str(fit_payload.get("model") or ""))
            except Exception:
                keys = []
            lines = []
            for k in keys:
                val = _fmt(popt.get(k))
                err = _fmt(perr.get(k))
                if val:
                    if err:
                        lines.append(f"<div><code>{html_escape(k)}</code>: <strong>{html_escape(val)}</strong> ± {html_escape(err)}</div>")
                    else:
                        lines.append(f"<div><code>{html_escape(k)}</code>: <strong>{html_escape(val)}</strong></div>")
            if lines:
                params_html = "<div class=\"toscana-fit-result-table__meta\" style=\"margin-top:8px;\">Parameters</div>" + "".join(lines)

        pane.object = (
            "<div class=\"toscana-fit-window-table\">"
            "<div class=\"toscana-fit-result-table__title\">Summary</div>"
            f"<div class=\"toscana-fit-result-table__meta\">Status: <strong>{html_escape(status_label)}</strong></div>"
            + (f"<div class=\"toscana-fit-result-table__meta\">{status_detail}</div>" if status_detail else "")
            + (f"<div class=\"toscana-fit-result-table__meta\">Q window: <strong>{html_escape(q_window)}</strong></div>" if q_window else "")
            + (f"<div class=\"toscana-fit-result-table__meta\">Y window: <strong>{html_escape(y_window)}</strong></div>" if y_window else "")
            + (f"<div class=\"toscana-fit-result-table__meta\">Model: <strong>{html_escape(model_display)}</strong></div>" if model_display else "")
            + params_html
            + "</div>"
        )

    def _refresh_self_static_structure_factor_panel(self) -> None:
        if self.current_project_root is None or self.current_project_state is None:
            return
        pane = getattr(self, "self_static_structure_factor_plot_pane", None)
        table = getattr(self, "self_static_structure_factor_summary_table", None)
        if pane is None or table is None:
            return

        context_id = str(getattr(getattr(self, "self_context_select", None), "value", "") or "").strip()
        if not context_id:
            self._render_self_static_structure_factor_summary_table(
                payload=None,
                fit_payload=None,
                measurement=None,
                stale=False,
                reason="Select a context first.",
            )
            pane.object = None
            return

        manifest_ref = self._selected_self_manifest_ref()
        payload = load_context_manifest(self.current_project_root, manifest_ref) if manifest_ref else None
        payload = payload if isinstance(payload, dict) else None

        fit_payload = self._self_static_structure_factor_current_fit_payload()
        if not isinstance(fit_payload, dict):
            self._render_self_static_structure_factor_summary_table(
                payload=payload,
                fit_payload=None,
                measurement=None,
                stale=False,
                reason="Run Fit first.",
            )
            pane.object = None
            return

        stale = self._self_static_structure_factor_is_stale(fit_payload)
        measurement = self._load_measurement_for_self_context(payload) if isinstance(payload, dict) else None

        # Compute and plot only when not stale.
        series = None
        reason = None
        if stale:
            reason = "Fit is stale."
        else:
            series = self._compute_self_static_structure_factor_series()
            if series is None:
                reason = "Missing prerequisites (corrected dsdo and non-stale fit)."

        self._render_self_static_structure_factor_summary_table(
            payload=payload,
            fit_payload=fit_payload,
            measurement=measurement,
            stale=stale,
            reason=reason,
        )

        if series is None or stale:
            pane.object = None
            return

        q = series.get("q")
        soq = series.get("soq")
        if q is None or soq is None:
            pane.object = None
            return

        uirev = f"self-soq:{context_id}"
        fig = pane.object if getattr(pane, "object", None) is not None else None
        title = "Static Structure Factor"
        if fig is None:
            fig = build_static_structure_factor_figure(
                q=np.asarray(q, dtype=float),
                soq=np.asarray(soq, dtype=float),
                title=title,
                width=800,
                height=600,
                uirevision=uirev,
            )
        else:
            update_static_structure_factor_figure(
                fig,
                q=np.asarray(q, dtype=float),
                soq=np.asarray(soq, dtype=float),
                title=title,
                width=800,
                height=600,
                uirevision=uirev,
            )
        pane.object = fig
        try:
            pane.param.trigger("object")
        except Exception:
            pass

    def _refresh_self_static_structure_factor_button_states(self) -> None:
        # Keep the plot/table in sync with the live fit cache.
        self._refresh_self_static_structure_factor_panel()

    def _self_fit_selection_snapshot(self) -> dict[str, object]:
        # Best-effort: mirror what is persisted under decisions.self_scattering.data_selection.
        mode = self._normalize_self_lowq_mode(getattr(getattr(self, "self_data_selection_selection_mode", None), "value", ""))
        # IMPORTANT: do not include UI-only fields (e.g. slider-vs-input mode) here.
        # This snapshot is used for fit staleness detection and must only capture
        # changes that affect the selected subset.
        snap: dict[str, object] = {"mode": mode}
        if mode == self._SELF_LOWQ_MODE_MANUAL:
            snap.update(
                {
                    "q_min": float(getattr(getattr(self, "self_data_selection_q_min", None), "value", 0.0) or 0.0),
                    "q_max": float(getattr(getattr(self, "self_data_selection_q_max", None), "value", 0.0) or 0.0),
                    "y_min": float(getattr(getattr(self, "self_data_selection_y_min", None), "value", 0.0) or 0.0),
                    "y_max": float(getattr(getattr(self, "self_data_selection_y_max", None), "value", 0.0) or 0.0),
                }
            )
        else:
            snap.update(
                {
                    "q_start": float(getattr(getattr(self, "self_data_selection_q_tail_low", None), "value", 0.0) or 0.0),
                    "q_end": float(getattr(getattr(self, "self_data_selection_q_tail_high", None), "value", 0.0) or 0.0),
                    "min_percentile": int(getattr(getattr(self, "self_data_selection_min_percentile", None), "value", 0) or 0),
                    "max_percentile": int(getattr(getattr(self, "self_data_selection_max_percentile", None), "value", 0) or 0),
                }
            )
        return snap

    def _self_fit_lowq_snapshot(self) -> dict[str, object]:
        fit = getattr(self, "_self_lowq_last", None)
        if not isinstance(fit, dict):
            return {}
        out: dict[str, object] = {}
        if isinstance(fit.get("fit"), dict):
            out["fit"] = dict(fit.get("fit") or {})
        if isinstance(fit.get("window_used"), dict):
            out["window_used"] = dict(fit.get("window_used") or {})
        return out

    def _load_self_dsdo_corrected_required(self) -> tuple[np.ndarray, np.ndarray, np.ndarray] | None:
        series = self._load_self_dsdo_series()
        if series is None:
            self._self_fit_set_alert("Select a context with `sample_dsdo_qdat` first.", alert_type="warning")
            return None
        q_all, y_all, e_all, _path = series

        context_id = str(getattr(getattr(self, "self_context_select", None), "value", "") or "").strip()
        fit = getattr(self, "_self_lowq_last", None)
        corrected = None
        if isinstance(fit, dict):
            if str(fit.get("project_root") or "") == str(getattr(self, "current_project_root", "") or "") and str(fit.get("context_id") or "") == context_id:
                corrected = fit.get("corrected")
            if not isinstance(corrected, np.ndarray) and isinstance(fit.get("fit"), dict):
                try:
                    from toscana.models.scattering import self024

                    fr = fit["fit"]
                    q0 = float(fr.get("q0"))
                    q2 = float(fr.get("q2"))
                    q4 = float(fr.get("q4"))
                    y_lowq = np.asarray(self024(q_all, q0, q2, q4), dtype=float)
                    window_used = fit.get("window_used") if isinstance(fit.get("window_used"), dict) else {}
                    if isinstance(window_used.get("q_min"), (int, float)) and isinstance(window_used.get("q_max"), (int, float)):
                        q_min = float(window_used["q_min"])
                        q_max = float(window_used["q_max"])
                    else:
                        q_min = 0.45
                        q_max = 2.0
                    corrected = beam_stop_correct(q=q_all, y_raw=y_all, y_lowq=y_lowq, q_min=q_min, q_max=q_max)
                except Exception:
                    corrected = None

        if not isinstance(corrected, np.ndarray) or corrected.shape != y_all.shape:
            self._self_fit_set_alert(
                "Corrected dsdo not found. Run **Sample Extrapolation to Low Q** first.",
                alert_type="warning",
            )
            return None

        self._self_fit_clear_alert()
        return np.asarray(q_all, dtype=float), np.asarray(corrected, dtype=float), np.asarray(e_all, dtype=float)

    def _self_fit_read_params_from_widgets(self, model: str) -> dict[str, dict[str, object]]:
        model = self._normalize_self_fit_model(model)
        prefix = self._self_fit_widget_prefix(model)
        params: dict[str, dict[str, object]] = {}
        for key in self._self_fit_param_keys(model):
            fixed_w = getattr(self, f"{prefix}_{key}_fixed", None)
            value_w = getattr(self, f"{prefix}_{key}_value", None)
            min_w = getattr(self, f"{prefix}_{key}_min", None)
            max_w = getattr(self, f"{prefix}_{key}_max", None)
            try:
                params[key] = {
                    "fixed": bool(getattr(fixed_w, "value", False)) if fixed_w is not None else False,
                    "value": float(getattr(value_w, "value", 0.0)) if value_w is not None else 0.0,
                    "min": float(getattr(min_w, "value", -1e6)) if min_w is not None else -1e6,
                    "max": float(getattr(max_w, "value", 1e6)) if max_w is not None else 1e6,
                }
            except Exception:
                params[key] = {"fixed": False, "value": 0.0, "min": -1e6, "max": 1e6}
        return params

    def _self_fit_write_params_to_widgets(self, model: str, params: dict[str, dict[str, object]]) -> None:
        model = self._normalize_self_fit_model(model)
        prefix = self._self_fit_widget_prefix(model)
        self._suspend_self_scattering_events = True
        try:
            for key in self._self_fit_param_keys(model):
                block = params.get(key) if isinstance(params, dict) else None
                if not isinstance(block, dict):
                    continue
                for field in ("value", "min", "max"):
                    widget = getattr(self, f"{prefix}_{key}_{field}", None)
                    if widget is None:
                        continue
                    if isinstance(block.get(field), (int, float)):
                        widget.value = float(block[field])
                fixed_w = getattr(self, f"{prefix}_{key}_fixed", None)
                if fixed_w is not None and isinstance(block.get("fixed"), (bool, int, float)):
                    fixed_w.value = bool(block.get("fixed"))
        finally:
            self._suspend_self_scattering_events = False

    def _apply_self_fit_fixed_states(self, model: str) -> None:
        model = self._normalize_self_fit_model(model)
        prefix = self._self_fit_widget_prefix(model)
        self._suspend_self_scattering_events = True
        try:
            for key in self._self_fit_param_keys(model):
                fixed_w = getattr(self, f"{prefix}_{key}_fixed", None)
                value_w = getattr(self, f"{prefix}_{key}_value", None)
                min_w = getattr(self, f"{prefix}_{key}_min", None)
                max_w = getattr(self, f"{prefix}_{key}_max", None)
                if fixed_w is None or value_w is None or min_w is None or max_w is None:
                    continue
                fixed = bool(getattr(fixed_w, "value", False))
                v = float(getattr(value_w, "value", 0.0) or 0.0)
                if fixed:
                    try:
                        min_w.value = v
                        max_w.value = v
                    except Exception:
                        pass
                try:
                    min_w.disabled = fixed
                    max_w.disabled = fixed
                except Exception:
                    pass
        finally:
            self._suspend_self_scattering_events = False

    def _persist_self_fit_model_to_context(self) -> None:
        if self.current_project_root is None or self.current_project_state is None:
            return
        if getattr(self, "_suspend_self_scattering_events", False):
            return
        context_id = str(getattr(getattr(self, "self_context_select", None), "value", "") or "").strip()
        if not context_id:
            return
        manifest_ref = self._selected_self_manifest_ref()
        if not manifest_ref:
            return
        payload = load_context_manifest(self.current_project_root, manifest_ref)
        if not isinstance(payload, dict):
            return

        model = self._self_fit_active_model()
        fit_payload: dict[str, object] = {
            "model": model,
            "params": self._self_fit_read_params_from_widgets(model),
            "advanced_bounds_visible": bool(getattr(getattr(self, "self_fit_params_bounds_toggle", None), "value", False)),
        }

        decisions = payload.get("decisions") if isinstance(payload.get("decisions"), dict) else {}
        self_block = decisions.get("self_scattering") if isinstance(decisions.get("self_scattering"), dict) else {}
        self_block["fit_model"] = {**(self_block.get("fit_model") if isinstance(self_block.get("fit_model"), dict) else {}), **fit_payload}
        decisions["self_scattering"] = self_block
        payload["decisions"] = decisions
        try:
            write_context_manifest(self.current_project_root, context_id=context_id, payload=payload)
        except Exception:
            return

    def _load_self_fit_model_from_context(self) -> None:
        if self.current_project_root is None or self.current_project_state is None:
            return
        context_id = str(getattr(getattr(self, "self_context_select", None), "value", "") or "").strip()
        if not context_id:
            return
        manifest_ref = self._selected_self_manifest_ref()
        if not manifest_ref:
            return
        payload = load_context_manifest(self.current_project_root, manifest_ref)
        if not isinstance(payload, dict):
            return

        decisions = payload.get("decisions") if isinstance(payload.get("decisions"), dict) else {}
        self_block = decisions.get("self_scattering") if isinstance(decisions.get("self_scattering"), dict) else {}
        fm = self_block.get("fit_model") if isinstance(self_block.get("fit_model"), dict) else {}

        model = self._normalize_self_fit_model(fm.get("model"))
        self._suspend_self_scattering_events = True
        try:
            if hasattr(self, "self_fit_model_selector"):
                self.self_fit_model_selector.value = model
            if hasattr(self, "self_fit_params_bounds_toggle") and isinstance(fm.get("advanced_bounds_visible"), (bool, int, float)):
                self.self_fit_params_bounds_toggle.value = bool(fm.get("advanced_bounds_visible"))
        finally:
            self._suspend_self_scattering_events = False

        params = fm.get("params")
        if isinstance(params, dict):
            self._self_fit_write_params_to_widgets(model, params)
        self._self_fit_set_model_visibility(model)
        self._apply_self_fit_fixed_states(model)

        last_fit = fm.get("last_fit")
        if isinstance(last_fit, dict):
            self._self_fit_last = {
                "project_root": str(getattr(self, "current_project_root", "") or ""),
                "context_id": context_id,
                "payload": last_fit,
            }
        else:
            self._self_fit_last = None

    def _self_fit_is_last_fit_stale(self, last_fit: dict[str, object]) -> bool:
        try:
            snap = last_fit.get("selection_snapshot")
            if isinstance(snap, dict):
                if snap != self._self_fit_selection_snapshot():
                    return True
            model = self._normalize_self_fit_model(last_fit.get("model"))
            if model != self._self_fit_active_model():
                return True
            lowq_snap = last_fit.get("lowq_snapshot")
            if isinstance(lowq_snap, dict) and lowq_snap != self._self_fit_lowq_snapshot():
                return True
        except Exception:
            return True
        return False

    def _refresh_self_fit_panel(self) -> None:
        if self.current_project_root is None or self.current_project_state is None:
            return
        model = self._self_fit_active_model()
        self._self_fit_set_model_visibility(model)

        if hasattr(self, "_refresh_self_fit_button_states"):
            self._refresh_self_fit_button_states()

        bounds_card = getattr(self, "self_fit_params_bounds_card", None)
        toggle = getattr(self, "self_fit_params_bounds_toggle", None)
        if bounds_card is not None and toggle is not None:
            try:
                bounds_card.visible = bool(getattr(toggle, "value", False))
            except Exception:
                pass

        self._apply_self_fit_fixed_states(model)

        # If we have a persisted fit, render it; otherwise keep empty.
        pane = getattr(self, "self_fit_plot_pane", None)
        table = getattr(self, "self_fit_result_table", None)
        if pane is None or table is None:
            return

        context_id = str(getattr(getattr(self, "self_context_select", None), "value", "") or "").strip()
        project_token = str(getattr(self, "current_project_root", "") or "")
        cached = getattr(self, "_self_fit_last", None)
        fit_payload = None
        if isinstance(cached, dict):
            if str(cached.get("project_root") or "") == project_token and str(cached.get("context_id") or "") == context_id:
                fit_payload = cached.get("payload")
        if not isinstance(fit_payload, dict):
            table.object = ""
            pane.object = None
            return

        stale = self._self_fit_is_last_fit_stale(fit_payload)
        self._render_self_fit_result_table(fit_payload, stale=stale)
        self._refresh_self_fit_plot(fit_payload)
        if hasattr(self, "self_fit_params_status"):
            if stale:
                self.self_fit_params_status.object = "**Status:** Fit is stale. Run Fit again."
            else:
                self.self_fit_params_status.object = "**Status:** Fit complete."

    def _self_fit_can_suggest(self) -> bool:
        if self.current_project_root is None or self.current_project_state is None:
            return False
        context_id = str(getattr(getattr(self, "self_context_select", None), "value", "") or "").strip()
        if not context_id:
            return False
        series = self._load_self_dsdo_series()
        if series is None:
            return False
        q_all, y_all, _e_all, _path = series

        fit = getattr(self, "_self_lowq_last", None)
        corrected = None
        if isinstance(fit, dict):
            if str(fit.get("project_root") or "") == str(getattr(self, "current_project_root", "") or "") and str(fit.get("context_id") or "") == context_id:
                corrected = fit.get("corrected")
            if not isinstance(corrected, np.ndarray) and isinstance(fit.get("fit"), dict):
                try:
                    from toscana.models.scattering import self024

                    fr = fit["fit"]
                    q0 = float(fr.get("q0"))
                    q2 = float(fr.get("q2"))
                    q4 = float(fr.get("q4"))
                    y_lowq = np.asarray(self024(q_all, q0, q2, q4), dtype=float)
                    window_used = fit.get("window_used") if isinstance(fit.get("window_used"), dict) else {}
                    if isinstance(window_used.get("q_min"), (int, float)) and isinstance(window_used.get("q_max"), (int, float)):
                        q_min = float(window_used["q_min"])
                        q_max = float(window_used["q_max"])
                    else:
                        q_min = 0.45
                        q_max = 2.0
                    corrected = beam_stop_correct(q=q_all, y_raw=y_all, y_lowq=y_lowq, q_min=q_min, q_max=q_max)
                except Exception:
                    corrected = None

        return isinstance(corrected, np.ndarray) and corrected.shape == y_all.shape

    def _refresh_self_fit_button_states(self) -> None:
        can_suggest = self._self_fit_can_suggest()
        op_in_progress = bool(getattr(self, "operation_in_progress", False))

        suggest_button = getattr(self, "self_fit_params_suggest_button", None)
        if suggest_button is not None:
            suggest_button.disabled = (not can_suggest) or op_in_progress

        run_button = getattr(self, "self_fit_params_run_button", None)
        if run_button is not None:
            run_button.disabled = (not can_suggest) or op_in_progress

    def _render_self_fit_result_table(self, fit_payload: dict[str, object], *, stale: bool) -> None:
        pane = getattr(self, "self_fit_result_table", None)
        if pane is None:
            return
        model = self._normalize_self_fit_model(fit_payload.get("model"))
        params = fit_payload.get("popt_full")
        perr = fit_payload.get("perr_full")
        if not isinstance(params, dict) or not isinstance(perr, dict):
            pane.object = ""
            return

        def _fmt_compact(v: object) -> str:
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
            s = f"{x:.3f}".rstrip("0").rstrip(".")
            return s

        def _fmt_value(v: object) -> str:
            return _fmt_compact(v)

        def _fmt_err(v: object) -> str:
            return _fmt_compact(v)

        keys = self._self_fit_param_keys(model)
        rows_html = []
        for key in keys:
            rows_html.append(
                "<tr>"
                f"<td class=\"toscana-fit-result-table__param\">{html_escape(key)}</td>"
                f"<td class=\"toscana-fit-result-table__value\">{html_escape(_fmt_value(params.get(key)))}</td>"
                f"<td class=\"toscana-fit-result-table__err\">{html_escape(_fmt_err(perr.get(key)))}</td>"
                "</tr>"
            )

        n_points = fit_payload.get("n_points")
        try:
            n_points_int = int(n_points) if n_points is not None else None
        except Exception:
            n_points_int = None

        meta_html = ""
        if n_points_int is not None and n_points_int >= 0:
            meta_html = f"<div class=\"toscana-fit-result-table__meta\">Selected points: <strong>{n_points_int}</strong></div>"

        title = "Fit result"
        if stale:
            title = "Fit result (stale)"

        pane.object = (
            "<div class=\"toscana-fit-window-table\">"
            f"<div class=\"toscana-fit-result-table__title\">{title}</div>"
            f"{meta_html}"
            "<table class=\"toscana-fit-result-table\">"
            "<thead><tr><th>Param</th><th>Value</th><th>±</th></tr></thead>"
            "<tbody>"
            + "".join(rows_html)
            + "</tbody>"
            "</table>"
            "</div>"
        )

    def _refresh_self_fit_plot(self, fit_payload: dict[str, object]) -> None:
        pane = getattr(self, "self_fit_plot_pane", None)
        if pane is None:
            return

        series = self._self_fit_build_render_series(fit_payload)
        if series is None:
            pane.object = None
            return
        q, y, y_fit, q_subset, y_subset = series

        context_id = str(getattr(getattr(self, "self_context_select", None), "value", "") or "").strip()
        uirev = f"self-fit-model:{context_id}"
        fig = pane.object if getattr(pane, "object", None) is not None else None
        title = self._self_fit_model_display_name(fit_payload.get("model"))
        if fig is None:
            fig = build_self_fit_model_figure(
                q=q,
                y=y,
                y_fit=y_fit,
                q_subset=q_subset,
                y_subset=y_subset,
                title=title,
                width=800,
                height=600,
                uirevision=uirev,
            )
        else:
            update_self_fit_model_figure(
                fig,
                q=q,
                y=y,
                y_fit=y_fit,
                q_subset=q_subset,
                y_subset=y_subset,
                title=title,
                width=800,
                height=600,
                uirevision=uirev,
            )
        pane.object = fig
        try:
            pane.param.trigger("object")
        except Exception:
            pass

    def _self_fit_model_display_name(self, raw: object) -> str:
        model = self._normalize_self_fit_model(raw)
        if model == self._SELF_FIT_MODEL_POLY:
            return "Polynomial"
        if model == self._SELF_FIT_MODEL_LORGAU:
            return "Lorentzian + Gaussian"
        return "Sigmoidal + Polynomial"

    def _self_fit_select_points_from_snapshot(self, *, q: np.ndarray, y: np.ndarray, snapshot: dict[str, object]) -> LowQSelection:
        mode = self._normalize_self_lowq_mode(snapshot.get("mode"))
        warnings: list[str] = []
        if mode == self._SELF_LOWQ_MODE_MANUAL:
            q_min = float(snapshot.get("q_min") or 0.0)
            q_max = float(snapshot.get("q_max") or 0.0)
            y_min = float(snapshot.get("y_min") or 0.0)
            y_max = float(snapshot.get("y_max") or 0.0)
            if q_max < q_min:
                warnings.append("Manual window has `q_max < q_min`.")
            if y_max < y_min:
                warnings.append("Manual window has `y_max < y_min`.")
            mask = (q >= q_min) & (q <= q_max) & (y >= y_min) & (y <= y_max)
            return LowQSelection(
                mode=mode,
                q_min=q_min,
                q_max=q_max,
                y_min=y_min,
                y_max=y_max,
                q_subset=q[mask],
                y_subset=y[mask],
                warnings=warnings,
            )

        q_min = float(snapshot.get("q_start") or 0.0)
        q_max = float(snapshot.get("q_end") or 0.0)
        min_pct = int(snapshot.get("min_percentile") or 0)
        max_pct = int(snapshot.get("max_percentile") or 0)
        if q_max < q_min:
            warnings.append("Percentile band has `Q end < Q start`.")
        if max_pct < min_pct:
            warnings.append("Percentile band has `upper percentile < lower percentile`.")

        finite_y = y[np.isfinite(y)]
        if finite_y.size == 0:
            y_min = float("nan")
            y_max = float("nan")
        else:
            y_min = float(np.percentile(finite_y, min_pct))
            y_max = float(np.percentile(finite_y, max_pct))
        mask = (q >= q_min) & (q <= q_max) & (y >= y_min) & (y <= y_max)
        return LowQSelection(
            mode=mode,
            q_min=q_min,
            q_max=q_max,
            y_min=y_min,
            y_max=y_max,
            q_subset=q[mask],
            y_subset=y[mask],
            warnings=warnings,
        )

    def _self_fit_build_render_series(
        self, fit_payload: dict[str, object]
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray | None, np.ndarray | None] | None:
        model = self._normalize_self_fit_model(fit_payload.get("model"))
        popt_full = fit_payload.get("popt_full")
        if not isinstance(popt_full, dict):
            return None

        data = self._load_self_dsdo_corrected_required()
        if data is None:
            return None
        q_all, y_all, _e = data

        snapshot = fit_payload.get("selection_snapshot")
        snap = snapshot if isinstance(snapshot, dict) else self._self_fit_selection_snapshot()
        selection = self._self_fit_select_points_from_snapshot(q=q_all, y=y_all, snapshot=snap)

        try:
            if model == self._SELF_FIT_MODEL_POLY:
                from toscana.math.polynomials import polyQ4 as base_func
            elif model == self._SELF_FIT_MODEL_LORGAU:
                from toscana.math.line_shapes import LorGau as base_func
            else:
                from toscana.models.scattering import vanaQdep as base_func
        except Exception:
            return None

        keys = self._self_fit_param_keys(model)
        try:
            theta = [float(popt_full.get(k)) for k in keys]
        except Exception:
            return None
        y_fit = np.asarray(base_func(q_all, *theta), dtype=float)
        return (
            np.asarray(q_all, dtype=float),
            np.asarray(y_all, dtype=float),
            np.asarray(y_fit, dtype=float),
            np.asarray(selection.q_subset, dtype=float),
            np.asarray(selection.y_subset, dtype=float),
        )

    def _on_self_fit_model_change(self, event=None) -> None:
        if getattr(self, "_suspend_self_scattering_events", False) or self.current_project_state is None:
            return
        model = self._self_fit_active_model()
        self._self_fit_set_model_visibility(model)
        self._apply_self_fit_fixed_states(model)
        self._persist_self_fit_model_to_context()
        self._invalidate_self_fit_result(reason="Fit model changed.")

    def _on_self_fit_params_bounds_toggle_change(self, event=None) -> None:
        if getattr(self, "_suspend_self_scattering_events", False) or self.current_project_state is None:
            return
        bounds_card = getattr(self, "self_fit_params_bounds_card", None)
        toggle = getattr(self, "self_fit_params_bounds_toggle", None)
        if bounds_card is None or toggle is None:
            return
        try:
            bounds_card.visible = bool(getattr(toggle, "value", False))
        except Exception:
            pass
        self._persist_self_fit_model_to_context()

    def _on_self_fit_params_change(self, event=None) -> None:
        if getattr(self, "_suspend_self_scattering_events", False) or self.current_project_state is None:
            return

        def _round_widget(widget) -> None:
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

        model = self._self_fit_active_model()
        prefix = self._self_fit_widget_prefix(model)

        self._suspend_self_scattering_events = True
        try:
            for key in self._self_fit_param_keys(model):
                _round_widget(getattr(self, f"{prefix}_{key}_value", None))
                _round_widget(getattr(self, f"{prefix}_{key}_min", None))
                _round_widget(getattr(self, f"{prefix}_{key}_max", None))
        finally:
            self._suspend_self_scattering_events = False

        self._apply_self_fit_fixed_states(model)
        self._persist_self_fit_model_to_context()
        self._invalidate_self_fit_result(reason="Fit parameters changed.")

    def _self_fit_params_suggest_initial_guess(self, _event=None) -> None:
        if self.current_project_root is None or self.current_project_state is None:
            return
        self._self_fit_clear_alert()
        model = self._self_fit_active_model()
        data = self._load_self_dsdo_corrected_required()
        if data is None:
            return
        q_all, y_all, _e = data
        selection = self._self_data_selection_select_points(q=q_all, y=y_all)
        q_subset = np.asarray(selection.q_subset, dtype=float)
        y_subset = np.asarray(selection.y_subset, dtype=float)
        finite = np.isfinite(q_subset) & np.isfinite(y_subset)
        q_subset = q_subset[finite]
        y_subset = y_subset[finite]
        if q_subset.size < 5:
            self._self_fit_set_alert("Not enough points selected for fitting. Adjust Data Selection.", alert_type="warning")
            return

        q_min = float(np.nanmin(q_subset))
        q_max = float(np.nanmax(q_subset))
        q_mid = 0.5 * (q_min + q_max) if np.isfinite(q_min) and np.isfinite(q_max) else 0.0
        q_span = max(1e-6, float(q_max - q_min)) if np.isfinite(q_max - q_min) else 1.0

        self._suspend_self_scattering_events = True
        try:
            bound_wide = 1e6
            if model == self._SELF_FIT_MODEL_POLY:
                a0 = float(np.nanmedian(y_subset)) if y_subset.size else 0.0
                for key, v in (("a0", a0), ("a1", 0.0), ("a2", 0.0), ("a3", 0.0), ("a4", 0.0)):
                    getattr(self, f"self_fit_params_poly_{key}_value").value = v
                    getattr(self, f"self_fit_params_poly_{key}_min").value = -bound_wide
                    getattr(self, f"self_fit_params_poly_{key}_max").value = bound_wide
                    getattr(self, f"self_fit_params_poly_{key}_fixed").value = False
            elif model == self._SELF_FIT_MODEL_LORGAU:
                bckg = float(np.nanmin(y_subset)) if y_subset.size else 0.0
                peak = float(np.nanmax(y_subset)) if y_subset.size else 1.0
                f0 = float(max(peak - bckg, 1e-12))
                guesses = {"f0": f0, "eta": 0.5, "sigma": 2.0, "gamma": 2.0, "bckg": bckg}
                bounds = {
                    "f0": (-bound_wide, bound_wide),
                    "eta": (0.0, 1.0),
                    "sigma": (1e-6, bound_wide),
                    "gamma": (1e-6, bound_wide),
                    "bckg": (-bound_wide, bound_wide),
                }
                for key in ("f0", "eta", "sigma", "gamma", "bckg"):
                    getattr(self, f"self_fit_params_lorgau_{key}_value").value = guesses[key]
                    getattr(self, f"self_fit_params_lorgau_{key}_min").value = bounds[key][0]
                    getattr(self, f"self_fit_params_lorgau_{key}_max").value = bounds[key][1]
                    getattr(self, f"self_fit_params_lorgau_{key}_fixed").value = False
            else:
                # vanaQdep: mimic normalization defaults with simple Q0/dQ estimates.
                lowQ_est = float(np.nanmin(y_subset)) if y_subset.size else 0.4
                for key, v in (("a0", 1.0), ("a1", 0.0), ("a2", 0.0), ("A", 51.0), ("lowQ", lowQ_est), ("Q0", q_mid), ("dQ", q_span / 4.0)):
                    getattr(self, f"self_fit_params_vana_{key}_value").value = float(v)
                    getattr(self, f"self_fit_params_vana_{key}_fixed").value = False
                for key in ("a0", "a1", "a2"):
                    getattr(self, f"self_fit_params_vana_{key}_min").value = -bound_wide
                    getattr(self, f"self_fit_params_vana_{key}_max").value = bound_wide
                self.self_fit_params_vana_A_min.value = 1.0
                self.self_fit_params_vana_A_max.value = 300.0
                self.self_fit_params_vana_lowQ_min.value = 0.0
                self.self_fit_params_vana_lowQ_max.value = bound_wide
                self.self_fit_params_vana_Q0_min.value = q_min
                self.self_fit_params_vana_Q0_max.value = q_max
                self.self_fit_params_vana_dQ_min.value = 1e-3
                self.self_fit_params_vana_dQ_max.value = max(1e-3, q_span)
        finally:
            self._suspend_self_scattering_events = False

        self._apply_self_fit_fixed_states(model)
        self._persist_self_fit_model_to_context()
        self._invalidate_self_fit_result(reason="Suggested initial guess.")
        if hasattr(self, "_show_success_toast"):
            self._show_success_toast("Suggested initial fit parameters.")

    def _self_fit_params_run_fit(self, _event=None) -> None:
        if self.current_project_root is None or self.current_project_state is None:
            return
        if getattr(self, "operation_in_progress", False):
            return

        # Schedule the fit on the next tick so the UI can render the loading overlay
        # and disabled states before starting an expensive optimization (e.g. LorGau).
        if pn.state.curdoc is not None:
            self.operation_in_progress = True
            if hasattr(self, "self_fit_params_status"):
                self.self_fit_params_status.object = "**Status:** Running fit..."
            if hasattr(self, "_begin_workspace_loading"):
                self._begin_workspace_loading("Running fit...")
            if hasattr(self, "_refresh_interaction_states"):
                self._refresh_interaction_states()
            if hasattr(self, "_refresh_self_fit_button_states"):
                self._refresh_self_fit_button_states()

            pn.state.curdoc.add_next_tick_callback(lambda: self._self_fit_params_run_fit_impl())
            return

        # Fallback (tests / non-server usage): run synchronously.
        self.operation_in_progress = True
        if hasattr(self, "self_fit_params_status"):
            self.self_fit_params_status.object = "**Status:** Running fit..."
        if hasattr(self, "_begin_workspace_loading"):
            self._begin_workspace_loading("Running fit...")
        if hasattr(self, "_refresh_interaction_states"):
            self._refresh_interaction_states()
        if hasattr(self, "_refresh_self_fit_button_states"):
            self._refresh_self_fit_button_states()
        self._self_fit_params_run_fit_impl()

    def _self_fit_params_run_fit_impl(self) -> None:
        try:
            if self.current_project_root is None or self.current_project_state is None:
                return
            self._self_fit_clear_alert()

            model = self._self_fit_active_model()
            data = self._load_self_dsdo_corrected_required()
            if data is None:
                return
            q_all, y_all, _e = data
            selection = self._self_data_selection_select_points(q=q_all, y=y_all)
            q_subset = np.asarray(selection.q_subset, dtype=float)
            y_subset = np.asarray(selection.y_subset, dtype=float)
            finite = np.isfinite(q_subset) & np.isfinite(y_subset)
            q_subset = q_subset[finite]
            y_subset = y_subset[finite]

            params = self._self_fit_read_params_from_widgets(model)
            keys = self._self_fit_param_keys(model)
            fixed_flags = {k: bool(params[k]["fixed"]) for k in keys if k in params}
            free_keys = [k for k in keys if not fixed_flags.get(k, False)]
            n_free = len(free_keys)
            min_needed = max(5, n_free + 1)
            if q_subset.size < min_needed:
                self._self_fit_set_alert(
                    f"Not enough points selected for fitting. Need at least {min_needed} points (free params: {n_free}).",
                    alert_type="warning",
                )
                return

            # Resolve model function.
            try:
                if model == self._SELF_FIT_MODEL_POLY:
                    from toscana.math.polynomials import polyQ4 as base_func
                elif model == self._SELF_FIT_MODEL_LORGAU:
                    from toscana.math.line_shapes import LorGau as base_func
                else:
                    from toscana.models.scattering import vanaQdep as base_func
            except Exception as exc:
                self._self_fit_set_alert(f"Could not import model function: {exc}", alert_type="danger")
                return

            # Reduce fixed params from optimization.
            fixed_values = {k: float(params[k]["value"]) for k in keys if fixed_flags.get(k, False)}
            p0_free = [float(params[k]["value"]) for k in free_keys]
            bounds_lo_free = [float(params[k]["min"]) for k in free_keys]
            bounds_hi_free = [float(params[k]["max"]) for k in free_keys]

            def _reconstruct(theta_free: list[float]) -> list[float]:
                out: list[float] = []
                j = 0
                for k in keys:
                    if fixed_flags.get(k, False):
                        out.append(float(fixed_values[k]))
                    else:
                        out.append(float(theta_free[j]))
                        j += 1
                return out

            def wrapped(x, *theta_free):
                return base_func(x, *_reconstruct(list(theta_free)))

            popt_full: dict[str, float] = {}
            perr_full: dict[str, float] = {}

            if hasattr(self, "_refresh_interaction_states"):
                self._refresh_interaction_states()
            if n_free == 0:
                theta = _reconstruct([])
                for k, v in zip(keys, theta, strict=False):
                    popt_full[k] = float(v)
                    perr_full[k] = 0.0
            else:
                from scipy.optimize import curve_fit

                popt, pcov = curve_fit(
                    wrapped,
                    q_subset,
                    y_subset,
                    p0=p0_free,
                    bounds=(bounds_lo_free, bounds_hi_free),
                    maxfev=20000,
                )
                diag = np.diag(pcov) if pcov is not None else np.full(len(popt), np.nan, dtype=float)
                perr = np.sqrt(np.maximum(diag, 0.0))
                theta = _reconstruct([float(v) for v in popt])
                for k, v in zip(keys, theta, strict=False):
                    popt_full[k] = float(v)
                # Fill errors.
                i = 0
                for k in keys:
                    if fixed_flags.get(k, False):
                        perr_full[k] = 0.0
                    else:
                        perr_full[k] = float(perr[i]) if i < len(perr) and np.isfinite(perr[i]) else float("nan")
                        i += 1

            # Compute curve for plotting.
            y_fit = np.asarray(base_func(q_all, *[popt_full[k] for k in keys]), dtype=float)
            series = {
                "q": np.asarray(q_all, dtype=float),
                "y": np.asarray(y_all, dtype=float),
                "y_fit": y_fit,
                "q_subset": np.asarray(q_subset, dtype=float),
                "y_subset": np.asarray(y_subset, dtype=float),
            }

            fit_payload: dict[str, object] = {
                "timestamp": now_iso(),
                "model": model,
                "n_points": int(q_subset.size),
                "selection_snapshot": self._self_fit_selection_snapshot(),
                "lowq_snapshot": self._self_fit_lowq_snapshot(),
                "popt_full": popt_full,
                "perr_full": perr_full,
                "series": series,
            }

            context_id = str(getattr(getattr(self, "self_context_select", None), "value", "") or "").strip()
            self._self_fit_last = {
                "project_root": str(getattr(self, "current_project_root", "") or ""),
                "context_id": context_id,
                "payload": fit_payload,
            }

            self._persist_self_fit_last_fit_to_context(fit_payload)
            self._render_self_fit_result_table(fit_payload, stale=False)
            self._refresh_self_fit_plot(fit_payload)
            if hasattr(self, "self_fit_params_status"):
                self.self_fit_params_status.object = "**Status:** Fit complete."
            if hasattr(self, "_show_success_toast"):
                self._show_success_toast("Fit completed.")
        except Exception as exc:
            self._self_fit_set_alert(f"Fit failed: {exc}", alert_type="warning")
            if hasattr(self, "_show_error_toast"):
                self._show_error_toast(f"Fit failed: {exc}")
        finally:
            self.operation_in_progress = False
            if hasattr(self, "_end_workspace_loading"):
                try:
                    self._end_workspace_loading(defer=True)
                except Exception:
                    pass
            if hasattr(self, "_refresh_interaction_states"):
                try:
                    self._refresh_interaction_states()
                except Exception:
                    pass
            if hasattr(self, "_refresh_self_fit_button_states"):
                try:
                    self._refresh_self_fit_button_states()
                except Exception:
                    pass
            if hasattr(self, "_refresh_self_static_structure_factor_button_states"):
                try:
                    self._refresh_self_static_structure_factor_button_states()
                except Exception:
                    pass
            elif hasattr(self, "_refresh_self_static_structure_factor_panel"):
                try:
                    self._refresh_self_static_structure_factor_panel()
                except Exception:
                    pass

    def _persist_self_fit_last_fit_to_context(self, fit_payload: dict[str, object]) -> None:
        if self.current_project_root is None or self.current_project_state is None:
            return
        context_id = str(getattr(getattr(self, "self_context_select", None), "value", "") or "").strip()
        if not context_id:
            return
        manifest_ref = self._selected_self_manifest_ref()
        if not manifest_ref:
            return
        payload = load_context_manifest(self.current_project_root, manifest_ref)
        if not isinstance(payload, dict):
            return
        decisions = payload.get("decisions") if isinstance(payload.get("decisions"), dict) else {}
        self_block = decisions.get("self_scattering") if isinstance(decisions.get("self_scattering"), dict) else {}
        # Persist only JSON-safe metadata (avoid storing numpy arrays in the manifest).
        safe_fit: dict[str, object] = {
            "timestamp": fit_payload.get("timestamp"),
            "model": fit_payload.get("model"),
            "n_points": fit_payload.get("n_points"),
            "selection_snapshot": fit_payload.get("selection_snapshot") if isinstance(fit_payload.get("selection_snapshot"), dict) else {},
            "lowq_snapshot": fit_payload.get("lowq_snapshot") if isinstance(fit_payload.get("lowq_snapshot"), dict) else {},
            "popt_full": fit_payload.get("popt_full") if isinstance(fit_payload.get("popt_full"), dict) else {},
            "perr_full": fit_payload.get("perr_full") if isinstance(fit_payload.get("perr_full"), dict) else {},
        }

        fm = self_block.get("fit_model") if isinstance(self_block.get("fit_model"), dict) else {}
        fm["last_fit"] = safe_fit
        self_block["fit_model"] = fm
        decisions["self_scattering"] = self_block
        payload["decisions"] = decisions
        try:
            write_context_manifest(self.current_project_root, context_id=context_id, payload=payload)
        except Exception:
            return

    def _self_fit_current_last_fit_payload(self) -> dict[str, object] | None:
        context_id = str(getattr(getattr(self, "self_context_select", None), "value", "") or "").strip()
        project_token = str(getattr(self, "current_project_root", "") or "")
        cached = getattr(self, "_self_fit_last", None)
        if not isinstance(cached, dict):
            return None
        if str(cached.get("context_id") or "").strip() != context_id:
            return None
        if str(cached.get("project_root") or "") != project_token:
            return None
        payload = cached.get("payload")
        return payload if isinstance(payload, dict) else None
