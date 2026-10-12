from property_triage import (
    InspectionReminder,
    MaintenanceRequest,
    PropertyWorkload,
    TenantDocument,
    triage_property_work,
)


class RecordingRouting:
    def __init__(self) -> None:
        self.excluded: list[str] | None = None

    def set_chat_routing(self, excluded_vendors: list[str]) -> None:
        self.excluded = excluded_vendors


class RecordingChat:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    def complete(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return "1. Dispatch a plumber to CEDAR-12 unit 4B."


def test_triage_uses_account_policy_and_one_model_request() -> None:
    workload = PropertyWorkload(
        maintenance_requests=[
            MaintenanceRequest(
                property_id="CEDAR-12",
                unit="4B",
                issue="Water below the kitchen sink",
                priority="urgent",
            )
        ],
        tenant_documents=[
            TenantDocument(
                property_id="CEDAR-12",
                unit="4B",
                document_name="renters insurance",
                expires_on="2026-10-08",
            )
        ],
        inspection_reminders=[
            InspectionReminder(
                property_id="CEDAR-12",
                inspection_type="annual fire safety",
                due_on="2026-10-03",
            )
        ],
    )
    routing = RecordingRouting()
    chat = RecordingChat()

    result = triage_property_work(
        workload,
        routing=routing,
        chat=chat,
        excluded_vendors=["vendor-under-maintenance"],
    )

    assert routing.excluded == ["vendor-under-maintenance"]
    assert len(chat.prompts) == 1
    assert "urgent: property CEDAR-12, unit 4B" in chat.prompts[0]
    assert "renters insurance expires 2026-10-08" in chat.prompts[0]
    assert "annual fire safety due 2026-10-03" in chat.prompts[0]
    assert result == "1. Dispatch a plumber to CEDAR-12 unit 4B."
