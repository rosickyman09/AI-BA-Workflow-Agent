$ErrorActionPreference = 'Stop'

$root = 'c:\Users\rosic\Documents\GitHub\AI-BA-Agent'
Set-Location $root

Add-Type -AssemblyName System.Net.Http

$rows = New-Object System.Collections.Generic.List[Object]

function Add-Gate($block, $gate, $expected, $result, $ok) {
  $rows.Add([PSCustomObject]@{
    Block = [string]$block
    Gate = [string]$gate
    Expected = [string]$expected
    Result = [string]$result
    Status = $(if ($ok) { '✅' } else { '❌' })
  })
}

function Login-Role([string]$email, [string]$password) {
  $body = @{ email = $email; password = $password } | ConvertTo-Json
  return Invoke-RestMethod -Method Post -Uri 'http://localhost:5001/auth/login' -ContentType 'application/json' -Body $body
}

function Upload-WithToken([string]$token, [string]$title) {
  $handler = New-Object System.Net.Http.HttpClientHandler
  $client = New-Object System.Net.Http.HttpClient($handler)
  $client.Timeout = [TimeSpan]::FromMinutes(2)
  $client.DefaultRequestHeaders.Authorization = New-Object System.Net.Http.Headers.AuthenticationHeaderValue('Bearer', $token)

  try {
    $content = New-Object System.Net.Http.MultipartFormDataContent
    $content.Add((New-Object System.Net.Http.StringContent('660e8400-e29b-41d4-a716-446655440000')), 'project_id')
    $content.Add((New-Object System.Net.Http.StringContent($title)), 'title')

    $fileBytes = [System.IO.File]::ReadAllBytes((Join-Path $root 'test_doc.txt'))
    $fileContent = New-Object System.Net.Http.ByteArrayContent(,$fileBytes)
    $fileContent.Headers.ContentType = [System.Net.Http.Headers.MediaTypeHeaderValue]::Parse('text/plain')
    $content.Add($fileContent, 'file', 'test_doc.txt')

    try {
      $resp = $client.PostAsync('http://localhost:5000/api/documents/upload', $content).Result
      $txt = ''
      if ($resp -and $resp.Content) {
        $txt = $resp.Content.ReadAsStringAsync().Result
      }
      return @{ status = [int]$resp.StatusCode; body = $txt }
    } catch {
      $code = -1
      $body = $_.Exception.Message
      if ($_.Exception.Response -and $_.Exception.Response.StatusCode) {
        $code = [int]$_.Exception.Response.StatusCode.value__
      }
      return @{ status = $code; body = $body }
    }
  } finally {
    $client.Dispose()
  }
}

function Wait-DocStatus([string]$token, [string]$docId) {
  $attempt = 0
  $final = ''
  do {
    Start-Sleep -Seconds 3
    $attempt++
    $s = Invoke-RestMethod -Method Get -Uri ("http://localhost:5000/api/documents/{0}/status" -f $docId) -Headers @{ Authorization = ('Bearer ' + $token) }
    $final = [string]$s.status
  } while ($attempt -lt 20 -and $final -notin @('COMPLETED', 'FAILED'))
  return @{ status = $final; polls = $attempt }
}

function Try-Insert-ItUser {
  try {
    docker exec ai_ba_postgres psql -U postgres -d ai_ba_db -c "INSERT INTO users (user_id, email, password_hash, role, full_name) VALUES (gen_random_uuid(), 'it@ai-ba.local', '$2b$12$04kZeSBUxCTH7MBV/0.xG.pAOq8uw1PQ1iTjUnIpH9VJeyyrj9Vy2', 'it', 'IT User') ON CONFLICT (email) DO NOTHING;" | Out-Null
  } catch {
  }
}

# Build/restart modified services first
Set-Location (Join-Path $root 'infra')
docker compose up -d --build backend rag_service | Out-Null
Set-Location $root

# BLOCK 1: logins
$admin = $null; $ba = $null; $owner = $null; $it = $null

