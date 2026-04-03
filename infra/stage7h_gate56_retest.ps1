$ErrorActionPreference = 'Stop'
$login='{"emailOrLdapLoginId":"rosickyman@gmail.com","password":"password123"}'
Invoke-RestMethod -Method Post -Uri 'http://localhost:5678/rest/login' -ContentType 'application/json' -Body $login -SessionVariable s | Out-Null
$paths=@(
  'c:\Users\rosic\Documents\GitHub\AI-BA-Agent\n8n\workflow_c_backlog.json',
  'c:\Users\rosic\Documents\GitHub\AI-BA-Agent\n8n\workflow_d_digest.json',
  'c:\Users\rosic\Documents\GitHub\AI-BA-Agent\n8n\workflow_e_reminder.json'
)
$ids=@{}
foreach($p in $paths){
  $wf = Get-Content $p -Raw | ConvertFrom-Json
  if($wf.PSObject.Properties.Name -contains 'versionId'){ $wf.PSObject.Properties.Remove('versionId') }
  if($wf.PSObject.Properties.Name -contains 'id'){ $wf.PSObject.Properties.Remove('id') }
  $json = $wf | ConvertTo-Json -Depth 100
  $bytes = [System.Text.Encoding]::UTF8.GetBytes($json)
  $resp = $null
  $ep = ''
  try {
    $resp = Invoke-RestMethod -Method Post -Uri 'http://localhost:5678/api/v1/workflows' -WebSession $s -ContentType 'application/json; charset=utf-8' -Body $bytes
    $ep = '/api/v1/workflows'
  } catch {
    $resp = Invoke-RestMethod -Method Post -Uri 'http://localhost:5678/rest/workflows' -WebSession $s -ContentType 'application/json; charset=utf-8' -Body $bytes
    $ep = '/rest/workflows'
  }

  $name=[IO.Path]::GetFileNameWithoutExtension($p)
  $id = ''
  if($resp.id){ $id = [string]$resp.id }
  elseif($resp.data -and $resp.data.id){ $id = [string]$resp.data.id }
  $ids[$name]=$id
  Write-Output ("IMPORTED " + $name + " id=" + $id + " endpoint=" + $ep)
}

$wid=$ids['workflow_c_backlog']
if(-not $wid){ throw 'workflow_c_backlog id missing after import' }

try {
  Invoke-RestMethod -Method Post -Uri ("http://localhost:5678/api/v1/workflows/{0}/run" -f $wid) -WebSession $s -ContentType 'application/json; charset=utf-8' -Body ([System.Text.Encoding]::UTF8.GetBytes('{}')) | Out-Null
  Write-Output ('TRIGGER_OK endpoint=/api/v1/workflows/{id}/run id=' + $wid)
} catch {
  Invoke-RestMethod -Method Post -Uri ("http://localhost:5678/rest/workflows/{0}/run" -f $wid) -WebSession $s -ContentType 'application/json; charset=utf-8' -Body ([System.Text.Encoding]::UTF8.GetBytes('{}')) | Out-Null
  Write-Output ('TRIGGER_OK endpoint=/rest/workflows/{id}/run id=' + $wid)
}

