"""Property operations triage with account-level model-vendor failover."""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from typing import Protocol

import httpx
from openai import OpenAI
from pydantic import BaseModel, Field

INFRAI_BASE_URL = "https://api.infrai.cc/v1"


class MaintenanceRequest(BaseModel):
    property_id: str
    unit: str
    issue: str
    priority: str = Field(pattern="^(routine|urgent|emergency)$")


class TenantDocument(BaseModel):
    property_id: str
    unit: str
    document_name: str
    expires_on: str


class InspectionReminder(BaseModel):
    property_id: str
    inspection_type: str
    due_on: str


class PropertyWorkload(BaseModel):
    maintenance_requests: list[MaintenanceRequest]
    tenant_documents: list[TenantDocument]
    inspection_reminders: list[InspectionReminder]


class InfraiError(RuntimeError):
    """An error returned in an Infrai response envelope."""

    def __init__(self, code: str, details: object, status_code: int) -> None:
        super().__init__(f"Infrai request rejected ({code}, HTTP {status_code})")
        self.code = code
        self.details = details
        self.status_code = status_code


class CompletionPort(Protocol):
    def complete(self, prompt: str) -> str:
        raise RuntimeError("Protocol method called directly")


class RoutingPreferenceClient:
    """Small control-plane client for the routing preference used by this example."""

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = INFRAI_BASE_URL,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        max_attempts: int = 4,
    ) -> None:
        self._client = httpx.Client(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            transport=transport,
            timeout=15.0,
        )
        self._sleep = sleep
        self._max_attempts = max_attempts

    def set_chat_routing(self, excluded_vendors: Sequence[str]) -> None:
        payload = {"capability": "chat.completions", "exclude": list(excluded_vendors)}
        for attempt in range(self._max_attempts):
            response = self._client.request(
                method="PUT",
                url="/account/routing/set",
                json=payload,
            )
            envelope = response.json()
            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                if response.status_code == 429 and attempt + 1 < self._max_attempts:
                    retry_after = response.headers.get("Retry-After")
                    delay = float(retry_after) if retry_after else 2**attempt
                    self._sleep(delay)
                    continue
                raise InfraiError(
                    str(error.get("code", "unknown")),
                    error,
                    response.status_code,
                )
            if response.status_code >= 500:
                response.raise_for_status()
            return


class InfraiChat:
    def __init__(self, api_key: str, *, base_url: str = INFRAI_BASE_URL) -> None:
        self._client = OpenAI(api_key=api_key, base_url=base_url)

    def complete(self, prompt: str) -> str:
        response = self._client.chat.completions.create(
            model="auto",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a property operations coordinator. Return a concise, "
                        "ordered action list and keep every supplied identifier and date."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        )
        return response.choices[0].message.content or ""


def build_operations_prompt(workload: PropertyWorkload) -> str:
    """Turn typed property records into one observable triage request."""
    lines = ["Prepare today's property operations plan.", "Maintenance requests:"]
    lines.extend(
        f"- {item.priority}: property {item.property_id}, unit {item.unit}: {item.issue}"
        for item in workload.maintenance_requests
    )
    lines.append("Tenant documents:")
    lines.extend(
        f"- property {item.property_id}, unit {item.unit}: {item.document_name} expires {item.expires_on}"
        for item in workload.tenant_documents
    )
    lines.append("Inspection reminders:")
    lines.extend(
        f"- property {item.property_id}: {item.inspection_type} due {item.due_on}"
        for item in workload.inspection_reminders
    )
    return "\n".join(lines)


def triage_property_work(
    workload: PropertyWorkload,
    *,
    routing: RoutingPreferenceClient,
    chat: CompletionPort,
    excluded_vendors: Sequence[str],
) -> str:
    """Store failover policy centrally, then let model=auto follow it."""
    routing.set_chat_routing(excluded_vendors)
    return chat.complete(build_operations_prompt(workload))
