Generated: 2026-09-07T12:34:00Z

# PrizmForge Code Indexes

Root: `C:\git\home\user\jeremy.gerdes\github\PrizmForge-Soak\Soak5-target\PrizmForge`

Lightweight context files (no full source dump). Regenerate with `python utils/consolidate.py`.

## Contents

- [Production](#index-production-code)
- [Tests](#index-test-suite)
- [Docs](#index-markdown-documentation)

---

## Index: Production code

Modules, classes, and top-level functions/methods under agents/, cli/, core/, file_editing/, workflow/, utils/, and root entrypoints.

### `agent_schemas/archivist.json`

_No Python symbols (or non-Python file)._

### `agent_schemas/deployment_validator.json`

_No Python symbols (or non-Python file)._

### `agent_schemas/developer.json`

_No Python symbols (or non-Python file)._

### `agent_schemas/jr_researcher.json`

_No Python symbols (or non-Python file)._

### `agent_schemas/jr_reviewer.json`

_No Python symbols (or non-Python file)._

### `agent_schemas/orchestrator.json`

_No Python symbols (or non-Python file)._

### `agent_schemas/prioritizer.json`

_No Python symbols (or non-Python file)._

### `agent_schemas/project_reporter.json`

_No Python symbols (or non-Python file)._

### `agent_schemas/resource_controller.json`

_No Python symbols (or non-Python file)._

### `agent_schemas/reviewer.json`

_No Python symbols (or non-Python file)._

### `agent_schemas/security_reviewer.json`

_No Python symbols (or non-Python file)._

### `agent_schemas/tech_writer.json`

_No Python symbols (or non-Python file)._

### `agents/__init__.py`

| Kind | Qualname | Line |
|------|----------|------|
| class | `agents.__init__.ResourceController` | 10 |
| method | `agents.__init__.ResourceController.__init__` | 13 |

### `agents/archivist_worker.py`

| Kind | Qualname | Line |
|------|----------|------|
| class | `agents.archivist_worker.ArchivistWorker` | 18 |
| method | `agents.archivist_worker.ArchivistWorker.__init__` | 48 |
| method | `agents.archivist_worker.ArchivistWorker.start` | 57 |
| method | `agents.archivist_worker.ArchivistWorker.stop` | 68 |
| method | `agents.archivist_worker.ArchivistWorker._worker_loop` | 76 |
| method | `agents.archivist_worker.ArchivistWorker._archive_old_messages` | 102 |
| method | `agents.archivist_worker.ArchivistWorker._archive_old_conversations` | 164 |
| method | `agents.archivist_worker.ArchivistWorker._check_for_restore_requests` | 235 |
| method | `agents.archivist_worker.ArchivistWorker._needs_context_restore` | 259 |
| method | `agents.archivist_worker.ArchivistWorker._restore_relevant_context` | 279 |
| method | `agents.archivist_worker.ArchivistWorker._build_message_archive_prompt` | 313 |
| method | `agents.archivist_worker.ArchivistWorker._build_conversation_archive_prompt` | 324 |
| method | `agents.archivist_worker.ArchivistWorker._parse_archive_response` | 336 |
| method | `agents.archivist_worker.ArchivistWorker._save_message_archive` | 361 |
| method | `agents.archivist_worker.ArchivistWorker._save_conversation_archive` | 401 |
| method | `agents.archivist_worker.ArchivistWorker._prune_conversation_batch` | 411 |
| function | `agents.archivist_worker.get_archivist_worker` | 424 |

### `agents/base.py`

| Kind | Qualname | Line |
|------|----------|------|
| function | `agents.base.get_rate_limiter` | 66 |
| function | `agents.base._endpoint_budget_key` | 74 |
| function | `agents.base.get_token_budget` | 82 |
| function | `agents.base.any_token_budget_remaining` | 101 |
| function | `agents.base.estimate_tokens` | 120 |
| function | `agents.base._resolve_fallback` | 125 |
| function | `agents.base._bounded_no_alternate_sleep` | 142 |
| function | `agents.base._fallback_to_alternate` | 153 |
| function | `agents.base._classify_empty_or_policy_body` | 218 |
| function | `agents.base._dump_unknown_llm_body_once` | 258 |
| function | `agents.base.call_endpoint` | 271 |
| function | `agents.base.call_agent` | 884 |
| function | `agents.base._get_agent_output_format` | 1164 |
| function | `agents.base._merge_responses` | 1201 |
| function | `agents.base._merge_json_responses` | 1224 |
| function | `agents.base._extract_json_content` | 1272 |
| function | `agents.base._merge_diff_responses` | 1316 |
| function | `agents.base._extract_diff_content` | 1335 |
| function | `agents.base._merge_text_responses` | 1354 |

### `agents/orchestrator.py`

| Kind | Qualname | Line |
|------|----------|------|
| function | `agents.orchestrator.call_orchestrator` | 12 |

### `agents/parallel_workers.py`

| Kind | Qualname | Line |
|------|----------|------|
| class | `agents.parallel_workers.FileChangeEvent` | 29 |
| class | `agents.parallel_workers.BoundedSet` | 43 |
| method | `agents.parallel_workers.BoundedSet.__init__` | 46 |
| method | `agents.parallel_workers.BoundedSet.add` | 50 |
| method | `agents.parallel_workers.BoundedSet.__contains__` | 58 |
| method | `agents.parallel_workers.BoundedSet.clear` | 61 |
| class | `agents.parallel_workers.BackgroundAgentPool` | 65 |
| method | `agents.parallel_workers.BackgroundAgentPool.__init__` | 66 |
| method | `agents.parallel_workers.BackgroundAgentPool.start` | 100 |
| method | `agents.parallel_workers.BackgroundAgentPool._join_workers_unlocked` | 177 |
| method | `agents.parallel_workers.BackgroundAgentPool.stop` | 193 |
| method | `agents.parallel_workers.BackgroundAgentPool._start_support_workers` | 215 |
| method | `agents.parallel_workers.BackgroundAgentPool._queue_all_files_for_initial_review` | 224 |
| method | `agents.parallel_workers.BackgroundAgentPool._resolve_seed_target_path` | 292 |
| method | `agents.parallel_workers.BackgroundAgentPool._queue_modified_files` | 326 |
| method | `agents.parallel_workers.BackgroundAgentPool._file_feeder_loop` | 378 |
| method | `agents.parallel_workers.BackgroundAgentPool._adjust_feeder_interval` | 396 |
| method | `agents.parallel_workers.BackgroundAgentPool._feed_random_files` | 411 |
| method | `agents.parallel_workers.BackgroundAgentPool._create_file_event` | 477 |
| method | `agents.parallel_workers.BackgroundAgentPool.queue_file_change` | 498 |
| method | `agents.parallel_workers.BackgroundAgentPool._worker_loop` | 556 |
| method | `agents.parallel_workers.BackgroundAgentPool._process_file` | 587 |
| method | `agents.parallel_workers.BackgroundAgentPool._parse_and_save_feedback` | 697 |
| method | `agents.parallel_workers.BackgroundAgentPool._update_review_tracking` | 805 |
| method | `agents.parallel_workers.BackgroundAgentPool.set_feeder_interval` | 831 |
| method | `agents.parallel_workers.BackgroundAgentPool.set_active_agents` | 843 |
| method | `agents.parallel_workers.BackgroundAgentPool.force_review_cycle` | 885 |
| function | `agents.parallel_workers.get_agent_pool` | 964 |

### `agents/prioritizer_worker.py`

| Kind | Qualname | Line |
|------|----------|------|
| function | `agents.prioritizer_worker._phase_model_override` | 23 |
| class | `agents.prioritizer_worker.FeedbackItem` | 42 |
| class | `agents.prioritizer_worker.PrioritizerWorker` | 59 |
| method | `agents.prioritizer_worker.PrioritizerWorker.__init__` | 69 |
| method | `agents.prioritizer_worker.PrioritizerWorker.start` | 101 |
| method | `agents.prioritizer_worker.PrioritizerWorker.stop` | 112 |
| method | `agents.prioritizer_worker.PrioritizerWorker._worker_loop` | 119 |
| method | `agents.prioritizer_worker.PrioritizerWorker._evaluate_item_quality` | 146 |
| method | `agents.prioritizer_worker.PrioritizerWorker._low_quality_patterns` | 176 |
| method | `agents.prioritizer_worker.PrioritizerWorker._filter_low_quality_feedback` | 189 |
| method | `agents.prioritizer_worker.PrioritizerWorker._should_run_cycle` | 236 |
| method | `agents.prioritizer_worker.PrioritizerWorker._run_full_prioritization_cycle` | 249 |
| method | `agents.prioritizer_worker.PrioritizerWorker._get_all_feedback` | 301 |
| method | `agents.prioritizer_worker.PrioritizerWorker._categorize_feedback` | 404 |
| method | `agents.prioritizer_worker.PrioritizerWorker._rr_next_model` | 472 |
| method | `agents.prioritizer_worker.PrioritizerWorker._categorize_batch` | 509 |
| method | `agents.prioritizer_worker.PrioritizerWorker._update_categories` | 579 |
| method | `agents.prioritizer_worker.PrioritizerWorker._score_within_categories` | 602 |
| method | `agents.prioritizer_worker.PrioritizerWorker._score_category` | 620 |
| method | `agents.prioritizer_worker.PrioritizerWorker._top_by_score` | 665 |
| method | `agents.prioritizer_worker.PrioritizerWorker._cross_category_ranking` | 669 |
| method | `agents.prioritizer_worker.PrioritizerWorker._post_results` | 742 |
| method | `agents.prioritizer_worker.PrioritizerWorker._mark_items_processed` | 791 |
| function | `agents.prioritizer_worker.get_prioritizer_worker` | 810 |

### `agents/reporter_worker.py`

| Kind | Qualname | Line |
|------|----------|------|
| class | `agents.reporter_worker.ProjectReporterWorker` | 14 |
| method | `agents.reporter_worker.ProjectReporterWorker.__init__` | 17 |
| method | `agents.reporter_worker.ProjectReporterWorker.start` | 29 |
| method | `agents.reporter_worker.ProjectReporterWorker.stop` | 40 |
| method | `agents.reporter_worker.ProjectReporterWorker._load_last_state` | 47 |
| method | `agents.reporter_worker.ProjectReporterWorker._save_state` | 64 |
| method | `agents.reporter_worker.ProjectReporterWorker._worker_loop` | 81 |
| method | `agents.reporter_worker.ProjectReporterWorker._should_generate_report` | 99 |
| method | `agents.reporter_worker.ProjectReporterWorker._get_total_indexed_files` | 148 |
| method | `agents.reporter_worker.ProjectReporterWorker._generate_report` | 158 |
| method | `agents.reporter_worker.ProjectReporterWorker._gather_report_data` | 185 |
| method | `agents.reporter_worker.ProjectReporterWorker._build_prompt` | 295 |
| method | `agents.reporter_worker.ProjectReporterWorker._save_report` | 339 |
| method | `agents.reporter_worker.ProjectReporterWorker._cleanup_old_reports` | 359 |
| method | `agents.reporter_worker.ProjectReporterWorker._record_report` | 368 |
| method | `agents.reporter_worker.ProjectReporterWorker._notify_orchestrator` | 398 |
| function | `agents.reporter_worker.get_reporter_worker` | 417 |

### `agents/resource_controller_worker.py`

| Kind | Qualname | Line |
|------|----------|------|
| class | `agents.resource_controller_worker.AgentProfile` | 36 |
| method | `agents.resource_controller_worker.AgentProfile.to_dict` | 47 |
| method | `agents.resource_controller_worker.AgentProfile.from_dict` | 51 |
| class | `agents.resource_controller_worker.ResourceState` | 56 |
| method | `agents.resource_controller_worker.ResourceState.__str__` | 70 |
| class | `agents.resource_controller_worker.ThrottleDecision` | 84 |
| method | `agents.resource_controller_worker.ThrottleDecision.to_dict` | 94 |
| class | `agents.resource_controller_worker.HeuristicOptimizer` | 98 |
| method | `agents.resource_controller_worker.HeuristicOptimizer.__init__` | 110 |
| method | `agents.resource_controller_worker.HeuristicOptimizer._model_downgrades_for` | 128 |
| method | `agents.resource_controller_worker.HeuristicOptimizer._get_priority_categories` | 148 |
| method | `agents.resource_controller_worker.HeuristicOptimizer._load_agent_profiles` | 153 |
| method | `agents.resource_controller_worker.HeuristicOptimizer._get_default_profiles` | 183 |
| method | `agents.resource_controller_worker.HeuristicOptimizer._save_agent_profiles` | 224 |
| method | `agents.resource_controller_worker.HeuristicOptimizer.optimize` | 244 |
| method | `agents.resource_controller_worker.HeuristicOptimizer._check_feedback_backlog` | 307 |
| method | `agents.resource_controller_worker.HeuristicOptimizer._throttle_critical` | 389 |
| method | `agents.resource_controller_worker.HeuristicOptimizer._throttle_aggressive` | 408 |
| method | `agents.resource_controller_worker.HeuristicOptimizer._throttle_moderate` | 435 |
| method | `agents.resource_controller_worker.HeuristicOptimizer._throttle_normal` | 466 |
| method | `agents.resource_controller_worker.HeuristicOptimizer._rank_agents_by_value` | 492 |
| method | `agents.resource_controller_worker.HeuristicOptimizer._get_priority_boost` | 527 |
| method | `agents.resource_controller_worker.HeuristicOptimizer.update_agent_performance` | 554 |
| class | `agents.resource_controller_worker.ResourceControllerWorker` | 602 |
| method | `agents.resource_controller_worker.ResourceControllerWorker.__init__` | 616 |
| method | `agents.resource_controller_worker.ResourceControllerWorker.start` | 628 |
| method | `agents.resource_controller_worker.ResourceControllerWorker.stop` | 640 |
| method | `agents.resource_controller_worker.ResourceControllerWorker._worker_loop` | 651 |
| method | `agents.resource_controller_worker.ResourceControllerWorker._gather_resource_state` | 688 |
| method | `agents.resource_controller_worker.ResourceControllerWorker._compute_burn_rate` | 727 |
| method | `agents.resource_controller_worker.ResourceControllerWorker._count_recent_api_calls` | 754 |
| method | `agents.resource_controller_worker.ResourceControllerWorker._count_recent_rate_limits` | 778 |
| method | `agents.resource_controller_worker.ResourceControllerWorker._should_apply_decision` | 806 |
| method | `agents.resource_controller_worker.ResourceControllerWorker._apply_decision` | 824 |
| method | `agents.resource_controller_worker.ResourceControllerWorker._store_model_overrides` | 878 |
| method | `agents.resource_controller_worker.ResourceControllerWorker._notify_orchestrator` | 900 |
| method | `agents.resource_controller_worker.ResourceControllerWorker._get_recommendation` | 944 |
| method | `agents.resource_controller_worker.ResourceControllerWorker._log_decision` | 955 |
| method | `agents.resource_controller_worker.ResourceControllerWorker.get_current_decision` | 983 |
| method | `agents.resource_controller_worker.ResourceControllerWorker.get_decision_history` | 987 |
| method | `agents.resource_controller_worker.ResourceControllerWorker.update_agent_performance` | 991 |
| method | `agents.resource_controller_worker.ResourceControllerWorker.get_model_override` | 1006 |
| method | `agents.resource_controller_worker.ResourceControllerWorker.get_agent_statistics` | 1029 |
| method | `agents.resource_controller_worker.ResourceControllerWorker._is_throttling_disabled` | 1057 |
| method | `agents.resource_controller_worker.ResourceControllerWorker.temporarily_disable_throttling` | 1063 |
| function | `agents.resource_controller_worker.get_resource_controller` | 1078 |

### `agents/response_cleaner.py`

| Kind | Qualname | Line |
|------|----------|------|
| function | `agents.response_cleaner.extract_json_aggressively` | 7 |
| function | `agents.response_cleaner.clean_llm_response` | 79 |

### `agents/worker_utils.py`

| Kind | Qualname | Line |
|------|----------|------|
| function | `agents.worker_utils.interruptible_sleep` | 11 |
| function | `agents.worker_utils.foreground_session_active` | 43 |
| function | `agents.worker_utils.begin_foreground_session` | 49 |
| function | `agents.worker_utils.end_foreground_session` | 55 |
| function | `agents.worker_utils.foreground_session_guard` | 62 |
| function | `agents.worker_utils.hold_while_foreground_session_active` | 75 |
| function | `agents.worker_utils.support_frozen` | 100 |
| function | `agents.worker_utils.set_support_frozen` | 106 |
| class | `agents.worker_utils.TransportErrorCoalescer` | 121 |
| method | `agents.worker_utils.TransportErrorCoalescer.__init__` | 129 |
| method | `agents.worker_utils.TransportErrorCoalescer.classify` | 134 |
| method | `agents.worker_utils.TransportErrorCoalescer.clear_for` | 144 |
| function | `agents.worker_utils.classify_transport_severity` | 152 |

### `audit/__init__.py`

| Kind | Qualname | Line |
|------|----------|------|

### `cli/__init__.py`

| Kind | Qualname | Line |
|------|----------|------|

### `cli/commands.py`

| Kind | Qualname | Line |
|------|----------|------|
| function | `cli.commands.cmd_init` | 23 |
| function | `cli.commands.cmd_files` | 155 |
| function | `cli.commands.cmd_status` | 174 |
| function | `cli.commands.cmd_history` | 190 |
| function | `cli.commands.cmd_feedback` | 220 |
| function | `cli.commands.cmd_reset_endpoint` | 238 |
| function | `cli.commands.cmd_fallback_stats` | 258 |
| function | `cli.commands.cmd_show_prompt` | 288 |
| function | `cli.commands.cmd_export_db` | 342 |
| function | `cli.commands._quote_identifier` | 423 |
| function | `cli.commands.table_has_task_id` | 428 |
| function | `cli.commands.cmd_export_task` | 438 |
| function | `cli.commands.cmd_list_exports` | 450 |
| function | `cli.commands.cmd_export_specific_tables` | 482 |
| function | `cli.commands.cmd_archives` | 556 |
| function | `cli.commands.cmd_review_status` | 632 |
| function | `cli.commands.cmd_endpoints` | 701 |
| function | `cli.commands.cmd_endpoint_health` | 746 |
| function | `cli.commands.cmd_reports` | 801 |
| function | `cli.commands.cmd_show_report` | 833 |
| function | `cli.commands.cmd_resource_status` | 865 |
| function | `cli.commands.cmd_json_parse_stats` | 916 |
| function | `cli.commands.cmd_task_progress` | 955 |
| function | `cli.commands.cmd_help` | 1013 |

### `core/__init__.py`

| Kind | Qualname | Line |
|------|----------|------|

### `core/agent_schemas.py`

| Kind | Qualname | Line |
|------|----------|------|
| class | `core.agent_schemas.AgentResponseSchema` | 18 |
| method | `core.agent_schemas.AgentResponseSchema.validate` | 30 |
| method | `core.agent_schemas.AgentResponseSchema.build_prompt_schema` | 56 |
| function | `core.agent_schemas._create_fallback_schema` | 254 |
| function | `core.agent_schemas.get_distinct_values` | 277 |
| function | `core.agent_schemas.get_schema_example` | 312 |
| function | `core.agent_schemas.get_priority_values` | 340 |
| function | `core.agent_schemas.get_category_values` | 351 |
| function | `core.agent_schemas.get_operation_types` | 371 |
| function | `core.agent_schemas.get_schema` | 384 |
| function | `core.agent_schemas.get_prompt_schema_text` | 407 |
| function | `core.agent_schemas.validate_agent_response` | 423 |
| function | `core.agent_schemas.list_agents` | 431 |
| function | `core.agent_schemas.get_agents_by_table` | 436 |
| function | `core.agent_schemas.is_using_fallback` | 441 |
| function | `core.agent_schemas.get_schema_statistics` | 447 |
| function | `core.agent_schemas.add_value_if_missing` | 462 |

### `core/archival.py`

| Kind | Qualname | Line |
|------|----------|------|
| function | `core.archival.archive_raw_response` | 8 |

### `core/cli_modes.py`

| Kind | Qualname | Line |
|------|----------|------|
| class | `core.cli_modes.CLIMode` | 8 |
| class | `core.cli_modes.UnattendedConfig` | 16 |
| method | `core.cli_modes.UnattendedConfig.from_config` | 35 |
| method | `core.cli_modes.UnattendedConfig.get_end_time` | 64 |
| class | `core.cli_modes.CLIState` | 72 |
| method | `core.cli_modes.CLIState.should_checkpoint` | 83 |
| method | `core.cli_modes.CLIState.update_checkpoint` | 90 |
| method | `core.cli_modes.CLIState.elapsed_hours` | 94 |
| method | `core.cli_modes.CLIState.elapsed_minutes` | 98 |
| function | `core.cli_modes.get_cli_mode_from_config` | 103 |

### `core/config.py`

| Kind | Qualname | Line |
|------|----------|------|
| function | `core.config.get_package_root` | 14 |
| function | `core.config.normalize_path` | 19 |
| function | `core.config.find_config_file` | 43 |
| function | `core.config._load_api_keys` | 71 |
| function | `core.config.load_config` | 88 |
| function | `core.config.get_repo_root` | 132 |
| function | `core.config.ensure_project_directory` | 143 |
| function | `core.config.validate_config` | 161 |
| function | `core.config.load_agent_prompts` | 309 |
| function | `core.config.get_config` | 328 |
| function | `core.config.get_agent_prompts` | 338 |
| function | `core.config.get_config_dir` | 348 |
| function | `core.config.reload_config` | 354 |

### `core/content_safety.py`

| Kind | Qualname | Line |
|------|----------|------|
| function | `core.content_safety._normalize_ext` | 67 |
| function | `core.content_safety.get_content_safety_settings` | 77 |
| function | `core.content_safety._as_bytes_sample` | 112 |
| function | `core.content_safety.looks_like_binary` | 124 |
| function | `core.content_safety.path_has_blocked_extension` | 150 |
| function | `core.content_safety.validate_source_content` | 167 |

### `core/context_manager.py`

| Kind | Qualname | Line |
|------|----------|------|
| function | `core.context_manager._usable_context` | 23 |
| class | `core.context_manager.FileContext` | 29 |
| class | `core.context_manager.ContextManager` | 38 |
| method | `core.context_manager.ContextManager.__init__` | 48 |
| method | `core.context_manager.ContextManager.get_model_context_limit` | 70 |
| method | `core.context_manager.ContextManager.build_orchestrator_context` | 101 |
| method | `core.context_manager.ContextManager._get_prioritized_files_fast` | 230 |
| method | `core.context_manager.ContextManager._calculate_priority` | 306 |
| method | `core.context_manager.ContextManager._format_file_summary` | 341 |
| method | `core.context_manager.ContextManager._get_prioritized_suggestions` | 360 |
| function | `core.context_manager.get_context_manager` | 457 |

### `core/db.py`

| Kind | Qualname | Line |
|------|----------|------|
| function | `core.db.get_db_path` | 7 |
| function | `core.db._split_sql_statements` | 34 |
| function | `core.db._statement_is_meaningful` | 123 |
| function | `core.db._apply_schema` | 132 |
| function | `core.db._table_columns` | 148 |
| function | `core.db._ensure_column` | 158 |
| function | `core.db._migrate_schema` | 171 |
| function | `core.db.init_db` | 235 |

### `core/db_connection.py`

| Kind | Qualname | Line |
|------|----------|------|
| class | `core.db_connection.DatabaseRetryError` | 10 |
| function | `core.db_connection._is_lock_error` | 27 |
| function | `core.db_connection._backoff_sleep` | 32 |
| function | `core.db_connection.get_db_connection` | 53 |
| function | `core.db_connection.get_init_db_connection` | 130 |
| function | `core.db_connection._commit_with_retry` | 180 |
| function | `core.db_connection._checkpoint_with_retry` | 208 |
| function | `core.db_connection.execute_with_retry` | 227 |

### `core/db_helpers.py`

| Kind | Qualname | Line |
|------|----------|------|
| function | `core.db_helpers.is_praise_only_feedback` | 52 |
| function | `core.db_helpers.normalize_category` | 141 |
| function | `core.db_helpers.get_db_path` | 163 |
| function | `core.db_helpers.post_message` | 169 |
| function | `core.db_helpers.get_unread_messages` | 194 |
| function | `core.db_helpers.mark_messages_read` | 248 |
| function | `core.db_helpers.save_conversation` | 257 |
| function | `core.db_helpers.create_task` | 285 |
| function | `core.db_helpers.mark_task_status` | 310 |
| function | `core.db_helpers.complete_task` | 324 |
| function | `core.db_helpers.normalize_feedback_message` | 329 |
| function | `core.db_helpers._dedupe_settings` | 340 |
| function | `core.db_helpers.save_agent_feedback` | 350 |
| function | `core.db_helpers.get_unaddressed_feedback` | 410 |
| function | `core.db_helpers.mark_feedback_addressed` | 450 |
| function | `core.db_helpers.backlog_metrics` | 462 |
| function | `core.db_helpers.age_feedback_backlog` | 498 |

### `core/edit_response_validator.py`

| Kind | Qualname | Line |
|------|----------|------|
| class | `core.edit_response_validator.EditFailureReason` | 19 |
| class | `core.edit_response_validator.EditValidationResult` | 32 |
| method | `core.edit_response_validator.EditValidationResult.should_fallback` | 42 |
| function | `core.edit_response_validator._extract_json_object` | 46 |
| function | `core.edit_response_validator.validate_developer_edit_response` | 80 |

### `core/endpoint_manager.py`

| Kind | Qualname | Line |
|------|----------|------|
| function | `core.endpoint_manager._register_manager` | 32 |
| function | `core.endpoint_manager._clear_managers_registry` | 39 |
| function | `core.endpoint_manager._latch_is_open` | 45 |
| function | `core.endpoint_manager._all_endpoints_latched` | 54 |
| function | `core.endpoint_manager._sync_support_freeze` | 70 |
| class | `core.endpoint_manager.EndpointStatus` | 95 |
| class | `core.endpoint_manager.EndpointConfig` | 106 |
| method | `core.endpoint_manager.EndpointConfig.__init__` | 109 |
| method | `core.endpoint_manager.EndpointConfig.extract_response` | 122 |
| class | `core.endpoint_manager.EndpointHealth` | 138 |
| method | `core.endpoint_manager.EndpointHealth.__init__` | 141 |
| method | `core.endpoint_manager.EndpointHealth._load_from_db` | 154 |
| method | `core.endpoint_manager.EndpointHealth._save_to_db` | 179 |
| method | `core.endpoint_manager.EndpointHealth.is_available` | 204 |
| method | `core.endpoint_manager.EndpointHealth.time_until_available` | 210 |
| method | `core.endpoint_manager.EndpointHealth.mark_success` | 216 |
| method | `core.endpoint_manager.EndpointHealth.mark_failure` | 226 |
| class | `core.endpoint_manager.AgentModelChoice` | 256 |
| class | `core.endpoint_manager.EndpointManager` | 261 |
| method | `core.endpoint_manager.EndpointManager.__init__` | 264 |
| method | `core.endpoint_manager.EndpointManager._load_models` | 288 |
| method | `core.endpoint_manager.EndpointManager._validate_model_references` | 309 |
| method | `core.endpoint_manager.EndpointManager._split_endpoint_prefix` | 331 |
| method | `core.endpoint_manager.EndpointManager._resolve_key` | 346 |
| method | `core.endpoint_manager.EndpointManager.list_all_model_references` | 373 |
| method | `core.endpoint_manager.EndpointManager.get_models_for_endpoint` | 377 |
| method | `core.endpoint_manager.EndpointManager.model_reference_exists` | 386 |
| method | `core.endpoint_manager.EndpointManager.get_endpoint_for_model` | 392 |
| method | `core.endpoint_manager.EndpointManager.get_model_config` | 406 |
| method | `core.endpoint_manager.EndpointManager.resolve_agent_model` | 425 |
| method | `core.endpoint_manager.EndpointManager.normalize_model_reference` | 438 |
| method | `core.endpoint_manager.EndpointManager._parse_model_reference` | 451 |
| method | `core.endpoint_manager.EndpointManager.get_api_key` | 478 |
| method | `core.endpoint_manager.EndpointManager._lookup_structured_api_key` | 484 |
| method | `core.endpoint_manager.EndpointManager.build_payload` | 502 |
| method | `core.endpoint_manager.EndpointManager.validate_model` | 538 |
| method | `core.endpoint_manager.EndpointManager.get_fallback_model` | 558 |
| method | `core.endpoint_manager.EndpointManager.get_available_endpoints` | 594 |
| method | `core.endpoint_manager.EndpointManager.get_health_summary` | 601 |
| function | `core.endpoint_manager.get_endpoint_manager` | 620 |
| function | `core.endpoint_manager.registered_or_none` | 631 |

### `core/events.py`

| Kind | Qualname | Line |
|------|----------|------|
| function | `core.events.publish_event` | 17 |
| function | `core.events.list_events` | 60 |

### `core/fallback_stats.py`

| Kind | Qualname | Line |
|------|----------|------|
| function | `core.fallback_stats.log_fallback` | 8 |
| function | `core.fallback_stats.get_fallback_stats` | 43 |

### `core/file_operations.py`

| Kind | Qualname | Line |
|------|----------|------|
| function | `core.file_operations.is_text_file` | 184 |
| function | `core.file_operations.compute_file_hash` | 237 |
| function | `core.file_operations.get_file_lines_with_guids` | 242 |
| function | `core.file_operations.format_file_with_guids` | 269 |
| function | `core.file_operations.get_project_directory` | 284 |
| function | `core.file_operations.is_secret_path` | 294 |
| function | `core.file_operations.should_ignore_file` | 300 |
| function | `core.file_operations.sync_file_to_database` | 340 |
| function | `core.file_operations.get_file_content_from_db` | 387 |
| function | `core.file_operations.format_file_for_agent` | 395 |
| function | `core.file_operations.generate_file_summary` | 412 |
| function | `core.file_operations.save_file_summary` | 465 |
| function | `core.file_operations.post_file_metadata_to_bus` | 505 |

### `core/file_retrieval.py`

| Kind | Qualname | Line |
|------|----------|------|
| function | `core.file_retrieval.get_file_explicit` | 8 |
| function | `core.file_retrieval.format_file_with_path` | 36 |

### `core/gitignore.py`

| Kind | Qualname | Line |
|------|----------|------|
| function | `core.gitignore.load_gitignore_spec` | 18 |
| function | `core.gitignore.should_ignore_by_gitignore` | 52 |

### `core/http_client.py`

| Kind | Qualname | Line |
|------|----------|------|
| class | `core.http_client.HttpResponse` | 19 |
| method | `core.http_client.HttpResponse.__init__` | 22 |
| method | `core.http_client.HttpResponse.json` | 28 |
| method | `core.http_client.HttpResponse.raise_for_status` | 31 |
| class | `core.http_client.HttpError` | 36 |
| function | `core.http_client._post_with_requests` | 40 |
| function | `core.http_client._post_with_urllib` | 60 |
| function | `core.http_client._get_with_requests` | 94 |
| function | `core.http_client._get_with_urllib` | 107 |
| function | `core.http_client.post_json` | 133 |
| function | `core.http_client.get_json` | 157 |
| function | `core.http_client.has_requests` | 174 |

### `core/http_diag.py`

| Kind | Qualname | Line |
|------|----------|------|
| function | `core.http_diag._header_items` | 35 |
| function | `core.http_diag._safe_headers` | 46 |
| function | `core.http_diag._priority_headers` | 56 |
| function | `core.http_diag.extract_error_payload` | 65 |
| function | `core.http_diag.format_http_error_dump` | 86 |
| function | `core.http_diag.print_http_error_dump` | 136 |

### `core/index_context.py`

| Kind | Qualname | Line |
|------|----------|------|
| function | `core.index_context.indexes_dir` | 25 |
| function | `core.index_context.load_index_text` | 33 |
| function | `core.index_context.load_symbol_json_context` | 63 |
| function | `core.index_context.build_index_context_block` | 84 |
| function | `core.index_context.index_paths_summary` | 115 |
| function | `core.index_context.refresh_target_indexes` | 125 |
| function | `core.index_context.refresh_file_symbols` | 169 |

### `core/json_parser.py`

| Kind | Qualname | Line |
|------|----------|------|
| class | `core.json_parser.ParseStatus` | 14 |
| class | `core.json_parser.ParseResult` | 25 |
| method | `core.json_parser.ParseResult.success` | 35 |
| method | `core.json_parser.ParseResult.can_resume` | 39 |
| class | `core.json_parser.JSONParser` | 44 |
| method | `core.json_parser.JSONParser.__init__` | 56 |
| method | `core.json_parser.JSONParser.parse` | 65 |
| method | `core.json_parser.JSONParser._extract_markdown_json` | 129 |
| method | `core.json_parser.JSONParser._extract_markdown_any` | 134 |
| method | `core.json_parser.JSONParser._extract_brace_bounded` | 144 |
| method | `core.json_parser.JSONParser._extract_first_json_object` | 164 |
| method | `core.json_parser.JSONParser._extract_raw` | 205 |
| method | `core.json_parser.JSONParser._try_parse` | 223 |
| method | `core.json_parser.JSONParser._looks_truncated` | 270 |
| method | `core.json_parser.JSONParser.build_resume_prompt` | 298 |
| function | `core.json_parser.get_json_parser` | 335 |
| function | `core.json_parser.parse_json_response` | 343 |

### `core/llm_test_mode.py`

| Kind | Qualname | Line |
|------|----------|------|
| function | `core.llm_test_mode.test_mode_enabled` | 26 |
| function | `core.llm_test_mode.reset_mock_queues` | 41 |
| function | `core.llm_test_mode._coerce_response` | 46 |
| function | `core.llm_test_mode._default_response` | 52 |
| function | `core.llm_test_mode.mock_call_agent` | 87 |

### `core/model_health.py`

| Kind | Qualname | Line |
|------|----------|------|
| function | `core.model_health._setting` | 113 |
| function | `core.model_health._connect` | 122 |
| function | `core.model_health._iso` | 153 |
| function | `core.model_health._parse` | 157 |
| function | `core.model_health._decay_weight` | 164 |
| function | `core.model_health.record_model_outcome` | 171 |
| function | `core.model_health.prune_old_events` | 205 |
| function | `core.model_health.load_events` | 221 |
| function | `core.model_health.load_events_for_models` | 241 |
| function | `core.model_health.compute_stats` | 279 |
| function | `core.model_health.evaluate_demotion` | 322 |
| function | `core.model_health.model_verdict` | 345 |
| function | `core.model_health._compute_down_until` | 353 |
| function | `core.model_health.model_down_until` | 373 |
| function | `core.model_health.rank_candidates` | 386 |
| function | `core.model_health.health_report` | 410 |

### `core/models_catalog.py`

| Kind | Qualname | Line |
|------|----------|------|
| function | `core.models_catalog.models_url` | 55 |
| function | `core.models_catalog.catalog_path` | 66 |
| function | `core.models_catalog.load_raw_json` | 73 |
| function | `core.models_catalog.save_raw_json` | 77 |
| function | `core.models_catalog.config_file_path` | 81 |
| function | `core.models_catalog.prompts_file_path` | 90 |
| function | `core.models_catalog.parse_model_ids` | 98 |
| function | `core.models_catalog.list_registered` | 128 |
| function | `core.models_catalog.list_assignments` | 133 |
| function | `core.models_catalog.catalog_refs` | 138 |
| function | `core.models_catalog.available_refs` | 146 |
| function | `core.models_catalog.resolve_choice` | 153 |
| function | `core.models_catalog._api_key` | 166 |
| function | `core.models_catalog._default_fetcher` | 176 |
| function | `core.models_catalog.fetch_catalog` | 187 |
| function | `core.models_catalog.load_catalog` | 233 |
| function | `core.models_catalog.resolve_or_none` | 247 |
| function | `core.models_catalog.ensure_registered` | 257 |
| function | `core.models_catalog.assign_agents` | 278 |
| function | `core.models_catalog.assign_tier` | 314 |
| function | `core.models_catalog.validate_assignments` | 327 |
| function | `core.models_catalog.prompt_text` | 362 |
| function | `core.models_catalog.set_prompt_text` | 376 |

### `core/models_wizard.py`

| Kind | Qualname | Line |
|------|----------|------|
| function | `core.models_wizard._truthy` | 33 |
| function | `core.models_wizard._default_model` | 40 |
| function | `core.models_wizard._tier_snapshot` | 45 |
| function | `core.models_wizard.print_current` | 50 |
| function | `core.models_wizard.print_numbered` | 62 |
| function | `core.models_wizard.print_resulting_config` | 71 |
| function | `core.models_wizard._pick` | 106 |
| function | `core.models_wizard._print_config_header` | 118 |
| function | `core.models_wizard._fetch_catalog_if_requested` | 132 |
| function | `core.models_wizard._pick_tiers` | 151 |
| function | `core.models_wizard._apply_tiers` | 166 |
| function | `core.models_wizard._edit_agent_overrides` | 189 |
| function | `core.models_wizard._edit_prompts` | 218 |
| function | `core.models_wizard._validate_and_write` | 262 |
| function | `core.models_wizard.run_configure` | 299 |

### `core/preflight.py`

| Kind | Qualname | Line |
|------|----------|------|
| function | `core.preflight.preflight_unattended` | 12 |

### `core/rate_limit_headers.py`

| Kind | Qualname | Line |
|------|----------|------|
| function | `core.rate_limit_headers.advertised_wait_seconds` | 44 |
| function | `core.rate_limit_headers._parse_retry_after_header` | 78 |
| function | `core.rate_limit_headers._parse_body_retry_after` | 105 |
| class | `core.rate_limit_headers.RateLimitInfo` | 125 |
| function | `core.rate_limit_headers.parse_reset_to_epoch` | 134 |
| function | `core.rate_limit_headers.classify_rate_limit` | 155 |

### `core/rate_limiter.py`

| Kind | Qualname | Line |
|------|----------|------|
| class | `core.rate_limiter.RateLimiter` | 15 |
| method | `core.rate_limiter.RateLimiter.__init__` | 18 |
| method | `core.rate_limiter.RateLimiter._effective_max_calls` | 27 |
| method | `core.rate_limiter.RateLimiter.on_success` | 31 |
| method | `core.rate_limiter.RateLimiter.on_rate_limited` | 36 |
| method | `core.rate_limiter.RateLimiter.wait_if_needed` | 41 |
| method | `core.rate_limiter.RateLimiter.set_max_calls` | 78 |

### `core/repo_env.py`

| Kind | Qualname | Line |
|------|----------|------|
| function | `core.repo_env.detect_pre_commit_hook` | 14 |
| function | `core.repo_env.build_repo_env_card` | 23 |

### `core/response_parser.py`

| Kind | Qualname | Line |
|------|----------|------|
| class | `core.response_parser.ResponseParser` | 15 |
| method | `core.response_parser.ResponseParser.__init__` | 18 |
| method | `core.response_parser.ResponseParser.parse` | 26 |
| method | `core.response_parser.ResponseParser._extract_markdown_json` | 59 |
| method | `core.response_parser.ResponseParser._extract_code_block` | 66 |
| method | `core.response_parser.ResponseParser._extract_raw_json` | 86 |
| method | `core.response_parser.ResponseParser._validate_and_parse` | 109 |

### `core/symbol_index.py`

| Kind | Qualname | Line |
|------|----------|------|
| class | `core.symbol_index.Symbol` | 23 |
| function | `core.symbol_index._utc_now` | 30 |
| function | `core.symbol_index.parse_python_symbols` | 34 |
| function | `core.symbol_index.upsert_file_symbols` | 67 |
| function | `core.symbol_index.delete_file_symbols` | 89 |
| function | `core.symbol_index.rebuild_project_symbols` | 96 |
| function | `core.symbol_index.fetch_symbol_rows` | 174 |
| function | `core.symbol_index.format_symbol_json` | 229 |
| function | `core.symbol_index.format_symbol_context_block` | 237 |

### `core/truncation_detector.py`

| Kind | Qualname | Line |
|------|----------|------|
| class | `core.truncation_detector.TruncationType` | 12 |
| class | `core.truncation_detector.TruncationResult` | 23 |
| method | `core.truncation_detector.TruncationResult.should_resume` | 33 |
| class | `core.truncation_detector.TruncationDetector` | 38 |
| method | `core.truncation_detector.TruncationDetector.__init__` | 49 |
| method | `core.truncation_detector.TruncationDetector.detect` | 52 |
| method | `core.truncation_detector.TruncationDetector._guess_format` | 86 |
| method | `core.truncation_detector.TruncationDetector._detect_json_truncation` | 97 |
| method | `core.truncation_detector.TruncationDetector._detect_diff_truncation` | 161 |
| method | `core.truncation_detector.TruncationDetector._detect_code_truncation` | 223 |
| method | `core.truncation_detector.TruncationDetector._detect_generic_truncation` | 280 |
| method | `core.truncation_detector.TruncationDetector._extract_json` | 309 |
| method | `core.truncation_detector.TruncationDetector._build_json_resume_hint` | 326 |
| function | `core.truncation_detector.get_truncation_detector` | 342 |
| function | `core.truncation_detector.detect_and_resume` | 350 |

### `file_editing/__init__.py`

| Kind | Qualname | Line |
|------|----------|------|

### `file_editing/db.py`

| Kind | Qualname | Line |
|------|----------|------|
| function | `file_editing.db.get_db_path` | 17 |
| function | `file_editing.db.get_db_connection` | 31 |
| function | `file_editing.db.log_error` | 47 |
| function | `file_editing.db.reconstruct_file_content` | 121 |
| function | `file_editing.db.capture_current_hashes` | 144 |

### `file_editing/edit_payload.py`

| Kind | Qualname | Line |
|------|----------|------|
| function | `file_editing.edit_payload._validate_target_path` | 8 |
| class | `file_editing.edit_payload.BaseOperation` | 31 |
| method | `file_editing.edit_payload.BaseOperation.__post_init__` | 36 |
| class | `file_editing.edit_payload.ReplaceBlock` | 56 |
| method | `file_editing.edit_payload.ReplaceBlock.__post_init__` | 62 |
| class | `file_editing.edit_payload.InsertAfter` | 72 |
| method | `file_editing.edit_payload.InsertAfter.__post_init__` | 77 |
| class | `file_editing.edit_payload.DeleteLines` | 86 |
| class | `file_editing.edit_payload.UpdateDocumentation` | 93 |
| method | `file_editing.edit_payload.UpdateDocumentation.__post_init__` | 97 |
| class | `file_editing.edit_payload.CreateFile` | 104 |
| method | `file_editing.edit_payload.CreateFile.__post_init__` | 109 |
| class | `file_editing.edit_payload.DeleteFile` | 117 |
| method | `file_editing.edit_payload.DeleteFile.__post_init__` | 127 |
| class | `file_editing.edit_payload.FindReplace` | 133 |
| method | `file_editing.edit_payload.FindReplace.__post_init__` | 142 |
| class | `file_editing.edit_payload.FullReplace` | 153 |
| method | `file_editing.edit_payload.FullReplace.__post_init__` | 159 |
| class | `file_editing.edit_payload.ApplyDiff` | 174 |
| method | `file_editing.edit_payload.ApplyDiff.__post_init__` | 180 |
| function | `file_editing.edit_payload._req_str` | 206 |
| function | `file_editing.edit_payload._req_any` | 213 |
| function | `file_editing.edit_payload._validate_find_replace` | 219 |
| function | `file_editing.edit_payload._validate_full_replace` | 227 |
| function | `file_editing.edit_payload.validate_operation` | 251 |
| class | `file_editing.edit_payload.EditPayload` | 272 |
| method | `file_editing.edit_payload.EditPayload.__post_init__` | 278 |
| method | `file_editing.edit_payload.EditPayload.model_validate_json` | 297 |
| method | `file_editing.edit_payload.EditPayload.model_validate` | 309 |
| method | `file_editing.edit_payload.EditPayload.model_dump_json` | 393 |

### `file_editing/editing.py`

| Kind | Qualname | Line |
|------|----------|------|
| function | `file_editing.editing._compute_hash` | 27 |
| function | `file_editing.editing._validate_guid_exists` | 31 |
| function | `file_editing.editing._validate_operation_guids` | 41 |
| function | `file_editing.editing.get_insert_sort_order` | 81 |
| function | `file_editing.editing.renumber_sort_orders` | 130 |
| function | `file_editing.editing.validate_proposal` | 167 |
| function | `file_editing.editing.apply_replace_block` | 204 |
| function | `file_editing.editing.apply_insert_after` | 278 |
| function | `file_editing.editing.apply_delete_lines` | 303 |
| function | `file_editing.editing.apply_update_documentation` | 358 |
| function | `file_editing.editing.apply_find_replace` | 373 |
| function | `file_editing.editing.apply_full_replace` | 444 |
| function | `file_editing.editing.apply_diff` | 481 |
| function | `file_editing.editing._apply_unified_diff` | 534 |
| function | `file_editing.editing.apply_create_file` | 621 |
| function | `file_editing.editing.apply_delete_file` | 692 |
| function | `file_editing.editing.apply_edit_proposal` | 732 |

### `file_editing/undo.py`

| Kind | Qualname | Line |
|------|----------|------|
| function | `file_editing.undo.ensure_snapshot_table` | 19 |
| function | `file_editing.undo.snapshot_before_apply` | 30 |
| function | `file_editing.undo.undo_proposal` | 52 |

### `file_editing/writer.py`

| Kind | Qualname | Line |
|------|----------|------|
| function | `file_editing.writer._compute_hash` | 25 |
| function | `file_editing.writer._get_or_create_file_id_short` | 29 |
| function | `file_editing.writer.initialize_file_lines` | 72 |
| function | `file_editing.writer._initialize_lines_impl` | 92 |
| function | `file_editing.writer._resolve_contained_path` | 146 |
| function | `file_editing.writer._delete_file_from_disk` | 164 |
| function | `file_editing.writer._run_ruff_precheck` | 185 |
| function | `file_editing.writer._record_lint_failure` | 224 |
| function | `file_editing.writer.write_file_to_disk` | 266 |
| function | `file_editing.writer.invalidate_other_proposals` | 306 |
| function | `file_editing.writer.materialize_proposal` | 361 |

### `interactive.py`

| Kind | Qualname | Line |
|------|----------|------|
| function | `interactive.resolve_task_description` | 42 |
| function | `interactive.signal_handler` | 67 |
| function | `interactive.should_continue_unattended` | 79 |
| function | `interactive.generate_next_task` | 111 |
| function | `interactive.save_checkpoint` | 203 |
| function | `interactive.load_checkpoint` | 232 |
| function | `interactive.run_unattended_mode` | 268 |
| function | `interactive.run_semi_attended_mode` | 437 |
| function | `interactive.interactive_loop` | 706 |

### `main.py`

| Kind | Qualname | Line |
|------|----------|------|
| function | `main.main` | 18 |

### `utils/__init__.py`

| Kind | Qualname | Line |
|------|----------|------|

### `utils/analyze_test_durations.py`

| Kind | Qualname | Line |
|------|----------|------|
| function | `utils.analyze_test_durations._load_report` | 29 |
| function | `utils.analyze_test_durations._merge_reports` | 37 |
| function | `utils.analyze_test_durations._fmt` | 45 |
| function | `utils.analyze_test_durations.main` | 51 |

### `utils/build_preview.sh`

_No Python symbols (or non-Python file)._

### `utils/consolidate.py`

| Kind | Qualname | Line |
|------|----------|------|
| class | `utils.consolidate.PySymbol` | 121 |
| class | `utils.consolidate.FileIndex` | 129 |
| function | `utils.consolidate._should_skip_dir` | 136 |
| function | `utils.consolidate.classify_path` | 144 |
| function | `utils.consolidate.parse_python_symbols` | 167 |
| function | `utils.consolidate.parse_markdown_sections` | 203 |
| function | `utils.consolidate._is_ignored_file` | 212 |
| function | `utils.consolidate._is_ignored_path` | 219 |
| function | `utils.consolidate.collect_indexes` | 231 |
| function | `utils.consolidate._write_production_index` | 279 |
| function | `utils.consolidate._write_test_index` | 296 |
| function | `utils.consolidate._write_markdown_index` | 319 |
| function | `utils.consolidate.write_index_files` | 334 |
| function | `utils.consolidate.generate_target_indexes` | 385 |
| function | `utils.consolidate.consolidate_project` | 436 |
| function | `utils.consolidate._generation_stamp` | 536 |
| function | `utils.consolidate.discover_project_root` | 543 |

### `utils/diagnose_soak.sh`

_No Python symbols (or non-Python file)._

### `utils/export_project_zip.py`

| Kind | Qualname | Line |
|------|----------|------|
| function | `utils.export_project_zip.discover_project_root` | 100 |
| function | `utils.export_project_zip.should_skip` | 125 |
| function | `utils.export_project_zip.run_consolidate` | 141 |
| function | `utils.export_project_zip.export_zip` | 158 |
| function | `utils.export_project_zip.main` | 197 |

### `utils/generate_agent_schemas.py`

| Kind | Qualname | Line |
|------|----------|------|
| function | `utils.generate_agent_schemas.create_schema_directory` | 250 |
| function | `utils.generate_agent_schemas.write_schema_file` | 256 |
| function | `utils.generate_agent_schemas.generate_all_schemas` | 266 |
| function | `utils.generate_agent_schemas.generate_readme` | 321 |

### `utils/git_operations.py`

| Kind | Qualname | Line |
|------|----------|------|
| function | `utils.git_operations.git_init` | 16 |
| function | `utils.git_operations.git_commit` | 35 |
| function | `utils.git_operations.ensure_git_initialized` | 128 |
| function | `utils.git_operations.git_status` | 256 |
| function | `utils.git_operations.git_log` | 277 |

### `utils/list_endpoint_models.py`

| Kind | Qualname | Line |
|------|----------|------|
| function | `utils.list_endpoint_models.load_test_models` | 28 |
| function | `utils.list_endpoint_models._post_with_retry` | 52 |
| function | `utils.list_endpoint_models.test_models_endpoint` | 91 |
| function | `utils.list_endpoint_models.test_model` | 124 |
| function | `utils.list_endpoint_models.main` | 173 |

### `utils/list_models_to_test.json`

_No Python symbols (or non-Python file)._

### `utils/loc_stats.py`

| Kind | Qualname | Line |
|------|----------|------|
| function | `utils.loc_stats._should_skip` | 54 |
| function | `utils.loc_stats._collect` | 62 |
| function | `utils.loc_stats._fmt_int` | 93 |
| function | `utils.loc_stats._fmt_bytes` | 97 |
| function | `utils.loc_stats._percentile` | 105 |
| function | `utils.loc_stats._sum` | 114 |
| function | `utils.loc_stats._md_table` | 118 |
| function | `utils.loc_stats._render` | 132 |
| function | `utils.loc_stats.main` | 350 |

### `utils/models_cli.py`

| Kind | Qualname | Line |
|------|----------|------|
| function | `utils.models_cli._load_runtime` | 48 |
| function | `utils.models_cli.cmd_configure` | 54 |
| function | `utils.models_cli.cmd_models_list` | 74 |
| function | `utils.models_cli.cmd_models_fetch` | 93 |
| function | `utils.models_cli.cmd_models_assign` | 115 |
| function | `utils.models_cli.cmd_models_assign_tier` | 144 |
| function | `utils.models_cli.cmd_models_validate` | 171 |
| function | `utils.models_cli.cmd_prompt_show` | 185 |
| function | `utils.models_cli.cmd_prompt_set` | 198 |
| function | `utils.models_cli.build_parser` | 218 |
| function | `utils.models_cli.main` | 266 |

### `utils/pre_commit.sh`

_No Python symbols (or non-Python file)._

### `utils/query_developer_responses.py`

| Kind | Qualname | Line |
|------|----------|------|
| function | `utils.query_developer_responses._db_file` | 37 |
| function | `utils.query_developer_responses._connect_ro` | 49 |
| function | `utils.query_developer_responses.list_recent_developer_responses` | 59 |
| function | `utils.query_developer_responses._print_table` | 153 |
| function | `utils.query_developer_responses._get_db` | 171 |
| function | `utils.query_developer_responses._q` | 180 |
| function | `utils.query_developer_responses.show_edit_proposals` | 189 |
| function | `utils.query_developer_responses.show_file_write_log` | 234 |
| function | `utils.query_developer_responses.show_errors` | 251 |
| function | `utils.query_developer_responses.show_edit_events` | 291 |
| function | `utils.query_developer_responses.show_file_line_counts` | 308 |
| function | `utils.query_developer_responses._is_sensitive_or_ignored` | 330 |
| function | `utils.query_developer_responses.show_git_failures` | 342 |
| function | `utils.query_developer_responses.show_run_effectiveness` | 373 |
| function | `utils.query_developer_responses.run_adhoc_sql` | 556 |
| function | `utils.query_developer_responses.run_model_health` | 588 |
| function | `utils.query_developer_responses._print_data_window` | 615 |
| function | `utils.query_developer_responses.run_full_diagnostic` | 645 |
| function | `utils.query_developer_responses.main` | 673 |

### `utils/run_codemodes.py`

| Kind | Qualname | Line |
|------|----------|------|
| function | `utils.run_codemodes.project_root_from_script` | 43 |
| function | `utils.run_codemodes.iter_py_files` | 50 |
| function | `utils.run_codemodes.read_text` | 57 |
| class | `utils.run_codemodes.CallableFixer` | 65 |
| method | `utils.run_codemodes.CallableFixer.__init__` | 66 |
| method | `utils.run_codemodes.CallableFixer.leave_Annotation` | 69 |
| method | `utils.run_codemodes.CallableFixer.leave_Param` | 81 |
| function | `utils.run_codemodes.run_fix_callable` | 88 |
| class | `utils.run_codemodes.TypingUsageCollector` | 114 |
| method | `utils.run_codemodes.TypingUsageCollector.__init__` | 115 |
| method | `utils.run_codemodes.TypingUsageCollector.visit_Name` | 118 |
| function | `utils.run_codemodes.run_add_typing_imports` | 123 |
| class | `utils.run_codemodes.OptionalizeParams` | 148 |
| method | `utils.run_codemodes.OptionalizeParams.__init__` | 149 |
| method | `utils.run_codemodes.OptionalizeParams.leave_Param` | 152 |
| class | `utils.run_codemodes.AddAnyAnn` | 200 |
| method | `utils.run_codemodes.AddAnyAnn.__init__` | 201 |
| method | `utils.run_codemodes.AddAnyAnn.leave_Assign` | 204 |
| function | `utils.run_codemodes.run_add_any_annotations` | 223 |
| function | `utils.run_codemodes.run_widen_edit_payload` | 249 |
| function | `utils.run_codemodes.parse_args` | 274 |
| function | `utils.run_codemodes.main` | 281 |

### `utils/run_critical_tests.py`

| Kind | Qualname | Line |
|------|----------|------|
| class | `utils.run_critical_tests.TestPathContainment` | 24 |
| method | `utils.run_critical_tests.TestPathContainment.test_rejects_traversal` | 25 |
| class | `utils.run_critical_tests.TestModeSelector` | 46 |
| method | `utils.run_critical_tests.TestModeSelector.test_fallback_chain` | 47 |
| class | `utils.run_critical_tests.TestEditValidator` | 61 |
| method | `utils.run_critical_tests.TestEditValidator.test_find_replace_and_empty` | 62 |
| class | `utils.run_critical_tests.TestMockLLM` | 74 |
| method | `utils.run_critical_tests.TestMockLLM.test_scripted_call_agent` | 75 |
| class | `utils.run_critical_tests.TestEditPayloadOps` | 88 |
| method | `utils.run_critical_tests.TestEditPayloadOps.test_parse_core_ops` | 89 |
| function | `utils.run_critical_tests.main` | 137 |

### `utils/run_tests.sh`

_No Python symbols (or non-Python file)._

### `utils/setup.sh`

_No Python symbols (or non-Python file)._

### `utils/smoke_real_model.py`

| Kind | Qualname | Line |
|------|----------|------|
| function | `utils.smoke_real_model._has_usable_key` | 24 |
| function | `utils.smoke_real_model.main` | 51 |

### `utils/soak-setup.sh`

_No Python symbols (or non-Python file)._

### `utils/testing.py`

| Kind | Qualname | Line |
|------|----------|------|
| function | `utils.testing.test_agent` | 6 |
| function | `utils.testing.test_all_agents` | 33 |

### `workflow/__init__.py`

| Kind | Qualname | Line |
|------|----------|------|

### `workflow/backlog.py`

| Kind | Qualname | Line |
|------|----------|------|
| function | `workflow.backlog.normalize_backlog_tiers` | 24 |
| function | `workflow.backlog.resolve_backlog_tier` | 39 |
| function | `workflow.backlog.tier_pool_policy` | 55 |
| function | `workflow.backlog.count_unaddressed_feedback` | 94 |
| function | `workflow.backlog.fetch_top_feedback` | 113 |
| function | `workflow.backlog.mark_targeted` | 140 |
| function | `workflow.backlog.stuck_feedback_ids` | 154 |
| function | `workflow.backlog.apply_backlog_overrides` | 163 |
| function | `workflow.backlog._stuck_threshold` | 231 |

### `workflow/developer_edit.py`

| Kind | Qualname | Line |
|------|----------|------|
| function | `workflow.developer_edit.fetch_latest_reviewer_feedback` | 34 |
| function | `workflow.developer_edit._build_generation_prompt` | 101 |
| function | `workflow.developer_edit._normalize_payload` | 197 |
| function | `workflow.developer_edit.run_developer_mutation` | 254 |

### `workflow/edit_mode_selector.py`

| Kind | Qualname | Line |
|------|----------|------|
| class | `workflow.edit_mode_selector.ModeDecision` | 32 |
| function | `workflow.edit_mode_selector._estimate_change_size` | 42 |
| function | `workflow.edit_mode_selector.select_edit_mode` | 84 |
| function | `workflow.edit_mode_selector.next_fallback_mode` | 173 |
| function | `workflow.edit_mode_selector.build_developer_edit_prompt` | 192 |

### `workflow/git_failure.py`

| Kind | Qualname | Line |
|------|----------|------|
| function | `workflow.git_failure.record_git_failure` | 28 |

### `workflow/path_targets.py`

| Kind | Qualname | Line |
|------|----------|------|
| function | `workflow.path_targets.parse_hook_cited_files` | 25 |
| function | `workflow.path_targets.sanitize_path_token` | 38 |
| function | `workflow.path_targets.extract_files_needed_from_text` | 81 |
| function | `workflow.path_targets.is_valid_edit_target_path` | 111 |

### `workflow/post_materialize.py`

| Kind | Qualname | Line |
|------|----------|------|
| function | `workflow.post_materialize.queue_localized_verify` | 18 |
| function | `workflow.post_materialize.notify_path_changed` | 43 |
| function | `workflow.post_materialize.apply_materialize_outcome` | 59 |

### `workflow/proposal_builder.py`

| Kind | Qualname | Line |
|------|----------|------|
| function | `workflow.proposal_builder._get_or_create_file_id` | 18 |
| function | `workflow.proposal_builder._get_affected_guids_from_operation` | 51 |
| function | `workflow.proposal_builder._capture_hashes_for_operations` | 74 |
| function | `workflow.proposal_builder.create_proposal_from_developer_output` | 97 |
| function | `workflow.proposal_builder.update_proposal_status` | 209 |

### `workflow/reviewer_gate.py`

| Kind | Qualname | Line |
|------|----------|------|
| class | `workflow.reviewer_gate.ReviewerVerdict` | 32 |
| method | `workflow.reviewer_gate.ReviewerVerdict.rejected` | 42 |
| function | `workflow.reviewer_gate.parse_reviewer_verdict` | 46 |
| function | `workflow.reviewer_gate.request_review_verdict` | 99 |
| function | `workflow.reviewer_gate.post_reviewer_suggestions` | 130 |
| function | `workflow.reviewer_gate.log_reviewer_rejection` | 144 |
| function | `workflow.reviewer_gate.handle_reviewer_rejection` | 173 |

### `workflow/shell_developer.py`

| Kind | Qualname | Line |
|------|----------|------|
| class | `workflow.shell_developer.ShellDeveloperConfig` | 67 |
| method | `workflow.shell_developer.ShellDeveloperConfig.from_config` | 104 |
| function | `workflow.shell_developer.build_instance_prompt` | 257 |
| function | `workflow.shell_developer.build_inspect_prompt` | 275 |
| function | `workflow.shell_developer.build_chat_prompt` | 348 |
| function | `workflow.shell_developer._chat_table_mode` | 375 |
| function | `workflow.shell_developer._seed_path_candidates` | 410 |
| function | `workflow.shell_developer._versionish_or_invalid` | 423 |
| function | `workflow.shell_developer._path_like_seed_candidate` | 439 |
| function | `workflow.shell_developer.resolve_seed_target_path` | 461 |
| function | `workflow.shell_developer.command_touches_target` | 482 |
| function | `workflow.shell_developer._parse_name_status` | 488 |
| function | `workflow.shell_developer._safe_edit_target` | 505 |
| function | `workflow.shell_developer._worktree_change_state` | 519 |
| function | `workflow.shell_developer.finish_claims_no_shell` | 530 |
| function | `workflow.shell_developer.is_enterprise_chat_developer` | 535 |
| function | `workflow.shell_developer._enterprise_chat_base_url` | 540 |
| function | `workflow.shell_developer.extract_bash_command` | 555 |
| function | `workflow.shell_developer.extract_finish` | 565 |
| function | `workflow.shell_developer.classify_shell_reply` | 570 |
| function | `workflow.shell_developer.evidence_command` | 575 |
| function | `workflow.shell_developer.is_evidence_command` | 579 |
| function | `workflow.shell_developer.augment_evidence_command` | 588 |
| function | `workflow.shell_developer.parse_evidence_output` | 599 |
| function | `workflow.shell_developer.evidence_inject_message` | 614 |
| class | `workflow.shell_developer.ShellWorktree` | 628 |
| method | `workflow.shell_developer.ShellWorktree.__init__` | 631 |
| method | `workflow.shell_developer.ShellWorktree._git` | 644 |
| method | `workflow.shell_developer.ShellWorktree.create` | 653 |
| method | `workflow.shell_developer.ShellWorktree._snapshot_baseline` | 692 |
| method | `workflow.shell_developer.ShellWorktree.sync_governed_state` | 709 |
| method | `workflow.shell_developer.ShellWorktree.working_dir` | 755 |
| method | `workflow.shell_developer.ShellWorktree.run_command` | 759 |
| method | `workflow.shell_developer.ShellWorktree.run_test_command` | 777 |
| method | `workflow.shell_developer.ShellWorktree.collect_changes` | 794 |
| method | `workflow.shell_developer.ShellWorktree.change_state_since_baseline` | 855 |
| method | `workflow.shell_developer.ShellWorktree._strip_sub` | 882 |
| method | `workflow.shell_developer.ShellWorktree.cleanup` | 892 |
| class | `workflow.shell_developer.SessionResult` | 918 |
| function | `workflow.shell_developer._recent_failure_kind` | 945 |
| function | `workflow.shell_developer._recent_failure_detail` | 954 |
| function | `workflow.shell_developer._recent_failure` | 962 |
| class | `workflow.shell_developer.ShellDeveloperSession` | 980 |
| method | `workflow.shell_developer.ShellDeveloperSession.__init__` | 981 |
| method | `workflow.shell_developer.ShellDeveloperSession._resolve_developer_model` | 1010 |
| method | `workflow.shell_developer.ShellDeveloperSession._llm` | 1040 |
| method | `workflow.shell_developer.ShellDeveloperSession._observation` | 1091 |
| method | `workflow.shell_developer.ShellDeveloperSession._record_step` | 1129 |
| method | `workflow.shell_developer.ShellDeveloperSession._emit_command_failed_if_needed` | 1167 |
| method | `workflow.shell_developer.ShellDeveloperSession._record_model_health` | 1175 |
| method | `workflow.shell_developer.ShellDeveloperSession._effective_command_timeout` | 1182 |
| method | `workflow.shell_developer.ShellDeveloperSession._run_worktree_command` | 1195 |
| method | `workflow.shell_developer.ShellDeveloperSession._apply_edit_payload` | 1201 |
| method | `workflow.shell_developer.ShellDeveloperSession._normalize_stall_key` | 1241 |
| method | `workflow.shell_developer.ShellDeveloperSession._note_step_outcome` | 1244 |
| method | `workflow.shell_developer.ShellDeveloperSession._mark_stalled` | 1267 |
| method | `workflow.shell_developer.ShellDeveloperSession._run_in_process_evidence` | 1281 |
| method | `workflow.shell_developer.ShellDeveloperSession._mark_target_inspected` | 1310 |
| method | `workflow.shell_developer.ShellDeveloperSession._reject_finish` | 1316 |
| method | `workflow.shell_developer.ShellDeveloperSession.run` | 1326 |
| method | `workflow.shell_developer.ShellDeveloperSession.serialize` | 1598 |
| function | `workflow.shell_developer.change_to_operation` | 1630 |
| function | `workflow.shell_developer._build_rationale` | 1651 |
| function | `workflow.shell_developer._bounded` | 1664 |
| function | `workflow.shell_developer._gate_and_materialize` | 1684 |
| function | `workflow.shell_developer._test_evidence` | 1799 |
| function | `workflow.shell_developer._read_current_file` | 1806 |
| function | `workflow.shell_developer._gate_and_materialize_changes` | 1812 |
| function | `workflow.shell_developer._publish_shell_event` | 1876 |
| function | `workflow.shell_developer._session_mut_fields` | 1884 |
| function | `workflow.shell_developer._handle_session_without_changes` | 1895 |
| function | `workflow.shell_developer._task_is_targeted` | 1922 |
| function | `workflow.shell_developer.run_shell_developer_turn` | 1941 |
| function | `workflow.shell_developer._mark_feedback_addressed` | 2146 |
| function | `workflow.shell_developer._save_trajectory` | 2182 |

### `workflow/shell_protocol.py`

| Kind | Qualname | Line |
|------|----------|------|
| function | `workflow.shell_protocol.is_valid_bash_block` | 38 |
| function | `workflow.shell_protocol.is_unterminated_bash_block` | 44 |
| function | `workflow.shell_protocol.extract_chat_table_action` | 52 |
| function | `workflow.shell_protocol._parse_edit_body` | 168 |
| function | `workflow.shell_protocol.extract_edit_payload` | 204 |
| function | `workflow.shell_protocol.classify_shell_reply` | 253 |
| function | `workflow.shell_protocol._first_nonempty_line` | 304 |
| function | `workflow.shell_protocol.is_canonical_finish` | 312 |
| function | `workflow.shell_protocol.normalize_shell_reply` | 328 |
| function | `workflow.shell_protocol.diagnose_shell_reply` | 347 |
| function | `workflow.shell_protocol.extract_bash_command` | 394 |
| function | `workflow.shell_protocol.extract_finish` | 412 |

### `workflow/task_runner.py`

| Kind | Qualname | Line |
|------|----------|------|
| function | `workflow.task_runner._is_network_failure_text` | 45 |
| function | `workflow.task_runner._edit_mode_settings` | 56 |
| function | `workflow.task_runner._inject_seed_feedback` | 72 |
| function | `workflow.task_runner._fallback_targets` | 109 |
| function | `workflow.task_runner._dispatch_developer` | 149 |
| function | `workflow.task_runner._edit_payload_fallback` | 231 |
| function | `workflow.task_runner._finish_gate_blocked` | 273 |
| function | `workflow.task_runner._finalize_task` | 293 |
| function | `workflow.task_runner._ensure_pool_started` | 320 |
| class | `workflow.task_runner.NetworkBusyLoopGuard` | 348 |
| method | `workflow.task_runner.NetworkBusyLoopGuard.__init__` | 358 |
| method | `workflow.task_runner.NetworkBusyLoopGuard.record_failure` | 364 |
| method | `workflow.task_runner.NetworkBusyLoopGuard.surface` | 372 |
| method | `workflow.task_runner.NetworkBusyLoopGuard.record_success` | 385 |
| method | `workflow.task_runner.NetworkBusyLoopGuard.consume_pause` | 390 |
| class | `workflow.task_runner.NoProgressLoopGuard` | 394 |
| method | `workflow.task_runner.NoProgressLoopGuard.__init__` | 421 |
| method | `workflow.task_runner.NoProgressLoopGuard.stalled` | 428 |
| method | `workflow.task_runner.NoProgressLoopGuard.record_change` | 431 |
| method | `workflow.task_runner.NoProgressLoopGuard.record_neutral` | 436 |
| method | `workflow.task_runner.NoProgressLoopGuard.record_cycle` | 439 |
| method | `workflow.task_runner.NoProgressLoopGuard.record_no_change` | 452 |
| class | `workflow.task_runner.ZeroCommandSeedGuard` | 470 |
| method | `workflow.task_runner.ZeroCommandSeedGuard.__init__` | 479 |
| method | `workflow.task_runner.ZeroCommandSeedGuard.latched` | 482 |
| method | `workflow.task_runner.ZeroCommandSeedGuard.record` | 485 |
| function | `workflow.task_runner._is_zero_command_seed_failure` | 491 |
| function | `workflow.task_runner._is_uncompleted_session` | 516 |
| function | `workflow.task_runner._record_developer_progress` | 547 |
| function | `workflow.task_runner.run_task_cycle` | 570 |

---

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

---

## Index: Markdown documentation

Doc files and heading sections (`#` ... `######`).

### `Federation/Plan.md`

| Level | Section | Line |
|-------|---------|------|
| H1 | Flexible Plan — Forge Federation | 1 |
| H2 | Overview | 6 |
| H2 | Development Philosophy | 14 |
| H2 | Architecture Alignment | 24 |
| H2 | Sprint Guidelines | 34 |
| H2 | Phased Direction (Flexible) | 42 |
| H3 | Phase 1: Enhance Existing PrizmForge (Next Several Sprints) | 44 |
| H3 | Phase 2: Evaluate Expansion (When Ready) | 59 |
| H3 | Phase 3: Broader Federation Capabilities (Future) | 70 |
| H2 | Resource Strategy | 75 |
| H2 | Current Priorities | 86 |
| H2 | Open Questions | 94 |
| H2 | Working Agreements | 102 |
| H2 | Persistence & multi-writer (design note) | 115 |

### `Federation/mental_model_territories.md`

| Level | Section | Line |
|-------|---------|------|
| H1 | Mental Model Territories | 1 |
| H2 | Overview | 8 |
| H2 | Core Architecture Layers | 16 |
| H3 | 1. Stewardship Governance Layer (Constitutional Layer) | 18 |
| H3 | 2. Spider Web Discrimination Layer (Cross-Cutting) | 29 |
| H3 | 3. Territories (Mental Model Ecosystems) | 33 |
| H2 | Territory Model | 39 |
| H3 | Incompatibility Matrix | 52 |
| H2 | How Territories Interact | 60 |
| H2 | Development Approach | 72 |
| H2 | Related Documents | 84 |

### `Federation/readme.md`

| Level | Section | Line |
|-------|---------|------|
| H1 | Forge Federation | 3 |
| H2 | What is Forge Federation? | 7 |
| H2 | Key Concepts | 13 |
| H2 | Documentation | 19 |
| H2 | Current Status | 29 |

### `Federation/system_mental_model_progression_plans.md`

| Level | Section | Line |
|-------|---------|------|
| H1 | System Mental Model Progression Plans | 1 |
| H2 | Current State: Stage 0 - Legacy PrizmForge | 12 |
| H3 | Key Characteristics | 16 |
| H3 | Primary Problems | 23 |
| H2 | Stage 1 - Enhanced PrizmForge (Next Target) | 33 |
| H3 | Goals | 37 |
| H3 | Planned Improvements | 43 |
| H3 | Stage 1 Success Metrics | 52 |
| H3 | Key Risks & Assumptions | 58 |
| H2 | Stage 2 - Forge Federation (Longer-Term Vision) | 67 |
| H3 | Core Concepts | 71 |
| H2 | Development Principles | 81 |
| H2 | Where Things Live | 90 |
| H2 | Stage Transition Criteria | 101 |
| H2 | Summary | 115 |

### `Federation/territory_model.md`

| Level | Section | Line |
|-------|---------|------|
| H1 | Territory Model — Hybrid Core + Role Design | 1 |
| H2 | Overview | 3 |
| H2 | Design Goals | 14 |
| H2 | Core Philosophy (The "Race") | 22 |
| H3 | Categories | 26 |
| H2 | Role (The "Class") | 38 |
| H3 | Categories | 42 |
| H2 | Incompatibility Matrix | 54 |
| H2 | Architectural Split: Hardcoded vs. Configured | 68 |
| H3 | Key Principle | 81 |
| H2 | Reducing Tamagotchi Tendencies | 88 |
| H2 | Territory Composition Rules (Current) | 97 |
| H2 | Future Considerations | 104 |
| H2 | Related Documents | 111 |

### `Federation/territory_role_details.md`

| Level | Section | Line |
|-------|---------|------|
| H1 | Territory Role Details | 1 |
| H2 | Overview | 5 |
| H3 | Role Composition Rules | 11 |
| H2 | Role Categories | 20 |
| H2 | Detailed Role Definitions | 34 |
| H3 | Critical / Analytical Roles | 36 |
| H4 | Adversarial | 38 |
| H4 | Auditor | 45 |
| H3 | Generative Roles | 52 |
| H4 | Synthesizer | 54 |
| H4 | Experimenter | 61 |
| H4 | Regenerator | 68 |
| H3 | Operational Roles | 75 |
| H4 | Implementer | 77 |
| H4 | Prioritizer | 84 |
| H3 | Coordination Roles | 91 |
| H4 | Facilitator | 93 |
| H4 | Archivist | 100 |
| H3 | Maintenance Roles | 107 |
| H4 | Maintainer | 109 |
| H2 | Role Interaction Guidelines | 118 |
| H2 | Summary Table | 127 |

### `README.md`

| Level | Section | Line |
|-------|---------|------|
| H1 | PrizmForge | 3 |
| H2 | Core Philosophy | 9 |
| H3 | Operator Principle #1 — The mutation path is the most unblocked path | 18 |
| H2 | Quick Start | 53 |
| H1 | 1. Bootstrap a local virtual environment and install dependencies | 56 |
| H1 | 2. Activate the environment | 59 |
| H1 | .venv\Scripts\activate           # Windows | 61 |
| H1 | 3. Copy configuration templates (if needed) | 63 |
| H1 | 4. Run | 67 |
| H2 | Architecture | 76 |
| H3 | System Architecture Diagram | 78 |
| H3 | Agent Classes | 121 |
| H2 | Current File Editing Methodology (Governed Editing) | 181 |
| H3 | Key Concepts | 185 |
| H3 | Editing Flow | 194 |
| H2 | Key Safety Features | 232 |
| H2 | Governed editing notes | 243 |
| H3 | `create_file` operation | 245 |
| H3 | Project directory / repo root | 256 |
| H3 | Mutation event log | 261 |
| H3 | Binary content rejection | 266 |
| H3 | Proposal undo | 287 |
| H2 | Dependencies | 295 |
| H1 | Preferred: one-command bootstrap (creates .venv + installs both files) | 305 |
| H1 | Manual alternative | 308 |
| H2 | Testing | 317 |
| H1 | Preferred CI / local normal gate | 323 |
| H1 | Full suite (host-aware) | 326 |
| H1 | Slow / concurrent worker stress | 329 |
| H1 | Ultra-minimal host (no pytest) | 332 |
| H1 | Optional real-model smoke (requires keys / network) | 335 |
| H2 | Compliance & authorization | 341 |
| H2 | Project export & indexes | 346 |
| H1 | Indexes + full review under report/ | 354 |
| H1 | Indexes only | 357 |
| H1 | Consolidate then create ../PrizmForge-multi-agent.zip | 360 |
| H1 | Zip without regenerating report/ | 363 |
| H2 | Configuration | 370 |
| H2 | CLI usage examples | 375 |
| H3 | First-time setup (detailed) | 380 |
| H1 | Preferred bootstrap | 383 |
| H1 | Copy templates if needed | 387 |
| H3 | Unattended (config only, no stdin) | 394 |
| H1 | Optional DB override (prefer project path, not /tmp for real runs): | 403 |
| H1 | PRIZMFORGE_DB_PATH=./ExampleProject/.PrizmForge/agents.db python main.py | 404 |
| H3 | Semi-attended / interactive commands | 407 |
| H3 | Utilities (from repo root) | 427 |
| H1 | Structural indexes + optional full review → report/ | 430 |
| H1 | Package project (runs consolidate, includes report/) | 435 |
| H1 | Tests (see tests/README.md for full details) | 440 |
| H3 | Dry-run without API keys | 446 |
| H1 | config.json: "llm": { "test_mode": true } | 449 |
| H1 | or: | 450 |
| H2 | Project Status | 456 |
| H2 | License | 462 |

### `agent_schemas/README.md`

| Level | Section | Line |
|-------|---------|------|
| H1 | Agent Schema Files | 1 |
| H2 | Categories | 5 |
| H2 | GUID Format | 11 |
| H2 | Usage | 15 |

### `contributing.md`

| Level | Section | Line |
|-------|---------|------|
| H1 | Contributing to PrizmForge | 1 |
| H2 | Table of Contents | 5 |
| H2 | Adding New Endpoints | 18 |
| H3 | Step 1: Add Endpoint Configuration | 20 |
| H3 | Step 2: Add API Key | 45 |
| H3 | Step 3: Test Endpoint | 58 |
| H1 | Should show your new endpoint | 64 |
| H1 | Should show as available | 67 |
| H3 | Step 4: Add Models for Endpoint | 70 |
| H3 | Example: Custom Endpoint with Different Response Format | 93 |
| H2 | Adding New Models | 121 |
| H3 | Step 1: Define Model | 123 |
| H3 | Step 2: Assign to Agents (Optional) | 146 |
| H3 | Step 3: Test Model | 156 |
| H1 | Should show new model | 160 |
| H1 | Test with specific agent | 162 |
| H2 | Adding New Agents | 168 |
| H3 | Step 1: Create System Prompt | 170 |
| H3 | Step 2: Assign Model | 183 |
| H3 | Step 3: Create Agent Logic (Optional) | 195 |
| H1 | Parse JSON response | 228 |
| H3 | Step 4: Integrate into Workflow | 241 |
| H1 | In task_runner.py | 246 |
| H1 | Get files to audit | 250 |
| H1 | Process results | 257 |
| H3 | Step 5: Update Orchestrator | 268 |
| H3 | Step 6: Test Agent | 280 |
| H2 | Adding New Commands | 288 |
| H3 | Step 1: Create Command Function | 290 |
| H1 | Query security feedback | 307 |
| H1 | Don't conn.close() | 322 |
| H1 | Group by severity | 328 |
| H3 | Step 2: Add Command Handler | 347 |
| H1 | In interactive_loop(), add before task execution fallthrough: | 352 |
| H3 | Step 3: Update Help | 361 |
| H3 | Step 4: Test Command | 376 |
| H1 | Should show new command | 382 |
| H1 | Should run without errors | 385 |
| H1 | Should show task-specific report | 388 |
| H2 | Adding Background Agents | 393 |
| H3 | Step 1: Create Agent Prompt | 395 |
| H3 | Step 2: Add to Worker Pool | 408 |
| H1 | Start workers | 427 |
| H3 | Step 3: Add Feedback Parsing | 435 |
| H1 | Extract findings based on agent type | 450 |
| H1 | Save each item... | 461 |
| H3 | Step 4: Assign Model | 464 |
| H3 | Step 5: Test | 476 |
| H1 | Watch for output: | 484 |
| H1 | 🤖 Started performance_analyzer worker | 485 |
| H1 | ✅ performance_analyzer posted 2 feedback item(s) | 486 |
| H1 | Should show performance_analyzer stats | 489 |
| H2 | Modifying Database Schema | 494 |
| H3 | Step 1: Add Table Definition | 496 |
| H3 | Step 2: Create Helper Functions | 526 |
| H1 | don't conn.commit() | 553 |
| H1 | don't conn.close() | 554 |
| H3 | Step 3: Use in Code | 576 |
| H1 | After security audit | 581 |
| H3 | Step 4: Test Migration | 586 |
| H1 | Backup database first | 589 |
| H1 | Run PrizmForge (will create new tables) | 592 |
| H1 | Verify tables created | 595 |
| H1 | Should show: security_scans | 597 |
| H2 | Creating Custom Workflows | 602 |
| H3 | Example: Security Audit Workflow | 604 |
| H1 | Get all Python files | 622 |
| H1 | Scan each file | 637 |
| H1 | Call security auditor | 645 |
| H1 | Parse vulnerabilities | 655 |
| H1 | Check for critical | 670 |
| H1 | Save to database | 675 |
| H1 | Summary | 683 |
| H3 | Integrate into CLI | 698 |
| H3 | Test Workflow | 732 |
| H2 | Testing Extensions | 764 |
| H3 | Unit Testing Custom Agents | 766 |
| H1 | Should indicate no issues or low severity | 804 |
| H3 | Integration Testing Workflows | 817 |
| H1 | Add test file | 837 |
| H3 | Manual Testing Checklist | 861 |
| H2 | Best Practices | 876 |
| H3 | Code Style | 878 |
| H1 | Good: Matches existing style | 883 |
| H1 | Implementation | 888 |
| H1 | Bad: Different style | 892 |
| H1 | Implementation | 895 |
| H3 | Database Operations | 926 |
| H1 | Good: Prevents SQL injection | 931 |
| H1 | Bad: Vulnerable to SQL injection | 934 |
| H1 | Use our custom context manager, close and commit happen automatically | 941 |
| H3 | Error Handling | 950 |
| H1 | Bad: Hides problems | 974 |
| H1 | Good: Handle specifically or re-raise | 980 |
| H3 | Agent Prompts | 990 |
| H1 | Good: Clear instructions | 995 |
| H1 | Bad: Vague | 1008 |
| H1 | Try multiple parsing strategies | 1033 |
| H2 | Debugging Extensions | 1051 |
| H3 | Enable Verbose Logging | 1053 |
| H3 | Check Database State | 1067 |
| H3 | Test Agent Responses | 1081 |
| H3 | Export for Analysis | 1093 |
| H1 | Open CSV in Excel/LibreOffice | 1098 |
| H1 | Check for patterns, errors, etc. | 1099 |
| H2 | Submitting Changes | 1104 |
| H3 | Before Submitting | 1106 |
| H3 | Documentation Updates | 1128 |
| H2 | Examples Repository | 1150 |
| H2 | Getting Help | 1163 |
| H3 | Resources | 1165 |
| H3 | Community | 1171 |
| H2 | Future Enhancements | 1179 |

### `docs/COMPLIANCE.md`

| Level | Section | Line |
|-------|---------|------|
| H1 | Compliance, RMF & Secure Development (Navy RAISE / DoD) | 1 |
| H2 | Solution context | 11 |
| H2 | RMF compliance framework & governance | 22 |
| H2 | Software development security requirements | 34 |
| H3 | 1. Secure Python architecture (DISA ASD STIG) | 38 |
| H3 | 2. Container hardening & AWS EKS governance | 48 |
| H2 | RMF & RAISE 2.0 compliance artifacts matrix | 55 |
| H3 | 1. Initial deployment & boundary readiness (pre-deployment) | 59 |
| H3 | 2. Automated CI/CD artifacts (continuous monitoring) | 68 |
| H2 | DevSecOps pipeline & continuous monitoring | 79 |
| H2 | Local development (security-oriented checks) | 88 |
| H3 | Prerequisites | 90 |
| H3 | Suggested local flow | 96 |
| H1 | optional: pip install -r requirements-dev.txt | 106 |
| H1 | Static security (when bandit is available in the environment) | 108 |
| H1 | Engineering test suite (no network required for default gate) | 111 |
| H1 | or unattended via config.json cli_mode + optional llm.test_mode | 119 |
| H2 | Points of contact | 132 |
| H2 | Document control | 142 |

### `docs/CONFIGURATION.md`

| Level | Section | Line |
|-------|---------|------|
| H1 | PrizmForge Configuration Schema | 1 |
| H2 | Files | 13 |
| H2 | Top-level keys | 25 |
| H2 | `cli_mode` | 56 |
| H3 | `cli_mode.unattended` | 63 |
| H2 | `endpoints` (map of name → endpoint) | 77 |
| H2 | `fallback_settings` | 100 |
| H2 | `models` (map of model id → spec) | 115 |
| H2 | `agent_model_preferences` | 127 |
| H2 | `proxy` | 137 |
| H2 | `token_budget` | 146 |
| H3 | `endpoints.<name>.token_budget` | 157 |
| H2 | `reporter` | 163 |
| H2 | `resource_controller` | 178 |
| H3 | `resource_controller.project_goals` | 188 |
| H2 | `background_agents` (map of agent → flags) | 199 |
| H2 | `background_feeder` | 211 |
| H2 | `file_operations` | 220 |
| H2 | `file_editing` | 229 |
| H2 | `developer` | 244 |
| H2 | `shell_developer` | 258 |
| H2 | `feedback` | 293 |
| H2 | `content_safety` | 307 |
| H2 | `api_key.json` schema | 326 |
| H2 | Minimal valid config | 350 |
| H2 | Related code | 362 |
| H2 | Target repository indexes | 372 |

### `docs/THIRD_PARTY_NOTICES.md`

| Level | Section | Line |
|-------|---------|------|
| H1 | Third-Party Notices | 1 |
| H2 | mini-swe-agent (MIT) | 3 |

### `docs/TODO.md`

| Level | Section | Line |
|-------|---------|------|
| H1 | PrizmForge Roadmap / TODO | 1 |
| H2 | How to use this file | 13 |
| H2 | Section priorities | 21 |
| H2 | 0. Current state & next focus | 38 |
| H2 | 10. Soak4 — make the mini-swe mutation path produce a proposal | 60 |
| H3 | 10.0 What already works (do not reopen) | 73 |
| H3 | 10.1 Soak4 facts (DB + trajectories) | 85 |
| H3 | 10.2 Session loop (every turn) | 124 |
| H3 | 10.3 Harness bugs visible in the same dump | 145 |
| H3 | 10.4 Required mutation-path changes | 181 |
| H4 | 10.4.1 Evidence is in-process (no LLM) | 189 |
| H4 | 10.4.2 First model turn is inspect-the-target, not prove-cwd | 207 |
| H4 | 10.4.3 Developer model is not optional | 231 |
| H4 | 10.4.4 Proposal path (only after a dirty tree) | 258 |
| H3 | 10.5 Tests (fixtures from Soak4) | 285 |
| H3 | 10.6 Out of scope | 311 |
| H3 | 10.7 Acceptance (short soak, two endpoints, developer ≠ Enterprise chat) | 323 |
| H3 | 10.8 Soak16 remediation — edits succeed, no silent stall (shipped #124) | 342 |
| H2 | 8. Operator soak A-1 — ran (Soak4); remaining work is §10 | 390 |
| H3 | 8.1 Soak-watches (Soak4 already showed them — implement under §10) | 400 |
| H3 | 8.2 Out of scope (unchanged) | 407 |
| H3 | 8.3 Acceptance (same Windows box, same 8-hour unlock cadence) | 419 |
| H2 | 6. Latch / fallback — next-soak acceptance | 462 |
| H2 | 2. Shell developer — remaining protocol holes | 478 |
| H3 | 2.3 Remaining protocol nits (only if the next soak shows them) | 490 |
| H2 | 3. Feedback / developer dispatch — soak watches | 503 |
| H2 | 1. Cold-soak SQLite ingest — NUC timing (operator) | 522 |
| H2 | 5. Optional SQL hygiene | 541 |
| H2 | 7. Closed-loop and mini-swe residuals | 556 |
| H3 | 7.1 Git closed loop | 561 |
| H3 | 7.2 Mini-swe / shell port | 576 |
| H2 | 9. Annexes (parked — do not start) | 596 |
| H3 | 9.1 Federation | 598 |
| H3 | 9.2 Structural tech-debt | 602 |
| H3 | 9.3 Defaults (do not reopen without evidence) | 611 |
| H3 | 9.4 Not this pass | 619 |
| H3 | 9.5 False positives — no change | 627 |
| H2 | Implementation sequence (open work only) | 638 |

### `docs/UNATTENDED_CLOSED_LOOP_CAPABILITIES.md`

| Level | Section | Line |
|-------|---------|------|
| H1 | Unattended Closed-Loop Editing — Configuration & Operator Runbook | 1 |
| H2 | 1. What the capability is | 15 |
| H3 | What the closed loop does for you | 35 |
| H2 | 2. Before you start | 49 |
| H3 | 2.1 Target repo safety | 51 |
| H3 | 2.2 Prerequisites | 64 |
| H1 | Repo root of PrizmForge | 67 |
| H2 | 3. Configure `config.json` | 79 |
| H3 | 3.1 Project and mode | 84 |
| H3 | 3.2 `cli_mode.unattended` | 94 |
| H3 | 3.3 Developer implementation | 136 |
| H3 | 3.4 Closed-loop and load controls | 165 |
| H2 | 4. Launching a run | 188 |
| H1 | Optional: point the DB at the target (default is repo-root .PrizmForge/agents.db) | 191 |
| H1 | Real endpoints | 194 |
| H1 | Dry-run with a scripted mock LLM (no keys needed) | 197 |
| H1 | config.json: "llm": { "test_mode": true }   or: | 198 |
| H2 | 5. What the closed loop does at runtime | 218 |
| H3 | 5.1 Mutation path | 220 |
| H3 | 5.2 Git / hooks closed loop | 231 |
| H3 | 5.3 Feedback and prioritization | 252 |
| H3 | 5.4 Self-healing under endpoint trouble | 262 |
| H2 | 6. Observing a run | 273 |
| H3 | 6.1 stdout signals | 275 |
| H3 | 6.2 Runtime artifacts | 286 |
| H1 | edit_proposals, file_write_log, errors, | 292 |
| H1 | agent_feedback, endpoint_health, ...) | 293 |
| H3 | 6.3 Diagnostic queries (read-only, live DB or a copy) | 299 |
| H3 | 6.4 Semi-attended commands | 317 |
| H2 | 7. Stopping, resuming, undo, rollback | 325 |
| H2 | 8. Troubleshooting quick reference | 337 |
| H2 | 9. Related documents | 351 |

### `docs/architecture.md`

| Level | Section | Line |
|-------|---------|------|
| H1 | PrizmForge Architecture | 1 |
| H2 | Table of Contents | 7 |
| H3 | System Overview | 28 |
| H4 | High-Level Architecture | 42 |
| H4 | Key Design Principles | 95 |
| H4 | Data Flow | 116 |
| H3 | Agent Architecture | 134 |
| H4 | Agent Categories | 136 |
| H4 | Sequential Agents (Governed Loop) | 144 |
| H4 | Background Agents | 158 |
| H3 | Governed File Editing System | 170 |
| H4 | Overview | 174 |
| H4 | Key Technical Components | 190 |
| H4 | Line-Level Storage | 201 |
| H4 | Optimistic Concurrency & Safety | 211 |
| H4 | File Context Delivery | 217 |
| H3 | Database Schema | 225 |
| H4 | Governed Editing Tables | 235 |
| H4 | Core System Tables | 321 |
| H4 | Important Indexes | 385 |
| H3 | Task Execution Flow | 402 |
| H4 | High-Level Flow | 406 |
| H4 | Iteration Behavior | 439 |
| H1 | Final validation before completion | 458 |
| H3 | Multi-Endpoint System | 464 |
| H4 | Components | 468 |
| H4 | Health Status Values | 475 |
| H4 | Fallback Logic | 485 |
| H4 | Configuration Example | 504 |
| H3 | Background Agent System | 520 |
| H4 | Purpose | 524 |
| H4 | Enable gate | 532 |
| H4 | Architecture | 540 |
| H4 | Worker Flow | 564 |
| H4 | Integration with Governed Editing | 575 |
| H4 | Explicit Triggering | 581 |
| H4 | Supported Background Agents | 588 |
| H3 | File Operations | 600 |
| H4 | Dual Storage Model | 604 |
| H4 | File Synchronization | 613 |
| H4 | Key Functions | 623 |
| H4 | Token Estimation | 630 |
| H4 | File Change Events | 634 |
| H3 | Context Archival | 640 |
| H4 | Scope | 644 |
| H4 | Archival Process | 656 |
| H4 | Archive Record Structure | 670 |
| H4 | Context Restoration | 683 |
| H4 | Design Goal | 687 |
| H3 | Message Bus | 691 |
| H4 | Purpose | 695 |
| H4 | Table Structure | 703 |
| H4 | Priority System | 718 |
| H4 | Current Usage Patterns | 731 |
| H3 | Rate Limiting | 743 |
| H4 | Implementation | 747 |
| H1 | Uses endpoint-specific limit when available | 764 |
| H4 | Integration Points | 768 |
| H4 | Behavior | 774 |
| H3 | Token Budget | 780 |
| H4 | Purpose | 784 |
| H4 | Token Estimation Strategy | 790 |
| H4 | Implementation | 800 |
| H1 | Records usage and persists to token_log | 810 |
| H1 | Checks against rolling window | 813 |
| H4 | Integration | 818 |
| H3 | Resource Controller | 826 |
| H4 | Core Responsibilities | 830 |
| H4 | Throttling Strategy | 839 |
| H4 | Key Features | 850 |
| H4 | Integration Points | 857 |
| H3 | Error Handling & Observability | 866 |
| H4 | Centralized Error Logging | 870 |
| H4 | Severity / level usage | 889 |
| H4 | Usage in Governed Editing | 898 |
| H4 | Observability Benefits | 907 |
| H3 | Performance Considerations | 916 |
| H4 | Database Optimization | 920 |
| H4 | Token Estimation Strategy | 924 |
| H4 | Context Management | 928 |
| H4 | Background Agent Efficiency | 936 |
| H4 | Governed Editing Performance | 945 |
| H3 | Security Considerations | 951 |
| H4 | API Key Management | 955 |
| H4 | Data Privacy | 963 |
| H4 | Database Contents | 970 |
| H4 | Network Security | 980 |
| H4 | Path containment and content safety | 986 |
| H4 | Autonomous Modification Risks | 992 |
| H4 | Operational Recommendations | 1003 |
| H3 | Unattended Closed-Loop Hardening | 1012 |

### `docs/mini_swe_agent.md`

| Level | Section | Line |
|-------|---------|------|
| H1 | Shell Developer (mini-swe-agent style) — Capability Runbook | 1 |
| H2 | 1. What it is | 14 |
| H2 | 2. Enabling and configuring | 37 |
| H3 | 2.1 Enable | 39 |
| H3 | 2.2 Recommended profile | 50 |
| H2 | 3. How a session runs | 83 |
| H2 | 4. Safety notes | 114 |
| H2 | 5. Audit artifacts | 130 |
| H2 | 6. Rollback | 140 |
| H2 | 7. Troubleshooting | 152 |
| H2 | 8. History | 164 |

### `docs/soak_runbook.md`

| Level | Section | Line |
|-------|---------|------|
| H1 | Soak Runbook — live self-edit analysis with `utils/soak-setup.sh` | 1 |
| H2 | 1. Layout | 15 |
| H2 | 2. Copy hygiene — what never crosses into a soak | 47 |
| H3 | Retention across rounds | 67 |
| H2 | 3. Requirements | 82 |
| H2 | 4. Usage | 90 |
| H2 | 5. Runtime expectations | 127 |
| H2 | 6. Full-cycle analysis | 146 |
| H2 | 7. Operations notes | 188 |

### `docs/troubleshooting.md`

| Level | Section | Line |
|-------|---------|------|
| H1 | PrizmForge Troubleshooting Guide | 1 |
| H2 | Table of Contents | 5 |
| H2 | Startup Issues | 19 |
| H3 | "config.json not found" | 21 |
| H1 | Should see: config.json, api_key.json, agent_prompts.json | 38 |
| H1 | Edit with your settings | 50 |
| H3 | "API key not configured" | 55 |
| H1 | Should show endpoint status | 86 |
| H3 | "Project directory not writable" | 91 |
| H1 | Should show write permissions (drwxr-xr-x or similar) | 108 |
| H2 | API and Endpoint Issues | 130 |
| H3 | "API KEY LOCKED OR INVALID" | 132 |
| H1 | Should show fallback endpoint available | 157 |
| H1 | After fixing the key | 163 |
| H3 | "No endpoints currently available" | 175 |
| H1 | Should return HTTP 200 or similar | 211 |
| H3 | "Model 'X' not found" | 226 |
| H1 | Shows all configured models | 243 |
| H3 | Rate Limiting (429 errors) | 270 |
| H1 | See how often rate limiting occurs | 300 |
| H3 | Token Budget Exceeded | 312 |
| H2 | File Operation Issues | 361 |
| H3 | "File not found" | 363 |
| H1 | Lists all indexed files | 385 |
| H3 | "Patch failed" | 406 |
| H1 | Look at the diff that was generated | 423 |
| H1 | Ensures database has latest file content | 429 |
| H1 | See recent modifications | 435 |
| H1 | Open file_modifications.csv to see what changed | 441 |
| H1 | Restore from backup if exists | 446 |
| H3 | "File manager not parsing" | 453 |
| H1 | Open in Excel, search for file_manager responses | 498 |
| H2 | Background Agent Issues | 503 |
| H3 | "Background agents not working" | 505 |
| H1 | Should show files | 543 |
| H1 | Should be > 0 | 555 |
| H3 | "Too many API calls from background agents" | 560 |
| H3 | "Background agents reviewing same files repeatedly" | 608 |
| H1 | See if file is being modified repeatedly | 650 |
| H2 | Database Issues | 655 |
| H3 | "Database locked" | 657 |
| H1 | Find processes using database | 673 |
| H1 | Kill if necessary | 676 |
| H1 | Exit cleanly | 682 |
| H1 | Restart | 685 |
| H1 | Should return: ok | 692 |
| H1 | Backup first! | 697 |
| H1 | Delete and re-initialize | 700 |
| H3 | "Database too large" | 708 |
| H1 | Backup first | 748 |
| H1 | Delete | 751 |
| H1 | Re-initialize | 754 |
| H3 | "Can't find .PrizmForge directory" | 761 |
| H1 | Shows hidden directories | 784 |
| H1 | Database is in project directory | 789 |
| H1 | Should see: agents.db, agents_exports/ | 805 |
| H2 | Performance Issues | 810 |
| H3 | "System very slow" | 812 |
| H3 | "High memory usage" | 874 |
| H1 | Limit files in context | 890 |
| H1 | After each major task | 903 |
| H2 | Configuration Issues | 919 |
| H3 | "Changes to config.json not taking effect" | 921 |
| H1 | Make sure editing correct file | 942 |
| H1 | Should output formatted JSON | 948 |
| H1 | If error, shows line number | 949 |
| H3 | "Invalid JSON in config" | 954 |
| H1 | Shows exact error location | 972 |
| H2 | Debugging Workflows | 998 |
| H3 | Debugging Task Failures | 1000 |
| H1 | Shows all prompts and responses | 1005 |
| H1 | Shows conversation flow | 1011 |
| H1 | Shows unaddressed issues | 1017 |
| H1 | Shows if endpoints available | 1023 |
| H1 | Shows endpoint switching | 1029 |
| H1 | Get CSV files for analysis | 1035 |
| H3 | Debugging Agent Not Responding | 1046 |
| H1 | Should show the model | 1065 |
| H1 | Check if endpoint available | 1071 |
| H3 | Debugging File Operations | 1087 |
| H1 | Should list the file | 1092 |
| H1 | Look at the input | 1117 |
| H3 | Debugging Endpoint Issues | 1127 |
| H1 | Lists all endpoints and models | 1132 |
| H1 | Shows availability | 1138 |
| H1 | Shows switching patterns | 1144 |
| H1 | Clears all cooldowns | 1169 |
| H2 | Common Error Messages | 1174 |
| H3 | "NoneType object has no attribute..." | 1176 |
| H3 | "list index out of range" | 1191 |
| H3 | "Connection timeout" | 1206 |
| H3 | "Permission denied" | 1221 |
| H2 | Getting More Help | 1236 |
| H3 | Export Diagnostic Data | 1238 |
| H1 | Export everything | 1241 |
| H1 | Export specific tables | 1244 |
| H3 | Check System Status | 1248 |
| H1 | Token usage | 1251 |
| H1 | Endpoint health | 1254 |
| H1 | Fallback statistics | 1257 |
| H1 | Review status | 1260 |
| H3 | Database Inspection | 1264 |
| H2 | Prevention Best Practices | 1290 |

### `file_editing/prizmforge_integration_documentation/README.md`

| Level | Section | Line |
|-------|---------|------|
| H1 | PrizmForge Integration Layer | 1 |
| H2 | Components | 7 |
| H2 | Philosophy | 16 |

### `file_editing/prizmforge_integration_documentation/prompts/developer_prompt_update.md`

| Level | Section | Line |
|-------|---------|------|
| H2 | Updated Developer Prompt Guidance (Schema-Aware) | 1 |
| H2 | Governed File Editing - Mandatory Rules | 6 |
| H3 | Required Output Structure | 11 |
| H3 | Important Schema & Field Requirements | 21 |
| H3 | Summary | 57 |

### `file_editing/prizmforge_integration_documentation/prompts/reviewer_prompt_update.md`

| Level | Section | Line |
|-------|---------|------|
| H1 | Reviewer Agent Prompt Update (Governed Path) | 1 |

### `file_editing/schema.md`

| Level | Section | Line |
|-------|---------|------|
| H1 | Governed File Editing Schema | 1 |

### `tests/LLM_CONTEXT.md`

| Level | Section | Line |
|-------|---------|------|
| H1 | PrizmForge Test Suite — LLM / Architectural Context | 1 |
| H2 | Purpose | 12 |
| H2 | Status — High-priority pure unit coverage (PR #67) | 23 |
| H2 | 7-Layer QA Architecture | 40 |
| H2 | Current State Audit & Gap Matrix | 54 |
| H3 | Gap / Remaining Work | 67 |
| H2 | Strategic Justification | 81 |
| H2 | Multi-Platform CI Notes | 94 |
| H2 | Guidance for Agents Extending the Suite | 118 |

### `tests/README.md`

| Level | Section | Line |
|-------|---------|------|
| H1 | PrizmForge Test Suite | 1 |
| H2 | Quick start | 8 |
| H1 | From repo root (prefer project .venv) | 11 |
| H1 | Preferred runners (resolve .venv automatically) | 14 |
| H1 | Direct pytest (markers only; no batch isolation matrix) | 19 |
| H2 | Markers (orthogonal axes) | 45 |
| H1 | Examples | 70 |
| H2 | Gates | 79 |
| H3 | MockLLM import sites | 99 |
| H2 | High-priority pure unit suite (PR #67) | 106 |
| H3 | Assertion strength (no hollow tests) | 131 |
| H2 | Production hardening scope | 143 |
| H2 | Philosophy (operational) | 149 |
| H2 | Mocking LLMs | 160 |
| H2 | Content safety (binary rejection) | 178 |
| H2 | Directory structure (high level) | 194 |
| H2 | Dependencies | 224 |
| H1 | optional: black>=24.4.2, isort>=7.0.0, ruff, mypy | 233 |
| H2 | Moving toward TDD (beyond unit tests and coverage) | 238 |
| H3 | What the current framework accomplishes | 243 |
| H3 | Process guidance | 255 |

