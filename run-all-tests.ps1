# Master Test Orchestrator
# Runs all 4 modules with strict gating: no module proceeds unless previous PASS
# Usage: .\run-all-tests.ps1

param(
    [switch]$SkipInfraCheck = $false
)

# Colors for output
$SuccessColor = 'Green'
$FailureColor = 'Red'
$WarningColor = 'Yellow'
$InfoColor = 'Cyan'

Write-Host ""
Write-Host "============================================================"
Write-Host ""
Write-Host "   AI BA AGENT - COMPLETE TESTING ORCHESTRATION"
Write-Host "   Module 1 -> Module 2 -> Module 3 -> Module 4 -> Integration"
Write-Host ""
Write-Host "   (Every test must PASS before proceeding to next module!)"
Write-Host "   (FAIL = Stop immediately + fix first)"
Write-Host ""
Write-Host "============================================================" -ForegroundColor $InfoColor
Write-Host ""

# Initialize test suite tracking
$testSuiteResults = @()
$overallStatus = "PASS"
$startTime = Get-Date

# ============================================================================
# PREFLIGHT CHECKS
# ============================================================================
Write-Host "[PREFLIGHT CHECKS]" -ForegroundColor $InfoColor
Write-Host "===================================================" -ForegroundColor $InfoColor

Write-Host ""
Write-Host "[1] Checking Docker..." -ForegroundColor $InfoColor

$dockerVersion = docker --version 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "[OK] Docker: $dockerVersion" -ForegroundColor $SuccessColor
} else {
    Write-Host "[FAIL] Docker not found. Please install Docker Desktop." -ForegroundColor $FailureColor
    exit 1
}

Write-Host ""
Write-Host "[2] Checking Docker Compose..." -ForegroundColor $InfoColor

$composeVersion = docker-compose --version 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "[OK] Docker Compose: $composeVersion" -ForegroundColor $SuccessColor
} else {
    Write-Host "[FAIL] Docker Compose not found. Please install Docker Compose." -ForegroundColor $FailureColor
    exit 1
}

Write-Host ""
Write-Host "[3] Checking infrastructure..." -ForegroundColor $InfoColor

if (Test-Path ".\infra\docker-compose.yml") {
    Write-Host "[OK] docker-compose.yml found" -ForegroundColor $SuccessColor
} else {
    Write-Host "[FAIL] docker-compose.yml not found" -ForegroundColor $FailureColor
    exit 1
}

if (Test-Path ".\infra\migrations") {
    $migrationCount = (Get-ChildItem ".\infra\migrations" -Filter "*.sql").Count
    Write-Host "[OK] Database migrations found ($migrationCount files)" -ForegroundColor $SuccessColor
} else {
    Write-Host "[WARN] Database migrations folder not found" -ForegroundColor $WarningColor
}

Write-Host ""
Write-Host "[PASS] Preflight checks PASSED" -ForegroundColor $SuccessColor
Write-Host ""

# ============================================================================
# INFRASTRUCTURE STARTUP
# ============================================================================
Write-Host "[START INFRASTRUCTURE]" -ForegroundColor $InfoColor
Write-Host "===================================================" -ForegroundColor $InfoColor

Write-Host ""
Write-Host "Bringing up PostgreSQL, Redis, and Qdrant..." -ForegroundColor $InfoColor

Push-Location ".\infra"
$infraStart = docker-compose up -d postgres redis qdrant 2>&1
Pop-Location

if ($LASTEXITCODE -eq 0) {
    Write-Host "[OK] Infrastructure services starting..." -ForegroundColor $SuccessColor
    Write-Host "  Waiting for health checks to pass (30 seconds)..." -ForegroundColor $InfoColor
    Start-Sleep -Seconds 15
} else {
    Write-Host "[FAIL] Failed to start infrastructure" -ForegroundColor $FailureColor
    Write-Host "Error: $infraStart" -ForegroundColor $FailureColor
    exit 1
}

