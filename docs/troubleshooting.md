# Troubleshooting

## UI opens but cannot reach the backend

Check the services and API logs:

```bash
sudo systemctl status mcp-stack-api mcp-stack-web --no-pager
sudo journalctl -u mcp-stack-api -n 100 --no-pager
```

The frontend expects the API at `127.0.0.1:8000`. Confirm that both installed
services are active and that the API has not exited with a configuration error.

## Actions fail with 403 behind a proxy

Set your **exact** HTTPS origin in `/etc/mcp-stack/deployment.env`:

```dotenv
MCP_STACK_PUBLIC_ORIGINS=https://mcp.example.com
```

No trailing slash or URL path. Restart both API and web services. Ensure the
proxy preserves the browser's Origin header. Do not disable origin checks.

## Client permission errors

`broker-peer-forbidden` means the client's UID is not allowed.

1. Add the client account to `mcp-stack-clients`.
2. Reconnect/login so the process receives the new group membership.
3. Add its numeric UID to the broker's
   `MCP_STACK_BROKER_ALLOWED_UIDS` using a systemd override, retaining
   the service UID and any already allowed client UIDs.
4. Restart the broker and recreate the MCP client session.

Use `sudo systemctl edit mcp-stack-broker` for the override. Never make
the broker socket world-writable or grant clients access to the secret store.

## Broker unavailable or launch failed

```bash
sudo systemctl status mcp-stack-broker --no-pager
sudo journalctl -u mcp-stack-broker -n 100 --no-pager
```

Check the target ID, executable path, working directory, and required secrets.
The server runs as `mcp-stack`, not as you. A command available in your
shell may be absent from the service's environment. mise environments must be
installed and trusted by the service account.

## A service starts and immediately stops

Open its Component/Tunnel page and read the recent logs. Check arguments,
resource paths, permissions, and required environment bindings. Each argument
field line is **one argument**: write `--transport` and `stdio` on separate lines.

“No active MCPStack systemd user unit is loaded” can be normal before
the first Start. It is an observation, not proof that configuration is invalid.

<details>
<summary>Where to look: application state, health, and logs</summary>

Use the Component page to compare provider state with health results and recent
output. This screenshot contains simulated demo observations, not a live diagnostic result.

![Component page showing application state, health observations, lifecycle controls, and recent logs](screenshots/application-health-logs-desktop.png)

</details>

## Environment changes did not take effect

Save the Stack, then restart the persistent Application or recreate the stdio
client session. Changing the bridge's environment does not change an attached
Application's environment; configure the process that consumes the setting.

## Logs are empty

Managed-service logs come from journald. Some programs emit no startup output;
check runtime and health separately. Stdio MCP protocol stdout is not a web log.
For systemd journal access errors, check API logs and the service account's
`systemd-journal` membership.

## Installer cannot resolve uv, Node, or pnpm

Run the installer as your normal user. Check `uv --version`, `node --version`,
and `pnpm --version` first. With mise, select the correct installed tools before
building. The installer resolves shims to standalone uv/Node binaries and refuses
wrappers that cannot work in the installed environment.

## Configuration changed on disk

Reload the editor and reapply your intended changes. A stale revision is refused
to protect newer work. Do not bypass it by editing internal revision fields.

## Reporting a problem

Include your OS, versions, reproduction steps, and redacted error/log excerpts.
Never attach real `.env` files, database files, secret slots, or full environments.
For a security concern, follow [SECURITY.md](../SECURITY.md), not a public bug report.
