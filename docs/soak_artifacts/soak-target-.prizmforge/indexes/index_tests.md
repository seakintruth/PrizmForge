Generated: 2026-09-07T12:34:00Z

# Test suite index

Root: `C:\git\home\user\jeremy.gerdes\github\PrizmForge-Soak\Soak5-target\PrizmForge`

Standalone index for context (no full source dump).

## Index: Test suite

Test modules and discovered test callables / helpers.

### `tests/__init__.py`

_No symbols parsed._

### `tests/conftest.py`

**Other symbols**

| Kind | Qualname | Line |
|------|----------|------|
| function | `tests.conftest._force_test_safe_config` | 37 |
| function | `tests.conftest._patch_get_config_everywhere` | 85 |
| function | `tests.conftest._duration_report_path` | 101 |
| function | `tests.conftest.pytest_configure` | 114 |
| function | `tests.conftest.pytest_runtest_logreport` | 120 |
| function | `tests.conftest.pytest_sessionstart` | 154 |
| function | `tests.conftest.pytest_sessionfinish` | 159 |
| function | `tests.conftest._isolate_prizmforge_workspace` | 208 |
| function | `tests.conftest.temp_db` | 284 |
| function | `tests.conftest.mock_minimal_config` | 314 |
| function | `tests.conftest.isolated_project` | 366 |
| function | `tests.conftest.capsys_and_temp_db` | 382 |
| function | `tests.conftest.mock_openai_chat` | 388 |
| function | `tests.conftest.mock_llm` | 421 |
| function | `tests.conftest.mock_llm_patched` | 431 |

### `tests/integration/test_edit_workflows.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| function | `tests.integration.test_edit_workflows._guids_for` | 28 |
| function | `tests.integration.test_edit_workflows._approve` | 44 |
| function | `tests.integration.test_edit_workflows._content` | 54 |
| class | `tests.integration.test_edit_workflows.TestFindReplaceWorkflow` | 68 |
| method | `tests.integration.test_edit_workflows.TestFindReplaceWorkflow.test_proposal_approve_apply` | 69 |
| class | `tests.integration.test_edit_workflows.TestFullReplaceWorkflow` | 106 |
| method | `tests.integration.test_edit_workflows.TestFullReplaceWorkflow.test_proposal_approve_apply` | 107 |
| class | `tests.integration.test_edit_workflows.TestGuidReplaceWorkflow` | 139 |
| method | `tests.integration.test_edit_workflows.TestGuidReplaceWorkflow.test_proposal_approve_apply` | 140 |
| class | `tests.integration.test_edit_workflows.TestDiffWorkflow` | 173 |
| method | `tests.integration.test_edit_workflows.TestDiffWorkflow.test_proposal_approve_apply` | 174 |
| class | `tests.integration.test_edit_workflows.TestModeSelectionWorkflow` | 215 |
| method | `tests.integration.test_edit_workflows.TestModeSelectionWorkflow.test_tshirt_and_fallback_chain` | 216 |
| class | `tests.integration.test_edit_workflows.TestValidationWorkflow` | 237 |
| method | `tests.integration.test_edit_workflows.TestValidationWorkflow.test_empty_ops_and_recovery_signal` | 238 |
| class | `tests.integration.test_edit_workflows.TestMockedAgentWorkflow` | 260 |
| method | `tests.integration.test_edit_workflows.TestMockedAgentWorkflow.test_orchestrator_developer_reviewer_sequence` | 261 |
| method | `tests.integration.test_edit_workflows.TestMockedAgentWorkflow.test_developer_invalid_then_valid_fallback` | 332 |
| method | `tests.integration.test_edit_workflows.TestMockedAgentWorkflow.test_mocked_developer_output_creates_proposal` | 372 |

### `tests/integration/test_file_editing_pipeline.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| class | `tests.integration.test_file_editing_pipeline.TestFileEditingPipeline` | 14 |
| method | `tests.integration.test_file_editing_pipeline.TestFileEditingPipeline.test_01_initialize_simple_file` | 17 |
| method | `tests.integration.test_file_editing_pipeline.TestFileEditingPipeline.test_02_initialize_multiline_file` | 26 |
| method | `tests.integration.test_file_editing_pipeline.TestFileEditingPipeline.test_03_single_line_replacement` | 39 |
| method | `tests.integration.test_file_editing_pipeline.TestFileEditingPipeline.test_04_range_replacement` | 82 |
| method | `tests.integration.test_file_editing_pipeline.TestFileEditingPipeline.test_05_insert_operations` | 133 |
| method | `tests.integration.test_file_editing_pipeline.TestFileEditingPipeline.test_06_delete_operations` | 171 |
| method | `tests.integration.test_file_editing_pipeline.TestFileEditingPipeline.test_07_missing_rationale_autofix` | 208 |

### `tests/integration/test_file_write_log_timestamps.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| function | `tests.integration.test_file_write_log_timestamps.test_materialize_populates_file_write_log_timestamps` | 6 |

### `tests/integration/test_golden_path.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| function | `tests.integration.test_golden_path.run_governed_edit_once` | 27 |
| function | `tests.integration.test_golden_path._init_file` | 135 |
| class | `tests.integration.test_golden_path.TestGoldenPathFindReplace` | 150 |
| method | `tests.integration.test_golden_path.TestGoldenPathFindReplace.test_orchestrator_developer_reviewer_materialize` | 151 |
| class | `tests.integration.test_golden_path.TestGoldenPathFallback` | 217 |
| method | `tests.integration.test_golden_path.TestGoldenPathFallback.test_invalid_json_then_find_replace_succeeds` | 218 |
| class | `tests.integration.test_golden_path.TestGoldenPathFullReplace` | 290 |
| method | `tests.integration.test_golden_path.TestGoldenPathFullReplace.test_small_file_full_replace` | 291 |
| class | `tests.integration.test_golden_path.TestGoldenPathCounters` | 344 |
| method | `tests.integration.test_golden_path.TestGoldenPathCounters.test_failed_validation_increments_edit_failures` | 345 |

### `tests/integration/test_prizmforge_architecture.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| function | `tests.integration.test_prizmforge_architecture.memory_db` | 26 |
| function | `tests.integration.test_prizmforge_architecture.test_resolve_task_description_scalar_precedence` | 86 |
| function | `tests.integration.test_prizmforge_architecture.test_build_generation_prompt_fallback_injection` | 102 |
| function | `tests.integration.test_prizmforge_architecture.test_closed_loop_reviewer_feedback` | 125 |
| function | `tests.integration.test_prizmforge_architecture.test_sql_response_exact_matching` | 161 |
| function | `tests.integration.test_prizmforge_architecture.test_export_db_full_scope` | 213 |

### `tests/integration/test_reporting_counters.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| function | `tests.integration.test_reporting_counters.counter_env` | 14 |
| function | `tests.integration.test_reporting_counters.test_files_modified_matches_applied_proposals` | 53 |

### `tests/integration/test_run_task_cycle.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| function | `tests.integration.test_run_task_cycle._install_cycle_config` | 21 |
| function | `tests.integration.test_run_task_cycle.cycle_env` | 70 |
| function | `tests.integration.test_run_task_cycle.test_run_task_cycle_find_replace` | 100 |
| function | `tests.integration.test_run_task_cycle.test_run_task_cycle_multi_turn_then_complete` | 160 |
| function | `tests.integration.test_run_task_cycle.test_run_task_cycle_reviewer_reject` | 218 |

### `tests/integration/test_unattended_acceptance.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| function | `tests.integration.test_unattended_acceptance.accept_env` | 20 |
| function | `tests.integration.test_unattended_acceptance.test_seed_task_materializes_under_project_directory` | 70 |

### `tests/integration/test_unattended_with_mock.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| function | `tests.integration.test_unattended_with_mock.test_unattended_run_with_mock_using_repo_root` | 18 |

### `tests/mocks/openai.py`

**Other symbols**

| Kind | Qualname | Line |
|------|----------|------|
| function | `tests.mocks.openai.register_call_agent_patch_target` | 30 |
| function | `tests.mocks.openai.make_chat_completion_payload` | 42 |
| function | `tests.mocks.openai.make_requests_response` | 71 |
| function | `tests.mocks.openai.mock_openai_chat_completion` | 93 |
| class | `tests.mocks.openai.LLMCallRecord` | 114 |
| class | `tests.mocks.openai.MockLLM` | 123 |
| method | `tests.mocks.openai.MockLLM.set_response` | 143 |
| method | `tests.mocks.openai.MockLLM.set_responses` | 149 |
| method | `tests.mocks.openai.MockLLM.set_default` | 156 |
| method | `tests.mocks.openai.MockLLM._next` | 160 |
| method | `tests.mocks.openai.MockLLM.handler` | 171 |
| method | `tests.mocks.openai.MockLLM.endpoint_handler` | 193 |
| method | `tests.mocks.openai.MockLLM.patch_call_agent` | 221 |
| method | `tests.mocks.openai.MockLLM.patch_call_endpoint` | 245 |
| method | `tests.mocks.openai.MockLLM.patch_all` | 249 |
| method | `tests.mocks.openai.MockLLM.calls_for` | 262 |
| method | `tests.mocks.openai.MockLLM.reset` | 265 |

### `tests/test_governed_editing.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| function | `tests.test_governed_editing._compute_content_hash` | 27 |
| function | `tests.test_governed_editing.db` | 32 |
| function | `tests.test_governed_editing.sample_file` | 67 |
| function | `tests.test_governed_editing.test_apply_replace_block` | 94 |
| function | `tests.test_governed_editing.test_optimistic_concurrency_conflict` | 128 |
| function | `tests.test_governed_editing.test_insert_after_with_none_for_empty_file` | 165 |
| function | `tests.test_governed_editing.test_delete_lines` | 189 |
| function | `tests.test_governed_editing.test_full_proposal_lifecycle` | 222 |
| function | `tests.test_governed_editing.test_delete_lines_single_line_only_start_guid` | 256 |
| function | `tests.test_governed_editing.test_delete_lines_nonexistent_start_guid` | 292 |
| function | `tests.test_governed_editing.test_replace_block_with_end_line_guid` | 324 |
| function | `tests.test_governed_editing.test_insert_after_last_line` | 359 |

### `tests/test_schema.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| function | `tests.test_schema.test_init_db_creates_all_tables` | 13 |

### `tests/test_smoke.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| function | `tests.test_smoke.test_imports` | 7 |
| function | `tests.test_smoke.test_editpayload_validation` | 18 |
| function | `tests.test_smoke.test_config_loading` | 41 |

### `tests/unit/test_agent_execution.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| class | `tests.unit.test_agent_execution.TestAgentExecutionBasic` | 8 |
| method | `tests.unit.test_agent_execution.TestAgentExecutionBasic.test_call_agent_developer_does_not_crash` | 11 |
| method | `tests.unit.test_agent_execution.TestAgentExecutionBasic.test_call_agent_unknown_agent_via_mock` | 23 |
| method | `tests.unit.test_agent_execution.TestAgentExecutionBasic.test_sequential_orchestrator_turns` | 37 |

### `tests/unit/test_agent_schemas.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| function | `tests.unit.test_agent_schemas.test_validate_missing_required_fields` | 19 |
| function | `tests.unit.test_agent_schemas.test_validate_orchestrator_complete` | 27 |
| function | `tests.unit.test_agent_schemas.test_validate_array_not_list` | 40 |
| function | `tests.unit.test_agent_schemas.test_validate_array_item_missing_core_fields` | 52 |
| function | `tests.unit.test_agent_schemas.test_validate_array_item_complete` | 65 |
| function | `tests.unit.test_agent_schemas.test_validate_array_item_not_object` | 85 |
| function | `tests.unit.test_agent_schemas.test_text_agent_schema_always_valid` | 97 |
| function | `tests.unit.test_agent_schemas.test_get_schema_explicit` | 110 |
| function | `tests.unit.test_agent_schemas.test_get_schema_fallback_for_security_reviewer` | 118 |
| function | `tests.unit.test_agent_schemas.test_get_schema_fallback_for_performance_analyzer` | 126 |
| function | `tests.unit.test_agent_schemas.test_get_schema_unknown_returns_none` | 133 |
| function | `tests.unit.test_agent_schemas.test_is_using_fallback` | 137 |
| function | `tests.unit.test_agent_schemas.test_list_agents_sorted` | 148 |
| function | `tests.unit.test_agent_schemas.test_get_agents_by_table` | 156 |
| function | `tests.unit.test_agent_schemas.test_build_prompt_schema_includes_priority_and_category` | 168 |
| function | `tests.unit.test_agent_schemas.test_build_prompt_schema_orchestrator_no_array` | 181 |
| function | `tests.unit.test_agent_schemas.test_build_prompt_schema_optional_fields_comment` | 189 |
| function | `tests.unit.test_agent_schemas.test_validate_agent_response_orchestrator` | 201 |
| function | `tests.unit.test_agent_schemas.test_validate_agent_response_unknown_agent_passes` | 214 |
| function | `tests.unit.test_agent_schemas.test_validate_agent_response_missing_fields` | 220 |

### `tests/unit/test_archival.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| function | `tests.unit.test_archival.test_archive_raw_response_success` | 6 |
| function | `tests.unit.test_archival.test_archive_raw_response_parse_failure` | 30 |
| function | `tests.unit.test_archival.test_archive_raw_response_shell_step_columns` | 48 |
| function | `tests.unit.test_archival.test_archive_raw_response_old_schema_migrated` | 74 |

### `tests/unit/test_archivist_context.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| function | `tests.unit.test_archivist_context.test_needs_context_restore_keywords` | 11 |
| function | `tests.unit.test_archivist_context.test_save_message_archive_inserts_row` | 20 |
| function | `tests.unit.test_archivist_context.test_archive_old_messages_requires_threshold` | 58 |
| function | `tests.unit.test_archivist_context.test_save_message_archive_skips_junk_on_parse_fail` | 89 |
| function | `tests.unit.test_archivist_context.test_archive_old_messages_keeps_originals_when_archivist_junk` | 118 |
| function | `tests.unit.test_archivist_context.test_message_archiving_is_batched_2020_5` | 152 |
| function | `tests.unit.test_archivist_context.test_unparseable_batch_keeps_originals_but_saved_batch_deleted` | 191 |
| function | `tests.unit.test_archivist_context._insert_conversations` | 235 |
| function | `tests.unit.test_archivist_context.test_conversation_archiving_prunes_saved_batches` | 249 |
| function | `tests.unit.test_archivist_context.test_conversation_archiving_keeps_unsaved_batch` | 271 |
| function | `tests.unit.test_archivist_context._sample_msg` | 304 |
| function | `tests.unit.test_archivist_context._sample_conv` | 319 |
| function | `tests.unit.test_archivist_context.test_all_archive_prompts_carry_json_output_contract` | 324 |

### `tests/unit/test_backlog_growth.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| function | `tests.unit.test_backlog_growth._insert_direct` | 29 |
| class | `tests.unit.test_backlog_growth.TestDedupeOnInsert` | 50 |
| method | `tests.unit.test_backlog_growth.TestDedupeOnInsert.test_100_near_duplicate_findings_kept_rows` | 51 |
| method | `tests.unit.test_backlog_growth.TestDedupeOnInsert.test_distinct_messages_stay_separate` | 72 |
| method | `tests.unit.test_backlog_growth.TestDedupeOnInsert.test_dedupe_respects_dedupe_window` | 97 |
| method | `tests.unit.test_backlog_growth.TestDedupeOnInsert.test_dedupe_disabled_keeps_every_row` | 122 |
| class | `tests.unit.test_backlog_growth.TestTierPolicy` | 140 |
| method | `tests.unit.test_backlog_growth.TestTierPolicy.test_resolve_boundaries` | 141 |
| method | `tests.unit.test_backlog_growth.TestTierPolicy.test_config_overrides_tiers` | 149 |
| method | `tests.unit.test_backlog_growth.TestTierPolicy.test_freeze_policy_disables_feeders` | 156 |
| method | `tests.unit.test_backlog_growth.TestTierPolicy.test_hard_policy_disables_feeders` | 162 |
| method | `tests.unit.test_backlog_growth.TestTierPolicy.test_soft_and_normal_keep_feeders` | 167 |
| method | `tests.unit.test_backlog_growth.TestTierPolicy.test_resource_controller_freeze_at_unaddressed_200` | 171 |
| method | `tests.unit.test_backlog_growth.TestTierPolicy.test_seed_rows_do_not_push_tier_to_freeze` | 190 |
| method | `tests.unit.test_backlog_growth.TestTierPolicy.test_burn_rate_above_warning_escalates_to_moderate` | 212 |
| class | `tests.unit.test_backlog_growth.TestStuckIdTracking` | 247 |
| method | `tests.unit.test_backlog_growth.TestStuckIdTracking.test_repeated_targeting_marks_stuck_and_skips_it` | 248 |
| class | `tests.unit.test_backlog_growth.TestReportMetrics` | 263 |
| method | `tests.unit.test_backlog_growth.TestReportMetrics.test_backlog_metrics_include_required_keys` | 264 |
| method | `tests.unit.test_backlog_growth.TestReportMetrics.test_pending_addressed_and_critical_do_not_break_metrics` | 283 |
| method | `tests.unit.test_backlog_growth.TestReportMetrics.test_seed_feedback_excluded_from_unaddressed_count` | 299 |
| method | `tests.unit.test_backlog_growth.TestReportMetrics.test_reporter_gather_embeds_backlog_metrics` | 322 |
| method | `tests.unit.test_backlog_growth.TestReportMetrics.test_reporter_run_metrics_success_ratio_and_git_fails` | 343 |
| method | `tests.unit.test_backlog_growth.TestReportMetrics.test_reporter_counts_circuit_opens` | 383 |

### `tests/unit/test_backlog_override.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| function | `tests.unit.test_backlog_override._seed_feedback` | 13 |
| function | `tests.unit.test_backlog_override.test_force_override_above_threshold` | 34 |
| function | `tests.unit.test_backlog_override.test_redirect_background_when_small_backlog` | 51 |
| function | `tests.unit.test_backlog_override.test_no_override_when_empty_and_developer` | 69 |
| function | `tests.unit.test_backlog_override.test_critical_sorted_first` | 81 |

### `tests/unit/test_backlog_redirect_dispatch.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| class | `tests.unit.test_backlog_redirect_dispatch._FakeRCDecision` | 8 |
| class | `tests.unit.test_backlog_redirect_dispatch._FakeRC` | 12 |
| method | `tests.unit.test_backlog_redirect_dispatch._FakeRC.get_current_decision` | 13 |
| function | `tests.unit.test_backlog_redirect_dispatch.test_backlog_processing_redirects_to_developer` | 17 |

### `tests/unit/test_base_agent.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| class | `tests.unit.test_base_agent.TestBaseAgentWithMock` | 11 |
| method | `tests.unit.test_base_agent.TestBaseAgentWithMock.test_call_agent_returns_scripted_response` | 14 |
| method | `tests.unit.test_base_agent.TestBaseAgentWithMock.test_call_agent_json_payload` | 27 |
| method | `tests.unit.test_base_agent.TestBaseAgentWithMock.test_per_agent_responses` | 49 |
| method | `tests.unit.test_base_agent.TestBaseAgentWithMock.test_http_layer_mock` | 61 |

