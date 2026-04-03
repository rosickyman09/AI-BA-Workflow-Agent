$ErrorActionPreference='Stop'

$admin = (Invoke-RestMethod -Method Post -Uri 'http://localhost:5001/auth/login' -ContentType 'application/json' -Body '{"email":"admin@ai-ba.local","password":"password123"}').access_token
$owner = (Invoke-RestMethod -Method Post -Uri 'http://localhost:5001/auth/login' -ContentType 'application/json' -Body '{"email":"owner@ai-ba.local","password":"password123"}').access_token
$ba = (Invoke-RestMethod -Method Post -Uri 'http://localhost:5001/auth/login' -ContentType 'application/json' -Body '{"email":"ba1@ai-ba.local","password":"password123"}').access_token

$docId = (docker exec ai_ba_postgres psql -U postgres -d ai_ba_db -t -A -c "SELECT doc_id FROM documents ORDER BY created_at DESC LIMIT 1;").Trim()
$projectId = (docker exec ai_ba_postgres psql -U postgres -d ai_ba_db -t -A -c "SELECT project_id FROM documents WHERE doc_id = '$docId' LIMIT 1;").Trim()

$hitlBody = (@{ doc_id=$docId; project_id=$projectId; reason='High-risk financial and legal wording detected'; risk_flags=@{ severity='HIGH'; categories=@('legal','financial') } } | ConvertTo-Json -Depth 8)
$hitl = Invoke-RestMethod -Method Post -Uri 'http://localhost:5000/api/approvals/hitl-trigger' -Headers @{ Authorization = "Bearer $ba" } -ContentType 'application/json' -Body $hitlBody
$workflowId = $hitl.workflow_id

$step1 = Invoke-RestMethod -Method Post -Uri ("http://localhost:5000/api/approvals/{0}/approve" -f $workflowId) -Headers @{ Authorization = "Bearer $owner" } -ContentType 'application/json' -Body (@{ comment='Owner approved after human review' } | ConvertTo-Json)
$step2 = Invoke-RestMethod -Method Post -Uri ("http://localhost:5000/api/approvals/{0}/approve" -f $workflowId) -Headers @{ Authorization = "Bearer $admin" } -ContentType 'application/json' -Body (@{ comment='Admin approved step2' } | ConvertTo-Json)
$step3 = Invoke-RestMethod -Method Post -Uri ("http://localhost:5000/api/approvals/{0}/approve" -f $workflowId) -Headers @{ Authorization = "Bearer $admin" } -ContentType 'application/json' -Body (@{ comment='Admin final approval' } | ConvertTo-Json)

$hitl2 = Invoke-RestMethod -Method Post -Uri 'http://localhost:5000/api/approvals/hitl-trigger' -Headers @{ Authorization = "Bearer $ba" } -ContentType 'application/json' -Body $hitlBody
$reject = Invoke-RestMethod -Method Post -Uri ("http://localhost:5000/api/approvals/{0}/reject" -f $hitl2.workflow_id) -Headers @{ Authorization = "Bearer $owner" } -ContentType 'application/json' -Body (@{ reason='Insufficient evidence in risk analysis' } | ConvertTo-Json)

$versionsCount = (docker exec ai_ba_postgres psql -U postgres -d ai_ba_db -t -A -c "SELECT COUNT(*) FROM document_versions WHERE doc_id = '$docId';").Trim()
$auditRows = docker exec ai_ba_postgres psql -U postgres -d ai_ba_db -t -A -c "SELECT action, user_id::text, to_char(created_at, 'YYYY-MM-DD HH24:MI:SS') FROM audit_logs WHERE entity_type='approval' ORDER BY created_at DESC LIMIT 10;"

[PSCustomObject]@{
  doc_id=$docId
  project_id=$projectId
  workflow_approved=$workflowId
  hitl_status=$hitl.status
  approve_step1_status=$step1.status
  approve_step2_status=$step2.status
  approve_step3_status=$step3.status
  workflow_rejected=$hitl2.workflow_id
  reject_status=$reject.status
  versions_count=$versionsCount
  audit_last10=$auditRows
} | ConvertTo-Json -Depth 8
