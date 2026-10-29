#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
settings_tool="${repo_root}/scripts/runtime/deployment-settings.py"
if [[ "${MCP_STACK_MIGRATE_CONFIG:-0}" != "0" ]]; then
  printf 'Repository example migration is no longer supported. Create Stacks through the UI.\n' >&2
  exit 2
fi

if [[ "${EUID}" -ne 0 ]]; then
  cd "${repo_root}"
  install_stage="$(mktemp -d /tmp/mcp-stack-install.XXXXXX)"
  # Only these disposable files are created during unprivileged staging.
  trap 'rm -f -- "${install_stage}/uv" "${install_stage}/node" "${install_stage}/deployment.env"; rmdir -- "${install_stage}" 2>/dev/null || true' EXIT
  python3 "${settings_tool}" resolve --repo "${repo_root}" --file "${install_stage}/deployment.env"
  uv build --project backend
  pnpm --dir frontend build
  bash "${repo_root}/scripts/runtime/stage-service-tools.sh" "${install_stage}"
  sudo \
    MCP_STACK_INSTALL_STAGE="${install_stage}" \
    "${BASH_SOURCE[0]}" --install-only
  exit
fi

if [[ "${1:-}" != "--install-only" ]]; then
  printf 'Run this installer as the repository user; it performs its build before elevation.\n' >&2
  exit 2
fi

wheel="$(find "${repo_root}/backend/dist" -maxdepth 1 -type f -name '*.whl' -printf '%T@ %p\n' | sort -nr | head -n1 | cut -d' ' -f2-)"
install_stage="${MCP_STACK_INSTALL_STAGE:-}"
standalone_root="${repo_root}/frontend/.next/standalone"
server_subdir="frontend"
[[ -f "${standalone_root}/${server_subdir}/server.js" ]] || server_subdir="."
if [[ -z "${wheel}" || ! -x "${install_stage}/uv" || ! -x "${install_stage}/node" || ! -f "${standalone_root}/${server_subdir}/server.js" ]]; then
  printf 'Release artifacts are missing; run the installer without sudo.\n' >&2
  exit 2
fi

tunnel_bundle="$(python3 "${settings_tool}" get --file "${install_stage}/deployment.env" \
  --key MCP_STACK_TUNNEL_BUNDLE)"
if [[ -n "${tunnel_bundle}" ]] && \
  { [[ ! -x "${tunnel_bundle}/tunnel-client" ]] || [[ ! -x "${tunnel_bundle}/cloudflared" ]]; }; then
  printf 'Configured tunnel bundle must contain executable tunnel-client and cloudflared files.\n' >&2
  exit 2
fi
install -d -m 0755 -o root -g root /etc/mcp-stack
python3 "${settings_tool}" install --file "${install_stage}/deployment.env"

getent group mcp-stack >/dev/null || groupadd --system mcp-stack
getent group mcp-stack-clients >/dev/null || groupadd --system mcp-stack-clients
getent passwd mcp-stack >/dev/null || useradd \
  --system --gid mcp-stack --home-dir /var/lib/mcp-stack \
  --shell /usr/sbin/nologin mcp-stack
getent passwd mcp-stack-web >/dev/null || useradd \
  --system --gid mcp-stack --home-dir /nonexistent \
  --shell /usr/sbin/nologin mcp-stack-web
usermod --append --groups mcp-stack-clients mcp-stack
usermod --append --groups systemd-journal mcp-stack
if getent passwd codex >/dev/null; then
  usermod --append --groups mcp-stack-clients codex
fi

service_uid="$(id -u mcp-stack)"
codex_uid="$(id -u codex 2>/dev/null || true)"
allowed_uids="${service_uid}${codex_uid:+,${codex_uid}}"

install -d -m 0755 /opt/mcp-stack /opt/mcp-stack/bin
install -m 0755 "${install_stage}/uv" /opt/mcp-stack/bin/uv
install -d -m 0750 -o mcp-stack -g mcp-stack \
  /var/lib/mcp-stack /var/lib/mcp-stack/stacks \
  /var/lib/mcp-stack/tunnel-profiles \
  /var/lib/mcp-stack/environments /var/lib/mcp-stack/stack-data
install -d -m 0700 -o mcp-stack -g mcp-stack \
  /var/lib/mcp-stack/secrets
install -d -m 2750 -o mcp-stack -g mcp-stack-clients \
  /run/mcp-stack

backend_release_id="$(date -u +%Y%m%dT%H%M%SZ)-$$"
backend_release="/opt/mcp-stack/backend-releases/${backend_release_id}"
install -d -m 0755 /opt/mcp-stack/backend-releases
/opt/mcp-stack/bin/uv venv --python python3 "${backend_release}"
/opt/mcp-stack/bin/uv pip install --python "${backend_release}/bin/python" "${wheel}"
rm -rf /opt/mcp-stack/backend.previous
if [[ -L /opt/mcp-stack/backend ]]; then
  ln -s "$(readlink /opt/mcp-stack/backend)" \
    /opt/mcp-stack/backend.previous