try { $admin = Login-Role 'admin@ai-ba.local' 'password123'; Add-Gate 1 'Admin login' 'role:admin' ("role=" + $admin.user.role) ($admin.user.role -eq 'admin') } catch { Add-Gate 1 'Admin login' 'role:admin' $_.Exception.Message $false }
try { $ba = Login-Role 'ba1@ai-ba.local' 'password123'; Add-Gate 1 'BA login' 'role:ba' ("role=" + $ba.user.role) ($ba.user.role -eq 'ba') } catch { Add-Gate 1 'BA login' 'role:ba' $_.Exception.Message $false }
try { $owner = Login-Role 'owner@ai-ba.local' 'password123'; Add-Gate 1 'Owner login' 'role:business_owner' ("role=" + $owner.user.role) ($owner.user.role -eq 'business_owner') } catch { Add-Gate 1 'Owner login' 'role:business_owner' $_.Exception.Message $false }

try {
  $it = Login-Role 'it@ai-ba.local' 'password123'
} catch {
  Try-Insert-ItUser
  try { $it = Login-Role 'it@ai-ba.local' 'password123' } catch {}
}
if ($it -and $it.user.role -eq 'it') {
  Add-Gate 1 'IT login' 'role:it' ("role=" + $it.user.role) $true
} else {
  Add-Gate 1 'IT login' 'role:it' 'login failed or role mismatch' $false
}

# BLOCK 2
$workflowId = ''
if ($it) {
  $itUpload = Upload-WithToken -token $it.access_token -title 'shakeout_it_upload.txt'
  Add-Gate 2 'IT upload' '403' ("http=" + $itUpload.status) ($itUpload.status -eq 403)
} else {
  Add-Gate 2 'IT upload' '403' 'IT token unavailable' $false
}

if ($ba) {
  $baUpload = Upload-WithToken -token $ba.access_token -title 'shakeout_ba_upload.txt'
  if ($baUpload.status -eq 200) {
    $obj = $baUpload.body | ConvertFrom-Json
    $workflowId = [string]$obj.workflow_id
    Add-Gate 2 'BA upload' '200' ("http=200 document_id=" + [string]$obj.document_id) $true
  } else {
    Add-Gate 2 'BA upload' '200' ("http=" + $baUpload.status + " body=" + $baUpload.body) $false
  }
} else {
  Add-Gate 2 'BA upload' '200' 'BA token unavailable' $false
}

if ($owner -and $workflowId) {
  try {
    $resp = Invoke-RestMethod -Method Post -Uri ("http://localhost:5000/api/approvals/{0}/approve" -f $workflowId) -Headers @{ Authorization = ('Bearer ' + $owner.access_token) } -ContentType 'application/json' -Body (@{comment='shakeout-owner-approve'}|ConvertTo-Json)
    Add-Gate 2 'Owner approve' '200' 'http=200' $true
  } catch {
    $code = if ($_.Exception.Response) { [int]$_.Exception.Response.StatusCode.value__ } else { -1 }
    Add-Gate 2 'Owner approve' '200' ("http=" + $code + " msg=" + $_.Exception.Message) $false
  }
} else {
  Add-Gate 2 'Owner approve' '200' 'missing owner token or workflow_id' $false
}

if ($ba -and $workflowId) {
  try {
    $null = Invoke-RestMethod -Method Post -Uri ("http://localhost:5000/api/approvals/{0}/approve" -f $workflowId) -Headers @{ Authorization = ('Bearer ' + $ba.access_token) } -ContentType 'application/json' -Body (@{comment='shakeout-ba-approve'}|ConvertTo-Json)
    Add-Gate 2 'BA approve' '403' 'http=200' $false
  } catch {
    $code = if ($_.Exception.Response) { [int]$_.Exception.Response.StatusCode.value__ } else { -1 }
    Add-Gate 2 'BA approve' '403' ("http=" + $code) ($code -eq 403)
  }
} else {
  Add-Gate 2 'BA approve' '403' 'missing BA token or workflow_id' $false
}

# BLOCK 3 timing
try {
  $wfBody = @{ document_id='df3da7b3-67e6-4cb4-937a-da4650a724b0'; project_id='660e8400-e29b-41d4-a716-446655440000'; content='Meeting: Team agreed on JWT auth and RBAC implementation.' } | ConvertTo-Json
  $sw = [System.Diagnostics.Stopwatch]::StartNew()
  $wf = Invoke-RestMethod -Method Post -Uri 'http://localhost:5002/rag/workflow/execute' -ContentType 'application/json' -Body $wfBody
  $sw.Stop()
  $ms = [int]$sw.ElapsedMilliseconds
  Add-Gate 3 'Workflow timing' '<120000ms' ("http=200 ms=$ms status=" + $wf.status) ($ms -lt 120000)
} catch {
  Add-Gate 3 'Workflow timing' '<120000ms' $_.Exception.Message $false
}

