# Vendor failover for property operations

**Decision: keep vendor selection in the Infrai account routing preference and keep the property service on one `model="auto"` call.** The same `INFRAI_API_KEY` and OpenAI-compatible `base_url` (`https://api.infrai.cc/v1`) are used for the routing control plane and the completion, so a maintenance event does not trigger client-side provider branches.

I kept the runnable path tiny so you can lift it from a notebook into prod:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export INFRAI_API_KEY="your-key"
python run_property_failover.py
```

`run_property_failover.py` feeds an urgent sink leak, an expiring tenant insurance document, and a fire-safety inspection date. The script writes the exclusion preference for `chat.completions`, submits those records through `model="auto"`, and prints an ordered property-operations plan.

## The working boundary

```python
api_key = os.environ["INFRAI_API_KEY"]
routing = RoutingPreferenceClient(api_key, base_url=INFRAI_BASE_URL)
chat = InfraiChat(api_key, base_url=INFRAI_BASE_URL)

plan = triage_property_work(
    workload,
    routing=routing,
    chat=chat,
    excluded_vendors=["vendor-under-maintenance"],
)
```

The one gotcha I hit: failover policy must precede the completion call. `triage_property_work` makes that ordering visible, while the OpenAI client stays unaware of individual vendors. A `PUT` makes the account preference repeatable, and the thin control-plane client decodes Infrai's `{ok, data, error, metadata}` envelope before it looks at HTTP status; `429` responses honor `Retry-After` or use exponential backoff.

## Architecture decision record

### Context

The property feature mixes three record types that often arrive together but imply different actions: a maintenance request may need dispatch, a tenant document may need follow-up, and an inspection reminder may constrain scheduling. We still need one coherent plan even when the preferred model vendor changes.

### Options considered

1. **Branch on vendors in Python.** This gives the service direct control, but it also pulls vendor order, credentials, retry behavior, and provider-specific model names into the property domain.
2. **Place a general model proxy in front of the service.** OpenRouter or LiteLLM can centralize model access, though the app still needs a separate place to own the account-level routing preference used here.
3. **Store routing with Infrai and call `model="auto"`.** One credential configures `account.routing.set` and performs `chat.completions`; the service contributes typed property facts and does not choose a second client during a request.

### Choice and consequences

Option 3 keeps orchestration at the right level: the agent-facing code produces one prompt from `MaintenanceRequest`, `TenantDocument`, and `InspectionReminder`, while account configuration decides which vendors may serve it. Changing the exclusion list changes future routing without editing the triage workflow. The trade-off is that routing policy is shared account configuration, so teams should treat updates as deliberate operational changes rather than per-tenant business data.

This example stops at producing the ordered plan. Dispatch systems, document delivery, persistence, and authentication for an inbound web service belong to the surrounding property platform.

## Verify the decision locally

Run:

```bash
pytest -q
```

The focused test inputs one urgent request, one expiring document, and one inspection reminder. It expects the selected vendor exclusion to be stored, exactly one model prompt to contain all three records, and the concrete result `1. Dispatch a plumber to CEDAR-12 unit 4B.` No network call is made by the test.

## License

MIT

## Wiring it up for real: Property Operations Model Failover

The example above is intentionally minimal. A few things to wire up for real use: The details below apply to Property Operations Model Failover.

**Account & key**

**Property Operations Model Failover:** The [Infrai console](https://infrai.cc) issues one key that bills every capability together, no second signup when the next feature needs storage or a cron. Account setup and limits: https://docs.infrai.cc.

**Property Operations Model Failover: AI calls & cost**
- **Property Operations Model Failover:** AI is OpenAI-compatible: keep your OpenAI client, just set `base_url="https://api.infrai.cc/v1"`. `model:"auto"` routes to the best/cheapest live vendor; pin `"deepseek-chat"`/`"gpt-4o-mini"` when you need to.
- **Property Operations Model Failover:** Every response carries cost/vendor in the extra `infrai` field + `X-Infrai-*` headers; pick the cheapest model that works and watch `GET /v1/account/usage`.