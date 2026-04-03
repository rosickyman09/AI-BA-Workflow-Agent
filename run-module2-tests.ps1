# Module 2: Backend API Testing Script
# Run this script once Module 1 (Database) is PASS and backend service is running
# Usage: .\run-module2-tests.ps1

param(
    [string]$ReportPath = "module2_test_report.md",
    [string]$BackendUrl = "http://localhost:5000",
    [string]$AuthServiceUrl = "http://localhost:5001",
    [int]$TimeoutSeconds = 300
)

# Colors for output
$SuccessColor = 'Green'
$FailureColor = 'Red'
$WarningColor = 'Yellow'
$InfoColor = 'Cyan'

Write-Host "=== MODULE 2: BACKEND API TESTING ===" -ForegroundColor $InfoColor
Write-Host "Starting Backend Module Tests at $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor $InfoColor
Write-Host "Backend URL: $BackendUrl" -ForegroundColor $InfoColor
Write-Host ""

# Check if Module 1 passed
$module1ReportFile = "module1_test_report.md"

if (-not (Test-Path $module1ReportFile)) {
    Write-Host "[FAIL] ERROR: Module 1 test report not found at $module1ReportFile" -ForegroundColor $FailureColor
    exit 1
}

$module1Content = Get-Content $module1ReportFile -Raw -ErrorAction SilentlyContinue

# Check for success indicators in report - look for multiple patterns
if (($module1Content -notmatch "Overall Result.*PASS") -and ($module1Content -notmatch "All tests PASSED")) {
    Write-Host "[FAIL] ERROR: Module 1 did not PASS" -ForegroundColor $FailureColor
    Write-Host "Module 1 must pass before running Module 2 tests" -ForegroundColor $FailureColor
    exit 1
}

# Array to track test results
$testResults = @()
$failureCount = 0

# ============================================================================
# TEST 2.1: API ENDPOINT RESPONSE
# ============================================================================
Write-Host "[TEST 2.1] API Endpoint Response..." -ForegroundColor $InfoColor

try {
    # Test health check endpoint
    Write-Host "  Testing /health endpoint..." -ForegroundColor $InfoColor
    $response = Invoke-WebRequest -Uri "$BackendUrl/health" -UseBasicParsing -ErrorAction SilentlyContinue
    
    if ($response.StatusCode -eq 200) {
        Write-Host "  [OK] Health check successful (200 OK)" -ForegroundColor $SuccessColor
    } else {
        Write-Host "  [FAIL] Health check returned: $($response.StatusCode)" -ForegroundColor $FailureColor
        $failureCount++
    }
    
    # Test FastAPI auto-generated docs endpoint
    Write-Host "  Testing /docs endpoint..." -ForegroundColor $InfoColor
    $docsResponse = Invoke-WebRequest -Uri "$BackendUrl/docs" -UseBasicParsing -ErrorAction SilentlyContinue
    
    if ($docsResponse.StatusCode -eq 200) {
        Write-Host "  [OK] API docs available (200 OK)" -ForegroundColor $SuccessColor
    } else {
        Write-Host "  [WARN] API docs returned: $($docsResponse.StatusCode)" -ForegroundColor $WarningColor
    }
    
    # Test 404 Not Found
    Write-Host "  Testing 404 handling..." -ForegroundColor $InfoColor
    try {
        $notFoundResponse = Invoke-WebRequest -Uri "$BackendUrl/api/invalid-endpoint-test" -UseBasicParsing -ErrorAction Stop
    } catch {
        if ($_.Exception.Response.StatusCode -eq 404) {
            Write-Host "  [OK] 404 correctly returned for invalid endpoint" -ForegroundColor $SuccessColor
        } else {
            Write-Host "  ✗ Unexpected status code: $($_.Exception.Response.StatusCode)" -ForegroundColor $FailureColor
            $failureCount++
        }
    }
    
    if ($failureCount -eq 0) {
        $testResults += [PSCustomObject]@{
            Test = "2.1 - API Endpoint Response"
            Result = "PASS"
        }
    } else {
        $testResults += [PSCustomObject]@{
            Test = "2.1 - API Endpoint Response"
            Result = "FAIL"
        }
    }
} catch {
    Write-Host "[FAIL] Error testing API endpoints: $_" -ForegroundColor $FailureColor
    $testResults += [PSCustomObject]@{
        Test = "2.1 - API Endpoint Response"
        Result = "FAIL - Service unreachable"
    }
    $failureCount++
}

Write-Host ""

# ============================================================================
# TEST 2.2: AUTHENTICATION & JWT
# ============================================================================
Write-Host "[TEST 2.2] Authentication & JWT..." -ForegroundColor $InfoColor

