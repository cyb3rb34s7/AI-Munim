# CLAUDE.md

This file is auto-loaded into every Claude Code session in this repo. It is the short version of our agreements. The full rulebook is `docs/conventions.md` — read it before touching code.

## What this project is

AI-Munim — a v0 "AI employee for D2C brands" built as a hiring assignment. Deadline **2026-05-17 23:59 IST**. Scoring is half craft, half judgment — the WHY of every choice is part of the deliverable.

- `docs/the-build.docx` — the original brief.
- `docs/requirements.md` — persona, scope, FRs/NFRs, acceptance criteria.
- `docs/architecture.md` — the technical design (schema, citation contract, agent, scale).
- `docs/conventions.md` — **the rulebook for all code in this repo.**

## Read these before every work session, in order

1. `context.md` — what's done, what's in progress, **problems we've already solved (never repeat them).**
2. `CHANGELOG.md` — recent changes with reasoning, for tracing regressions and reverts.
3. `docs/conventions.md` — conventions and architecture rules.
4. Then whatever the current task needs.

If you skip the first two, you will repeat a mistake we already paid for. Don't.

## The module workflow

Every feature follows this loop. No exceptions.

1. **Define** — agree on acceptance criteria for the slice (in chat with the user).
2. **Plan** — I write the plan using `superpowers:writing-plans`. User reviews and iterates.
3. **Implement** — I dispatch **one** coder subagent **per phase** (not per task) with the full plan + a reference to `docs/conventions.md`. The subagent works through the plan top to bottom, committing per task as the plan dictates. Per-task dispatch is rejected — the dispatch overhead exceeds the value at our task granularity. (Skill: `superpowers:subagent-driven-development`.)
4. **Review** — I dispatch a reviewer subagent for a critical review of the whole phase against `docs/conventions.md`. Reviewer reads the diff + the plan + the conventions and reports issues by severity. (Skill: `superpowers:requesting-code-review`.)
5. **Fix** — apply review findings.
6. **Verify** — I update `context.md` (decisions, problems, solutions) and `CHANGELOG.md` (what, why, date) **in the same commit as the code**. (Skill: `superpowers:verification-before-completion`.)
7. **Manual test** — hand off to the user.

Tracking each step with `TaskCreate` is encouraged; it makes the workflow visible to the user.

## Non-negotiable rules (everything else is in `docs/conventions.md`)

### Process

- **Always read `context.md` and `CHANGELOG.md` at session start.** Find the relevant problem entries before writing new code.
- **Update `context.md` and `CHANGELOG.md` in the same commit as the change.** A change is not done until both are updated.
- **Conventional Commits.** `feat(scope):`, `fix(scope):`, `docs(scope):`, etc. The brief explicitly says reviewers will read commit history.

### Code

- **No silent fallbacks.** If a fallback feels necessary, **STOP and ask the user.** Never insert one quietly.
- **No broad `except Exception:`.** Catch the specific class you understand. Re-raise as a typed domain error. Anything else propagates to the global handler.
- **No magic strings in branches.** Status comparisons, payment methods, entity types, error codes all live in `StrEnum` / `as const` constants. `if x == "cod":` is wrong; `if x is PaymentMethod.COD:` is right.
- **Money: `Decimal` only, never float. Time: UTC ISO 8601 on the wire, IST at display.** One helper for each (`inr()`, `fmtIST()`), never inline formatting.
- **`trace_id` on every request, every log line, every tool call, every agent run.** It threads through HTTP → DB → LLM. JSON logs are mandatory.
- **API responses always have the envelope.** Success: `{ success: true, data, trace_id }`. Error: `{ success: false, error: { code, message, details? }, trace_id }`. Error `code` is a typed enum; frontend branches on `code`, never `message`.
- **Citation contract is fail-closed.** If the post-processor errors, the response is rejected. We never ship an unverified number.

### Architecture

- **Vertical slice everywhere.** Each module owns `router/service/repository/schemas/tests` (backend) or `api/components/hooks/store/types/utils/constants` (frontend). Shared code lives in `shared/`, but only after the third use.
- **Components are dumb.** Logic lives in hooks. Components receive props, render JSX, hold local cosmetic state, and nothing else.
- **Server state = TanStack Query. UI state = Zustand.** Don't mix them.
- **No DB mocks in tests.** Integration tests hit a real (temp) SQLite. External APIs use VCR-style cassettes.

### Tooling

- **`ruff`, `mypy`, `eslint`, `tsc`, `prettier` must all pass locally before commit.** Pre-commit hooks enforce this. No `--no-verify`.
- **`pnpm` for JS, `uv` for Python.** Stay in those tools.

## What "done" means

A module is done when:

1. Plan was reviewed and approved by the user.
2. Code passes lint, typecheck, and tests locally.
3. Reviewer subagent's findings are addressed (or explicitly deferred with a `context.md` entry).
4. `context.md` and `CHANGELOG.md` are updated, committed alongside the code.
5. User has manually tested and accepted.

Anything short of this is in-progress.

## Asking the user vs. proceeding

Pause and ask when:

- A fallback feels necessary anywhere.
- A convention in `docs/conventions.md` seems wrong for the situation.
- A scope change is implied (the plan didn't cover it).
- A destructive git or filesystem action would help (force-push, hard reset, branch delete, rm -rf).
- An external dependency or paid API would be added.

Proceed without asking when:

- The work is inside the approved plan.
- The change is local, reversible, and conforms to the conventions.
- It's a doc / changelog / context update reflecting work already done.

## Skills that apply to this project

These are the existing superpowers we lean on. Invoke them by name when the situation matches.

- `superpowers:writing-plans` — when a module is defined and the plan needs to be written.
- `superpowers:subagent-driven-development` — when dispatching the coder subagent.
- `superpowers:requesting-code-review` — when dispatching the reviewer subagent.
- `superpowers:verification-before-completion` — before claiming any task done.
- `superpowers:test-driven-development` — when writing the citation enforcer, scoring functions, and connector mappers.
- `superpowers:systematic-debugging` — when something breaks unexpectedly. Don't just patch — find the root cause and log it in `context.md`.

We deliberately did **not** create a new project-specific skill: existing superpowers cover the workflow, and `docs/conventions.md` + this file carry the project rules.
