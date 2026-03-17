# Ecosystem Dependency Graph Summary

## Systems
- comment-resolution-engine (operational_engine, loop=document_production, maturity=6) consumes: comment_resolution_matrix, reviewer_comment_set, working_paper_input; emits: comment_resolution_matrix, comment_resolution_matrix_spreadsheet_contract; contracts: comment_resolution_matrix, comment_resolution_matrix_spreadsheet_contract, provenance_record, reviewer_comment_set
- docx-comment-injection-engine (operational_engine, loop=document_production, maturity=6) consumes: comment_resolution_matrix_spreadsheet_contract, working_paper_input; emits: pdf_anchored_docx_comment_injection_contract, updated_working_paper_docx; contracts: comment_resolution_matrix_spreadsheet_contract, pdf_anchored_docx_comment_injection_contract, provenance_record
- meeting-minutes-engine (operational_engine, loop=coordination, maturity=5) consumes: meeting_agenda_contract, transcript; emits: meeting_minutes, meeting_minutes_record; contracts: meeting_agenda_contract, meeting_minutes, provenance_record
- spectrum-data-lake (data_lake, loop=cross_loop, maturity=5) consumes: meeting_minutes_record, provenance_record, reviewer_comment_set, working_paper_input; emits: external_artifact_manifest, provenance_record; contracts: external_artifact_manifest, provenance_record, standards_manifest
- spectrum-pipeline-engine (orchestration, loop=cross_loop, maturity=7) consumes: pipeline_run_manifest, provenance_record, standards_manifest; emits: pipeline_run_manifest, study_readiness_assessment; contracts: external_artifact_manifest, provenance_record, standards_manifest, study_readiness_assessment
- spectrum-program-advisor (advisory, loop=cross_loop, maturity=9) consumes: pipeline_run_manifest, provenance_record, study_readiness_assessment; emits: next_best_action_memo, program_brief, risk_register; contracts: next_best_action_memo, program_brief, provenance_record, risk_register, study_readiness_assessment
- spectrum-systems (governance, loop=governance, maturity=4) consumes: provenance_record, standards_manifest; emits: governance_guidance, standards_manifest; contracts: standards_manifest
- system-factory (factory, loop=governance, maturity=3) consumes: governance_templates, standards_manifest; emits: scaffolded_repository_manifest, standards_manifest; contracts: provenance_record, standards_manifest
- working-paper-review-engine (operational_engine, loop=document_production, maturity=6) consumes: review_guidance, working_paper_input; emits: reviewer_comment_set; contracts: provenance_record, reviewer_comment_set, working_paper_input

## Artifacts
- adjudicated_matrix [review] producers: —; consumers: —; Approved adjudication state for reviewer comments.
- assumption_register [work] producers: —; consumers: —; Governed artifact for contract `assumption_register`.
- comment_resolution_matrix [review] producers: comment-resolution-engine; consumers: comment-resolution-engine; Governed artifact for contract `comment_resolution_matrix`.
- comment_resolution_matrix_spreadsheet [review] producers: —; consumers: —; Spreadsheet representation of the governed comment resolution matrix.
- comment_resolution_matrix_spreadsheet_contract [review] producers: comment-resolution-engine; consumers: docx-comment-injection-engine; Governed artifact for contract `comment_resolution_matrix_spreadsheet_contract`.
- coordination_loop [coordination] producers: —; consumers: —; Marker node for systems participating in the coordination loop.
- cross_loop [coordination] producers: —; consumers: —; Marker node for systems that orchestrate or advise across loops.
- decision_log [coordination] producers: —; consumers: —; Governed artifact for contract `decision_log`.
- document_production_loop [work] producers: —; consumers: —; Marker node for systems participating in the document production loop.
- evaluation_manifest [coordination] producers: —; consumers: —; Governed artifact for contract `evaluation_manifest`.
- external_artifact_manifest [coordination] producers: spectrum-data-lake; consumers: —; Governed artifact for contract `external_artifact_manifest`.
- governance_guidance [coordination] producers: spectrum-systems; consumers: —; Narrative governance instructions emitted by spectrum-systems.
- governance_loop [coordination] producers: —; consumers: —; Marker node for control-plane and governance functions.
- governance_templates [coordination] producers: —; consumers: system-factory; Template files used by system-factory when scaffolding governed repos.
- meeting_agenda_contract [coordination] producers: —; consumers: meeting-minutes-engine; Governed artifact for contract `meeting_agenda_contract`.
- meeting_minutes [coordination] producers: meeting-minutes-engine; consumers: —; Governed artifact for contract `meeting_minutes`.
- meeting_minutes_docx [coordination] producers: —; consumers: —; Rendered DOCX minutes distributed to participants.
- meeting_minutes_record [coordination] producers: meeting-minutes-engine; consumers: spectrum-data-lake; Governed artifact for contract `meeting_minutes_record`.
- milestone_plan [coordination] producers: —; consumers: —; Governed artifact for contract `milestone_plan`.
- next_best_action_memo [coordination] producers: spectrum-program-advisor; consumers: —; Governed artifact for contract `next_best_action_memo`.
- pdf_anchored_docx_comment_injection_contract [review] producers: docx-comment-injection-engine; consumers: —; Governed artifact for contract `pdf_anchored_docx_comment_injection_contract`.
- pipeline_run_manifest [coordination] producers: spectrum-pipeline-engine; consumers: spectrum-pipeline-engine, spectrum-program-advisor; Structured manifest describing a pipeline run configuration and outputs.
- program_brief [coordination] producers: spectrum-program-advisor; consumers: —; Governed artifact for contract `program_brief`.
- provenance_record [coordination] producers: spectrum-data-lake; consumers: spectrum-data-lake, spectrum-pipeline-engine, spectrum-program-advisor, spectrum-systems; Governed artifact for contract `provenance_record`.
- review_guidance [review] producers: —; consumers: working-paper-review-engine; Guidance documents steering reviewer expectations and rubric.
- reviewer_comment_set [review] producers: working-paper-review-engine; consumers: comment-resolution-engine, spectrum-data-lake; Governed artifact for contract `reviewer_comment_set`.
- risk_register [coordination] producers: spectrum-program-advisor; consumers: —; Governed artifact for contract `risk_register`.
- scaffolded_repository_manifest [coordination] producers: system-factory; consumers: —; Manifest describing the generated repository from system-factory.
- slide_deck [work] producers: —; consumers: —; Governed artifact for contract `slide_deck`.
- slide_intelligence_packet [work] producers: —; consumers: —; Governed artifact for contract `slide_intelligence_packet`.
- standards_manifest [coordination] producers: spectrum-systems, system-factory; consumers: spectrum-pipeline-engine, spectrum-systems, system-factory; Governed artifact for contract `standards_manifest`.
- study_readiness_assessment [coordination] producers: spectrum-pipeline-engine; consumers: spectrum-program-advisor; Governed artifact for contract `study_readiness_assessment`.
- transcript [coordination] producers: —; consumers: meeting-minutes-engine; Raw meeting transcript captured before governance processing.
- updated_working_paper [work] producers: —; consumers: —; Working paper revision after adjudication or injection.
- updated_working_paper_docx [work] producers: docx-comment-injection-engine; consumers: —; DOCX export of the updated working paper.
- working_paper_input [work] producers: —; consumers: comment-resolution-engine, docx-comment-injection-engine, spectrum-data-lake, working-paper-review-engine; Governed artifact for contract `working_paper_input`.

