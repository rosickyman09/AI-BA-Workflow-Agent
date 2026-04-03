# Testing & QA Guide
**Version:** 1.0  
**Date:** 2026-03-15  
**Project:** AI 智能業務助理 (AI BA Agent)  
**Phase:** MVP Phase 1

---

## 1. Testing Strategy

### 1.1 Test Pyramid

```
        ▲
       /|\
      / | \
     /  |  \    E2E Tests (5-10%)
    /   |   \
   /    |    \
  /     |     \
 /      |      \    Integration Tests (20-30%)
/       |       \
───────────────────  
|       |       |   
|       |       |    Unit Tests (60-70%)
|       |       |
```

### 1.2 Test Distribution

| Test Type | Coverage | Framework | Count |
|-----------|----------|-----------|-------|
| Unit Tests | 60-70% | pytest, Jest | 200+ |
| Integration Tests | 20-30% | pytest, Jest | 50+ |
| E2E Tests | 5-10% | Cypress, Playwright | 30+ |
| Manual Tests | - | UI/UX focus | 20+ |

### 1.3 Test Execution Schedule

| Phase | Trigger | Frequency | Duration |
|-------|---------|-----------|----------|
| Pre-commit | Git hook | Per commit | < 5 min |
| CI Pipeline | Push to develop | Per push | 15-20 min |
| Staging | Before release | Once daily | 30-45 min |
| Production | Smoke tests | Every 15 min | 5-10 min |

---

## 2. Unit Testing

### 2.1 Backend Unit Tests (Python)

**Framework:** pytest  
**Coverage Target:** 85%+  

**File Structure:**
```
backend/
├── src/
│   ├── main.py
│   ├── models/
│   │   └── user.py
│   ├── services/
│   │   └── auth_service.py
│   └── routes/
│       └── auth_routes.py
└── tests/
    ├── conftest.py
    ├── unit/
    │   ├── test_auth_service.py
    │   ├── test_document_service.py
    │   └── test_rag_service.py
    ├── integration/
    │   └── test_api_endpoints.py
    └── fixtures/
        └── mock_data.py
```

**Sample Test:** `tests/unit/test_auth_service.py`

```python
import pytest
from unittest.mock import patch, MagicMock
from src.services.auth_service import AuthService
from src.models.user import User

class TestAuthService:
    """Test suite for AuthService"""

    @pytest.fixture
    def auth_service(self):
        """Initialize AuthService for testing"""
        return AuthService()

    @pytest.fixture
    def mock_user(self):
        """Create mock user for testing"""
        return User(
            id="user_123",
            email="test@example.com",
            name="Test User",
            password_hash="hashed_password"
        )

    def test_hash_password_creates_valid_hash(self, auth_service):
        """Test password hashing generates bcrypt hash"""
        password = "secure_password_123"
        hashed = auth_service.hash_password(password)
        
        assert hashed != password
        assert len(hashed) > 20
        assert auth_service.verify_password(password, hashed)

    def test_hash_password_with_empty_string_raises_error(self, auth_service):
        """Test password hashing rejects empty password"""
        with pytest.raises(ValueError):
            auth_service.hash_password("")

    @patch('src.services.auth_service.generate_token')
    def test_generate_jwt_token_with_valid_user(self, mock_generate, auth_service, mock_user):
        """Test JWT token generation"""
        mock_generate.return_value = "eyJhbGc..."
        
        token = auth_service.generate_jwt_token(mock_user)
        
        assert token is not None
        assert isinstance(token, str)
        mock_generate.assert_called_once()

    def test_verify_password_with_correct_password(self, auth_service):
        """Test password verification with correct password"""
        password = "test_password_123"
        hashed = auth_service.hash_password(password)
        
        assert auth_service.verify_password(password, hashed)

    def test_verify_password_with_incorrect_password(self, auth_service):
        """Test password verification rejects incorrect password"""
        password = "test_password_123"
        wrong_password = "wrong_password_456"
        hashed = auth_service.hash_password(password)
        
        assert not auth_service.verify_password(wrong_password, hashed)

    @pytest.mark.parametrize("email,expected", [
        ("user@example.com", True),
        ("invalid-email", False),
        ("@example.com", False),
        ("user@", False),
    ])
    def test_validate_email_format(self, auth_service, email, expected):
        """Test email validation with various formats"""
        result = auth_service.validate_email(email)
        assert result == expected
```

