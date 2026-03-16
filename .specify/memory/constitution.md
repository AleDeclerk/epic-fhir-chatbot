<!--
Sync Impact Report
==================
- Version change: N/A → 1.0.0 (initial ratification)
- Principles added:
  1. Layered Separation & Decoupling
  2. Security-First & Graceful Failure
  3. Test-Driven Development (Non-Negotiable)
- Sections added:
  - Code Conventions & Standards
  - Development Workflow
  - Governance
- Templates requiring updates:
  - .specify/templates/plan-template.md — no update needed (Constitution Check section is generic)
  - .specify/templates/spec-template.md — no update needed (user stories structure compatible)
  - .specify/templates/tasks-template.md — no update needed (TDD workflow already supported)
- Follow-up TODOs: none
-->

# Epic FHIR Chatbot Constitution

## Core Principles

### I. Layered Separation & Decoupling

The system MUST enforce strict separation between the AI agent layer
and the FHIR data access layer. Specifically:

- The Claude agent MUST NOT call the Epic FHIR API directly.
  All FHIR operations MUST pass through the `fhir_client.py` adapter.
- Each chatbot capability MUST be defined as a tool with a JSON schema
  contract. The agent decides which tool to invoke; the tool executes
  the FHIR operation.
- The `fhir_client.py` module MUST be usable independently of the
  Claude agent (no agent imports, no agent-specific logic).
- The backend MUST be stateless for the MVP: each request from the
  frontend includes the full conversation history. No server-side
  session storage.
- The frontend MUST NOT access Epic FHIR directly; all FHIR
  communication goes through the backend API.

**Rationale**: Decoupling the AI orchestration from the healthcare
data layer enables independent testing, swappable components, and
clear security boundaries around PHI access.

### II. Security-First & Graceful Failure

All code MUST prioritize security and user-facing resilience:

- Credentials (OAuth client secrets, API keys) MUST NEVER be
  hardcoded. All secrets MUST live in `.env` and load via
  `config.py` using Pydantic Settings.
- OAuth tokens MUST be held in memory only and MUST NEVER be logged.
- User inputs MUST be sanitized before reaching the Claude agent.
- Backend endpoints MUST enforce rate limiting.
- When Epic FHIR returns an error or Claude cannot resolve intent,
  the chatbot MUST respond with a friendly, non-technical message.
  Raw stack traces or API errors MUST NEVER be shown to patients.
- `.env` and any file containing secrets MUST be listed in
  `.gitignore`.

**Rationale**: This system handles patient-facing healthcare data.
Security failures have regulatory and trust consequences. Graceful
degradation ensures patients are never confused by technical errors.

### III. Test-Driven Development (Non-Negotiable)

All feature code MUST follow strict TDD:

- Tests MUST be written before the implementation they verify.
- The Red-Green-Refactor cycle MUST be enforced:
  1. Write a failing test (Red).
  2. Write the minimal code to make it pass (Green).
  3. Refactor while keeping tests green (Refactor).
- Unit tests for `fhir_client.py` MUST mock Epic FHIR responses.
- Integration tests for agent tools MUST verify end-to-end tool
  invocation behavior.
- Each module MUST be tested before being integrated with other
  modules.
- Tests MUST use `pytest` as the test runner.

**Rationale**: TDD catches integration issues early, documents
expected behavior, and prevents regressions in a system where
incorrect responses could affect patient care decisions.

## Code Conventions & Standards

### Python (backend)

- Type hints MUST be present on all function signatures.
- All HTTP calls MUST use `async`/`await` (via `httpx`).
- Docstrings MUST be present on all modules and public functions.
- Naming: `snake_case` for variables/functions, `PascalCase` for
  classes, `UPPER_SNAKE_CASE` for constants.
- Imports MUST be ordered: stdlib, third-party, local.
- Maximum line length: 88 characters (black-compatible).
- Logging MUST use the `logging` module. `print()` is forbidden.

### JavaScript / React (frontend)

- Functional components with hooks only.
- `camelCase` for variables/functions, `PascalCase` for components.

### File Organization

- One module per responsibility (no monolithic files).
- No module SHOULD exceed 300 lines.

## Development Workflow

- Build order: FHIR client -> Tools -> Agent -> API -> Frontend.
- Commits MUST be atomic: one commit per completed functionality.
- Branch naming: `feature/<feature-name>`.
- Each module MUST pass its tests before integration with the next
  layer.

### Build-From-Bottom-Up Sequence

1. `backend/app/config.py` — environment and settings
2. `backend/app/auth.py` — OAuth 2.0 / SMART on FHIR
3. `backend/app/fhir_client.py` — Epic FHIR adapter
4. `backend/app/tools.py` — tool definitions and handlers
5. `backend/app/agent.py` — Claude agent orchestrator
6. `backend/app/routes/chat.py` — API endpoint
7. `backend/app/main.py` — FastAPI app assembly
8. `frontend/index.html` — React SPA

## Governance

- This constitution supersedes all other project practices and
  conventions. In case of conflict, the constitution wins.
- Amendments require:
  1. A written proposal describing the change and rationale.
  2. Update to this document with version bump.
  3. A migration plan if the change affects existing code.
- Version follows semantic versioning:
  - MAJOR: Principle removal or backward-incompatible redefinition.
  - MINOR: New principle/section added or materially expanded.
  - PATCH: Clarifications, typos, non-semantic refinements.
- Compliance review: every PR MUST verify adherence to the three
  core principles before merge.

**Version**: 1.0.0 | **Ratified**: 2026-03-16 | **Last Amended**: 2026-03-16
