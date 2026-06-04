from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

from toscana.io.loading import read_xye
from toscana.math.fourier import backFT

from toscana_gui.contexts import (
    load_context_manifest,
    project_relpath,
    resolve_project_path,
)
from toscana_gui.bft.plots import build_bft_animation_figure, build_bft_placeholder_figure
from toscana_gui.ft.plots import build_ft_real_space_function_figure


def _html_escape(value: object) -> str:
    import html

    return html.escape(str(value), quote=True)


def _fmt_compact_number(value: object, *, decimals: int = 6) -> str:
    try:
        x = float(value)
    except Exception:
        return ""
    if not np.isfinite(x):
        return ""
    if x == 0.0:
        return "0"
    if abs(x) < 1e-3:
        return f"{x:.3e}"
    return f"{x:.{int(decimals)}f}".rstrip("0").rstrip(".")


class BFTControllerMixin:
    _BFT_BLUE_LINE = "rgba(37, 99, 235, 0.90)"

    def _set_bft_animation_counter(self, *, idx: int, max_idx: int) -> None:
        """
        Update the small iteration counter label shown above the Player.

        idx/max_idx are 0-based inclusive bounds.
        """
        pane = getattr(self, "bft_animation_counter", None)
        if pane is None:
            return
        if max_idx < 0:
            text = ""
        else:
            # Display as 1-based for users.
            text = f"<strong>Iteration {int(idx) + 1}/{int(max_idx) + 1}</strong>"
        try:
            pane.object = text
        except Exception:
            pass

    @staticmethod
    def _bft_final_plot_specs() -> list[dict[str, str]]:
        # Mirrors FT real-space keys, but BFT is always "final iteration".
        return [
            {"key": "pcf", "title": "Pair Correlation Function", "latex": "G(R)", "yaxis": "G(R)"},
            {"key": "pdf", "title": "Pair Distribution Function", "latex": "g(R)", "yaxis": "g(R)"},
            {"key": "rdf", "title": "Radial Distribution Function", "latex": "RDF(R)", "yaxis": "RDF(R)"},
            {"key": "tor", "title": "Linearised Radial Distribution Function", "latex": "T(R)", "yaxis": "T(R)"},
            {"key": "run", "title": "Running integral of RDF(R)", "latex": r"\int_0^R RDF(r)\,dr", "yaxis": "Running integral"},
        ]

    def _bft_state_store(self) -> dict[str, dict[str, object]]:
        store = getattr(self, "_bft_state_by_context", None)
        if not isinstance(store, dict):
            store = {}
            self._bft_state_by_context = store
        return store

    def _bft_current_state(self) -> dict[str, object] | None:
        context_id = str(getattr(getattr(self, "bft_context_select", None), "value", "") or "").strip()
        if not context_id:
            return None
        return self._bft_state_store().get(context_id)

    def _get_bft_context_entries(self) -> list[dict[str, Any]]:
        if self.current_project_state is None:
            return []
        if hasattr(self, "_get_background_state"):
            state = self._get_background_state()
        else:
            state = getattr(self.current_project_state, "background", {}) or {}
        contexts = state.get("contexts") if isinstance(state.get("contexts"), dict) else {}
        entries = contexts.get("entries") if isinstance(contexts.get("entries"), list) else []
        return [e for e in entries if isinstance(e, dict)]

    def _selected_bft_manifest_ref(self) -> str:
        selected = str(getattr(getattr(self, "bft_context_select", None), "value", "") or "").strip()
        if not selected:
            return ""
        entry = next((e for e in self._get_bft_context_entries() if str(e.get("context_id") or "").strip() == selected), None)
        if not isinstance(entry, dict):
            return ""
        return str(entry.get("manifest") or "").strip()

    @staticmethod
    def _format_context_timestamp(value: object) -> str:
        # Keep formatting identical to FT.
        raw = str(value).strip() if value is not None else ""
        if not raw:
            return ""
        try:
            parsed = datetime.fromisoformat(raw)
            return parsed.strftime("%Y-%m-%d %H:%M")
        except Exception:
            return raw

    def _refresh_bft_context_options(self, *, apply_selection: bool) -> None:
        if self.current_project_state is None or self.current_project_root is None:
            return
        if not hasattr(self, "bft_context_select"):
            return

        entries = self._get_bft_context_entries()
        options: dict[str, str] = {}
        for entry in entries:
            context_id = str(entry.get("context_id") or "").strip()
            manifest = str(entry.get("manifest") or "").strip()
            if not context_id or not manifest:
                continue
            created_at = self._format_context_timestamp(entry.get("created_at"))
            sample_title = str(entry.get("sample_title" or "")).strip()
            label = " — ".join([v for v in (created_at, sample_title, context_id) if v])
            options[label] = context_id

        if not options:
            options = {"No exported background contexts yet.": ""}
            self.bft_context_select.options = options
            self.bft_context_select.value = ""
            self.bft_context_select.disabled = True
            if hasattr(self, "bft_context_message"):
                self.bft_context_message.object = "No background contexts are available yet. Run **Background â†’ Export Data** first."
                self.bft_context_message.alert_type = "warning"
            return

        self.bft_context_select.disabled = False
        self.bft_context_select.options = options

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

        suspend_flag = "_suspend_bft_events"
        setattr(self, suspend_flag, True)
        try:
            self.bft_context_select.value = selected
        finally:
            setattr(self, suspend_flag, False)

    def _refresh_bft_context_summary(self) -> None:
        if self.current_project_root is None:
            return
        if not hasattr(self, "bft_context_message") or not hasattr(self, "bft_context_info_hover") or not hasattr(
            self, "bft_context_summary"
        ):
            return

        selected = str(getattr(getattr(self, "bft_context_select", None), "value", "") or "").strip()
        if not selected:
            self.bft_context_summary.object = ""
            self.bft_context_info_hover.value = ""
            self.bft_context_message.object = "Select a context to proceed. Contexts are created by **Background â†’ Export Data**."
            self.bft_context_message.alert_type = "secondary"
            self._bft_soq_selected_path = None
            return

        manifest_ref = self._selected_bft_manifest_ref()
        if not manifest_ref:
            self.bft_context_summary.object = ""
            self.bft_context_info_hover.value = ""
            self.bft_context_message.object = "Selected context has no manifest path."
            self.bft_context_message.alert_type = "danger"
            self._bft_soq_selected_path = None
            return

        payload = load_context_manifest(self.current_project_root, manifest_ref)
        if payload is None:
            manifest_path = resolve_project_path(self.current_project_root, manifest_ref)
            self.bft_context_summary.object = ""
            self.bft_context_info_hover.value = ""
            self.bft_context_message.object = f"Context manifest could not be loaded: `{manifest_path}`"
            self.bft_context_message.alert_type = "danger"
            self._bft_soq_selected_path = None
            return

        artifacts = payload.get("artifacts") if isinstance(payload.get("artifacts"), dict) else {}
        soq_ref = artifacts.get("static_structure_factor_qdat") if isinstance(artifacts.get("static_structure_factor_qdat"), str) else None
        if not isinstance(soq_ref, str) or not soq_ref.strip():
            self.bft_context_message.object = "This context has no `SOQ_qdat`. Run **Self â†’ Export Static Structure Factor** for this context."
            self.bft_context_message.alert_type = "warning"
            soq_path = None
        else:
            try:
                soq_path = resolve_project_path(self.current_project_root, soq_ref)
            except Exception:
                soq_path = None
                self.bft_context_message.object = "The `SOQ_qdat` reference could not be resolved."
                self.bft_context_message.alert_type = "danger"

        self._bft_soq_selected_path = soq_path

        # Tooltip (same formatting as FT).
        self.bft_context_summary.object = ""

        def _code(val: object) -> str:
            return f"<code style=\"overflow-wrap:anywhere; word-break:break-word;\">{_html_escape(val)}</code>"

        sample = payload.get("sample") if isinstance(payload.get("sample"), dict) else {}
        sample_title = str(sample.get("title") or "").strip()
        par_rel = str(sample.get("par_path_rel") or "").strip()
        ft_dat_path: Path | None = None
        ft_dat_ref = artifacts.get("ft_real_space_no_lorch_dat") if isinstance(artifacts.get("ft_real_space_no_lorch_dat"), str) else None
        if isinstance(ft_dat_ref, str) and ft_dat_ref.strip():
            try:
                ft_dat_path = resolve_project_path(self.current_project_root, ft_dat_ref)
            except Exception:
                ft_dat_path = None

        body_lines = [
            f"<div><strong>Context id:</strong> {_code(selected)}</div>",
            f"<div><strong>Sample title:</strong> {_html_escape(sample_title) if sample_title else _code('')}</div>",
            f"<div><strong>Par (rel):</strong> {_code(par_rel)}</div>",
            f"<div><strong>SOQ_qdat:</strong> {_code(project_relpath(self.current_project_root, soq_path) if isinstance(soq_path, Path) else '')}</div>",
        ]
        self.bft_context_info_hover.value = (
            "<div style=\"max-width: 420px; line-height: 1.6; overflow-wrap:anywhere; word-break:break-word;\">"
            + "".join(body_lines)
            + "</div>"
        )

        # If we already set a hard failure about SOQ above, keep that message.
        if self.bft_context_message.alert_type in {"danger", "warning"} and "SOQ_qdat" in str(self.bft_context_message.object):
            return

        # Determine whether we have FT inputs.
        in_session_ok = self._bft_can_use_in_session_ft(context_id=selected)
        ft_export_ok = isinstance(ft_dat_path, Path) and ft_dat_path.exists() and ft_dat_path.is_file()

        if soq_path is None:
            # keep earlier message
            return
        if not soq_path.exists():
            self.bft_context_message.object = f"`SOQ_qdat` not found on disk: `{soq_path}`"
            self.bft_context_message.alert_type = "warning"
            return

        if not (in_session_ok or ft_export_ok):
            self.bft_context_message.object = (
                "FT inputs are missing for this context. Confirm Effective Atomic Density in **FT** (in-session) "
                "or export FT Real Space Functions for this context."
            )
            self.bft_context_message.alert_type = "warning"
            return

        self.bft_context_message.object = "Context ready for BFT."
        self.bft_context_message.alert_type = "success"

    def _on_bft_context_change(self, event) -> None:
        if bool(getattr(self, "_suspend_bft_events", False)) or self.current_project_state is None:
            return
        if event.new == event.old:
            return

        context_id = str(event.new or "").strip()
        if not context_id:
            return

        # Mirror FT behavior: store active context id in background contexts state.
        if hasattr(self, "_get_background_state") and hasattr(self, "_persist_background_state"):
            state = self._get_background_state()
            contexts = state.get("contexts") if isinstance(state.get("contexts"), dict) else {}
            contexts["active_context_id"] = context_id
            state["contexts"] = contexts
            self._persist_background_state(state)

        self._refresh_bft_context_summary()
        self._refresh_bft_results_panel()
        if hasattr(self, "_refresh_interaction_states"):
            self._refresh_interaction_states()
        if hasattr(self, "_render_current_screen"):
            self._render_current_screen()

    def _bft_can_use_in_session_ft(self, *, context_id: str) -> bool:
        state = getattr(self, "_ft_rho_state", None)
        if not isinstance(state, dict):
            return False
        if str(state.get("context_id") or "").strip() != str(context_id or "").strip():
            return False
        selection = state.get("rho_selection") if isinstance(state.get("rho_selection"), dict) else None
        if not isinstance(selection, dict) or not bool(selection.get("confirmed", False)):
            return False
        snap = selection.get("confirmed_snapshot") if isinstance(selection.get("confirmed_snapshot"), dict) else None
        if not isinstance(snap, dict):
            return False
        no_block = snap.get("no_lorch") if isinstance(snap.get("no_lorch"), dict) else None
        if not isinstance(no_block, dict):
            return False
        try:
            rho = float(no_block.get("chosen_rho"))
        except Exception:
            return False
        if not np.isfinite(rho) or rho <= 0:
            return False

        real_space = state.get("real_space") if isinstance(state.get("real_space"), dict) else None
        if not isinstance(real_space, dict):
            return False
        series_data = real_space.get("series_data") if isinstance(real_space.get("series_data"), dict) else None
        if not isinstance(series_data, dict):
            return False
        no_rs = series_data.get("no_lorch") if isinstance(series_data.get("no_lorch"), dict) else None
        if not isinstance(no_rs, dict):
            return False
        r = no_rs.get("r")
        pdf = no_rs.get("pdf")
        if not isinstance(r, np.ndarray) or not isinstance(pdf, np.ndarray):
            return False
        return r.size > 1 and pdf.size == r.size

    def _bft_load_ft_inputs(self, *, context_id: str, payload: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, float, str] | None:
        """
        Returns (r, pdf, rho, signature) for No-Lorch series.
        Prefers in-session FT, falls back to ft_real_space_no_lorch_dat.
        """
        # 1) In-session FT
        state = getattr(self, "_ft_rho_state", None)
        if isinstance(state, dict) and str(state.get("context_id") or "").strip() == str(context_id).strip():
            selection = state.get("rho_selection") if isinstance(state.get("rho_selection"), dict) else None
            snap = selection.get("confirmed_snapshot") if isinstance(selection, dict) else None
            no_block = snap.get("no_lorch") if isinstance(snap, dict) else None
            real_space = state.get("real_space") if isinstance(state.get("real_space"), dict) else None
            series_data = real_space.get("series_data") if isinstance(real_space, dict) else None
            no_rs = series_data.get("no_lorch") if isinstance(series_data, dict) else None
            if isinstance(no_block, dict) and isinstance(no_rs, dict):
                try:
                    rho = float(no_block.get("chosen_rho"))
                except Exception:
                    rho = float("nan")
                r = no_rs.get("r")
                pdf = no_rs.get("pdf")
                if (
                    np.isfinite(rho)
                    and rho > 0
                    and isinstance(r, np.ndarray)
                    and isinstance(pdf, np.ndarray)
                    and r.size > 1
                    and pdf.shape == r.shape
                ):
                    sig = str(no_rs.get("signature") or "")
                    signature = f"in-session:{sig}:{rho:.12g}"
                    return np.asarray(r, dtype=float), np.asarray(pdf, dtype=float), float(rho), signature

        # 2) FT export file
        artifacts = payload.get("artifacts") if isinstance(payload.get("artifacts"), dict) else {}
        ref = artifacts.get("ft_real_space_no_lorch_dat") if isinstance(artifacts.get("ft_real_space_no_lorch_dat"), str) else None
        if not isinstance(ref, str) or not ref.strip() or self.current_project_root is None:
            return None
        try:
            path = resolve_project_path(self.current_project_root, ref)
        except Exception:
            return None
        if not path.exists() or not path.is_file():
            return None

        parsed = self._bft_parse_ft_real_space_dat(path)
        if parsed is None:
            return None
        r, pdf, rho = parsed

        try:
            stat = path.stat()
            mtime_ns = int(getattr(stat, "st_mtime_ns", int(stat.st_mtime * 1e9)))
            size = int(stat.st_size)
        except Exception:
            mtime_ns = -1
            size = -1
        signature = f"ft-export:{str(path.resolve(strict=False))}:{mtime_ns}:{size}:{rho:.12g}"
        return r, pdf, rho, signature

    @staticmethod
    def _bft_parse_ft_real_space_dat(path: Path) -> tuple[np.ndarray, np.ndarray, float] | None:
        """
        Parse FT real-space export .dat written by FTControllerMixin._perform_ft_real_space_export.
        Returns (r, pdf, rho).
        """
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            return None

        rho = None
        r_vals: list[float] = []
        pdf_vals: list[float] = []
        for raw in text.splitlines():
            line = raw.strip()
            if not line:
                continue
            if line.startswith("#"):
                if "rho_effective_atomic_density:" in line:
                    try:
                        rho = float(line.split("rho_effective_atomic_density:", 1)[1].strip())
                    except Exception:
                        rho = None
                continue
            parts = line.split()
            if len(parts) < 3:
                continue
            try:
                rr = float(parts[0])
                pdf = float(parts[2])  # column order: R, G(R), g(R), RDF, T(R), RUN
            except Exception:
                continue
            r_vals.append(rr)
            pdf_vals.append(pdf)

        if rho is None:
            return None
        if not np.isfinite(rho) or rho <= 0:
            return None
        if len(r_vals) < 2 or len(pdf_vals) != len(r_vals):
            return None
        r = np.asarray(r_vals, dtype=float)
        pdf = np.asarray(pdf_vals, dtype=float)
        order = np.argsort(r)
        r = r[order]
        pdf = pdf[order] if pdf.shape == r.shape else pdf
        return r, pdf, float(rho)

    def _bft_load_soq(self, *, context_id: str, payload: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, str] | None:
        if self.current_project_root is None:
            return None
        artifacts = payload.get("artifacts") if isinstance(payload.get("artifacts"), dict) else {}
        soq_ref = artifacts.get("static_structure_factor_qdat") if isinstance(artifacts.get("static_structure_factor_qdat"), str) else None
        if not isinstance(soq_ref, str) or not soq_ref.strip():
            return None
        try:
            path = resolve_project_path(self.current_project_root, soq_ref)
        except Exception:
            return None
        if not path.exists() or not path.is_file():
            return None

        # Reuse FT cache if available.
        if hasattr(self, "_read_ft_soq_xye_cached"):
            q, y, _e = self._read_ft_soq_xye_cached(path)  # type: ignore[attr-defined]
        else:
            q, y, _e = read_xye(str(path))
            q = np.asarray(q, dtype=float)
            y = np.asarray(y, dtype=float)

        try:
            stat = path.stat()
            mtime_ns = int(getattr(stat, "st_mtime_ns", int(stat.st_mtime * 1e9)))
            size = int(stat.st_size)
        except Exception:
            mtime_ns = -1
            size = -1
        signature = f"{str(path.resolve(strict=False))}:{mtime_ns}:{size}:{context_id}"
        return q, y, signature

    def _bft_iteration_signature(
        self,
        *,
        soq_sig: str,
        ft_sig: str,
        niter: int,
        cut: list[float],
    ) -> str:
        cut_sig = ",".join(_fmt_compact_number(v) for v in cut)
        return f"{soq_sig}:{ft_sig}:niter={int(niter)}:cut=[{cut_sig}]"

    def _bft_set_disabled_ui(self, *, reason: str) -> None:
        if hasattr(self, "bft_run_status"):
            try:
                self.bft_run_status.object = str(reason)
            except Exception:
                pass
        for name in (
            "bft_run_button",
            "bft_iterations_input",
            "bft_final_prev_plot_button",
            "bft_final_next_plot_button",
        ):
            w = getattr(self, name, None)
            if w is None:
                continue
            try:
                w.disabled = True
            except Exception:
                pass
        if hasattr(self, "bft_animation_pane"):
            try:
                self.bft_animation_pane.object = build_bft_placeholder_figure(width=800, height=600)
            except Exception:
                pass
        if hasattr(self, "bft_final_plot_pane"):
            try:
                self.bft_final_plot_pane.object = build_bft_placeholder_figure(width=800, height=600)
            except Exception:
                pass
        if hasattr(self, "bft_final_plot_view_label"):
            try:
                self.bft_final_plot_view_label.object = ""
            except Exception:
                pass

    def _refresh_bft_results_panel(self) -> None:
        if self.current_project_root is None or self.current_project_state is None:
            self._bft_set_disabled_ui(reason="Open a project to use BFT.")
            return
        context_id = str(getattr(getattr(self, "bft_context_select", None), "value", "") or "").strip()
        if not context_id:
            self._bft_set_disabled_ui(reason="Select a context to view BFT results.")
            return

        # Enable run controls if context is ready.
        if hasattr(self, "bft_run_button"):
            try:
                self.bft_run_button.disabled = bool(getattr(self, "operation_in_progress", False))
            except Exception:
                pass
        if hasattr(self, "bft_iterations_input"):
            try:
                self.bft_iterations_input.disabled = bool(getattr(self, "operation_in_progress", False))
            except Exception:
                pass

        state = self._bft_current_state()
        if not isinstance(state, dict):
            if hasattr(self, "bft_run_status"):
                try:
                    self.bft_run_status.object = "No Back-FT results yet. Set iterations and click Run."
                except Exception:
                    pass
            if hasattr(self, "bft_animation_pane"):
                try:
                    self.bft_animation_pane.object = build_bft_placeholder_figure(width=800, height=600)
                except Exception:
                    pass
            if hasattr(self, "bft_final_plot_pane"):
                try:
                    self.bft_final_plot_pane.object = build_bft_placeholder_figure(width=800, height=600)
                except Exception:
                    pass
            if hasattr(self, "bft_final_plot_view_label"):
                try:
                    self.bft_final_plot_view_label.object = ""
                except Exception:
                    pass
            if hasattr(self, "bft_final_prev_plot_button"):
                self.bft_final_prev_plot_button.disabled = True
            if hasattr(self, "bft_final_next_plot_button"):
                self.bft_final_next_plot_button.disabled = True
            if hasattr(self, "bft_animation_player"):
                try:
                    self.bft_animation_player.disabled = True
                    self.bft_animation_player.start = 0
                    self.bft_animation_player.end = 0
                    self.bft_animation_player.value = 0
                except Exception:
                    pass
            self._set_bft_animation_counter(idx=0, max_idx=-1)
            return

        self._refresh_bft_results_view(state)

    def _sync_bft_animation_player(self, state: dict[str, object]) -> int:
        """
        Sync the Player widget range/value from the current BFT state.
        Returns the selected iteration index actually used.
        """
        pcf_iter = state.get("pcf_iter")
        pdf_iter = state.get("pdf_iter")
        if not (isinstance(pcf_iter, list) and isinstance(pdf_iter, list)):
            return 0
        max_idx = max(0, min(len(pcf_iter), len(pdf_iter)) - 1)
        idx = int(state.get("selected_animation_index") or 0)
        idx = max(0, min(idx, max_idx))
        state["selected_animation_index"] = idx

        player = getattr(self, "bft_animation_player", None)
        if player is None:
            return idx

        suspend_flag = "_suspend_bft_animation_events"
        setattr(self, suspend_flag, True)
        try:
            player.disabled = max_idx <= 0 or bool(getattr(self, "operation_in_progress", False))
            player.start = 0
            player.end = max_idx
            if int(getattr(player, "value", 0) or 0) != idx:
                player.value = idx
        finally:
            setattr(self, suspend_flag, False)
        self._set_bft_animation_counter(idx=idx, max_idx=max_idx)
        return idx

    def _refresh_bft_results_view(self, state: dict[str, object]) -> None:
        context_id = str(state.get("context_id") or "").strip()
        q = state.get("q")
        r = state.get("r")
        soq_iter = state.get("soq_iter")
        pcf_iter = state.get("pcf_iter")
        pdf_iter = state.get("pdf_iter")
        if not (
            isinstance(q, np.ndarray)
            and isinstance(r, np.ndarray)
            and isinstance(soq_iter, list)
            and isinstance(pcf_iter, list)
            and isinstance(pdf_iter, list)
        ):
            self._bft_set_disabled_ui(reason="Back-FT results are not available yet.")
            return

        niter = int(state.get("iterations") or 0)
        # Intentionally keep the run-status line quiet on success (per UX request).
        if hasattr(self, "bft_run_status"):
            try:
                self.bft_run_status.object = ""
            except Exception:
                pass

        anim_idx = self._sync_bft_animation_player(state)
        if hasattr(self, "bft_animation_pane"):
            try:
                self.bft_animation_pane.object = build_bft_animation_figure(
                    r=r,
                    pcf_iter=state.get("pcf_iter") if isinstance(state.get("pcf_iter"), list) else [],
                    pdf_iter=pdf_iter,
                    iteration=int(anim_idx),
                    context_id=context_id,
                    width=800,
                    height=600,
                )
            except Exception:
                try:
                    self.bft_animation_pane.object = build_bft_placeholder_figure(width=800, height=600)
                except Exception:
                    pass

        # Final function viewer
        selected_plot_index = int(state.get("selected_plot_index") or 0)
        specs = self._bft_final_plot_specs()
        selected_plot_index = max(0, min(selected_plot_index, len(specs) - 1))
        state["selected_plot_index"] = selected_plot_index

        # Enable/disable navigation.
        if hasattr(self, "bft_final_prev_plot_button"):
            self.bft_final_prev_plot_button.disabled = bool(getattr(self, "operation_in_progress", False)) or selected_plot_index <= 0
        if hasattr(self, "bft_final_next_plot_button"):
            self.bft_final_next_plot_button.disabled = bool(getattr(self, "operation_in_progress", False)) or selected_plot_index >= (len(specs) - 1)

        key = specs[selected_plot_index]["key"]
        y = state.get(key)
        if not isinstance(y, np.ndarray):
            # Back-compat: allow state to store final arrays in a dict.
            final = state.get("final") if isinstance(state.get("final"), dict) else {}
            y = final.get(key) if isinstance(final.get(key), np.ndarray) else None
        if not isinstance(y, np.ndarray):
            if hasattr(self, "bft_final_plot_pane"):
                self.bft_final_plot_pane.object = None
            return

        title = specs[selected_plot_index]["title"]
        yaxis = specs[selected_plot_index]["yaxis"]
        if hasattr(self, "bft_final_plot_view_label"):
            try:
                self.bft_final_plot_view_label.object = f"<strong>{_html_escape(title)}</strong>"
            except Exception:
                pass

        if hasattr(self, "bft_final_plot_pane"):
            try:
                self.bft_final_plot_pane.object = build_ft_real_space_function_figure(
                    x=np.asarray(r, dtype=float),
                    y=np.asarray(y, dtype=float),
                    series_label=f"Iteration {niter}",
                    xaxis_title="R",
                    yaxis_title=yaxis,
                    line_color=self._BFT_BLUE_LINE,
                    context_id=context_id,
                    width=800,
                    height=600,
                )
            except Exception:
                self.bft_final_plot_pane.object = None

    def _on_bft_final_prev_plot(self, _event=None) -> None:
        if bool(getattr(self, "operation_in_progress", False)):
            return
        state = self._bft_current_state()
        if not isinstance(state, dict):
            return
        idx = int(state.get("selected_plot_index") or 0)
        state["selected_plot_index"] = max(0, idx - 1)
        self._refresh_bft_results_view(state)

    def _on_bft_final_next_plot(self, _event=None) -> None:
        if bool(getattr(self, "operation_in_progress", False)):
            return
        state = self._bft_current_state()
        if not isinstance(state, dict):
            return
        idx = int(state.get("selected_plot_index") or 0)
        state["selected_plot_index"] = idx + 1
        self._refresh_bft_results_view(state)

    def _clear_bft_iterations_warning(self) -> None:
        if hasattr(self, "bft_iterations_warning_card"):
            try:
                self.bft_iterations_warning_card.visible = False
            except Exception:
                pass
        if hasattr(self, "bft_iterations_warning"):
            try:
                self.bft_iterations_warning.visible = False
            except Exception:
                pass
        for name in ("bft_iterations_confirm_button", "bft_iterations_cancel_button"):
            btn = getattr(self, name, None)
            if btn is None:
                continue
            try:
                btn.disabled = bool(getattr(self, "operation_in_progress", False))
            except Exception:
                pass

    def _prompt_bft_iterations_warning(self, *, niter: int) -> None:
        if hasattr(self, "bft_iterations_warning"):
            try:
                self.bft_iterations_warning.object = (
                    f"You selected **{int(niter)}** iterations. Values above 5 can affect results. "
                    "Confirm to continue."
                )
                self.bft_iterations_warning.alert_type = "warning"
                self.bft_iterations_warning.visible = True
            except Exception:
                pass
        if hasattr(self, "bft_iterations_warning_card"):
            try:
                self.bft_iterations_warning_card.visible = True
            except Exception:
                pass

        # Ensure warning buttons are clickable even if they were disabled during a prior operation.
        for name in ("bft_iterations_confirm_button", "bft_iterations_cancel_button"):
            btn = getattr(self, name, None)
            if btn is None:
                continue
            try:
                btn.disabled = bool(getattr(self, "operation_in_progress", False))
            except Exception:
                pass

    def _on_bft_run_clicked(self, _event=None) -> None:
        if self.operation_in_progress:
            if hasattr(self, "_show_workspace_blocked_message"):
                self._show_workspace_blocked_message()
            return
        niter = int(getattr(getattr(self, "bft_iterations_input", None), "value", 0) or 0)
        if niter > 5:
            self._prompt_bft_iterations_warning(niter=niter)
            if hasattr(self, "_render_current_screen"):
                self._render_current_screen()
            return
        self._run_bft_iterations(niter=niter)

    def _on_bft_confirm_iterations_warning(self, _event=None) -> None:
        if self.operation_in_progress:
            return
        niter = int(getattr(getattr(self, "bft_iterations_input", None), "value", 0) or 0)
        self._clear_bft_iterations_warning()
        self._run_bft_iterations(niter=niter)

    def _on_bft_cancel_iterations_warning(self, _event=None) -> None:
        self._clear_bft_iterations_warning()
        if hasattr(self, "_render_current_screen"):
            self._render_current_screen()

    def _on_bft_animation_iteration_change(self, event) -> None:
        if bool(getattr(self, "_suspend_bft_animation_events", False)):
            return
        if bool(getattr(self, "operation_in_progress", False)):
            return
        state = self._bft_current_state()
        if not isinstance(state, dict):
            return
        try:
            idx = int(event.new)
        except Exception:
            idx = 0
        state["selected_animation_index"] = idx

        q = state.get("q")
        r = state.get("r")
        pcf_iter = state.get("pcf_iter")
        pdf_iter = state.get("pdf_iter")
        if not (isinstance(q, np.ndarray) and isinstance(r, np.ndarray) and isinstance(pcf_iter, list) and isinstance(pdf_iter, list)):
            return

        context_id = str(state.get("context_id") or "").strip()
        max_idx = max(0, min(len(pcf_iter), len(pdf_iter)) - 1)
        idx = max(0, min(idx, max_idx))
        state["selected_animation_index"] = idx
        self._set_bft_animation_counter(idx=idx, max_idx=max_idx)
        if hasattr(self, "bft_animation_pane"):
            try:
                self.bft_animation_pane.object = build_bft_animation_figure(
                    r=np.asarray(r, dtype=float),
                    pcf_iter=pcf_iter,
                    pdf_iter=pdf_iter,
                    iteration=int(idx),
                    context_id=context_id,
                    width=800,
                    height=600,
                )
            except Exception:
                pass

    def _run_bft_iterations(self, *, niter: int) -> None:
        if self.current_project_root is None or self.current_project_state is None:
            return
        context_id = str(getattr(getattr(self, "bft_context_select", None), "value", "") or "").strip()
        if not context_id:
            return

        manifest_ref = self._selected_bft_manifest_ref()
        payload = load_context_manifest(self.current_project_root, manifest_ref) if manifest_ref else None
        if not isinstance(payload, dict):
            if hasattr(self, "_show_error_toast"):
                self._show_error_toast("Context manifest could not be loaded.")
            return

        ft_inputs = self._bft_load_ft_inputs(context_id=context_id, payload=payload)
        soq_inputs = self._bft_load_soq(context_id=context_id, payload=payload)
        if ft_inputs is None or soq_inputs is None:
            if hasattr(self, "_show_warning_toast"):
                self._show_warning_toast("BFT inputs are missing. Confirm density in FT or export FT Real Space Functions.")
            return

        r, pdf0, rho, ft_sig = ft_inputs
        q, soq0, soq_sig = soq_inputs
        if r.size < 2 or q.size < 2:
            if hasattr(self, "_show_warning_toast"):
                self._show_warning_toast("BFT input arrays are empty.")
            return

        # Avoid division by 0 / NaN at Q=0 or R=0 (legacy behavior).
        q = np.asarray(q, dtype=float).copy()
        r = np.asarray(r, dtype=float).copy()
        if q.size and q[0] == 0.0:
            q[0] = 1e-6
        if r.size and r[0] == 0.0:
            r[0] = 1e-6

        # Legacy notebook behavior uses a repulsion-region cut (e.g. [2.6]).
        # v1 does not expose this in the UI, but we keep the legacy default so
        # the iteration loop produces the expected refinement behavior.
        cut: list[float] = [2.6]
        computed_sig = self._bft_iteration_signature(soq_sig=soq_sig, ft_sig=ft_sig, niter=int(niter), cut=cut)
        existing = self._bft_state_store().get(context_id)
        if isinstance(existing, dict) and str(existing.get("computed_signature") or "") == computed_sig:
            self._refresh_bft_results_panel()
            return

        # Run compute.
        self.operation_in_progress = True
        if hasattr(self, "_clear_workspace_message"):
            self._clear_workspace_message()
        if hasattr(self, "_begin_workspace_loading"):
            self._begin_workspace_loading("Running Back Fourier Transform...")
        if hasattr(self, "_render_current_screen"):
            self._render_current_screen()

        try:
            soq_iter: list[np.ndarray] = [np.asarray(soq0, dtype=float)]
            pcf_iter: list[np.ndarray] = [np.zeros_like(r, dtype=float)]  # unknown at iteration 0 in this UI
            pdf_iter: list[np.ndarray] = [np.asarray(pdf0, dtype=float)]
            rdf_iter: list[np.ndarray] = [np.zeros_like(r, dtype=float)]
            tor_iter: list[np.ndarray] = [np.zeros_like(r, dtype=float)]
            run_iter: list[np.ndarray] = [np.zeros_like(r, dtype=float)]

            # If in-session FT exists for this context, we can seed iteration 0 correlation functions for completeness.
            state_ft = getattr(self, "_ft_rho_state", None)
            if isinstance(state_ft, dict) and str(state_ft.get("context_id") or "").strip() == context_id:
                rs = state_ft.get("real_space") if isinstance(state_ft.get("real_space"), dict) else {}
                series_data = rs.get("series_data") if isinstance(rs.get("series_data"), dict) else {}
                no_rs = series_data.get("no_lorch") if isinstance(series_data.get("no_lorch"), dict) else None
                if isinstance(no_rs, dict):
                    for key, bucket in (
                        ("pcf", pcf_iter),
                        ("rdf", rdf_iter),
                        ("tor", tor_iter),
                        ("run", run_iter),
                    ):
                        arr = no_rs.get(key)
                        if isinstance(arr, np.ndarray) and arr.shape == r.shape:
                            bucket[0] = np.asarray(arr, dtype=float)

            for i in range(int(niter)):
                soqb, pcfb, pdfb, rdfb, torb, runb = backFT(
                    np.asarray(q, dtype=float),
                    np.asarray(r, dtype=float),
                    np.asarray(pdf_iter[i], dtype=float),
                    float(rho),
                    cut=cut,
                )
                soq_iter.append(np.asarray(soqb, dtype=float))
                pcf_iter.append(np.asarray(pcfb, dtype=float) if pcfb is not None else np.zeros_like(r, dtype=float))
                pdf_iter.append(np.asarray(pdfb, dtype=float))
                rdf_iter.append(np.asarray(rdfb, dtype=float))
                tor_iter.append(np.asarray(torb, dtype=float))
                run_iter.append(np.asarray(runb, dtype=float))

            state: dict[str, object] = {
                "context_id": context_id,
                "iterations": int(niter),
                "cut": list(cut),
                "computed_signature": computed_sig,
                "q": np.asarray(q, dtype=float),
                "r": np.asarray(r, dtype=float),
                "soq_iter": soq_iter,
                "pcf_iter": pcf_iter,
                "pdf_iter": pdf_iter,
                "rdf_iter": rdf_iter,
                "tor_iter": tor_iter,
                "run_iter": run_iter,
                "selected_plot_index": 0,
                "selected_animation_index": 0,
                # Final arrays for the viewer:
                "pcf": pcf_iter[-1],
                "pdf": pdf_iter[-1],
                "rdf": rdf_iter[-1],
                "tor": tor_iter[-1],
                "run": run_iter[-1],
            }
            self._bft_state_store()[context_id] = state

            self._clear_bft_iterations_warning()
            self._refresh_bft_results_panel()
            if hasattr(self, "_show_success_toast"):
                self._show_success_toast("Back Fourier Transform iterations computed.")
        except Exception as exc:
            if hasattr(self, "_show_error_toast"):
                self._show_error_toast(f"Back Fourier Transform failed: {exc}")
        finally:
            self.operation_in_progress = False
            if hasattr(self, "_refresh_interaction_states"):
                try:
                    self._refresh_interaction_states()
                except Exception:
                    pass
            if hasattr(self, "_render_current_screen"):
                self._render_current_screen()
            if hasattr(self, "_end_workspace_loading"):
                self._end_workspace_loading(defer=True)
