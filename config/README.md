# Example configurations

These files demonstrate the configuration model. They contain no real service
registrations, tunnel IDs, or secret values, and are **never installed automatically**.

## Stack examples

| File | Demonstrates |
| --- | --- |
| [stdio.yaml](stacks/stdio.yaml) | Session-owned package runner, mise environment, secret reference |
| [http.yaml](stacks/http.yaml) | Existing Streamable HTTP MCP endpoint |
| [application.yaml](stacks/application.yaml) | Managed persistent program, HTTP health, journal logs |
| [composite.yaml](stacks/composite.yaml) | An Application and the stdio MCP adapter that depends on it |

The package names, executable paths, and URLs are placeholders. Install your
own software and adapt the fields before using them.

[environments/example-stdio/mise.toml](environments/example-stdio/mise.toml)
shows a Node tool selection. It must be installed/trusted by the service account;
it is not automatically activated by saving a Stack.

## Tunnel examples

- [example-stdio.yaml](tunnel-profiles/example-stdio.yaml) exposes a stdio Stack.
- [example-http.yaml](tunnel-profiles/example-http.yaml) exposes an HTTP endpoint.

Replace the fictional tunnel IDs with identifiers issued for your own tunnels.
The API-key fields reference an environment variable, not a stored credential.

## Keep your configuration private

Use **New Stack** and **Tunnels** in the UI. Live configuration is authoritative
under `/var/lib/mcp-stack/`, outside the checkout. Enter API keys through
write-only secret fields; do not put them in example YAML.

Real configurations and per-Stack installation scripts are not distributed by
this repository. Keep local source inputs in ignored `config.local/` or another
private directory. See [usage](../docs/usage.md).
