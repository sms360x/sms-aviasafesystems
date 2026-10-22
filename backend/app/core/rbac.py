from typing import Any, Dict, List, Optional

# Module-based permissions per role
PERMISSIONS = {
    'tenant_admin': ['module1', 'module2', 'module3', 'settings'],
    'safety_manager': ['module1', 'module2', 'module3'],
    'department_head': ['module2'],
    'employee': ['module2'],
    'regulator': ['module5'],
    # Accountable Executive: tenant-wide read/oversight (Modules 1-3); the
    # narrow terminal writes are enforced by dedicated route gates, not here.
    'accountable_executive': ['module1', 'module2', 'module3'],
    # Safety Action Group member: Module B review.
    'sag_member': ['module2'],
}

# Human-readable role definitions
ROLES = {
    'tenant_admin': 'Full access to their tenant (Modules 1, 2, 3, Settings)',
    'safety_manager': 'Modules 1, 2, 3 (full access)',
    'department_head': 'Module 2 only (hazards, CAN/CAP)',
    'employee': 'Submit reports, view own submissions (Module 2 limited)',
    'regulator': 'Module 5 only (aggregated view)',
    'accountable_executive': 'Tenant-wide oversight (Modules 1-3); terminal CAP/EIP + risk acceptance',
    'sag_member': 'Module 2 safety review (SAG)',
}

# Module mapping for endpoints
MODULE_ENDPOINTS = {
    'module1': ['/maturity', '/survey', '/module1'],
    'module2': ['/hazards', '/sram', '/cans', '/caps', '/reports'],
    'module3': ['/safety', '/dashboard'],
    'module5': ['/regulator', '/industry', '/aggregation', '/benchmark'],
    'settings': ['/settings', '/admin/tenants'],
}

def has_permission(role: str, module: str) -> bool:
    """Check if role has permission for module."""
    if not role or not module:
        return False
    allowed = PERMISSIONS.get(role, [])
    return module in allowed

def get_permissions(role: str) -> List[str]:
    return PERMISSIONS.get(role, [])

def get_role_display(role: str) -> str:
    return ROLES.get(role, "Unknown role")

def is_regulator(role: str) -> bool:
    return role == 'regulator'

def is_tenant_user(role: str) -> bool:
    return role in (
        'tenant_admin', 'safety_manager', 'department_head', 'employee',
        'accountable_executive', 'sag_member',
    )

# ---------------------------------------------------------------------------
# Department-scoped Safety Officer rule (Step-3 RBAC hardening)
#
# Step-3 retired the STAFF role and folded the general employee into OFFICER.
# OFFICER is NOT a Safety Officer by itself: only an officer that belongs to
# the Safety (Corporate Safety) department holds Safety Manager privileges.
# A Flight Ops / Maintenance / CAMO officer falls back to the least-privilege
# employee profile (Module 2 only). This mirrors the rule already applied to
# raw VSR visibility (can_view_raw_vsr) and to the department scoping model
# of DEPARTMENT_CODES (app/core/config.py).
# ---------------------------------------------------------------------------

# Canonical department codes that count as "the Safety Department".
SAFETY_DEPARTMENT_CODES = frozenset({"safety", "corporate_safety"})

# Legacy role literal that is a Safety Officer regardless of department
# (compatibility only; no live account holds it).
SAFETY_OFFICER_ROLE = "SAFETY_OFFICER"


def department_code(department: Optional[str]) -> str:
    """Normalise a department value to its canonical lower-case code."""
    return (department or "").strip().lower()


def is_safety_department(department: Optional[str]) -> bool:
    """True when the department is the Safety (Corporate Safety) department."""
    return department_code(department) in SAFETY_DEPARTMENT_CODES


def is_safety_officer(user: Optional[Dict[str, Any]] = None) -> bool:
    """True when the caller holds Safety Officer (Safety Manager) privileges.

    - the legacy ``SAFETY_OFFICER`` literal is admitted for compatibility;
    - ``OFFICER`` only when it belongs to the Safety department.
    """
    user = user or {}
    role = (user.get("role") or "").strip().upper()
    if role == SAFETY_OFFICER_ROLE:
        return True
    if role == "OFFICER":
        return is_safety_department(user.get("department"))
    return False


def normalize_legacy_role(legacy_role: str, department: Optional[str] = None) -> str:
    """Map legacy roles to new RBAC roles.

    ``OFFICER`` is department-scoped: only an officer of the Safety
    department maps to ``safety_manager``; every other officer (Flight Ops,
    Maintenance, CAMO, ...) falls back to the least-privilege ``employee``
    profile.
    """
    mapping = {
        'TENANT_ADMIN': 'tenant_admin',
        'SUPER_ADMIN': 'tenant_admin',  # super admin has tenant_admin + regulator via separate logic
        'STATE_SMD': 'regulator',
        'SAFETY_OFFICER': 'safety_manager',
        'DEPT_ADMIN': 'department_head',
        'USER': 'employee',
        'ACCOUNTABLE_EXECUTIVE': 'accountable_executive',
        'SAG_MEMBER': 'sag_member',
    }
    if legacy_role == 'OFFICER':
        return 'safety_manager' if is_safety_department(department) else 'employee'
    return mapping.get(legacy_role, 'employee')
