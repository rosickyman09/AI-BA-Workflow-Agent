$ErrorActionPreference = 'Stop'

$root = 'c:\Users\rosic\Documents\GitHub\AI-BA-Agent'
$infraEnv = Join-Path $root 'infra/.env'
$envExample = Join-Path $root '.env.example'
$wfCPath = Join-Path $root 'n8n/workflow_c_backlog.json'
$wfDPath = Join-Path $root 'n8n/workflow_d_digest.json'
$wfEPath = Join-Path $root 'n8n/workflow_e_reminder.json'

$result = [ordered]@{}

function GateResult($name, $pass, $detail) {
  return [ordered]@{ gate = $name; pass = $pass; detail = $detail }
}

# Read optional n8n API key from infra/.env
$n8nApiKey = ''
if (Test-Path $infraEnv) {
  $line = Get-Content $infraEnv | Where-Object { $_ -match '^N8N_API_KEY=' } | Select-Object -First 1
  if ($line) { $n8nApiKey = ($line -replace '^N8N_API_KEY=', '').Trim() }
}

$headersJson = @{ 'Content-Type' = 'application/json' }
$headersN8n = @{ 'Content-Type' = 'application/json' }
if ($n8nApiKey -and $n8nApiKey -ne '') { $headersN8n['X-N8N-API-KEY'] = $n8nApiKey }

# Fresh token
$loginBody = '{"email":"admin@ai-ba.local","password":"password123"}'
$loginResp = Invoke-RestMethod -Method Post -Uri 'http://localhost:5001/auth/login' -Headers $headersJson -Body $loginBody
$token = $loginResp.access_token
$authHeaders = @{ Authorization = "Bearer $token"; 'Content-Type'='application/json' }

# Gate 1
try {
  $g1Body = '{"message":"Test notification","type":"info"}'
  $g1 = Invoke-WebRequest -Method Post -Uri 'http://localhost:5000/api/notifications/send' -Headers $authHeaders -Body $g1Body
  $g1Obj = $g1.Content | ConvertFrom-Json
  $shapeOk = ($g1Obj.PSObject.Properties.Name -contains 'sent') -and ($g1Obj.PSObject.Properties.Name -contains 'type') -and ($g1Obj.PSObject.Properties.Name -contains 'timestamp')
  $result.g1 = GateResult 'Gate 1 - send endpoint' (($g1.StatusCode -eq 200) -and $shapeOk) ("status=$($g1.StatusCode), shapeOk=$shapeOk")
} catch {
  $result.g1 = GateResult 'Gate 1 - send endpoint' $false $_.Exception.Message
}

# Gate 2
try {
  $g2Body = '{"message":{"text":"/status","chat":{"id":12345}}}'
  $g2 = Invoke-WebRequest -Method Post -Uri 'http://localhost:5000/api/notifications/telegram/webhook' -Headers $headersJson -Body $g2Body
  $g2Obj = $g2.Content | ConvertFrom-Json
  $handled = ($g2Obj.handled -eq $true) -and ($g2Obj.command -eq '/status')
  $result.g2 = GateResult 'Gate 2 - /status command' (($g2.StatusCode -eq 200) -and $handled) ("status=$($g2.StatusCode), handled=$handled")
} catch {
  $result.g2 = GateResult 'Gate 2 - /status command' $false $_.Exception.Message
}

# Gate 3
try {
  $g3 = Invoke-WebRequest -Method Post -Uri 'http://localhost:5000/api/notifications/approval-reminders/run' -Headers $authHeaders
  $g3Obj = $g3.Content | ConvertFrom-Json
  $okFields = ($g3Obj.PSObject.Properties.Name -contains 'sent') -and ($g3Obj.PSObject.Properties.Name -contains 'total_candidates')
  $result.g3 = GateResult 'Gate 3 - approval reminders' (($g3.StatusCode -eq 200) -and $okFields) ("status=$($g3.StatusCode), fieldsOk=$okFields")
} catch {
  $result.g3 = GateResult 'Gate 3 - approval reminders' $false $_.Exception.Message
}

# Gate 4
try {
  $filesExist = (Test-Path $wfCPath) -and (Test-Path $wfDPath) -and (Test-Path $wfEPath)
  $cronC = $false; $cronD = $false; $eventE = $false; $validJson = $false
  if ($filesExist) {
    $wfC = Get-Content $wfCPath -Raw | ConvertFrom-Json
    $wfD = Get-Content $wfDPath -Raw | ConvertFrom-Json
    $wfE = Get-Content $wfEPath -Raw | ConvertFrom-Json
    $validJson = $true
    $cronC = (($wfC.nodes | Where-Object { $_.type -eq 'n8n-nodes-base.cron' }).parameters.triggerTimes[0].cronExpression -eq '0 8 * * 1-5')
    $cronD = (($wfD.nodes | Where-Object { $_.type -eq 'n8n-nodes-base.cron' }).parameters.triggerTimes[0].cronExpression -eq '0 17 * * 5')
    $eventE = [bool](($wfE.nodes | Where-Object { $_.type -eq 'n8n-nodes-base.webhook' }).Count -ge 1)
  }
  $pass4 = $filesExist -and $validJson -and $cronC -and $cronD -and $eventE
  $result.g4 = GateResult 'Gate 4 - workflow files' $pass4 ("filesExist=$filesExist, validJson=$validJson, cronC=$cronC, cronD=$cronD, eventE=$eventE")
} catch {
  $result.g4 = GateResult 'Gate 4 - workflow files' $false $_.Exception.Message
}