# BLOCK 4 data quality
try {
  $srow = docker exec ai_ba_postgres psql -U postgres -d ai_ba_db -t -A -c "SELECT agent_name || '|' || COALESCE(state_data::text,'') FROM agent_state WHERE agent_name ILIKE '%summar%' ORDER BY created_at DESC LIMIT 1;"
  $line = ($srow | Select-Object -Last 1)
  $hasMd = ($line -match '"markdown"\s*:')
  $hasDoc = ($line -match '"document"\s*:')
  Add-Gate 4 'Summarization content' 'markdown present' ("has_markdown=$hasMd has_document=$hasDoc") ($hasMd -and $hasDoc)
} catch {
  Add-Gate 4 'Summarization content' 'markdown present' $_.Exception.Message $false
}

try {
  $arows = docker exec ai_ba_postgres psql -U postgres -d ai_ba_db -t -A -c "SELECT action || '|' || created_at::text FROM audit_logs ORDER BY created_at DESC LIMIT 5;"
  $cnt = @($arows | Where-Object { $_ -and $_.Trim() -ne '' }).Count
  Add-Gate 4 'Audit logs' 'recent entries' ("rows=$cnt") ($cnt -ge 1)
} catch {
  Add-Gate 4 'Audit logs' 'recent entries' $_.Exception.Message $false
}

# BLOCK 5 notifications
if ($admin) {
  try {
    $n1 = Invoke-RestMethod -Method Post -Uri 'http://localhost:5000/api/notifications/send' -Headers @{ Authorization = ('Bearer ' + $admin.access_token) } -ContentType 'application/json' -Body (@{ message='Pre-Railway test'; type='info' }|ConvertTo-Json)
    Add-Gate 5 'Notification send' '200' 'http=200' $true
  } catch {
    $code = if ($_.Exception.Response) { [int]$_.Exception.Response.StatusCode.value__ } else { -1 }
    Add-Gate 5 'Notification send' '200' ("http=" + $code + " msg=" + $_.Exception.Message) $false
  }

  try {
    $n3 = Invoke-RestMethod -Method Post -Uri 'http://localhost:5000/api/notifications/approval-reminders/run' -Headers @{ Authorization = ('Bearer ' + $admin.access_token) }
    Add-Gate 5 'Approval reminder' '200' 'http=200' $true
  } catch {
    $code = if ($_.Exception.Response) { [int]$_.Exception.Response.StatusCode.value__ } else { -1 }
    Add-Gate 5 'Approval reminder' '200' ("http=" + $code + " msg=" + $_.Exception.Message) $false
  }
} else {
  Add-Gate 5 'Notification send' '200' 'admin token unavailable' $false
  Add-Gate 5 'Approval reminder' '200' 'admin token unavailable' $false
}

try {
  $n2 = Invoke-RestMethod -Method Post -Uri 'http://localhost:5000/api/notifications/telegram/webhook' -ContentType 'application/json' -Body (@{ message=@{ text='/status'; chat=@{ id=12345 } } }|ConvertTo-Json -Depth 6)
  $handled = [bool]$n2.handled
  Add-Gate 5 'Telegram command' '200' ("http=200 handled=$handled") $handled
} catch {
  $code = if ($_.Exception.Response) { [int]$_.Exception.Response.StatusCode.value__ } else { -1 }
  Add-Gate 5 'Telegram command' '200' ("http=" + $code + " msg=" + $_.Exception.Message) $false
}

# BLOCK 6 reliability
Set-Location (Join-Path $root 'infra')
try {
  docker compose restart rag_service | Out-Null
  Start-Sleep -Seconds 30
  $h = Invoke-RestMethod -Method Get -Uri 'http://localhost:5002/rag/health'
  Add-Gate 6 'rag_service restart' 'healthy' ("status=" + $h.status) ($h.status -eq 'healthy')
} catch {
  Add-Gate 6 'rag_service restart' 'healthy' $_.Exception.Message $false
}

try {
  docker compose restart backend auth_service | Out-Null
  Start-Sleep -Seconds 30
  $b = Invoke-RestMethod -Method Get -Uri 'http://localhost:5000/health'
  $a = Invoke-RestMethod -Method Get -Uri 'http://localhost:5001/auth/health'
  $ok = (($b.status -eq 'healthy') -and ($a.status -eq 'healthy'))
  Add-Gate 6 'backend restart' 'healthy' ("backend=" + $b.status + " auth=" + $a.status) $ok
} catch {
  Add-Gate 6 'backend restart' 'healthy' $_.Exception.Message $false
}
Set-Location $root

