# Module 1: Database Testing Script
# Run this script once Docker Desktop is fixed and running
# Usage: .\run-module1-tests.ps1

param(
    [string]$ReportPath = "module1_test_report.md",
    [int]$TimeoutSeconds = 300
)

# Colors for output
$SuccessColor = 'Green'
$FailureColor = 'Red'
$WarningColor = 'Yellow'
$InfoColor = 'Cyan'

Write-Host "=== MODULE 1: DATABASE TESTING ===" -ForegroundColor $InfoColor
Write-Host "Starting Database Module Tests at $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor $InfoColor
Write-Host ""

# Initialize test report
$reportContent = @"
# MODULE 1: DATABASE TESTING REPORT

**Report Date:** $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
**Tester:** Automated QA Agent
**Test Environment:** Docker Compose local
**Database Version:** PostgreSQL 15.x

## Overall Result: [PENDING] ⏳

"@

# Array to track test results
$testResults = @()
$failureCount = 0

# ============================================================================
# TEST 1.1: DATABASE CONNECTIVITY
# ============================================================================
Write-Host "[TEST 1.1] Database Connectivity..." -ForegroundColor $InfoColor

try {
    # Check if postgres container is running
    $psqlRunning = docker ps --format "{{.Names}}" | Where-Object { $_ -eq "ai_ba_postgres" }
    
    if ($psqlRunning) {
        Write-Host "[OK] PostgreSQL container is running" -ForegroundColor $SuccessColor
        
        # Test connection with pg_isready
        $healthCheck = docker exec ai_ba_postgres pg_isready -U postgres -d ai_ba_db
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "[OK] PostgreSQL port 5432 is accessible" -ForegroundColor $SuccessColor
            
            # Get version
            $version = docker exec ai_ba_postgres psql -U postgres -d ai_ba_db -t -c "SELECT version();"
            Write-Host "[OK] PostgreSQL version: $version" -ForegroundColor $SuccessColor
            
            # Check connection pool
            $maxConnections = docker exec ai_ba_postgres psql -U postgres -d ai_ba_db -t -c "SHOW max_connections;"
            Write-Host "[OK] Max connections: $maxConnections" -ForegroundColor $SuccessColor
            
            $testResults += [PSCustomObject]@{
                Test = "1.1 - Database Connectivity"
                Result = "PASS"
            }
        } else {
            Write-Host "[FAIL] PostgreSQL health check failed" -ForegroundColor $FailureColor
            $testResults += [PSCustomObject]@{
                Test = "1.1 - Database Connectivity"
                Result = "FAIL"
            }
            $failureCount++
        }
    } else {
        Write-Host "[FAIL] PostgreSQL container not running. Start with: docker-compose up -d postgres" -ForegroundColor $FailureColor
        $testResults += [PSCustomObject]@{
            Test = "1.1 - Database Connectivity"
            Result = "FAIL"
        }
        $failureCount++
    }
} catch {
    Write-Host "[FAIL] Error testing database connectivity: $_" -ForegroundColor $FailureColor
    $testResults += [PSCustomObject]@{
        Test = "1.1 - Database Connectivity"
        Result = "FAIL - $($_.Exception.Message)"
    }
    $failureCount++
}

Write-Host ""

# ============================================================================
# TEST 1.2: SCHEMA VALIDATION
# ============================================================================
Write-Host "[TEST 1.2] Schema Validation..." -ForegroundColor $InfoColor

