from __future__ import annotations

import time
from datetime import UTC, datetime
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener

from mcp_stack.configuration import StackRecord
from mcp_stack.domain.configuration import (
    ApplicationEndpoint,
    ComponentTarget,
    ConfiguredEndpoint,
    EndpointTarget,
    TunnelTarget,
)
from mcp_stack.domain.observations import HealthObservation, RuntimeSnapshot
from mcp_stack.lifecycle import LifecycleService

# Health checks describe their exact destination in trusted configuration.  Do
# not let ambient HTTP proxy variables redirect local control-plane probes.
_http_opener = build_opener(ProxyHandler({}))


class HealthService:
    def __init__(self, lifecycle: LifecycleService) -> None:
        self._lifecycle = lifecycle

    def observations_for(
        self, record: StackRecord, runtime: RuntimeSnapshot
    ) -> list[HealthObservation]:
        return [
            self._observe(record, check, runtime) for check in record.configuration.health_checks
        ]

    def _observe(self, record: StackRecord, check, runtime: RuntimeSnapshot) -> HealthObservation:
        observed_at = datetime.now(UTC)
        started = time.monotonic()
        if check.probe == "process-running" and isinstance(check.target, ComponentTarget):
            component = next(
                (
                    item
                    for item in runtime.components
                    if item.component_id == check.target.component_ref
                ),
                None,
            )
            passing = component is not None and component.status == "running"
            return HealthObservation(
                health_check_ref=check.id,
                status="passing" if passing else "failing",
                observed_at=observed_at,
                reason="managed process is active" if passing else "managed process is not active",
                latency_ms=(time.monotonic() - started) * 1000,
            )
        if check.probe == "http" and isinstance(check.target, EndpointTarget):
            url = self._endpoint_url(record, check.target.endpoint_ref)
            if url is None:
                return self._unknown(check.id, observed_at, "configured endpoint cannot be probed")
            try:
                request = Request(url, method="GET", headers={"User-Agent": "mcp-stack-health/1"})
                with _http_opener.open(request, timeout=check.timeout_seconds or 5) as response:
                    expected = check.expected_status or 200
                    passing = response.status == expected
                return HealthObservation(
                    health_check_ref=check.id,
                    status="passing" if passing else "failing",
                    observed_at=observed_at,
                    reason="HTTP probe matched expected status"
                    if passing
                    else "HTTP probe returned an unexpected status",
                    latency_ms=(time.monotonic() - started) * 1000,
                )
            except HTTPError as error:
                passing = error.code == (check.expected_status or 200)
                return HealthObservation(
                    health_check_ref=check.id,
                    status="passing" if passing else "failing",
                    observed_at=observed_at,
                    reason="HTTP probe matched expected status"
                    if passing
                    else "HTTP probe returned an unexpected status",
                    latency_ms=(time.monotonic() - started) * 1000,
                )
            except (OSError, URLError, TimeoutError):
                return HealthObservation(
                    health_check_ref=check.id,
                    status="failing",
                    observed_at=observed_at,
                    reason="HTTP probe could not reach the configured endpoint",
                    latency_ms=(time.monotonic() - started) * 1000,
                )
        if check.probe == "tunnel-connected" and isinstance(check.target, TunnelTarget):
            component = next(
                (
                    item
                    for item in record.configuration.components
                    if getattr(item.subject, "tunnel_ref", None) == check.target.tunnel_ref
                ),
                None,
            )
            observation = (
                self._lifecycle.observation_for(record, component.id) if component else None
            )
            passing = observation is not None and observation.state == "active"
            return HealthObservation(
                health_check_ref=check.id,
                status="passing" if passing else "failing",
                observed_at=observed_at,
                reason="tunnel process is active" if passing else "tunnel process is not active",
                latency_ms=(time.monotonic() - started) * 1000,
            )
        return self._unknown(
            check.id, observed_at, "probe is not observable without protocol activity"
        )

    @staticmethod
    def _unknown(check_id: str, observed_at: datetime, reason: str) -> HealthObservation:
        return HealthObservation(
            health_check_ref=check_id,
            status="unknown",
            observed_at=observed_at,
            reason=reason,
        )

    @staticmethod
    def _endpoint_url(record: StackRecord, endpoint_id: str) -> str | None:
        endpoint = next(
            (item for item in record.configuration.endpoints if item.id == endpoint_id), None
        )
        if isinstance(endpoint, ConfiguredEndpoint):
            return endpoint.url
        if isinstance(endpoint, ApplicationEndpoint):
            listener = endpoint.listener
            return f"{listener.scheme}://{listener.host}:{listener.port}{listener.path}"
        return None