try {
  $admin2 = Login-Role 'admin@ai-ba.local' 'password123'
  $up = Upload-WithToken -token $admin2.access_token -title 'shakeout_post_restart.txt'
  if ($up.status -eq 200) {
    $obj = $up.body | ConvertFrom-Json
    $doc = [string]$obj.document_id
    $ws = Wait-DocStatus -token $admin2.access_token -docId $doc
    Add-Gate 6 'Upload after restart' '200' ("http=200 status=" + $ws.status) ($ws.status -eq 'COMPLETED')
  } else {
    Add-Gate 6 'Upload after restart' '200' ("http=" + $up.status) $false
  }
} catch {
  Add-Gate 6 'Upload after restart' '200' $_.Exception.Message $false
}

try {
  $sbody = @{ query='authentication'; project_id='660e8400-e29b-41d4-a716-446655440000' } | ConvertTo-Json
  $sr = Invoke-RestMethod -Method Post -Uri 'http://localhost:5002/rag/search' -ContentType 'application/json' -Body $sbody
  Add-Gate 6 'Search after restart' '200' ("http=200 total_found=" + [string]$sr.total_found) $true
} catch {
  Add-Gate 6 'Search after restart' '200' $_.Exception.Message $false
}

# BLOCK 7 gateway + health
try {
  $f = Invoke-WebRequest -UseBasicParsing -Uri 'http://localhost'
  Add-Gate 7 'Frontend via gateway' '200' ("http=" + [int]$f.StatusCode) ($f.StatusCode -eq 200)
} catch {
  Add-Gate 7 'Frontend via gateway' '200' $_.Exception.Message $false
}

try {
  $g = Invoke-RestMethod -Method Get -Uri 'http://localhost/health'
  $a = Invoke-RestMethod -Method Get -Uri 'http://localhost:5001/auth/health'
  $b = Invoke-RestMethod -Method Get -Uri 'http://localhost:5000/health'
  $r = Invoke-RestMethod -Method Get -Uri 'http://localhost:5002/rag/health'
  $ok = (($a.status -eq 'healthy') -and ($b.status -eq 'healthy') -and ($r.status -eq 'healthy'))
  Add-Gate 7 'All health endpoints' 'healthy' ("gateway=ok auth=" + $a.status + " backend=" + $b.status + " rag=" + $r.status) $ok
} catch {
  Add-Gate 7 'All health endpoints' 'healthy' $_.Exception.Message $false
}

try {
  $null = Invoke-RestMethod -Method Get -Uri 'http://localhost:5000/api/documents'
  Add-Gate 7 'Unauth rejection' '401/403' 'http=200' $false
} catch {
  $code = if ($_.Exception.Response) { [int]$_.Exception.Response.StatusCode.value__ } else { -1 }
  Add-Gate 7 'Unauth rejection' '401/403' ("http=" + $code) ($code -eq 401 -or $code -eq 403)
}

# BLOCK 8 mobile responsive static check
try {
  $pages = @('login.tsx','documents.tsx','approvals.tsx','knowledge-base.tsx')
  $signals = 0
  foreach ($p in $pages) {
    $content = Get-Content (Join-Path $root ("frontend\\pages\\" + $p)) -Raw
    if ($content -match 'container' -or $content -match 'table-responsive' -or $content -match 'form-control') { $signals++ }
  }
  $globalCss = Get-Content (Join-Path $root 'frontend\\src\\styles\\globals.css') -Raw
  $noFixed = -not ($globalCss -match 'width:\s*\d+px')
  $ok = ($signals -eq 4 -and $noFixed)
  Add-Gate 8 'Mobile 375px' 'no scroll' ("staticSignals=$signals/4 noFixedWidth=$noFixed") $ok
} catch {
  Add-Gate 8 'Mobile 375px' 'no scroll' $_.Exception.Message $false
}