### `tests/unit/test_call_endpoint_rate_limit.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| function | `tests.unit.test_call_endpoint_rate_limit._resp` | 35 |
| class | `tests.unit.test_call_endpoint_rate_limit._Choice` | 45 |
| class | `tests.unit.test_call_endpoint_rate_limit._FakeEndpoint` | 50 |
| method | `tests.unit.test_call_endpoint_rate_limit._FakeEndpoint.__init__` | 55 |
| method | `tests.unit.test_call_endpoint_rate_limit._FakeEndpoint.extract_response` | 63 |
| class | `tests.unit.test_call_endpoint_rate_limit._FakeManager` | 67 |
| method | `tests.unit.test_call_endpoint_rate_limit._FakeManager.__init__` | 68 |
| method | `tests.unit.test_call_endpoint_rate_limit._FakeManager.normalize_model_reference` | 71 |
| method | `tests.unit.test_call_endpoint_rate_limit._FakeManager.validate_model` | 74 |
| method | `tests.unit.test_call_endpoint_rate_limit._FakeManager.build_payload` | 77 |
| method | `tests.unit.test_call_endpoint_rate_limit._FakeManager.get_fallback_model` | 85 |
| method | `tests.unit.test_call_endpoint_rate_limit._FakeManager.get_api_key` | 88 |
| class | `tests.unit.test_call_endpoint_rate_limit._RecordingHealth` | 92 |
| method | `tests.unit.test_call_endpoint_rate_limit._RecordingHealth.__init__` | 93 |
| method | `tests.unit.test_call_endpoint_rate_limit._RecordingHealth.is_available` | 96 |
| method | `tests.unit.test_call_endpoint_rate_limit._RecordingHealth.time_until_available` | 99 |
| method | `tests.unit.test_call_endpoint_rate_limit._RecordingHealth.mark_success` | 102 |
| method | `tests.unit.test_call_endpoint_rate_limit._RecordingHealth.mark_failure` | 105 |
| function | `tests.unit.test_call_endpoint_rate_limit.call_endpoint_env` | 110 |
| function | `tests.unit.test_call_endpoint_rate_limit.test_429_applies_aimd_backoff_then_ramps_on_success` | 130 |
| function | `tests.unit.test_call_endpoint_rate_limit.test_429_with_invalid_retry_after_header_defaults_120` | 152 |
| function | `tests.unit.test_call_endpoint_rate_limit.test_429_long_cooldown_marks_unavailable_and_uses_backoff` | 169 |
| function | `tests.unit.test_call_endpoint_rate_limit.test_429_dumps_body_and_redacts_auth` | 188 |
| function | `tests.unit.test_call_endpoint_rate_limit.test_local_latch_skip_prints_dump_without_calling_api` | 218 |
| class | `tests.unit.test_call_endpoint_rate_limit._LatchesAfterFailureHealth` | 253 |
| method | `tests.unit.test_call_endpoint_rate_limit._LatchesAfterFailureHealth.__init__` | 254 |
| method | `tests.unit.test_call_endpoint_rate_limit._LatchesAfterFailureHealth.is_available` | 261 |
| method | `tests.unit.test_call_endpoint_rate_limit._LatchesAfterFailureHealth.time_until_available` | 264 |
| method | `tests.unit.test_call_endpoint_rate_limit._LatchesAfterFailureHealth.mark_success` | 267 |
| method | `tests.unit.test_call_endpoint_rate_limit._LatchesAfterFailureHealth.mark_failure` | 270 |
| function | `tests.unit.test_call_endpoint_rate_limit.test_429_dump_prints_once_per_latch_then_skip_is_one_line` | 275 |
| function | `tests.unit.test_call_endpoint_rate_limit.test_429_quota_ms_reset_parks_and_does_not_hop` | 307 |
| function | `tests.unit.test_call_endpoint_rate_limit.test_429_quota_body_token_parks_and_does_not_hop` | 344 |
| function | `tests.unit.test_call_endpoint_rate_limit.test_429_quota_short_reset_sleeps_to_reset_then_retries` | 374 |
| function | `tests.unit.test_call_endpoint_rate_limit.test_429_burst_with_ratelimit_headers_not_quota` | 396 |
| function | `tests.unit.test_call_endpoint_rate_limit.test_skip_path_all_parked_sleeps_bounded_backoff` | 424 |
| class | `tests.unit.test_call_endpoint_rate_limit._FallbackManager` | 450 |
| method | `tests.unit.test_call_endpoint_rate_limit._FallbackManager.__init__` | 451 |
| method | `tests.unit.test_call_endpoint_rate_limit._FallbackManager.normalize_model_reference` | 457 |
| method | `tests.unit.test_call_endpoint_rate_limit._FallbackManager.get_fallback_model` | 463 |
| function | `tests.unit.test_call_endpoint_rate_limit.test_503_retry_after_90_retries_same_and_succeeds` | 474 |
| function | `tests.unit.test_call_endpoint_rate_limit.test_429_retry_after_42534_falls_back_no_sleep` | 491 |
| function | `tests.unit.test_call_endpoint_rate_limit.test_503_retry_after_600_retries_once` | 510 |
| function | `tests.unit.test_call_endpoint_rate_limit.test_503_retry_after_601_falls_back_no_wait` | 526 |
| function | `tests.unit.test_call_endpoint_rate_limit.test_503_no_header_default_300_retries_once` | 545 |
| function | `tests.unit.test_call_endpoint_rate_limit.test_503_retry_then_second_503_falls_back` | 561 |
| function | `tests.unit.test_call_endpoint_rate_limit.test_503_http_date_retry_after_honored` | 581 |
| function | `tests.unit.test_call_endpoint_rate_limit.test_500_retries_with_legacy_backoff_not_503_default` | 598 |
| function | `tests.unit.test_call_endpoint_rate_limit.test_502_falls_back_after_retries_exhausted` | 619 |
| function | `tests.unit.test_call_endpoint_rate_limit.test_concurrent_agents_observe_shared_latch_bound_backoff` | 646 |
| function | `tests.unit.test_call_endpoint_rate_limit.test_latched_primary_falls_back_to_healthy_endpoint` | 672 |
| function | `tests.unit.test_call_endpoint_rate_limit.test_successful_retry_does_not_record_failure` | 729 |
| function | `tests.unit.test_call_endpoint_rate_limit.test_token_budget_overflow_no_fallback_records_failure` | 752 |
| function | `tests.unit.test_call_endpoint_rate_limit.test_all_parked_no_alternate_records_failure` | 772 |
| function | `tests.unit.test_call_endpoint_rate_limit.test_classify_nonempty_extract_never_classified_from_raw_substrings` | 809 |
| function | `tests.unit.test_call_endpoint_rate_limit.test_classify_empty_extract_detects_structured_policy_signals` | 830 |
| function | `tests.unit.test_call_endpoint_rate_limit.test_200_with_safetyratings_and_text_still_returns_text` | 847 |
| function | `tests.unit.test_call_endpoint_rate_limit.test_empty_policy_200_marks_failure_and_falls_back` | 872 |

### `tests/unit/test_checkpoint_idle.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| function | `tests.unit.test_checkpoint_idle.test_should_checkpoint_first_always_true` | 10 |
| function | `tests.unit.test_checkpoint_idle.test_should_checkpoint_respects_interval` | 15 |
| function | `tests.unit.test_checkpoint_idle.test_save_and_load_checkpoint_roundtrip` | 25 |
| function | `tests.unit.test_checkpoint_idle.test_unattended_counts_file_modifications_for_task` | 48 |
| function | `tests.unit.test_checkpoint_idle.test_min_idle_config_defaults_and_override` | 81 |

### `tests/unit/test_cli_commands.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| class | `tests.unit.test_cli_commands.TestHelpAndStatus` | 24 |
| method | `tests.unit.test_cli_commands.TestHelpAndStatus.test_cmd_help_mentions_status` | 25 |
| method | `tests.unit.test_cli_commands.TestHelpAndStatus.test_cmd_help_lists_commands` | 30 |
| method | `tests.unit.test_cli_commands.TestHelpAndStatus.test_cmd_status_runs` | 36 |
| method | `tests.unit.test_cli_commands.TestHelpAndStatus.test_cmd_history_runs` | 41 |
| method | `tests.unit.test_cli_commands.TestHelpAndStatus.test_cmd_review_status_runs` | 44 |
| method | `tests.unit.test_cli_commands.TestHelpAndStatus.test_cmd_files_runs` | 47 |
| class | `tests.unit.test_cli_commands.TestEndpointsCommands` | 51 |
| method | `tests.unit.test_cli_commands.TestEndpointsCommands.test_cmd_endpoints` | 52 |
| method | `tests.unit.test_cli_commands.TestEndpointsCommands.test_cmd_endpoint_health` | 57 |
| method | `tests.unit.test_cli_commands.TestEndpointsCommands.test_cmd_fallback_stats` | 63 |
| class | `tests.unit.test_cli_commands.TestInitCommand` | 70 |
| method | `tests.unit.test_cli_commands.TestInitCommand.test_cmd_init_creates_project_dir` | 72 |
| class | `tests.unit.test_cli_commands.TestExportAndReports` | 93 |
| method | `tests.unit.test_cli_commands.TestExportAndReports.test_cmd_list_exports` | 94 |
| method | `tests.unit.test_cli_commands.TestExportAndReports.test_cmd_reports` | 100 |
| method | `tests.unit.test_cli_commands.TestExportAndReports.test_cmd_json_parse_stats` | 106 |
| class | `tests.unit.test_cli_commands.TestTaskRunnerMockedFromCLILayer` | 113 |
| method | `tests.unit.test_cli_commands.TestTaskRunnerMockedFromCLILayer.test_run_task_cycle_can_be_mocked` | 114 |
| method | `tests.unit.test_cli_commands.TestTaskRunnerMockedFromCLILayer.test_interactive_imports_run_task_cycle` | 130 |
| class | `tests.unit.test_cli_commands.TestCLIModes` | 136 |
| method | `tests.unit.test_cli_commands.TestCLIModes.test_cli_mode_enum` | 137 |
| method | `tests.unit.test_cli_commands.TestCLIModes.test_get_cli_mode_from_config_default` | 155 |
| class | `tests.unit.test_cli_commands.TestMainModule` | 162 |
| method | `tests.unit.test_cli_commands.TestMainModule.test_main_module_importable` | 163 |
| function | `tests.unit.test_cli_commands.test_cmd_init_creates_and_updates_gitignore` | 169 |
| function | `tests.unit.test_cli_commands.test_quote_identifier_escapes_embedded_quotes` | 198 |
| function | `tests.unit.test_cli_commands.test_export_keyword_table_name` | 203 |

### `tests/unit/test_cold_init_ingest.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| function | `tests.unit.test_cold_init_ingest._project` | 13 |
| function | `tests.unit.test_cold_init_ingest.test_initialize_file_lines_executemany_reconstructs` | 21 |
| function | `tests.unit.test_cold_init_ingest.test_cmd_init_does_not_use_file_editing_db_connection` | 31 |
| function | `tests.unit.test_cold_init_ingest.test_cmd_init_restores_runtime_pragmas` | 50 |
| function | `tests.unit.test_cold_init_ingest.test_cmd_init_does_not_open_per_file_writers` | 72 |
| function | `tests.unit.test_cold_init_ingest.test_cmd_init_hash_skip_second_pass` | 93 |

### `tests/unit/test_config.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| function | `tests.unit.test_config.test_normalize_path_empty_returns_dot` | 26 |
| function | `tests.unit.test_config.test_normalize_path_absolute_unix` | 31 |
| function | `tests.unit.test_config.test_normalize_path_relative_uses_package_root_by_default` | 39 |
| function | `tests.unit.test_config.test_normalize_path_relative_respects_base` | 44 |
| function | `tests.unit.test_config.test_normalize_path_home_expand` | 51 |
| function | `tests.unit.test_config.test_normalize_path_mixed_slashes` | 69 |
| function | `tests.unit.test_config.test_find_config_file_in_cwd` | 87 |
| function | `tests.unit.test_config.test_find_config_file_in_parent` | 95 |
| function | `tests.unit.test_config.test_find_config_file_defaults_to_package_root_when_missing` | 105 |
| function | `tests.unit.test_config.test_get_repo_root_falls_back_to_package_root` | 117 |
| function | `tests.unit.test_config.test_get_repo_root_from_config_location` | 126 |
| function | `tests.unit.test_config.test_load_config_project_directory_ignores_cwd` | 133 |
| function | `tests.unit.test_config.test_load_config_reads_structured_api_keys` | 154 |
| function | `tests.unit.test_config.test_load_config_missing_api_keys_is_empty` | 162 |
| function | `tests.unit.test_config.test_load_config_rejects_unstructured_api_keys` | 173 |
| function | `tests.unit.test_config.test_get_config_is_cached_until_reload` | 180 |
| function | `tests.unit.test_config.test_ensure_project_directory_creates` | 204 |
| function | `tests.unit.test_config.test_ensure_project_directory_absolute` | 219 |
| function | `tests.unit.test_config.test_validate_config_requires_project_directory` | 238 |
| function | `tests.unit.test_config.test_validate_config_rejects_non_string_project_directory` | 243 |
| function | `tests.unit.test_config.test_validate_config_accepts_minimal` | 248 |
| function | `tests.unit.test_config.test_validate_config_rejects_unknown_file_editing_method` | 256 |
| function | `tests.unit.test_config.test_validate_config_rejects_bad_preferred_modes` | 266 |
| function | `tests.unit.test_config.test_validate_config_rejects_unknown_preferred_mode` | 276 |
| function | `tests.unit.test_config.test_validate_config_rejects_bad_threshold` | 286 |
| function | `tests.unit.test_config.test_validate_config_accepts_known_modes` | 296 |
| function | `tests.unit.test_config.test_validate_config_rejects_bad_content_safety_type` | 315 |
| function | `tests.unit.test_config.test_validate_config_rejects_non_bool_disallow_binary` | 325 |
| function | `tests.unit.test_config._slashed_cfg` | 340 |
| function | `tests.unit.test_config.test_validate_config_accepts_slashed_model_ids` | 372 |
| function | `tests.unit.test_config.test_validate_config_accepts_bare_slashed_model_id` | 377 |
| function | `tests.unit.test_config.test_validate_config_rejects_unknown_slashed_reference` | 385 |
| function | `tests.unit.test_config.test_validate_config_rejects_ambiguous_bare_id_without_prefix` | 392 |

### `tests/unit/test_content_safety.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| function | `tests.unit.test_content_safety.test_rejects_msi_ole_magic` | 12 |
| function | `tests.unit.test_content_safety.test_normalize_ext_defaults` | 20 |
| function | `tests.unit.test_content_safety.test_rejects_pe_mz_header` | 30 |
| function | `tests.unit.test_content_safety.test_rejects_msi_extension_even_if_text` | 38 |
| function | `tests.unit.test_content_safety.test_rejects_exe_extension` | 45 |
| function | `tests.unit.test_content_safety.test_allows_powershell_script_text` | 52 |
| function | `tests.unit.test_content_safety.test_allows_bat_cmd_js_text` | 58 |
| function | `tests.unit.test_content_safety.test_allows_normal_source` | 66 |
| function | `tests.unit.test_content_safety.test_full_replace_rejects_binary` | 72 |
| function | `tests.unit.test_content_safety.test_empty_blocked_extensions_allows_msi_path_text` | 90 |
| function | `tests.unit.test_content_safety.test_custom_blocked_list` | 104 |
| function | `tests.unit.test_content_safety.test_disallow_binary_content_false` | 118 |

### `tests/unit/test_context_limit_resolution.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| function | `tests.unit.test_context_limit_resolution._patch_env` | 7 |
| function | `tests.unit.test_context_limit_resolution.test_resolves_nested_endpoint_model` | 15 |
| function | `tests.unit.test_context_limit_resolution.test_no_warning_for_known_model_without_explicit_limit` | 29 |
| function | `tests.unit.test_context_limit_resolution.test_unknown_model_still_warns` | 43 |

### `tests/unit/test_context_manager.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| class | `tests.unit.test_context_manager.TestContextManagerBasic` | 15 |
| method | `tests.unit.test_context_manager.TestContextManagerBasic.test_context_manager_singleton` | 18 |
| method | `tests.unit.test_context_manager.TestContextManagerBasic.test_context_manager_has_config` | 25 |
| method | `tests.unit.test_context_manager.TestContextManagerBasic.test_model_limits_loaded` | 31 |
| class | `tests.unit.test_context_manager.TestModelContextLimits` | 39 |
| method | `tests.unit.test_context_manager.TestModelContextLimits.test_get_model_context_limit_known_model` | 42 |
| method | `tests.unit.test_context_manager.TestModelContextLimits.test_get_model_context_limit_unknown_model` | 52 |
| method | `tests.unit.test_context_manager.TestModelContextLimits.test_get_model_context_limit_none` | 60 |
| class | `tests.unit.test_context_manager.TestGetPrioritizedFilesFast` | 69 |
| method | `tests.unit.test_context_manager.TestGetPrioritizedFilesFast.test_get_prioritized_files_empty_db` | 72 |
| method | `tests.unit.test_context_manager.TestGetPrioritizedFilesFast.test_get_prioritized_files_with_limit` | 80 |
| method | `tests.unit.test_context_manager.TestGetPrioritizedFilesFast.test_get_prioritized_files_invalid_limit` | 109 |
| class | `tests.unit.test_context_manager.TestBuildOrchestratorContext` | 122 |
| method | `tests.unit.test_context_manager.TestBuildOrchestratorContext.test_build_context_basic` | 125 |
| method | `tests.unit.test_context_manager.TestBuildOrchestratorContext.test_build_context_metadata_structure` | 140 |
| method | `tests.unit.test_context_manager.TestBuildOrchestratorContext.test_build_context_respects_token_limit` | 161 |
| method | `tests.unit.test_context_manager.TestBuildOrchestratorContext.test_build_context_with_conversation_history` | 174 |
| method | `tests.unit.test_context_manager.TestBuildOrchestratorContext.test_build_context_with_files` | 193 |
| class | `tests.unit.test_context_manager.TestGetPrioritizedSuggestions` | 237 |
| method | `tests.unit.test_context_manager.TestGetPrioritizedSuggestions.test_get_suggestions_empty_db` | 240 |
| method | `tests.unit.test_context_manager.TestGetPrioritizedSuggestions.test_get_suggestions_with_feedback` | 248 |
| class | `tests.unit.test_context_manager.TestEdgeCases` | 277 |
| method | `tests.unit.test_context_manager.TestEdgeCases.test_handles_missing_files_table` | 280 |
| method | `tests.unit.test_context_manager.TestEdgeCases.test_handles_none_task_id` | 289 |
| method | `tests.unit.test_context_manager.TestEdgeCases.test_handles_empty_string_task_id` | 297 |
| method | `tests.unit.test_context_manager.TestEdgeCases.test_very_large_limit` | 305 |
| class | `tests.unit.test_context_manager.TestPerformance` | 315 |
| method | `tests.unit.test_context_manager.TestPerformance.test_query_completes_quickly` | 318 |
| method | `tests.unit.test_context_manager.TestPerformance.test_build_context_performance` | 351 |
| function | `tests.unit.test_context_manager.test_context_manager_counts_files_in_subdirectories_excluding_metadata` | 368 |

### `tests/unit/test_db_retry_countdown.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| class | `tests.unit.test_db_retry_countdown.TestBackoffCountdown` | 21 |
| method | `tests.unit.test_db_retry_countdown.TestBackoffCountdown.test_backoff_stops_when_deadline_passed` | 22 |
| method | `tests.unit.test_db_retry_countdown.TestBackoffCountdown.test_backoff_sleeps_within_budget` | 26 |
| class | `tests.unit.test_db_retry_countdown.TestCommitRetryTerminal` | 35 |
| method | `tests.unit.test_db_retry_countdown.TestCommitRetryTerminal.test_commit_raises_after_budget` | 36 |
| method | `tests.unit.test_db_retry_countdown.TestCommitRetryTerminal.test_non_lock_error_not_retried` | 46 |
| method | `tests.unit.test_db_retry_countdown.TestCommitRetryTerminal.test_database_retry_error_not_caught_by_execute_with_retry` | 55 |
| class | `tests.unit.test_db_retry_countdown.TestResponseParser` | 69 |
| method | `tests.unit.test_db_retry_countdown.TestResponseParser.test_parses_markdown_json` | 70 |
| method | `tests.unit.test_db_retry_countdown.TestResponseParser.test_parses_raw_object` | 77 |
| method | `tests.unit.test_db_retry_countdown.TestResponseParser.test_empty_response` | 83 |
| method | `tests.unit.test_db_retry_countdown.TestResponseParser.test_malformed` | 88 |

