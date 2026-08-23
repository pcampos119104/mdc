---
name: spec-driven-development
description: Use for medium or large features, cross-module changes, significant refactors, architecture changes, external integrations, regression-prone work, ambiguous requirements, or work requiring technical decisions before implementation.
compatibility: opencode
metadata:
  project: mdc
  process: spec-driven-development
---

# Spec-Driven Development

Use this skill to coordinate medium and large engineering tasks before implementation. It defines a process for discovering the current system, specifying the required outcome, obtaining human approval, planning the implementation, executing it, and verifying the result.

Follow `AGENTS.md` and all other active project instructions throughout the process. When a specialized skill applies, use it for framework-specific guidance while this skill remains responsible for process and scope control.

## Core Principle

A specification and an implementation plan are different artifacts:

- The specification defines **what must be true** after the change.
- The implementation plan defines **how the approved outcome will be produced**.
- Do not choose implementation details merely to make an incomplete requirement appear resolved.
- Do not start implementation before the required review checkpoints.
- Tests and verification are part of the specification, not optional cleanup after coding.

## When To Use

Use this skill when a task includes one or more of these characteristics:

- A new feature affects multiple files, modules, apps, or services.
- A significant refactor changes behavior, boundaries, or several call sites.
- An architectural or data-model decision is required.
- An external service or API must be integrated.
- The change has meaningful regression, migration, security, privacy, or operational risk.
- Requirements are incomplete, ambiguous, or internally inconsistent.
- Product or business-rule decisions must be made before writing code.
- Multiple technically valid approaches have materially different trade-offs.

Do not force the full process onto trivial, localized, low-risk work such as a typo, a narrowly defined one-line fix, or a mechanical change with an obvious verification method.

## Proportional Process

Classify the task before choosing the process depth. Increase the level when uncertainty or risk is higher, even if the diff is expected to be small.

### Small Task

Perform a brief, focused analysis and implement directly when the scope, behavior, and verification are obvious. Still follow project instructions and verify the result.

### Medium Task

Perform focused discovery and produce a compact specification containing at least:

- Goal
- Scope
- Constraints
- Acceptance criteria
- Verification

Stop for human review of the specification. After approval, provide a compact implementation plan and wait for plan approval unless the user explicitly asks to continue without another checkpoint.

### Large Task

Use the complete process:

1. Discovery
2. Specification
3. Human review
4. Implementation plan
5. Plan review
6. Implementation
7. Verification
8. Final report

Suggest a dedicated branch or `git worktree` when the work is long-running, high-risk, likely to conflict with parallel work, or benefits from isolated experiments. Never create one without the user's approval.

## Evidence Discipline

Keep these categories distinct in specifications and review discussions:

- **Observed fact:** behavior, structure, or convention verified in the repository or an authoritative source.
- **User requirement:** behavior explicitly requested or approved by the user.
- **Assumption:** an unverified belief used to reason about the task. Assumptions that affect behavior require confirmation.
- **Recommendation:** a proposed choice with its rationale and trade-offs.

Never present an assumption or recommendation as an observed fact. Never silently invent a product rule to remove ambiguity.

## Phase 1: Discovery

Before proposing an implementation:

1. Inspect only the parts of the repository relevant to the task.
2. Identify the current user-visible and system behavior.
3. Identify existing project patterns and conventions.
4. Locate relevant models, migrations, forms, views, URLs, templates, tests, services, selectors, APIs, settings, jobs, static assets, deployment files, or documentation as applicable.
5. Trace important callers, dependencies, data flows, and integration boundaries.
6. Identify invariants and compatibility requirements that must be preserved.
7. Identify likely indirect effects, including permissions, validation, database state, templates, tests, deployment, and operations.
8. Record uncertainties instead of resolving them through guesses.

Discovery is read-only:

- Do not modify source code, configuration, migrations, tests, generated files, or documentation.
- Do not run commands that mutate application or repository state.
- Do not load the entire repository into context without a concrete need.
- Start from direct references and expand exploration only when findings justify it.

Report the important discovery results in the specification. Do not turn raw file listings into a substitute for understanding behavior.

## Phase 2: Specification

Produce the specification before an implementation plan. Unless the project has an approved spec location, present it in the conversation rather than creating a new repository file automatically.

