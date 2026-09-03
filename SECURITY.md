# Security Policy

## Supported versions

| Version        | Supported |
|----------------|-----------|
| 0.14.x (Core)  | ✅ Yes    |
| older          | ❌ No     |

Security fixes are applied to the latest `0.14.x` line.

## Reporting a vulnerability

Please **do not** open a public issue for security vulnerabilities.

Instead, report privately by emailing the maintainers (see the repository
owner's profile for a contact address), or use GitHub's private vulnerability
reporting if available. Include:

- A description of the issue and its impact.
- Steps to reproduce, or a proof of concept.
- Affected version(s).

You can expect an acknowledgment within a few business days. We will coordinate a
fix and disclosure timeline with you.

## Security posture of this codebase

Project Factory was reviewed for secret leakage prior to open-sourcing:

- **No hardcoded credentials.** API keys / tokens are referenced only by
  *environment variable name* (e.g. `OPENAI_API_KEY`, `XAI_API_KEY`). The actual
  values are never written to disk by the Core.
- **Secret redaction.** Before any text is persisted or forwarded to an external
  service, the Core redacts patterns such as `sk-…`, `ghp_…`, `AKIA…`,
  `Bearer …`, and `api_key=…`. See `core/src/project_factory/normalizer.py`.
- **Isolated runtime.** The Python Core runs in its own virtual environment and
  does not modify system Python packages.
- **Sample-only defaults.** Generated project templates contain development-only
  sample defaults (for example a `POSTGRES_PASSWORD: app` inside a scaffolded
  `docker-compose` drawing). These are illustrative values for generated output,
  not credentials for Project Factory itself.

If you discover that any real secret has been committed, please report it
immediately using the channel above so it can be rotated and removed from
history.