elif [[ -d /opt/mcp-stack/backend ]]; then
  mv /opt/mcp-stack/backend /opt/mcp-stack/backend.previous
fi
ln -sfn "backend-releases/${backend_release_id}" /opt/mcp-stack/backend
ln -sfn /opt/mcp-stack/backend/bin/mcpctl /usr/local/bin/mcpctl

frontend_next="/opt/mcp-stack/frontend.next.$$"
cp -a "${standalone_root}" "${frontend_next}"
install -d "${frontend_next}/${server_subdir}/.next"
cp -a "${repo_root}/frontend/.next/static" "${frontend_next}/${server_subdir}/.next/static"
if [[ -d "${repo_root}/frontend/public" ]]; then
  cp -a "${repo_root}/frontend/public" "${frontend_next}/${server_subdir}/public"
fi
if [[ -d /opt/mcp-stack/frontend ]]; then
  rm -rf /opt/mcp-stack/frontend.previous
  mv /opt/mcp-stack/frontend /opt/mcp-stack/frontend.previous
fi
mv "${frontend_next}" /opt/mcp-stack/frontend
chown -R root:mcp-stack /opt/mcp-stack/frontend
chmod -R a=rX,u+w /opt/mcp-stack/frontend

if [[ -n "${tunnel_bundle}" ]]; then
  install -d -m 0755 /opt/mcp-stack/tunnel-client/current/bin
  install -m 0755 "${tunnel_bundle}/tunnel-client" \
    /opt/mcp-stack/tunnel-client/current/bin/tunnel-client
  install -m 0755 "${tunnel_bundle}/cloudflared" \
    /opt/mcp-stack/tunnel-client/current/bin/cloudflared
fi


loginctl enable-linger mcp-stack
install -m 0644 /dev/stdin /etc/systemd/system/mcp-stack-broker.service <<EOF
[Unit]
Description=MCPStack stdio execution broker
After=user@${service_uid}.service
Requires=user@${service_uid}.service

[Service]
Type=simple
User=mcp-stack
Group=mcp-stack-clients
RuntimeDirectory=mcp-stack
RuntimeDirectoryMode=2750
Environment=MCP_STACK_BROKER_ALLOWED_UIDS=${allowed_uids}
Environment=HOME=/var/lib/mcp-stack
Environment=MISE_DATA_DIR=/var/lib/mcp-stack/mise
ExecStart=/opt/mcp-stack/backend/bin/mcp-stack-broker
Restart=on-failure
RestartSec=2

[Install]
WantedBy=multi-user.target
EOF

install -m 0644 /dev/stdin /etc/systemd/system/mcp-stack-api.service <<EOF
[Unit]
Description=MCPStack API
After=user@${service_uid}.service mcp-stack-broker.service
Requires=user@${service_uid}.service

[Service]
Type=simple
User=mcp-stack
Group=mcp-stack
SupplementaryGroups=systemd-journal
Environment=XDG_RUNTIME_DIR=/run/user/${service_uid}
Environment=DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/${service_uid}/bus
Environment=HOME=/var/lib/mcp-stack
Environment=MISE_DATA_DIR=/var/lib/mcp-stack/mise
EnvironmentFile=/etc/mcp-stack/deployment.env
ExecStart=/opt/mcp-stack/backend/bin/mcp-stack-api
Restart=on-failure
RestartSec=2

[Install]
WantedBy=multi-user.target
EOF

install -m 0755 "${install_stage}/node" /opt/mcp-stack/bin/node
node_path=/opt/mcp-stack/bin/node
install -m 0644 /dev/stdin /etc/systemd/system/mcp-stack-web.service <<EOF
[Unit]
Description=MCPStack web UI
After=mcp-stack-api.service

[Service]
Type=simple
User=mcp-stack-web
Group=mcp-stack
WorkingDirectory=/opt/mcp-stack/frontend/${server_subdir}
Environment=HOSTNAME=127.0.0.1
Environment=PORT=3100
Environment=MCP_STACK_API_URL=http://127.0.0.1:8000
EnvironmentFile=/etc/mcp-stack/deployment.env
ExecStart=${node_path} /opt/mcp-stack/frontend/${server_subdir}/server.js
Restart=on-failure
RestartSec=2

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable mcp-stack-broker mcp-stack-api mcp-stack-web
systemctl reset-failed mcp-stack-broker mcp-stack-api mcp-stack-web || true
systemctl restart mcp-stack-broker
systemctl restart mcp-stack-api
systemctl restart mcp-stack-web
for service in \
  mcp-stack-broker \
  mcp-stack-api \
  mcp-stack-web; do
  if ! systemctl is-active --quiet "${service}"; then
    printf 'Installation failed: %s is not active.\n' "${service}" >&2
    exit 1
  fi
done
rm -rf "${install_stage}"
printf 'Installed dedicated MCPStack services. Open http://127.0.0.1:3100/stacks\n'