# ============================================================================
# MODULE 1: DATABASE TESTING
# ============================================================================
Write-Host ""
Write-Host "[MODULE 1: DATABASE TESTING]" -ForegroundColor $InfoColor
Write-Host "===================================================" -ForegroundColor $InfoColor
Write-Host ""

$module1Start = Get-Date
.\run-module1-tests.ps1

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "[PASS] MODULE 1: PASS" -ForegroundColor $SuccessColor
    $testSuiteResults += [PSCustomObject]@{
        Module = "Module 1: Database"
        Status = "PASS"
        Duration = "{0:mm\:ss}" -f ((Get-Date) - $module1Start)
    }
} else {
    Write-Host ""
    Write-Host "[FAIL] MODULE 1: FAIL" -ForegroundColor $FailureColor
    $testSuiteResults += [PSCustomObject]@{
        Module = "Module 1: Database"
        Status = "FAIL"
        Duration = "{0:mm\:ss}" -f ((Get-Date) - $module1Start)
    }
    $overallStatus = "FAIL"
    
    Write-Host ""
    Write-Host "[GATE RULE] Module 1 must PASS before proceeding to Module 2" -ForegroundColor $FailureColor
    Write-Host "Fix the failures above and re-run: .\run-all-tests.ps1" -ForegroundColor $InfoColor
    exit 1
}

# ============================================================================
# MODULE 2: BACKEND API TESTING
# ============================================================================
Write-Host ""
Write-Host "[MODULE 2: BACKEND API TESTING]" -ForegroundColor $InfoColor
Write-Host "===================================================" -ForegroundColor $InfoColor
Write-Host ""

$module2Start = Get-Date
.\run-module2-tests.ps1

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "[PASS] MODULE 2: PASS" -ForegroundColor $SuccessColor
    $testSuiteResults += [PSCustomObject]@{
        Module = "Module 2: Backend API"
        Status = "PASS"
        Duration = "{0:mm\:ss}" -f ((Get-Date) - $module2Start)
    }
} else {
    Write-Host ""
    Write-Host "[FAIL] MODULE 2: FAIL" -ForegroundColor $FailureColor
    $testSuiteResults += [PSCustomObject]@{
        Module = "Module 2: Backend API"
        Status = "FAIL"
        Duration = "{0:mm\:ss}" -f ((Get-Date) - $module2Start)
    }
    $overallStatus = "FAIL"
    
    Write-Host ""
    Write-Host "[GATE RULE] Module 2 must PASS before proceeding to Module 3" -ForegroundColor $FailureColor
    Write-Host "Fix the failures above and re-run: .\run-all-tests.ps1" -ForegroundColor $InfoColor
    exit 1
}

# ============================================================================
# MODULE 3: AI AGENT TESTING
# ============================================================================
Write-Host ""
Write-Host "[MODULE 3: AI AGENT TESTING]" -ForegroundColor $InfoColor
Write-Host "===================================================" -ForegroundColor $InfoColor
Write-Host ""

$module3Start = Get-Date
.\run-module3-tests.ps1

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "[PASS] MODULE 3: PASS" -ForegroundColor $SuccessColor
    $testSuiteResults += [PSCustomObject]@{
        Module = "Module 3: AI Agent"
        Status = "PASS"
        Duration = "{0:mm\:ss}" -f ((Get-Date) - $module3Start)
    }
} else {
    Write-Host ""
    Write-Host "[FAIL] MODULE 3: FAIL" -ForegroundColor $FailureColor
    $testSuiteResults += [PSCustomObject]@{
        Module = "Module 3: AI Agent"
        Status = "FAIL"
        Duration = "{0:mm\:ss}" -f ((Get-Date) - $module3Start)
    }
    $overallStatus = "FAIL"
    
    Write-Host ""
    Write-Host "[GATE RULE] Module 3 must PASS before proceeding to Module 4" -ForegroundColor $FailureColor
    Write-Host "Fix the failures above and re-run: .\run-all-tests.ps1" -ForegroundColor $InfoColor
    exit 1
}