**Running Tests:**
```bash
# All tests
pytest

# With coverage
pytest --cov=src --cov-report=html

# Specific file
pytest tests/unit/test_auth_service.py

# Verbose output
pytest -v

# Stop on first failure
pytest -x

# Run last failed tests
pytest --lf
```

### 2.2 Frontend Unit Tests (JavaScript)

**Framework:** Jest + React Testing Library  
**Coverage Target:** 80%+  

**Sample Test:** `frontend/src/components/__tests__/LoginForm.test.tsx`

```typescript
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { LoginForm } from '../LoginForm';
import * as authService from '../../services/authService';

jest.mock('../../services/authService');

describe('LoginForm Component', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders login form with email and password fields', () => {
    render(<LoginForm />);
    
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /login/i })).toBeInTheDocument();
  });

  it('displays error message on login failure', async () => {
    const errorMessage = 'Invalid credentials';
    (authService.login as jest.Mock).mockRejectedValue(
      new Error(errorMessage)
    );

    render(<LoginForm />);
    
    await userEvent.type(screen.getByLabelText(/email/i), 'test@example.com');
    await userEvent.type(screen.getByLabelText(/password/i), 'password123');
    await userEvent.click(screen.getByRole('button', { name: /login/i }));

    await waitFor(() => {
      expect(screen.getByText(errorMessage)).toBeInTheDocument();
    });
  });

  it('calls login service with correct credentials', async () => {
    (authService.login as jest.Mock).mockResolvedValue({
      access_token: 'token123',
      user: { id: 'user_1', email: 'test@example.com' }
    });

    render(<LoginForm />);
    
    const email = 'test@example.com';
    const password = 'password123';
    
    await userEvent.type(screen.getByLabelText(/email/i), email);
    await userEvent.type(screen.getByLabelText(/password/i), password);
    await userEvent.click(screen.getByRole('button', { name: /login/i }));

    await waitFor(() => {
      expect(authService.login).toHaveBeenCalledWith(email, password);
    });
  });

  it('validates email format before submission', async () => {
    render(<LoginForm />);
    
    await userEvent.type(screen.getByLabelText(/email/i), 'invalid-email');
    await userEvent.click(screen.getByRole('button', { name: /login/i }));

    expect(screen.getByText(/valid email/i)).toBeInTheDocument();
    expect(authService.login).not.toHaveBeenCalled();
  });

  it('disables submit button while loading', async () => {
    (authService.login as jest.Mock).mockImplementation(
      () => new Promise(resolve => setTimeout(resolve, 1000))
    );

    render(<LoginForm />);
    
    await userEvent.type(screen.getByLabelText(/email/i), 'test@example.com');
    await userEvent.type(screen.getByLabelText(/password/i), 'password123');
    
    const submitButton = screen.getByRole('button', { name: /login/i });
    await userEvent.click(submitButton);

    expect(submitButton).toBeDisabled();
  });
});
```

**Running Tests:**
```bash
# All tests
npm test

# Watch mode
npm test -- --watch

# With coverage
npm test -- --coverage

# Specific file
npm test -- LoginForm.test.tsx

# Update snapshots
npm test -- -u
```

---

## 3. Integration Testing

### 3.1 Backend Integration Tests

**File:** `tests/integration/test_api_endpoints.py`

