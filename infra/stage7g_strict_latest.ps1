$ErrorActionPreference='Stop'
function Invoke-Api {
  param([string]$Method,[string]$Uri,[string]$Token,[string]$JsonBody='')
  try {
    if ($JsonBody -ne '') { $obj = Invoke-RestMethod -Method $Method -Uri $Uri -Headers @{ Authorization = "Bearer $Token" } -ContentType 'application/json' -Body $JsonBody }
    else { $obj = Invoke-RestMethod -Method $Method -Uri $Uri -Headers @{ Authorization = "Bearer $Token" } }
    return @{ status=200; body=$obj }
  } catch {
    if ($_.Exception.Response) {
      $code=[int]$_.Exception.Response.StatusCode
      $msg=''
      try { $sr=New-Object IO.StreamReader($_.Exception.Response.GetResponseStream()); $msg=$sr.ReadToEnd() } catch {}
      return @{ status=$code; body=$msg }
    }
    return @{ status=0; body=($_ | Out-String) }
  }
}

# fresh tokens
$adminToken = (Invoke-RestMethod -Method Post -Uri 'http://localhost:5001/auth/login' -ContentType 'application/json' -Body '{"email":"admin@ai-ba.local","password":"password123"}').access_token
$baToken = (Invoke-RestMethod -Method Post -Uri 'http://localhost:5001/auth/login' -ContentType 'application/json' -Body '{"email":"ba1@ai-ba.local","password":"password123"}').access_token
$ownerToken = (Invoke-RestMethod -Method Post -Uri 'http://localhost:5001/auth/login' -ContentType 'application/json' -Body '{"email":"owner@ai-ba.local","password":"password123"}').access_token

$doc='df3da7b3-67e6-4cb4-937a-da4650a724b0'
$proj='660e8400-e29b-41d4-a716-446655440000'

# Gate 1
$g1 = Invoke-Api -Method 'Post' -Uri 'http://localhost:5000/api/approvals' -Token $adminToken -JsonBody (@{ document_id=$doc; project_id=$proj; workflow_type='approval' } | ConvertTo-Json)
$workflowId=''
if ($g1.status -eq 200 -and $g1.body.workflow_id) { $workflowId = [string]$g1.body.workflow_id }
if (-not $workflowId) { $workflowId='00000000-0000-0000-0000-000000000000' }

# Gate 2
$g2 = Invoke-Api -Method 'Post' -Uri ("http://localhost:5000/api/approvals/{0}/approve" -f $workflowId) -Token $baToken -JsonBody (@{ comment='BA tries approve' } | ConvertTo-Json)

# Gate 3
$g3 = Invoke-Api -Method 'Post' -Uri ("http://localhost:5000/api/approvals/{0}/approve" -f $workflowId) -Token $ownerToken -JsonBody (@{ comment='Approved by owner' } | ConvertTo-Json)

# Gate 4
$audit = docker exec ai_ba_postgres psql -U postgres -d ai_ba_db -t -A -c "SELECT action, user_id::text, to_char(created_at, 'YYYY-MM-DD HH24:MI:SS') FROM audit_logs ORDER BY created_at DESC LIMIT 5;"

# Gate 5
$g5 = Invoke-Api -Method 'Get' -Uri ("http://localhost:5000/api/documents/{0}/versions" -f $doc) -Token $ownerToken

# Gate 6
$g6 = Invoke-Api -Method 'Post' -Uri 'http://localhost:5000/api/approvals/hitl-trigger' -Token $adminToken -JsonBody (@{ document_id=$doc; reason='High risk content detected' } | ConvertTo-Json)

$result = [PSCustomObject]@{
  gate1_status=$g1.status; gate1_body=$g1.body;
  workflow_id=$workflowId;
  gate2_status=$g2.status; gate2_body=$g2.body;
  gate3_status=$g3.status; gate3_body=$g3.body;
  gate4_audit=$audit;
  gate5_status=$g5.status; gate5_body=$g5.body;
  gate6_status=$g6.status; gate6_body=$g6.body
}
$result | ConvertTo-Json -Depth 12 | Set-Content -Path 'C:\Users\rosic\Documents\GitHub\AI-BA-Agent\infra\stage7g_strict_result_latest.json' -Encoding ascii
Write-Output 'WROTE_STAGE7G_RESULT'