# ============================================================================
# MODULE 4: FRONTEND TESTING
# ============================================================================
Write-Host ""
Write-Host "[MODULE 4: FRONTEND TESTING]" -ForegroundColor $InfoColor
Write-Host "===================================================" -ForegroundColor $InfoColor
Write-Host ""

$module4Start = Get-Date
.\run-module4-tests.ps1

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "[PASS] MODULE 4: PASS" -ForegroundColor $SuccessColor
    $testSuiteResults += [PSCustomObject]@{
        Module = "Module 4: Frontend"
        Status = "PASS"
        Duration = "{0:mm\:ss}" -f ((Get-Date) - $module4Start)
    }
} else {
    Write-Host ""
    Write-Host "[FAIL] MODULE 4: FAIL" -ForegroundColor $FailureColor
    $testSuiteResults += [PSCustomObject]@{
        Module = "Module 4: Frontend"
        Status = "FAIL"
        Duration = "{0:mm\:ss}" -f ((Get-Date) - $module4Start)
    }
    $overallStatus = "FAIL"
    
    Write-Host ""
    Write-Host "[GATE RULE] Module 4 must PASS before Integration Testing" -ForegroundColor $FailureColor
    Write-Host "Fix the failures above and re-run: .\run-all-tests.ps1" -ForegroundColor $InfoColor
    exit 1
}

# ============================================================================
# FINAL SUMMARY & REPORT
# ============================================================================
Write-Host ""
Write-Host "===================================================" -ForegroundColor $InfoColor
Write-Host "[TEST SUITE SUMMARY]" -ForegroundColor $InfoColor
Write-Host "===================================================" -ForegroundColor $InfoColor

$testSuiteResults | Format-Table -Property Module, Status, Duration -AutoSize | Out-String | Write-Host

$totalDuration = Get-Date - $startTime

Write-Host ""
Write-Host "Total Test Duration: $("{0:mm\:ss}" -f $totalDuration)" -ForegroundColor $InfoColor
Write-Host ""

if ($overallStatus -eq "PASS") {
    Write-Host "===================================================" -ForegroundColor $SuccessColor
    Write-Host "[SUCCESS] ALL TESTS PASSED - SYSTEM READY!" -ForegroundColor $SuccessColor
    Write-Host "===================================================" -ForegroundColor $SuccessColor
    Write-Host ""
    Write-Host "[RESULTS]" -ForegroundColor $SuccessColor
    Write-Host "  [OK] Database Module:    PASS" -ForegroundColor $SuccessColor
    Write-Host "  [OK] Backend API Module: PASS" -ForegroundColor $SuccessColor
    Write-Host "  [OK] AI Agent Module:    PASS" -ForegroundColor $SuccessColor
    Write-Host "  [OK] Frontend Module:    PASS" -ForegroundColor $SuccessColor
    Write-Host ""
    Write-Host "[NEXT] Deploy to production!" -ForegroundColor $SuccessColor
    Write-Host "===================================================" -ForegroundColor $SuccessColor
    Write-Host ""
    exit 0
} else {
    Write-Host "===================================================" -ForegroundColor $FailureColor
    Write-Host "[FAILURE] TESTS FAILED - FIX AND RERUN" -ForegroundColor $FailureColor
    Write-Host "===================================================" -ForegroundColor $FailureColor
    Write-Host ""
    Write-Host "[ACTIONS]" -ForegroundColor $FailureColor
    Write-Host "  Review test reports for failures:" -ForegroundColor $FailureColor
    Write-Host "  - module1_test_report.md" -ForegroundColor $FailureColor
    Write-Host "  - module2_test_report.md" -ForegroundColor $FailureColor
    Write-Host "  - module3_test_report.md" -ForegroundColor $FailureColor
    Write-Host "  - module4_test_report.md" -ForegroundColor $FailureColor
    Write-Host ""
    Write-Host "[COMMAND] .\run-all-tests.ps1" -ForegroundColor $FailureColor
    Write-Host "===================================================" -ForegroundColor $FailureColor
    Write-Host ""
    exit 1
}