### `tests/unit/test_db_retry_patience.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| class | `tests.unit.test_db_retry_patience.TestDbRetryDefaults` | 24 |
| method | `tests.unit.test_db_retry_patience.TestDbRetryDefaults.test_default_commit_max_seconds_increased` | 25 |
| method | `tests.unit.test_db_retry_patience.TestDbRetryDefaults.test_default_commit_retries_unchanged` | 29 |
| class | `tests.unit.test_db_retry_patience.TestCommitWithRetryBudget` | 34 |
| method | `tests.unit.test_db_retry_patience.TestCommitWithRetryBudget.test_commit_raises_after_new_budget` | 35 |
| method | `tests.unit.test_db_retry_patience.TestCommitWithRetryBudget.test_commit_succeeds_within_budget` | 45 |
| class | `tests.unit.test_db_retry_patience.TestGetDbConnectionPatience` | 60 |
| method | `tests.unit.test_db_retry_patience.TestGetDbConnectionPatience.test_max_retry_seconds_passed_through` | 61 |
| method | `tests.unit.test_db_retry_patience.TestGetDbConnectionPatience.test_default_patience_when_not_specified` | 71 |

### `tests/unit/test_delete_file_op.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| class | `tests.unit.test_delete_file_op.TestSchemaGate` | 17 |
| method | `tests.unit.test_delete_file_op.TestSchemaGate.test_valid_delete_file_passes_shared_gate` | 18 |
| method | `tests.unit.test_delete_file_op.TestSchemaGate.test_delete_file_requires_target_file_path` | 22 |
| method | `tests.unit.test_delete_file_op.TestSchemaGate.test_delete_file_model_validate_resolves_type` | 25 |
| class | `tests.unit.test_delete_file_op.TestApplyDeleteFile` | 43 |
| method | `tests.unit.test_delete_file_op.TestApplyDeleteFile.test_marks_file_and_lines_deleted` | 44 |
| method | `tests.unit.test_delete_file_op.TestApplyDeleteFile.test_refuses_repeat_delete` | 65 |
| method | `tests.unit.test_delete_file_op.TestApplyDeleteFile.test_refuses_path_mismatch` | 81 |
| class | `tests.unit.test_delete_file_op.TestMaterializeDelete` | 101 |
| method | `tests.unit.test_delete_file_op.TestMaterializeDelete.test_materialize_removes_disk_file_and_logs_deleted` | 102 |
| class | `tests.unit.test_delete_file_op.TestShellMapping` | 161 |
| method | `tests.unit.test_delete_file_op.TestShellMapping.test_d_status_maps_to_delete_file` | 162 |
| method | `tests.unit.test_delete_file_op.TestShellMapping.test_oversize_status_still_skipped` | 166 |
| class | `tests.unit.test_delete_file_op.TestDiskRemovalResilience` | 175 |
| method | `tests.unit.test_delete_file_op.TestDiskRemovalResilience.test_missing_file_is_successful_noop` | 176 |
| method | `tests.unit.test_delete_file_op.TestDiskRemovalResilience.test_directory_unlink_oserror_is_surfaced` | 182 |
| method | `tests.unit.test_delete_file_op.TestDiskRemovalResilience.test_path_escape_is_error` | 195 |

### `tests/unit/test_developer_edit_helpers.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| function | `tests.unit.test_developer_edit_helpers.test_normalize_full_replace_shape` | 12 |
| function | `tests.unit.test_developer_edit_helpers.test_normalize_find_top_level` | 26 |
| function | `tests.unit.test_developer_edit_helpers.test_normalize_diff_shape` | 35 |
| function | `tests.unit.test_developer_edit_helpers.test_normalize_bare_single_op_wraps_without_operations_key` | 47 |
| function | `tests.unit.test_developer_edit_helpers.test_normalize_bare_apply_diff_op` | 71 |
| function | `tests.unit.test_developer_edit_helpers.test_normalize_payload_without_type_or_operations_stays_empty` | 80 |

### `tests/unit/test_edit_contracts.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| function | `tests.unit.test_edit_contracts._approve` | 22 |
| function | `tests.unit.test_edit_contracts._content` | 32 |
| function | `tests.unit.test_edit_contracts._guids` | 40 |
| class | `tests.unit.test_edit_contracts.TestEditPayloadContracts` | 164 |
| method | `tests.unit.test_edit_contracts.TestEditPayloadContracts.test_payload_parses` | 166 |
| method | `tests.unit.test_edit_contracts.TestEditPayloadContracts.test_unknown_type_rejected` | 173 |
| class | `tests.unit.test_edit_contracts.TestDeveloperSchemaFile` | 187 |
| method | `tests.unit.test_edit_contracts.TestDeveloperSchemaFile.test_developer_schema_loads` | 188 |
| method | `tests.unit.test_edit_contracts.TestDeveloperSchemaFile.test_all_schema_files_are_json` | 194 |
| class | `tests.unit.test_edit_contracts.TestApplyContracts` | 207 |
| method | `tests.unit.test_edit_contracts.TestApplyContracts.test_find_replace_apply` | 208 |
| method | `tests.unit.test_edit_contracts.TestApplyContracts.test_full_replace_apply` | 236 |
| method | `tests.unit.test_edit_contracts.TestApplyContracts.test_replace_block_apply` | 263 |
| method | `tests.unit.test_edit_contracts.TestApplyContracts.test_insert_after_apply` | 292 |
| method | `tests.unit.test_edit_contracts.TestApplyContracts.test_delete_lines_apply` | 322 |
| method | `tests.unit.test_edit_contracts.TestApplyContracts.test_apply_diff` | 352 |
| method | `tests.unit.test_edit_contracts.TestApplyContracts.test_create_file_apply` | 381 |
| method | `tests.unit.test_edit_contracts.TestApplyContracts.test_create_file_refuses_existing` | 410 |
| method | `tests.unit.test_edit_contracts.TestApplyContracts.test_apply_diff_malformed` | 446 |
| method | `tests.unit.test_edit_contracts.TestApplyContracts.test_apply_diff_empty` | 481 |

### `tests/unit/test_edit_mode_selector.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| function | `tests.unit.test_edit_mode_selector.test_very_small_file_prefers_full_replace` | 18 |
| function | `tests.unit.test_edit_mode_selector.test_rename_prefers_find_replace` | 25 |
| function | `tests.unit.test_edit_mode_selector.test_large_refactor_prefers_guid` | 31 |
| function | `tests.unit.test_edit_mode_selector.test_multi_file_counts_as_large` | 40 |
| function | `tests.unit.test_edit_mode_selector.test_medium_on_small_file_prefers_find_replace` | 50 |
| function | `tests.unit.test_edit_mode_selector.test_preferred_modes_honoured_when_no_strong_signal` | 56 |
| function | `tests.unit.test_edit_mode_selector.test_custom_fallback_order_filters_unknown` | 65 |
| function | `tests.unit.test_edit_mode_selector.test_empty_fallback_order_uses_default` | 76 |
| function | `tests.unit.test_edit_mode_selector.test_next_fallback_chain_order` | 81 |
| function | `tests.unit.test_edit_mode_selector.test_next_fallback_exhausted` | 90 |
| function | `tests.unit.test_edit_mode_selector.test_build_prompt_full_replace_contains_schema_keys` | 94 |
| function | `tests.unit.test_edit_mode_selector.test_build_prompt_find_replace_contains_operations` | 101 |
| function | `tests.unit.test_edit_mode_selector.test_build_prompt_diff_mentions_unified` | 107 |
| function | `tests.unit.test_edit_mode_selector.test_build_prompt_guid_default` | 113 |

### `tests/unit/test_edit_payload.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| function | `tests.unit.test_edit_payload.test_replace_block_coerces_string_new_content` | 19 |
| function | `tests.unit.test_edit_payload.test_replace_block_rejects_bad_new_content_type` | 25 |
| function | `tests.unit.test_edit_payload.test_insert_after_coerces_string` | 30 |
| function | `tests.unit.test_edit_payload.test_find_replace_requires_non_empty_find` | 35 |
| function | `tests.unit.test_edit_payload.test_find_replace_rejects_negative_count` | 40 |
| function | `tests.unit.test_edit_payload.test_full_replace_joins_list_lines` | 45 |
| function | `tests.unit.test_edit_payload.test_full_replace_rejects_blank` | 51 |
| function | `tests.unit.test_edit_payload.test_rationale_auto_expand_when_short` | 56 |
| function | `tests.unit.test_edit_payload.test_rationale_auto_truncate_when_too_long` | 62 |
| function | `tests.unit.test_edit_payload.test_rationale_up_to_limit_passes_through_untouched` | 69 |
| function | `tests.unit.test_edit_payload.test_edit_payload_rationale_auto_truncate_when_too_long` | 76 |
| function | `tests.unit.test_edit_payload.test_edit_payload_model_validate_find_replace` | 89 |
| function | `tests.unit.test_edit_payload.test_edit_payload_model_validate_json_roundtrip` | 103 |
| function | `tests.unit.test_edit_payload.test_edit_payload_unknown_op_type` | 122 |
| function | `tests.unit.test_edit_payload.test_edit_payload_short_summary_rejected` | 133 |
| function | `tests.unit.test_edit_payload.test_edit_payload_auto_rationale_on_ops` | 143 |

### `tests/unit/test_edit_response_validator.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| function | `tests.unit.test_edit_response_validator.test_empty_response` | 14 |
| function | `tests.unit.test_edit_response_validator.test_whitespace_only_response` | 21 |
| function | `tests.unit.test_edit_response_validator.test_no_json` | 27 |
| function | `tests.unit.test_edit_response_validator.test_invalid_json` | 33 |
| function | `tests.unit.test_edit_response_validator.test_root_scalar_unknown` | 39 |
| function | `tests.unit.test_edit_response_validator.test_full_replace_valid` | 46 |
| function | `tests.unit.test_edit_response_validator.test_full_replace_missing_content` | 55 |
| function | `tests.unit.test_edit_response_validator.test_full_replace_null_content` | 62 |
| function | `tests.unit.test_edit_response_validator.test_find_replace_top_level` | 69 |
| function | `tests.unit.test_edit_response_validator.test_find_replace_replacements_list` | 76 |
| function | `tests.unit.test_edit_response_validator.test_diff_mode_valid` | 86 |
| function | `tests.unit.test_edit_response_validator.test_diff_mode_blank_rejected_as_no_ops` | 97 |
| function | `tests.unit.test_edit_response_validator.test_operations_find_replace` | 104 |
| function | `tests.unit.test_edit_response_validator.test_empty_operations` | 116 |
| function | `tests.unit.test_edit_response_validator.test_operations_not_a_list` | 123 |
| function | `tests.unit.test_edit_response_validator.test_operations_without_type` | 130 |
| function | `tests.unit.test_edit_response_validator.test_single_top_level_operation` | 137 |
| function | `tests.unit.test_edit_response_validator.test_root_list_of_operations_normalized` | 149 |
| function | `tests.unit.test_edit_response_validator.test_markdown_fenced_json_accepted` | 166 |
| function | `tests.unit.test_edit_response_validator.test_preamble_then_json_object` | 174 |
| function | `tests.unit.test_edit_response_validator.test_result_dataclass_defaults` | 182 |

### `tests/unit/test_edit_validation_alignment.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| class | `tests.unit.test_edit_validation_alignment.TestRejectGuidType` | 19 |
| method | `tests.unit.test_edit_validation_alignment.TestRejectGuidType.test_guid_type_is_invalid` | 27 |
| method | `tests.unit.test_edit_validation_alignment.TestRejectGuidType.test_unknown_type_names_invalid` | 36 |
| class | `tests.unit.test_edit_validation_alignment.TestRequireFindReplaceFields` | 48 |
| method | `tests.unit.test_edit_validation_alignment.TestRequireFindReplaceFields.test_find_replace_missing_fields_invalid` | 59 |
| method | `tests.unit.test_edit_validation_alignment.TestRequireFindReplaceFields.test_find_replace_with_both_fields_valid` | 65 |
| method | `tests.unit.test_edit_validation_alignment.TestRequireFindReplaceFields.test_replace_block_requires_anchor_guid` | 75 |
| class | `tests.unit.test_edit_validation_alignment.TestSchemaParityWithEditPayload` | 87 |
| method | `tests.unit.test_edit_validation_alignment.TestSchemaParityWithEditPayload.test_full_replace_op_accepts_list_content` | 90 |
| method | `tests.unit.test_edit_validation_alignment.TestSchemaParityWithEditPayload.test_valid_ops_all_accepted` | 109 |
| class | `tests.unit.test_edit_validation_alignment.TestNoProposalForInvalidOps` | 115 |
| method | `tests.unit.test_edit_validation_alignment.TestNoProposalForInvalidOps.test_invalid_ops_create_no_proposal_row` | 116 |

### `tests/unit/test_endpoint_failures.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| function | `tests.unit.test_endpoint_failures._resp` | 18 |
| function | `tests.unit.test_endpoint_failures.endpoint_config` | 31 |
| function | `tests.unit.test_endpoint_failures.test_401_does_not_block_two_minutes` | 57 |
| function | `tests.unit.test_endpoint_failures.test_429_response_shape` | 75 |
| function | `tests.unit.test_endpoint_failures.test_call_agent_empty_when_endpoint_always_fails` | 84 |
| function | `tests.unit.test_endpoint_failures.test_http_5xx_via_post_json` | 95 |

### `tests/unit/test_endpoint_manager.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| function | `tests.unit.test_endpoint_manager.ep_config` | 16 |
| function | `tests.unit.test_endpoint_manager.manager` | 60 |
| function | `tests.unit.test_endpoint_manager.test_endpoint_config_fields` | 69 |
| function | `tests.unit.test_endpoint_manager.test_extract_response_default_path` | 87 |
| function | `tests.unit.test_endpoint_manager.test_extract_response_custom_path` | 93 |
| function | `tests.unit.test_endpoint_manager.test_endpoint_status_values` | 107 |
| function | `tests.unit.test_endpoint_manager.test_health_starts_healthy` | 116 |
| function | `tests.unit.test_endpoint_manager.test_mark_failure_sets_cooldown` | 122 |
| function | `tests.unit.test_endpoint_manager.test_mark_success_clears_failure` | 130 |
| function | `tests.unit.test_endpoint_manager.test_manager_loads_endpoints_and_models` | 145 |
| function | `tests.unit.test_endpoint_manager.test_get_endpoint_for_model` | 153 |
| function | `tests.unit.test_endpoint_manager.test_get_endpoint_for_unknown_model_uses_default` | 161 |
| function | `tests.unit.test_endpoint_manager.test_get_model_config` | 166 |
| function | `tests.unit.test_endpoint_manager.test_get_api_key_specific_name` | 174 |
| function | `tests.unit.test_endpoint_manager.test_get_api_key_falls_back_to_generic` | 182 |
| function | `tests.unit.test_endpoint_manager.test_build_payload_includes_model_when_configured` | 188 |
| function | `tests.unit.test_endpoint_manager.test_build_payload_omits_model_when_disabled` | 195 |
| function | `tests.unit.test_endpoint_manager.test_validate_model_known` | 202 |
| function | `tests.unit.test_endpoint_manager.test_validate_model_unknown_returns_fallback` | 206 |
| function | `tests.unit.test_endpoint_manager.test_validate_model_empty_returns_none` | 213 |
| function | `tests.unit.test_endpoint_manager.test_get_available_endpoints_sorted_by_priority` | 218 |
| function | `tests.unit.test_endpoint_manager.test_get_fallback_model` | 224 |
| function | `tests.unit.test_endpoint_manager.test_get_fallback_model_disabled` | 233 |
| function | `tests.unit.test_endpoint_manager.test_get_fallback_model_prefers_healthy_over_higher_priority` | 239 |
| function | `tests.unit.test_endpoint_manager.test_get_health_summary_shape` | 261 |
| function | `tests.unit.test_endpoint_manager._isolate_freeze_registry` | 277 |
| function | `tests.unit.test_endpoint_manager.test_mark_failure_latches_only_endpoint_freezes_support` | 285 |
| function | `tests.unit.test_endpoint_manager.test_mark_success_on_only_endpoint_resumes_support` | 310 |
| function | `tests.unit.test_endpoint_manager.test_mixed_config_stays_unfrozen_when_one_healthy` | 334 |
| function | `tests.unit.test_endpoint_manager.test_unavailable_until_expiry_unfreezes_support` | 345 |

### `tests/unit/test_error_logging_observability.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| function | `tests.unit.test_error_logging_observability.test_log_error_persists_agent_name_and_details` | 10 |
| function | `tests.unit.test_error_logging_observability.test_call_agent_failure_logs_agent_name_and_model` | 36 |

### `tests/unit/test_events_undo.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| function | `tests.unit.test_events_undo.test_publish_and_list_events` | 12 |
| function | `tests.unit.test_events_undo.test_undo_restores_content` | 27 |
| function | `tests.unit.test_events_undo.test_undo_multiline_replacement` | 71 |
| function | `tests.unit.test_events_undo.test_undo_without_snapshot_errors` | 119 |
| function | `tests.unit.test_events_undo.test_proposal_created_emits_event` | 127 |
| function | `tests.unit.test_events_undo.test_create_file_then_materialize` | 153 |

### `tests/unit/test_fallback_stats.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| function | `tests.unit.test_fallback_stats.test_log_and_get_fallback_stats` | 6 |

### `tests/unit/test_feedback_aging.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| function | `tests.unit.test_feedback_aging.test_save_and_fetch_feedback` | 8 |
| function | `tests.unit.test_feedback_aging.test_age_feedback_dismisses_old_low_only` | 27 |
| function | `tests.unit.test_feedback_aging.test_backlog_force_override_above_threshold` | 70 |

### `tests/unit/test_fuzz_tables.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| class | `tests.unit.test_fuzz_tables.TestJsonParserFuzzTable` | 38 |
| method | `tests.unit.test_fuzz_tables.TestJsonParserFuzzTable.test_parse_cases` | 40 |
| class | `tests.unit.test_fuzz_tables.TestPathContainmentFuzzTable` | 66 |
| method | `tests.unit.test_fuzz_tables.TestPathContainmentFuzzTable.test_path_cases` | 68 |

