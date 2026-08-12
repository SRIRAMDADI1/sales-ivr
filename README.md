# Sales IVR (LLM agents)

Insurance sales IVR platform driven by **real LLM agents** (Azure OpenAI by default),
with tools for CRM, catalog, pricing, and compliance.

Optional: token usage can be flushed to a TelemetryBot collector when `telemetry.yaml`
points at a running collector and the `agentelemetry` SDK is installed (soft-fail otherwise).

## Quick start

```powershell
cd sales-ivr
python -m venv .venv
.\.venv\Scripts\activate
pip install -e ".[dev]"
copy .env.example .env
# edit .env — set AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT
python -m pytest
python -m sales_ivr.cli auto_quote_ca.json
python -m sales_ivr.web.app
```

Web UI: http://127.0.0.1:8000

## Azure OpenAI setup (do this once)

### 1. Create an Azure OpenAI resource

1. Open [https://portal.azure.com](https://portal.azure.com) and sign in.
2. Click **Create a resource** → search **Azure OpenAI** → **Create**.
3. Fill in:
   - Subscription: your credit subscription
   - Resource group: create `rg-sales-ivr` (or any name)
   - Region: pick one that supports your model (e.g. East US, Sweden Central)
   - Name: e.g. `sales-ivr-openai`
   - Pricing tier: Standard S0
4. **Review + create** → **Create**. Wait until deployment finishes.

> If you get "Request access": Azure OpenAI may still require a one-time access
> request for some subscriptions. Complete the form if prompted, then retry.

### 2. Deploy a model

1. Open your Azure OpenAI resource in the portal.
2. Click **Model deployments** / **Go to Azure AI Foundry** (or OpenAI Studio).
3. **Deploy model** → **Deploy base model**.
4. Choose a chat model (e.g. **gpt-4o-mini** for demos).
5. Set **Deployment name** to match `config.yaml` → `llm.deployment`.
6. Deploy.

### 3. Copy endpoint + API key

1. Back in the Azure portal → your OpenAI resource.
2. Left menu: **Keys and Endpoint**.
3. Copy:
   - **Endpoint** (e.g. `https://sales-ivr-openai.openai.azure.com/`)
   - **KEY 1**

> **The key and endpoint must come from the same resource that owns the deployment.**
> Foundry can show a deployment as `Succeeded` while your endpoint points at a different
> resource — Azure then answers every request with `404 DeploymentNotFound` and this app
> falls back to passthrough.

Only the resource root belongs in `AZURE_OPENAI_ENDPOINT`. Do not paste the full target URI
shown on a Foundry deployment page — the SDK appends
`/openai/deployments/<name>/chat/completions` itself, so a full URL produces a 404.

### 4. Store credentials once

**Option A — `.env` (recommended)**

```powershell
copy .env.example .env
# edit .env and set AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT
```

**Option B — `config.local.yaml`**

```powershell
copy config.local.yaml.example config.local.yaml
# edit: set llm.api_key, llm.endpoint, llm.provider: azure
```

Both files are gitignored. Do **not** put real keys in `config.yaml`.

Shell env still works if you prefer:

```powershell
$env:AZURE_OPENAI_API_KEY = "<KEY 1>"
$env:AZURE_OPENAI_ENDPOINT = "https://your-resource-name.openai.azure.com/"
```

Ensure `config.yaml` `llm.deployment` matches your Azure deployment name.

### 5. Verify

```powershell
pip install -e ".[dev]"
python -m sales_ivr.cli auto_quote_ca.json
```

You should see `llm_calls:` with real token counts.

## Without Azure credentials

There is **no mock LLM**. If `provider` is not `azure`, the API key/endpoint are missing,
or the model **deployment does not exist**, `run_session` returns the **input state unchanged**
(passthrough). The web chat echoes your answers and explains what to fix.

```bash
python -m pytest
python -m sales_ivr.cli auto_quote_ca.json
```

## CLI & batch

```bash
python -m sales_ivr.cli auto_quote_ca.json
python -m sales_ivr.cli auto_quote_ca.json --json
python run_batch.py
```

## Web conversation agent

```bash
sales-ivr-web
# or: python -m sales_ivr.web.app
# open http://127.0.0.1:8000
```

The web agent accepts details in any order, answers open-ended messages, and keeps the
conversation active after quoting. When the customer requests a quote or changes details and
asks for a revision, it builds a fresh session JSON and reruns the complete agent pipeline.

Public deploy (**no Docker**): [WEB.md](WEB.md)

## Optional telemetry

`sales_ivr/telemetry.py` soft-fails if the SDK or collector is unavailable. To enable:

1. Install a TelemetryBot-compatible `agentelemetry` package into this venv.
2. Point `telemetry.yaml` at your collector (`collector_url`, `api_key`, `project_id`).

Without that, quoting and chat still work normally.

## Architecture

Each of the 8 LangGraph nodes is an LLM agent that:

1. Receives session JSON context
2. Optionally calls tools (`lookup_crm`, `list_products`, `calculate_premium`, `load_compliance`, …)
3. Returns structured JSON applied to `IVRState`
4. Records `LLMUsage` (tokens, latency, tool_calls) on the state

## Input / output

**Input:** fixture JSON under `sales_ivr/fixtures/sessions/`  
**Output:** enriched `IVRState` with quote/handoff + `llm_usage[]`
