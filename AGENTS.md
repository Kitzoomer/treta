# Agent instructions for TRETA

Scope: entire repository.

## Project intent
TRETA is a decision operating system with persistent state and event-driven orchestration. Keep behavior stable unless a task explicitly requires business logic changes.

## Change policy
- Prefer **small, local edits**.
- Avoid broad refactors, renames, or architectural rewrites.
- Do not add heavy frameworks.
- Keep Docker/WSL compatibility intact.

## Safety and secrets
- Never commit secrets or real credentials.
- Do not modify `.env` files with real values.
- Use `.env.example` for documented config.

## Impact analysis before editing
Always check whether change touches:
1. backend orchestration,
2. event contracts,
3. persistence (SQLite and JSON stores),
4. UI polling/runtime behavior.

If not required, do not modify those layers.

## Validation expectations
For each meaningful change:
- provide a short test/checklist,
- include manual verification steps,
- include a simple rollback command sequence.