### `tests/unit/test_git_closed_loop.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| function | `tests.unit.test_git_closed_loop._git_failure_result` | 26 |
| function | `tests.unit.test_git_closed_loop._git_success_result` | 39 |
| function | `tests.unit.test_git_closed_loop._event_rows` | 52 |
| function | `tests.unit.test_git_closed_loop._feedback_rows` | 64 |
| function | `tests.unit.test_git_closed_loop._error_rows` | 73 |
| function | `tests.unit.test_git_closed_loop._make_proposal` | 82 |
| function | `tests.unit.test_git_closed_loop.git_config_env` | 119 |
| class | `tests.unit.test_git_closed_loop.TestFileIdRules` | 176 |
| method | `tests.unit.test_git_closed_loop.TestFileIdRules.test_reuses_and_resurrects_soft_deleted_path` | 177 |
| class | `tests.unit.test_git_closed_loop.TestBacklogDrain` | 209 |
| method | `tests.unit.test_git_closed_loop.TestBacklogDrain.test_git_hook_critical_drains_before_high` | 210 |
| method | `tests.unit.test_git_closed_loop.TestBacklogDrain.test_multiple_critical_rows_pick_newest_unaddressed` | 242 |
| class | `tests.unit.test_git_closed_loop.TestMaterializeStatus` | 271 |
| method | `tests.unit.test_git_closed_loop.TestMaterializeStatus.test_hook_failure_is_not_success` | 272 |
| method | `tests.unit.test_git_closed_loop.TestMaterializeStatus.test_hook_success_returns_success` | 290 |
| method | `tests.unit.test_git_closed_loop.TestMaterializeStatus.test_git_disabled_is_not_a_failure` | 304 |
| method | `tests.unit.test_git_closed_loop.TestMaterializeStatus.test_multi_file_success_does_not_clear_failure` | 318 |
| method | `tests.unit.test_git_closed_loop.TestMaterializeStatus.test_multi_file_all_success` | 342 |
| class | `tests.unit.test_git_closed_loop.TestRecordGitFailureHelper` | 367 |
| method | `tests.unit.test_git_closed_loop.TestRecordGitFailureHelper.test_records_event_and_critical_feedback_deduped` | 368 |
| method | `tests.unit.test_git_closed_loop.TestRecordGitFailureHelper.test_returns_false_when_not_attempted` | 388 |
| class | `tests.unit.test_git_closed_loop.TestGateAndMaterializeClosedLoop` | 407 |
| method | `tests.unit.test_git_closed_loop.TestGateAndMaterializeClosedLoop.test_git_failure_emits_event_feedback_errors` | 408 |
| class | `tests.unit.test_git_closed_loop.TestRunDeveloperMutationClosedLoop` | 455 |
| method | `tests.unit.test_git_closed_loop.TestRunDeveloperMutationClosedLoop.test_addressing_not_closed_and_loop_is_recorded` | 456 |

### `tests/unit/test_git_operations.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| function | `tests.unit.test_git_operations.git_enabled_config` | 18 |
| class | `tests.unit.test_git_operations.TestGitCommitStructuredOutcome` | 37 |
| method | `tests.unit.test_git_operations.TestGitCommitStructuredOutcome.test_commit_success_returns_ok_result` | 40 |
| method | `tests.unit.test_git_operations.TestGitCommitStructuredOutcome.test_commit_hook_failure_returns_failure_data` | 56 |
| method | `tests.unit.test_git_operations.TestGitCommitStructuredOutcome.test_git_add_failure_returns_failure_data` | 79 |
| method | `tests.unit.test_git_operations.TestGitCommitStructuredOutcome.test_timeout_returns_failure_data` | 93 |
| method | `tests.unit.test_git_operations.TestGitCommitStructuredOutcome.test_disabled_git_returns_not_attempted` | 104 |

### `tests/unit/test_gitignore.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| function | `tests.unit.test_gitignore.project_root` | 13 |
| function | `tests.unit.test_gitignore._reset_cache` | 37 |
| function | `tests.unit.test_gitignore.test_load_spec_present` | 48 |
| function | `tests.unit.test_gitignore.test_load_spec_missing` | 52 |
| function | `tests.unit.test_gitignore.test_should_ignore_by_gitignore` | 75 |
| function | `tests.unit.test_gitignore.test_outside_project_root_is_ignored` | 81 |
| function | `tests.unit.test_gitignore.test_no_gitignore_fail_open` | 85 |
| function | `tests.unit.test_gitignore.test_explicit_spec_overrides` | 91 |
| function | `tests.unit.test_gitignore.test_file_operations_hardcoded_ignores` | 96 |
| function | `tests.unit.test_gitignore.test_sync_file_to_database_skips_secrets` | 115 |
| function | `tests.unit.test_gitignore.test_consolidate_respects_gitignore` | 134 |

### `tests/unit/test_hardening.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| function | `tests.unit.test_hardening._hash` | 19 |
| class | `tests.unit.test_hardening.TestPathContainment` | 28 |
| method | `tests.unit.test_hardening.TestPathContainment.test_legitimate_relative_write` | 29 |
| method | `tests.unit.test_hardening.TestPathContainment.test_traversal_rejected` | 52 |
| method | `tests.unit.test_hardening.TestPathContainment.test_absolute_outside_rejected` | 74 |
| class | `tests.unit.test_hardening.TestEditModeSelector` | 103 |
| method | `tests.unit.test_hardening.TestEditModeSelector.test_small_file_prefers_full_replace` | 104 |
| method | `tests.unit.test_hardening.TestEditModeSelector.test_rename_prefers_find_replace` | 110 |
| method | `tests.unit.test_hardening.TestEditModeSelector.test_large_prefers_guid` | 116 |
| method | `tests.unit.test_hardening.TestEditModeSelector.test_fallback_chain_order` | 125 |
| method | `tests.unit.test_hardening.TestEditModeSelector.test_validator_detects_empty_ops` | 135 |
| method | `tests.unit.test_hardening.TestEditModeSelector.test_validator_detects_find_replace` | 142 |
| function | `tests.unit.test_hardening.governed_db` | 156 |
| class | `tests.unit.test_hardening.TestConcurrencyAndGuids` | 165 |
| method | `tests.unit.test_hardening.TestConcurrencyAndGuids.test_hash_mismatch_returns_conflicted` | 166 |
| method | `tests.unit.test_hardening.TestConcurrencyAndGuids.test_missing_guid_returns_conflicted` | 212 |
| method | `tests.unit.test_hardening.TestConcurrencyAndGuids.test_find_replace_still_works` | 246 |
| class | `tests.unit.test_hardening.TestRepoRootContainment` | 293 |
| method | `tests.unit.test_hardening.TestRepoRootContainment.test_get_repo_root_returns_path` | 294 |
| method | `tests.unit.test_hardening.TestRepoRootContainment.test_ensure_project_directory_under_repo` | 300 |
| method | `tests.unit.test_hardening.TestRepoRootContainment.test_ensure_project_directory_allows_outside_repo` | 313 |

### `tests/unit/test_http_client.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| class | `tests.unit.test_http_client.TestHttpClient` | 20 |
| method | `tests.unit.test_http_client.TestHttpClient.test_has_requests` | 21 |
| method | `tests.unit.test_http_client.TestHttpClient.test_post_json_uses_requests_when_available` | 27 |
| method | `tests.unit.test_http_client.TestHttpClient.test_post_json_urllib_path` | 45 |
| method | `tests.unit.test_http_client.TestHttpClient.test_http_error_raise_for_status` | 78 |
| class | `tests.unit.test_http_client.TestEndpointResilienceMocks` | 86 |
| method | `tests.unit.test_http_client.TestEndpointResilienceMocks.test_401_response_shape` | 87 |
| method | `tests.unit.test_http_client.TestEndpointResilienceMocks.test_rate_limit_429_body` | 103 |
| method | `tests.unit.test_http_client.TestEndpointResilienceMocks.test_mock_openai_chat_still_patches_requests` | 110 |
| class | `tests.unit.test_http_client.TestRateLimiter` | 128 |
| method | `tests.unit.test_http_client.TestRateLimiter.test_rate_limiter_basic` | 129 |

### `tests/unit/test_http_diag.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| function | `tests.unit.test_http_diag._resp` | 11 |
| function | `tests.unit.test_http_diag.test_openai_style_error_dict_is_parsed` | 16 |
| function | `tests.unit.test_http_diag.test_string_error_field_is_not_dropped` | 31 |
| function | `tests.unit.test_http_diag.test_dump_includes_status_headers_and_body` | 37 |
| function | `tests.unit.test_http_diag.test_non_json_body_still_printed` | 66 |

### `tests/unit/test_index_context.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| function | `tests.unit.test_index_context.test_load_symbol_json_context_after_upsert` | 6 |
| function | `tests.unit.test_index_context.test_load_index_text_missing_returns_empty` | 19 |
| function | `tests.unit.test_index_context.test_load_index_text_reads_markdown` | 26 |
| function | `tests.unit.test_index_context.test_load_index_text_named_variant` | 36 |
| function | `tests.unit.test_index_context.test_load_index_text_raises_on_unknown_which` | 46 |

### `tests/unit/test_iteration_timeout.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| class | `tests.unit.test_iteration_timeout.TestActiveWorkTracking` | 16 |
| method | `tests.unit.test_iteration_timeout.TestActiveWorkTracking.test_active_time_accumulates_across_calls` | 19 |
| method | `tests.unit.test_iteration_timeout.TestActiveWorkTracking.test_timeout_uses_active_time_not_wall_clock` | 32 |
| method | `tests.unit.test_iteration_timeout.TestActiveWorkTracking.test_timeout_fires_when_active_budget_exhausted` | 53 |
| method | `tests.unit.test_iteration_timeout.TestActiveWorkTracking.test_db_lock_backoff_not_counted` | 67 |
| method | `tests.unit.test_iteration_timeout.TestActiveWorkTracking.test_active_time_resets_per_iteration` | 79 |

### `tests/unit/test_json_parser.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| function | `tests.unit.test_json_parser.test_parse_result_success_property` | 18 |
| function | `tests.unit.test_json_parser.test_parse_result_truncated_can_resume` | 24 |
| function | `tests.unit.test_json_parser.test_parse_empty_response` | 35 |
| function | `tests.unit.test_json_parser.test_parse_whitespace_only` | 43 |
| function | `tests.unit.test_json_parser.test_parse_plain_object` | 49 |
| function | `tests.unit.test_json_parser.test_parse_plain_array_as_object_wrapper_not_forced` | 58 |
| function | `tests.unit.test_json_parser.test_extract_markdown_json_fence` | 67 |
| function | `tests.unit.test_json_parser.test_extract_generic_markdown_fence_with_json` | 80 |
| function | `tests.unit.test_json_parser.test_extract_generic_markdown_fence_ignores_non_json` | 90 |
| function | `tests.unit.test_json_parser.test_extract_brace_bounded_with_preamble` | 100 |
| function | `tests.unit.test_json_parser.test_brace_matching_ignores_braces_inside_strings` | 108 |
| function | `tests.unit.test_json_parser.test_brace_matching_with_escaped_quotes` | 117 |
| function | `tests.unit.test_json_parser.test_malformed_unclosed_object_is_truncated_or_malformed` | 127 |
| function | `tests.unit.test_json_parser.test_truncated_unclosed_braces_detected` | 135 |
| function | `tests.unit.test_json_parser.test_ends_with_comma_looks_truncated` | 143 |
| function | `tests.unit.test_json_parser.test_balanced_object_not_truncated` | 148 |
| function | `tests.unit.test_json_parser.test_odd_quote_count_looks_truncated` | 153 |
| function | `tests.unit.test_json_parser.test_expected_keys_all_present` | 163 |
| function | `tests.unit.test_json_parser.test_expected_keys_missing_non_strict_still_success` | 170 |
| function | `tests.unit.test_json_parser.test_expected_keys_missing_strict_is_malformed` | 179 |
| function | `tests.unit.test_json_parser.test_build_resume_prompt_contains_context` | 192 |
| function | `tests.unit.test_json_parser.test_build_resume_prompt_short_partial` | 201 |
| function | `tests.unit.test_json_parser.test_get_json_parser_singleton` | 213 |
| function | `tests.unit.test_json_parser.test_parse_json_response_valid` | 219 |
| function | `tests.unit.test_json_parser.test_parse_json_response_markdown` | 226 |
| function | `tests.unit.test_json_parser.test_parse_json_response_malformed_returns_none` | 235 |
| function | `tests.unit.test_json_parser.test_parse_json_response_empty_returns_none` | 241 |
| function | `tests.unit.test_json_parser.test_parse_json_response_with_auto_resume_success` | 245 |
| function | `tests.unit.test_json_parser.test_parse_json_response_surrounding_text` | 261 |

### `tests/unit/test_json_repair.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| function | `tests.unit.test_json_repair.stub_agent_deps` | 33 |
| class | `tests.unit.test_json_repair.TestJsonRepair` | 96 |
| method | `tests.unit.test_json_repair.TestJsonRepair.test_valid_json_skips_repair` | 97 |
| method | `tests.unit.test_json_repair.TestJsonRepair.test_malformed_triggers_one_repair` | 113 |
| method | `tests.unit.test_json_repair.TestJsonRepair.test_repair_failure_keeps_original` | 132 |
| method | `tests.unit.test_json_repair.TestJsonRepair.test_text_output_agent_skips_repair` | 150 |
| method | `tests.unit.test_json_repair.TestJsonRepair.test_is_repair_attempt_prevents_recursion` | 166 |
| method | `tests.unit.test_json_repair.TestJsonRepair.test_empty_response_skips_repair` | 188 |

### `tests/unit/test_lint_precheck.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| class | `tests.unit.test_lint_precheck.FakeRuffProcess` | 14 |
| class | `tests.unit.test_lint_precheck.FakeRuffOk` | 20 |
| function | `tests.unit.test_lint_precheck._propose_approved` | 26 |
| class | `tests.unit.test_lint_precheck.TestRunPrecheck` | 45 |
| method | `tests.unit.test_lint_precheck.TestRunPrecheck.test_disabled_returns_empty` | 46 |
| method | `tests.unit.test_lint_precheck.TestRunPrecheck.test_failure_marker` | 49 |
| class | `tests.unit.test_lint_precheck.TestMaterializeLintGate` | 59 |
| method | `tests.unit.test_lint_precheck.TestMaterializeLintGate.test_ruff_failure_surfaces_lint_failed_closed_loop` | 60 |
| method | `tests.unit.test_lint_precheck.TestMaterializeLintGate.test_ruff_ok_passes_through` | 92 |
| method | `tests.unit.test_lint_precheck.TestMaterializeLintGate.test_disabled_has_no_lint_gate` | 107 |

### `tests/unit/test_llm_mock_registry.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| function | `tests.unit.test_llm_mock_registry.test_registry_includes_core_sites` | 6 |
| function | `tests.unit.test_llm_mock_registry.test_register_extends_targets` | 13 |
| function | `tests.unit.test_llm_mock_registry.test_mock_llm_uses_registry` | 23 |

### `tests/unit/test_llm_mocks.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| class | `tests.unit.test_llm_mocks.TestMockLLMScripting` | 14 |
| method | `tests.unit.test_llm_mocks.TestMockLLMScripting.test_set_response_and_handler` | 15 |
| method | `tests.unit.test_llm_mocks.TestMockLLMScripting.test_sequential_responses` | 26 |
| method | `tests.unit.test_llm_mocks.TestMockLLMScripting.test_default_fallback` | 37 |
| method | `tests.unit.test_llm_mocks.TestMockLLMScripting.test_patch_call_agent_context_manager` | 43 |
| class | `tests.unit.test_llm_mocks.TestMockHttpLayer` | 61 |
| method | `tests.unit.test_llm_mocks.TestMockHttpLayer.test_make_requests_response_shape` | 62 |
| method | `tests.unit.test_llm_mocks.TestMockHttpLayer.test_mock_openai_chat_fixture` | 71 |
| method | `tests.unit.test_llm_mocks.TestMockHttpLayer.test_mock_llm_fixture` | 80 |
| method | `tests.unit.test_llm_mocks.TestMockHttpLayer.test_mock_llm_patched_fixture` | 88 |
| class | `tests.unit.test_llm_mocks.TestNoNetworkLeak` | 97 |
| method | `tests.unit.test_llm_mocks.TestNoNetworkLeak.test_call_agent_mock_blocks_requests` | 100 |

### `tests/unit/test_llm_test_mode.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| function | `tests.unit.test_llm_test_mode.test_env_enables` | 6 |
| function | `tests.unit.test_llm_test_mode.test_config_enables` | 11 |
| function | `tests.unit.test_llm_test_mode.test_mock_orchestrator_json` | 16 |
| function | `tests.unit.test_llm_test_mode.test_scripted_override` | 22 |
| function | `tests.unit.test_llm_test_mode.test_mock_response_queue` | 27 |

### `tests/unit/test_mode_fallback_requery.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| function | `tests.unit.test_mode_fallback_requery.mutation_env` | 11 |
| function | `tests.unit.test_mode_fallback_requery.test_fallback_forces_second_developer_call` | 54 |
| function | `tests.unit.test_mode_fallback_requery.test_next_fallback_mode_chain` | 123 |

### `tests/unit/test_model_health.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| function | `tests.unit.test_model_health.tracker_db` | 11 |
| function | `tests.unit.test_model_health._ev` | 18 |
| function | `tests.unit.test_model_health.test_decay_weights_recent_failures_more` | 25 |
| function | `tests.unit.test_model_health.test_successes_reduce_failure_ratio` | 37 |
| function | `tests.unit.test_model_health.test_consecutive_streak_counts_trailing_failures_only` | 44 |
| function | `tests.unit.test_model_health.test_demotion_requires_min_samples` | 60 |
| function | `tests.unit.test_model_health.test_ratio_rule_demotes_with_base_cooldown` | 66 |
| function | `tests.unit.test_model_health.test_streak_rule_trips_early_and_doubles_cooldown` | 75 |
| function | `tests.unit.test_model_health.test_operator_kinds_do_not_demote` | 90 |
| function | `tests.unit.test_model_health.test_two_unauthorized_401s_do_not_down_or_demote` | 103 |
| function | `tests.unit.test_model_health.test_real_failures_still_demote_across_operator_events` | 120 |
| function | `tests.unit.test_model_health.test_record_outcome_stores_retry_after` | 134 |
| function | `tests.unit.test_model_health.test_recovery_after_successes_clears_demotion` | 142 |
| function | `tests.unit.test_model_health.test_rank_candidates_puts_demoted_last` | 153 |
| function | `tests.unit.test_model_health.test_record_outcome_persists_and_prunes` | 174 |
| function | `tests.unit.test_model_health.test_disabled_tracker_records_nothing` | 185 |
| function | `tests.unit.test_model_health.test_health_report_flags_worst_model` | 191 |
| function | `tests.unit.test_model_health.test_load_events_for_models_partitions_and_orders` | 203 |
| function | `tests.unit.test_model_health.test_compute_stats_skips_unparseable_ts` | 227 |
| function | `tests.unit.test_model_health.test_rank_candidates_sinks_down_models_last` | 237 |

