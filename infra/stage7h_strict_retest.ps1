$ErrorActionPreference = 'Stop'
$root = 'c:\Users\rosic\Documents\GitHub\AI-BA-Agent'
$envExample = Join-Path $root '.env.example'
$wfCPath = Join-Path $root 'n8n/workflow_c_backlog.json'
$wfDPath = Join-Path $root 'n8n/workflow_d_digest.json'
$wfEPath = Join-Path $root 'n8n/workflow_e_reminder.json'

$result = [ordered]@{}
function GateResult($name, $pass, $detail) { [ordered]@{ gate=$name; pass=$pass; detail=$detail } }

# Fresh backend token
$loginBody = '{"email":"admin@ai-ba.local","password":"password123"}'
$loginResp = Invoke-RestMethod -Method Post -Uri 'http://localhost:5001/auth/login' -ContentType 'application/json' -Body $loginBody
$token = $loginResp.access_token
$authHeaders = @{ Authorization = "Bearer $token"; 'Content-Type'='application/json' }

# Gate 1
try {
  $g1Body = '{"message":"Test notification","type":"info"}'
  $g1 = Invoke-RestMethod -Method Post -Uri 'http://localhost:5000/api/notifications/send' -Headers $authHeaders -Body $g1Body
  $shapeOk = ($g1.PSObject.Properties.Name -contains 'sent') -and ($g1.PSObject.Properties.Name -contains 'type') -and ($g1.PSObject.Properties.Name -contains 'timestamp')
  $result.g1 = GateResult 'Gate 1 - send endpoint' $shapeOk ("status=200, shapeOk=$shapeOk")
} catch { $result.g1 = GateResult 'Gate 1 - send endpoint' $false $_.Exception.Message }

# Gate 2
try {
  $g2Body = '{"message":{"text":"/status","chat":{"id":12345}}}'
  $g2 = Invoke-RestMethod -Method Post -Uri 'http://localhost:5000/api/notifications/telegram/webhook' -ContentType 'application/json' -Body $g2Body
  $handled = ($g2.handled -eq $true) -and ($g2.command -eq '/status')
  $result.g2 = GateResult 'Gate 2 - /status command' $handled ("status=200, handled=$handled")
} catch { $result.g2 = GateResult 'Gate 2 - /status command' $false $_.Exception.Message }

# Gate 3
try {
  $g3 = Invoke-RestMethod -Method Post -Uri 'http://localhost:5000/api/notifications/approval-reminders/run' -Headers $authHeaders
  $okFields = ($g3.PSObject.Properties.Name -contains 'sent') -and ($g3.PSObject.Properties.Name -contains 'total_candidates')
  $result.g3 = GateResult 'Gate 3 - approval reminders' $okFields ("status=200, fieldsOk=$okFields")
} catch { $result.g3 = GateResult 'Gate 3 - approval reminders' $false $_.Exception.Message }

# Gate 4
try {
  $filesExist = (Test-Path $wfCPath) -and (Test-Path $wfDPath) -and (Test-Path $wfEPath)
  $validJson = $false; $cronC = $false; $cronD = $false; $eventE = $false
  if ($filesExist) {
    $wfC = Get-Content $wfCPath -Raw | ConvertFrom-Json
    $wfD = Get-Content $wfDPath -Raw | ConvertFrom-Json
    $wfE = Get-Content $wfEPath -Raw | ConvertFrom-Json
    $validJson = $true
    $cronNodeC = @($wfC.nodes | Where-Object { $_.type -eq 'n8n-nodes-base.cron' })[0]
    $cronNodeD = @($wfD.nodes | Where-Object { $_.type -eq 'n8n-nodes-base.cron' })[0]
    $cronC = ($cronNodeC.parameters.triggerTimes[0].cronExpression -eq '0 8 * * 1-5')
    $cronD = ($cronNodeD.parameters.triggerTimes[0].cronExpression -eq '0 17 * * 5')
    $eventE = @($wfE.nodes | Where-Object { $_.type -like '*webhook*' }).Count -ge 1
  }
  $pass4 = $filesExist -and $validJson -and $cronC -and $cronD -and $eventE
  $result.g4 = GateResult 'Gate 4 - workflow files' $pass4 ("filesExist=$filesExist, validJson=$validJson, cronC=$cronC, cronD=$cronD, eventE=$eventE")
} catch { $result.g4 = GateResult 'Gate 4 - workflow files' $false $_.Exception.Message }