# Gate 5 import workflows
$imported = @{}
$workflowIds = @{}
try {
  $wfMap = @{
    workflow_c_backlog = $wfCPath
    workflow_d_digest = $wfDPath
    workflow_e_reminder = $wfEPath
  }

  foreach ($name in $wfMap.Keys) {
    $wfRaw = Get-Content $wfMap[$name] -Raw
    $wfObj = $wfRaw | ConvertFrom-Json
    if (-not $wfObj.PSObject.Properties.Name.Contains('active')) { $wfObj | Add-Member -NotePropertyName active -NotePropertyValue $false }
    if (-not $wfObj.PSObject.Properties.Name.Contains('settings')) { $wfObj | Add-Member -NotePropertyName settings -NotePropertyValue @{} }

    $body = $wfObj | ConvertTo-Json -Depth 100
    $resp = $null
    $usedEndpoint = ''

    try {
      $resp = Invoke-RestMethod -Method Post -Uri 'http://localhost:5678/api/v1/workflows' -Headers $headersN8n -Body $body
      $usedEndpoint = '/api/v1/workflows'
    } catch {
      # fallback to old n8n REST endpoint
      $resp = Invoke-RestMethod -Method Post -Uri 'http://localhost:5678/rest/workflows' -Headers $headersN8n -Body $body
      $usedEndpoint = '/rest/workflows'
    }

    $wid = $null
    if ($resp.id) { $wid = [string]$resp.id }
    elseif ($resp.data -and $resp.data.id) { $wid = [string]$resp.data.id }

    $imported[$name] = [ordered]@{ ok = $true; endpoint = $usedEndpoint; id = $wid }
    if ($wid) { $workflowIds[$name] = $wid }
  }

  $allImported = ($imported.Keys.Count -eq 3) -and (($imported.Values | Where-Object { $_.ok -ne $true }).Count -eq 0)
  $result.g5 = GateResult 'Gate 5 - import to n8n' $allImported (($imported | ConvertTo-Json -Depth 6 -Compress))
} catch {
  $result.g5 = GateResult 'Gate 5 - import to n8n' $false $_.Exception.Message
}

# Gate 6 trigger workflow C
try {
  $wid = $workflowIds['workflow_c_backlog']
  if (-not $wid) { throw 'workflow_c_backlog id unavailable from Gate 5 import' }

  $triggerOk = $false
  $triggerEndpoint = ''
  try {
    $tr1 = Invoke-RestMethod -Method Post -Uri ("http://localhost:5678/api/v1/workflows/{0}/run" -f $wid) -Headers $headersN8n -Body '{}'
    $triggerOk = $true
    $triggerEndpoint = '/api/v1/workflows/{id}/run'
  } catch {
    $tr2 = Invoke-RestMethod -Method Post -Uri ("http://localhost:5678/rest/workflows/{0}/run" -f $wid) -Headers $headersN8n -Body '{}'
    $triggerOk = $true
    $triggerEndpoint = '/rest/workflows/{id}/run'
  }

  $result.g6 = GateResult 'Gate 6 - trigger workflow C' $triggerOk ("triggered=$triggerOk endpoint=$triggerEndpoint id=$wid")
} catch {
  $result.g6 = GateResult 'Gate 6 - trigger workflow C' $false $_.Exception.Message
}

# Gate 7 env vars in .env.example
try {
  $envTxt = Get-Content $envExample -Raw
  $hasBot = $envTxt -match '(?m)^TELEGRAM_BOT_TOKEN='
  $hasChat = $envTxt -match '(?m)^TELEGRAM_CHAT_ID='
  $result.g7 = GateResult 'Gate 7 - env vars present' ($hasBot -and $hasChat) ("TELEGRAM_BOT_TOKEN=$hasBot, TELEGRAM_CHAT_ID=$hasChat")
} catch {
  $result.g7 = GateResult 'Gate 7 - env vars present' $false $_.Exception.Message
}

$resultPath = Join-Path $root 'infra/stage7h_strict_result.json'
($result | ConvertTo-Json -Depth 10) | Set-Content -Path $resultPath -Encoding ascii
Write-Output ("RESULT_FILE=" + $resultPath)
Write-Output (($result | ConvertTo-Json -Depth 10))
