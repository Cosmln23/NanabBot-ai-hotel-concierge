## Agent Core (Stable)

This module contains the LLM logic + tools. Treat it as a "black box".

- Do not modify files in `app/agent/` without running the automated tests.
- The prompt and rules are calibrated to force the use of tools and avoid hallucinations.
- Task deduplication is controlled by the backend; each `create_staff_ticket` creates a new task.

If you need to change the behavior, first add a test (see `tests/test_golden_scenarios.py` recommended) and update the documentation.