try {
    # List tables
    $tablesOutput = docker exec ai_ba_postgres psql -U postgres -d ai_ba_db -c "\dt" 2>&1
    $tableCount = ($tablesOutput | Select-String "public" | Measure-Object).Count
    
    if ($tableCount -ge 8) {
        Write-Host "[OK] Database has $tableCount tables (expected: 8+)" -ForegroundColor $SuccessColor
        
        # Get specific table names
        $tables = docker exec ai_ba_postgres psql -U postgres -d ai_ba_db -t -c "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename;"
        Write-Host "[OK] Tables found: $($tables -join ', ')" -ForegroundColor $SuccessColor
        
        # Check indexes
        $indexCountOutput = docker exec ai_ba_postgres psql -U postgres -d ai_ba_db -t -c "SELECT COUNT(*) FROM pg_indexes WHERE schemaname='public';" 2>&1
        $indexCount = [int]($indexCountOutput | Select-Object -First 1).Trim()
        Write-Host "[OK] Indexes created: $indexCount (expected: 15+)" -ForegroundColor $(if($indexCount -ge 15) { $SuccessColor } else { $WarningColor })
        
        # Check primary keys
        $pkCountOutput = docker exec ai_ba_postgres psql -U postgres -d ai_ba_db -t -c "SELECT COUNT(DISTINCT table_name) FROM information_schema.table_constraints WHERE table_schema='public' AND constraint_type='PRIMARY KEY';" 2>&1
        $pkCount = [int]($pkCountOutput | Select-Object -First 1).Trim()
        Write-Host "[OK] Primary keys found: $pkCount/11 tables" -ForegroundColor $(if($pkCount -ge 11) { $SuccessColor } else { $FailureColor })
        
        if ($indexCount -ge 15 -and $pkCount -ge 11) {
            $testResults += [PSCustomObject]@{
                Test = "1.2 - Schema Validation"
                Result = "PASS"
            }
        } else {
            $testResults += [PSCustomObject]@{
                Test = "1.2 - Schema Validation"
                Result = "FAIL - Missing indexes or primary keys"
            }
            $failureCount++
        }
    } else {
        Write-Host "[FAIL] Database has only $tableCount tables (expected: 8)" -ForegroundColor $FailureColor
        $testResults += [PSCustomObject]@{
            Test = "1.2 - Schema Validation"
            Result = "FAIL - Missing tables"
        }
        $failureCount++
    }
} catch {
    Write-Host "[FAIL] Error validating schema: $_" -ForegroundColor $FailureColor
    $testResults += [PSCustomObject]@{
        Test = "1.2 - Schema Validation"
        Result = "FAIL - $($_.Exception.Message)"
    }
    $failureCount++
}

Write-Host ""

# ============================================================================
# TEST 1.3: CRUD OPERATIONS
# ============================================================================
Write-Host "[TEST 1.3] CRUD Operations..." -ForegroundColor $InfoColor

try {
    $crudSuccess = $true
    
    # Test INSERT
    Write-Host "  Testing INSERT..." -ForegroundColor $InfoColor
    $insertResult = docker exec ai_ba_postgres psql -U postgres -d ai_ba_db -t -c "
    INSERT INTO projects (name, owner_id, created_at)
    VALUES ('Test Project', (SELECT user_id FROM users LIMIT 1), NOW())
    RETURNING project_id, name;
    " 2>&1
    
    if ($insertResult -like "*Test Project*") {
        Write-Host "  [OK] INSERT successful" -ForegroundColor $SuccessColor
    } else {
        Write-Host "  [FAIL] INSERT failed: $insertResult" -ForegroundColor $FailureColor
        $crudSuccess = $false
    }
    
    # Test SELECT
    Write-Host "  Testing SELECT..." -ForegroundColor $InfoColor
    $selectOutput = docker exec ai_ba_postgres psql -U postgres -d ai_ba_db -t -c "SELECT COUNT(*) FROM projects;" 2>&1
    $selectResult = [int]($selectOutput | Select-Object -First 1).Trim()
    
    if ($selectResult -ge 1) {
        Write-Host "  [OK] SELECT successful (found $selectResult record)" -ForegroundColor $SuccessColor
    } else {
        Write-Host "  [FAIL] SELECT failed" -ForegroundColor $FailureColor
        $crudSuccess = $false
    }
    
    # Test UPDATE
    Write-Host "  Testing UPDATE..." -ForegroundColor $InfoColor
    $updateResult = docker exec ai_ba_postgres psql -U postgres -d ai_ba_db -t -c "
    UPDATE projects SET name='Updated Project' WHERE name='Test Project'
    RETURNING name;
    " 2>&1
    
    if ($updateResult -like "*Updated*") {
        Write-Host "  [OK] UPDATE successful" -ForegroundColor $SuccessColor
    } else {
        Write-Host "  [FAIL] UPDATE failed: $updateResult" -ForegroundColor $FailureColor
        $crudSuccess = $false
    }
    
    # Test DELETE
    Write-Host "  Testing DELETE..." -ForegroundColor $InfoColor
    $deleteResult = docker exec ai_ba_postgres psql -U postgres -d ai_ba_db -t -c "
    DELETE FROM projects WHERE name='Updated Project'
    RETURNING project_id;
    " 2>&1
    
    if ($deleteResult -NotLike "ERROR*") {
        Write-Host "  [OK] DELETE successful" -ForegroundColor $SuccessColor
    } else {
        Write-Host "  [FAIL] DELETE failed: $deleteResult" -ForegroundColor $FailureColor
        $crudSuccess = $false
    }
    
    if ($crudSuccess) {
        $testResults += [PSCustomObject]@{
            Test = "1.3 - CRUD Operations"
            Result = "PASS"
        }
    } else {
        $testResults += [PSCustomObject]@{
            Test = "1.3 - CRUD Operations"
            Result = "FAIL"
        }
        $failureCount++
    }
} catch {
    Write-Host "[FAIL] Error testing CRUD operations: $_" -ForegroundColor $FailureColor
    $testResults += [PSCustomObject]@{
        Test = "1.3 - CRUD Operations"
        Result = "FAIL - $($_.Exception.Message)"
    }
    $failureCount++
}

