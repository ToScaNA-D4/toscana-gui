from __future__ import annotations

from datetime import datetime
from contextlib import contextmanager
from os import chdir, getcwd
from pathlib import Path
from typing import Any

import numpy as np

from toscana.io.running_params import getRunningParams
from toscana.io.loading import read_xye
from toscana.math.fourier import getSineFT

from toscana_gui.contexts import (
    load_context_manifest,
    project_relpath,
    resolve_project_path,
    write_context_manifest,
)

from toscana_gui.ft.plots import (
    build_ft_base_gr_figure,
    build_ft_real_space_function_figure,
    build_ft_rho_fit_figure,
    build_ft_rho_fit_figure_single,
    build_ft_rho_selection_figure,
    build_ft_rho_selection_figure_single,
    build_ft_soq_figure,
    update_ft_rho_fit_figure_single,
    update_ft_rho_selection_figure_single,
)


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


class FTControllerMixin:
    _FT_BLUE_LINE = "rgba(37, 99, 235, 0.90)"
    _FT_RED_LINE = "rgba(255, 0, 0, 0.82)"

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

    @staticmethod
    def _ft_real_space_plot_specs() -> list[dict[str, str]]:
        return [
            {
                "key": "pcf",
                "title": "Pair Correlation Function",
                "latex": "G(R)",
                "yaxis": "G(R)",
            },
            {
                "key": "pdf",
                "title": "Pair Distribution Function",
                "latex": "g(R)",
                "yaxis": "g(R)",
            },
            {
                "key": "rdf",
                "title": "Radial Distribution Function",
                "latex": "RDF(R)",
                "yaxis": "RDF(R)",
            },
            {
                "key": "tor",
                "title": "Linearised Radial Distribution Function",
                "latex": "T(R)",
                "yaxis": "T(R)",
            },
            {
                "key": "run",
                "title": "Running integral of RDF(R)",
                "latex": r"\int_0^R RDF(r)\,dr",
                "yaxis": "Running integral",
            },
        ]

    @staticmethod
    def _ft_real_space_default_state() -> dict[str, object]:
        return {
            "selected_series": "no_lorch",
            "selected_plot_index": 0,
            "computed_signature": "",
            "series_data": {},
        }

    @staticmethod
    def _ft_real_space_series_label(series: str) -> str:
        return "Lorch" if str(series) == "lorch" else "No Lorch"

    def _ft_real_space_set_disabled_ui(self, *, reason: str) -> None:
        if hasattr(self, "ft_real_space_plot_view_label"):
            try:
                self.ft_real_space_plot_view_label.object = str(reason)
            except Exception:
                pass
        for name in (
            "ft_real_space_prev_block_button",
            "ft_real_space_next_block_button",
            "ft_real_space_prev_plot_button",
            "ft_real_space_next_plot_button",
        ):
            btn = getattr(self, name, None)
            if btn is not None:
                try:
                    btn.disabled = True
                except Exception:
                    pass
        export_btn = getattr(self, "ft_real_space_export_button", None)
        if export_btn is not None:
            try:
                export_btn.disabled = True
            except Exception:
                pass
        if hasattr(self, "ft_real_space_export_prompt"):
            try:
                self.ft_real_space_export_prompt.visible = False
            except Exception:
                pass
        if hasattr(self, "_sync_ft_real_space_export_prompt_visibility"):
            try:
                self._sync_ft_real_space_export_prompt_visibility()
            except Exception:
                pass
        if hasattr(self, "ft_real_space_plot_pane"):
            try:
                self.ft_real_space_plot_pane.object = None
            except Exception:
                pass

    def _refresh_ft_real_space_view(self, state: dict[str, object] | None = None) -> None:
        if state is None:
            state = getattr(self, "_ft_rho_state", None)
        if not isinstance(state, dict):
            self._ft_real_space_set_disabled_ui(reason="Real-space functions are not available yet.")
            return

        base = getattr(self, "_ft_base_gr_current", None)
        if not isinstance(base, dict):
            self._ft_real_space_set_disabled_ui(reason="Load FT data first to compute real-space functions.")
            return

        context_id = str(base.get("context_id") or "").strip()
        selection = state.get("rho_selection") if isinstance(state.get("rho_selection"), dict) else {}
        confirmed = bool(selection.get("confirmed", False))
        real_space = state.get("real_space") if isinstance(state.get("real_space"), dict) else None
        if not isinstance(real_space, dict):
            real_space = self._ft_real_space_default_state()
            state["real_space"] = real_space
            self._ft_rho_state = state

        specs = self._ft_real_space_plot_specs()
        n_plots = len(specs)
        series = str(real_space.get("selected_series") or "no_lorch")
        if series not in ("no_lorch", "lorch"):
            series = "no_lorch"
        plot_index = int(real_space.get("selected_plot_index") or 0)
        plot_index = max(0, min(plot_index, n_plots - 1))
        real_space["selected_series"] = series
        real_space["selected_plot_index"] = plot_index
        state["real_space"] = real_space
        self._ft_rho_state = state

        series_label = self._ft_real_space_series_label(series)
        if hasattr(self, "ft_real_space_block_view_label"):
            try:
                self.ft_real_space_block_view_label.object = f"Currently Viewing {series_label}"
            except Exception:
                pass

        if not confirmed:
            self._ft_real_space_set_disabled_ui(reason="Confirm Effective Atomic Density to compute real-space functions.")
            return

        series_data = real_space.get("series_data") if isinstance(real_space.get("series_data"), dict) else {}
        series_block = series_data.get(series) if isinstance(series_data.get(series), dict) else None
        if not isinstance(series_block, dict):
            self._ft_real_space_set_disabled_ui(reason="Real-space functions not computed yet. Click Confirm to compute.")
            return

        spec = specs[plot_index]
        key = str(spec.get("key") or "")
        title = str(spec.get("title") or "")
        latex = str(spec.get("latex") or "")
        if hasattr(self, "ft_real_space_plot_view_label"):
            try:
                title_html = _html_escape(title)
                latex_html = _html_escape(latex)
                self.ft_real_space_plot_view_label.object = (
                    "<div style=\"text-align: center;\">"
                    f"Currently Viewing: {title_html} \\({latex_html}\\) &mdash; Plot {plot_index + 1}/{n_plots}"
                    "</div>"
                )
            except Exception:
                pass

        x = np.asarray(series_block.get("r", []), dtype=float)
        y = np.asarray(series_block.get(key, []), dtype=float)
        if x.size == 0 or y.size == 0:
            self._ft_real_space_set_disabled_ui(reason="No real-space data available to plot.")
            return

        color = self._FT_RED_LINE if series == "lorch" else self._FT_BLUE_LINE
        try:
            self.ft_real_space_plot_pane.object = build_ft_real_space_function_figure(
                x,
                y,
                series_label=series_label,
                xaxis_title="R",
                yaxis_title=str(spec.get("yaxis") or ""),
                line_color=color,
                context_id=context_id,
            )
        except Exception:
            try:
                self.ft_real_space_plot_pane.object = None
            except Exception:
                pass

        can_interact = not bool(getattr(self, "operation_in_progress", False))
        export_button = getattr(self, "ft_real_space_export_button", None)
        if export_button is not None:
            can_export = False
            try:
                selection = state.get("rho_selection") if isinstance(state.get("rho_selection"), dict) else {}
                confirmed = bool(selection.get("confirmed", False))
                real_space = state.get("real_space") if isinstance(state.get("real_space"), dict) else {}
                series_data = real_space.get("series_data") if isinstance(real_space.get("series_data"), dict) else {}
                no_block = series_data.get("no_lorch") if isinstance(series_data.get("no_lorch"), dict) else None
                lorch_block = series_data.get("lorch") if isinstance(series_data.get("lorch"), dict) else None
                if confirmed and isinstance(no_block, dict) and isinstance(lorch_block, dict):
                    for block in (no_block, lorch_block):
                        rr = block.get("r")
                        ok = isinstance(rr, np.ndarray) and rr.size > 0
                        for key in ("pcf", "pdf", "rdf", "tor", "run"):
                            arr = block.get(key)
                            ok = ok and isinstance(arr, np.ndarray) and isinstance(rr, np.ndarray) and arr.shape == rr.shape
                        can_export = bool(ok)
                        if not can_export:
                            break
            except Exception:
                can_export = False
            try:
                export_button.disabled = (not can_export) or (not can_interact)
            except Exception:
                pass

        prev_block = getattr(self, "ft_real_space_prev_block_button", None)
        next_block = getattr(self, "ft_real_space_next_block_button", None)
        prev_plot = getattr(self, "ft_real_space_prev_plot_button", None)
        next_plot = getattr(self, "ft_real_space_next_plot_button", None)
        if prev_block is not None:
            try:
                prev_block.disabled = (not can_interact) or series == "no_lorch"
            except Exception:
                pass
        if next_block is not None:
            try:
                next_block.disabled = (not can_interact) or series == "lorch"
            except Exception:
                pass
        if prev_plot is not None:
            try:
                prev_plot.disabled = (not can_interact) or plot_index <= 0
            except Exception:
                pass
        if next_plot is not None:
            try:
                next_plot.disabled = (not can_interact) or plot_index >= (n_plots - 1)
            except Exception:
                pass

        confirm = getattr(self, "ft_real_space_export_confirm_button", None)
        cancel = getattr(self, "ft_real_space_export_cancel_button", None)
        if confirm is not None:
            try:
                confirm.disabled = bool(getattr(self, "operation_in_progress", False))
            except Exception:
                pass
        if cancel is not None:
            try:
                cancel.disabled = bool(getattr(self, "operation_in_progress", False))
            except Exception:
                pass

    def _sync_ft_real_space_export_prompt_visibility(self) -> None:
        if not hasattr(self, "ft_real_space_export_prompt_card"):
            return
        prompt = getattr(self, "ft_real_space_export_prompt", None)
        visible = bool(getattr(prompt, "visible", False)) if prompt is not None else False
        try:
            self.ft_real_space_export_prompt_card.visible = visible
        except Exception:
            pass

    def _prompt_ft_real_space_export(self, _event=None) -> None:
        if self.current_project_root is None or self.current_project_state is None:
            return
        prompt = getattr(self, "ft_real_space_export_prompt", None)
        if prompt is None:
            return
        if bool(getattr(prompt, "visible", False)):
            prompt.visible = False
            self._sync_ft_real_space_export_prompt_visibility()
            return

        state = getattr(self, "_ft_rho_state", None)
        if not isinstance(state, dict):
            if hasattr(self, "_show_warning_toast"):
                self._show_warning_toast("Real-space functions not ready. Confirm Effective Atomic Density first.")
            return
        selection = state.get("rho_selection") if isinstance(state.get("rho_selection"), dict) else {}
        if not bool(selection.get("confirmed", False)):
            if hasattr(self, "_show_warning_toast"):
                self._show_warning_toast("Confirm Effective Atomic Density first to export.")
            return

        context_id = str(state.get("context_id") or "").strip()
        if not context_id:
            if hasattr(self, "_show_warning_toast"):
                self._show_warning_toast("Select a context first.")
            return

        manifest_ref = self._selected_ft_manifest_ref()
        payload = load_context_manifest(self.current_project_root, manifest_ref) if manifest_ref else None
        payload = payload if isinstance(payload, dict) else None
        sample = payload.get("sample") if isinstance(payload, dict) else {}
        sample_title = str(sample.get("title") or "").strip() if isinstance(sample, dict) else ""
        stem = self._sanitize_export_filename_stem(sample_title or context_id)

        filename_no = f"{stem}_RSF_NoLorch.dat"
        filename_l = f"{stem}_RSF_Lorch.dat"
        target_dir = self.current_project_root / "processed" / "ft" / context_id
        target_no = target_dir / filename_no
        target_l = target_dir / filename_l

        rel_no = project_relpath(self.current_project_root, target_no)
        rel_l = project_relpath(self.current_project_root, target_l)

        lines = [
            "Proceeding will write (or overwrite) Real Space Function exports:",
            "",
            f"No Lorch: `{rel_no}` \n",
            f"Lorch: `{rel_l}`",
        ]
        overwrite = target_no.exists() or target_l.exists()
        prompt.alert_type = "warning" if overwrite else "secondary"
        if overwrite:
            lines.append("")
            lines.append("Warning: one or more files already exist and will be overwritten.")
        prompt.object = "\n".join(lines)
        prompt.visible = True
        self._sync_ft_real_space_export_prompt_visibility()

    def _cancel_ft_real_space_export(self, _event=None) -> None:
        if hasattr(self, "ft_real_space_export_prompt"):
            try:
                self.ft_real_space_export_prompt.visible = False
            except Exception:
                pass
        self._sync_ft_real_space_export_prompt_visibility()

    def _confirm_ft_real_space_export(self, _event=None) -> None:
        self._perform_ft_real_space_export()

    def _perform_ft_real_space_export(self) -> None:
        if self.current_project_root is None or self.current_project_state is None:
            return
        if getattr(self, "operation_in_progress", False):
            return

        state = getattr(self, "_ft_rho_state", None)
        if not isinstance(state, dict):
            if hasattr(self, "_show_warning_toast"):
                self._show_warning_toast("Real-space functions not ready.")
            return

        context_id = str(state.get("context_id") or "").strip()
        if not context_id:
            if hasattr(self, "_show_warning_toast"):
                self._show_warning_toast("Select a context first.")
            return

        selection = state.get("rho_selection") if isinstance(state.get("rho_selection"), dict) else {}
        if not bool(selection.get("confirmed", False)):
            if hasattr(self, "_show_warning_toast"):
                self._show_warning_toast("Confirm Effective Atomic Density first.")
            return

        real_space = state.get("real_space") if isinstance(state.get("real_space"), dict) else {}
        series_data = real_space.get("series_data") if isinstance(real_space.get("series_data"), dict) else {}
        no_block = series_data.get("no_lorch") if isinstance(series_data.get("no_lorch"), dict) else None
        l_block = series_data.get("lorch") if isinstance(series_data.get("lorch"), dict) else None
        if not (isinstance(no_block, dict) and isinstance(l_block, dict)):
            if hasattr(self, "_show_warning_toast"):
                self._show_warning_toast("No real-space data available to export.")
            return

        def _rho_from(series_key: str) -> float | None:
            snap = selection.get("confirmed_snapshot") if isinstance(selection.get("confirmed_snapshot"), dict) else None
            block = snap.get(series_key) if isinstance(snap, dict) and isinstance(snap.get(series_key), dict) else {}
            value = block.get("chosen_rho")
            try:
                rho_val = float(value)
            except Exception:
                return None
            return float(rho_val) if np.isfinite(rho_val) and rho_val > 0 else None

        rho_no = _rho_from("no_lorch")
        rho_l = _rho_from("lorch")
        if rho_no is None or rho_l is None:
            if hasattr(self, "_show_warning_toast"):
                self._show_warning_toast("Effective Atomic Density missing; cannot export.")
            return

        manifest_ref = self._selected_ft_manifest_ref()
        payload = load_context_manifest(self.current_project_root, manifest_ref) if manifest_ref else None
        payload = payload if isinstance(payload, dict) else None
        sample = payload.get("sample") if isinstance(payload, dict) else {}
        sample_title = str(sample.get("title") or "").strip() if isinstance(sample, dict) else ""
        par_ref = ""
        if isinstance(sample, dict):
            par_ref = str(sample.get("par_path_rel") or sample.get("par_path") or "").strip()

        base = getattr(self, "_ft_base_gr_current", None)
        soq_rel = ""
        if isinstance(base, dict) and isinstance(base.get("soq_path"), (str, Path)):
            try:
                soq_path = Path(base.get("soq_path")) if isinstance(base.get("soq_path"), str) else base.get("soq_path")
                soq_rel = project_relpath(self.current_project_root, soq_path)
            except Exception:
                soq_rel = str(base.get("soq_path") or "")
        elif isinstance(payload, dict):
            artifacts = payload.get("artifacts") if isinstance(payload.get("artifacts"), dict) else {}
            soq_ref = artifacts.get("static_structure_factor_qdat") if isinstance(artifacts.get("static_structure_factor_qdat"), str) else ""
            if isinstance(soq_ref, str) and soq_ref.strip():
                try:
                    soq_path = resolve_project_path(self.current_project_root, soq_ref)
                    soq_rel = project_relpath(self.current_project_root, soq_path)
                except Exception:
                    soq_rel = soq_ref

        stem = self._sanitize_export_filename_stem(sample_title or context_id)
        filename_no = f"{stem}_RSF_NoLorch.dat"
        filename_l = f"{stem}_RSF_Lorch.dat"

        # Record in run history (best-effort).
        run_record = None
        try:
            from toscana_gui.persistence import OutputPaths, RunRecord, now_iso

            run_id = None
            if hasattr(self, "_create_run_id"):
                run_id = str(self._create_run_id())
            run_record = RunRecord(
                run_id=run_id or f"ft-rsf-{now_iso()}",
                workflow="ft_real_space_export",
                status="running",
                started_at=now_iso(),
                summary=f"Exporting real-space functions for context `{context_id}`",
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

            target_dir = self.current_project_root / "processed" / "ft" / context_id
            target_dir.mkdir(parents=True, exist_ok=True)
            target_no = target_dir / filename_no
            target_l = target_dir / filename_l

            def _arrays(block: dict[str, object]) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
                rr = np.asarray(block.get("r"), dtype=float)
                pcf = np.asarray(block.get("pcf"), dtype=float)
                pdf = np.asarray(block.get("pdf"), dtype=float)
                rdf = np.asarray(block.get("rdf"), dtype=float)
                tor = np.asarray(block.get("tor"), dtype=float)
                run = np.asarray(block.get("run"), dtype=float)
                if not (rr.shape == pcf.shape == pdf.shape == rdf.shape == tor.shape == run.shape):
                    raise RuntimeError("Shape mismatch in real-space arrays.")
                return rr, pcf, pdf, rdf, tor, run

            rr_no, pcf_no, pdf_no, rdf_no, tor_no, run_no = _arrays(no_block)
            rr_l, pcf_l, pdf_l, rdf_l, tor_l, run_l = _arrays(l_block)

            try:
                from toscana_gui.persistence import now_iso

                timestamp = now_iso()
            except Exception:
                timestamp = datetime.now().isoformat()

            def _write_dat(
                path: Path,
                *,
                series_label: str,
                rho: float,
                r: np.ndarray,
                pcf: np.ndarray,
                pdf: np.ndarray,
                rdf: np.ndarray,
                tor: np.ndarray,
                run: np.ndarray,
            ) -> None:
                header_lines = [
                    f"# {str(path)}",
                    f"# timestamp: {timestamp}",
                    f"# context_id: {context_id}",
                    f"# sample_title: {sample_title}",
                    f"# series: {series_label}",
                    f"# rho_effective_atomic_density: {rho:.12g}",
                    f"# source_static_structure_factor_qdat: {soq_rel}",
                    f"# source_par_file: {par_ref}",
                    "# Real space functions",
                    "# R (A)               G(R)               g(R)              RDF(R)               T(R)     Int_0^R_RDF(r)dr",
                ]
                with path.open("w", encoding="utf-8", newline="\n") as handle:
                    handle.write("\n".join(header_lines) + "\n")
                    for i in range(int(r.size)):
                        handle.write(
                            "{: 12.6f} {: 18.6f} {: 18.6f} {: 18.6f} {: 18.6f} {: 18.6f}\n".format(
                                float(r[i]),
                                float(pcf[i]),
                                float(pdf[i]),
                                float(rdf[i]),
                                float(tor[i]),
                                float(run[i]),
                            )
                        )

            _write_dat(
                target_no,
                series_label="No Lorch",
                rho=float(rho_no),
                r=rr_no,
                pcf=pcf_no,
                pdf=pdf_no,
                rdf=rdf_no,
                tor=tor_no,
                run=run_no,
            )
            _write_dat(
                target_l,
                series_label="Lorch",
                rho=float(rho_l),
                r=rr_l,
                pcf=pcf_l,
                pdf=pdf_l,
                rdf=rdf_l,
                tor=tor_l,
                run=run_l,
            )

            # Persist artifact references.
            if isinstance(payload, dict):
                artifacts = payload.get("artifacts") if isinstance(payload.get("artifacts"), dict) else {}
                artifacts["ft_real_space_no_lorch_dat"] = project_relpath(self.current_project_root, target_no)
                artifacts["ft_real_space_lorch_dat"] = project_relpath(self.current_project_root, target_l)
                payload["artifacts"] = artifacts
                try:
                    write_context_manifest(self.current_project_root, context_id=context_id, payload=payload)
                except Exception:
                    pass

            if run_record is not None:
                try:
                    from toscana_gui.persistence import now_iso

                    run_record.status = "succeeded"
                    run_record.finished_at = now_iso()
                    run_record.summary = f"Exported `{filename_no}` / `{filename_l}`"
                    run_record.output_paths.generated_files = [
                        project_relpath(self.current_project_root, target_no),
                        project_relpath(self.current_project_root, target_l),
                    ]
                    if hasattr(self.current_project_state, "project") and hasattr(self.current_project_state.project, "updated_at"):
                        self.current_project_state.project.updated_at = now_iso()  # type: ignore[assignment]
                    if hasattr(self, "_persist_current_project_state"):
                        self._persist_current_project_state()
                except Exception:
                    pass

            if hasattr(self, "_show_success_toast"):
                self._show_success_toast("Exported Real Space Function files.")
            if hasattr(self, "ft_real_space_export_prompt"):
                try:
                    self.ft_real_space_export_prompt.visible = False
                except Exception:
                    pass
                self._sync_ft_real_space_export_prompt_visibility()
        except Exception as exc:
            if hasattr(self, "_show_error_toast"):
                self._show_error_toast(f"Export failed: {exc}")
            if run_record is not None:
                try:
                    from toscana_gui.persistence import now_iso

                    run_record.status = "failed"
                    run_record.finished_at = now_iso()
                    run_record.summary = f"Export failed: {exc}"
                    if hasattr(self, "_persist_current_project_state"):
                        self._persist_current_project_state()
                except Exception:
                    pass
        finally:
            self.operation_in_progress = False
            if hasattr(self, "_refresh_interaction_states"):
                try:
                    self._refresh_interaction_states()
                except Exception:
                    pass
            try:
                self._refresh_ft_real_space_view()
            except Exception:
                pass

    def _compute_ft_real_space_functions_from_confirmed_selection(self, state: dict[str, object]) -> None:
        base = getattr(self, "_ft_base_gr_current", None)
        if not isinstance(base, dict):
            return
        selection = state.get("rho_selection") if isinstance(state.get("rho_selection"), dict) else None
        if not isinstance(selection, dict) or not bool(selection.get("confirmed", False)):
            return
        snap = selection.get("confirmed_snapshot") if isinstance(selection.get("confirmed_snapshot"), dict) else None
        if not isinstance(snap, dict):
            return

        base_signature = str(base.get("signature") or "")
        context_id = str(base.get("context_id") or "")
        r = np.asarray(base.get("r"), dtype=float)
        gr = np.asarray(base.get("gr"), dtype=float)
        gr_lorch = np.asarray(base.get("gr_lorch"), dtype=float)
        if r.size == 0:
            return
        order = np.argsort(r)
        r = r[order]
        if gr.shape == r.shape:
            gr = gr[order]
        if gr_lorch.shape == r.shape:
            gr_lorch = gr_lorch[order]

        def _rho_from(series_key: str) -> float | None:
            block = snap.get(series_key) if isinstance(snap.get(series_key), dict) else {}
            value = block.get("chosen_rho")
            try:
                rho_val = float(value)
            except Exception:
                return None
            return float(rho_val) if np.isfinite(rho_val) and rho_val > 0 else None

        rho_no = _rho_from("no_lorch")
        rho_l = _rho_from("lorch")
        if rho_no is None or rho_l is None:
            return

        computed_sig = f"{base_signature}:{rho_no:.12g}:{rho_l:.12g}"
        real_space = state.get("real_space") if isinstance(state.get("real_space"), dict) else None
        if not isinstance(real_space, dict):
            real_space = self._ft_real_space_default_state()
        if str(real_space.get("computed_signature") or "") == computed_sig and isinstance(real_space.get("series_data"), dict):
            state["real_space"] = real_space
            self._ft_rho_state = state
            return

        def _safe_ratio(num: np.ndarray, denom: np.ndarray) -> np.ndarray:
            out = np.zeros_like(num, dtype=float)
            mask = np.isfinite(num) & np.isfinite(denom) & (denom != 0.0)
            if mask.any():
                out[mask] = num[mask] / denom[mask]
            return out

        def _running_integral(x: np.ndarray, y: np.ndarray) -> np.ndarray:
            x = np.asarray(x, dtype=float)
            y = np.asarray(y, dtype=float)
            if x.size == 0 or y.size == 0:
                return np.zeros_like(x, dtype=float)
            try:
                from scipy import integrate  # type: ignore

                if hasattr(integrate, "cumulative_trapezoid"):
                    c = integrate.cumulative_trapezoid(y, x, initial=0.0)
                    return np.asarray(c, dtype=float)
            except Exception:
                pass
            dx = np.diff(x)
            avg = 0.5 * (y[1:] + y[:-1])
            run = np.zeros_like(x, dtype=float)
            if dx.size:
                run[1:] = np.cumsum(avg * dx)
            return run

        def _compute_for(series_key: str, *, pcf: np.ndarray, rho: float) -> dict[str, object]:
            denom = 4.0 * float(np.pi) * float(rho) * r
            pdf = 1.0 + _safe_ratio(pcf, denom)
            rdf = 4.0 * float(np.pi) * float(rho) * (r * r) * pdf
            tor = _safe_ratio(rdf, r)
            run = _running_integral(r, rdf)
            return {
                "context_id": context_id,
                "signature": computed_sig,
                "r": r,
                "pcf": pcf,
                "pdf": pdf,
                "rdf": rdf,
                "tor": tor,
                "run": run,
            }

        series_data = {
            "no_lorch": _compute_for("no_lorch", pcf=gr, rho=float(rho_no)),
            "lorch": _compute_for("lorch", pcf=gr_lorch, rho=float(rho_l)),
        }

        real_space["series_data"] = series_data
        real_space["computed_signature"] = computed_sig
        real_space["selected_series"] = "no_lorch"
        real_space["selected_plot_index"] = 0
        state["real_space"] = real_space
        self._ft_rho_state = state

    def _on_ft_real_space_prev_block(self, _event=None) -> None:
        if bool(getattr(self, "operation_in_progress", False)):
            return
        state = getattr(self, "_ft_rho_state", None)
        if not isinstance(state, dict):
            return
        real_space = state.get("real_space") if isinstance(state.get("real_space"), dict) else None
        if not isinstance(real_space, dict):
            return
        if str(real_space.get("selected_series") or "no_lorch") == "lorch":
            real_space["selected_series"] = "no_lorch"
            state["real_space"] = real_space
            self._ft_rho_state = state
            self._refresh_ft_real_space_view(state)

    def _on_ft_real_space_next_block(self, _event=None) -> None:
        if bool(getattr(self, "operation_in_progress", False)):
            return
        state = getattr(self, "_ft_rho_state", None)
        if not isinstance(state, dict):
            return
        real_space = state.get("real_space") if isinstance(state.get("real_space"), dict) else None
        if not isinstance(real_space, dict):
            return
        if str(real_space.get("selected_series") or "no_lorch") == "no_lorch":
            real_space["selected_series"] = "lorch"
            state["real_space"] = real_space
            self._ft_rho_state = state
            self._refresh_ft_real_space_view(state)

    def _on_ft_real_space_prev_plot(self, _event=None) -> None:
        if bool(getattr(self, "operation_in_progress", False)):
            return
        state = getattr(self, "_ft_rho_state", None)
        if not isinstance(state, dict):
            return
        real_space = state.get("real_space") if isinstance(state.get("real_space"), dict) else None
        if not isinstance(real_space, dict):
            return
        idx = int(real_space.get("selected_plot_index") or 0)
        idx = max(0, idx - 1)
        real_space["selected_plot_index"] = idx
        state["real_space"] = real_space
        self._ft_rho_state = state
        self._refresh_ft_real_space_view(state)

    def _on_ft_real_space_next_plot(self, _event=None) -> None:
        if bool(getattr(self, "operation_in_progress", False)):
            return
        state = getattr(self, "_ft_rho_state", None)
        if not isinstance(state, dict):
            return
        real_space = state.get("real_space") if isinstance(state.get("real_space"), dict) else None
        if not isinstance(real_space, dict):
            return
        max_idx = len(self._ft_real_space_plot_specs()) - 1
        idx = int(real_space.get("selected_plot_index") or 0)
        idx = min(max_idx, idx + 1)
        real_space["selected_plot_index"] = idx
        state["real_space"] = real_space
        self._ft_rho_state = state
        self._refresh_ft_real_space_view(state)

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

    def _reset_ft_runtime_state(self) -> None:
        self._ft_soq_cache = {}
        self._ft_soq_current = None
        self._ft_soq_selected_path = None
        self._ft_base_gr_current = None
        self._ft_rho_state = None

    @contextmanager
    def _working_directory(self, target: Path):
        original = Path(getcwd())
        chdir(str(target))
        try:
            yield
        finally:
            chdir(str(original))

    @staticmethod
    def _ft_view_toggle_label(view_mode: str) -> str:
        return (
            "Show Static Structure Factor"
            if str(view_mode or "gr") == "gr"
            else "Show Pair Correlation Function G(R)"
        )

    def _set_ft_view_toggle_label(self) -> None:
        snapshot = getattr(self, "_ft_base_gr_current", None)
        view_mode = str(snapshot.get("view_mode") if isinstance(snapshot, dict) else "gr")
        label = self._ft_view_toggle_label(view_mode)
        if hasattr(self, "ft_view_label"):
            try:
                self.ft_view_label.object = label
            except Exception:
                pass

    def _load_ft_state_into_widgets(self) -> None:
        if self.current_project_state is None or self.current_project_root is None:
            return
        if not hasattr(self, "ft_context_select"):
            return
        self._refresh_ft_context_options(apply_selection=True)
        self._refresh_ft_context_summary()
        self._load_ft_soq_series()
        self._refresh_ft_base_gr_panel()
        self._refresh_ft_effective_atomic_density_panel()

    def _get_ft_context_entries(self) -> list[dict[str, Any]]:
        if self.current_project_state is None:
            return []
        if hasattr(self, "_get_background_state"):
            state = self._get_background_state()
        else:
            state = getattr(self.current_project_state, "background", {}) or {}
        contexts = state.get("contexts") if isinstance(state.get("contexts"), dict) else {}
        entries = contexts.get("entries") if isinstance(contexts.get("entries"), list) else []
        return [e for e in entries if isinstance(e, dict)]

    def _selected_ft_manifest_ref(self) -> str:
        selected = str(getattr(getattr(self, "ft_context_select", None), "value", "") or "").strip()
        if not selected:
            return ""
        entry = next((e for e in self._get_ft_context_entries() if str(e.get("context_id") or "").strip() == selected), None)
        if not isinstance(entry, dict):
            return ""
        return str(entry.get("manifest") or "").strip()

    def _refresh_ft_context_options(self, *, apply_selection: bool) -> None:
        if self.current_project_state is None or self.current_project_root is None:
            return
        if not hasattr(self, "ft_context_select"):
            return

        entries = self._get_ft_context_entries()
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
            self.ft_context_select.options = options
            self.ft_context_select.value = ""
            self.ft_context_select.disabled = True
            if hasattr(self, "ft_context_message"):
                self.ft_context_message.object = "No background contexts are available yet. Run **Background → Export Data** first."
                self.ft_context_message.alert_type = "warning"
            return

        self.ft_context_select.disabled = False
        self.ft_context_select.options = options

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

        self._suspend_ft_events = True
        try:
            self.ft_context_select.value = selected
        finally:
            self._suspend_ft_events = False

    def _refresh_ft_context_summary(self) -> None:
        if self.current_project_root is None:
            return
        if not hasattr(self, "ft_context_message") or not hasattr(self, "ft_context_info_hover") or not hasattr(
            self, "ft_context_summary"
        ):
            return

        selected = str(getattr(getattr(self, "ft_context_select", None), "value", "") or "").strip()
        if not selected:
            self.ft_context_summary.object = ""
            self.ft_context_info_hover.value = ""
            self.ft_context_message.object = "Select a context to proceed. Contexts are created by **Background → Export Data**."
            self.ft_context_message.alert_type = "secondary"
            self._ft_soq_selected_path = None
            return

        manifest_ref = self._selected_ft_manifest_ref()
        if not manifest_ref:
            self.ft_context_summary.object = ""
            self.ft_context_info_hover.value = ""
            self.ft_context_message.object = "Selected context has no manifest path."
            self.ft_context_message.alert_type = "danger"
            self._ft_soq_selected_path = None
            return

        payload = load_context_manifest(self.current_project_root, manifest_ref)
        if payload is None:
            manifest_path = resolve_project_path(self.current_project_root, manifest_ref)
            self.ft_context_summary.object = ""
            self.ft_context_info_hover.value = ""
            self.ft_context_message.object = f"Context manifest could not be loaded: `{manifest_path}`"
            self.ft_context_message.alert_type = "danger"
            self._ft_soq_selected_path = None
            return

        artifacts = payload.get("artifacts") if isinstance(payload.get("artifacts"), dict) else {}
        soq_ref = artifacts.get("static_structure_factor_qdat") if isinstance(artifacts.get("static_structure_factor_qdat"), str) else None
        if not isinstance(soq_ref, str) or not soq_ref.strip():
            self.ft_context_message.object = "This context has no `SOQ_qdat`. Run **Self → Export Static Structure Factor** for this context."
            self.ft_context_message.alert_type = "warning"
            soq_path = None
        else:
            try:
                soq_path = resolve_project_path(self.current_project_root, soq_ref)
            except Exception:
                soq_path = None
                self.ft_context_message.object = "The `SOQ_qdat` reference could not be resolved."
                self.ft_context_message.alert_type = "danger"

        self._ft_soq_selected_path = soq_path

        self.ft_context_summary.object = ""

        def _code(val: object) -> str:
            return f"<code style=\"overflow-wrap:anywhere; word-break:break-word;\">{_html_escape(val)}</code>"

        sample = payload.get("sample") if isinstance(payload.get("sample"), dict) else {}
        sample_title = str(sample.get("title") or "").strip()
        par_rel = str(sample.get("par_path_rel") or "").strip()
        body_lines = [
            f"<div><strong>Context id:</strong> {_code(selected)}</div>",
            f"<div><strong>Sample title:</strong> {_html_escape(sample_title) if sample_title else _code('')}</div>",
            f"<div><strong>Par (rel):</strong> {_code(par_rel)}</div>",
            f"<div><strong>SOQ_qdat:</strong> {_code(project_relpath(self.current_project_root, soq_path) if isinstance(soq_path, Path) else '')}</div>",
        ]
        self.ft_context_info_hover.value = (
            "<div style=\"max-width: 420px; line-height: 1.6; overflow-wrap:anywhere; word-break:break-word;\">"
            + "".join(body_lines)
            + "</div>"
        )

        if soq_path is not None:
            if soq_path.exists():
                self.ft_context_message.object = "Context ready for FT."
                self.ft_context_message.alert_type = "success"
            else:
                self.ft_context_message.object = f"`SOQ_qdat` not found on disk: `{soq_path}`"
                self.ft_context_message.alert_type = "warning"

    def _on_ft_context_change(self, event) -> None:
        if getattr(self, "_suspend_ft_events", False) or self.current_project_state is None:
            return
        if event.new == event.old:
            return

        context_id = str(event.new or "").strip()
        if not context_id:
            return

        if hasattr(self, "_get_background_state") and hasattr(self, "_persist_background_state"):
            state = self._get_background_state()
            contexts = state.get("contexts") if isinstance(state.get("contexts"), dict) else {}
            contexts["active_context_id"] = context_id
            state["contexts"] = contexts
            self._persist_background_state(state)

        self._refresh_ft_context_summary()
        self._load_ft_soq_series()
        self._refresh_ft_base_gr_panel()
        self._refresh_ft_effective_atomic_density_panel()
        if hasattr(self, "_refresh_interaction_states"):
            self._refresh_interaction_states()
        if hasattr(self, "_render_current_screen"):
            self._render_current_screen()

    def _read_ft_soq_xye_cached(self, path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        cache = getattr(self, "_ft_soq_cache", None)
        if not isinstance(cache, dict):
            cache = {}
            self._ft_soq_cache = cache

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

    def _load_ft_soq_series(self) -> None:
        if self.current_project_root is None:
            return
        context_id = str(getattr(getattr(self, "ft_context_select", None), "value", "") or "").strip()
        path = getattr(self, "_ft_soq_selected_path", None)
        if not context_id or not isinstance(path, Path) or not path.exists() or not path.is_file():
            self._ft_soq_current = None
            return

        q, soq, err = self._read_ft_soq_xye_cached(path)
        self._ft_soq_current = {
            "context_id": context_id,
            "path": str(path.resolve(strict=False)),
            "q": q,
            "soq": soq,
            "err": err,
        }

    def _refresh_ft_base_gr_panel(self) -> None:
        if self.current_project_root is None:
            return
        if not hasattr(self, "ft_title_plot_pane"):
            return

        soq_current = getattr(self, "_ft_soq_current", None)
        if not isinstance(soq_current, dict):
            self._ft_base_gr_current = None
            self.ft_title_plot_pane.object = None
            if hasattr(self, "ft_view_switch"):
                self.ft_view_switch.disabled = True
                self.ft_view_switch.value = False
            return

        context_id = str(soq_current.get("context_id") or "").strip()
        soq_path = str(soq_current.get("path") or "").strip()
        q = np.asarray(soq_current.get("q"), dtype=float)
        soq = np.asarray(soq_current.get("soq"), dtype=float)
        err = np.asarray(soq_current.get("err"), dtype=float)
        if not context_id or not soq_path or q.size == 0 or soq.size == 0:
            self._ft_base_gr_current = None
            self.ft_title_plot_pane.object = None
            if hasattr(self, "ft_view_switch"):
                self.ft_view_switch.disabled = True
                self.ft_view_switch.value = False
            return

        manifest_ref = self._selected_ft_manifest_ref()
        payload = load_context_manifest(self.current_project_root, manifest_ref) if manifest_ref else None
        sample = payload.get("sample") if isinstance(payload, dict) else {}
        par_rel = str(sample.get("par_path_rel") or "").strip() if isinstance(sample, dict) else ""
        if not par_rel:
            if hasattr(self, "ft_context_message"):
                self.ft_context_message.object = "Context manifest is missing `sample.par_path_rel`; cannot compute Base G(R)."
                self.ft_context_message.alert_type = "danger"
            self._ft_base_gr_current = None
            self.ft_title_plot_pane.object = None
            if hasattr(self, "ft_view_switch"):
                self.ft_view_switch.disabled = True
                self.ft_view_switch.value = False
            return

        try:
            par_path = resolve_project_path(self.current_project_root, par_rel)
        except Exception:
            par_path = None

        if par_path is None or not par_path.exists() or not par_path.is_file():
            if hasattr(self, "ft_context_message"):
                self.ft_context_message.object = f"Sample `.par` file not found for Base G(R): `{par_rel}`"
                self.ft_context_message.alert_type = "danger"
            self._ft_base_gr_current = None
            self.ft_title_plot_pane.object = None
            if hasattr(self, "ft_view_switch"):
                self.ft_view_switch.disabled = True
                self.ft_view_switch.value = False
            return

        try:
            input_par = getRunningParams(str(par_path))
            rsc = input_par.get("<rsc>") if isinstance(input_par, dict) else None
            if rsc is None:
                raise KeyError("Missing `<rsc>` in running params")
            if isinstance(rsc, (list, tuple)) and len(rsc) >= 4 and isinstance(rsc[0], str):
                r_tuple = (float(rsc[1]), float(rsc[2]), float(rsc[3]))
            elif isinstance(rsc, (list, tuple)) and len(rsc) >= 3:
                r_tuple = (float(rsc[0]), float(rsc[1]), float(rsc[2]))
            else:
                raise ValueError(f"Unsupported `<rsc>` format: {type(rsc).__name__}")
        except Exception as exc:
            if hasattr(self, "ft_context_message"):
                self.ft_context_message.object = f"Could not read rScale from `.par` for Base G(R): {exc}"
                self.ft_context_message.alert_type = "danger"
            self._ft_base_gr_current = None
            self.ft_title_plot_pane.object = None
            if hasattr(self, "ft_view_switch"):
                self.ft_view_switch.disabled = True
                self.ft_view_switch.value = False
            return

        try:
            ar = np.arange(*r_tuple, dtype=float)
        except Exception as exc:
            if hasattr(self, "ft_context_message"):
                self.ft_context_message.object = f"Invalid rScale for Base G(R): {exc}"
                self.ft_context_message.alert_type = "danger"
            self._ft_base_gr_current = None
            self.ft_title_plot_pane.object = None
            if hasattr(self, "ft_view_switch"):
                self.ft_view_switch.disabled = True
                self.ft_view_switch.value = False
            return

        if ar.size == 0:
            if hasattr(self, "ft_context_message"):
                self.ft_context_message.object = "Computed r-grid is empty; cannot compute Base G(R)."
                self.ft_context_message.alert_type = "danger"
            self._ft_base_gr_current = None
            self.ft_title_plot_pane.object = None
            if hasattr(self, "ft_view_switch"):
                self.ft_view_switch.disabled = True
                self.ft_view_switch.value = False
            return

        # Avoid division by 0 / NaN at R=0.
        if ar[0] == 0.0:
            ar[0] = 1e-6

        try:
            stat = Path(soq_path).stat()
            mtime_ns = int(getattr(stat, "st_mtime_ns", int(stat.st_mtime * 1e9)))
            size = int(stat.st_size)
        except Exception:
            mtime_ns = -1
            size = -1

        signature = f"{soq_path}:{mtime_ns}:{size}:{r_tuple!r}"
        existing = getattr(self, "_ft_base_gr_current", None)

        if isinstance(existing, dict) and existing.get("signature") == signature:
            view_mode = str(existing.get("view_mode") or "gr")
            if view_mode == "soq":
                self.ft_title_plot_pane.object = build_ft_soq_figure(q=q, soq=soq, context_id=context_id)
            else:
                self.ft_title_plot_pane.object = build_ft_base_gr_figure(
                    r=np.asarray(existing.get("r"), dtype=float),
                    gr=np.asarray(existing.get("gr"), dtype=float),
                    gr_lorch=np.asarray(existing.get("gr_lorch"), dtype=float),
                    context_id=context_id,
                )
            if hasattr(self, "ft_view_switch"):
                self.ft_view_switch.disabled = False
                desired = view_mode == "soq"
                if bool(getattr(self.ft_view_switch, "value", False)) != desired:
                    self.ft_view_switch.value = desired
            self._set_ft_view_toggle_label()
            return

        try:
            gr = getSineFT(q, soq, ar, w=0)
            gr_lorch = getSineFT(q, soq, ar, w=1)
        except Exception as exc:
            if hasattr(self, "ft_context_message"):
                self.ft_context_message.object = f"Failed to compute Base G(R): {exc}"
                self.ft_context_message.alert_type = "danger"
            self._ft_base_gr_current = None
            self.ft_title_plot_pane.object = None
            if hasattr(self, "ft_view_switch"):
                self.ft_view_switch.disabled = True
                self.ft_view_switch.value = False
            return

        if gr is None or gr_lorch is None:
            if hasattr(self, "ft_context_message"):
                self.ft_context_message.object = "Base G(R) computation returned no data."
                self.ft_context_message.alert_type = "danger"
            self._ft_base_gr_current = None
            self.ft_title_plot_pane.object = None
            if hasattr(self, "ft_view_switch"):
                self.ft_view_switch.disabled = True
                self.ft_view_switch.value = False
            return

        gr = np.asarray(gr, dtype=float)
        gr_lorch = np.asarray(gr_lorch, dtype=float)
        if gr.shape != ar.shape or gr_lorch.shape != ar.shape:
            if hasattr(self, "ft_context_message"):
                self.ft_context_message.object = "Base G(R) output shape mismatch; cannot plot."
                self.ft_context_message.alert_type = "danger"
            self._ft_base_gr_current = None
            self.ft_title_plot_pane.object = None
            if hasattr(self, "ft_view_switch"):
                self.ft_view_switch.disabled = True
                self.ft_view_switch.value = False
            return

        self._ft_base_gr_current = {
            "context_id": context_id,
            "soq_path": soq_path,
            "par_path": str(par_path.resolve(strict=False)),
            "q": q,
            "soq": soq,
            "err": err,
            "r": ar,
            "gr": gr,
            "gr_lorch": gr_lorch,
            "view_mode": "gr",
            "signature": signature,
        }

        self.ft_title_plot_pane.object = build_ft_base_gr_figure(r=ar, gr=gr, gr_lorch=gr_lorch, context_id=context_id)
        if hasattr(self, "ft_view_switch"):
            self.ft_view_switch.disabled = False
            self.ft_view_switch.value = False
        self._set_ft_view_toggle_label()

    def _on_ft_toggle_view(self, _event=None) -> None:
        switch = getattr(self, "ft_view_switch", None)
        if switch is None:
            return
        try:
            switch.value = not bool(getattr(switch, "value", False))
        except Exception:
            return

    def _on_ft_view_change(self, event) -> None:
        if getattr(self, "_suspend_ft_events", False):
            return
        snapshot = getattr(self, "_ft_base_gr_current", None)
        if not isinstance(snapshot, dict):
            return

        show_soq = bool(getattr(event, "new", False))
        next_mode = "soq" if show_soq else "gr"
        snapshot["view_mode"] = next_mode
        self._ft_base_gr_current = snapshot

        if not hasattr(self, "ft_title_plot_pane"):
            return

        try:
            if next_mode == "soq":
                fig = build_ft_soq_figure(
                    q=np.asarray(snapshot.get("q"), dtype=float),
                    soq=np.asarray(snapshot.get("soq"), dtype=float),
                    context_id=str(snapshot.get("context_id") or ""),
                )
            else:
                fig = build_ft_base_gr_figure(
                    r=np.asarray(snapshot.get("r"), dtype=float),
                    gr=np.asarray(snapshot.get("gr"), dtype=float),
                    gr_lorch=np.asarray(snapshot.get("gr_lorch"), dtype=float),
                    context_id=str(snapshot.get("context_id") or ""),
                )
            self.ft_title_plot_pane.object = fig
        except Exception:
            return

        self._set_ft_view_toggle_label()
        # Avoid full-screen re-render here; it causes a visible freeze and scroll jump.

    @staticmethod
    def _ft_rho_view_label(view: str) -> str:
        return "Switch to Run Fit" if str(view or "select") == "select" else "Switch to Selection"

    def _set_ft_rho_view_label(self, view: str) -> None:
        if hasattr(self, "ft_rho_view_label"):
            try:
                self.ft_rho_view_label.object = self._ft_rho_view_label(view)
            except Exception:
                pass

    @staticmethod
    def _ft_rho_series_label(active_series: str) -> str:
        return "Switch to G(R) No Lorch" if str(active_series or "no_lorch") == "lorch" else "Switch to G(R) Lorch"

    def _set_ft_rho_series_label(self, active_series: str) -> None:
        if hasattr(self, "ft_rho_series_label"):
            try:
                self.ft_rho_series_label.object = self._ft_rho_series_label(active_series)
            except Exception:
                pass

    def _ft_rho_fit_signature(self, *, base_signature: str, series: str, r_window: tuple[float, float]) -> str:
        return f"{base_signature}:{series}:{r_window!r}"

    def _load_ft_original_rho(self, *, payload: dict[str, object]) -> float | None:
        if self.current_project_root is None:
            return None
        sample = payload.get("sample")
        if not isinstance(sample, dict):
            return None

        def _extract_rho(measurement: object) -> float | None:
            try:
                rho = float(getattr(measurement, "EffAtomicDensity", 0.0) or 0.0)
            except Exception:
                return None
            return rho if np.isfinite(rho) and rho > 0 else None

        # Prefer persisted measurement artifact if present.
        artifact_ref = sample.get("measurement_artifact")
        if isinstance(artifact_ref, str) and artifact_ref.strip():
            try:
                artifact_path = resolve_project_path(self.current_project_root, artifact_ref)
            except Exception:
                artifact_path = None
            if isinstance(artifact_path, Path) and artifact_path.exists() and artifact_path.is_file():
                try:
                    if artifact_path.suffix.lower() == ".pkl":
                        import pickle

                        with artifact_path.open("rb") as handle:
                            loaded = pickle.load(handle)
                    else:
                        import json

                        loaded = json.loads(artifact_path.read_text(encoding="utf-8", errors="replace"))
                except Exception:
                    loaded = None

                if loaded is not None and hasattr(loaded, "EffAtomicDensity"):
                    rho = _extract_rho(loaded)
                    if rho is not None:
                        return rho

                if isinstance(loaded, dict):
                    # Rebuild Measurement in the `.par` directory so relative paths resolve deterministically.
                    par_ref = sample.get("par_path_rel") if isinstance(sample.get("par_path_rel"), str) else sample.get("par_path")
                    if isinstance(par_ref, str) and par_ref.strip():
                        try:
                            par_path = resolve_project_path(self.current_project_root, par_ref)
                        except Exception:
                            par_path = None
                    else:
                        par_path = None
                    base_dir = par_path.parent if isinstance(par_path, Path) and par_path.parent.exists() else self.current_project_root
                    try:
                        from toscana.experiment.measurement import Measurement
                    except Exception:
                        return None
                    try:
                        with self._working_directory(base_dir):
                            measurement = Measurement(loaded)
                    except Exception:
                        measurement = None
                    if measurement is not None:
                        rho = _extract_rho(measurement)
                        if rho is not None:
                            return rho

        # Fallback: rebuild from `.par` file.
        par_ref = sample.get("par_path_rel") if isinstance(sample.get("par_path_rel"), str) else sample.get("par_path")
        if not isinstance(par_ref, str) or not par_ref.strip():
            return None
        try:
            par_path = resolve_project_path(self.current_project_root, par_ref)
        except Exception:
            return None
        if not par_path.exists() or not par_path.is_file():
            return None
        try:
            from toscana.experiment.measurement import Measurement
        except Exception:
            return None
        try:
            params = getRunningParams(str(par_path))
            with self._working_directory(par_path.parent):
                measurement = Measurement(params)
        except Exception:
            return None
        return _extract_rho(measurement)

    @staticmethod
    def _ft_rho_select_window_mask(*, r: np.ndarray, y: np.ndarray, r_min: float, r_max: float) -> np.ndarray:
        r = np.asarray(r, dtype=float)
        y = np.asarray(y, dtype=float)
        lo = float(min(r_min, r_max))
        hi = float(max(r_min, r_max))
        finite = np.isfinite(r) & np.isfinite(y)
        return finite & (r >= lo) & (r <= hi)

    def _ft_rho_selection_summary(self, *, r: np.ndarray, y: np.ndarray, mask: np.ndarray) -> dict[str, object]:
        r = np.asarray(r, dtype=float)
        y = np.asarray(y, dtype=float)
        mask = np.asarray(mask, dtype=bool)
        if mask.shape != r.shape:
            mask = np.zeros_like(r, dtype=bool)
        subset = y[mask]
        subset = subset[np.isfinite(subset)]
        if subset.size == 0:
            return {"y_min": None, "y_max": None, "n_points": 0}
        return {
            "y_min": float(np.nanmin(subset)),
            "y_max": float(np.nanmax(subset)),
            "n_points": int(subset.size),
        }

    def _render_ft_rho_window_table(self, state: dict[str, object]) -> None:
        pane = getattr(self, "ft_rho_window_table", None)
        if pane is None:
            return

        def _section(title: str, window: tuple[float, float], summary: dict[str, object]) -> str:
            r_min, r_max = window
            y_min = summary.get("y_min")
            y_max = summary.get("y_max")
            n_points = int(summary.get("n_points") or 0)
            y_min_text = _fmt_compact_number(y_min) if y_min is not None else "N/A"
            y_max_text = _fmt_compact_number(y_max) if y_max is not None else "N/A"
            rows = [
                f"<tr><td class=\"toscana-fit-result-table__param\">R min</td><td class=\"toscana-fit-result-table__value\" style=\"text-align:left;\"><code>{_html_escape(_fmt_compact_number(r_min, decimals=1))}</code></td></tr>",
                f"<tr><td class=\"toscana-fit-result-table__param\">R max</td><td class=\"toscana-fit-result-table__value\" style=\"text-align:left;\"><code>{_html_escape(_fmt_compact_number(r_max, decimals=1))}</code></td></tr>",
                f"<tr><td class=\"toscana-fit-result-table__param\">Y min</td><td class=\"toscana-fit-result-table__value\" style=\"text-align:left;\"><code>{_html_escape(y_min_text)}</code></td></tr>",
                f"<tr><td class=\"toscana-fit-result-table__param\">Y max</td><td class=\"toscana-fit-result-table__value\" style=\"text-align:left;\"><code>{_html_escape(y_max_text)}</code></td></tr>",
                f"<tr><td class=\"toscana-fit-result-table__param\">Fit points</td><td class=\"toscana-fit-result-table__value\" style=\"text-align:left;\"><code>{n_points:d}</code></td></tr>",
            ]
            return (
                "<div class=\"toscana-fit-window-table\">"
                f"<div class=\"toscana-fit-result-table__title\">{_html_escape(title)}</div>"
                "<table class=\"toscana-fit-result-table\">"
                "<thead><tr><th>Field</th><th>Value</th></tr></thead>"
                "<tbody>"
                + "".join(rows)
                + "</tbody></table></div>"
            )

        active_series = str(state.get("active_series") or "no_lorch")
        series_block = state.get("series") if isinstance(state.get("series"), dict) else {}
        series_state = series_block.get(active_series) if isinstance(series_block.get(active_series), dict) else {}
        window = series_state.get("r_window")
        summary = series_state.get("summary") if isinstance(series_state.get("summary"), dict) else {}
        if not (isinstance(window, tuple) and len(window) == 2):
            pane.object = ""
            return
        title = "Lorch" if active_series == "lorch" else "No Lorch"
        pane.object = _section(title, window, summary)

    def _render_ft_rho_fit_result_table(self, state: dict[str, object]) -> None:
        pane = getattr(self, "ft_rho_fit_result_table", None)
        if pane is None:
            return

        active_series = str(state.get("active_series") or "no_lorch")
        series_block = state.get("series") if isinstance(state.get("series"), dict) else {}
        series_state = series_block.get(active_series) if isinstance(series_block.get(active_series), dict) else {}
        last_fit = series_state.get("last_fit") if isinstance(series_state.get("last_fit"), dict) else None
        rho_original = state.get("rho_original")
        rho_original_text = _fmt_compact_number(rho_original) if rho_original is not None else "N/A"

        if not isinstance(last_fit, dict) or last_fit.get("stale", True):
            pane.object = (
                "<div class=\"toscana-fit-window-table\">"
                "<div class=\"toscana-fit-result-table__title\">Fit results</div>"
                f"<div class=\"toscana-fit-result-table__meta\">Original ρ: <strong>{_html_escape(rho_original_text)}</strong></div>"
                "</div>"
            )
            return

        rho_fit = last_fit.get("rho_fit")
        rho_fit_text = _fmt_compact_number(rho_fit) if rho_fit is not None else "N/A"
        n_points = int(last_fit.get("n_points") or 0)

        delta = None
        if rho_original is not None and rho_fit is not None:
            try:
                delta = float(rho_fit) - float(rho_original)
            except Exception:
                delta = None
        delta_text = _fmt_compact_number(delta) if delta is not None else "N/A"
        series_title = "Lorch" if active_series == "lorch" else "No Lorch"

        pane.object = (
            "<div class=\"toscana-fit-window-table\">"
            "<div class=\"toscana-fit-result-table__title\">Fit results</div>"
            f"<div class=\"toscana-fit-result-table__meta\">Series: <strong>{_html_escape(series_title)}</strong></div>"
            f"<div class=\"toscana-fit-result-table__meta\">Points: <strong>{n_points:d}</strong></div>"
            f"<div class=\"toscana-fit-result-table__meta\" style=\"margin-top:8px;\">Original ρ: <strong>{_html_escape(rho_original_text)}</strong></div>"
            f"<div class=\"toscana-fit-result-table__meta\">Fitted ρ: <strong>{_html_escape(rho_fit_text)}</strong></div>"
            f"<div class=\"toscana-fit-result-table__meta\" style=\"margin-top:8px;\">Δ: <strong>{_html_escape(delta_text)}</strong></div>"
            "</div>"
        )

    def _refresh_ft_effective_atomic_density_panel(self) -> None:
        if self.current_project_root is None:
            return
        if not hasattr(self, "ft_rho_plot_pane"):
            return

        base = getattr(self, "_ft_base_gr_current", None)
        if not isinstance(base, dict):
            self._ft_rho_state = None
            self.ft_rho_plot_pane.object = None
            self._ft_real_space_set_disabled_ui(reason="Confirm Effective Atomic Density to compute real-space functions.")
            if hasattr(self, "ft_rho_view_switch"):
                self.ft_rho_view_switch.disabled = True
                self.ft_rho_view_switch.value = False
            slider = getattr(self, "ft_rho_r_range_slider", None)
            if slider is not None:
                try:
                    slider.disabled = True
                except Exception:
                    pass
            if hasattr(self, "ft_rho_run_fit_button"):
                self.ft_rho_run_fit_button.disabled = True
            if hasattr(self, "ft_rho_resolve_density_button"):
                self.ft_rho_resolve_density_button.disabled = True
            if hasattr(self, "ft_rho_confirm_selection_panel"):
                try:
                    self.ft_rho_confirm_selection_panel.visible = False
                except Exception:
                    pass
            if hasattr(self, "ft_rho_window_table"):
                self.ft_rho_window_table.object = ""
            if hasattr(self, "ft_rho_fit_result_table"):
                self.ft_rho_fit_result_table.object = ""
            return

        context_id = str(base.get("context_id") or "").strip()
        base_signature = str(base.get("signature") or "").strip()
        r = np.asarray(base.get("r"), dtype=float)
        gr = np.asarray(base.get("gr"), dtype=float)
        gr_lorch = np.asarray(base.get("gr_lorch"), dtype=float)
        if not context_id or not base_signature or r.size == 0:
            return

        order = np.argsort(r)
        r_sorted = r[order]
        r_min = float(np.nanmin(r_sorted[np.isfinite(r_sorted)])) if np.isfinite(r_sorted).any() else 0.0
        r_max = float(np.nanmax(r_sorted[np.isfinite(r_sorted)])) if np.isfinite(r_sorted).any() else 1.0
        if not np.isfinite(r_min) or not np.isfinite(r_max) or r_max <= r_min:
            r_min, r_max = 0.0, 1.0

        step = 0.1

        state = getattr(self, "_ft_rho_state", None)
        needs_reset = (
            not isinstance(state, dict)
            or str(state.get("base_signature") or "") != base_signature
            or str(state.get("context_id") or "") != context_id
        )
        if needs_reset:
            manifest_ref = self._selected_ft_manifest_ref()
            payload = load_context_manifest(self.current_project_root, manifest_ref) if manifest_ref else None
            rho_original = self._load_ft_original_rho(payload=payload) if isinstance(payload, dict) else None
            default_window = (0.0, 0.10 * float(r_max))
            state = {
                "context_id": context_id,
                "base_signature": base_signature,
                "rho_original": rho_original,
                "active_series": "no_lorch",
                "series": {
                    "no_lorch": {"r_window": default_window, "summary": {"y_min": None, "y_max": None, "n_points": 0}, "last_fit": None},
                    "lorch": {"r_window": default_window, "summary": {"y_min": None, "y_max": None, "n_points": 0}, "last_fit": None},
                },
                "view": "select",
                "rho_selection": {
                    "confirmed": False,
                    "panel_open": False,
                    "confirmed_snapshot": None,
                    "lorch": {"mode": None, "custom_value": None, "chosen_rho": None},
                    "no_lorch": {"mode": None, "custom_value": None, "chosen_rho": None},
                },
                "real_space": self._ft_real_space_default_state(),
            }
            self._ft_rho_state = state

            self._suspend_ft_events = True
            try:
                slider = getattr(self, "ft_rho_r_range_slider", None)
                if slider is not None:
                    slider.start = 0.0
                    slider.end = r_max
                    slider.step = step
                    slider.value = [default_window[0], default_window[1]]
                    if hasattr(slider, "value_throttled"):
                        slider.value_throttled = [default_window[0], default_window[1]]
                    slider.disabled = False
                if hasattr(self, "ft_rho_view_switch"):
                    self.ft_rho_view_switch.disabled = False
                    self.ft_rho_view_switch.value = False
                if hasattr(self, "ft_rho_series_switch"):
                    self.ft_rho_series_switch.disabled = False
                    self.ft_rho_series_switch.value = False
                if hasattr(self, "ft_rho_run_fit_button"):
                    self.ft_rho_run_fit_button.disabled = True
                if hasattr(self, "ft_rho_resolve_density_button"):
                    self.ft_rho_resolve_density_button.disabled = False
            finally:
                self._suspend_ft_events = False

        active_series = str(state.get("active_series") or "no_lorch")
        if hasattr(self, "ft_rho_series_switch"):
            active_series = "lorch" if bool(getattr(self.ft_rho_series_switch, "value", False)) else "no_lorch"
            state["active_series"] = active_series
        self._set_ft_rho_series_label(active_series)

        view = "run_fit" if bool(getattr(getattr(self, "ft_rho_view_switch", None), "value", False)) else "select"
        state["view"] = view
        self._set_ft_rho_view_label(view)

        series_block = state.get("series") if isinstance(state.get("series"), dict) else {}
        series_state = series_block.get(active_series) if isinstance(series_block.get(active_series), dict) else {}

        slider = getattr(self, "ft_rho_r_range_slider", None)
        stored_window = series_state.get("r_window") if isinstance(series_state.get("r_window"), tuple) else None
        try:
            window = tuple(getattr(slider, "value", [0.0, r_max])) if slider is not None else ()
            if len(window) == 2:
                r_window = (float(window[0]), float(window[1]))
            elif isinstance(stored_window, tuple) and len(stored_window) == 2:
                r_window = (float(stored_window[0]), float(stored_window[1]))
            else:
                r_window = (0.0, 0.10 * float(r_max))
        except Exception:
            r_window = (0.0, 0.10 * float(r_max))

        series_state["r_window"] = r_window
        y_active = gr_lorch if active_series == "lorch" else gr
        mask = self._ft_rho_select_window_mask(r=r, y=y_active, r_min=r_window[0], r_max=r_window[1])
        series_state["summary"] = self._ft_rho_selection_summary(r=r, y=y_active, mask=mask)
        series_block[active_series] = series_state
        state["series"] = series_block
        self._ft_rho_state = state

        # Shared R-filter slider applies to the currently active series.
        if slider is not None:
            try:
                slider.disabled = view == "run_fit"
            except Exception:
                pass

        self._render_ft_rho_window_table(state)

        # Enable fit button only in run-fit view and with enough points.
        if hasattr(self, "ft_rho_run_fit_button"):
            n_points = int(series_state.get("summary", {}).get("n_points") or 0) if isinstance(series_state.get("summary"), dict) else 0
            can_fit = view == "run_fit" and n_points >= 2
            self.ft_rho_run_fit_button.disabled = not bool(can_fit)

        last_fit = series_state.get("last_fit") if isinstance(series_state.get("last_fit"), dict) else None
        if isinstance(last_fit, dict):
            fit_sig = self._ft_rho_fit_signature(base_signature=base_signature, series=active_series, r_window=r_window)
            if str(last_fit.get("fit_signature") or "") != fit_sig:
                last_fit["stale"] = True
                series_state["last_fit"] = last_fit
                series_block[active_series] = series_state
                state["series"] = series_block
                self._ft_rho_state = state

        # Plot
        if view == "select":
            series_key = "lorch" if active_series == "lorch" else "no_lorch"
            existing_fig = getattr(getattr(self, "ft_rho_plot_pane", None), "object", None)
            if existing_fig is not None and hasattr(existing_fig, "update_layout") and hasattr(existing_fig, "data"):
                try:
                    update_ft_rho_selection_figure_single(
                        existing_fig,
                        r=r,
                        y=y_active,
                        selected_mask=mask,
                        series=series_key,
                        context_id=context_id,
                    )
                    self.ft_rho_plot_pane.object = existing_fig
                except Exception:
                    self.ft_rho_plot_pane.object = build_ft_rho_selection_figure_single(
                        r=r,
                        y=y_active,
                        selected_mask=mask,
                        series=series_key,
                        context_id=context_id,
                    )
            else:
                self.ft_rho_plot_pane.object = build_ft_rho_selection_figure_single(
                    r=r,
                    y=y_active,
                    selected_mask=mask,
                    series=series_key,
                    context_id=context_id,
                )
        else:
            if isinstance(last_fit, dict) and not bool(last_fit.get("stale", True)):
                series_key = "lorch" if active_series == "lorch" else "no_lorch"
                fit_signature = str(last_fit.get("fit_signature") or "")
                rho_fit_value = float(last_fit.get("rho_fit"))
                existing_fig = getattr(getattr(self, "ft_rho_plot_pane", None), "object", None)
                if existing_fig is not None and hasattr(existing_fig, "update_layout") and hasattr(existing_fig, "data"):
                    try:
                        update_ft_rho_fit_figure_single(
                            existing_fig,
                            r=r,
                            y=y_active,
                            rho=rho_fit_value,
                            series=series_key,
                            context_id=context_id,
                            fit_signature=fit_signature,
                        )
                        self.ft_rho_plot_pane.object = existing_fig
                    except Exception:
                        self.ft_rho_plot_pane.object = build_ft_rho_fit_figure_single(
                            r=r,
                            y=y_active,
                            rho=rho_fit_value,
                            series=series_key,
                            context_id=context_id,
                            fit_signature=fit_signature,
                        )
                else:
                    self.ft_rho_plot_pane.object = build_ft_rho_fit_figure_single(
                        r=r,
                        y=y_active,
                        rho=rho_fit_value,
                        series=series_key,
                        context_id=context_id,
                        fit_signature=fit_signature,
                    )
            else:
                self.ft_rho_plot_pane.object = None

        self._render_ft_rho_fit_result_table(state)
        self._ft_rho_refresh_confirm_selection_ui(state)
        self._refresh_ft_real_space_view(state)

    def _on_ft_rho_view_change(self, event) -> None:
        if getattr(self, "_suspend_ft_events", False):
            return
        self._update_ft_rho_fast(series_changed=False)

    def _on_ft_rho_series_change(self, event) -> None:
        if getattr(self, "_suspend_ft_events", False):
            return
        self._update_ft_rho_fast(series_changed=True)

    def _on_ft_rho_window_change(self, event=None) -> None:
        if getattr(self, "_suspend_ft_events", False):
            return
        self._update_ft_rho_fast(series_changed=False)

    def _update_ft_rho_fast(self, *, series_changed: bool) -> None:
        if getattr(self, "_suspend_ft_events", False):
            return

        base = getattr(self, "_ft_base_gr_current", None)
        state = getattr(self, "_ft_rho_state", None)
        slider = getattr(self, "ft_rho_r_range_slider", None)
        if slider is None or not isinstance(base, dict):
            return
        if not isinstance(state, dict):
            self._refresh_ft_effective_atomic_density_panel()
            return

        context_id = str(base.get("context_id") or "").strip()
        base_signature = str(base.get("signature") or "").strip()
        if str(state.get("context_id") or "") != context_id or str(state.get("base_signature") or "") != base_signature:
            self._refresh_ft_effective_atomic_density_panel()
            return

        r = np.asarray(base.get("r"), dtype=float)
        gr = np.asarray(base.get("gr"), dtype=float)
        gr_lorch = np.asarray(base.get("gr_lorch"), dtype=float)
        if r.size == 0:
            return

        active_series = "lorch" if bool(getattr(getattr(self, "ft_rho_series_switch", None), "value", False)) else "no_lorch"
        view = "run_fit" if bool(getattr(getattr(self, "ft_rho_view_switch", None), "value", False)) else "select"
        state["active_series"] = active_series
        state["view"] = view
        self._set_ft_rho_series_label(active_series)
        self._set_ft_rho_view_label(view)

        try:
            slider.disabled = view == "run_fit"
        except Exception:
            pass

        series_block = state.get("series") if isinstance(state.get("series"), dict) else {}
        series_state = series_block.get(active_series) if isinstance(series_block.get(active_series), dict) else {}

        stored_window = series_state.get("r_window") if isinstance(series_state.get("r_window"), tuple) and len(series_state.get("r_window")) == 2 else None
        if series_changed and stored_window is not None:
            self._suspend_ft_events = True
            try:
                slider.value = [float(stored_window[0]), float(stored_window[1])]
                if hasattr(slider, "value_throttled"):
                    slider.value_throttled = [float(stored_window[0]), float(stored_window[1])]
            finally:
                self._suspend_ft_events = False

        try:
            raw = getattr(slider, "value", None)
        except Exception:
            raw = None
        if isinstance(raw, (list, tuple)) and len(raw) == 2:
            r_window = (float(raw[0]), float(raw[1]))
        elif stored_window is not None:
            r_window = (float(stored_window[0]), float(stored_window[1]))
        else:
            r_window = (0.0, 0.0)

        # Clamp to slider bounds.
        try:
            bound_max = float(getattr(slider, "end", 0.0) or 0.0)
        except Exception:
            bound_max = float(np.nanmax(r[np.isfinite(r)])) if np.isfinite(r).any() else 1.0
        r_window = (max(0.0, min(r_window[0], bound_max)), max(0.0, min(r_window[1], bound_max)))
        if r_window[1] < r_window[0]:
            r_window = (r_window[1], r_window[0])

        prev_window = stored_window
        series_state["r_window"] = r_window
        if prev_window is not None and (float(prev_window[0]) != float(r_window[0]) or float(prev_window[1]) != float(r_window[1])):
            if isinstance(series_state.get("last_fit"), dict):
                series_state["last_fit"]["stale"] = True

        y_active = gr_lorch if active_series == "lorch" else gr
        mask = self._ft_rho_select_window_mask(r=r, y=y_active, r_min=r_window[0], r_max=r_window[1])
        series_state["summary"] = self._ft_rho_selection_summary(r=r, y=y_active, mask=mask)

        base_sig = str(state.get("base_signature") or "")
        last_fit = series_state.get("last_fit") if isinstance(series_state.get("last_fit"), dict) else None
        if isinstance(last_fit, dict):
            fit_sig = self._ft_rho_fit_signature(base_signature=base_sig, series=active_series, r_window=r_window)
            if str(last_fit.get("fit_signature") or "") != fit_sig:
                last_fit["stale"] = True
                series_state["last_fit"] = last_fit

        series_block[active_series] = series_state
        state["series"] = series_block
        self._ft_rho_state = state

        self._render_ft_rho_window_table(state)
        self._render_ft_rho_fit_result_table(state)
        self._ft_rho_refresh_confirm_selection_ui(state)

        if hasattr(self, "ft_rho_run_fit_button"):
            n_points = int(series_state.get("summary", {}).get("n_points") or 0) if isinstance(series_state.get("summary"), dict) else 0
            self.ft_rho_run_fit_button.disabled = not (view == "run_fit" and n_points >= 2)

        series_key = "lorch" if active_series == "lorch" else "no_lorch"
        if view == "select":
            fig = getattr(getattr(self, "ft_rho_plot_pane", None), "object", None)
            if fig is None:
                self.ft_rho_plot_pane.object = build_ft_rho_selection_figure_single(
                    r=r,
                    y=y_active,
                    selected_mask=mask,
                    series=series_key,
                    context_id=context_id,
                )
            else:
                try:
                    update_ft_rho_selection_figure_single(
                        fig,
                        r=r,
                        y=y_active,
                        selected_mask=mask,
                        series=series_key,
                        context_id=context_id,
                    )
                    # Re-assign to force Panel/Plotly pane to sync in-place figure updates.
                    self.ft_rho_plot_pane.object = fig
                except Exception:
                    self.ft_rho_plot_pane.object = build_ft_rho_selection_figure_single(
                        r=r,
                        y=y_active,
                        selected_mask=mask,
                        series=series_key,
                        context_id=context_id,
                    )
        else:
            if isinstance(last_fit, dict) and not bool(last_fit.get("stale", True)) and last_fit.get("rho_fit") is not None:
                rho_fit_value = float(last_fit.get("rho_fit"))
                fit_signature = str(last_fit.get("fit_signature") or "")
                fig = getattr(getattr(self, "ft_rho_plot_pane", None), "object", None)
                if fig is None:
                    self.ft_rho_plot_pane.object = build_ft_rho_fit_figure_single(
                        r=r,
                        y=y_active,
                        rho=rho_fit_value,
                        series=series_key,
                        context_id=context_id,
                        fit_signature=fit_signature,
                    )
                else:
                    try:
                        update_ft_rho_fit_figure_single(
                            fig,
                            r=r,
                            y=y_active,
                            rho=rho_fit_value,
                            series=series_key,
                            context_id=context_id,
                            fit_signature=fit_signature,
                        )
                        # Re-assign to force Panel/Plotly pane to sync in-place figure updates.
                        self.ft_rho_plot_pane.object = fig
                    except Exception:
                        self.ft_rho_plot_pane.object = build_ft_rho_fit_figure_single(
                            r=r,
                            y=y_active,
                            rho=rho_fit_value,
                            series=series_key,
                            context_id=context_id,
                            fit_signature=fit_signature,
                        )
            else:
                self.ft_rho_plot_pane.object = None

        self._ft_rho_refresh_confirm_selection_ui(state)

    def _ft_rho_get_fit_rho(self, *, state: dict[str, object], series: str) -> float | None:
        series = str(series or "").strip()
        series_block = state.get("series") if isinstance(state.get("series"), dict) else {}
        series_state = series_block.get(series) if isinstance(series_block.get(series), dict) else {}
        last_fit = series_state.get("last_fit") if isinstance(series_state.get("last_fit"), dict) else None
        if not isinstance(last_fit, dict) or bool(last_fit.get("stale", True)):
            return None
        rho_fit = last_fit.get("rho_fit")
        try:
            rho_val = float(rho_fit)
        except Exception:
            return None
        return rho_val if np.isfinite(rho_val) else None

    def _ft_rho_can_enable_confirm_selection(self, *, state: dict[str, object]) -> bool:
        return self._ft_rho_get_fit_rho(state=state, series="no_lorch") is not None and self._ft_rho_get_fit_rho(
            state=state, series="lorch"
        ) is not None

    def _ft_rho_apply_selection(self, *, state: dict[str, object], series: str, mode: str) -> None:
        selection = state.get("rho_selection") if isinstance(state.get("rho_selection"), dict) else None
        if not isinstance(selection, dict):
            return
        series_key = "lorch" if str(series) == "lorch" else "no_lorch"
        block = selection.get(series_key) if isinstance(selection.get(series_key), dict) else {}
        mode = str(mode or "").strip()
        if mode not in ("original", "fitted", "custom"):
            block["mode"] = None
            block["chosen_rho"] = None
            selection[series_key] = block
            state["rho_selection"] = selection
            return

        block["mode"] = mode

        if mode == "original":
            rho_original = state.get("rho_original")
            if rho_original is None:
                block["chosen_rho"] = None
            else:
                try:
                    rho_val = float(rho_original)
                except Exception:
                    rho_val = None
                block["chosen_rho"] = float(rho_val) if rho_val is not None and np.isfinite(rho_val) else None
        elif mode == "fitted":
            block["chosen_rho"] = self._ft_rho_get_fit_rho(state=state, series=series_key)
        else:
            custom_value = block.get("custom_value")
            try:
                rho_val = float(custom_value)
            except Exception:
                rho_val = None
            block["chosen_rho"] = float(rho_val) if rho_val is not None and np.isfinite(rho_val) else None

        selection[series_key] = block
        state["rho_selection"] = selection

    def _ft_rho_refresh_confirm_selection_ui(self, state: dict[str, object]) -> None:
        selection = state.get("rho_selection") if isinstance(state.get("rho_selection"), dict) else None
        if not isinstance(selection, dict):
            return

        can_enable = self._ft_rho_can_enable_confirm_selection(state=state)
        button = getattr(self, "ft_rho_resolve_density_button", None)
        if button is not None:
            try:
                # Resolve button is available as soon as the panel has Base G(R) context.
                button.disabled = False
            except Exception:
                pass

        panel = getattr(self, "ft_rho_confirm_selection_panel", None)
        panel_open = bool(selection.get("panel_open", False))
        if panel is not None:
            try:
                panel.visible = bool(panel_open)
            except Exception:
                pass

        rho_original = state.get("rho_original")
        rho_original_text = _fmt_compact_number(rho_original) if rho_original is not None else "N/A"
        fit_no = self._ft_rho_get_fit_rho(state=state, series="no_lorch")
        fit_lorch = self._ft_rho_get_fit_rho(state=state, series="lorch")
        fit_no_text = _fmt_compact_number(fit_no) if fit_no is not None else "N/A"
        fit_l_text = _fmt_compact_number(fit_lorch) if fit_lorch is not None else "N/A"

        # Update radio options (labels include numeric values).
        for series_key, fit_text in (("lorch", fit_l_text), ("no_lorch", fit_no_text)):
            radio = getattr(self, "ft_rho_choice_lorch" if series_key == "lorch" else "ft_rho_choice_no_lorch", None)
            if radio is not None:
                try:
                    fitted_label = f"Use Fitted ρ {fit_text}" if fit_text != "N/A" else "Use Fitted ρ N/A (Run Fit)"
                    radio.options = {
                        f"Use Original ρ {rho_original_text}": "original",
                        fitted_label: "fitted",
                        "Use Custom Value": "custom",
                    }
                except Exception:
                    pass

        # Enforce original disabled behavior when rho_original missing.
        if rho_original is None:
            for name in ("ft_rho_choice_lorch", "ft_rho_choice_no_lorch"):
                radio = getattr(self, name, None)
                if radio is not None and getattr(radio, "value", None) == "original":
                    try:
                        radio.value = None
                    except Exception:
                        pass

        # Custom input visibility
        for series_key in ("lorch", "no_lorch"):
            radio = getattr(self, "ft_rho_choice_lorch" if series_key == "lorch" else "ft_rho_choice_no_lorch", None)
            custom = getattr(self, "ft_rho_custom_lorch" if series_key == "lorch" else "ft_rho_custom_no_lorch", None)
            mode = getattr(radio, "value", None) if radio is not None else None
            if custom is not None:
                try:
                    custom.visible = mode == "custom"
                except Exception:
                    pass

        # Bottom Confirm/Cancel buttons visible only when both series have a valid chosen_rho.
        lorch_block = selection.get("lorch") if isinstance(selection.get("lorch"), dict) else {}
        no_block = selection.get("no_lorch") if isinstance(selection.get("no_lorch"), dict) else {}
        lorch_ok = isinstance(lorch_block.get("chosen_rho"), (int, float)) and np.isfinite(float(lorch_block.get("chosen_rho")))
        no_ok = isinstance(no_block.get("chosen_rho"), (int, float)) and np.isfinite(float(no_block.get("chosen_rho")))
        confirm_btn = getattr(self, "ft_rho_confirm_button", None)
        cancel_btn = getattr(self, "ft_rho_cancel_button", None)
        if cancel_btn is not None:
            try:
                cancel_btn.visible = bool(panel_open)
            except Exception:
                pass
        if confirm_btn is not None:
            try:
                confirm_btn.visible = bool(panel_open)
                confirm_btn.disabled = not bool(lorch_ok and no_ok)
            except Exception:
                pass

    def _on_ft_rho_open_confirm_selection(self, _event=None) -> None:
        state = getattr(self, "_ft_rho_state", None)
        if not isinstance(state, dict):
            return
        selection = state.get("rho_selection") if isinstance(state.get("rho_selection"), dict) else None
        if not isinstance(selection, dict):
            return
        # Allow opening the resolver even if fits are missing; the fitted option will guide users to run the fit.
        # Prepopulate widgets from last confirmed (or last edited) state.
        self._suspend_ft_events = True
        try:
            lorch_block = selection.get("lorch") if isinstance(selection.get("lorch"), dict) else {}
            no_block = selection.get("no_lorch") if isinstance(selection.get("no_lorch"), dict) else {}
            if hasattr(self, "ft_rho_choice_lorch"):
                self.ft_rho_choice_lorch.value = lorch_block.get("mode")
            if hasattr(self, "ft_rho_choice_no_lorch"):
                self.ft_rho_choice_no_lorch.value = no_block.get("mode")
            if hasattr(self, "ft_rho_custom_lorch"):
                self.ft_rho_custom_lorch.value = lorch_block.get("custom_value")
            if hasattr(self, "ft_rho_custom_no_lorch"):
                self.ft_rho_custom_no_lorch.value = no_block.get("custom_value")
        except Exception:
            pass
        finally:
            self._suspend_ft_events = False
        selection["panel_open"] = True
        state["rho_selection"] = selection
        self._ft_rho_refresh_confirm_selection_ui(state)

    def _on_ft_rho_choice_change(self, event) -> None:
        if getattr(self, "_suspend_ft_events", False):
            return
        state = getattr(self, "_ft_rho_state", None)
        if not isinstance(state, dict):
            return
        series = None
        try:
            if getattr(event, "obj", None) is getattr(self, "ft_rho_choice_lorch", None):
                series = "lorch"
            elif getattr(event, "obj", None) is getattr(self, "ft_rho_choice_no_lorch", None):
                series = "no_lorch"
        except Exception:
            series = None
        if series is None:
            return

        mode = str(getattr(event, "new", "") or "")
        if mode == "original" and state.get("rho_original") is None:
            # enforce disabled original option when missing
            radio = getattr(self, "ft_rho_choice_lorch" if series == "lorch" else "ft_rho_choice_no_lorch", None)
            if radio is not None:
                try:
                    radio.value = None
                except Exception:
                    pass
            if hasattr(self, "_show_warning_toast"):
                self._show_warning_toast("Original $\rho_N$ is not available for this context.")
            mode = ""
        if mode == "fitted" and self._ft_rho_get_fit_rho(state=state, series=series) is None:
            radio = getattr(self, "ft_rho_choice_lorch" if series == "lorch" else "ft_rho_choice_no_lorch", None)
            if radio is not None:
                try:
                    radio.value = None
                except Exception:
                    pass
            if hasattr(self, "_show_warning_toast"):
                self._show_warning_toast("No Fitted $\rho_N$ is available yet. Run the fit first.")
            mode = ""
        self._ft_rho_apply_selection(state=state, series=series, mode=mode)
        self._ft_rho_refresh_confirm_selection_ui(state)

    def _on_ft_rho_custom_change(self, event) -> None:
        if getattr(self, "_suspend_ft_events", False):
            return
        state = getattr(self, "_ft_rho_state", None)
        if not isinstance(state, dict):
            return
        selection = state.get("rho_selection") if isinstance(state.get("rho_selection"), dict) else None
        if not isinstance(selection, dict):
            return
        series = None
        try:
            if getattr(event, "obj", None) is getattr(self, "ft_rho_custom_lorch", None):
                series = "lorch"
            elif getattr(event, "obj", None) is getattr(self, "ft_rho_custom_no_lorch", None):
                series = "no_lorch"
        except Exception:
            series = None
        if series is None:
            return

        block = selection.get(series) if isinstance(selection.get(series), dict) else {}
        block["custom_value"] = getattr(event, "new", None)
        selection[series] = block
        state["rho_selection"] = selection
        # Only applies when mode is custom.
        radio = getattr(self, "ft_rho_choice_lorch" if series == "lorch" else "ft_rho_choice_no_lorch", None)
        mode = getattr(radio, "value", None) if radio is not None else None
        if mode == "custom":
            self._ft_rho_apply_selection(state=state, series=series, mode="custom")
        self._ft_rho_refresh_confirm_selection_ui(state)

    def _on_ft_rho_confirm_selection(self, _event=None) -> None:
        state = getattr(self, "_ft_rho_state", None)
        if not isinstance(state, dict):
            return
        selection = state.get("rho_selection") if isinstance(state.get("rho_selection"), dict) else None
        if not isinstance(selection, dict):
            return
        lorch_block = selection.get("lorch") if isinstance(selection.get("lorch"), dict) else {}
        no_block = selection.get("no_lorch") if isinstance(selection.get("no_lorch"), dict) else {}
        lorch_ok = isinstance(lorch_block.get("chosen_rho"), (int, float)) and np.isfinite(float(lorch_block.get("chosen_rho")))
        no_ok = isinstance(no_block.get("chosen_rho"), (int, float)) and np.isfinite(float(no_block.get("chosen_rho")))
        if not (lorch_ok and no_ok):
            return
        selection["confirmed"] = True
        selection["panel_open"] = False
        selection["confirmed_snapshot"] = {
            "lorch": dict(lorch_block),
            "no_lorch": dict(no_block),
        }
        state["rho_selection"] = selection
        self._ft_rho_refresh_confirm_selection_ui(state)
        self._compute_ft_real_space_functions_from_confirmed_selection(state)
        self._refresh_ft_real_space_view(state)

    def _on_ft_rho_cancel_selection(self, _event=None) -> None:
        state = getattr(self, "_ft_rho_state", None)
        if not isinstance(state, dict):
            return
        selection = state.get("rho_selection") if isinstance(state.get("rho_selection"), dict) else None
        if not isinstance(selection, dict):
            return

        # If never confirmed, discard in-progress edits.
        if not bool(selection.get("confirmed", False)):
            selection["lorch"] = {"mode": None, "custom_value": None, "chosen_rho": None}
            selection["no_lorch"] = {"mode": None, "custom_value": None, "chosen_rho": None}
        else:
            snap = selection.get("confirmed_snapshot") if isinstance(selection.get("confirmed_snapshot"), dict) else None
            if isinstance(snap, dict):
                if isinstance(snap.get("lorch"), dict):
                    selection["lorch"] = dict(snap["lorch"])
                if isinstance(snap.get("no_lorch"), dict):
                    selection["no_lorch"] = dict(snap["no_lorch"])

        selection["panel_open"] = False
        state["rho_selection"] = selection
        self._ft_rho_refresh_confirm_selection_ui(state)
    def _on_ft_rho_run_fit(self, _event=None) -> None:
        state = getattr(self, "_ft_rho_state", None)
        base = getattr(self, "_ft_base_gr_current", None)
        if not (isinstance(state, dict) and isinstance(base, dict)):
            return
        if str(state.get("context_id") or "") != str(base.get("context_id") or ""):
            return

        r = np.asarray(base.get("r"), dtype=float)
        gr = np.asarray(base.get("gr"), dtype=float)
        gr_lorch = np.asarray(base.get("gr_lorch"), dtype=float)
        base_signature = str(base.get("signature") or "")

        active_series = str(state.get("active_series") or "no_lorch")
        series_block = state.get("series") if isinstance(state.get("series"), dict) else {}
        series_state = series_block.get(active_series) if isinstance(series_block.get(active_series), dict) else None
        if not isinstance(series_state, dict):
            return
        window = series_state.get("r_window")
        if not (isinstance(window, tuple) and len(window) == 2):
            return
        y_active = gr_lorch if active_series == "lorch" else gr
        mask = self._ft_rho_select_window_mask(r=r, y=y_active, r_min=float(window[0]), r_max=float(window[1]))

        def _fit_rho(mask: np.ndarray, y: np.ndarray) -> tuple[float | None, int]:
            rr = np.asarray(r[mask], dtype=float)
            yy = np.asarray(y[mask], dtype=float)
            finite = np.isfinite(rr) & np.isfinite(yy) & (rr != 0.0)
            rr = rr[finite]
            yy = yy[finite]
            if rr.size < 2:
                return None, int(rr.size)
            denom = float(np.dot(rr, rr))
            if not np.isfinite(denom) or denom == 0.0:
                return None, int(rr.size)
            m = float(np.dot(rr, yy)) / denom
            rho = -m / (4.0 * float(np.pi))
            if not np.isfinite(rho):
                return None, int(rr.size)
            return float(rho), int(rr.size)

        rho_fit, n_points = _fit_rho(mask, y_active)
        if rho_fit is None or n_points < 2:
            if hasattr(self, "_show_warning_toast"):
                self._show_warning_toast("Not enough fit points. Widen the R windows.")
            return

        fit_sig = self._ft_rho_fit_signature(
            base_signature=str(base_signature),
            series=active_series,
            r_window=(float(window[0]), float(window[1])),
        )
        series_state["last_fit"] = {
            "fit_signature": fit_sig,
            "rho_fit": float(rho_fit),
            "n_points": int(n_points),
            "stale": False,
        }
        series_block[active_series] = series_state
        state["series"] = series_block
        self._ft_rho_state = state
        self._refresh_ft_effective_atomic_density_panel()
        try:
            self.ft_rho_plot_pane.param.trigger("object")
        except Exception:
            pass