### `tests/unit/test_model_resolution.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| function | `tests.unit.test_model_resolution.resolution_config` | 15 |
| function | `tests.unit.test_model_resolution.manager` | 75 |
| function | `tests.unit.test_model_resolution.test_list_all_model_references` | 84 |
| function | `tests.unit.test_model_resolution.test_get_models_for_endpoint` | 92 |
| function | `tests.unit.test_model_resolution.test_model_reference_exists` | 103 |
| function | `tests.unit.test_model_resolution.test_normalize_full_reference` | 117 |
| function | `tests.unit.test_model_resolution.test_normalize_bare_name_prefers_default_endpoint` | 123 |
| function | `tests.unit.test_model_resolution.test_normalize_none_returns_default_endpoint` | 129 |
| function | `tests.unit.test_model_resolution.test_resolve_agent_model_full_pref` | 135 |
| function | `tests.unit.test_model_resolution.test_resolve_unknown_agent_falls_back` | 146 |
| function | `tests.unit.test_model_resolution.test_get_endpoint_for_model_bare_uses_default` | 157 |
| function | `tests.unit.test_model_resolution.test_get_endpoint_for_model_full_ref` | 163 |
| function | `tests.unit.test_model_resolution.test_get_model_config_bare_and_full` | 169 |
| function | `tests.unit.test_model_resolution.test_get_model_config_missing_returns_empty` | 180 |
| function | `tests.unit.test_model_resolution.test_validate_model_known_returns_bare` | 189 |
| function | `tests.unit.test_model_resolution.test_validate_model_unknown_returns_fallback` | 194 |
| function | `tests.unit.test_model_resolution.test_validate_model_empty_returns_none` | 200 |
| function | `tests.unit.test_model_resolution.test_build_payload_strips_full_ref_to_bare` | 205 |
| function | `tests.unit.test_model_resolution.test_full_model_resolution_flow` | 215 |
| function | `tests.unit.test_model_resolution.slashed_config` | 237 |
| function | `tests.unit.test_model_resolution.slashed_manager` | 273 |
| function | `tests.unit.test_model_resolution.test_slashed_id_full_reference_parses_endpoint_and_full_id` | 277 |
| function | `tests.unit.test_model_resolution.test_slashed_id_bare_reference_resolves_via_default_endpoint` | 284 |
| function | `tests.unit.test_model_resolution.test_validate_model_preserves_slashed_id` | 291 |
| function | `tests.unit.test_model_resolution.test_build_payload_sends_full_slashed_id` | 298 |
| function | `tests.unit.test_model_resolution.test_build_payload_bare_slashed_id_keeps_whole_id` | 309 |
| function | `tests.unit.test_model_resolution.test_identical_slashed_ids_on_two_endpoints_differentiate` | 319 |
| function | `tests.unit.test_model_resolution.test_identical_slashed_ids_scoped_config_lookup` | 332 |
| function | `tests.unit.test_model_resolution.test_slashed_id_model_reference_exists` | 344 |
| function | `tests.unit.test_model_resolution.test_unknown_first_segment_treated_as_model_id` | 352 |
| function | `tests.unit.test_model_resolution.test_get_endpoint_for_model_slashed_bare_uses_default` | 360 |
| function | `tests.unit.test_model_resolution.test_hallucinated_model_override_is_rejected` | 370 |
| function | `tests.unit.test_model_resolution.test_call_agent_ignores_unknown_model_override` | 382 |

### `tests/unit/test_model_rotation.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| function | `tests.unit.test_model_rotation.tracker_db` | 18 |
| function | `tests.unit.test_model_rotation.test_two_consecutive_failures_mark_model_down_5_minutes` | 27 |
| function | `tests.unit.test_model_rotation.test_single_failure_does_not_mark_down` | 37 |
| function | `tests.unit.test_model_rotation.test_down_window_doubles_and_caps` | 42 |
| function | `tests.unit.test_model_rotation.test_success_clears_down_window` | 54 |
| function | `tests.unit.test_model_rotation.test_expired_window_reports_up` | 61 |
| function | `tests.unit.test_model_rotation.test_rank_puts_down_model_behind_everything` | 81 |
| function | `tests.unit.test_model_rotation.test_rr_rotates_to_next_candidate_on_failure` | 112 |
| function | `tests.unit.test_model_rotation.test_rr_skips_down_models_via_ranking` | 147 |

### `tests/unit/test_models_catalog.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| function | `tests.unit.test_models_catalog._cfg` | 27 |
| function | `tests.unit.test_models_catalog.test_models_url_from_chat_completions` | 53 |
| function | `tests.unit.test_models_catalog.test_parse_model_ids_openai_shape` | 59 |
| function | `tests.unit.test_models_catalog.test_fetch_catalog_uses_injector_and_persists` | 64 |
| function | `tests.unit.test_models_catalog.test_assign_known_ref` | 81 |
| function | `tests.unit.test_models_catalog.test_assign_unknown_without_register_raises` | 87 |
| function | `tests.unit.test_models_catalog.test_assign_from_catalog_requires_register` | 93 |
| function | `tests.unit.test_models_catalog.test_assign_register_adds_stub` | 100 |
| function | `tests.unit.test_models_catalog.test_assign_tier_cheap` | 109 |
| function | `tests.unit.test_models_catalog.test_validate_flags_unknown_and_missing_prompt` | 117 |
| function | `tests.unit.test_models_catalog.test_validate_clean` | 125 |
| function | `tests.unit.test_models_catalog.test_ensure_registered_rejects_unknown_endpoint` | 131 |
| function | `tests.unit.test_models_catalog.test_prompt_roundtrip` | 137 |
| function | `tests.unit.test_models_catalog.test_resolve_choice_index_and_literal` | 146 |
| function | `tests.unit.test_models_catalog.test_available_refs_orders_registered_then_catalog` | 157 |
| function | `tests.unit.test_models_catalog.test_configure_wizard_assigns_tiers_from_answers` | 164 |

### `tests/unit/test_network_busy_loop.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| class | `tests.unit.test_network_busy_loop.FakeTokenBudget` | 11 |
| method | `tests.unit.test_network_busy_loop.FakeTokenBudget.can_spend` | 12 |
| class | `tests.unit.test_network_busy_loop.FakeNoop` | 16 |
| method | `tests.unit.test_network_busy_loop.FakeNoop.get_current_decision` | 17 |
| method | `tests.unit.test_network_busy_loop.FakeNoop.temporarily_disable_throttling` | 20 |
| class | `tests.unit.test_network_busy_loop.FakePool` | 24 |
| method | `tests.unit.test_network_busy_loop.FakePool.queue_file_change` | 25 |
| class | `tests.unit.test_network_busy_loop.TestDetection` | 34 |
| method | `tests.unit.test_network_busy_loop.TestDetection.test_matches_outage_phrasings` | 35 |
| method | `tests.unit.test_network_busy_loop.TestDetection.test_does_not_match_normal_results` | 45 |
| class | `tests.unit.test_network_busy_loop.TestGuard` | 61 |
| method | `tests.unit.test_network_busy_loop.TestGuard.test_single_failure_does_not_pause` | 62 |
| method | `tests.unit.test_network_busy_loop.TestGuard.test_threshold_pauses_and_surfaces_once_until_success` | 67 |
| method | `tests.unit.test_network_busy_loop.TestGuard.test_success_resets_episode` | 85 |
| method | `tests.unit.test_network_busy_loop.TestGuard.test_threshold_constant_is_two` | 93 |
| class | `tests.unit.test_network_busy_loop.TestWiringDeveloperOutage` | 102 |
| method | `tests.unit.test_network_busy_loop.TestWiringDeveloperOutage.test_single_agent_outage_does_not_trigger_pause` | 103 |
| class | `tests.unit.test_network_busy_loop.TestWiringFullOutage` | 140 |
| method | `tests.unit.test_network_busy_loop.TestWiringFullOutage.test_failsafe_outage_pauses_and_surfaces_single_critical` | 141 |

### `tests/unit/test_orchestrator_decisions.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| function | `tests.unit.test_orchestrator_decisions._decision` | 11 |
| function | `tests.unit.test_orchestrator_decisions.test_orchestrator_routes_developer` | 25 |
| function | `tests.unit.test_orchestrator_decisions.test_orchestrator_routes_complete` | 48 |
| function | `tests.unit.test_orchestrator_decisions.test_orchestrator_routes_background` | 73 |
| function | `tests.unit.test_orchestrator_decisions.test_orchestrator_invalid_json_returns_none_or_empty` | 102 |
| function | `tests.unit.test_orchestrator_decisions.test_orchestrator_empty_agent_response` | 123 |
| function | `tests.unit.test_orchestrator_decisions.test_orchestrator_cold_start_short_circuit` | 145 |
| function | `tests.unit.test_orchestrator_decisions.test_orchestrator_background_disabled_override` | 166 |

### `tests/unit/test_parallel_workers.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| function | `tests.unit.test_parallel_workers.pool_env` | 27 |
| class | `tests.unit.test_parallel_workers.TestParallelWorkers` | 45 |
| method | `tests.unit.test_parallel_workers.TestParallelWorkers.test_file_change_event_creation` | 48 |
| method | `tests.unit.test_parallel_workers.TestParallelWorkers.test_background_agent_pool_instantiation` | 63 |
| method | `tests.unit.test_parallel_workers.TestParallelWorkers.test_agent_pool_start_stop` | 71 |
| method | `tests.unit.test_parallel_workers.TestParallelWorkers.test_start_noop_when_agents_disabled` | 87 |
| method | `tests.unit.test_parallel_workers.TestParallelWorkers.test_get_agent_pool_singleton` | 95 |
| method | `tests.unit.test_parallel_workers.TestParallelWorkers.test_queue_file_change` | 102 |
| method | `tests.unit.test_parallel_workers.TestParallelWorkers.test_worker_processes_events` | 119 |
| method | `tests.unit.test_parallel_workers.TestParallelWorkers.test_empty_queue_handling` | 136 |
| method | `tests.unit.test_parallel_workers.TestParallelWorkers.test_force_review_cycle` | 149 |
| class | `tests.unit.test_parallel_workers.TestAgentPoolConfiguration` | 166 |
| method | `tests.unit.test_parallel_workers.TestAgentPoolConfiguration.test_agent_configs_loaded` | 169 |
| method | `tests.unit.test_parallel_workers.TestAgentPoolConfiguration.test_modification_agents_list` | 175 |
| method | `tests.unit.test_parallel_workers.TestAgentPoolConfiguration.test_random_review_agents_list` | 180 |
| class | `tests.unit.test_parallel_workers.TestAgentPoolActiveControl` | 187 |
| method | `tests.unit.test_parallel_workers.TestAgentPoolActiveControl.test_set_active_agents` | 191 |
| method | `tests.unit.test_parallel_workers.TestAgentPoolActiveControl.test_set_active_agents_none_resumes_all` | 205 |
| method | `tests.unit.test_parallel_workers.TestAgentPoolActiveControl.test_set_active_agents_empty_pauses_feedback_only` | 215 |
| method | `tests.unit.test_parallel_workers.TestAgentPoolActiveControl.test_initial_review_capped_by_config` | 221 |
| method | `tests.unit.test_parallel_workers.TestAgentPoolActiveControl.test_initial_review_scoped_to_seed_target` | 249 |
| method | `tests.unit.test_parallel_workers.TestAgentPoolActiveControl.test_set_feeder_interval` | 300 |
| class | `tests.unit.test_parallel_workers.TestConcurrentBehavior` | 310 |
| method | `tests.unit.test_parallel_workers.TestConcurrentBehavior.test_multiple_file_changes_concurrent` | 313 |
| method | `tests.unit.test_parallel_workers.TestConcurrentBehavior.test_start_stop_lifecycle` | 332 |

### `tests/unit/test_pass1_feedback_constraints.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| function | `tests.unit.test_pass1_feedback_constraints.test_praise_only_without_suggestion_is_rejected` | 19 |
| function | `tests.unit.test_pass1_feedback_constraints.test_praise_only_phrase_without_suggestion_rejected` | 23 |
| function | `tests.unit.test_pass1_feedback_constraints.test_robust_fallback_praise_rejected` | 27 |
| function | `tests.unit.test_pass1_feedback_constraints.test_actionable_problem_with_suggestion_is_accepted` | 31 |
| function | `tests.unit.test_pass1_feedback_constraints.test_actionable_but_no_suggestion_is_kept` | 41 |
| function | `tests.unit.test_pass1_feedback_constraints.test_error_token_overrides_praise_phrase` | 48 |
| function | `tests.unit.test_pass1_feedback_constraints.test_praise_phrase_still_rejected_without_problem_language` | 59 |
| function | `tests.unit.test_pass1_feedback_constraints._pool_with_agent_config` | 67 |
| class | `tests.unit.test_pass1_feedback_constraints._FakeQueue` | 87 |
| method | `tests.unit.test_pass1_feedback_constraints._FakeQueue.__init__` | 88 |
| method | `tests.unit.test_pass1_feedback_constraints._FakeQueue.put` | 91 |
| method | `tests.unit.test_pass1_feedback_constraints._FakeQueue.qsize` | 94 |
| method | `tests.unit.test_pass1_feedback_constraints._FakeQueue.get_nowait` | 97 |
| function | `tests.unit.test_pass1_feedback_constraints._fake_event` | 103 |
| function | `tests.unit.test_pass1_feedback_constraints.test_ingestion_rejects_praise_only_and_missing_path` | 119 |
| function | `tests.unit.test_pass1_feedback_constraints.test_ingestion_caps_per_reviewer_cycle` | 149 |
| function | `tests.unit.test_pass1_feedback_constraints.test_feeder_pause_on_unaddressed_backlog` | 170 |
| function | `tests.unit.test_pass1_feedback_constraints.test_prio_intake_capped_and_seed_boosted` | 195 |
| function | `tests.unit.test_pass1_feedback_constraints.test_prio_intake_seed_survives_newer_reviewer_cap` | 230 |
| function | `tests.unit.test_pass1_feedback_constraints.test_prio_quality_filter_keeps_seed_tasks_and_messages` | 270 |

### `tests/unit/test_path_normalization.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| function | `tests.unit.test_path_normalization.project_env` | 16 |
| class | `tests.unit.test_path_normalization.TestResolveContainedPath` | 49 |
| method | `tests.unit.test_path_normalization.TestResolveContainedPath.test_relative_path_resolves_inside_project` | 50 |
| method | `tests.unit.test_path_normalization.TestResolveContainedPath.test_absolute_path_inside_project_accepted` | 58 |
| method | `tests.unit.test_path_normalization.TestResolveContainedPath.test_absolute_path_outside_project_rejected` | 66 |
| method | `tests.unit.test_path_normalization.TestResolveContainedPath.test_traversal_rejected` | 78 |
| class | `tests.unit.test_path_normalization.TestWriteFileToDiskContainment` | 86 |
| method | `tests.unit.test_path_normalization.TestWriteFileToDiskContainment.test_writes_relative_path` | 87 |
| method | `tests.unit.test_path_normalization.TestWriteFileToDiskContainment.test_rejects_outside_absolute` | 97 |
| class | `tests.unit.test_path_normalization.TestMaterializePathNormalizationLogic` | 108 |
| method | `tests.unit.test_path_normalization.TestMaterializePathNormalizationLogic.test_normalize_written_path_to_relative` | 114 |
| method | `tests.unit.test_path_normalization.TestMaterializePathNormalizationLogic.test_outside_absolute_cannot_normalize_for_index_or_git` | 131 |
| method | `tests.unit.test_path_normalization.TestMaterializePathNormalizationLogic.test_git_add_args_use_relative_path_and_project_cwd` | 147 |

### `tests/unit/test_path_targets.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| class | `tests.unit.test_path_targets.TestSanitizePathToken` | 44 |
| method | `tests.unit.test_path_targets.TestSanitizePathToken.test_sanitize_cases` | 46 |
| class | `tests.unit.test_path_targets.TestExtractFilesNeeded` | 93 |
| method | `tests.unit.test_path_targets.TestExtractFilesNeeded.test_extract_cases` | 99 |
| class | `tests.unit.test_path_targets.TestIsValidEditTargetPath` | 103 |
| method | `tests.unit.test_path_targets.TestIsValidEditTargetPath.test_accepts_clean_relative` | 104 |
| method | `tests.unit.test_path_targets.TestIsValidEditTargetPath.test_rejects_traversal` | 107 |
| method | `tests.unit.test_path_targets.TestIsValidEditTargetPath.test_rejects_none` | 110 |
| method | `tests.unit.test_path_targets.TestIsValidEditTargetPath.test_rejects_markdown_wrapper` | 113 |
| method | `tests.unit.test_path_targets.TestIsValidEditTargetPath.test_accepts_after_markdown_only_if_sanitizable` | 116 |
| class | `tests.unit.test_path_targets.TestCreateFilePathValidation` | 122 |
| method | `tests.unit.test_path_targets.TestCreateFilePathValidation.test_create_file_clean_path_ok` | 125 |
| method | `tests.unit.test_path_targets.TestCreateFilePathValidation.test_create_file_markdown_path_rejected` | 145 |
| method | `tests.unit.test_path_targets.TestCreateFilePathValidation.test_create_file_traversal_rejected` | 164 |
| method | `tests.unit.test_path_targets.TestCreateFilePathValidation.test_top_level_target_markdown_rejected` | 170 |

### `tests/unit/test_post_materialize.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| class | `tests.unit.test_post_materialize._FakePool` | 26 |
| method | `tests.unit.test_post_materialize._FakePool.__init__` | 27 |
| method | `tests.unit.test_post_materialize._FakePool.queue_file_change` | 31 |
| function | `tests.unit.test_post_materialize.running_pool` | 36 |
| class | `tests.unit.test_post_materialize.TestQueueLocalizedVerify` | 43 |
| method | `tests.unit.test_post_materialize.TestQueueLocalizedVerify.test_exactly_one_high_priority_entry_per_path` | 44 |
| method | `tests.unit.test_post_materialize.TestQueueLocalizedVerify.test_no_queue_when_pool_not_running` | 51 |
| class | `tests.unit.test_post_materialize.TestNotifyPathChanged` | 56 |
| method | `tests.unit.test_post_materialize.TestNotifyPathChanged.test_creates_single_orchestrator_message` | 57 |
| class | `tests.unit.test_post_materialize.TestApplyMaterializeOutcome` | 67 |
| method | `tests.unit.test_post_materialize.TestApplyMaterializeOutcome.test_success_increments_counters_and_localizes_verify` | 68 |
| method | `tests.unit.test_post_materialize.TestApplyMaterializeOutcome.test_git_failure_no_celebration_and_cites_files` | 81 |
| method | `tests.unit.test_post_materialize.TestApplyMaterializeOutcome.test_other_failure_increments_failure_counter` | 109 |
| class | `tests.unit.test_post_materialize.TestParseHookCitedFiles` | 119 |
| method | `tests.unit.test_post_materialize.TestParseHookCitedFiles.test_parses_ruff_flake_diagnostics` | 120 |
| method | `tests.unit.test_post_materialize.TestParseHookCitedFiles.test_dedupes_and_caps` | 129 |
| method | `tests.unit.test_post_materialize.TestParseHookCitedFiles.test_empty_and_junk` | 135 |

### `tests/unit/test_preflight.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| function | `tests.unit.test_preflight.test_preflight_ok_in_test_mode` | 6 |
| function | `tests.unit.test_preflight.test_preflight_fails_without_keys_outside_test_mode` | 25 |
| function | `tests.unit.test_preflight.test_preflight_skips_non_unattended_mode` | 45 |
| function | `tests.unit.test_preflight.test_unattended_config_seed_queue_order` | 53 |

### `tests/unit/test_prioritizer_budget_cap.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| class | `tests.unit.test_prioritizer_budget_cap.FakeItem` | 15 |
| method | `tests.unit.test_prioritizer_budget_cap.FakeItem.__init__` | 16 |
| function | `tests.unit.test_prioritizer_budget_cap._make_worker` | 29 |
| class | `tests.unit.test_prioritizer_budget_cap.TestPrioritizerBatchCap` | 47 |
| method | `tests.unit.test_prioritizer_budget_cap.TestPrioritizerBatchCap.test_caps_at_max_batches_per_cycle` | 48 |
| method | `tests.unit.test_prioritizer_budget_cap.TestPrioritizerBatchCap.test_all_items_when_under_cap` | 60 |
| method | `tests.unit.test_prioritizer_budget_cap.TestPrioritizerBatchCap.test_probe_mode_still_single_batch` | 72 |
| method | `tests.unit.test_prioritizer_budget_cap.TestPrioritizerBatchCap.test_no_batches_when_all_categorized` | 83 |

### `tests/unit/test_prioritizer_circuit.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| class | `tests.unit.test_prioritizer_circuit.FakeItem` | 11 |
| method | `tests.unit.test_prioritizer_circuit.FakeItem.__init__` | 12 |
| function | `tests.unit.test_prioritizer_circuit._make_worker` | 22 |
| function | `tests.unit.test_prioritizer_circuit.test_all_items_categorized_skips_api` | 40 |
| function | `tests.unit.test_prioritizer_circuit.test_circuit_breaker_aborts_after_consecutive_failures` | 59 |
| function | `tests.unit.test_prioritizer_circuit.test_circuit_open_publishes_surface_event` | 69 |
| function | `tests.unit.test_prioritizer_circuit.test_successful_batches_do_not_trip_breaker` | 81 |
| function | `tests.unit.test_prioritizer_circuit.test_open_circuit_probes_single_batch` | 88 |
| function | `tests.unit.test_prioritizer_circuit.test_successful_probe_reopens_circuit` | 100 |