```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.main import app
from src.database import Base, get_db

# Use test database
TEST_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

class TestAuthEndpoints:
    """Integration tests for auth endpoints"""

    def test_register_user_success(self):
        """Test successful user registration"""
        response = client.post("/api/v1/users/register", json={
            "email": "newuser@example.com",
            "password": "secure_password123",
            "name": "Test User",
            "company": "Test Corp"
        })
        
        assert response.status_code == 201
        data = response.json()["data"]
        assert data["email"] == "newuser@example.com"
        assert data["name"] == "Test User"

    def test_register_user_duplicate_email(self):
        """Test registration rejects duplicate email"""
        # First registration
        client.post("/api/v1/users/register", json={
            "email": "duplicate@example.com",
            "password": "password123",
            "name": "User 1"
        })
        
        # Second registration with same email
        response = client.post("/api/v1/users/register", json={
            "email": "duplicate@example.com",
            "password": "password456",
            "name": "User 2"
        })
        
        assert response.status_code == 409

    def test_login_with_valid_credentials(self):
        """Test login with valid credentials"""
        # First register user
        client.post("/api/v1/users/register", json={
            "email": "testuser@example.com",
            "password": "test_password_123",
            "name": "Test User"
        })
        
        # Then login
        response = client.post("/api/v1/auth/login", json={
            "email": "testuser@example.com",
            "password": "test_password_123"
        })
        
        assert response.status_code == 200
        data = response.json()["data"]
        assert "access_token" in data
        assert data["token_type"] == "Bearer"

    def test_login_with_invalid_password(self):
        """Test login rejects incorrect password"""
        # Register user
        client.post("/api/v1/users/register", json={
            "email": "testuser@example.com",
            "password": "correct_password",
            "name": "Test User"
        })
        
        # Try login with wrong password
        response = client.post("/api/v1/auth/login", json={
            "email": "testuser@example.com",
            "password": "wrong_password"
        })
        
        assert response.status_code == 401

    def test_protected_endpoint_requires_auth(self):
        """Test protected endpoints require authentication"""
        response = client.get("/api/v1/users/profile")
        
        assert response.status_code == 401

    def test_protected_endpoint_with_valid_token(self):
        """Test protected endpoint with valid token"""
        # Register and login
        client.post("/api/v1/users/register", json={
            "email": "authuser@example.com",
            "password": "password123",
            "name": "Auth User"
        })
        
        login_response = client.post("/api/v1/auth/login", json={
            "email": "authuser@example.com",
            "password": "password123"
        })
        
        token = login_response.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Access protected endpoint
        response = client.get("/api/v1/users/profile", headers=headers)
        
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["email"] == "authuser@example.com"
```

**Running Integration Tests:**
```bash
pytest tests/integration/ -v
```

### 3.2 Frontend Integration Tests

**Framework:** Cypress  
**File:** `frontend/cypress/e2e/auth.cy.ts`

```typescript
describe('Authentication Flow', () => {
  beforeEach(() => {
    cy.visit('http://localhost:3000');
  });

  it('should complete user registration', () => {
    cy.contains('Sign Up').click();
    
    cy.get('[data-testid=email-input]').type('newuser@example.com');
    cy.get('[data-testid=password-input]').type('SecurePassword123!');
    cy.get('[data-testid=name-input]').type('Test User');
    cy.get('[data-testid=company-input]').type('Test Corp');
    
    cy.contains('Register').click();
    
    cy.url().should('include', '/dashboard');
    cy.contains('Welcome, Test User').should('be.visible');
  });

  it('should login with valid credentials', () => {
    cy.contains('Login').click();
    
    cy.get('[data-testid=email-input]').type('testuser@example.com');
    cy.get('[data-testid=password-input]').type('TestPassword123!');
    
    cy.contains('Login').click();
    
    cy.url().should('include', '/dashboard');
  });

  it('should show error for invalid credentials', () => {
    cy.contains('Login').click();
    
    cy.get('[data-testid=email-input]').type('testuser@example.com');
    cy.get('[data-testid=password-input]').type('WrongPassword');
    
    cy.contains('Login').click();
    
    cy.contains('Invalid credentials').should('be.visible');
  });

  it('should logout successfully', () => {
    // Login first
    cy.contains('Login').click();
    cy.get('[data-testid=email-input]').type('testuser@example.com');
    cy.get('[data-testid=password-input]').type('TestPassword123!');
    cy.contains('Login').click();
    
    cy.url().should('include', '/dashboard');
    
    // Logout
    cy.get('[data-testid=user-menu]').click();
    cy.contains('Logout').click();
    
    cy.url().should('include', '/login');
  });
});
```

