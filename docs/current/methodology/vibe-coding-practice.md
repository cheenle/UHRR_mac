# Vibe Coding Practice Core Documents

## Purpose

The original SDD is the core document set for this project's Vibe Coding practice. It captures the project framing, design narrative, architecture intent, and decision trail that guided MRRC's implementation.

Current runtime documentation should verify behavior from code. The SDD should be preserved as the primary methodology and design-practice context, even when individual implementation details have drifted.

## Core Document Set

The preserved SDD lives here:

- `docs/legacy/sdd/original-sdd/README.md`
- `docs/legacy/sdd/original-sdd/01-executive-summary.md`
- `docs/legacy/sdd/original-sdd/02-business-direction.md`
- `docs/legacy/sdd/original-sdd/03-project-definition.md`
- `docs/legacy/sdd/original-sdd/04-system-context.md`
- `docs/legacy/sdd/original-sdd/05-non-functional-requirements.md`
- `docs/legacy/sdd/original-sdd/06-use-case-model.md`
- `docs/legacy/sdd/original-sdd/07-subject-area-model.md`
- `docs/legacy/sdd/original-sdd/08-architecture-decisions.md`
- `docs/legacy/sdd/original-sdd/09-architecture-overview.md`
- `docs/legacy/sdd/original-sdd/10-service-model.md`
- `docs/legacy/sdd/original-sdd/11-component-model.md`
- `docs/legacy/sdd/original-sdd/12-operational-model.md`
- `docs/legacy/sdd/original-sdd/13-feasibility-assessment.md`
- `docs/legacy/sdd/original-sdd/14-version-history.md`

## How To Use It

Use the SDD for:

- Project intent and design direction.
- Vibe Coding workflow and reasoning style.
- Architecture narrative and decision history.
- Feature framing before implementation work.
- Cross-checking whether new docs still match the original product direction.

Use `docs/current/` for:

- Verified runtime behavior.
- Current ports, routes, scripts, config, and loaded frontend modules.
- Current operations and troubleshooting procedures.
- Drift notes where implementation differs from older design text.

## Maintenance Rule

Do not treat the SDD as disposable legacy. If a claim in the SDD no longer matches code, document the current behavior in `docs/current/` and keep the SDD as the preserved practice record unless there is a deliberate rewrite of the methodology material.
