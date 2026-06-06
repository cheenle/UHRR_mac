---
name: aladdin-v2
description: Use when the user mentions 阿拉丁 V2, 老灯新灵, FDE, SDD, harness, agentic engineering, vibe coding, software architecture methodology, or wants to plan/review/execute an engineering cycle using veteran judgment plus AI agents.
---

# Aladdin V2 Skill

Use this skill to apply the 阿拉丁 V2 / 老灯新灵 method: IT veteran judgment plus vibe coding / agentic engineering, driven by FDE cycles, structured by SDD, and constrained by harness.

## Core Model

```text
Aladdin V2 = 老灯新灵 + FDE Cycle + SDD Spine + Agentic Harness + Product Leverage
老灯新灵 = Veteran Judgment + Vibe Coding + Field Truth
```

Meaning:

- 老灯: IT veteran judgment, production experience, failure intuition, architecture taste, tradeoff ability.
- 新灵: AI/vibe coding/agentic coding execution power released and constrained by veteran judgment.
- Field Truth: evidence from real operation, logs, measurements, user experience, hardware/browser behavior.
- FDE Cycle: Echo -> Delta -> Product.
- SDD Spine: architecture memory and decision structure.
- Harness: context, specs, plans, commands, tests, guardrails, postmortems.
- Product Leverage: each cycle must reduce the next cycle's marginal cost.

## When To Use

Use this skill for:

- Creating or refining engineering methodology documents.
- Planning a feature or refactor as an FDE cycle.
- Turning a vague request into Echo / Delta / Product work.
- Creating agentic plans, checklists, specs, ADRs, SDD updates, or guardrails.
- Reviewing whether a proposed implementation has enough harness and Product leverage.
- Updating `AGENTS.md`, SDD, FDE docs, or repo-local OpenCode skills around engineering practice.
- Diagnosing why vibe coding produced fast but unsafe code.

Do not use this skill for small one-line edits or purely informational answers unless the user asks for methodology, planning, architecture, FDE, SDD, harness, or agentic workflow.

## Always Start With Phase Detection

Before acting, classify the user's request into one phase:

```text
Discovery: user is asking what the problem/method should be.
Echo: define field truth, demo, scope, and success metrics.
Delta: implement or plan a fast prototype to validate one uncertainty.
Product: abstract, document, add harness, update SDD/ADR/AGENTS.
Review: inspect whether work respects Aladdin V2 guardrails.
Skill-System: create or update reusable OpenCode skills/agents/plans.
```

If the user asks to implement, proceed; do not stop at theory. If the user asks for a methodology or skill, create the docs/skill files directly.

## Required Output Shape For Cycle Work

For any non-trivial cycle, produce or update a document/plan with these sections:

```markdown
# Aladdin V2 Cycle: [Name]

## 老灯: Veteran Judgment
- Engineering risk:
- Architecture tradeoff:
- Things AI is likely to guess wrong:
- Quality line that must not be crossed:

## Field Truth
- Scenario:
- Pain:
- Evidence:
- Current workaround:

## Echo
- One-sentence problem:
- Demo script:
- Success metrics:
- Out of scope:
- SDD impact:

## Delta
- Biggest uncertainty:
- Prototype strategy:
- Iteration plan:
- Verification commands:

## Product
- Reusable abstraction:
- ADR/SDD updates:
- Harness updates:
- Postmortem/docs:

## Product Leverage
- What becomes easier next time:
- Remaining risks:
```

## Phase Rules

### Discovery

Goal: turn fuzzy intent into a concrete Aladdin V2 direction.

Actions:

- Read high-value docs before inventing concepts.
- Extract old-lamp veteran judgment from existing failures, docs, scripts, and architecture decisions.
- Identify which hidden experience must be made explicit.
- Define what the new-spirit/vibe-coding layer can accelerate.
- Recommend a concrete next artifact: methodology doc, cycle plan, SDD update, ADR, AGENTS guardrail, or skill.

### Echo

Goal: define a valuable demo, not a large requirements document.

Checklist:

