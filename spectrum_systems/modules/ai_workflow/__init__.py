"""
AI Workflow modules — spectrum_systems/modules/ai_workflow/

Sub-modules
-----------
context_assembly
    Builds and governs context bundles fed to every AI task.
multi_pass_reasoning
    Governed multi-pass reasoning chain engine.  Runs typed reasoning passes,
    validates intermediate outputs, enforces pass budgets and circuit breakers,
    and emits traceable pass-chain records.
"""
