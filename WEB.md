# Firstpass Quotes web chat — local run + public Azure deploy (**no Docker**)

Conversational agent front door for the Sales IVR. Customers can speak naturally, provide
details in any order, revise facts after a quote, and ask the agent to rerun the complete
pipeline for an updated customer-facing quote.

**Do not put API keys in this file.** Use `.env` in the repo root locally, or App Settings in Azure.

This guide deploys with **Azure App Service (Python)** + zip upload.  
**Docker Desktop is not required.**

---

## Why Azure kept returning 503 (`No module named 'sales_ivr'`)

This failed repeatedly for **three stacked reasons**. All are fixed in this folder; follow Part B exactly.

### 1. PowerShell `Compress-Archive` builds a Linux-broken zip

`Compress-Archive` stores entries like `sales_ivr\__init__.py` (backslashes).  
Azure App Service runs **Linux**. Unzip/Oryx then often **does not** create a real `sales_ivr/` package directory. Gunicorn starts, then dies:

```text
ModuleNotFoundError: No module named 'sales_ivr'
```

**Fix:** always build the zip with `pack_azure_zip.py` (forward-slash paths). Never use `Compress-Archive` for this deploy.

### 2. Oryx runs the app from `/tmp/...`, not from wwwroot

With `SCM_DO_BUILD_DURING_DEPLOYMENT=true`, Oryx builds `antenv`, writes `output.tar.zst`, and at cold start extracts to `/tmp/<id>/`. It sets `PYTHONPATH` to **only** the venv site-packages. Your package is a sibling folder next to `antenv`, so it is **not** importable unless startup adds that folder to `PYTHONPATH`.

Hardcoding `--pythonpath /home/site/wwwroot` is wrong for compressed builds.

**Fix:** `startup.sh` derives `APP_ROOT` from the live `antenv` path on `sys.path`, then runs `gunicorn ... app:app` with `--chdir` / `--pythonpath` set to that root. Root `app.py` is the ASGI entry.

### 3. wwwroot can contain a *broken* leftover `sales_ivr/` folder

Older startup logic did `[ -d /home/site/wwwroot/sales_ivr ]` and treated that as success. After Oryx compress, that directory can be empty/incomplete. Startup then pointed gunicorn at wwwroot → same `ModuleNotFoundError` → Azure marks the site failed → **503** → after a few crashes Azure **blocks** restarts for 1–2 minutes.

**Fix:** never trust “directory exists”; require `import app` / `import sales_ivr` before binding the port.

---

## Part A — Run on your PC (optional)

```powershell
cd <this-repo>

# create venv once if needed
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"

.\.venv\Scripts\python.exe -m sales_ivr.web.app
```

Open: http://127.0.0.1:8000

### Sample chat

1. Phone: `555-123-4001`
2. State: `CA`
3. ZIP: `90210`
4. Need: `I'd like a quote for auto insurance`
5. Details: `I drive a 2020 sedan about twelve thousand miles a year`
6. Confirm: `yes`

Live quotes need Azure OpenAI (key + endpoint + a **deployed** model matching `config.yaml` → `llm.deployment`). Without that, the app returns your input (passthrough).

---

## Part B — Public site on Azure (no Docker)

Use **one** PowerShell window. Run sections in order.

### What you need

1. [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli-windows) (`az version`)
2. An Azure subscription
3. **Not** Docker Desktop

### What Azure creates

| Resource | Purpose |
|----------|---------|
| Resource group | Container for the app |
| App Service plan (Linux B1) | Compute |
| Web App (Python 3.12) | Public HTTPS URL |

---

### B1. Install Azure CLI (once)

1. Install: https://learn.microsoft.com/cli/azure/install-azure-cli-windows  
2. Open a **new** PowerShell window  
3. Check:

```powershell
az version
```

---

### B2. Login and pick subscription

If `az` says the refresh token expired, run `az login` again before anything else.

```powershell
az login
az account list -o table
az account set --subscription "<PASTE-SUBSCRIPTION-ID>"
az account show -o table
```

---

### B3. Set names (edit, then keep this window open)

Web app name must be **globally unique** (becomes `https://NAME.azurewebsites.net`).

```powershell
$SubscriptionId = "<PASTE-SUBSCRIPTION-ID>"
$Location       = "eastus"
$ResourceGroup  = "rg-harborline"
$PlanName       = "harborline-plan"
$WebAppName     = "harborline-chat-sd1902"   # change if taken

# Optional live OpenAI (leave empty for passthrough mode)
# Must be the resource root of the resource that owns config.yaml -> llm.deployment.
# Verify with: az cognitiveservices account deployment list -n <resource> -g <group> -o table
$AzureOpenAIKey      = ""
$AzureOpenAIEndpoint = ""   # e.g. https://your-resource.openai.azure.com/
```

---

### B4. Go to the app folder

```powershell
cd <this-repo>
dir app.py, pack_azure_zip.py, requirements.txt, startup.sh, config.yaml, sales_ivr
```

---

### B5. Register App Service provider (first-time subscriptions)

```powershell
az provider register --namespace Microsoft.Web
do {
  Start-Sleep -Seconds 10
  $state = az provider show -n Microsoft.Web --query registrationState -o tsv
  Write-Host "Microsoft.Web = $state"
} while ($state -ne "Registered")
```

