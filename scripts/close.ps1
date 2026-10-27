# Stop billing for the public site.
# Deletes the AKS cluster (node, disk, load balancer, public IP) and the Basic registry.
# Leaves the resource group, Azure OpenAI, and the sales.firstpassquotes.com DNS record in place.
# Does not ask for confirmation. Run it only when the site should go dark.

$ErrorActionPreference = "Stop"

$SubscriptionId = "bc55f11d-f48a-476c-b9a4-21a1f009de48"
$ResourceGroup  = "rg-firstpass"
$AcrName        = "firstpassacrsd1902"
$AksName        = "firstpass-aks"

az account set --subscription $SubscriptionId

$aks = az aks show --resource-group $ResourceGroup --name $AksName --query name -o tsv 2>$null
if ($aks) {
  Write-Host "Deleting cluster $AksName"
  az aks delete --resource-group $ResourceGroup --name $AksName --yes
} else {
  Write-Host "Cluster $AksName is already gone."
}

$acr = az acr show --name $AcrName --resource-group $ResourceGroup --query name -o tsv 2>$null
if ($acr) {
  Write-Host "Deleting registry $AcrName"
  az acr delete --name $AcrName --resource-group $ResourceGroup --yes
} else {
  Write-Host "Registry $AcrName is already gone."
}

Write-Host "Remaining resources in ${ResourceGroup}:"
az resource list --resource-group $ResourceGroup --query "[].{name:name, type:type}" -o table
