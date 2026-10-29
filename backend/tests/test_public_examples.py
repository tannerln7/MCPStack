import subprocess
from pathlib import Path

import yaml

from mcp_stack.tunnels.repository import TunnelProfileRepository


def test_generic_tunnel_examples_are_valid(repository_root: Path, tmp_path: Path) -> None:
    root = tmp_path / "profiles"
    root.mkdir(mode=0o700)
    for example in (repository_root / "config/tunnel-profiles").glob("*.yaml"):
        destination = root / example.name
        destination.write_bytes(example.read_bytes())
        destination.chmod(0o600)
    profiles = TunnelProfileRepository(root).list()

    assert len(profiles) == 2
    assert all(item.valid for item in profiles)
    assert {item.profile.target.kind for item in profiles} == {"stdio", "http"}
    for item in profiles:
        assert item.profile.tunnel_id.startswith("tunnel_example_")
        document = yaml.safe_load((root / item.path).read_text())
        assert document["control_plane"]["api_key"] == "env:CONTROL_PLANE_API_KEY"


def test_private_inputs_are_ignored_but_examples_are_shareable(repository_root: Path) -> None:
    private = [
        ".env",
        "config.local/stacks/private.yaml",
        "config/stacks/private.yaml",
        "config/environments/private/mise.toml",
        "config/tunnel-profiles/private.yaml",
        "scripts/install-private-stack.sh",
    ]
    for path in private:
        result = subprocess.run(
            ["git", "check-ignore", "--no-index", "--quiet", path],
            cwd=repository_root,
            check=False,
            timeout=5,
        )
        assert result.returncode == 0, path

    public = [
        ".env.example",
        "scripts/install-service.sh",
        "config/environments/example-stdio/mise.toml",
        *[
            str(path.relative_to(repository_root))
            for path in (repository_root / "config/stacks").glob("*.yaml")
        ],
        "config/tunnel-profiles/example-http.yaml",
        "config/tunnel-profiles/example-stdio.yaml",
    ]
    for path in public:
        result = subprocess.run(
            ["git", "check-ignore", "--no-index", "--quiet", path],
            cwd=repository_root,
            check=False,
            timeout=5,
        )
        assert result.returncode == 1, path


def test_base_installer_refuses_legacy_example_copy_without_mutation(repository_root: Path):
    import os

    result = subprocess.run(
        ["bash", str(repository_root / "scripts/install-service.sh")],
        env={**os.environ, "MCP_STACK_MIGRATE_CONFIG": "1"},
        capture_output=True,
        text=True,
        check=False,
        timeout=5,
    )
    assert result.returncode == 2
    assert "no longer supported" in result.stderr
    assert result.stdout == ""
