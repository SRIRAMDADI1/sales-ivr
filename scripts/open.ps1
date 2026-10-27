# Bring https://sales.firstpassquotes.com back after scripts/close.ps1.
# Recreates the Basic registry, builds and pushes the image, creates the free-tier
# AKS cluster, restores the OpenAI secret from .env, and applies the manifests.
# Cluster create is usually 5-10 minutes. Run this before the site needs to be up.
# Standard_B2s and Standard_D2s_v3 are not allowed in this subscription in eastus.

$ErrorActionPreference = "Stop"

$SubscriptionId = "bc55f11d-f48a-476c-b9a4-21a1f009de48"
$Location       = "eastus"
$ResourceGroup  = "rg-firstpass"
$AcrName        = "firstpassacrsd1902"
$AksName        = "firstpass-aks"
$DnsLabel       = "firstpass-chat-sd1902"
$NodeVmSize     = "Standard_D2s_v4"
$RepoRoot       = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

function Import-DotEnv {
  param([string]$Path)
  if (-not (Test-Path $Path)) { return }
  foreach ($line in Get-Content $Path) {
    $trimmed = $line.Trim()
    if (-not $trimmed -or $trimmed.StartsWith("#")) { continue }
    $parts = $trimmed -split "=", 2
    if ($parts.Count -ne 2) { continue }
    $name = $parts[0].Trim()
    $value = $parts[1].Trim().Trim('"').Trim("'")
    if (-not (Test-Path "Env:$name") -or [string]::IsNullOrWhiteSpace((Get-Item "Env:$name").Value)) {
      Set-Item -Path "Env:$name" -Value $value
    }
  }
}

Import-DotEnv (Join-Path $RepoRoot ".env")

if ([string]::IsNullOrWhiteSpace($env:AZURE_OPENAI_API_KEY) -or $env:AZURE_OPENAI_API_KEY -eq "your-key-here") {
  throw "Set AZURE_OPENAI_API_KEY in .env before opening the site."
}
if ([string]::IsNullOrWhiteSpace($env:AZURE_OPENAI_ENDPOINT) -or $env:AZURE_OPENAI_ENDPOINT -match "your-resource") {
  throw "Set AZURE_OPENAI_ENDPOINT in .env before opening the site."
}

az account set --subscription $SubscriptionId
az group create --name $ResourceGroup --location $Location | Out-Null

$ErrorActionPreference = "Continue"
$acr = az acr show --name $AcrName --resource-group $ResourceGroup --query name -o tsv 2>$null
if ($LASTEXITCODE -ne 0) { $acr = $null }
$ErrorActionPreference = "Stop"
if (-not $acr) {
  Write-Host "Creating registry $AcrName"
  az acr create --name $AcrName --resource-group $ResourceGroup --sku Basic | Out-Null
}

$image = "$AcrName.azurecr.io/firstpass-quotes:latest"
Write-Host "Building and pushing $image"
az acr login --name $AcrName
docker build --tag $image $RepoRoot
if ($LASTEXITCODE -ne 0) { throw "docker build failed." }
docker push $image
if ($LASTEXITCODE -ne 0) { throw "docker push failed." }

$ErrorActionPreference = "Continue"
$aks = az aks show --resource-group $ResourceGroup --name $AksName --query name -o tsv 2>$null
if ($LASTEXITCODE -ne 0) { $aks = $null }
$ErrorActionPreference = "Stop"
if (-not $aks) {
  Write-Host "Creating cluster $AksName ($NodeVmSize). This usually takes 5-10 minutes."
  az aks create `
    --name $AksName `
    --resource-group $ResourceGroup `
    --node-count 1 `
    --node-vm-size $NodeVmSize `
    --tier free `
    --generate-ssh-keys `
    --attach-acr $AcrName
  if ($LASTEXITCODE -ne 0) { throw "az aks create failed." }
}

az aks get-credentials --resource-group $ResourceGroup --name $AksName --overwrite-existing

kubectl create secret generic firstpass-openai `
  --from-literal=AZURE_OPENAI_API_KEY="$env:AZURE_OPENAI_API_KEY" `
  --from-literal=AZURE_OPENAI_ENDPOINT="$env:AZURE_OPENAI_ENDPOINT" `
  --dry-run=client -o yaml | kubectl apply -f -

(Get-Content (Join-Path $RepoRoot "k8s\deployment.yaml") -Raw) -replace "REPLACE_ACR", $AcrName |
  kubectl apply -f -
(Get-Content (Join-Path $RepoRoot "k8s\service.yaml") -Raw) -replace "REPLACE_DNS_LABEL", $DnsLabel |
  kubectl apply -f -

kubectl rollout status deployment/firstpass-quotes --timeout=180s

do {
  Start-Sleep -Seconds 10
  $ip = kubectl get svc firstpass-quotes -o jsonpath="{.status.loadBalancer.ingress[0].ip}"
  Write-Host "LoadBalancer IP: $ip"
} while (-not $ip)

$url = "http://$DnsLabel.$Location.cloudapp.azure.com"
Invoke-RestMethod "$url/api/health"
Write-Host "Health: $url/api/health"
Write-Host "Site:   https://sales.firstpassquotes.com"
Write-Host "sales.firstpassquotes.com works when it is a CNAME to $DnsLabel.$Location.cloudapp.azure.com."
Write-Host "GitHub deploys need a new KUBE_CONFIG secret; this cluster's kubeconfig replaced the previous one."
