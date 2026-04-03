$ErrorActionPreference='Stop'
$loginBody = '{"email":"admin@ai-ba.local","password":"password123"}'
$token = (Invoke-RestMethod -Method Post -Uri 'http://localhost:5001/auth/login' -ContentType 'application/json' -Body $loginBody).access_token

$projectA = '660e8400-e29b-41d4-a716-446655440000'
$projectB = '660e8400-e29b-41d4-a716-446655440001'
$docA = 'stage7f-accept-a'
$docB = 'stage7f-accept-b'

$embedA = (@{ document_id=$docA; project_id=$projectA; text_content="# Overview`nThe team discussed authentication and approvals.`n## Requirements`nSystem must support JWT auth, RBAC, approval workflow.`n## Risks`nMissing approvals may delay release."; metadata=@{ source='stage7f-accept'; page=1 } } | ConvertTo-Json -Depth 8)
$embedB = (@{ document_id=$docB; project_id=$projectB; text_content="# Other Project`nWarehouse forecasting and logistics optimization only."; metadata=@{ source='stage7f-accept'; page=1 } } | ConvertTo-Json -Depth 8)

$embedRespA = Invoke-RestMethod -Method Post -Uri 'http://localhost:5002/rag/embed' -Headers @{ Authorization = "Bearer $token" } -ContentType 'application/json' -Body $embedA
$embedRespB = Invoke-RestMethod -Method Post -Uri 'http://localhost:5002/rag/embed' -Headers @{ Authorization = "Bearer $token" } -ContentType 'application/json' -Body $embedB

$searchBodyA = (@{ query='JWT RBAC approval workflow'; project_id=$projectA; top_k=5 } | ConvertTo-Json)
$t1 = Get-Date
$searchRespA = Invoke-RestMethod -Method Post -Uri 'http://localhost:5002/rag/search' -Headers @{ Authorization = "Bearer $token" } -ContentType 'application/json' -Body $searchBodyA
$t2 = Get-Date
$latencyMs = [math]::Round(($t2-$t1).TotalMilliseconds,2)

$searchBodyB = (@{ query='JWT RBAC approval workflow'; project_id=$projectB; top_k=5 } | ConvertTo-Json)
$searchRespB = Invoke-RestMethod -Method Post -Uri 'http://localhost:5002/rag/search' -Headers @{ Authorization = "Bearer $token" } -ContentType 'application/json' -Body $searchBodyB

$qdrantCheck = docker exec ai_ba_rag_service python -c "from app.services.vector_db_service import get_client,collection_name; pid='$projectA'; c=get_client(); name=collection_name(pid); r=c.count(collection_name=name, exact=True); print(r.count)"
$qdrantCount = [int]($qdrantCheck | Select-Object -Last 1)

$results = @()
$results += [PSCustomObject]@{ gate='Embedding pipeline'; pass=(($embedRespA.status -eq 'embedded' -and [int]$embedRespA.chunks -gt 0) -and ($embedRespB.status -eq 'embedded')); detail="A:status=$($embedRespA.status),chunks=$($embedRespA.chunks); B:status=$($embedRespB.status),chunks=$($embedRespB.chunks)" }
$results += [PSCustomObject]@{ gate='Qdrant data persisted'; pass=($qdrantCount -gt 0); detail="projectA_count=$qdrantCount" }
$results += [PSCustomObject]@{ gate='Semantic search <500ms'; pass=($latencyMs -lt 500); detail="latency_ms=$latencyMs; api_search_time_ms=$($searchRespA.search_time_ms)" }
$results += [PSCustomObject]@{ gate='Confidence threshold >=0.6'; pass=(($searchRespA.total_found -gt 0) -and ($searchRespA.results[0].score -ge 0.6) -and ($searchRespA.confidence -ge 0.6)); detail="top_score=$($searchRespA.results[0].score); confidence=$($searchRespA.confidence); total_found=$($searchRespA.total_found)" }
$results += [PSCustomObject]@{ gate='Project isolation'; pass=($searchRespB.total_found -eq 0); detail="projectB_total_found=$($searchRespB.total_found)" }
$citation = if ($searchRespA.total_found -gt 0) { $searchRespA.results[0].citation } else { '' }
$results += [PSCustomObject]@{ gate='Citation format [doc_id#section]'; pass=($citation -match '^\[[^\]#]+#[^\]]+\]$'); detail="citation=$citation" }

$report = [PSCustomObject]@{ token_obtained=[bool]$token; latency_ms=$latencyMs; searchA=$searchRespA; searchB=$searchRespB; qdrant_count_projectA=$qdrantCount; gates=$results; all_pass=(-not ($results | Where-Object { -not $_.pass })) }
$report | ConvertTo-Json -Depth 12
