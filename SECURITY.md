# Security

## Intended use

MCPStack is a trusted local administration tool. It is not a
multi-tenant service and does not provide an account/role system.

- Keep the API on loopback. Put authentication in front of any remote UI access.
- Origin/CSRF checks protect browser mutations; they are not user authentication.
- Same-user processes and local administrators remain trusted.
- Managed MCP implementations share the `mcp-stack` identity. They are
  not isolated from each other or from service-readable secrets. Only install
  trusted implementations; shell-execution tools require extra isolation.
- Secret APIs accept replacements but do not return stored values. A trusted
  executable receiving a secret can still disclose it; the store is not a
  sandbox for malicious programs.

## Secrets and local files

Never commit real Stack documents, tunnel IDs, private keys, deployment `.env`
files, database files, or operational backups. Store API keys through the UI's
write-only secret fields, not in literal configuration or deployment settings.
Ignore rules are a convenience, not a security boundary.

## Report a vulnerability

Use GitHub's **Security → Report a vulnerability** when private reporting is
enabled. If it is unavailable, request a private reporting channel without
posting exploit details or credentials. There is no published security email
or guaranteed response time yet.

Include affected versions, impact, and a minimal reproduction using fake data.
Do not post working tokens or private deployment information in a public issue.

The project is evolving and has no formal long-term security-support window.
Review updates before deployment and report reproducible issues on the current
version. Operators remain responsible for updating managed third-party software.