### `tests/unit/test_prioritizer_phases.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| function | `tests.unit.test_prioritizer_phases._fb` | 10 |
| function | `tests.unit.test_prioritizer_phases.test_score_category_applies_mock_scores` | 34 |
| function | `tests.unit.test_prioritizer_phases.test_cross_category_ranking_fallback_sorts_by_score` | 51 |
| function | `tests.unit.test_prioritizer_phases.test_cross_category_ranking_uses_llm_order` | 68 |
| function | `tests.unit.test_prioritizer_phases.test_post_results_writes_orchestrator_message` | 90 |
| function | `tests.unit.test_prioritizer_phases._orchestrator_msg_count` | 117 |
| function | `tests.unit.test_prioritizer_phases.test_identical_ranked_set_is_not_reposted` | 127 |
| function | `tests.unit.test_prioritizer_phases.test_changed_ranked_set_is_reposted_after_skip` | 138 |

### `tests/unit/test_prioritizer_quality.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| function | `tests.unit.test_prioritizer_quality._item` | 8 |
| function | `tests.unit.test_prioritizer_quality.test_filter_dismisses_placeholder_and_short_messages` | 23 |
| function | `tests.unit.test_prioritizer_quality.test_filter_dismisses_category_echo` | 61 |

### `tests/unit/test_prompt_snapshots.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| function | `tests.unit.test_prompt_snapshots.prompts` | 23 |
| function | `tests.unit.test_prompt_snapshots._system` | 29 |
| class | `tests.unit.test_prompt_snapshots.TestDeveloperPrompt` | 37 |
| method | `tests.unit.test_prompt_snapshots.TestDeveloperPrompt.test_requires_json_and_operations` | 38 |
| method | `tests.unit.test_prompt_snapshots.TestDeveloperPrompt.test_mentions_edit_modes` | 43 |
| class | `tests.unit.test_prompt_snapshots.TestReviewerPrompt` | 50 |
| method | `tests.unit.test_prompt_snapshots.TestReviewerPrompt.test_approve_gate` | 51 |
| class | `tests.unit.test_prompt_snapshots.TestOrchestratorPrompt` | 57 |
| method | `tests.unit.test_prompt_snapshots.TestOrchestratorPrompt.test_routing_next_agent` | 58 |
| class | `tests.unit.test_prompt_snapshots.TestSchemaFilesPresent` | 64 |
| method | `tests.unit.test_prompt_snapshots.TestSchemaFilesPresent.test_core_schemas_exist` | 65 |

### `tests/unit/test_proposal_builder.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| class | `tests.unit.test_proposal_builder.TestGetAffectedGuids` | 12 |
| method | `tests.unit.test_proposal_builder.TestGetAffectedGuids.test_replace_block_guids` | 13 |
| method | `tests.unit.test_proposal_builder.TestGetAffectedGuids.test_delete_lines_guids` | 22 |
| method | `tests.unit.test_proposal_builder.TestGetAffectedGuids.test_insert_after_with_guid` | 31 |
| method | `tests.unit.test_proposal_builder.TestGetAffectedGuids.test_insert_after_without_guid` | 38 |
| method | `tests.unit.test_proposal_builder.TestGetAffectedGuids.test_find_replace_has_no_guids` | 45 |
| class | `tests.unit.test_proposal_builder.TestCreateProposal` | 52 |
| method | `tests.unit.test_proposal_builder.TestCreateProposal.test_create_find_replace_persists_task_id` | 53 |
| method | `tests.unit.test_proposal_builder.TestCreateProposal.test_create_with_fallback_metadata` | 96 |
| method | `tests.unit.test_proposal_builder.TestCreateProposal.test_invalid_payload_returns_error` | 139 |
| method | `tests.unit.test_proposal_builder.TestCreateProposal.test_update_status_approve` | 149 |
| method | `tests.unit.test_proposal_builder.TestCreateProposal.test_update_status_rejects_unknown` | 178 |
| method | `tests.unit.test_proposal_builder.TestCreateProposal.test_update_status_without_reviewer` | 181 |

### `tests/unit/test_proposal_builder_regressions.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| class | `tests.unit.test_proposal_builder_regressions._RecordingConn` | 17 |
| method | `tests.unit.test_proposal_builder_regressions._RecordingConn.__init__` | 20 |
| method | `tests.unit.test_proposal_builder_regressions._RecordingConn.__getattr__` | 24 |
| method | `tests.unit.test_proposal_builder_regressions._RecordingConn.execute` | 27 |
| function | `tests.unit.test_proposal_builder_regressions.recording_proposal_builder` | 33 |
| class | `tests.unit.test_proposal_builder_regressions.TestNoRuntimeAlter` | 49 |
| method | `tests.unit.test_proposal_builder_regressions.TestNoRuntimeAlter.test_proposal_create_uses_schema_columns_not_runtime_ddl` | 50 |
| class | `tests.unit.test_proposal_builder_regressions.TestBatchHashCapture` | 77 |
| method | `tests.unit.test_proposal_builder_regressions.TestBatchHashCapture._seed_with_guids` | 78 |
| method | `tests.unit.test_proposal_builder_regressions.TestBatchHashCapture.test_hashes_fetched_in_single_in_query` | 93 |
| method | `tests.unit.test_proposal_builder_regressions.TestBatchHashCapture.test_no_guids_short_circuits` | 120 |
| class | `tests.unit.test_proposal_builder_regressions.TestBareSingleOpPayload` | 140 |
| method | `tests.unit.test_proposal_builder_regressions.TestBareSingleOpPayload.test_bare_payload_creates_proposal` | 143 |
| method | `tests.unit.test_proposal_builder_regressions.TestBareSingleOpPayload.test_payload_missing_operations_and_type_rejected` | 160 |
| method | `tests.unit.test_proposal_builder_regressions.TestBareSingleOpPayload.test_empty_operations_list_rejected` | 171 |
| class | `tests.unit.test_proposal_builder_regressions.TestDeleteThenRecreate` | 187 |
| method | `tests.unit.test_proposal_builder_regressions.TestDeleteThenRecreate._propose` | 190 |
| method | `tests.unit.test_proposal_builder_regressions.TestDeleteThenRecreate.test_recreate_reuses_soft_deleted_file_id` | 206 |
| method | `tests.unit.test_proposal_builder_regressions.TestDeleteThenRecreate.test_delete_then_recreate_has_single_file_row` | 230 |

### `tests/unit/test_query_developer_responses.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| function | `tests.unit.test_query_developer_responses._seed_archive` | 8 |
| function | `tests.unit.test_query_developer_responses._seed_effectiveness_tables` | 19 |
| function | `tests.unit.test_query_developer_responses.test_run_full_diagnostic_smoke` | 116 |
| function | `tests.unit.test_query_developer_responses.test_show_run_effectiveness_smoke` | 140 |
| function | `tests.unit.test_query_developer_responses.test_main_help_exits_zero` | 168 |
| function | `tests.unit.test_query_developer_responses.test_show_git_failures_dumps_events` | 180 |
| function | `tests.unit.test_query_developer_responses.test_show_file_line_counts_hides_sensitive_paths` | 219 |
| function | `tests.unit.test_query_developer_responses.test_dump_lists_shell_session_proposals` | 246 |
| function | `tests.unit.test_query_developer_responses.test_dump_prints_data_window_stamp` | 269 |
| function | `tests.unit.test_query_developer_responses.test_data_window_watermark_uses_normalized_record_timestamps` | 292 |

### `tests/unit/test_rate_limit_headers.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| function | `tests.unit.test_rate_limit_headers.test_parse_ms_epoch_reset` | 21 |
| function | `tests.unit.test_rate_limit_headers.test_parse_seconds_epoch_reset` | 25 |
| function | `tests.unit.test_rate_limit_headers.test_parse_relative_seconds_reset` | 29 |
| function | `tests.unit.test_rate_limit_headers.test_parse_invalid_reset_returns_none` | 33 |
| function | `tests.unit.test_rate_limit_headers.test_burst_when_remaining_positive_no_reset` | 39 |
| function | `tests.unit.test_rate_limit_headers.test_quota_when_remaining_zero` | 47 |
| function | `tests.unit.test_rate_limit_headers.test_reset_header_alone_is_not_quota` | 52 |
| function | `tests.unit.test_rate_limit_headers.test_quota_via_body_tokens_without_headers` | 58 |
| function | `tests.unit.test_rate_limit_headers.test_quota_via_free_usage_limit_error_type` | 67 |
| function | `tests.unit.test_rate_limit_headers.test_headers_case_insensitive` | 80 |
| function | `tests.unit.test_rate_limit_headers.test_non_dict_like_headers_safe` | 86 |
| function | `tests.unit.test_rate_limit_headers.test_advertised_wait_from_retry_after_header` | 92 |
| function | `tests.unit.test_rate_limit_headers.test_advertised_wait_from_retry_after_http_date` | 96 |
| function | `tests.unit.test_rate_limit_headers.test_advertised_wait_from_body_retry_after_seconds` | 103 |
| function | `tests.unit.test_rate_limit_headers.test_advertised_wait_status_defaults` | 108 |
| function | `tests.unit.test_rate_limit_headers.test_advertised_wait_unparseable_uses_status_default` | 114 |
| function | `tests.unit.test_rate_limit_headers.test_advertised_wait_above_max_returned_uncapped` | 118 |
| function | `tests.unit.test_rate_limit_headers.test_advertised_wait_unknown_status_returns_none` | 125 |
| function | `tests.unit.test_rate_limit_headers.test_advertised_wait_clamps_min_to_one` | 130 |

### `tests/unit/test_rate_limiter.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| function | `tests.unit.test_rate_limiter.test_rate_limiter_basic_no_wait` | 15 |
| function | `tests.unit.test_rate_limiter.test_rate_limiter_per_endpoint_isolation` | 23 |
| function | `tests.unit.test_rate_limiter.test_rate_limiter_multiple_calls` | 35 |
| function | `tests.unit.test_rate_limiter.test_rate_limiter_thread_safety` | 42 |
| function | `tests.unit.test_rate_limiter.test_set_max_calls` | 63 |
| function | `tests.unit.test_rate_limiter.test_aimd_rate_limited_halves_effective_capacity` | 70 |
| function | `tests.unit.test_rate_limiter.test_aimd_success_ramps_back_up` | 78 |
| function | `tests.unit.test_rate_limiter.test_aimd_scale_floors_at_minimum` | 91 |
| function | `tests.unit.test_rate_limiter.test_aimd_set_max_calls_resets_scale` | 99 |
| function | `tests.unit.test_rate_limiter.test_global_limit_triggers_sleep_with_mocked_time` | 108 |
| function | `tests.unit.test_rate_limiter.test_old_calls_evicted_from_window` | 138 |
| function | `tests.unit.test_rate_limiter.test_per_endpoint_uses_config_limit` | 154 |

### `tests/unit/test_recursive_fallback.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| function | `tests.unit.test_recursive_fallback._isolate_freeze_registry` | 25 |
| function | `tests.unit.test_recursive_fallback.ep_config` | 37 |
| function | `tests.unit.test_recursive_fallback._resp` | 62 |
| class | `tests.unit.test_recursive_fallback._Health` | 72 |
| method | `tests.unit.test_recursive_fallback._Health.__init__` | 73 |
| method | `tests.unit.test_recursive_fallback._Health.is_available` | 80 |
| method | `tests.unit.test_recursive_fallback._Health.time_until_available` | 83 |
| method | `tests.unit.test_recursive_fallback._Health.mark_success` | 86 |
| method | `tests.unit.test_recursive_fallback._Health.mark_failure` | 90 |
| class | `tests.unit.test_recursive_fallback._Ep` | 96 |
| method | `tests.unit.test_recursive_fallback._Ep.__init__` | 97 |
| method | `tests.unit.test_recursive_fallback._Ep.extract_response` | 103 |
| class | `tests.unit.test_recursive_fallback._PingPongManager` | 107 |
| method | `tests.unit.test_recursive_fallback._PingPongManager.__init__` | 110 |
| method | `tests.unit.test_recursive_fallback._PingPongManager.normalize_model_reference` | 118 |
| method | `tests.unit.test_recursive_fallback._PingPongManager.validate_model` | 124 |
| method | `tests.unit.test_recursive_fallback._PingPongManager.build_payload` | 127 |
| method | `tests.unit.test_recursive_fallback._PingPongManager.get_api_key` | 135 |
| method | `tests.unit.test_recursive_fallback._PingPongManager.get_fallback_model` | 138 |
| function | `tests.unit.test_recursive_fallback.call_env` | 153 |
| function | `tests.unit.test_recursive_fallback.test_key_locked_falls_back_once_to_healthy_b` | 170 |
| function | `tests.unit.test_recursive_fallback.test_both_locked_does_not_infinite_loop` | 204 |
| function | `tests.unit.test_recursive_fallback.test_budget_ping_pong_cannot_exceed_depth` | 233 |
| function | `tests.unit.test_recursive_fallback.test_latch_ping_pong_cannot_exceed_depth` | 264 |
| function | `tests.unit.test_recursive_fallback.test_is_available_does_not_call_sync_support_freeze` | 279 |
| function | `tests.unit.test_recursive_fallback.test_all_endpoints_latched_does_not_call_is_available` | 294 |
| function | `tests.unit.test_recursive_fallback.test_sync_freeze_does_not_recurse_when_guard_forced_off` | 312 |
| function | `tests.unit.test_recursive_fallback.test_log_fallback_swallows_recursion_error` | 335 |
| function | `tests.unit.test_recursive_fallback.test_get_fallback_model_skips_seen_endpoints` | 346 |

### `tests/unit/test_repo_env.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| function | `tests.unit.test_repo_env.test_detect_pre_commit_hook_framework_config` | 8 |
| function | `tests.unit.test_repo_env.test_detect_pre_commit_hook_git_dir` | 13 |
| function | `tests.unit.test_repo_env.test_detect_no_hook` | 20 |
| function | `tests.unit.test_repo_env.test_card_disabled_git` | 24 |
| function | `tests.unit.test_repo_env.test_card_enabled_with_hook` | 30 |
| function | `tests.unit.test_repo_env.test_card_enabled_without_hook` | 37 |
| function | `tests.unit.test_repo_env.test_developer_prompt_includes_env_card` | 42 |

### `tests/unit/test_reporter_double_close.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| class | `tests.unit.test_reporter_double_close.TestReporterSaveState` | 14 |
| method | `tests.unit.test_reporter_double_close.TestReporterSaveState.test_save_state_does_not_double_close` | 15 |
| method | `tests.unit.test_reporter_double_close.TestReporterSaveState.test_save_state_executes_insert` | 39 |

### `tests/unit/test_resource_controller.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| class | `tests.unit.test_resource_controller.TestAgentProfile` | 16 |
| method | `tests.unit.test_resource_controller.TestAgentProfile.test_agent_profile_creation` | 19 |
| method | `tests.unit.test_resource_controller.TestAgentProfile.test_agent_profile_to_dict_roundtrip` | 31 |
| class | `tests.unit.test_resource_controller.TestResourceState` | 47 |
| method | `tests.unit.test_resource_controller.TestResourceState.test_resource_state_full_creation` | 50 |
| method | `tests.unit.test_resource_controller.TestResourceState.test_resource_state_string_representation` | 65 |
| method | `tests.unit.test_resource_controller.TestResourceState.test_resource_state_rate_limited_default_and_suffix` | 81 |
| class | `tests.unit.test_resource_controller.TestThrottleDecision` | 111 |
| method | `tests.unit.test_resource_controller.TestThrottleDecision.test_throttle_decision_moderate` | 114 |
| method | `tests.unit.test_resource_controller.TestThrottleDecision.test_throttle_decision_to_dict` | 127 |
| class | `tests.unit.test_resource_controller.TestHeuristicOptimizer` | 142 |
| method | `tests.unit.test_resource_controller.TestHeuristicOptimizer.test_optimizer_can_be_instantiated` | 145 |
| method | `tests.unit.test_resource_controller.TestHeuristicOptimizer.test_optimizer_returns_decision` | 150 |
| method | `tests.unit.test_resource_controller.TestHeuristicOptimizer.test_optimizer_rate_limited_feedback_biases_decision` | 166 |
| class | `tests.unit.test_resource_controller.TestResourceControllerWorker` | 191 |
| method | `tests.unit.test_resource_controller.TestResourceControllerWorker.test_resource_controller_worker_instantiation` | 194 |
| method | `tests.unit.test_resource_controller.TestResourceControllerWorker.test_resource_controller_worker_start_stop_lifecycle` | 201 |
| method | `tests.unit.test_resource_controller.TestResourceControllerWorker.test_worker_uses_optimizer_gracefully` | 211 |
| method | `tests.unit.test_resource_controller.TestResourceControllerWorker.test_worker_respects_resource_controller_config` | 221 |
| method | `tests.unit.test_resource_controller.TestResourceControllerWorker.test_worker_thread_safety_of_stop` | 228 |
| method | `tests.unit.test_resource_controller.TestResourceControllerWorker.test_apply_decision_adjusts_resolved_endpoint_rate_limiter` | 242 |

### `tests/unit/test_response_cleaner.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| function | `tests.unit.test_response_cleaner.test_extract_plain_json` | 10 |
| function | `tests.unit.test_response_cleaner.test_extract_fenced_json` | 18 |
| function | `tests.unit.test_response_cleaner.test_extract_with_prefix_noise` | 25 |
| function | `tests.unit.test_response_cleaner.test_extract_empty_fails` | 33 |
| function | `tests.unit.test_response_cleaner.test_extract_no_brace_fails` | 39 |
| function | `tests.unit.test_response_cleaner.test_clean_llm_response_returns_none_on_garbage` | 45 |
| function | `tests.unit.test_response_cleaner.test_clean_llm_response_success` | 49 |

### `tests/unit/test_response_parser.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| function | `tests.unit.test_response_parser.test_empty_response` | 9 |
| function | `tests.unit.test_response_parser.test_whitespace_only` | 17 |
| function | `tests.unit.test_response_parser.test_plain_json_object` | 23 |
| function | `tests.unit.test_response_parser.test_markdown_json_fence` | 31 |
| function | `tests.unit.test_response_parser.test_generic_code_block_with_json` | 39 |
| function | `tests.unit.test_response_parser.test_code_block_with_language_tag_stripped` | 47 |
| function | `tests.unit.test_response_parser.test_code_block_json5_tag_stripped` | 56 |
| function | `tests.unit.test_response_parser.test_tagged_block_with_non_json_body_is_not_code` | 65 |
| function | `tests.unit.test_response_parser.test_json_tag_with_non_json_body_is_malformed` | 73 |
| function | `tests.unit.test_response_parser.test_raw_brace_slice_with_preamble` | 80 |
| function | `tests.unit.test_response_parser.test_raw_array_slice` | 89 |
| function | `tests.unit.test_response_parser.test_no_json_is_malformed` | 101 |
| function | `tests.unit.test_response_parser.test_invalid_json_inside_fences` | 108 |
| function | `tests.unit.test_response_parser.test_free_text_without_braces_is_malformed` | 116 |
| function | `tests.unit.test_response_parser.test_prefers_earliest_structure` | 124 |
| function | `tests.unit.test_response_parser.test_truncated_object_fails` | 133 |