Use the following structure for a large task. A medium task may use the reduced structure defined above.

### Context

Describe the current behavior and architecture relevant to the request. Include only verified details needed to understand the change.

### Goal

State the outcome the change must produce. Describe the resulting capability or behavior, not the intended code structure.

### Non-goals

Explicitly list adjacent work that is outside the task. Use non-goals to prevent accidental expansion and opportunistic refactors.

### Scope

Identify the system areas likely to be affected. This may include apps, modules, interfaces, data, users, operations, or integrations. File paths may be included when discovery supports them, but avoid pretending the implementation design is already fixed.

### Functional Requirements

List observable behaviors that must exist after implementation. Assign stable identifiers such as `FR-1`, `FR-2`, and `FR-3` when they help connect requirements to acceptance criteria and tests.

Requirements must state:

- The actor or initiating condition when relevant.
- The action or event.
- The expected system behavior or state change.
- Authorization, validation, error, and persistence behavior when relevant.

### Constraints

Record applicable technical and business restrictions, including:

- Rules from `AGENTS.md` and other active project instructions.
- Existing compatibility and invariants.
- Framework and dependency constraints.
- Security, privacy, accessibility, performance, migration, or deployment constraints.
- Explicit deadlines or rollout requirements supplied by the user.

Do not create constraints that were not observed, required, or approved.

### Edge Cases

Identify boundary conditions, invalid inputs, expected failures, concurrency concerns, partial failures, empty states, permission differences, existing data, and behavior that must remain unchanged. Include only cases relevant to the task and its risk.

### Acceptance Criteria

Define objective, observable, and verifiable criteria. Assign identifiers such as `AC-1`, `AC-2`, and `AC-3` for non-trivial work.

Good acceptance criteria specify a concrete input or scenario and an observable result, for example:

- A named endpoint returns the expected status, template, redirect, or payload for a defined request.
- A defined action creates or updates specific persisted data.
- An invalid scenario displays a defined validation error and does not change persisted data.
- An unauthorized user receives the specified access-control behavior.
- Existing behavior identified as an invariant remains covered and unchanged.
- All existing tests and newly required tests pass.

Do not use vague criteria such as:

- "Works correctly."
- "The code is good."
- "The interface is better."
- "Errors are handled."

### Verification

Define how each acceptance criterion will be validated. Use the narrowest effective checks during development and the project-standard comprehensive checks before completion.

Consider, when applicable:

- Unit tests.
- Integration tests.
- Regression tests.
- `pytest` or the project's `just test` command.
- Ruff or other configured linting and formatting checks.
- Configured type checking.
- `python manage.py check`.
- Migration checks and database behavior.
- Frontend builds and browser checks on desktop and mobile.
- Accessibility or interaction checks.
- External-service failure simulations.
- Domain-specific data and permission checks.
- Inspection of the complete diff.

Map important acceptance criteria to a test, command, or manual check. If a criterion cannot be verified in the current environment, state the limitation and the required external verification.

### Risks

List known ways the change could fail or regress existing behavior. Include impact and mitigation when known. Do not mix confirmed risks with unanswered requirements.

### Open Questions

List decisions that require human input, including unresolved business rules, user experience choices, rollout decisions, and trade-offs with no clearly mandated answer.

Recommendations are allowed, but each recommendation must:

- Be labeled as a recommendation.
- Explain the relevant trade-offs.
- Avoid silently deciding a product or business rule.

### Assumptions

List any remaining assumptions separately. An assumption that changes functional behavior, data meaning, access control, or scope must be confirmed before implementation.

## Phase 3: Human Review Checkpoint

After presenting the specification:

- Stop.
- Do not produce implementation code.
- Do not modify files.
- Highlight ambiguities, assumptions, recommendations, and decisions requiring approval.
- Ask the user to approve the specification or request changes.

Approval must be explicit. If the user changes a requirement, update the specification and present the affected parts for review again. Do not treat silence or an unrelated response as approval.

## Phase 4: Implementation Plan

Only after specification approval, produce a plan that explains how to implement the approved outcome. Do not implement during this phase.

The plan must:

