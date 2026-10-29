# Operations

For first-time setup, use [installation](../installation.md). For everyday UI
tasks, use [usage](../usage.md).

## Services

The base installer starts and boot-enables:

- `mcp-stack-broker.service` — stdio execution broker
- `mcp-stack-api.service` — backend
- `mcp-stack-web.service` — browser frontend

```bash
sudo systemctl status mcp-stack-broker mcp-stack-api mcp-stack-web
sudo systemctl restart mcp-stack-broker mcp-stack-api mcp-stack-web
sudo systemctl stop mcp-stack-web mcp-stack-api mcp-stack-broker
```

Managed Stack Applications and tunnel profiles are separate resources. They
are manually activated and are not automatically boot-enabled by the app.

## Paths

| What | Where |
| --- | --- |
| Non-secret deployment settings | `/etc/mcp-stack/deployment.env` |
| Installed program files | `/opt/mcp-stack/` |
| Stack configuration | `/var/lib/mcp-stack/stacks/` |
| Tunnel profiles | `/var/lib/mcp-stack/tunnel-profiles/` |
| Private secret slots | `/var/lib/mcp-stack/secrets/` |
| Runtime tool environments | `/var/lib/mcp-stack/environments/` |
| Application data | `/var/lib/mcp-stack/stack-data/` |
| Broker socket and transient observations | `/run/mcp-stack/` |
| Installed client | `/usr/local/bin/mcpctl` |

The backend/broker run as `mcp-stack`. The frontend runs as
`mcp-stack-web` and has no direct secret-store access.

## Logs

```bash
sudo journalctl -u mcp-stack-api -n 100 --no-pager
sudo journalctl -u mcp-stack-broker -n 100 --no-pager
sudo journalctl -u mcp-stack-web -n 100 --no-pager
```

Application and tunnel logs are available in their UI detail pages. Those use
the service identity's systemd user manager, not your interactive user's manager.
The API's `systemd-journal` membership permits bounded journal retrieval.

<details>
<summary>Preview: inspect application and tunnel logs in the UI</summary>

View application output alongside lifecycle and health information, then refresh
or download the recent log selection. These examples use simulated demo data.

![Application detail with health, lifecycle controls, and recent logs](../screenshots/application-health-logs-desktop.png)

Tunnel detail pages offer their own controls and logs, including a mobile layout.
You can investigate remote exposure without changing the target application's state.

<img src="../screenshots/tunnel-controls-mobile.png" width="280" alt="Tunnel lifecycle and logs on a mobile screen.">

</details>

Never share unredacted application logs: upstream programs can print credentials
that the control plane may not know to redact.

## Updating the base application

Run the [installer](../installation.md#update) as the repository user, not with
sudo. It builds before elevation. It resolves mise shims to actual uv/Node
executables and checks staged copies with an empty environment. An inactive
shim may use a matching standalone PATH fallback; a different version or
environment-dependent wrapper is refused. See
[mise executable resolution](https://mise.jdx.dev/cli/which.html).

The installer preserves live Stacks, secret slots, and tunnel profiles.
Per-Stack program installation and updates are your responsibility; keep those
helpers separate from the base control-plane install. The old repository-wide
configuration migration switch is no longer supported.

## Backups

Back up `/etc/mcp-stack/` and `/var/lib/mcp-stack/` to a private,
access-controlled destination. This includes secrets: do not attach the backup
to issues or commit it. Application databases may need application-specific
consistent backups; stop the Application first if its backup procedure requires it.

Do not back up `/run/mcp-stack/` as durable state. Restoring configuration
does not restore an MCP protocol connection or a previously running process.

## Deletion and secret cleanup

Deleting a Stack stops its owned managed Components and associated tunnel
profiles, removes its source, and clears Stack-scoped secret slots. The shared
tunnel API key is retained. Arbitrary application data is not deleted.

The UI accepts secret replacements but never reveals stored values. Keep the
deployment settings file non-secret.

## Security boundary

Both web/API listeners bind to loopback. Put authenticated HTTPS access in front
of the frontend if needed, and configure the exact origin for both API/web
services. Origin and mutation-header checks are not an account system. Same-host
administrators remain trusted; see [SECURITY.md](../../SECURITY.md).
