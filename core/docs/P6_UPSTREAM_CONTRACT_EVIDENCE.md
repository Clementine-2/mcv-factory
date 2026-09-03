# P6 Upstream Contract Evidence

Checked: 2026-08-30

## OpenAI Codex

OpenAI's Codex documentation describes `AGENTS.md` as project instructions scoped by directory tree, with deeper files taking precedence. P6 therefore materializes the canonical contract to root `AGENTS.md` for the Codex adapter.

Reference: https://openai.com/index/introducing-codex/

## GitHub Spec Kit v1.0.1

Release: https://github.com/github/spec-kit/releases/tag/v1.0.1
Published: 2026-08-21

Pinned upstream source evidence inspected through GitHub's contents API:

- Codex integration: `src/specify_cli/integrations/codex/__init__.py`
  - blob SHA: `2ffa59ca4b50e2bb257ca4c968e299dd0eccd37a`
  - declares `.agents/skills` skills-based integration and multi-install safety.
- Claude integration: `src/specify_cli/integrations/claude/__init__.py`
  - blob SHA: `2ce7fb6dcc8cc92426b37666e2980e0fd7308596`
  - declares `.claude/skills` skills-based integration and multi-install safety.
- Agent-context extension descriptor: `extensions/agent-context/extension.yml`
  - blob SHA: `191069e32c3effd9ed97de339f73762ff7a6459a`
  - explicitly manages coding-agent context files as an opt-in extension.

Spec Kit documentation also states that multiple safe integrations can coexist, with `specify integration install <key>`, and records installed integrations in `.specify/integration.json`.

References:
- https://github.github.com/spec-kit/reference/integrations.html
- https://github.github.com/spec-kit/reference/core.html
- https://github.com/github/spec-kit/blob/v1.0.1/extensions/agent-context/extension.yml

## Verification limitation

These sources establish public file/command contracts. They do not prove that a real Codex/Claude/Spec Kit runtime ran in the P6 build environment. P6 preserves that distinction in Evidence and Project Lock.
