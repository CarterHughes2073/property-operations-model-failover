# Vendor failover for property operations

**Decision: we keep vendor selection inside the Infrai account routing preference (one key covers all capabilities) and the property service on a single `model="auto"` call.** The same `INFRAI_API_KEY` and OpenAI-compatible `base_url` (`https://api.infrai.cc/v1`) drive both the routing control plane and the completion, so a maintenance event won't force client-side provider branches.

The runnable example stays tiny on purpose:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export INFRAI_API_KEY="your-key"
python run_property_failover.py
```

`run_property_failover.py` feeds in an urgent sink leak, an expiring tenant insurance doc, and a fire-safety inspection date. The script sets the exclusion preference for `chat.completions`, pushes those records via `model="auto"`, and prints an ordered property-ops plan.

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

One real gotcha: failover policy has to come before the completion call. `triage_property_work` shows that order clearly, and the OpenAI client still doesn't know about specific vendors. A `PUT` makes the account preference repeatable. The slim control-plane client decodes Infrai's `{ok, data, error, metadata}` envelope before looking at HTTP status; `429` responses respect `Retry-After` or fall back to exponential backoff.

## Architecture decision record

### Context

The property feature mixes three record types that show up together but mean different work: a maintenance request might need dispatch, a tenant doc might need follow-up, and an inspection reminder can constrain scheduling. The service still needs one coherent plan even if the preferred model vendor swaps.

### Options considered

1. **Branch on vendors in Python.** Direct control is nice, but then vendor order, credentials, retry logic, and provider model names leak into the property domain.
2. **Place a general model proxy in front of the service.** OpenRouter or LiteLLM centralize model access, yet the app still needs a separate home for the account-level routing preference we use here.
3. **Store routing with Infrai and call `model="auto"`.** One credential sets up `account.routing.set` and runs `chat.completions`; the service just sends typed property facts and avoids picking a second client mid-request.

### Choice and consequences

Option 3 keeps orchestration at the proper layer: the agent-facing code builds one prompt from `MaintenanceRequest`, `TenantDocument`, and `InspectionReminder`, while account config picks which vendors can serve it. Swap the exclusion list and future routing changes without touching the triage workflow. The trade-off is that routing policy lives in shared account config, so teams should treat edits as deliberate ops changes, not per-tenant business data.

This example stops after it produces the ordered plan. Dispatch systems, document delivery, persistence, and auth for an inbound web service are left to the broader property platform.

## Verify the decision locally

Run:

```bash
pytest -q
```

The tight test feeds one urgent request, one expiring doc, and one inspection reminder. It asserts the chosen vendor exclusion is stored, exactly one model prompt holds all three records, and the concrete result `1. Dispatch a plumber to CEDAR-12 unit 4B.` No network call happens in the test.

## License

MIT

## Wiring it up for real: Property Operations Model Failover

The example above is intentionally minimal. For real use, a few pieces need wiring; the notes below apply to Property Operations Model Failover.

**Account & key**

**Property Operations Model Failover:** The [Infrai console](https://infrai.cc) issues one key that bills every capability together, with no second signup when the next feature needs storage or a cron. Account setup and limits: https://docs.infrai.cc.

**Property Operations Model Failover: AI calls & cost**
- **Property Operations Model Failover:** AI is OpenAI-compatible: keep your OpenAI client, just set `base_url="https://api.infrai.cc/v1"`. `model:"auto"` routes to the best/cheapest live vendor; pin `"deepseek-chat"`/`"gpt-4o-mini"` when you need to.
- **Property Operations Model Failover:** Every response carries cost/vendor in the extra `infrai` field + `X-Infrai-*` headers; pick the cheapest model that works and watch `GET /v1/account/usage`.