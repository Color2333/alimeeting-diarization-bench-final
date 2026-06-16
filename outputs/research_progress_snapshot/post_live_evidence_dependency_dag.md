# Post-Live Evidence Dependency DAG

- Runtime contract: `post_live_evidence_dependency_dag_no_live_calls`
- Status: `blocked_waiting_live_outputs`
- DAG nodes: `10`
- P0 / P1 nodes: `8` / `2`
- Blocked nodes: `10`
- Fallback-only nodes: `1`
- Label-only nodes: `1`
- Ready nodes: `0`
- Expected live calls: `382`
- Missing output surfaces: `3`
- Ready to score: `0`
- Scoring execution steps: `6`
- Metric contracts: `8`
- Schema contracts: `8`
- Scorecard rows: `9`
- Latency claim rows: `8`
- Ready to promote: `0`
- Traceability rows: `54`
- Live calls performed by builder: `0`
- No scoring commands executed: `True`
- No new metric claim: `True`

| # | Node | Priority | Stage | State | Depends on | Boundary |
|---:|---|---|---|---|---|---|
| 1 | `live_outputs_complete` | `P0` | `live_output_coverage` | `blocked_missing_output` | `root` | `no_metric_claim_until_live_outputs_complete` |
| 2 | `output_schema_clean` | `P0` | `schema_validation` | `blocked_waiting_live_outputs` | `live_outputs_complete` | `schema_gate_no_live_metric_claim` |
| 3 | `deepseek_resume_safety_score` | `P0` | `safety_scoring` | `blocked_missing_output` | `output_schema_clean` | `required_before_zero_harm_safety_claim` |
| 4 | `deepseek_split20_latency_score` | `P0` | `latency_comparison` | `blocked_waiting_safety_score` | `deepseek_resume_safety_score` | `required_before_full_surface_latency_claim` |
| 5 | `omni48_label_metrics` | `P1` | `label_metric_scoring` | `blocked_missing_output` | `output_schema_clean` | `label_only_no_timeline_writeback` |
| 6 | `qwen_backup_metrics` | `P1` | `fallback_metric_scoring` | `fallback_only_waiting_credentials` | `output_schema_clean` | `fallback_only_not_primary_claim` |
| 7 | `metric_extraction_complete` | `P0` | `metric_extraction` | `blocked_waiting_scoring_outputs` | `deepseek_resume_safety_score`, `deepseek_split20_latency_score`, `omni48_label_metrics`, `qwen_backup_metrics` | `metric_extraction_schema_no_live_metric_claim` |
| 8 | `latency_claim_matrix_update` | `P0` | `latency_claim_boundary` | `blocked_waiting_metric_extraction` | `metric_extraction_complete` | `latency_claim_matrix_no_new_metric_claim_until_promotion` |
| 9 | `promotion_gate_pass` | `P0` | `claim_promotion` | `blocked_waiting_traceability_and_promotion_inputs` | `latency_claim_matrix_update` | `promote_only_after_output_audit_scoring_slo_and_traceability_pass` |
| 10 | `report_ppt_refresh_validation` | `P0` | `report_ppt_validation` | `blocked_waiting_promotion_refresh` | `promotion_gate_pass` | `report_ppt_sync_required_before_claim_promotion` |

## Gates

### 1. live_outputs_complete

- Evidence artifacts: `outputs/research_progress_snapshot/live_output_audit.md`
- Success gate: `expected_live_calls == 382 and missing_output_surfaces == 0`

### 2. output_schema_clean

- Evidence artifacts: `outputs/research_progress_snapshot/live_output_schema_contract.md; outputs/research_progress_snapshot/live_output_audit.md`
- Success gate: `all live/scoring/promotion schema contracts parse with required fields present`

### 3. deepseek_resume_safety_score

- Evidence artifacts: `outputs/research_progress_snapshot/live_scoring_readiness.md; outputs/research_progress_snapshot/post_live_scoring_execution_plan.md`
- Success gate: `DeepSeek resume safety summary exists and harmful_accepts == 0`

### 4. deepseek_split20_latency_score

- Evidence artifacts: `outputs/research_progress_snapshot/post_live_scoring_execution_plan.md; outputs/research_progress_snapshot/post_live_latency_claim_matrix.md`
- Success gate: `full split20 comparison covers 104 parents / 147 planned calls`

### 5. omni48_label_metrics

- Evidence artifacts: `outputs/research_progress_snapshot/live_metric_extraction_contract.md; outputs/research_progress_snapshot/post_live_scoring_execution_plan.md`
- Success gate: `96 Omni48 label-only rows produce quality and latency summaries`

### 6. qwen_backup_metrics

- Evidence artifacts: `outputs/research_progress_snapshot/live_metric_extraction_contract.md; outputs/research_progress_snapshot/post_live_scoring_execution_plan.md`
- Success gate: `Qwen fallback safety/comparison summaries exist and remain marked fallback-only`

### 7. metric_extraction_complete

- Evidence artifacts: `outputs/research_progress_snapshot/live_metric_extraction_contract.md; outputs/research_progress_snapshot/post_live_acceptance_scorecard.md; outputs/research_progress_snapshot/post_live_scoring_output_audit.md`
- Success gate: `all 8 metric contracts are populated with post-live values or explicit fallback labels and scoring output audit is promotion-ready`

### 8. latency_claim_matrix_update

- Evidence artifacts: `outputs/research_progress_snapshot/post_live_latency_claim_matrix.md; outputs/research_progress_snapshot/post_live_acceptance_scorecard.md`
- Success gate: `latency matrix separates claim-now, promoted, blocked, label-only, and fallback-only rows`

### 9. promotion_gate_pass

- Evidence artifacts: `outputs/research_progress_snapshot/post_live_claim_promotion_gate.md; outputs/research_progress_snapshot/report_ppt_traceability.md`
- Success gate: `ready_to_promote_count only increases after output audit, scoring, SLO, and traceability pass`

### 10. report_ppt_refresh_validation

- Evidence artifacts: `outputs/research_progress_snapshot/latest_artifact_validation.md; outputs/research_progress_snapshot/report_ppt_traceability.md; docs/reports/2026-06-03-realtime-dual-agent-roadmap.md; ../研究进展汇报.pptx`
- Success gate: `refresh pass; validator failed_checks empty; report/PPT traceability fully covered`

## Reading

- This DAG fixes the dependency order from live output coverage through schema, scoring, metric extraction, latency claim boundary, promotion, and report/PPT validation.
- DeepSeek safety remains upstream of full split20 latency promotion; Omni48 remains label-only and Qwen remains fallback-only.
- The builder performs no live/API/model/scoring calls, writes no secret values, and makes no new metric claim.
