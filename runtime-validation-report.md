# Runtime Validation Report

**Generated:** 2026-10-06  
**Target:** AI-Powered Employee Management System with Virtual Voice Assistant

## Summary

| Step | Status | Exit code | Details |
|---|---|---:|---|
| Startup | PASS | 0 | Django migrations applied to an isolated SQLite database; local server started and employee login reached the dashboard. |
| Integration tests | PASS | 0 | 73 Django tests passed; 0 failures. |
| Browser smoke flows | PASS | 0 | Login/dashboard and assistant text-question flows worked in Chromium. Simulated speech recognition submitted a transcript and received the expected response. |
| Voice fallback | PASS | 0 | Simulated `not-allowed` recognition error displayed manual-typing guidance and reset the listening UI; unsupported-API mode retained working text input. |
| Physical microphone | BLOCKED | n/a | Native Chromium microphone activation returned “Voice recognition error. Please try again.” Actual microphone capture/permission could not be verified in this environment. |

**Overall:** NEEDS_SIGNOFF — the application checks and regression suite passed, but the browser smoke test did not exercise all 167 manual scenarios. The companion Excel report marks only directly evidenced cases as Pass.

## Environment

- Docker: unavailable; the Docker executable was not found.
- Node.js: available, v24.18.0.
- Playwright: available through `npx`, v1.63.0.
- Chromium: installed for browser validation.
- Database: isolated SQLite database, removed after the browser run.

## Test Evidence

- Command: `.venv\Scripts\python.exe manage.py test --verbosity 1`
- Result: 64 passed, 0 failed; exit code 0.
- Django system check: `manage.py check` — no issues.
- Model/migration consistency: `manage.py makemigrations --check --dry-run` — no changes detected.
- `manage.py showmigrations` reports unapplied migrations in the existing local database: `assistant_app.0001_initial`, `organization.0001_initial`, and `tasks.0003_task_project`. These were not applied to the user's local database. Tests use Django's isolated test database, where migrations were applied.
- JavaScript syntax: `node --check static/js/app.js` — passed.
- Test files: `qa_validation/test_authentication.py`, `test_task_flows.py`, `test_leave_performance.py`, `test_reports.py`, `test_organization_workflows.py`, `test_ai_actions.py`, `test_collaboration_workflows.py`, and `test_full_coverage.py`.
- Browser smoke: authenticated employee login → dashboard; assistant task lookup returned “You currently have no pending tasks.” Simulated recognized speech reached the same assistant flow, and simulated permission denial provided a text-input fallback.

## Coverage Limits

- Excel case status after this validation pass: 71 Pass, 18 Blocked, 78 Not Run, 0 Fail. Pass statuses are backed by specific test assertions or browser checks.
- Blocked cases include unsupported workflows (such as multi-assignee tasks, sprint rollover, Kanban WIP limits, calendar integrations, and automatic notifications) and microphone tests that could not be completed in the browser environment.
- Not Run means there was no direct assertion or browser evidence for that specific scenario; it does not mean the case passed.