## Contracts
- assumption_register [work] intended consumers: spectrum-pipeline-engine, spectrum-program-advisor; artifacts: assumption_register
- comment_resolution_matrix [review] intended consumers: comment-resolution-engine, system-factory, working-paper-review-engine; artifacts: comment_resolution_matrix
- comment_resolution_matrix_spreadsheet_contract [review] intended consumers: comment-resolution-engine, spectrum-pipeline-engine, system-factory; artifacts: comment_resolution_matrix_spreadsheet_contract
- decision_log [coordination] intended consumers: spectrum-pipeline-engine, spectrum-program-advisor; artifacts: decision_log
- evaluation_manifest [coordination] intended consumers: spectrum-pipeline-engine, spectrum-program-advisor, spectrum-systems; artifacts: evaluation_manifest
- external_artifact_manifest [coordination] intended consumers: comment-resolution-engine, spectrum-pipeline-engine, study-artifact-generator; artifacts: external_artifact_manifest
- meeting_agenda_contract [coordination] intended consumers: comment-resolution-engine, meeting-minutes-engine, spectrum-pipeline-engine, system-factory; artifacts: meeting_agenda_contract
- meeting_minutes [coordination] intended consumers: meeting-minutes-engine, spectrum-pipeline-engine, spectrum-program-advisor, system-factory; artifacts: meeting_minutes
- meeting_minutes_record [coordination] intended consumers: meeting-minutes-engine, spectrum-program-advisor; artifacts: meeting_minutes_record
- milestone_plan [coordination] intended consumers: spectrum-pipeline-engine, spectrum-program-advisor; artifacts: milestone_plan
- next_best_action_memo [coordination] intended consumers: spectrum-pipeline-engine, spectrum-program-advisor; artifacts: next_best_action_memo
- pdf_anchored_docx_comment_injection_contract [review] intended consumers: comment-resolution-engine, docx-comment-injection-engine, system-factory, working-paper-review-engine; artifacts: pdf_anchored_docx_comment_injection_contract
- program_brief [coordination] intended consumers: spectrum-pipeline-engine, spectrum-program-advisor; artifacts: program_brief
- provenance_record [coordination] intended consumers: comment-resolution-engine, system-factory, working-paper-review-engine; artifacts: provenance_record
- reviewer_comment_set [review] intended consumers: comment-resolution-engine, system-factory, working-paper-review-engine; artifacts: reviewer_comment_set
- risk_register [coordination] intended consumers: spectrum-pipeline-engine, spectrum-program-advisor; artifacts: risk_register
- slide_deck [work] intended consumers: slide-intelligence-engine, spectrum-pipeline-engine, working-paper-review-engine; artifacts: slide_deck
- slide_intelligence_packet [work] intended consumers: assumptions-registry-engine, knowledge-graph-engine, spectrum-program-advisor, working-paper-review-engine; artifacts: slide_intelligence_packet
- standards_manifest [coordination] intended consumers: downstream schema loaders, system-factory; artifacts: standards_manifest
- study_readiness_assessment [coordination] intended consumers: spectrum-pipeline-engine, spectrum-program-advisor; artifacts: study_readiness_assessment
- working_paper_input [work] intended consumers: system-factory, working-paper-review-engine; artifacts: working_paper_input

## Loop Participation
- coordination_loop: meeting-minutes-engine
- cross_loop: spectrum-data-lake, spectrum-pipeline-engine, spectrum-program-advisor
- document_production_loop: comment-resolution-engine, docx-comment-injection-engine, working-paper-review-engine
- governance_loop: spectrum-systems, system-factory

Generated via scripts/build_dependency_graph.py from registry and standards sources.