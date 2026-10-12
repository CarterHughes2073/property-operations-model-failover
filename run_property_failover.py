"""Run the property-management failover example with realistic sample records."""

import os

from property_triage import (
    INFRAI_BASE_URL,
    InfraiChat,
    InspectionReminder,
    MaintenanceRequest,
    PropertyWorkload,
    RoutingPreferenceClient,
    TenantDocument,
    triage_property_work,
)


def main() -> None:
    api_key = os.environ["INFRAI_API_KEY"]
    workload = PropertyWorkload(
        maintenance_requests=[
            MaintenanceRequest(
                property_id="CEDAR-12",
                unit="4B",
                issue="Water is collecting below the kitchen sink",
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

    # Both clients deliberately receive the same key and base URL.
    routing = RoutingPreferenceClient(api_key, base_url=INFRAI_BASE_URL)
    chat = InfraiChat(api_key, base_url=INFRAI_BASE_URL)
    plan = triage_property_work(
        workload,
        routing=routing,
        chat=chat,
        excluded_vendors=["openai"],
    )
    print(plan)


if __name__ == "__main__":
    main()