### `tests/unit/test_reviewer_gate.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| function | `tests.unit.test_reviewer_gate._make_proposal` | 21 |
| function | `tests.unit.test_reviewer_gate._feedback_rows_for` | 39 |
| class | `tests.unit.test_reviewer_gate.TestParseReviewerVerdict` | 54 |
| method | `tests.unit.test_reviewer_gate.TestParseReviewerVerdict.test_empty_response_rejects` | 56 |
| method | `tests.unit.test_reviewer_gate.TestParseReviewerVerdict.test_valid_approve` | 62 |
| method | `tests.unit.test_reviewer_gate.TestParseReviewerVerdict.test_lowercase_approve_normalizes` | 71 |
| method | `tests.unit.test_reviewer_gate.TestParseReviewerVerdict.test_markdown_fenced_approve_parses` | 77 |
| method | `tests.unit.test_reviewer_gate.TestParseReviewerVerdict.test_prose_response_rejects` | 83 |
| method | `tests.unit.test_reviewer_gate.TestParseReviewerVerdict.test_prose_with_brace_mention_still_rejects` | 89 |
| method | `tests.unit.test_reviewer_gate.TestParseReviewerVerdict.test_missing_decision_key_rejects` | 95 |
| method | `tests.unit.test_reviewer_gate.TestParseReviewerVerdict.test_unknown_decision_value_rejects` | 103 |
| method | `tests.unit.test_reviewer_gate.TestParseReviewerVerdict.test_explicit_reject_works` | 109 |
| method | `tests.unit.test_reviewer_gate.TestParseReviewerVerdict.test_defaults_for_blank_fields` | 117 |
| method | `tests.unit.test_reviewer_gate.TestParseReviewerVerdict.test_string_suggestions_split_into_list` | 124 |
| class | `tests.unit.test_reviewer_gate.TestHandleReviewerRejection` | 141 |
| method | `tests.unit.test_reviewer_gate.TestHandleReviewerRejection.test_records_rejection` | 142 |
| class | `tests.unit.test_reviewer_gate.TestLegacyDeveloperFailClosed` | 182 |
| method | `tests.unit.test_reviewer_gate.TestLegacyDeveloperFailClosed._seed_file` | 183 |
| method | `tests.unit.test_reviewer_gate.TestLegacyDeveloperFailClosed.test_non_json_reviewer_response_rejects` | 193 |
| method | `tests.unit.test_reviewer_gate.TestLegacyDeveloperFailClosed.test_fenced_approve_still_materializes` | 239 |
| class | `tests.unit.test_reviewer_gate.TestShellGateFailClosed` | 283 |
| method | `tests.unit.test_reviewer_gate.TestShellGateFailClosed.test_non_json_reviewer_response_rejects` | 284 |
| class | `tests.unit.test_reviewer_gate.TestRequestReviewRetry` | 320 |
| method | `tests.unit.test_reviewer_gate.TestRequestReviewRetry._run` | 323 |
| method | `tests.unit.test_reviewer_gate.TestRequestReviewRetry.test_approve_first_is_single_call` | 336 |
| method | `tests.unit.test_reviewer_gate.TestRequestReviewRetry.test_semantic_reject_is_never_retried` | 342 |
| method | `tests.unit.test_reviewer_gate.TestRequestReviewRetry.test_transport_none_is_never_retried` | 348 |
| method | `tests.unit.test_reviewer_gate.TestRequestReviewRetry.test_empty_then_valid_approve_retries_once` | 354 |
| method | `tests.unit.test_reviewer_gate.TestRequestReviewRetry.test_empty_persists_capped_at_two_attempts` | 359 |
| method | `tests.unit.test_reviewer_gate.TestRequestReviewRetry.test_garbage_then_garbage_rejects_real_json_of_intent` | 365 |
| method | `tests.unit.test_reviewer_gate.TestRequestReviewRetry.test_unknown_decision_retries_then_rejects_on_again` | 371 |
| method | `tests.unit.test_reviewer_gate.TestRequestReviewRetry.test_calls_used_reflects_actual_plays` | 379 |

### `tests/unit/test_reviewer_retry_discipline.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| class | `tests.unit.test_reviewer_retry_discipline.FakeEvent` | 12 |
| method | `tests.unit.test_reviewer_retry_discipline.FakeEvent.__init__` | 13 |
| function | `tests.unit.test_reviewer_retry_discipline._make_pool` | 21 |
| function | `tests.unit.test_reviewer_retry_discipline.test_empty_response_stops_retry_ladder` | 41 |
| function | `tests.unit.test_reviewer_retry_discipline.test_malformed_json_retries_with_stricter_prompt` | 48 |
| function | `tests.unit.test_reviewer_retry_discipline.test_valid_json_parses_first_attempt` | 58 |

### `tests/unit/test_schema_migration.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| function | `tests.unit.test_schema_migration._create_legacy_edit_proposals_db` | 9 |
| function | `tests.unit.test_schema_migration.test_migrate_adds_task_id_and_mode_columns` | 30 |
| function | `tests.unit.test_schema_migration.test_migrate_adds_token_log_endpoint_name` | 66 |
| function | `tests.unit.test_schema_migration.test_migrate_adds_model_health_retry_after_s` | 92 |
| function | `tests.unit.test_schema_migration.test_ensure_column_is_idempotent` | 128 |
| function | `tests.unit.test_schema_migration.test_split_sql_keeps_semicolon_in_comment_and_string` | 141 |

### `tests/unit/test_seed_feedback.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| function | `tests.unit.test_seed_feedback.test_inject_seed_feedback_creates_row` | 6 |
| function | `tests.unit.test_seed_feedback.test_inject_seed_feedback_is_idempotent` | 25 |
| function | `tests.unit.test_seed_feedback.test_inject_seed_feedback_ignores_empty_command` | 37 |
| function | `tests.unit.test_seed_feedback.test_backlog_overrides_exclude_seed_task` | 47 |

### `tests/unit/test_shell_developer.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| function | `tests.unit.test_shell_developer.test_extract_bash_command_returns_last_block` | 22 |
| function | `tests.unit.test_shell_developer.test_extract_bash_command_none_when_missing` | 27 |
| function | `tests.unit.test_shell_developer.test_extract_finish_returns_summary_without_token` | 32 |
| function | `tests.unit.test_shell_developer.test_extract_finish_absent` | 38 |
| function | `tests.unit.test_shell_developer.test_change_to_operation_mapping` | 42 |
| function | `tests.unit.test_shell_developer.test_bounded_keeps_short_text_untouched` | 60 |
| function | `tests.unit.test_shell_developer.test_bounded_cuts_on_newline_boundary_with_marker` | 64 |
| function | `tests.unit.test_shell_developer.test_bounded_no_newline_inside_cut_adds_marker_without_fake_token` | 77 |
| function | `tests.unit.test_shell_developer.git_project` | 90 |
| function | `tests.unit.test_shell_developer.test_worktree_create_collect_cleanup` | 117 |
| function | `tests.unit.test_shell_developer.test_worktree_requires_git_repo` | 139 |
| function | `tests.unit.test_shell_developer.test_worktree_fails_loud_when_project_outside_repo` | 147 |
| function | `tests.unit.test_shell_developer.test_worktree_fails_loud_when_project_gitignored` | 158 |
| function | `tests.unit.test_shell_developer.shell_env` | 182 |
| function | `tests.unit.test_shell_developer.test_turn_success_materializes_approved_proposal` | 215 |
| function | `tests.unit.test_shell_developer.test_gate_presents_full_content_for_full_replace` | 243 |
| function | `tests.unit.test_shell_developer.test_gate_keeps_unified_diff_for_non_full_replace` | 276 |
| function | `tests.unit.test_shell_developer.test_turn_rejection_reports_rejected_status` | 302 |
| function | `tests.unit.test_shell_developer.test_turn_fails_closed_when_reviewer_unavailable` | 327 |
| function | `tests.unit.test_shell_developer.test_turn_fails_closed_on_non_json_verdict` | 346 |
| function | `tests.unit.test_shell_developer.test_turn_fails_closed_on_invalid_decision_value` | 368 |
| function | `tests.unit.test_shell_developer.test_finish_with_final_command_defers_then_finishes` | 390 |
| function | `tests.unit.test_shell_developer.test_early_exit_step_limit_materializes_wip_changes` | 416 |
| function | `tests.unit.test_shell_developer.test_mixed_gate_turn_reports_error_not_success` | 446 |
| class | `tests.unit.test_shell_developer._FakeCursor` | 482 |
| method | `tests.unit.test_shell_developer._FakeCursor.__init__` | 483 |
| method | `tests.unit.test_shell_developer._FakeCursor.fetchall` | 486 |
| class | `tests.unit.test_shell_developer._FakeConn` | 490 |
| method | `tests.unit.test_shell_developer._FakeConn.__init__` | 493 |
| method | `tests.unit.test_shell_developer._FakeConn.execute` | 496 |
| method | `tests.unit.test_shell_developer._FakeConn.__enter__` | 499 |
| method | `tests.unit.test_shell_developer._FakeConn.__exit__` | 502 |
| function | `tests.unit.test_shell_developer.test_worktree_syncs_governed_db_state` | 506 |
| function | `tests.unit.test_shell_developer.test_collect_changes_exclude_sync_drift` | 526 |
| function | `tests.unit.test_shell_developer.test_max_file_bytes_config_respected` | 552 |
| function | `tests.unit.test_shell_developer.test_out_of_scope_changes_warned_and_excluded` | 565 |
| function | `tests.unit.test_shell_developer.test_from_config_validates_on_test_failure` | 595 |
| function | `tests.unit.test_shell_developer.test_feedback_addressed_only_for_materialized_files` | 616 |

### `tests/unit/test_shell_developer_feed_fixes.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| function | `tests.unit.test_shell_developer_feed_fixes._repo` | 14 |
| function | `tests.unit.test_shell_developer_feed_fixes._real_session` | 28 |
| function | `tests.unit.test_shell_developer_feed_fixes._app_text` | 57 |
| function | `tests.unit.test_shell_developer_feed_fixes.test_edit_block_replace_applies_edit_and_observes_state` | 64 |
| function | `tests.unit.test_shell_developer_feed_fixes.test_edit_block_full_replace` | 85 |
| function | `tests.unit.test_shell_developer_feed_fixes.test_edit_old_not_found_reports_error_then_recovers` | 97 |
| function | `tests.unit.test_shell_developer_feed_fixes.test_edit_ambiguous_old_fails` | 111 |
| function | `tests.unit.test_shell_developer_feed_fixes.test_edit_path_traversal_rejected` | 128 |
| function | `tests.unit.test_shell_developer_feed_fixes.test_chat_edit_row_applies_edit` | 141 |
| function | `tests.unit.test_shell_developer_feed_fixes.test_stall_tripwire_fires_on_repeated_failing_command` | 169 |
| function | `tests.unit.test_shell_developer_feed_fixes.test_stall_tripwire_does_not_fire_on_unique_successful_steps` | 182 |
| function | `tests.unit.test_shell_developer_feed_fixes.test_research_session_finish_does_not_stall` | 199 |
| function | `tests.unit.test_shell_developer_feed_fixes.test_change_state_since_baseline_reports_agent_change` | 217 |
| function | `tests.unit.test_shell_developer_feed_fixes.test_task_is_targeted_by_seed_file` | 233 |
| function | `tests.unit.test_shell_developer_feed_fixes.test_task_is_targeted_by_decision` | 244 |
| function | `tests.unit.test_shell_developer_feed_fixes.test_exploratory_cap_and_note` | 250 |

### `tests/unit/test_shell_developer_llm_resilience.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| function | `tests.unit.test_shell_developer_llm_resilience._session` | 26 |
| class | `tests.unit.test_shell_developer_llm_resilience._FakeWorktree` | 37 |
| method | `tests.unit.test_shell_developer_llm_resilience._FakeWorktree.run_command` | 38 |
| method | `tests.unit.test_shell_developer_llm_resilience._FakeWorktree.run_test_command` | 41 |
| method | `tests.unit.test_shell_developer_llm_resilience._FakeWorktree.working_dir` | 44 |
| function | `tests.unit.test_shell_developer_llm_resilience._install_rc_stub` | 48 |
| function | `tests.unit.test_shell_developer_llm_resilience._install_endpoint_manager` | 58 |
| function | `tests.unit.test_shell_developer_llm_resilience._install_llm_script` | 89 |
| function | `tests.unit.test_shell_developer_llm_resilience._capture_health_records` | 115 |
| function | `tests.unit.test_shell_developer_llm_resilience.test_transient_failure_backs_off_retries_and_finishes` | 124 |
| function | `tests.unit.test_shell_developer_llm_resilience.test_all_transient_failures_gives_up_truthfully_with_metadata` | 155 |
| function | `tests.unit.test_shell_developer_llm_resilience.test_token_budget_retries_when_another_endpoint_has_room` | 172 |
| function | `tests.unit.test_shell_developer_llm_resilience.test_token_budget_gives_up_when_every_endpoint_is_dead` | 196 |
| function | `tests.unit.test_shell_developer_llm_resilience.test_permanent_failure_does_not_retry` | 213 |
| function | `tests.unit.test_shell_developer_llm_resilience.test_resolve_developer_model_uses_agent_prefs_when_no_override` | 232 |
| function | `tests.unit.test_shell_developer_llm_resilience.test_resolve_developer_model_prefers_rc_override` | 241 |
| function | `tests.unit.test_shell_developer_llm_resilience.test_resolve_developer_model_ignores_unknown_override` | 253 |
| function | `tests.unit.test_shell_developer_llm_resilience.test_serialize_exposes_failure_metadata` | 270 |
| function | `tests.unit.test_shell_developer_llm_resilience._real_health_db` | 302 |
| function | `tests.unit.test_shell_developer_llm_resilience.test_recent_failure_kind_reads_recorded_event_real_db` | 307 |
| function | `tests.unit.test_shell_developer_llm_resilience.test_recent_failure_detail_reads_stored_excerpt_real_db` | 315 |
| function | `tests.unit.test_shell_developer_llm_resilience.test_recent_failure_kind_real_db_missing_refs_return_empty` | 333 |
| function | `tests.unit.test_shell_developer_llm_resilience.test_unknown_kind_records_body_excerpt` | 345 |

### `tests/unit/test_shell_developer_pass1.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| function | `tests.unit.test_shell_developer_pass1.test_system_prompt_contains_required_format_contract` | 21 |
| function | `tests.unit.test_shell_developer_pass1.test_build_instance_prompt_contains_missing_file_safety_rule` | 28 |
| function | `tests.unit.test_shell_developer_pass1.test_session_prompt_inspects_target_not_cwd_evidence` | 38 |
| function | `tests.unit.test_shell_developer_pass1.test_extract_bash_command_recovers_unterminated_fence` | 54 |
| function | `tests.unit.test_shell_developer_pass1.test_extract_bash_command_unterminated_matches_protocol` | 58 |
| function | `tests.unit.test_shell_developer_pass1.test_format_error_diagnostic_reason_recorded` | 65 |
| function | `tests.unit.test_shell_developer_pass1.test_format_error_correction_message_carries_reason_below_threshold` | 77 |
| function | `tests.unit.test_shell_developer_pass1.test_diagnose_shell_reply_unterminated_reason` | 92 |
| function | `tests.unit.test_shell_developer_pass1.test_session_archives_command_step` | 101 |
| function | `tests.unit.test_shell_developer_pass1.test_session_archives_finish_step` | 137 |
| function | `tests.unit.test_shell_developer_pass1.test_session_archives_format_error_step` | 165 |
| function | `tests.unit.test_shell_developer_pass1.test_prose_response_publishes_prose_event` | 191 |
| function | `tests.unit.test_shell_developer_pass1.test_unterminated_fence_publishes_event` | 205 |
| function | `tests.unit.test_shell_developer_pass1.test_repeated_format_error_publishes_event` | 219 |
| function | `tests.unit.test_shell_developer_pass1.test_command_failure_publishes_event` | 235 |
| function | `tests.unit.test_shell_developer_pass1.test_workspace_validation_failure_publishes_event` | 262 |
| function | `tests.unit.test_shell_developer_pass1.test_session_no_mutation_publishes_event` | 284 |
| function | `tests.unit.test_shell_developer_pass1.test_protocol_valid_and_command_outcomes_recorded` | 336 |
| function | `tests.unit.test_shell_developer_pass1.test_protocol_invalid_and_command_failure_outcomes_recorded` | 357 |
| function | `tests.unit.test_shell_developer_pass1._session_with_replies` | 376 |
| function | `tests.unit.test_shell_developer_pass1._patch_call_endpoint` | 387 |
| class | `tests.unit.test_shell_developer_pass1._FakeWorktree` | 401 |
| method | `tests.unit.test_shell_developer_pass1._FakeWorktree.__init__` | 402 |
| method | `tests.unit.test_shell_developer_pass1._FakeWorktree.run_command` | 406 |
| method | `tests.unit.test_shell_developer_pass1._FakeWorktree.working_dir` | 409 |
| method | `tests.unit.test_shell_developer_pass1._FakeWorktree.run_test_command` | 412 |

### `tests/unit/test_shell_developer_protocol_recovery.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| function | `tests.unit.test_shell_developer_protocol_recovery.test_prose_only_classified_as_prose` | 43 |
| function | `tests.unit.test_shell_developer_protocol_recovery.test_unterminated_fence_classified_as_unterminated` | 47 |
| function | `tests.unit.test_shell_developer_protocol_recovery.test_valid_closed_fence_classified_as_valid_block` | 51 |
| function | `tests.unit.test_shell_developer_protocol_recovery.test_finish_inside_block_is_a_block_not_a_finish` | 55 |
| function | `tests.unit.test_shell_developer_protocol_recovery.test_valid_finish_classified_as_finish_session` | 59 |
| function | `tests.unit.test_shell_developer_protocol_recovery.test_missing_file_claim_is_valid_block` | 63 |
| function | `tests.unit.test_shell_developer_protocol_recovery.test_normalize_repairs_unterminated_fence` | 70 |
| function | `tests.unit.test_shell_developer_protocol_recovery.test_normalize_leaves_valid_block_untouched` | 76 |
| function | `tests.unit.test_shell_developer_protocol_recovery.test_normalize_leaves_prose_untouched` | 80 |
| function | `tests.unit.test_shell_developer_protocol_recovery.test_normalize_does_not_repair_missing_file_claim_multiline_prose` | 84 |
| function | `tests.unit.test_shell_developer_protocol_recovery.test_normalize_does_not_repair_empty_command` | 89 |
| function | `tests.unit.test_shell_developer_protocol_recovery.test_normalize_does_not_repair_finish_inside_block` | 94 |
| function | `tests.unit.test_shell_developer_protocol_recovery.test_extract_command_from_valid_block` | 101 |
| function | `tests.unit.test_shell_developer_protocol_recovery.test_extract_command_from_unterminated_fence_recovered` | 105 |
| function | `tests.unit.test_shell_developer_protocol_recovery.test_extract_command_none_from_prose` | 109 |
| function | `tests.unit.test_shell_developer_protocol_recovery.test_extract_command_none_from_finish` | 113 |
| function | `tests.unit.test_shell_developer_protocol_recovery.test_extract_command_ignores_finish_token_in_block` | 117 |
| function | `tests.unit.test_shell_developer_protocol_recovery.test_extract_finish_from_valid_summary` | 125 |
| function | `tests.unit.test_shell_developer_protocol_recovery.test_extract_finish_absent_from_prose` | 129 |
| function | `tests.unit.test_shell_developer_protocol_recovery.test_extract_finish_absent_from_block` | 133 |
| function | `tests.unit.test_shell_developer_protocol_recovery.test_essay_mentioning_finish_token_is_not_a_finish` | 137 |
| function | `tests.unit.test_shell_developer_protocol_recovery.test_canonical_finish_must_be_first_nonempty_line` | 143 |
| function | `tests.unit.test_shell_developer_protocol_recovery.test_diagnose_prose_reason` | 153 |
| function | `tests.unit.test_shell_developer_protocol_recovery.test_diagnose_unterminated_reason` | 157 |
| function | `tests.unit.test_shell_developer_protocol_recovery.test_diagnose_includes_excerpt_and_expected` | 161 |
| function | `tests.unit.test_shell_developer_protocol_recovery.test_all_fixtures_classify_without_error` | 171 |
| function | `tests.unit.test_shell_developer_protocol_recovery.test_all_fixtures_normalize_orm_diagnose_without_error` | 182 |
| function | `tests.unit.test_shell_developer_protocol_recovery.test_chat_table_direct_object_command` | 190 |
| function | `tests.unit.test_shell_developer_protocol_recovery.test_chat_table_list_takes_last_entry` | 197 |
| function | `tests.unit.test_shell_developer_protocol_recovery.test_chat_table_nested_dict_takes_last_entry` | 208 |
| function | `tests.unit.test_shell_developer_protocol_recovery.test_chat_table_finish_action` | 214 |
| function | `tests.unit.test_shell_developer_protocol_recovery.test_chat_table_markdown_fenced_json` | 221 |

