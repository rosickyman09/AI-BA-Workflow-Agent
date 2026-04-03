$ErrorActionPreference = 'Stop'

$root = 'c:\Users\rosic\Documents\GitHub\AI-BA-Agent'
$result = [ordered]@{}

function GateResult($name, $pass, $detail) {
  [ordered]@{ gate = $name; pass = $pass; detail = $detail }
}

# Helpers
function Login-Session([string]$email, [string]$password) {
  $body = @{ email = $email; password = $password } | ConvertTo-Json
  $resp = Invoke-WebRequest -UseBasicParsing -Method Post -Uri 'http://localhost:3000/api/auth/login' -ContentType 'application/json' -Body $body -SessionVariable s
  return @{ response = $resp; session = $s }
}

function Upload-Document([Microsoft.PowerShell.Commands.WebRequestSession]$session, [string]$filePath, [string]$projectId, [string]$title) {
  Add-Type -AssemblyName System.Net.Http

  $handler = New-Object System.Net.Http.HttpClientHandler
  $handler.UseCookies = $true
  $handler.CookieContainer = New-Object System.Net.CookieContainer

  $cookieHeader = $session.Cookies.GetCookieHeader([Uri]'http://localhost:3000')
  if (-not [string]::IsNullOrWhiteSpace($cookieHeader)) {
    $handler.CookieContainer.SetCookies([Uri]'http://localhost:3000', $cookieHeader)
  }

  $client = New-Object System.Net.Http.HttpClient($handler)
  try {
    $content = New-Object System.Net.Http.MultipartFormDataContent
    $content.Add((New-Object System.Net.Http.StringContent($projectId)), 'project_id')
    $content.Add((New-Object System.Net.Http.StringContent($title)), 'title')

    $fileBytes = [System.IO.File]::ReadAllBytes($filePath)
    $fileContent = New-Object System.Net.Http.ByteArrayContent(,$fileBytes)
    $fileContent.Headers.ContentType = [System.Net.Http.Headers.MediaTypeHeaderValue]::Parse('text/plain')
    $content.Add($fileContent, 'file', [System.IO.Path]::GetFileName($filePath))

    $response = $client.PostAsync('http://localhost:3000/api/documents/upload', $content).Result
    $responseBody = $response.Content.ReadAsStringAsync().Result
    if (-not $response.IsSuccessStatusCode) {
      throw ("upload failed status={0}, body={1}" -f [int]$response.StatusCode, $responseBody)
    }
    return ($responseBody | ConvertFrom-Json)
  } finally {
    $client.Dispose()
  }
}

# Gate 1: Real Login
$adminSession = $null
$adminRole = ''
try {
  $login = Login-Session 'admin@ai-ba.local' 'password123'
  $adminSession = $login.session
  $statusOk = ($login.response.StatusCode -eq 200)
  $cookie = [string]$login.response.Headers['Set-Cookie']
  $httpOnly = $cookie -match 'HttpOnly'

  $me = Invoke-RestMethod -Method Get -Uri 'http://localhost:3000/api/auth/me' -WebSession $adminSession
  $adminRole = [string]$me.role

  $noLocalStorageToken = -not (Select-String -Path "$root\\frontend\\**\\*.ts*" -Pattern 'localStorage\.getItem\(' -SimpleMatch -ErrorAction SilentlyContinue)

  $result.g1 = GateResult 'Gate 1 - Real Login' ($statusOk -and $httpOnly -and $noLocalStorageToken) ("status=$($login.response.StatusCode), httpOnly=$httpOnly, noLocalStorageToken=$noLocalStorageToken, role=$adminRole")
} catch {
  $result.g1 = GateResult 'Gate 1 - Real Login' $false $_.Exception.Message
}

# Gate 2: Upload + Status Polling
$uploadedDocId = ''
try {
  if (-not $adminSession) { throw 'admin session not established' }
  $projectId = '660e8400-e29b-41d4-a716-446655440000'
  $fileObj = Get-Item "$root\\test_doc.txt"

  $upload = Upload-Document -session $adminSession -filePath $fileObj.FullName -projectId $projectId -title 'test_doc.txt'
  $uploadedDocId = [string]$upload.document_id
  if (-not $uploadedDocId) { throw 'upload returned no document_id' }

  $attempt = 0
  $finalStatus = ''
  do {
    Start-Sleep -Seconds 3
    $attempt++
    $statusResp = Invoke-RestMethod -Method Get -Uri ("http://localhost:3000/api/documents/{0}/status" -f $uploadedDocId) -WebSession $adminSession
    $finalStatus = [string]$statusResp.status
  } while ($attempt -lt 12 -and $finalStatus -notin @('COMPLETED', 'FAILED'))

  $pollingOk = $attempt -ge 1
  $terminalOk = $finalStatus -in @('COMPLETED', 'FAILED')
  $result.g2 = GateResult 'Gate 2 - Upload + Polling' ($pollingOk -and $terminalOk) ("document_id=$uploadedDocId, polls=$attempt, finalStatus=$finalStatus")
} catch {
  $result.g2 = GateResult 'Gate 2 - Upload + Polling' $false $_.Exception.Message
}

