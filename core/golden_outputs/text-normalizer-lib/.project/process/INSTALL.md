# Optional Spec Kit Process Integration

This project is usable without Spec Kit. The commands below install the optional process layer.
Project Factory owns `AGENTS.md` and `CLAUDE.md`; do not add the Spec Kit `agent-context` extension unless ownership is explicitly changed.

Pinned upstream contract: Spec Kit 1.0.1

## Planned commands

```bash
specify init --here --integration codex --script py
```

```bash
specify integration install claude --script py
```

```bash
specify integration status
```

## Verification boundary

A plan file is not proof that Spec Kit was installed. Check `.project/evidence/process-integration.json` and `.specify/integration.json` after a real installation.
