from __future__ import annotations

def bind_shell_callbacks(shell) -> None:
    shell.start_project_button.on_click(shell._go_to_workspace_from_start)
    shell.continue_project_button.on_click(shell._go_to_workspace_from_continue)
    shell.back_to_menu_button.on_click(shell._go_to_landing_page)
    shell.reset_project_button.on_click(shell._prompt_reset_project)
    for tab_name, button in shell.workspace_buttons.items():
        button.on_click(shell._make_workspace_navigation_handler(tab_name))
    shell.create_project_confirm_button.on_click(shell._create_project)
    shell.save_project_button.on_click(shell._save_current_project)
    shell.manual_open_button.on_click(shell._open_project_from_manual_path)
    shell.numors_validate_button.on_click(shell._validate_numors_selection)
    shell.numors_run_button.on_click(shell._notify_numors_execution_pending)
    shell.numors_prev_block_button.on_click(shell._on_numors_prev_run_block)
    shell.numors_next_block_button.on_click(shell._on_numors_next_run_block)
    shell.numors_prev_plot_button.on_click(shell._on_numors_prev_plot)
    shell.numors_next_plot_button.on_click(shell._on_numors_next_plot)
    shell.numors_import_confirm_button.on_click(shell._copy_numors_file_into_project)
    shell.numors_import_cancel_button.on_click(shell._cancel_numors_import)
    shell.background_validate_button.on_click(shell._validate_background_selection)
    shell.background_extract_button.on_click(shell._notify_background_extraction_pending)
    shell.background_import_confirm_button.on_click(shell._copy_background_file_into_project)
    shell.background_import_cancel_button.on_click(shell._cancel_background_import)
    shell.background_linear_compute_button.on_click(shell._compute_background_linear_combination)
    shell.background_vanadium_compute_button.on_click(shell._compute_background_vanadium_linear_combination)
    shell.background_export_button.on_click(shell._prompt_background_export)
    shell.background_export_confirm_button.on_click(shell._confirm_background_export)
    shell.background_export_cancel_button.on_click(shell._cancel_background_export)
    shell.normalization_validate_button.on_click(shell._validate_normalization_selection)
    shell.normalization_import_confirm_button.on_click(shell._copy_normalization_files_into_project)
    shell.normalization_import_cancel_button.on_click(shell._cancel_normalization_import)
    shell.normalization_adopt_confirm_button.on_click(shell._confirm_normalization_adopt)
    shell.normalization_adopt_cancel_button.on_click(shell._cancel_normalization_adopt)
    shell.normalization_fit_params_suggest_button.on_click(shell._normalization_fit_params_suggest_initial_guess)
    shell.normalization_fit_params_run_button.on_click(shell._normalization_fit_params_run_fit)
    shell.normalization_export_button.on_click(shell._prompt_normalization_export)
    shell.normalization_export_confirm_button.on_click(shell._confirm_normalization_export)
    shell.normalization_export_cancel_button.on_click(shell._cancel_normalization_export)
    shell.normalization_export_folder_input.param.watch(shell._on_normalization_export_folder_change, "value")
    shell.normalization_fit_params_plot_mode.param.watch(shell._on_normalization_fit_params_plot_mode_change, "value")
    shell.normalization_fit_params_bounds_toggle.param.watch(shell._on_normalization_fit_params_bounds_toggle_change, "value")
    shell.normalization_vanadium_self_fit_preview_view_switch.param.watch(
        shell._on_normalization_vanadium_self_fit_preview_view_change, "value"
    )
    shell.self_context_select.param.watch(shell._on_self_context_change, "value")
    shell.ft_context_select.param.watch(shell._on_ft_context_change, "value")
    shell.bft_context_select.param.watch(shell._on_bft_context_change, "value")
    if hasattr(shell, "bft_animation_player"):
        shell.bft_animation_player.param.watch(shell._on_bft_animation_iteration_change, "value")
    shell.ft_view_switch.param.watch(shell._on_ft_view_change, "value")
    shell.ft_rho_view_switch.param.watch(shell._on_ft_rho_view_change, "value")
    shell.ft_rho_series_switch.param.watch(shell._on_ft_rho_series_change, "value")
    shell.ft_rho_r_range_slider.param.watch(shell._on_ft_rho_window_change, "value")
    shell.ft_rho_run_fit_button.on_click(shell._on_ft_rho_run_fit)
    shell.ft_rho_resolve_density_button.on_click(shell._on_ft_rho_open_confirm_selection)
    shell.ft_rho_choice_lorch.param.watch(shell._on_ft_rho_choice_change, "value")
    shell.ft_rho_choice_no_lorch.param.watch(shell._on_ft_rho_choice_change, "value")
    shell.ft_rho_custom_lorch.param.watch(shell._on_ft_rho_custom_change, "value")
    shell.ft_rho_custom_no_lorch.param.watch(shell._on_ft_rho_custom_change, "value")
    shell.ft_rho_confirm_button.on_click(shell._on_ft_rho_confirm_selection)
    shell.ft_rho_cancel_button.on_click(shell._on_ft_rho_cancel_selection)
    shell.ft_real_space_prev_block_button.on_click(shell._on_ft_real_space_prev_block)
    shell.ft_real_space_next_block_button.on_click(shell._on_ft_real_space_next_block)
    shell.ft_real_space_prev_plot_button.on_click(shell._on_ft_real_space_prev_plot)
    shell.ft_real_space_next_plot_button.on_click(shell._on_ft_real_space_next_plot)
    if hasattr(shell, "ft_export_folder_input"):
        shell.ft_export_folder_input.param.watch(shell._on_ft_export_folder_change, "value")
    if hasattr(shell, "ft_export_button"):
        shell.ft_export_button.on_click(shell._prompt_ft_export)
    if hasattr(shell, "ft_export_confirm_button"):
        shell.ft_export_confirm_button.on_click(shell._confirm_ft_export)
    if hasattr(shell, "ft_export_cancel_button"):
        shell.ft_export_cancel_button.on_click(shell._cancel_ft_export)

    # Back Fourier Transform (BFT)
    shell.bft_run_button.on_click(shell._on_bft_run_clicked)
    shell.bft_iterations_confirm_button.on_click(shell._on_bft_confirm_iterations_warning)
    shell.bft_iterations_cancel_button.on_click(shell._on_bft_cancel_iterations_warning)
    shell.bft_final_prev_plot_button.on_click(shell._on_bft_final_prev_plot)
    shell.bft_final_next_plot_button.on_click(shell._on_bft_final_next_plot)
    shell.self_lowq_redesign_switch_input_mode.on_click(shell._toggle_self_lowq_input_mode)
    shell.self_lowq_redesign_switch_method.on_click(shell._toggle_self_lowq_method)
    shell.self_lowq_extrapolate_button.on_click(shell._run_self_lowq_extrapolate)
    shell.self_lowq_view_switch.param.watch(shell._on_self_lowq_view_change, "value")
    shell.self_data_selection_redesign_switch_input_mode.on_click(shell._toggle_self_data_selection_input_mode)
    shell.self_data_selection_redesign_switch_method.on_click(shell._toggle_self_data_selection_method)
    shell.reset_project_confirm_button.on_click(shell._confirm_reset_project)
    shell.reset_project_cancel_button.on_click(shell._cancel_reset_project)
    shell.save_and_continue_button.on_click(shell._save_and_continue)
    shell.discard_and_continue_button.on_click(shell._discard_and_continue)
    shell.cancel_navigation_button.on_click(shell._cancel_pending_navigation)
    shell.project_editor_name_input.param.watch(
        shell._on_project_editor_name_change,
        "value",
    )
    shell.project_name_input.param.watch(shell._on_project_name_input_change, "value")
    shell.project_folder_input.param.watch(shell._on_project_folder_input_change, "value")
    shell.project_folder_mode.param.watch(shell._on_project_folder_mode_change, "value")
    shell.project_folder_file_selector.param.watch(
        shell._on_project_folder_candidate_change,
        "value",
    )
    shell.manual_project_file_mode.param.watch(
        shell._on_manual_project_file_mode_change,
        "value",
    )
    shell.manual_project_file_input.param.watch(
        shell._on_manual_project_file_input_change,
        "value",
    )
    shell.manual_project_file_selector.param.watch(
        shell._on_manual_project_file_candidate_change,
        "value",
    )
    shell.numors_source_mode.param.watch(shell._on_numors_source_mode_change, "value")
    shell.background_source_mode.param.watch(shell._on_background_source_mode_change, "value")
    shell.normalization_source_mode.param.watch(shell._on_normalization_source_mode_change, "value")
    shell.numors_manual_path_input.param.watch(
        shell._on_numors_manual_path_change,
        "value",
    )
    shell.background_manual_path_input.param.watch(shell._on_background_manual_path_change, "value")
    shell.normalization_sample_qdat_path_input.param.watch(
        lambda _e: (shell._clear_normalization_import_prompt(), shell._clear_normalization_adopt_prompt()),
        "value",
    )
    shell.normalization_vanadium_qdat_path_input.param.watch(
        lambda _e: (shell._clear_normalization_import_prompt(), shell._clear_normalization_adopt_prompt()),
        "value",
    )
    shell.numors_par_dropdown.param.watch(shell._on_numors_par_dropdown_change, "value")
    shell.background_par_dropdown.param.watch(shell._on_background_par_dropdown_change, "value")
    shell.normalization_sample_qdat_dropdown.param.watch(
        lambda _e: (shell._clear_normalization_import_prompt(), shell._clear_normalization_adopt_prompt()),
        "value",
    )
    shell.normalization_vanadium_qdat_dropdown.param.watch(
        lambda _e: (shell._clear_normalization_import_prompt(), shell._clear_normalization_adopt_prompt()),
        "value",
    )
    shell.background_subtraction_method.param.watch(
        shell._on_background_subtraction_method_change,
        "value",
    )
    shell.background_sample_method_select.param.watch(
        shell._on_background_sample_method_select_change,
        "value",
    )
    shell.background_linear_t_start.param.watch(shell._on_background_linear_settings_change, "value")
    shell.background_linear_t_stop.param.watch(shell._on_background_linear_settings_change, "value")
    shell.background_linear_t_step.param.watch(shell._on_background_linear_settings_change, "value")
    shell.background_linear_smoothing.param.watch(shell._on_background_linear_settings_change, "value")
    shell.background_linear_ignore_points.param.watch(shell._on_background_linear_settings_change, "value")
    shell.background_linear_t_mode.param.watch(shell._on_background_linear_t_selection_change, "value")
    shell.background_linear_custom_t.param.watch(shell._on_background_linear_t_selection_change, "value")
    shell.background_sample_view_switch.param.watch(shell._on_background_sample_view_switch_change, "value")
    shell.background_sample_use_computed_t_button.on_click(shell._on_background_sample_use_computed_t_click)
    shell.background_sample_use_custom_t_button.on_click(shell._on_background_sample_use_custom_t_click)
    shell.background_vanadium_method_select.param.watch(shell._on_background_vanadium_method_select_change, "value")
    shell.background_vanadium_view_switch.param.watch(shell._on_background_vanadium_view_switch_change, "value")
    shell.background_vanadium_use_computed_t_button.on_click(shell._on_background_vanadium_use_computed_t_click)
    shell.background_vanadium_use_custom_t_button.on_click(shell._on_background_vanadium_use_custom_t_click)

    def _sync_background_sample_custom_t_ui(_event=None) -> None:
        use_custom = bool(getattr(shell.background_sample_use_custom_t_toggle, "value", False))
        shell.background_sample_custom_t_input.visible = True
        shell.background_sample_custom_t_input.disabled = not use_custom
        if hasattr(shell, "_refresh_interaction_states"):
            shell._refresh_interaction_states()

    shell.background_sample_use_custom_t_toggle.param.watch(_sync_background_sample_custom_t_ui, "value")
    shell.background_sample_custom_t_input.param.watch(_sync_background_sample_custom_t_ui, "value")
    shell.background_linear_chi_plot_pane.param.watch(_sync_background_sample_custom_t_ui, "object")
    _sync_background_sample_custom_t_ui()

    def _sync_background_vanadium_custom_t_ui(_event=None) -> None:
        use_custom = bool(getattr(shell.background_vanadium_use_custom_t_toggle, "value", False))
        shell.background_vanadium_custom_t_input.visible = True
        shell.background_vanadium_custom_t_input.disabled = not use_custom
        if hasattr(shell, "_refresh_interaction_states"):
            shell._refresh_interaction_states()

    shell.background_vanadium_use_custom_t_toggle.param.watch(_sync_background_vanadium_custom_t_ui, "value")
    shell.background_vanadium_custom_t_input.param.watch(_sync_background_vanadium_custom_t_ui, "value")
    shell.background_vanadium_chi_plot_pane.param.watch(_sync_background_vanadium_custom_t_ui, "object")
    _sync_background_vanadium_custom_t_ui()
    shell.background_vanadium_t_start.param.watch(shell._on_background_vanadium_settings_change, "value")
    shell.background_vanadium_t_stop.param.watch(shell._on_background_vanadium_settings_change, "value")
    shell.background_vanadium_t_step.param.watch(shell._on_background_vanadium_settings_change, "value")
    shell.background_vanadium_smoothing.param.watch(shell._on_background_vanadium_settings_change, "value")
    shell.background_vanadium_ignore_points.param.watch(shell._on_background_vanadium_settings_change, "value")
    shell.background_vanadium_t_mode.param.watch(shell._on_background_vanadium_t_selection_change, "value")
    shell.background_vanadium_custom_t.param.watch(shell._on_background_vanadium_t_selection_change, "value")
    shell.background_export_folder_input.param.watch(shell._on_background_export_folder_change, "value")
    shell.numors_block_select.param.watch(shell._on_numors_block_select_change, "value")
    shell.normalization_context_select.param.watch(shell._on_normalization_context_change, "value")
    shell.normalization_custom_files_toggle_button.on_click(shell._toggle_normalization_custom_files_override)
    shell.normalization_custom_files_switch.param.watch(shell._on_normalization_custom_files_switch_change, "value")
    shell.normalization_fit_data_selection_mode.param.watch(shell._on_normalization_fit_data_selection_mode_change, "value")
    shell.normalization_fit_data_use_sliders.param.watch(shell._on_normalization_fit_data_use_sliders_change, "value")
    shell.normalization_fit_data_redesign_switch_input_mode.on_click(shell._toggle_normalization_fit_data_redesign_input_mode)
    shell.normalization_fit_data_redesign_switch_method.on_click(shell._toggle_normalization_fit_data_redesign_method)
    def _sync_normalization_fit_data_input_menu(_event=None) -> None:
        visible = bool(getattr(shell.normalization_fit_data_input_menu_toggle, "value", False))
        shell.normalization_fit_data_input_tray.visible = visible
        shell.normalization_fit_data_input_menu_toggle.name = (
            "Hide controls" if visible else "Show controls"
        )

    shell.normalization_fit_data_input_menu_toggle.param.watch(
        _sync_normalization_fit_data_input_menu,
        "value",
    )
    _sync_normalization_fit_data_input_menu()
    shell.normalization_fit_data_q_tail_low.param.watch(shell._on_normalization_fit_data_controls_change, "value")
    shell.normalization_fit_data_q_tail_high.param.watch(shell._on_normalization_fit_data_controls_change, "value")
    shell.normalization_fit_data_min_percentile.param.watch(shell._on_normalization_fit_data_controls_change, "value")
    shell.normalization_fit_data_max_percentile.param.watch(shell._on_normalization_fit_data_controls_change, "value")
    shell.normalization_fit_data_q_min.param.watch(shell._on_normalization_fit_data_controls_change, "value")
    shell.normalization_fit_data_q_max.param.watch(shell._on_normalization_fit_data_controls_change, "value")
    shell.normalization_fit_data_y_min.param.watch(shell._on_normalization_fit_data_controls_change, "value")
    shell.normalization_fit_data_y_max.param.watch(shell._on_normalization_fit_data_controls_change, "value")
    shell.normalization_fit_data_q_tail_low_slider.param.watch(shell._on_normalization_fit_data_controls_change, "value")
    shell.normalization_fit_data_q_tail_high_slider.param.watch(
        shell._on_normalization_fit_data_controls_change, "value"
    )
    shell.normalization_fit_data_min_percentile_slider.param.watch(
        shell._on_normalization_fit_data_controls_change, "value"
    )
    shell.normalization_fit_data_max_percentile_slider.param.watch(
        shell._on_normalization_fit_data_controls_change, "value"
    )
    shell.normalization_fit_data_q_min_slider.param.watch(shell._on_normalization_fit_data_controls_change, "value")
    shell.normalization_fit_data_q_max_slider.param.watch(shell._on_normalization_fit_data_controls_change, "value")
    shell.normalization_fit_data_y_min_slider.param.watch(shell._on_normalization_fit_data_controls_change, "value")
    shell.normalization_fit_data_y_max_slider.param.watch(shell._on_normalization_fit_data_controls_change, "value")
    shell.normalization_fit_data_q_tail_low_slider.param.watch(
        shell._on_normalization_fit_data_controls_commit, "value_throttled"
    )
    shell.normalization_fit_data_q_tail_high_slider.param.watch(
        shell._on_normalization_fit_data_controls_commit, "value_throttled"
    )
    shell.normalization_fit_data_min_percentile_slider.param.watch(
        shell._on_normalization_fit_data_controls_commit, "value_throttled"
    )
    shell.normalization_fit_data_max_percentile_slider.param.watch(
        shell._on_normalization_fit_data_controls_commit, "value_throttled"
    )
    shell.normalization_fit_data_q_min_slider.param.watch(
        shell._on_normalization_fit_data_controls_commit, "value_throttled"
    )
    shell.normalization_fit_data_q_max_slider.param.watch(
        shell._on_normalization_fit_data_controls_commit, "value_throttled"
    )
    shell.normalization_fit_data_y_min_slider.param.watch(
        shell._on_normalization_fit_data_controls_commit, "value_throttled"
    )
    shell.normalization_fit_data_y_max_slider.param.watch(
        shell._on_normalization_fit_data_controls_commit, "value_throttled"
    )
    shell.normalization_fit_data_redesign_q_range_slider.param.watch(
        shell._on_normalization_fit_data_controls_change, "value"
    )
    shell.normalization_fit_data_redesign_vertical_range_slider.param.watch(
        shell._on_normalization_fit_data_controls_change, "value"
    )
    shell.normalization_fit_data_redesign_q_start_input.param.watch(
        shell._on_normalization_fit_data_redesign_numeric_input_change, "value"
    )
    shell.normalization_fit_data_redesign_q_end_input.param.watch(
        shell._on_normalization_fit_data_redesign_numeric_input_change, "value"
    )
    shell.normalization_fit_data_redesign_vertical_lower_input.param.watch(
        shell._on_normalization_fit_data_redesign_numeric_input_change, "value"
    )
    shell.normalization_fit_data_redesign_vertical_upper_input.param.watch(
        shell._on_normalization_fit_data_redesign_numeric_input_change, "value"
    )
    shell.normalization_fit_data_redesign_q_range_slider.param.watch(
        shell._on_normalization_fit_data_controls_commit, "value_throttled"
    )
    shell.normalization_fit_data_redesign_vertical_range_slider.param.watch(
        shell._on_normalization_fit_data_controls_commit, "value_throttled"
    )
    shell.self_lowq_selection_mode.param.watch(shell._on_self_lowq_controls_change, "value")
    shell.self_lowq_use_sliders.param.watch(shell._on_self_lowq_controls_change, "value")
    for name in (
        "self_lowq_q_tail_low",
        "self_lowq_q_tail_high",
        "self_lowq_min_percentile",
        "self_lowq_max_percentile",
        "self_lowq_q_min",
        "self_lowq_q_max",
        "self_lowq_y_min",
        "self_lowq_y_max",
    ):
        getattr(shell, name).param.watch(shell._on_self_lowq_controls_change, "value")

    shell.self_lowq_redesign_q_range_slider.param.watch(shell._on_self_lowq_controls_change, "value")
    shell.self_lowq_redesign_vertical_range_slider.param.watch(shell._on_self_lowq_controls_change, "value")
    shell.self_lowq_redesign_q_start_input.param.watch(shell._on_self_lowq_redesign_numeric_input_change, "value")
    shell.self_lowq_redesign_q_end_input.param.watch(shell._on_self_lowq_redesign_numeric_input_change, "value")
    shell.self_lowq_redesign_vertical_lower_input.param.watch(shell._on_self_lowq_redesign_numeric_input_change, "value")
    shell.self_lowq_redesign_vertical_upper_input.param.watch(shell._on_self_lowq_redesign_numeric_input_change, "value")
    shell.self_lowq_redesign_q_range_slider.param.watch(shell._on_self_lowq_controls_commit, "value_throttled")
    shell.self_lowq_redesign_vertical_range_slider.param.watch(shell._on_self_lowq_controls_commit, "value_throttled")

    shell.self_data_selection_selection_mode.param.watch(shell._on_self_data_selection_controls_change, "value")
    shell.self_data_selection_use_sliders.param.watch(shell._on_self_data_selection_controls_change, "value")
    for name in (
        "self_data_selection_q_tail_low",
        "self_data_selection_q_tail_high",
        "self_data_selection_min_percentile",
        "self_data_selection_max_percentile",
        "self_data_selection_q_min",
        "self_data_selection_q_max",
        "self_data_selection_y_min",
        "self_data_selection_y_max",
    ):
        getattr(shell, name).param.watch(shell._on_self_data_selection_controls_change, "value")

    shell.self_data_selection_redesign_q_range_slider.param.watch(shell._on_self_data_selection_controls_change, "value")
    shell.self_data_selection_redesign_vertical_range_slider.param.watch(shell._on_self_data_selection_controls_change, "value")
    shell.self_data_selection_redesign_q_start_input.param.watch(shell._on_self_data_selection_redesign_numeric_input_change, "value")
    shell.self_data_selection_redesign_q_end_input.param.watch(shell._on_self_data_selection_redesign_numeric_input_change, "value")
    shell.self_data_selection_redesign_vertical_lower_input.param.watch(shell._on_self_data_selection_redesign_numeric_input_change, "value")
    shell.self_data_selection_redesign_vertical_upper_input.param.watch(shell._on_self_data_selection_redesign_numeric_input_change, "value")
    shell.self_data_selection_redesign_q_range_slider.param.watch(shell._on_self_data_selection_controls_commit, "value_throttled")
    shell.self_data_selection_redesign_vertical_range_slider.param.watch(shell._on_self_data_selection_controls_commit, "value_throttled")

    # Self: Fit model
    shell.self_fit_params_suggest_button.on_click(shell._self_fit_params_suggest_initial_guess)
    shell.self_fit_params_run_button.on_click(shell._self_fit_params_run_fit)
    shell.self_fit_model_selector.param.watch(shell._on_self_fit_model_change, "value")
    shell.self_fit_params_bounds_toggle.param.watch(shell._on_self_fit_params_bounds_toggle_change, "value")
    for prefix, keys in (
        ("self_fit_params_vana", ("a0", "a1", "a2", "A", "lowQ", "Q0", "dQ")),
        ("self_fit_params_poly", ("a0", "a1", "a2", "a3", "a4")),
        ("self_fit_params_lorgau", ("f0", "eta", "sigma", "gamma", "bckg")),
    ):
        for key in keys:
            getattr(shell, f"{prefix}_{key}_fixed").param.watch(shell._on_self_fit_params_change, "value")
            getattr(shell, f"{prefix}_{key}_value").param.watch(shell._on_self_fit_params_change, "value")
            getattr(shell, f"{prefix}_{key}_min").param.watch(shell._on_self_fit_params_change, "value")
            getattr(shell, f"{prefix}_{key}_max").param.watch(shell._on_self_fit_params_change, "value")

    if hasattr(shell, "self_export_folder_input"):
        shell.self_export_folder_input.param.watch(shell._on_self_export_folder_change, "value")
    if hasattr(shell, "self_export_button"):
        shell.self_export_button.on_click(shell._prompt_self_export)
    if hasattr(shell, "self_export_confirm_button"):
        shell.self_export_confirm_button.on_click(shell._confirm_self_export)
    if hasattr(shell, "self_export_cancel_button"):
        shell.self_export_cancel_button.on_click(shell._cancel_self_export)

    # Normalization fit-parameter editor (Slice 1: persistence only).
    shell.normalization_fit_params_A_pinned.param.watch(shell._on_normalization_fit_params_change, "value")
    for key in ("a0", "a1", "a2", "A", "lowQ", "Q0", "dQ"):
        getattr(shell, f"normalization_fit_params_{key}_value").param.watch(
            shell._on_normalization_fit_params_change, "value"
        )
        getattr(shell, f"normalization_fit_params_{key}_min").param.watch(
            shell._on_normalization_fit_params_change, "value"
        )
        getattr(shell, f"normalization_fit_params_{key}_max").param.watch(
            shell._on_normalization_fit_params_change, "value"
        )
    shell.project_folder_browse_button.on_click(shell._toggle_project_folder_browser)
    shell.project_folder_native_browse_button.on_click(shell._choose_project_folder_native)
    shell.project_folder_confirm_button.on_click(shell._confirm_project_folder_browser)
    shell.project_folder_cancel_button.on_click(shell._cancel_project_folder_browser)
    shell.manual_project_file_browse_button.on_click(
        shell._toggle_manual_project_file_browser
    )
    shell.manual_project_file_native_browse_button.on_click(
        shell._choose_manual_project_file_native
    )
    shell.manual_project_file_confirm_button.on_click(
        shell._confirm_manual_project_file_browser
    )
    shell.manual_project_file_cancel_button.on_click(
        shell._cancel_manual_project_file_browser
    )