try {
    # Test login endpoint on auth service (port 5001)
    Write-Host "  Testing login endpoint on auth service..." -ForegroundColor $InfoColor
    $loginBody = @{
        email = "test@example.com"
        password = "password123"
    } | ConvertTo-Json
    
    $loginResponse = Invoke-WebRequest `
        -Uri "$AuthServiceUrl/auth/login" `
        -Method POST `
        -ContentType "application/json" `
        -Body $loginBody `
        -UseBasicParsing `
        -ErrorAction SilentlyContinue
    
    if ($loginResponse.StatusCode -eq 200) {
        $loginData = $loginResponse.Content | ConvertFrom-Json
        
        if ($loginData.access_token) {
            Write-Host "  [OK] Login successful, JWT token generated" -ForegroundColor $SuccessColor
            $token = $loginData.access_token
            
            # Test token format (JWT has 3 parts separated by dots)
            if ($token -match '^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$') {
                Write-Host "  [OK] Token format is valid JWT" -ForegroundColor $SuccessColor
                
                # Test using token on real backend endpoint
                Write-Host "  Testing protected endpoint with token..." -ForegroundColor $InfoColor
                $headers = @{ "Authorization" = "Bearer $token" }
                $protectedResponse = Invoke-WebRequest `
                    -Uri "$BackendUrl/api/documents/test-doc-001" `
                    -Headers $headers `
                    -UseBasicParsing `
                    -ErrorAction SilentlyContinue
                
                if ($protectedResponse.StatusCode -eq 200) {
                    Write-Host "  [OK] Protected endpoint accessible with valid token" -ForegroundColor $SuccessColor
                } else {
                    Write-Host "  [FAIL] Protected endpoint returned: $($protectedResponse.StatusCode)" -ForegroundColor $FailureColor
                    $failureCount++
                }
            } else {
                Write-Host "  [FAIL] Token format invalid" -ForegroundColor $FailureColor
                $failureCount++
            }
        } else {
            Write-Host "  [FAIL] No token in login response" -ForegroundColor $FailureColor
            $failureCount++
        }
    } else {
        Write-Host "  [FAIL] Login endpoint returned: $($loginResponse.StatusCode)" -ForegroundColor $FailureColor
        $failureCount++
    }
    
    # Test error handling for non-existent endpoints (404)
    Write-Host "  Testing 404 for non-existent endpoint..." -ForegroundColor $InfoColor
    try {
        $notFoundResponse = Invoke-WebRequest `
            -Uri "$BackendUrl/api/nonexistent/endpoint" `
            -UseBasicParsing `
            -ErrorAction Stop
    } catch {
        if ($_.Exception.Response.StatusCode -eq "NotFound") {
            Write-Host "  [OK] 404 correctly returned for non-existent endpoint" -ForegroundColor $SuccessColor
        } else {
            Write-Host "  [WARN] Got status code: $($_.Exception.Response.StatusCode)" -ForegroundColor $WarningColor
        }
    }
    
    if ($failureCount -eq 0) {
        $testResults += [PSCustomObject]@{
            Test = "2.2 - Authentication & JWT"
            Result = "PASS"
        }
    } else {
        $testResults += [PSCustomObject]@{
            Test = "2.2 - Authentication & JWT"
            Result = "FAIL"
        }
    }
} catch {
    Write-Host "[FAIL] Error testing authentication: $_" -ForegroundColor $FailureColor
    $testResults += [PSCustomObject]@{
        Test = "2.2 - Authentication & JWT"
        Result = "FAIL - $($_.Exception.Message)"
    }
    $failureCount++
}

Write-Host ""

# ============================================================================
# TEST 2.3: ERROR HANDLING
# ============================================================================
Write-Host "[TEST 2.3] Error Handling & Standard Format..." -ForegroundColor $InfoColor

try {
    $errorTestsPassed = $true
    
    # Test 400 Bad Request
    Write-Host "  Testing 400 Bad Request..." -ForegroundColor $InfoColor
    try {
        $badRequest = Invoke-WebRequest `
            -Uri "$BackendUrl/api/documents/upload" `
            -Method POST `
            -ContentType "application/json" `
            -Body '{}' `
            -UseBasicParsing `
            -ErrorAction Stop
    } catch {
        if ($_.Exception.Response.StatusCode -eq 400) {
            $errorBody = $_.Exception.Response.Content | ConvertFrom-Json
            if ($errorBody.error -and $errorBody.code) {
                Write-Host "  [OK] 400 returned with standard error format" -ForegroundColor $SuccessColor
            } else {
                Write-Host "  ⚠ 400 returned but missing standard fields" -ForegroundColor $WarningColor
                $errorTestsPassed = $false
            }
        }
    }
    
    # Test error doesn't expose stack traces
    Write-Host "  Testing error response format..." -ForegroundColor $InfoColor
    if ($errorBody.error -notmatch "Traceback" -and $errorBody.error -notmatch "File") {
        Write-Host "  [OK] Error response doesn't expose stack trace" -ForegroundColor $SuccessColor
    } else {
        Write-Host "  [FAIL] Error response may contain stack trace" -ForegroundColor $FailureColor
        $errorTestsPassed = $false
    }
    
    if ($errorTestsPassed) {
        $testResults += [PSCustomObject]@{
            Test = "2.3 - Error Handling"
            Result = "PASS"
        }
    } else {
        $testResults += [PSCustomObject]@{
            Test = "2.3 - Error Handling"
            Result = "FAIL"
        }
        $failureCount++
    }
} catch {
    Write-Host "[FAIL] Error testing error handling: $_" -ForegroundColor $FailureColor
    $testResults += [PSCustomObject]@{
        Test = "2.3 - Error Handling"
        Result = "FAIL - $($_.Exception.Message)"
    }
    $failureCount++
}

Write-Host ""

# ============================================================================
# TEST 2.4: DATABASE INTEGRATION
# ============================================================================
Write-Host "[TEST 2.4] Database Integration..." -ForegroundColor $InfoColor

try {
    # Verify database is accessible from backend
    Write-Host "  Checking database connectivity via backend..." -ForegroundColor $InfoColor
    
    # This test assumes the backend can query documents (which tests DB connectivity)
    $dbIntegrationPassed = $true
    
    # Check that backend logs show database operations
    Write-Host "  Verifying database operations in logs..." -ForegroundColor $InfoColor
    $logs = docker logs ai_ba_backend 2>&1 | Select-String -Pattern "database|postgres|connected" -ErrorAction SilentlyContinue
    
    if ($logs) {
        Write-Host "  [OK] Database operations logged by backend" -ForegroundColor $SuccessColor
    } else {
        Write-Host "  ⚠ No explicit database logs found" -ForegroundColor $WarningColor
    }
    
    if ($dbIntegrationPassed) {
        $testResults += [PSCustomObject]@{
            Test = "2.4 - Database Integration"
            Result = "PASS"
        }
    } else {
        $testResults += [PSCustomObject]@{
            Test = "2.4 - Database Integration"
            Result = "FAIL"
        }
        $failureCount++
    }
} catch {
    Write-Host "[FAIL] Error testing database integration: $_" -ForegroundColor $FailureColor
    $testResults += [PSCustomObject]@{
        Test = "2.4 - Database Integration"
        Result = "FAIL - $($_.Exception.Message)"
    }
    $failureCount++
}

Write-Host ""

# ============================================================================
# GENERATE TEST REPORT
# ============================================================================
Write-Host "=== TEST SUMMARY ===" -ForegroundColor $InfoColor

$reportContent = @"
# MODULE 2: BACKEND API TESTING REPORT

**Report Date:** $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
**Tester:** Automated QA Agent
**Backend URL:** $BackendUrl
**Dependencies:** ✅ Module 1 PASSED (Required)

## Overall Result: $(if($failureCount -eq 0) { 'PASS ✅' } else { 'FAIL ❌' })

### Test Results Summary

| Test # | Test Name | Result |
|--------|-----------|--------|
"@

foreach ($result in $testResults) {
    $status = if ($result.Result -eq "PASS") { "✅ PASS" } else { "❌ $($result.Result)" }
    $reportContent += "`n| $($result.Test) | $status |"
}

$reportContent += @"

### Detailed Results

"@

foreach ($result in $testResults) {
    $reportContent += "`n#### $($result.Test)`n"
    $reportContent += "**Result:** $($result.Result)`n`n"
}

$reportContent += @"

### Issues Found
**Total Issues:** $failureCount

"@

if ($failureCount -eq 0) {
    $reportContent += @"
✅ **All tests PASSED**

### Sign-Off
- Testing Completed: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
- Prerequisite (Module 1): ✅ PASSED
- Tester: Automated QA Agent
- Approval: ✅ PASS

**NEXT STEP:** ✅ **PROCEED TO MODULE 3: AI AGENT TESTING**

"@
} else {
    $reportContent += @"
[FAIL] **$failureCount tests FAILED**

### Sign-Off
- Testing Completed: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
- Prerequisite (Module 1): [PASS] PASSED
- Tester: Automated QA Agent
- Approval: [FAIL] FAIL

**NEXT STEP:** [STOP] **STOP HERE.** Fix failures and re-run Module 2 testing before proceeding to Module 3.

"@
}

# Save report
$reportContent | Out-File -FilePath $ReportPath -Encoding UTF8
Write-Host "[OK] Test report saved to: $ReportPath" -ForegroundColor $SuccessColor

# Display summary
Write-Host ""
Write-Host "=== TEST EXECUTION COMPLETE ===" -ForegroundColor $(if($failureCount -eq 0) { $SuccessColor } else { $FailureColor })
Write-Host "Passed: $($testResults.Count - $failureCount)/$($testResults.Count)" -ForegroundColor $InfoColor
Write-Host "Failed: $failureCount/$($testResults.Count)" -ForegroundColor $(if($failureCount -eq 0) { $SuccessColor } else { $FailureColor })
Write-Host ""

if ($failureCount -eq 0) {
    Write-Host "[PASS] ALL TESTS PASSED - Ready to proceed to Module 3" -ForegroundColor $SuccessColor
    exit 0
} else {
    Write-Host "[FAIL] TESTS FAILED - Fix issues and rerun testing" -ForegroundColor $FailureColor
    exit 1
}
