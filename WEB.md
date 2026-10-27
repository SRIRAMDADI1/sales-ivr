# Firstpass Quotes web chat — local run + public Kubernetes deploy

Conversational agent front door for the Sales IVR. Customers can speak naturally, provide
details in any order, revise facts after a quote, and ask the agent to rerun the complete
pipeline for an updated customer-facing quote.

**Do not put API keys in this file or in the container image.** Use `.env` in the repo root
locally, or the `firstpass-openai` Kubernetes Secret on the cluster.

This guide deploys the existing `Dockerfile` to **Azure Kubernetes Service (AKS)**.
The public URL is an Azure load balancer in front of one pod.

---



## Part A — Run on your PC (optional)

```powershell
cd <this-repo>

# create venv once if needed
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"

.\.venv\Scripts\python.exe -m sales_ivr.web.app
```

Open: [http://127.0.0.1:8000](http://127.0.0.1:8000)

### Sample chat

1. Phone: `555-123-4001`
2. State: `CA`
3. ZIP: `90210`
4. Need: `I'd like a quote for auto insurance`
5. Details: `I drive a 2020 sedan about twelve thousand miles a year`
6. Confirm: `yes`

Live quotes need Azure OpenAI (key + endpoint + a **deployed** model matching `config.yaml` → `llm.deployment`). Without that, the app returns your input (passthrough).

---



## Part B — Public site on Kubernetes (AKS)

Use **one** PowerShell window. Run sections in order.

### What you need

1. [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli-windows) (`az version`)
2. [Docker Desktop](https://docs.docker.com/desktop/setup/install/windows-install/) (running, Linux containers)
3. An Azure subscription
4. `kubectl` — installed in B1 if `kubectl version --client` fails



### What Azure creates


| Resource                                 | Purpose                                          |
| ---------------------------------------- | ------------------------------------------------ |
| Resource group                           | Container for the cluster and registry           |
| Azure Container Registry (Basic)         | Stores the app image                             |
| AKS cluster (1 node, free control plane) | Runs the pod                                     |
| Public load balancer                     | `http://<dns-label>.<region>.cloudapp.azure.com` |


The load balancer URL is **HTTP** and is only for health checks. The public site is **https://sales.firstpassquotes.com**, a CNAME to `<dns-label>.<region>.cloudapp.azure.com`. HTTPS is provided in front of that name. Voice needs the HTTPS address.

---



### B1. Install Azure CLI, Docker, and kubectl (once)

1. Install Azure CLI: [https://learn.microsoft.com/cli/azure/install-azure-cli-windows](https://learn.microsoft.com/cli/azure/install-azure-cli-windows)
2. Install and start Docker Desktop.
3. Open a **new** PowerShell window and check:

```powershell
az version
docker version
```

If `kubectl` is missing:

```powershell
az aks install-cli
kubectl version --client
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

ACR name must be **globally unique**, 5–50 characters, letters and numbers only.
DNS label must be **globally unique** in that region (it becomes the public hostname).

```powershell
$SubscriptionId = "bc55f11d-f48a-476c-b9a4-21a1f009de48"
$Location       = "eastus"
$ResourceGroup  = "rg-firstpass"
$AcrName        = "firstpassacrsd1902"     # letters and numbers only
$AksName        = "firstpass-aks"
$DnsLabel       = "firstpass-chat-sd1902"  # load balancer hostname label

# Optional live OpenAI (leave empty for passthrough mode).
# Must be the resource root of the resource that owns config.yaml -> llm.deployment.
# Verify with: az cognitiveservices account deployment list -n <resource> -g <group> -o table
$AzureOpenAIKey      = ""   # paste KEY 1 locally; do not commit it
$AzureOpenAIEndpoint = "https://scd5583-0635-resource.openai.azure.com/"   # e.g. https://your-resource.openai.azure.com/
```

---



### B4. Go to the app folder

```powershell
cd <this-repo>
dir Dockerfile, k8s\deployment.yaml, k8s\service.yaml, config.yaml, sales_ivr
```

---



### B5. Register container providers (first-time subscriptions)

```powershell
az provider register --namespace Microsoft.ContainerService
az provider register --namespace Microsoft.ContainerRegistry
foreach ($ns in @("Microsoft.ContainerService", "Microsoft.ContainerRegistry")) {
  do {
    Start-Sleep -Seconds 10
    $state = az provider show -n $ns --query registrationState -o tsv
    Write-Host "$ns = $state"
  } while ($state -ne "Registered")
}
```

---



### B6. Create the resource group, registry, and cluster

Skip a command if that resource already exists.

Cluster create usually takes **5–10 minutes**. The control plane is free (`--tier free`). The node VM is billed until you delete the group (Part D).

```powershell
az group create --name $ResourceGroup --location $Location

az acr create `
  --name $AcrName `
  --resource-group $ResourceGroup `
  --sku Basic

az aks create `
  --name $AksName `
  --resource-group $ResourceGroup `
  --node-count 1 `
  --node-vm-size Standard_B2s `
  --tier free `
  --generate-ssh-keys `
  --attach-acr $AcrName
```

If `Standard_B2s` is unavailable in `$Location`, rerun `az aks create` with `--node-vm-size Standard_D2s_v3`.

If the ACR name is taken, change `$AcrName` and rerun `az acr create` and `az aks create`.

---



### B7. Build the image and push it to the registry

```powershell
cd <this-repo>
$Image = "$AcrName.azurecr.io/firstpass-quotes:latest"

az acr login --name $AcrName
docker build -t $Image .
docker push $Image
```

---



### B8. Point kubectl at the cluster and store the OpenAI secret

Empty key and endpoint are valid. The site still starts; quotes stay in passthrough until you set both.

```powershell
az aks get-credentials --resource-group $ResourceGroup --name $AksName --overwrite-existing

kubectl create secret generic firstpass-openai `
  --from-literal=AZURE_OPENAI_API_KEY="$AzureOpenAIKey" `
  --from-literal=AZURE_OPENAI_ENDPOINT="$AzureOpenAIEndpoint" `
  --dry-run=client -o yaml | kubectl apply -f -
```

---



### B9. Deploy the app and open the load balancer

`k8s/deployment.yaml` and `k8s/service.yaml` contain placeholders. The replace below fills them for this session only; it does not edit the files in git.

```powershell
cd <this-repo>

(Get-Content .\k8s\deployment.yaml -Raw) -replace 'REPLACE_ACR', $AcrName |
  kubectl apply -f -

(Get-Content .\k8s\service.yaml -Raw) -replace 'REPLACE_DNS_LABEL', $DnsLabel |
  kubectl apply -f -

kubectl rollout status deployment/firstpass-quotes --timeout=180s
```

Wait until the load balancer has an address (often 1–2 minutes):

```powershell
do {
  Start-Sleep -Seconds 10
  $Ip = kubectl get svc firstpass-quotes -o jsonpath="{.status.loadBalancer.ingress[0].ip}"
  Write-Host "LoadBalancer IP: $Ip"
} while (-not $Ip)

$Url = "http://$DnsLabel.$Location.cloudapp.azure.com"
Write-Host "Health: $Url/api/health"
Write-Host "Site:   https://sales.firstpassquotes.com"
Start-Process "https://sales.firstpassquotes.com"
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
kubectl get pods
kubectl describe deployment firstpass-quotes
kubectl logs deployment/firstpass-quotes --tail=80
```

Look for:

- Pod `Running` and `1/1` ready (good)
- `ImagePullBackOff` (bad — ACR name mismatch, or `az aks create` was run without `--attach-acr`)
- `CreateContainerConfigError` (bad — `firstpass-openai` secret missing; rerun B8)

---



### B11. (Optional) Google Search

`sales_ivr/web/static/sitemap.xml` and `sales_ivr/web/static/robots.txt` already use `https://sales.firstpassquotes.com`.

1. [Google Search Console](https://search.google.com/search-console) → add property → URL prefix `https://sales.firstpassquotes.com/`.
2. Submit sitemap `https://sales.firstpassquotes.com/sitemap.xml`.
3. Indexing can take days/weeks.

Google does **not** host the site — it only indexes that public URL.

---



## Part C — Redeploy after code changes

`:latest` is reused, so the deployment sets `imagePullPolicy: Always` and a restart pulls the new image.

```powershell
cd <this-repo>
$AcrName = "firstpassacrsd1902"
$Image = "$AcrName.azurecr.io/firstpass-quotes:latest"

az acr login --name $AcrName
docker build -t $Image .
docker push $Image

kubectl rollout restart deployment/firstpass-quotes
kubectl rollout status deployment/firstpass-quotes --timeout=180s
Invoke-RestMethod "http://firstpass-chat-sd1902.eastus.cloudapp.azure.com/api/health"
```

To change the OpenAI secret without rebuilding:

```powershell
kubectl create secret generic firstpass-openai `
  --from-literal=AZURE_OPENAI_API_KEY="$AzureOpenAIKey" `
  --from-literal=AZURE_OPENAI_ENDPOINT="$AzureOpenAIEndpoint" `
  --dry-run=client -o yaml | kubectl apply -f -

kubectl rollout restart deployment/firstpass-quotes
```

---



## Part D — Tear down (stop billing)

```powershell
az group delete --name rg-firstpass --yes --no-wait
```

That deletes the cluster, the node VM, the registry, and the public IP.

---



## Part E — Temporary demo URL only (not for Google)

With the local server already running on port 8000:

```powershell
npx localtunnel --port 8000
```

---



## Checklist


| Step                                       | Required?                |
| ------------------------------------------ | ------------------------ |
| Azure CLI                                  | Yes                      |
| Docker Desktop                             | **Yes**                  |
| `kubectl` (`az aks install-cli`)           | Yes                      |
| `docker build` + `docker push` to ACR      | **Yes** for every deploy |
| `k8s/deployment.yaml` + `k8s/service.yaml` | Yes                      |
| Part B cluster                             | Yes for a public site    |
| Azure OpenAI key + model deployment        | Yes for live quotes      |
| Google Search Console                      | Optional                 |




## API

- `POST /api/chat/start` → `{ session_id, reply, step }`
- `POST /api/chat/start?channel=voice` starts a spoken call (same agent, short replies)
- `POST /api/chat/message` → `{ reply, done, result, ... }`
- `GET /api/health`