---

### B6. Create resource group + Linux plan + Python Web App

Skip `az group create` / `az appservice plan create` / `az webapp create` if they already exist (e.g. you already use `harborline-chat-sd1902`).

```powershell
az group create --name $ResourceGroup --location $Location

az appservice plan create `
  --name $PlanName `
  --resource-group $ResourceGroup `
  --is-linux `
  --sku B1

az webapp create `
  --name $WebAppName `
  --resource-group $ResourceGroup `
  --plan $PlanName `
  --runtime "PYTHON:3.12"
```

If the name is taken, change `$WebAppName` and re-run only `az webapp create`.

---

### B7. Configure startup + build + env vars

```powershell
az webapp config set `
  --name $WebAppName `
  --resource-group $ResourceGroup `
  --startup-file "startup.sh"

$settings = @(
  "SCM_DO_BUILD_DURING_DEPLOYMENT=true"
  "ENABLE_ORYX_BUILD=true"
  "WEBSITES_PORT=8000"
)
if ($AzureOpenAIKey -and $AzureOpenAIEndpoint) {
  $settings += "AZURE_OPENAI_API_KEY=$AzureOpenAIKey"
  $settings += "AZURE_OPENAI_ENDPOINT=$AzureOpenAIEndpoint"
}

az webapp config appsettings set `
  --name $WebAppName `
  --resource-group $ResourceGroup `
  --settings $settings
```

Do **not** set `SALES_IVR_CONFIG_PATH` to wwwroot; `startup.sh` sets it next to the extracted package.

---

### B8. Stop the site, build a Linux-safe zip, deploy

Stopping first avoids Azure’s crash-loop / “site blocked” while you upload a new package.

```powershell
cd <this-repo>

az webapp stop --name $WebAppName --resource-group $ResourceGroup

# REQUIRED: Linux-safe zip (forward slashes). Do NOT use Compress-Archive.
python .\pack_azure_zip.py

az webapp deploy `
  --name $WebAppName `
  --resource-group $ResourceGroup `
  --src-path ..\harborline-deploy.zip `
  --type zip
```

First deploy (and any deploy that reinstalls wheels) can take **5–15 minutes** while Oryx runs `pip install -r requirements.txt`. Wait until `az webapp deploy` prints success. Do not health-check mid-deploy.

---

### B9. Start the site and open it

```powershell
# If Azure previously blocked cold starts, wait out the block window
Start-Sleep -Seconds 130

az webapp start --name $WebAppName --resource-group $ResourceGroup

$Url = "https://$WebAppName.azurewebsites.net"
Write-Host "Site:   $Url"
Write-Host "Health: $Url/api/health"

# Cold start + Oryx extract often needs a minute
Start-Sleep -Seconds 90
Start-Process $Url
```

---

### B10. Verify

```powershell
Invoke-RestMethod "$Url/api/health"
```

Expected:

```json
{"status":"ok","service":"firstpass-quotes"}
```

If it fails:

```powershell
az webapp log startup show --name $WebAppName --resource-group $ResourceGroup
```

Look for:

- `Firstpass startup: APP_ROOT=/tmp/...` (good)
- `cannot import app/sales_ivr` or `ModuleNotFoundError` (bad — usually means B8 used `Compress-Archive` or an old zip)

---

### B11. (Optional) Google Search

1. Public URL from B9 is enough to share immediately.
2. Optional custom domain: Portal → Web App → Custom domains.
3. Edit `sales_ivr/web/static/sitemap.xml` (replace `REPLACE_WITH_YOUR_PUBLIC_URL`), redeploy (Part C).
4. [Google Search Console](https://search.google.com/search-console) → add property → submit sitemap.
5. Indexing can take days/weeks.

Google does **not** host the site — it only indexes your Azure URL.

---

## Part C — Redeploy after code changes

```powershell
cd <this-repo>
$WebAppName = "harborline-chat-sd1902"
$ResourceGroup = "rg-harborline"

az webapp stop --name $WebAppName --resource-group $ResourceGroup
python .\pack_azure_zip.py

az webapp deploy `
  --name $WebAppName `
  --resource-group $ResourceGroup `
  --src-path ..\harborline-deploy.zip `
  --type zip

Start-Sleep -Seconds 130
az webapp start --name $WebAppName --resource-group $ResourceGroup
Start-Sleep -Seconds 90
Invoke-RestMethod "https://$WebAppName.azurewebsites.net/api/health"
```

---

## Part D — Tear down (stop billing)

```powershell
az group delete --name rg-harborline --yes --no-wait
```

---

## Part E — Temporary demo URL only (not for Google)

With the local server already running on port 8000:

```powershell
npx localtunnel --port 8000
```

---

## Checklist

| Step | Required? |
|------|-----------|
| Azure CLI | Yes |
| Docker Desktop | **No** |
| `python .\pack_azure_zip.py` (not Compress-Archive) | **Yes** for every deploy |
| Part B deploy | Yes for a public HTTPS site |
| Azure OpenAI key + model deployment | Yes for live quotes |
| Google Search Console | Optional |

## API

- `POST /api/chat/start` → `{ session_id, reply, step }`
- `POST /api/chat/message` → `{ reply, done, result, ... }`
- `GET /api/health`