---

## 4. End-to-End (E2E) Testing

### 4.1 E2E Test Scenarios

**File:** `frontend/cypress/e2e/user_journey.cy.ts`

```typescript
describe('Complete User Journey', () => {
  it('should allow user to upload document and search it', () => {
    // 1. Login
    cy.visit('http://localhost:3000');
    cy.contains('Login').click();
    cy.get('[data-testid=email-input]').type('testuser@example.com');
    cy.get('[data-testid=password-input]').type('TestPassword123!');
    cy.contains('Login').click();
    cy.url().should('include', '/dashboard');

    // 2. Navigate to documents
    cy.contains('Documents').click();
    cy.url().should('include', '/documents');

    // 3. Upload document
    cy.get('[data-testid=upload-btn]').click();
    cy.get('[data-testid=file-input]').selectFile('cypress/fixtures/sample_report.pdf');
    cy.get('[data-testid=document-title]').type('Q2 2026 Report');
    cy.get('[data-testid=document-category]').select('knowledge_base');
    cy.contains('Upload').click();

    // 4. Verify upload
    cy.contains('Document queued for processing').should('be.visible');
    cy.get('[data-testid=queue-item]').should('contain', 'Q2 2026 Report');

    // 5. Wait for processing
    cy.get('[data-testid=processing-status]', { timeout: 30000 })
      .should('contain', 'Completed');

    // 6. Navigate to search
    cy.contains('Search').click();
    cy.url().should('include', '/search');

    // 7. Search
    cy.get('[data-testid=search-input]').type('Q2 revenue forecast');
    cy.get('[data-testid=search-btn]').click();

    // 8. Verify results
    cy.get('[data-testid=search-results]').should('be.visible');
    cy.get('[data-testid=result-item]').should('have.length.greaterThan', 0);
    cy.contains('Q2 2026 Report').should('be.visible');

    // 9. Ask AI
    cy.get('[data-testid=ai-question]').type('What is the revenue forecast for Q3?');
    cy.get('[data-testid=ask-btn]').click();

    // 10. Verify AI response
    cy.get('[data-testid=ai-response]', { timeout: 15000 })
      .should('be.visible')
      .and('contain', 'revenue');
    
    cy.get('[data-testid=citations]')
      .should('be.visible')
      .and('contain', 'Q2 2026 Report');
  });
});
```

---

## 5. Smoke Testing

### 5.1 Smoke Test Checklist

Quick tests to verify system is operational:

```bash
#!/bin/bash
# File: infra/smoke_tests.sh

echo "=== Smoke Tests ==="

# Test 1: System Health
echo -n "1. System Health: "
curl -s http://localhost/health > /dev/null && echo "✓" || echo "✗"

# Test 2: Frontend Load
echo -n "2. Frontend Load: "
curl -s http://localhost:3000 | grep -q "<!DOCTYPE" && echo "✓" || echo "✗"

# Test 3: API Response
echo -n "3. API Response: "
curl -s http://localhost/api/v1/docs | grep -q "openapi" && echo "✓" || echo "✗"

# Test 4: Database Connection
echo -n "4. Database Connection: "
docker-compose exec -T postgres pg_isready > /dev/null 2>&1 && echo "✓" || echo "✗"

# Test 5: Redis Connection
echo -n "5. Redis Connection: "
docker-compose exec -T redis redis-cli ping | grep -q "PONG" && echo "✓" || echo "✗"

# Test 6: Qdrant Service
echo -n "6. Qdrant Service: "
curl -s http://localhost:6333/health | grep -q "ok" && echo "✓" || echo "✗"

echo "===  Complete  ==="
```

---

## 6. Performance Testing

### 6.1 Load Test with Locust

**File:** `tests/performance/locustfile.py`