### `tests/unit/test_shell_workspace_evidence.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| class | `tests.unit.test_shell_workspace_evidence._FakeWorktree` | 16 |
| method | `tests.unit.test_shell_workspace_evidence._FakeWorktree.__init__` | 17 |
| method | `tests.unit.test_shell_workspace_evidence._FakeWorktree.working_dir` | 23 |
| method | `tests.unit.test_shell_workspace_evidence._FakeWorktree.run_command` | 26 |
| method | `tests.unit.test_shell_workspace_evidence._FakeWorktree.run_test_command` | 30 |
| function | `tests.unit.test_shell_workspace_evidence._session` | 34 |
| function | `tests.unit.test_shell_workspace_evidence._git_repo` | 57 |
| function | `tests.unit.test_shell_workspace_evidence.test_in_process_evidence_runs_before_any_llm` | 72 |
| function | `tests.unit.test_shell_workspace_evidence.test_in_process_evidence_failure_does_not_call_llm` | 89 |
| function | `tests.unit.test_shell_workspace_evidence.test_validation_failure_publishes_event` | 100 |
| function | `tests.unit.test_shell_workspace_evidence.test_enterprise_refusal_is_format_error_without_evidence_inject` | 110 |
| function | `tests.unit.test_shell_workspace_evidence.test_finish_claiming_no_filesystem_after_evidence_is_rejected` | 119 |
| function | `tests.unit.test_shell_workspace_evidence.test_echo_shell_access_is_not_evidence` | 136 |
| function | `tests.unit.test_shell_workspace_evidence.test_inspect_target_command_runs_after_in_process_evidence` | 141 |
| function | `tests.unit.test_shell_workspace_evidence.test_finish_before_target_inspect_is_rejected` | 157 |
| function | `tests.unit.test_shell_workspace_evidence.test_system_prompt_has_no_shell_sermon` | 165 |
| function | `tests.unit.test_shell_workspace_evidence.test_enterprise_chat_model_runs_chat_table_protocol` | 173 |
| function | `tests.unit.test_shell_workspace_evidence.test_resolved_enterprise_model_runs_chat_table_protocol_when_cfg_null` | 197 |
| function | `tests.unit.test_shell_workspace_evidence.test_chat_table_mode_can_be_disabled_via_config` | 213 |
| function | `tests.unit.test_shell_workspace_evidence.test_correct_worktree_exposes_marker` | 228 |
| function | `tests.unit.test_shell_workspace_evidence.test_empty_temporary_directory_fails_real_evidence` | 243 |
| function | `tests.unit.test_shell_workspace_evidence.test_worktree_path_is_not_parent_repository` | 256 |
| function | `tests.unit.test_shell_workspace_evidence.test_run_command_uses_worktree_cwd` | 272 |
| class | `tests.unit.test_shell_workspace_evidence._RealDirWorktree` | 298 |
| method | `tests.unit.test_shell_workspace_evidence._RealDirWorktree.__init__` | 299 |
| method | `tests.unit.test_shell_workspace_evidence._RealDirWorktree.working_dir` | 303 |
| function | `tests.unit.test_shell_workspace_evidence.test_seed_path_candidate_filter_drops_version_and_domain_tokens` | 307 |
| function | `tests.unit.test_shell_workspace_evidence.test_path_like_seed_candidate_discriminates_targets_from_prose` | 314 |
| function | `tests.unit.test_shell_workspace_evidence.test_version_token_in_seed_prose_does_not_abort` | 324 |
| function | `tests.unit.test_shell_workspace_evidence.test_missing_path_like_target_still_aborts` | 337 |

### `tests/unit/test_soak_process_fixes.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| class | `tests.unit.test_soak_process_fixes.TestNormalizeCategory` | 12 |
| method | `tests.unit.test_soak_process_fixes.TestNormalizeCategory.test_maps_to_canonical` | 50 |
| method | `tests.unit.test_soak_process_fixes.TestNormalizeCategory.test_process_categories_pass_through` | 54 |
| method | `tests.unit.test_soak_process_fixes.TestNormalizeCategory.test_unknown_becomes_other` | 57 |
| method | `tests.unit.test_soak_process_fixes.TestNormalizeCategory.test_empty_becomes_other` | 60 |
| class | `tests.unit.test_soak_process_fixes.TestFinishGate` | 68 |
| method | `tests.unit.test_soak_process_fixes.TestFinishGate.test_critical_always_blocks` | 69 |
| method | `tests.unit.test_soak_process_fixes.TestFinishGate.test_high_blocks_within_grace` | 76 |
| method | `tests.unit.test_soak_process_fixes.TestFinishGate.test_high_stops_blocking_after_grace` | 82 |
| method | `tests.unit.test_soak_process_fixes.TestFinishGate.test_nothing_pending_never_blocks` | 88 |
| class | `tests.unit.test_soak_process_fixes.TestFinalizeTask` | 95 |
| method | `tests.unit.test_soak_process_fixes.TestFinalizeTask.test_completed_when_files_modified` | 96 |
| method | `tests.unit.test_soak_process_fixes.TestFinalizeTask.test_stalled_when_no_files_modified` | 111 |
| method | `tests.unit.test_soak_process_fixes.TestFinalizeTask.test_keyboard_interrupt_is_failed` | 125 |
| method | `tests.unit.test_soak_process_fixes.TestFinalizeTask.test_evidence_ok_no_change_is_no_change_required` | 138 |
| method | `tests.unit.test_soak_process_fixes.TestFinalizeTask.test_zero_command_terminal_status_is_failed` | 152 |
| method | `tests.unit.test_soak_process_fixes.TestFinalizeTask.test_does_not_downgrade_completed` | 169 |

### `tests/unit/test_symbol_index.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| function | `tests.unit.test_symbol_index.test_parse_python_symbols_basic` | 13 |
| function | `tests.unit.test_symbol_index.test_upsert_and_fetch` | 25 |
| function | `tests.unit.test_symbol_index.test_upsert_replaces_stale` | 41 |
| function | `tests.unit.test_symbol_index.test_json_context_block` | 54 |

### `tests/unit/test_symbol_index_bounds.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| function | `tests.unit.test_symbol_index_bounds.test_rebuild_only_indexes_configured_project` | 6 |
| function | `tests.unit.test_symbol_index_bounds.test_upsert_symbols_for_single_file` | 35 |

### `tests/unit/test_task_runner.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| class | `tests.unit.test_task_runner.TestTaskRunnerSignature` | 12 |
| method | `tests.unit.test_task_runner.TestTaskRunnerSignature.test_run_task_cycle_function_exists` | 13 |
| method | `tests.unit.test_task_runner.TestTaskRunnerSignature.test_run_task_cycle_accepts_time_box` | 18 |
| class | `tests.unit.test_task_runner.TestTaskRunnerWithMocks` | 27 |
| method | `tests.unit.test_task_runner.TestTaskRunnerWithMocks.test_call_agent_patched_during_cycle_components` | 28 |
| method | `tests.unit.test_task_runner.TestTaskRunnerWithMocks.test_developer_edit_payload_roundtrip` | 51 |
| function | `tests.unit.test_task_runner._extract_target_files_from_text` | 89 |
| function | `tests.unit.test_task_runner.test_file_extraction_regex_no_unterminated_charset_error` | 115 |
| function | `tests.unit.test_task_runner.test_path_cleaning_and_none_filtering` | 125 |
| function | `tests.unit.test_task_runner.test_requested_files_single_file_cap` | 141 |
| class | `tests.unit.test_task_runner.TestDeferredPoolStart` | 151 |
| method | `tests.unit.test_task_runner.TestDeferredPoolStart._make_pool` | 156 |
| method | `tests.unit.test_task_runner.TestDeferredPoolStart.test_no_start_before_materialize_and_turn_threshold` | 166 |
| method | `tests.unit.test_task_runner.TestDeferredPoolStart.test_start_after_first_materialize` | 173 |
| method | `tests.unit.test_task_runner.TestDeferredPoolStart.test_start_after_turn_threshold_without_materialize` | 180 |
| method | `tests.unit.test_task_runner.TestDeferredPoolStart.test_start_is_idempotent_once_running` | 187 |
| method | `tests.unit.test_task_runner.TestDeferredPoolStart.test_pool_without_start_attribute_is_noop` | 207 |
| class | `tests.unit.test_task_runner.TestNoProgressGuard` | 219 |
| method | `tests.unit.test_task_runner.TestNoProgressGuard.test_not_stalled_below_threshold` | 224 |
| method | `tests.unit.test_task_runner.TestNoProgressGuard.test_default_threshold_latches_after_constant` | 230 |
| method | `tests.unit.test_task_runner.TestNoProgressGuard.test_posts_single_stall_summary_per_episode` | 239 |
| method | `tests.unit.test_task_runner.TestNoProgressGuard.test_change_resets_streak_and_latch` | 252 |
| method | `tests.unit.test_task_runner.TestNoProgressGuard.test_record_developer_progress_helper` | 262 |
| method | `tests.unit.test_task_runner.TestNoProgressGuard.test_failed_session_is_neutral_never_latches` | 282 |
| method | `tests.unit.test_task_runner.TestNoProgressGuard.test_genuine_finished_zero_change_still_latches` | 307 |
| method | `tests.unit.test_task_runner.TestNoProgressGuard.test_success_with_change_clears_streak_even_after_failures` | 332 |
| method | `tests.unit.test_task_runner.TestNoProgressGuard.test_latch_rearms_after_rearm_after_cycles` | 343 |
| class | `tests.unit.test_task_runner.TestZeroCommandSeedGuard` | 364 |
| method | `tests.unit.test_task_runner.TestZeroCommandSeedGuard.test_finish_without_bash_latches_immediately` | 367 |
| method | `tests.unit.test_task_runner.TestZeroCommandSeedGuard.test_workspace_validation_failed_latches_even_if_evidence_ran` | 382 |
| method | `tests.unit.test_task_runner.TestZeroCommandSeedGuard.test_llm_unavailable_stays_dispatchable` | 397 |
| method | `tests.unit.test_task_runner.TestZeroCommandSeedGuard.test_edit_payload_errors_are_not_shell_zero_command` | 413 |
| method | `tests.unit.test_task_runner.TestZeroCommandSeedGuard.test_evidence_ok_plus_llm_unavailable_does_not_latch` | 419 |
| method | `tests.unit.test_task_runner.TestZeroCommandSeedGuard.test_finished_with_evidence_and_no_mutation_does_not_zero_command_latch` | 435 |
| method | `tests.unit.test_task_runner.TestZeroCommandSeedGuard.test_latch_does_not_rearm` | 449 |
| class | `tests.unit.test_task_runner.TestDispatchDeveloperFallback` | 471 |
| method | `tests.unit.test_task_runner.TestDispatchDeveloperFallback.test_shell_error_skips_fallback_when_no_target` | 477 |
| method | `tests.unit.test_task_runner.TestDispatchDeveloperFallback.test_shell_error_falls_back_when_requested_files_given` | 519 |
| method | `tests.unit.test_task_runner.TestDispatchDeveloperFallback.test_shell_error_falls_back_from_decision_files_needed` | 567 |
| method | `tests.unit.test_task_runner.TestDispatchDeveloperFallback.test_shell_success_does_not_fall_back` | 604 |

### `tests/unit/test_truncation_detector.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| class | `tests.unit.test_truncation_detector.TestTruncationDetector` | 10 |
| method | `tests.unit.test_truncation_detector.TestTruncationDetector.test_detect_complete_json` | 13 |
| method | `tests.unit.test_truncation_detector.TestTruncationDetector.test_detect_truncated_json` | 20 |
| method | `tests.unit.test_truncation_detector.TestTruncationDetector.test_detect_incomplete_code_block` | 28 |
| method | `tests.unit.test_truncation_detector.TestTruncationDetector.test_detect_complete_text` | 40 |
| method | `tests.unit.test_truncation_detector.TestTruncationDetector.test_detect_mid_sentence_truncation` | 46 |
| class | `tests.unit.test_truncation_detector.TestTruncationDetectorFactory` | 53 |
| method | `tests.unit.test_truncation_detector.TestTruncationDetectorFactory.test_get_truncation_detector_returns_instance` | 56 |
| method | `tests.unit.test_truncation_detector.TestTruncationDetectorFactory.test_detect_and_resume_signature` | 60 |

### `tests/unit/test_truncation_resume.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| function | `tests.unit.test_truncation_resume.test_detect_and_resume_merges_when_truncated` | 8 |
| function | `tests.unit.test_truncation_resume.test_detect_and_resume_no_op_on_complete_json` | 32 |

### `tests/unit/test_unattended_continue.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| function | `tests.unit.test_unattended_continue.test_unattended_config_repr_hides_seed_queue` | 11 |
| function | `tests.unit.test_unattended_continue.test_unattended_config_eq_ignores_seed_queue` | 17 |
| function | `tests.unit.test_unattended_continue.test_stops_when_duration_exceeded` | 24 |
| function | `tests.unit.test_unattended_continue.test_continues_within_duration` | 30 |
| function | `tests.unit.test_unattended_continue.test_stops_when_seed_queue_empty_and_no_autogen` | 36 |
| function | `tests.unit.test_unattended_continue.test_stops_when_backlog_empty_flag` | 42 |
| function | `tests.unit.test_unattended_continue.test_continues_when_backlog_has_items` | 49 |
| function | `tests.unit.test_unattended_continue.test_generate_next_task_pops_seed_queue` | 67 |
| function | `tests.unit.test_unattended_continue.test_generate_next_task_prioritizes_critical_feedback` | 75 |

### `tests/unit/test_worker_lifecycle.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| function | `tests.unit.test_worker_lifecycle.pool_env` | 37 |
| class | `tests.unit.test_worker_lifecycle.TestBoundedSet` | 53 |
| method | `tests.unit.test_worker_lifecycle.TestBoundedSet.test_evicts_oldest` | 54 |
| method | `tests.unit.test_worker_lifecycle.TestBoundedSet.test_clear` | 65 |
| class | `tests.unit.test_worker_lifecycle.TestPoolLifecycle` | 75 |
| method | `tests.unit.test_worker_lifecycle.TestPoolLifecycle.test_idempotent_stop` | 77 |
| method | `tests.unit.test_worker_lifecycle.TestPoolLifecycle.test_start_stop_clears_running_flag` | 88 |
| method | `tests.unit.test_worker_lifecycle.TestPoolLifecycle.test_start_when_disabled_is_noop` | 103 |
| method | `tests.unit.test_worker_lifecycle.TestPoolLifecycle.test_start_when_already_running_is_noop` | 113 |
| method | `tests.unit.test_worker_lifecycle.TestPoolLifecycle.test_force_review_when_not_running` | 129 |
| class | `tests.unit.test_worker_lifecycle.TestActiveAgentControl` | 140 |
| method | `tests.unit.test_worker_lifecycle.TestActiveAgentControl.test_pause_all_feedback_agents` | 141 |
| method | `tests.unit.test_worker_lifecycle.TestActiveAgentControl.test_reenable_subset` | 157 |
| method | `tests.unit.test_worker_lifecycle.TestActiveAgentControl.test_feeder_interval_under_lock` | 173 |
| class | `tests.unit.test_worker_lifecycle.TestHeuristicOptimizerDecisions` | 193 |
| method | `tests.unit.test_worker_lifecycle.TestHeuristicOptimizerDecisions._state` | 194 |
| method | `tests.unit.test_worker_lifecycle.TestHeuristicOptimizerDecisions.test_optimize_returns_decision_or_none` | 210 |
| method | `tests.unit.test_worker_lifecycle.TestHeuristicOptimizerDecisions.test_critical_budget_throttles` | 217 |
| method | `tests.unit.test_worker_lifecycle.TestHeuristicOptimizerDecisions.test_update_agent_performance` | 231 |
| class | `tests.unit.test_worker_lifecycle.TestResourceControllerLifecycle` | 240 |
| method | `tests.unit.test_worker_lifecycle.TestResourceControllerLifecycle.test_double_stop_safe` | 241 |
| method | `tests.unit.test_worker_lifecycle.TestResourceControllerLifecycle.test_start_stop` | 250 |
| class | `tests.unit.test_worker_lifecycle.TestPoolBehavioralP2` | 263 |
| method | `tests.unit.test_worker_lifecycle.TestPoolBehavioralP2.test_start_queue_stop_with_mock_agent` | 266 |
| method | `tests.unit.test_worker_lifecycle.TestPoolBehavioralP2.test_pause_active_agents_clears_filter` | 284 |
| class | `tests.unit.test_worker_lifecycle.TestRCOptimizerP2` | 301 |
| method | `tests.unit.test_worker_lifecycle.TestRCOptimizerP2.test_optimizer_levels_do_not_raise` | 304 |

### `tests/unit/test_worker_utils.py`

**Tests / test classes**

| Kind | Qualname | Line |
|------|----------|------|
| function | `tests.unit.test_worker_utils.test_interruptible_sleep_exits_early_when_stopped` | 20 |
| function | `tests.unit.test_worker_utils.test_interruptible_sleep_zero_is_noop` | 39 |
| function | `tests.unit.test_worker_utils.test_foreground_gate_counter_semantics` | 51 |
| function | `tests.unit.test_worker_utils.test_foreground_session_guard_cleans_up_on_return` | 67 |
| function | `tests.unit.test_worker_utils.test_foreground_session_guard_cleans_up_on_exception` | 78 |
| function | `tests.unit.test_worker_utils.test_hold_returns_immediately_when_no_foreground_session` | 92 |
| function | `tests.unit.test_worker_utils.test_hold_waits_while_foreground_active` | 104 |
| function | `tests.unit.test_worker_utils.test_hold_breaks_when_stopped_during_hold` | 117 |
| function | `tests.unit.test_worker_utils.test_support_frozen_flag_roundtrip` | 139 |
| function | `tests.unit.test_worker_utils.test_hold_waits_while_transport_frozen` | 150 |
| function | `tests.unit.test_worker_utils.test_hold_returns_immediately_when_no_foreground_and_not_frozen` | 165 |
| function | `tests.unit.test_worker_utils.test_coalescer_first_high_then_medium_within_window` | 185 |
| function | `tests.unit.test_worker_utils.test_coalescer_agents_are_independent` | 192 |
| function | `tests.unit.test_worker_utils.test_coalescer_new_episode_after_window_elapses` | 199 |
| function | `tests.unit.test_worker_utils.test_coalescer_clear_for_resets_episode` | 207 |

