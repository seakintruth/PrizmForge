Generated: 2026-09-07T12:34:00Z

# Production code index

Root: `C:\git\home\user\jeremy.gerdes\github\PrizmForge-Soak\Soak5-target\PrizmForge`

Standalone index for context (no full source dump).

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