```python
from locust import HttpUser, task, between
import random

class APIUser(HttpUser):
    wait_time = between(1, 3)
    
    def on_start(self):
        # Login once per user
        response = self.client.post("/api/v1/auth/login", json={
            "email": "loadtest@example.com",
            "password": "password123"
        })
        self.token = response.json()["data"]["access_token"]

    @task(3)
    def search_documents(self):
        self.client.post(
            "/api/v1/queries/search",
            json={
                "query": "revenue forecast",
                "top_k": 5
            },
            headers={"Authorization": f"Bearer {self.token}"}
        )

    @task(2)
    def get_documents_list(self):
        self.client.get(
            "/api/v1/documents",
            headers={"Authorization": f"Bearer {self.token}"}
        )

    @task(1)
    def ai_query(self):
        self.client.post(
            "/api/v1/queries/ai-answer",
            json={
                "query": "What is the market trend?",
                "model": "gpt-4-turbo"
            },
            headers={"Authorization": f"Bearer {self.token}"}
        )
```

**Running Load Tests:**
```bash
locust -f tests/performance/locustfile.py --host=http://localhost -u 100 -r 10
# Opens web UI at http://localhost:8089
```

---

## 7. CI/CD Pipeline

### 7.1 GitHub Actions Pipeline

**File:** `.github/workflows/test.yml`

```yaml
name: Test & Deploy

on:
  push:
    branches: [develop, main]
  pull_request:
    branches: [develop, main]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: test_password
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432

    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          cd backend
          pip install -r requirements.txt
      
      - name: Run backend tests
        run: |
          cd backend
          pytest --cov=src --cov-report=xml
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          files: ./backend/coverage.xml
      
      - name: Set up Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '20'
      
      - name: Install frontend dependencies
        run: |
          cd frontend
          npm ci
      
      - name: Run frontend tests
        run: |
          cd frontend
          npm test -- --coverage
      
      - name: Build frontend
        run: |
          cd frontend
          npm run build
```

---

## 8. Test Data & Fixtures

### 8.1 Test Data Loading

**File:** `tests/fixtures/seed_data.py`

```python
from src.models import User, Document
from src.database import get_db
import uuid

def seed_test_users(db):
    """Create test users"""
    users = [
        User(
            id=str(uuid.uuid4()),
            email="user1@example.com",
            name="User One",
            password_hash="hashed_password_1"
        ),
        User(
            id=str(uuid.uuid4()),
            email="user2@example.com",
            name="User Two",
            password_hash="hashed_password_2"
        ),
    ]
    
    for user in users:
        db.add(user)
    db.commit()
    return users

def seed_test_documents(db, user_id):
    """Create test documents"""
    documents = [
        Document(
            id=str(uuid.uuid4()),
            user_id=user_id,
            title="Q1 Financial Report",
            file_name="q1_report.pdf",
            status="processed"
        ),
        Document(
            id=str(uuid.uuid4()),
            user_id=user_id,
            title="Q2 Financial Report",
            file_name="q2_report.pdf",
            status="processed"
        ),
    ]
    
    for doc in documents:
        db.add(doc)
    db.commit()
    return documents
```

---

## 9. Test Reports & Metrics

### 9.1 Coverage Reports

```bash
# Backend coverage
pytest --cov=src --cov-report=html:htmlcov

# Frontend coverage
npm test -- --coverage --watchAll=false
```

### 9.2 Test Execution Dashboard

Create a dashboard to track:
- Test pass/fail rates
- Code coverage trends
- Performance benchmarks
- Deployment frequency

---

## 10. Troubleshooting Tests

### 10.1 Flaky Tests

```python
# Add retry decorator
@pytest.mark.flaky(reruns=3, reruns_delay=2)
def test_unstable_api_call():
    """This test will retry up to 3 times"""
    pass
```

### 10.2 Test Cleanup

```python
@pytest.fixture(autouse=True)
def cleanup_database():
    """Clean up after each test"""
    yield
    # Cleanup code here
    db.clear_all()
```

---

## END OF TESTING & QA GUIDE