# Login n8n session
$n8nSession = $null
$n8nLoginOk = $false
try {
  $n8nLoginBody = '{"emailOrLdapLoginId":"rosickyman@gmail.com","password":"password123"}'
  $null = Invoke-RestMethod -Method Post -Uri 'http://localhost:5678/rest/login' -ContentType 'application/json' -Body $n8nLoginBody -SessionVariable n8nSession
  $n8nLoginOk = $true
} catch {
  $result.g5 = GateResult 'Gate 5 - import to n8n' $false ("n8n login failed: " + $_.Exception.Message)
}

$workflowIds = @{}
if ($n8nLoginOk) {
  # Gate 5
  try {
    $wfMap = [ordered]@{ workflow_c_backlog=$wfCPath; workflow_d_digest=$wfDPath; workflow_e_reminder=$wfEPath }
    $imported = @{}
    foreach ($name in $wfMap.Keys) {
      $wfObj = Get-Content $wfMap[$name] -Raw | ConvertFrom-Json
      if ($wfObj.PSObject.Properties.Name -contains 'versionId') { $wfObj.PSObject.Properties.Remove('versionId') }
      if ($wfObj.PSObject.Properties.Name -contains 'id') { $wfObj.PSObject.Properties.Remove('id') }
      $body = $wfObj | ConvertTo-Json -Depth 100
      $resp = $null; $endpoint = ''
      try {
        $resp = Invoke-RestMethod -Method Post -Uri 'http://localhost:5678/api/v1/workflows' -WebSession $n8nSession -ContentType 'application/json' -Body $body
        $endpoint = '/api/v1/workflows'
      } catch {
        $resp = Invoke-RestMethod -Method Post -Uri 'http://localhost:5678/rest/workflows' -WebSession $n8nSession -ContentType 'application/json' -Body $body
        $endpoint = '/rest/workflows'
      }
      $wid = $null
      if ($resp.id) { $wid = [string]$resp.id }
      elseif ($resp.data -and $resp.data.id) { $wid = [string]$resp.data.id }
      $imported[$name] = @{ ok=$true; endpoint=$endpoint; id=$wid }
      if ($wid) { $workflowIds[$name] = $wid }
    }
    $allImported = ($imported.Count -eq 3) -and (@($imported.Values | Where-Object { $_.ok -ne $true }).Count -eq 0)
    $result.g5 = GateResult 'Gate 5 - import to n8n' $allImported (($imported | ConvertTo-Json -Depth 6 -Compress))
  } catch {
    $result.g5 = GateResult 'Gate 5 - import to n8n' $false $_.Exception.Message
  }

  # Gate 6
  try {
    $wid = $workflowIds['workflow_c_backlog']
    if (-not $wid) { throw 'workflow_c_backlog id unavailable from Gate 5 import' }
    $triggerEndpoint = ''
    try {
      $null = Invoke-RestMethod -Method Post -Uri ("http://localhost:5678/api/v1/workflows/{0}/run" -f $wid) -WebSession $n8nSession -ContentType 'application/json' -Body '{}'
      $triggerEndpoint = '/api/v1/workflows/{id}/run'
    } catch {
      $null = Invoke-RestMethod -Method Post -Uri ("http://localhost:5678/rest/workflows/{0}/run" -f $wid) -WebSession $n8nSession -ContentType 'application/json' -Body '{}'
      $triggerEndpoint = '/rest/workflows/{id}/run'
    }
    $result.g6 = GateResult 'Gate 6 - trigger workflow C' $true ("triggered=true endpoint=$triggerEndpoint id=$wid")
  } catch {
    $result.g6 = GateResult 'Gate 6 - trigger workflow C' $false $_.Exception.Message
  }
}

# Gate 7
try {
  $envTxt = Get-Content $envExample -Raw
  $hasBot = $envTxt -match '(?m)^TELEGRAM_BOT_TOKEN='
  $hasChat = $envTxt -match '(?m)^TELEGRAM_CHAT_ID='
  $result.g7 = GateResult 'Gate 7 - env vars present' ($hasBot -and $hasChat) ("TELEGRAM_BOT_TOKEN=$hasBot, TELEGRAM_CHAT_ID=$hasChat")
} catch { $result.g7 = GateResult 'Gate 7 - env vars present' $false $_.Exception.Message }

$resultPath = Join-Path $root 'infra/stage7h_strict_result_retest.json'
($result | ConvertTo-Json -Depth 12) | Set-Content -Path $resultPath -Encoding ascii
Write-Output ("RESULT_FILE=" + $resultPath)
Write-Output (($result | ConvertTo-Json -Depth 12))