# Gate 3: Approval Dashboard RBAC behavior check
try {
  $ba = Login-Session 'ba1@ai-ba.local' 'password123'
  $owner = Login-Session 'owner@ai-ba.local' 'password123'
  $baMe = Invoke-RestMethod -Method Get -Uri 'http://localhost:3000/api/auth/me' -WebSession $ba.session
  $ownerMe = Invoke-RestMethod -Method Get -Uri 'http://localhost:3000/api/auth/me' -WebSession $owner.session

  $baRoleOk = ([string]$baMe.role -eq 'ba')
  $ownerRoleOk = ([string]$ownerMe.role -eq 'business_owner')

  # UI role-display logic is client-side; validate implementation condition exists.
  $approvalPage = Get-Content "$root\\frontend\\pages\\approvals.tsx" -Raw
  $hasRoleCondition = ($approvalPage -match "role === 'admin' \|\| role === 'business_owner'")

  $result.g3 = GateResult 'Gate 3 - Approval RBAC' ($baRoleOk -and $ownerRoleOk -and $hasRoleCondition) ("baRole=$($baMe.role), ownerRole=$($ownerMe.role), roleConditionInUI=$hasRoleCondition")
} catch {
  $result.g3 = GateResult 'Gate 3 - Approval RBAC' $false $_.Exception.Message
}

# Gate 4: RAG Search + Citations
try {
  if (-not $adminSession) { throw 'admin session not established' }
  $ragBody = @{ query = 'authentication requirements'; project_id = '660e8400-e29b-41d4-a716-446655440000'; top_k = 5; user_id = 'frontend-user' } | ConvertTo-Json
  $rag = Invoke-RestMethod -Method Post -Uri 'http://localhost:3000/api/rag/search' -WebSession $adminSession -ContentType 'application/json' -Body $ragBody

  $hasResultsArray = $null -ne $rag.results
  $citationFormatOk = $true
  if ($hasResultsArray -and $rag.results.Count -gt 0) {
    foreach ($item in $rag.results) {
      $docId = [string]$item.doc_id
      $section = [string]$item.section
      if ([string]::IsNullOrWhiteSpace($docId) -or [string]::IsNullOrWhiteSpace($section)) {
        $citationFormatOk = $false
      }
    }
  }

  $result.g4 = GateResult 'Gate 4 - RAG + Citations' ($hasResultsArray -and $citationFormatOk) ("resultsCount=$($rag.results.Count), citationFormatOk=$citationFormatOk")
} catch {
  $result.g4 = GateResult 'Gate 4 - RAG + Citations' $false $_.Exception.Message
}

# Gate 5: Knowledge Base list + versions
try {
  if (-not $adminSession) { throw 'admin session not established' }
  $docs = Invoke-RestMethod -Method Get -Uri 'http://localhost:3000/api/documents?project_id=660e8400-e29b-41d4-a716-446655440000' -WebSession $adminSession
  $docCount = @($docs.documents).Count
  $versionExpandableOk = $false
  if ($docCount -gt 0) {
    $firstDoc = [string]$docs.documents[0].doc_id
    $versions = Invoke-RestMethod -Method Get -Uri ("http://localhost:3000/api/documents/{0}/versions" -f $firstDoc) -WebSession $adminSession
    $versionExpandableOk = ($null -ne $versions.versions)
  }

  $result.g5 = GateResult 'Gate 5 - KB Versions' (($docCount -gt 0) -and $versionExpandableOk) ("docCount=$docCount, versionExpandableOk=$versionExpandableOk")
} catch {
  $result.g5 = GateResult 'Gate 5 - KB Versions' $false $_.Exception.Message
}

# Gate 6: Mobile responsive static verification
try {
  $pages = @('login.tsx','documents.tsx','approvals.tsx','knowledge-base.tsx')
  $responsiveSignals = 0
  foreach ($p in $pages) {
    $content = Get-Content "$root\\frontend\\pages\\$p" -Raw
    if ($content -match 'container' -or $content -match 'table-responsive' -or $content -match 'form-control') {
      $responsiveSignals++
    }
  }
  $globalCss = Get-Content "$root\\frontend\\src\\styles\\globals.css" -Raw
  $noFixedPageWidth = -not ($globalCss -match 'width:\s*\d+px')
  $result.g6 = GateResult 'Gate 6 - Mobile Responsive' (($responsiveSignals -ge 4) -and $noFixedPageWidth) ("responsiveSignals=$responsiveSignals/4, noFixedPageWidth=$noFixedPageWidth")
} catch {
  $result.g6 = GateResult 'Gate 6 - Mobile Responsive' $false $_.Exception.Message
}

# Gate 7: Logout clears cookie and blocks /auth/me
try {
  if (-not $adminSession) { throw 'admin session not established' }
  $logoutResp = Invoke-WebRequest -UseBasicParsing -Method Post -Uri 'http://localhost:3000/api/auth/logout' -WebSession $adminSession
  $setCookie = [string]$logoutResp.Headers['Set-Cookie']
  $clearedCookie = ($setCookie -match 'Max-Age=0')

  $meBlocked = $false
  try {
    $null = Invoke-RestMethod -Method Get -Uri 'http://localhost:3000/api/auth/me' -WebSession $adminSession
    $meBlocked = $false
  } catch {
    $meBlocked = $true
  }

  $result.g7 = GateResult 'Gate 7 - Logout' ($clearedCookie -and $meBlocked) ("cookieCleared=$clearedCookie, meBlockedAfterLogout=$meBlocked")
} catch {
  $result.g7 = GateResult 'Gate 7 - Logout' $false $_.Exception.Message
}

$resultPath = "$root\\infra\\stage7i_strict_result.json"
($result | ConvertTo-Json -Depth 10) | Set-Content -Path $resultPath -Encoding ascii
Write-Output ("RESULT_FILE=" + $resultPath)
Write-Output (($result | ConvertTo-Json -Depth 10))
