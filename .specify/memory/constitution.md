<!--
SYNC IMPACT REPORT (scratch for human review; remove before committing)

Version change: unratified template -> 1.0.0 (initial ratification)
Project name: Movie Maker (from spec.txt)

Principles defined (user requested four; template's fifth slot dropped):
  I.   Code Quality (코드품질)
  II.  Test-First (테스트우선) - NON-NEGOTIABLE
  III. Accessibility (접근성)
  IV.  Performance (성능)

Modified principles: none (first ratification; all template placeholders replaced)
Added sections: Technical Constraints, Development Workflow
  (both inferred from spec.txt sections 1.3 and 2.1 and from the principles;
   the user did not request them, so cut them if unwanted)
Removed sections: none

Deferred TODOs: none
Assumptions to confirm:
  - RATIFICATION_DATE set to 2026-11-20 (date of first adoption).
  - Numeric budgets in Performance (300 ms p95, 10% regression gate) are proposed
    defaults, not measured values. Confirm against the first plan.md.
  - WCAG 2.2 Level AA is the accessibility target.
  - Ruff and mypy are the chosen lint and type tools for this Python project.
-->

# Movie Maker Constitution

## Core Principles

### I. Code Quality (코드품질)

Code MUST be readable, consistent, and easy to change. The system chains several models
and services, so inconsistent code makes failures hard to localize.

- All Python code MUST pass `ruff check` and `ruff format --check` before merge. A lint
  suppression MUST carry an inline comment that states why it is needed.
- New and changed code MUST have type annotations and MUST introduce no new `mypy` errors.
- A function MUST have one clear responsibility. A function longer than 50 lines or with
  cyclomatic complexity above 10 MUST be refactored or justified in review.
- Dead code, commented-out code, and unused dependencies MUST NOT be merged.
- Public functions and classes MUST have docstrings that state their purpose, inputs,
  return values, and the errors they raise.

### II. Test-First (테스트우선) - NON-NEGOTIABLE

Behavior MUST be specified by tests before it is implemented. The cycle is strict:

1. Write a test that describes the expected behavior.
2. Run it and confirm it fails for the expected reason.
3. Write the minimum implementation that makes it pass.
4. Refactor with the tests green.

- Each `VideoProvider` adapter MUST pass a shared contract test suite before merge.
- Every bug fix MUST include a regression test that fails before the fix and passes after.
- Unit tests MUST replace external services (video models, LLM APIs, TTS) with fakes.
  Tests that call a real engine are integration tests and MUST run separately from the
  unit suite.
- A PR that changes behavior without tests MUST NOT be merged. Documentation-only and
  configuration-only changes are exempt.

Rationale: generation runs are slow, costly, and non-deterministic, so regressions MUST be
caught at the contract level with fast tests.

### III. Accessibility (접근성)

User interfaces MUST be usable by people with visual, auditory, motor, and cognitive
disabilities. The target is WCAG 2.2 Level AA.

- Every interactive control MUST be fully operable by keyboard and MUST have an accessible
  name.
- Body text MUST have a contrast ratio of at least 4.5:1. Large text and UI component
  boundaries MUST have at least 3:1.
- Each uploaded or generated image MUST accept user-entered alt text.
- When a generated video contains narration, it MUST provide captions or subtitles.
- Error messages MUST describe the problem in text. Color MUST NOT be the only way to convey
  status.
- Every UI change MUST pass an automated accessibility scan and at least one manual pass
  using keyboard navigation and a screen reader before release.

Rationale: the inputs are text and photos, which are simple to make accessible when
accessibility is designed in from the start and expensive to retrofit later.

### IV. Performance (성능)

Performance MUST be budgeted, measured, and enforced. Budgets are proposed defaults and
MUST be confirmed against the first plan.md.

- Every plan.md MUST state the performance budgets for the paths it changes: request latency
  at p95, peak memory and VRAM, and generation time per second of output video.
- Non-generation API endpoints MUST respond within 300 ms at p95 under the documented
  baseline load.
- Video generation MUST run as an asynchronous job. The API MUST return a job ID immediately,
  and clients MUST receive state and progress updates. A request handler MUST NOT block on
  generation.
- Models MUST be loaded once and reused across jobs. Loading a model per request is
  prohibited.
- Intermediate artifacts (keyframes, shot clips) MUST follow a documented retention policy
  that bounds disk use.
- A change that exceeds its declared budget by more than 10% MUST NOT be merged until the
  overrun is justified in review.

Rationale: local GPU memory is scarce. The smallest recommended model needs 8 GB of VRAM
(spec.txt section 2.1), so unbounded resource use makes the system unusable.

## Technical Constraints

- Video engines MUST be selected through the `VideoProvider` abstraction and switched by
  environment variable only (spec.txt section 1.3). Application logic outside provider
  adapters MUST NOT depend on a specific engine.
- The default engine MUST be a local open-weight model. A model whose license restricts use
  in Korea MUST NOT be adopted as a default. Before any model is adopted, its license and
  current version MUST be re-verified.
- The server owns all generation. Clients MUST NOT contain model-specific logic.

## Development Workflow

- Feature work MUST follow this order: spec, plan (with the Constitution Check in the
  Governance section below), tasks, failing tests, implementation, review.
- Every PR MUST pass the automated lint, format, type-check, and unit-test steps before merge.
- UI-facing PRs MUST include the accessibility checklist (Principle III) and the performance
  budget check (Principle IV) in the review.

## Governance

This constitution supersedes all other practices, including the spec, plan, and task
documents. Where they conflict, this constitution wins.

- **Amendment procedure**: An amendment is proposed as a PR that changes this file. The PR
  MUST include the Sync Impact Report, a rationale, and a migration note for any in-progress
  feature it affects. It MUST be approved by at least one reviewer other than its author.
- **Versioning policy** (semantic versioning):
  - MAJOR: removing or redefining a principle so that previously compliant work becomes
    non-compliant.
  - MINOR: adding a principle or section, or materially expanding a requirement.
  - PATCH: clarifying wording, fixing typos, or making other non-semantic refinements.
- **Compliance review**: Every plan.md MUST include a Constitution Check that lists each
  principle and how the plan meets it. Reviewers MUST verify this before approving a PR.
  Any violation MUST be recorded as an exception in the plan's Complexity Tracking section,
  with a justification.

**Version**: 1.0.0 | **Ratified**: 2026-11-20 | **Last Amended**: 2026-11-20