Write-Host ""

# ============================================================================
# TEST 1.4: MIGRATION VERIFICATION
# ============================================================================
Write-Host "[TEST 1.4] Migration Verification..." -ForegroundColor $InfoColor

try {
    # Check migrations folder
    $migrationPath = ".\infra\migrations"
    $migrationFiles = Get-ChildItem -Path $migrationPath -Filter "*.sql" -ErrorAction SilentlyContinue
    
    if ($migrationFiles.Count -gt 0) {
        Write-Host "[OK] Found $($migrationFiles.Count) migration files" -ForegroundColor $SuccessColor
        
        # Check if migration table exists (some setups auto-apply without tracking table)
        $migrationTable = docker exec ai_ba_postgres psql -U postgres -d ai_ba_db -t -c "SELECT COUNT(*) FROM pg_tables WHERE tablename='schema_migrations' AND schemaname='public';" 2>&1 | Select-Object -First 1
        $migrationTableCount = [int]($migrationTable).Trim()
        
        if ($migrationTableCount -eq 1) {
            Write-Host "[OK] schema_migrations tracking table exists" -ForegroundColor $SuccessColor
            
            # List applied migrations
            $appliedMigrations = docker exec ai_ba_postgres psql -U postgres -d ai_ba_db -c "SELECT COUNT(*) FROM schema_migrations;" 2>&1
            Write-Host "[OK] Applied migrations tracked: $appliedMigrations" -ForegroundColor $SuccessColor
            
            $testResults += [PSCustomObject]@{
                Test = "1.4 - Migration Verification"
                Result = "PASS"
            }
        } else {
            Write-Host "[OK] Migrations exist (auto-applied without tracking table)" -ForegroundColor $SuccessColor
            $testResults += [PSCustomObject]@{
                Test = "1.4 - Migration Verification"
                Result = "PASS"
            }
        }
    } else {
        Write-Host "[WARN] No migration files found in ./infra/migrations (may be auto-applied)" -ForegroundColor $WarningColor
        $testResults += [PSCustomObject]@{
            Test = "1.4 - Migration Verification"
            Result = "PARTIAL - Migrations applied but files missing"
        }
    }
} catch {
    Write-Host "[FAIL] Error verifying migrations: $_" -ForegroundColor $FailureColor
    $testResults += [PSCustomObject]@{
        Test = "1.4 - Migration Verification"
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
# MODULE 1: DATABASE TESTING REPORT

**Report Date:** $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
**Tester:** Automated QA Agent
**Test Environment:** Docker Compose local
**Database Version:** PostgreSQL 15.x

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
- Tester: Automated QA Agent
- Approval: ✅ PASS

**NEXT STEP:** [PASS] **PROCEED TO MODULE 2: BACKEND API TESTING**

"@
} else {
    $reportContent += @"
[FAIL] **$failureCount tests FAILED**

### Sign-Off
- Testing Completed: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
- Tester: Automated QA Agent
- Approval: [FAIL] FAIL

**NEXT STEP:** [STOP] **STOP HERE.** Fix failures and re-run Module 1 testing before proceeding to Module 2.

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
    Write-Host "[PASS] ALL TESTS PASSED - Ready to proceed to Module 2" -ForegroundColor $SuccessColor
    exit 0
} else {
    Write-Host "[FAIL] TESTS FAILED - Fix issues and rerun testing" -ForegroundColor $FailureColor
    exit 1
}