1. Divide work into small, ordered, coherent steps.
2. Identify components and likely files affected by each step.
3. Explain dependencies between steps.
4. Include required tests, migrations, fixtures, documentation, configuration, or rollout work.
5. State when focused and comprehensive verification will run.
6. Preserve approved non-goals and avoid unrelated cleanup.
7. Call out irreversible, risky, or externally coordinated operations.

The plan may choose technical details that are consistent with the approved specification and project conventions. If a technical choice changes the approved behavior or scope, return to the specification instead.

## Phase 5: Plan Review Checkpoint

Present the implementation plan and wait for approval before beginning relevant changes.

The agent may continue without another checkpoint only when the user explicitly asks to proceed after presenting the plan or has explicitly requested that the plan-review checkpoint be skipped. Specification approval is still required for medium and large tasks using this skill.

When the user requests plan changes, revise the plan and obtain approval before implementation.

## Phase 6: Implementation

During implementation:

- Follow the approved specification and plan.
- Keep changes small, coherent, and within scope.
- Reuse existing project patterns and specialized skills.
- Avoid opportunistic refactors and unrelated cleanup.
- Add or update tests as part of the implementation, not as deferred work.
- Run focused checks incrementally at useful boundaries.
- Preserve user changes and avoid reverting unrelated work.
- Keep the user informed of material discoveries, blockers, and deviations.

If implementation reveals that the specification is incorrect, incomplete, contradictory, or no longer feasible:

1. Stop the affected implementation work.
2. Explain the discovery and its impact.
3. Propose a specification amendment, clearly labeling facts and recommendations.
4. Obtain human approval for the amended specification.
5. Update and reapprove the implementation plan when the amendment changes it.

Never silently alter a requirement to fit the implementation.

## Phase 7: Verification

Before declaring completion:

1. Execute the checks defined in the specification.
2. Verify every acceptance criterion and record its result.
3. Fix failures introduced by the implementation.
4. Run the appropriate project-level regression checks.
5. Review the complete diff, not only individual edited files.
6. Check for accidental, generated, secret, unrelated, or out-of-scope changes.
7. Confirm that migrations, configuration, documentation, and deployment effects are handled when applicable.

Do not claim a check passed unless it was executed successfully. Distinguish passed checks, failed checks, and checks that could not be run.

## Phase 8: Final Report

Provide a concise final report containing:

- What was implemented.
- Main files and components changed.
- Tests and verification commands executed.
- Results of those checks.
- Acceptance criteria status.
- Deviations from the approved plan and why they occurred.
- Remaining risks or limitations.
- Decisions that still require human attention.

Do not hide incomplete verification or unresolved risks behind a general statement that the task is complete.

## Scope Change Protocol

Any discovery during implementation that changes required behavior, acceptance criteria, non-goals, data meaning, permissions, integration contracts, or rollout expectations is a specification change.

For a specification change:

1. Stop work on the affected portion.
2. Update the relevant specification sections.
3. Explain the impact on scope, risk, plan, and verification.
4. Obtain human approval.
5. Resume from planning when necessary.

Minor implementation details that do not change approved behavior may be adjusted without respecification, but material plan deviations must be reported.

## Coordination With Specialized Skills

This skill owns the engineering process. Specialized skills own technical guidance in their domains.

Examples:

- Use Django skills for models, migrations, views, forms, URLs, templates, and tests.
- Use HTMX or Alpine.js skills for server-driven interactions and local client state.
- Use frontend or Flowbite skills for layout, components, accessibility, and responsive behavior.
- Use Docker or deployment guidance for build, runtime, and rollout details.

Do not duplicate framework documentation in the specification. Instead, record the relevant constraint or decision and invoke the specialized skill when planning or implementing that portion.

## Completion Checklist

Before finishing an SDD task, confirm:

- The process depth matched the task's uncertainty and risk.
- Discovery was focused and read-only.
- The specification described outcomes rather than implementation steps.
- Facts, requirements, assumptions, and recommendations stayed distinct.
- Acceptance criteria were objective and verifiable.
- Verification was defined before implementation.
- Required human checkpoints occurred.
- Implementation remained within approved scope.
- Scope-changing discoveries returned to specification review.
- The complete diff and all available checks were reviewed.
- The final report disclosed results, deviations, and remaining risks.