- Problem is grounded in field truth or production evidence.
- Demo is concrete and emotionally/operationally meaningful.
- Metrics are measurable.
- Scope is explicitly bounded.
- SDD impact is known, usually Ch4/Ch5/Ch6.

Avoid:

- Large speculative requirements.
- Feature lists without demo.
- Starting implementation before identifying the biggest uncertainty.

### Delta

Goal: validate the biggest uncertainty quickly.

Rules:

- First prototype may hardcode, log, print, or use narrow assumptions.
- Record assumptions that must be removed in Product.
- Demo every 2-3 days or after each small iteration.
- If 5 iterations do not converge, question the approach.
- Do not create broad abstractions before the path is proven.

Verification:

- Prefer focused commands over whole-repo assumptions.
- For MRRC, remember hardware/audio tests can require devices and dependencies.
- Use repo-specific guardrails from `AGENTS.md` before touching PTT/audio/FT8/deployment.

### Product

Goal: turn learning into reusable leverage.

Required outputs:

- Reusable module/pattern or explicit decision not to abstract.
- ADR or architecture decision update for major choices.
- SDD updates for changed context, NFR, services, components, operations, or version history.
- Harness updates: commands, tests, plans, `AGENTS.md`, postmortem, troubleshooting doc, or skill.
- Product leverage statement: what future work is now cheaper.

Do not accept “it works” as done if no knowledge was captured.

### Review

Review against these questions:

- Did old-lamp veteran judgment define risks and boundaries?
- Is there field truth, or is this speculation?
- Did vibe coding accelerate work within constraints, or bypass constraints?
- Are NFRs measurable?
- Is there a harness for future agents?
- Did the work create Product leverage?
- Are SDD/ADR/AGENTS/docs updated where needed?

Findings should focus on missing guardrails, unverifiable claims, premature abstraction, skipped Product work, and repeated known risks.

### Skill-System

When creating or updating OpenCode skills:

- Put project skills under `.opencode/skills/<name>/SKILL.md`.
- Include frontmatter with `name` and a concrete trigger-heavy `description`.
- Keep the skill actionable: phase detection, checklists, templates, references.
- Avoid vague motivational prose in skills; put long explanation in `docs/`.
- Remind the user to restart opencode after skill/config changes.

## MRRC-Specific References

Use these as source material in this repository:

- `docs/aldv2/Aladdin_V2_Methodology.md`: top-level methodology.
- `docs/aldv2/Laodeng_Xinling_Methodology.md`: core old-lamp/new-spirit model.
- `FDE.md`: MRRC FDE retrospective.
- `docs/FDE_Practice_Guide.md`: operational FDE guide.
- `SDD/`: IBM TeamSD 14-chapter architecture spine.
- `DESIGN/MRRC_SDD.md`: compact SDD overview.
- `docs/superpowers/specs/`: agentic specs examples.
- `docs/superpowers/plans/`: executable agentic plans examples.
- `AGENTS.md`: repo-specific OpenCode guardrails.
- `docs/PTT_Audio_Postmortem_and_Best_Practices.md`: example of memory harness.

## Templates

### Agentic Plan

```markdown
# [Task] Implementation Plan

> For agentic workers: execute step-by-step. Do not skip verification.

Goal:
Architecture:
Scope:
Out of Scope:
Guardrails:

## Task 1: [smallest safe step]
- Files:
- Steps:
- Verification:
- Expected result:

## Task 2: [next step]
- Files:
- Steps:
- Verification:
- Expected result:

## Productization
- ADR/SDD:
- Harness:
- Docs:
- Product leverage:
```

### ADR Prompt

```markdown
## AD-[ID]: [Decision]

Problem:
Context:
Decision:
Alternatives:
Rationale:
Impact:
Verification:
Follow-up harness:
```

### Postmortem Prompt

```markdown
# [Incident/Problem] Postmortem

What happened:
User/system impact:
Root cause:
Why existing harness missed it:
Fix:
Guardrail added:
Verification:
Product leverage:
```

## Final Response Guidance

When completing work under this skill, summarize:

- Which Aladdin V2 phase was applied.
- What artifacts were created or updated.
- What harness or guardrail was added.
- What future work is now easier.
- Any verification not run and why.