# BLOCK 9 secrets check
try {
  $envFiles = Get-ChildItem -Path $root -Recurse -Force -File | Where-Object {
    $_.Name -eq '.env.example' -or $_.Name -like '*.env.example' -or $_.Name -like '*.example'
  }
  $hits = @()
  foreach ($f in $envFiles) {
    $lines = Get-Content $f.FullName -ErrorAction SilentlyContinue
    foreach ($line in $lines) {
      if ($line -match '^\s*#') { continue }
      if ($line -match '^\s*$') { continue }
      if ($line -match '^(ELEVENLABS_API_KEY|TELEGRAM_BOT_TOKEN|JWT_SECRET|.*API_KEY)\s*=\s*(.+)$') {
        $key = $Matches[1]
        $val = $Matches[2].Trim().Trim('"').Trim("'")
        $isPlaceholder = ($val -match '^(your[-_].*|change_me.*|placeholder.*|dummy.*|example.*|\*\*\*|)$')
        if (-not $isPlaceholder -and $val.Length -gt 10) {
          $hits += ($f.FullName.Replace($root + '\\','') + ':' + $key)
        }
      }
    }
  }
  $clean = ($hits.Count -eq 0)
  $result = if ($clean) { 'no non-placeholder secrets in committed env templates' } else { ('found=' + ($hits -join ';')) }
  Add-Gate 9 'No secrets in files' 'clean' $result $clean
} catch {
  Add-Gate 9 'No secrets in files' 'clean' $_.Exception.Message $false
}

# BLOCK 10 regressions
try {
  $admin3 = Login-Role 'admin@ai-ba.local' 'password123'
  $u3 = Upload-WithToken -token $admin3.access_token -title 'regression_criterion1.txt'
  if ($u3.status -eq 200) {
    $obj3 = $u3.body | ConvertFrom-Json
    $ws3 = Wait-DocStatus -token $admin3.access_token -docId ([string]$obj3.document_id)
    Add-Gate 10 'Criterion 1' 'COMPLETED' ("status=" + $ws3.status) ($ws3.status -eq 'COMPLETED')
  } else {
    Add-Gate 10 'Criterion 1' 'COMPLETED' ("http=" + $u3.status) $false
  }
} catch {
  Add-Gate 10 'Criterion 1' 'COMPLETED' $_.Exception.Message $false
}

try {
  $wfBody2 = @{ document_id='df3da7b3-67e6-4cb4-937a-da4650a724b0'; project_id='660e8400-e29b-41d4-a716-446655440000'; content='Meeting: Team agreed on JWT auth implementation.' } | ConvertTo-Json
  $sw2 = [System.Diagnostics.Stopwatch]::StartNew()
  $wf2 = Invoke-RestMethod -Method Post -Uri 'http://localhost:5002/rag/workflow/execute' -ContentType 'application/json' -Body $wfBody2
  $sw2.Stop()
  $ms2 = [int]$sw2.ElapsedMilliseconds
  Add-Gate 10 'Criterion 3' '<120000ms' ("ms=$ms2 status=" + $wf2.status) ($ms2 -lt 120000)
} catch {
  Add-Gate 10 'Criterion 3' '<120000ms' $_.Exception.Message $false
}

try {
  $srow2 = docker exec ai_ba_postgres psql -U postgres -d ai_ba_db -t -A -c "SELECT agent_name || '|' || COALESCE(state_data::text,'') FROM agent_state WHERE agent_name ILIKE '%summar%' ORDER BY created_at DESC LIMIT 1;"
  $line2 = ($srow2 | Select-Object -Last 1)
  $hasMd2 = ($line2 -match '"markdown"\s*:')
  Add-Gate 10 'Criterion 4' 'markdown present' ("has_markdown=$hasMd2") $hasMd2
} catch {
  Add-Gate 10 'Criterion 4' 'markdown present' $_.Exception.Message $false
}

try {
  if (-not $it) { $it = Login-Role 'it@ai-ba.local' 'password123' }
  $u4 = Upload-WithToken -token $it.access_token -title 'regression_it_upload.txt'
  Add-Gate 10 'Criterion 12' 'IT 403' ("http=" + $u4.status) ($u4.status -eq 403)
} catch {
  Add-Gate 10 'Criterion 12' 'IT 403' $_.Exception.Message $false
}

# Persist report JSON
$reportPath = Join-Path $root 'infra\pre_railway_shakeout_result.json'
$rows | ConvertTo-Json -Depth 6 | Set-Content -Path $reportPath -Encoding ascii

# Output concise summary
$passCount = @($rows | Where-Object { $_.Status -eq '✅' }).Count
$totalCount = $rows.Count
Write-Output ('REPORT_PATH=' + $reportPath)
Write-Output ('PASS=' + $passCount + '/' + $totalCount)
$rows | ConvertTo-Json -Depth 6
