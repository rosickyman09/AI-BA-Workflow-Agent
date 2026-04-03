"""
RBAC middleware for backend service.
Decodes JWT issued by auth_service and enforces role-based access.
No database needed - all user info is embedded in the JWT claims.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import List
from jose import JWTError, jwt
import os

JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"

security = HTTPBearer()


class TokenUser:
    """User info extracted from JWT claims"""
    def __init__(self, payload: dict):
        self.user_id = payload.get("sub")
        self.email = payload.get("email")
        self.role = payload.get("role")
        self.full_name = payload.get("full_name")
        raw_projects = payload.get("projects", [])
        self.projects = [
            p["project_id"] if isinstance(p, dict) else p
            for p in raw_projects
        ]


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> TokenUser:
    """Decode JWT and return current user. Raises 401 if invalid."""
    try:
        payload = jwt.decode(
            credentials.credentials,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM]
        )
        token_type = payload.get("type", "access")
        if token_type != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type"
            )
        return TokenUser(payload)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )


def make_require_role(required_roles: List[str]):
    """Factory: returns a FastAPI dependency that enforces role membership."""
    async def role_checker(current_user: TokenUser = Depends(get_current_user)) -> TokenUser:
        if current_user.role not in required_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Role '{current_user.role}' is not permitted. "
                       f"Required one of: {required_roles}"
            )
        return current_user
    return role_checker


# ── Role dependencies ──────────────────────────────────────────────────────────
# admin only
require_admin = make_require_role(["admin"])

# Approvers: ba and pm can approve step 2; business_owner approves step 1
require_approver = make_require_role(["admin", "business_owner", "ba", "pm", "legal"])
require_reviewer = make_require_role(["admin", "business_owner", "ba", "pm", "legal"])

# BA / document creators: ba, pm, tech_lead, business_owner, admin
require_ba = make_require_role(["admin", "ba", "business_owner", "pm", "tech_lead"])

# Read-only: every authenticated role
require_readonly = make_require_role(["admin", "ba", "business_owner", "it", "pm",
                                      "tech_lead", "legal", "finance", "viewer"])
