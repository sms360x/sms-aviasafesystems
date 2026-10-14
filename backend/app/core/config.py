from pathlib import Path
from dotenv import load_dotenv

from pydantic_settings import BaseSettings
from typing import List, Optional

# Ensure .env is loaded into os.environ regardless of pydantic-settings path resolution
_env_path = Path(__file__).resolve().parent.parent.parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path, override=False)


class Settings(BaseSettings):
    # ── API ──
    API_VERSION: str = "1.0.0"
    API_PREFIX_AUTH: str = "/api/v1/auth"
    API_PREFIX_REPORTS: str = "/api/v1/reports"
    API_PREFIX_DASHBOARD: str = "/api/v1/dashboard"
    API_PREFIX_ADMIN: str = "/api/v1/admin"
    API_PREFIX_HAZARDS: str = "/api/v1/hazards"
    API_PREFIX_CAN_CAP: str = "/api/v1/cans"
    API_PREFIX_VERIFICATION: str = "/api/v1/verification"
    API_PREFIX_REPORTING: str = "/api/v1/reporting"
    API_PREFIX_FLIGHT_DIVERSIONS: str = "/api/v1/flight-diversions"
    API_PREFIX_STATE_RISK: str = "/api/v1/state-risk"
    API_PREFIX_SURVEYS: str = "/api/v1/surveys"
    API_PREFIX_SMS_MATURITY: str = "/api/v1/sms-maturity"
    API_PREFIX_TENANTS: str = "/api/v1/tenants"
    API_PREFIX_REGULATORS: str = "/api/v1/regulators"
    API_PREFIX_CONTACT: str = "/api/v1/contact"
    API_PREFIX_FEEDBACK: str = "/api/v1/feedback"
    API_PREFIX_COPILOT: str = "/api/v1/copilot"
    API_PREFIX_PSOE: str = "/api/v1/psoe"
    API_PREFIX_AUTH_LEGACY: str = "/api/auth"
    API_PREFIX_REPORTS_LEGACY: str = "/api/reports"
    API_PREFIX_DASHBOARD_LEGACY: str = "/api/dashboard"
    API_PREFIX_ADMIN_LEGACY: str = "/api/admin"
    API_PREFIX_HAZARDS_LEGACY: str = "/api/hazards"
    API_PREFIX_CAN_CAP_LEGACY: str = "/api/cans"
    API_PREFIX_VERIFICATION_LEGACY: str = "/api/verification"
    API_PREFIX_REPORTING_LEGACY: str = "/api/reporting"
    API_PREFIX_FLIGHT_DIVERSIONS_LEGACY: str = "/api/flight-diversions"
    API_PREFIX_STATE_RISK_LEGACY: str = "/api/state-risk"
    API_PREFIX_SURVEYS_LEGACY: str = "/api/surveys"
    API_PREFIX_TENANTS_LEGACY: str = "/api/tenants"
    API_PREFIX_PSOE_LEGACY: str = "/api/psoe"
    DEBUG: bool = False
    # Deployment environment: "production" (default), "beta", "staging",
    # "development". Drives self-service registration gating (production
    # requires the enterprise access key / admin invite code) and beta sandbox
    # tagging (is_beta_sandbox + auto_expire_days on self-service tenants).
    ENVIRONMENT: str = "production"

    # ── CORS ──
    # Single-canonical-domain origin list (betasms.* decommissioned 2026-08).
    ALLOWED_ORIGINS: str = "https://sms.aviasafesystems.com,https://aerosafety-sms-prod.web.app,https://demo.aviasafesystems.com"
    # When set, takes precedence over ALLOWED_ORIGINS (Render-env friendly).
    CORS_ORIGINS: Optional[str] = None

    # ── PostgreSQL ──
    # asyncpg-compatible connection URL. Production points at the Supabase
    # TRANSACTION pooler (PgBouncer, host *.pooler.supabase.com, port 6543)
    # so bursty Render instances do not overwhelm the free-tier connection
    # budget. sslmode=require / pgbouncer hints are normalised by
    # app/db/session.py.
    # Empty by default so the app boots on Firestore-only deployments; the async
    # SQLAlchemy engine is created lazily in app/db/session.py.
    DATABASE_URL: Optional[str] = None
    # Client-side asyncpg command timeout (seconds). A slow query fails fast with
    # a client-side timeout instead of waiting for the server-side
    # statement_timeout. Bounds the Supabase pooler handshake/query stalls.
    DB_COMMAND_TIMEOUT: int = 30
    # Phase 2C.3 — RLS enforcement on the app path. When True, every
    # authenticated transaction also executes `SET LOCAL ROLE authenticated`
    # (in addition to the app.current_* GUCs, which are always set). Enabled in
    # 2C.3d Phase 2 (2026-10-14) after 2C.4 completed the policy set; rollback is
    # this one line (True -> False). Env: RLS_ENFORCEMENT_ENABLED.
    RLS_ENFORCEMENT_ENABLED: bool = True

    # ── Firebase (Auth-only; Firestore removed B4) ──
    FIREBASE_PROJECT_ID: Optional[str] = None
    FIREBASE_PRIVATE_KEY: Optional[str] = None
    FIREBASE_CLIENT_EMAIL: Optional[str] = None
    # Deprecated (phase C, 2026-09-12): Firestore named database (sms-db) — no
    # longer used after B4 Auth-only trim (app/firebase.py no longer creates a
    # Firestore client). Kept for env backward-compat and 30-day rollback;
    # ignored at runtime. Do NOT delete yet.
    FIREBASE_DATABASE_ID: Optional[str] = None
    # Public Firebase Web API key used by the server-side login endpoint
    # (app/services/login_service.py) to verify credentials against the
    # Identity Toolkit REST API. It is the same public key shipped in
    # public/js/firebase.js — not a secret — but is configurable here for
    # non-default projects.
    FIREBASE_WEB_API_KEY: str = "AIzaSyCdCtUuyOcUIoCBEaiWGbhp6_XwZKHsicc"
    FIREBASE_COLLECTION_TENANTS: str = "tenants"
    FIREBASE_COLLECTION_REPORTS: str = "reports"
    FIREBASE_COLLECTION_METADATA: str = "metadata"
    FIREBASE_COLLECTION_USERS: str = "users"
    FIREBASE_COLLECTION_REGULATORS: str = "regulators"
    FIREBASE_COLLECTION_AUDIT_LOGS: str = "audit_logs"
    FIREBASE_DOCUMENT_INFO: str = "info"
    FIREBASE_TOKEN_URI: str = "https://oauth2.googleapis.com/token"

    # ── JWT ──
    JWT_ALGORITHM: str = "RS256"
    JWT_EXPIRES_IN: int = 3600

    # ── AI / Gemini ──
    AI_MODEL: str = "gemini-2.0-pro-exp-02-05"
    AI_PROMPT_VERSION: str = "2.0"
    AI_NARRATIVE_TRUNCATE: int = 5000
    AI_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None

    # ── AI / Groq Copilot ──
    # Groq API key for the Safety & Compliance Copilot chat assistant. When
    # unset the chat endpoint degrades to a helpful offline response (200).
    GROQ_API_KEY: Optional[str] = None
    GROQ_MODEL: str = "openai/gpt-oss-120b"
    GROQ_MAX_TOKENS: int = 900
    GROQ_TEMPERATURE: float = 0.4

    # ── Repository / Pagination ──
    REPO_CACHE_TTL_SECONDS: int = 60
    REPO_DEFAULT_PAGE_SIZE: int = 20
    REPO_MAX_PAGE_SIZE: int = 200
    REPO_QUERY_LIMIT: int = 5000

    # ── Dashboard defaults ──
    DASHBOARD_DEFAULT_DAYS: int = 90
    DASHBOARD_TREND_DAYS: int = 180
    DASHBOARD_RECENT_PAGE_SIZE: int = 10
    DASHBOARD_ADMIN_USAGE_DAYS: int = 30
    DASHBOARD_ADMIN_SYSTEM_DAYS: int = 7
    DASHBOARD_ADMIN_TENANT_DAYS: int = 30

    # ── Module A — SMS maturity assessment cache (MODULE_A_CONTRACT.md §7) ──
    # TTL for the cached LLM assessment; survey submission / manual refresh
    # invalidate it, and a stale read triggers a background re-analysis (P2-1).
    SMS_MATURITY_CACHE_TTL: int = 6 * 3600  # seconds
    # Survey look-back window for the background analysis job (P2-2).
    SMS_MATURITY_ANALYSIS_WINDOW_DAYS: int = 365
    # Bounded retries for a failed background LLM analysis (P2-2).
    SMS_MATURITY_ANALYSIS_MAX_RETRIES: int = 3

    # ── Roles ──
    ROLE_DEFAULT: str = "STAFF"
    ROLE_DEFAULT_REGISTRATION: str = "AIRLINE_ADMIN"
    # 2B.4b: NOT canonicalized. Many out-of-scope readers still compare the
    # literal "CAAN_SMD" (routes/hazards.py, can_cap.py, occurrence_reports.py,
    # reporting.py, …), so dropping it here would make the canonical STATE_SMD
    # pass this gate and then fail those literal checks. Reported as residual
    # (STOP condition: a *_ROLES list has a reader that cannot consume the
    # canonical value). CAAN_SMD is retired in the data (2B.3); it is kept here
    # only until the regulator vocabulary is unified.
    CROSS_TENANT_ROLES: List[str] = ["CAAN_SMD", "STATE_SMD", "SUPER_ADMIN"]
    SUPER_ADMIN_ROLES: List[str] = ["SUPER_ADMIN"]
    # Canonical role constants for the delegated admin hierarchy.
    ROLE_TENANT_ADMIN: str = "TENANT_ADMIN"
    ROLE_DEPT_ADMIN: str = "DEPT_ADMIN"
    # NOTE (2B.4b): ROLE_SAFETY_OFFICER / ROLE_SAG_MEMBER are kept because
    # services/invites.py (out of this item's scope) still reads them. They are
    # removed when invites.py is migrated.
    ROLE_SAFETY_OFFICER: str = "SAFETY_OFFICER"
    ROLE_OFFICER: str = "OFFICER"
    ROLE_STAFF: str = "STAFF"
    ROLE_ACCOUNTABLE_EXECUTIVE: str = "ACCOUNTABLE_EXECUTIVE"
    ROLE_SAG_MEMBER: str = "SAG_MEMBER"
    # Canonical roles (2B.1 design of record, SME 2026-10-12): seven roles.
    CANONICAL_ROLES: List[str] = [
        "SUPER_ADMIN",
        "STATE_SMD",
        "TENANT_ADMIN",
        "DEPT_ADMIN",
        "OFFICER",
        "ACCOUNTABLE_EXECUTIVE",
        "STAFF",
    ]
    # 2B.4b: canonical-only membership. Legacy names were migrated in 2B.3, so
    # the lists no longer carry dual-accept aliases (their names are kept so the
    # out-of-scope readers continue to work).
    TENANT_ADMIN_ROLES: List[str] = ["TENANT_ADMIN"]
    DEPT_ADMIN_ROLES: List[str] = ["DEPT_ADMIN"]
    SAFETY_OFFICER_ROLES: List[str] = ["OFFICER"]
    STAFF_ROLES: List[str] = ["STAFF"]
    ACCOUNTABLE_EXECUTIVE_ROLES: List[str] = ["ACCOUNTABLE_EXECUTIVE"]
    SAG_MEMBER_ROLES: List[str] = ["SAG_MEMBER"]  # reader: services/role_validation.py
    # Roles permitted to act across the whole tenant (tenant admins + cross-tenant).
    TENANT_WIDE_ROLES: List[str] = ["TENANT_ADMIN", "STATE_SMD", "SUPER_ADMIN"]

    # ── Tenant kinds (2A.3c) ──
    # Canonical tenant/service-provider kinds. Not a DB CHECK constraint; the
    # list is expected to grow. 'regulator' is created via its own admin step;
    # 'platform' is created outside the UI.
    TENANT_KINDS: List[str] = [
        "regulator",   # state authority
        "operator",    # airline
        "airport",     # aerodrome operator
        "amo",         # approved maintenance organisation
        "ato",         # approved training organisation
        "ans",         # air navigation service provider
        "platform",    # the vendor's own tenant
    ]
    # Subset exposed to the service-provider creation UI.
    TENANT_KINDS_SERVICE_PROVIDER: List[str] = [
        "operator",
        "airport",
        "amo",
        "ato",
        "ans",
    ]

    # ── Upstash Redis (enabled when REDIS_URL is non-empty) ──
    REDIS_URL: str = ""
    REDIS_ENABLED: bool = True

    # ── Rate limiting ──
    RATE_LIMIT_PER_MINUTE: int = 60
    # Per-tenant daily survey submission cap (configurable per deployment).
    SURVEY_RATE_LIMIT: int = 5
    # Max failed login attempts per IP per 15-min sliding window. Raised from
    # 5 (credential-stuffing default) to 20 to avoid blocking operators during
    # staging/testing while keeping a basic brute-force guard.
    LOGIN_FAILURE_RATE_LIMIT: int = 20

    # ── Admin security (env-only; RC-1) ──
    # Setup key used as a second factor on admin provisioning endpoints. Never
    # hardcoded; must be provided via the environment. Access is never granted
    # by the key alone — a SUPER_ADMIN Firebase ID token is always required.
    SETUP_SECRET: Optional[str] = None
    # Shared secret for internal scheduled tasks (e.g. the Cloud Scheduler job
    # that runs the overdue/escalation check). Sent as the X-Task-Key header.
    TASK_API_KEY: Optional[str] = None
    # Password used by /provision-airlines. No hardcoded fallback.
    DEFAULT_PROVISION_PASSWORD: Optional[str] = None
    # Password used by the seed data pipeline (backend/seed). No hardcoded fallback.
    DEFAULT_SEED_PASSWORD: Optional[str] = None
    # When True (default), data-destructive endpoints (/seed-demo-data,
    # /create-seed-users) return 404. Disable only in non-production environments.
    DISABLE_DESTRUCTIVE_ENDPOINTS: bool = True

    # ── Self-service onboarding ──
    # Access key required for public tenant registration and enterprise
    # onboarding. No hardcoded fallback: the value must be supplied by the
    # environment and a provided key must match exactly.
    #
    # Rotated 2026-09-18 due to public exposure in git history. The old value
    # must be treated as compromised; the new value is set in the Render
    # dashboard (render.yaml: sync: false) and never committed. Production
    # refuses to start when this is unset (see app.main._validate_production_config).
    BETA_ACCESS_KEY: Optional[str] = None

    # ── Tenant credentials / welcome email ──
    # When True (default), tenant onboarding seeds the ICAO hazard register
    # via the unified seeder (Postgres path only; Firestore is removed).
    # Disabled in tests so the suite stays hermetic against the live DB.
    ONBOARDING_HAZARD_SEED: bool = True

    # Provider: none (log + preview only), smtp, or sendgrid.
    EMAIL_PROVIDER: str = "none"
    EMAIL_FROM: Optional[str] = None
    EMAIL_FROM_NAME: str = "AviaSAFE SMS Team"
    APP_LOGIN_URL: str = "https://sms.aviasafesystems.com"
    APP_SUPPORT_EMAIL: str = "info@aviasafesystems.com"
    SENDGRID_API_KEY: Optional[str] = None
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASS: Optional[str] = None

    # ── Gmail REST API dispatcher (registration intake acknowledgments) ──
    # Dedicated Gmail channel used by app/services/gmail_dispatcher.py to send
    # self-service registration acknowledgments over HTTPS (port 443) via the
    # Gmail REST API with an OAuth2 refresh-token flow. Leave
    # GMAIL_CLIENT_ID / GMAIL_REFRESH_TOKEN empty to skip delivery (the
    # acknowledgment is logged only and the provisioned tenant record is never
    # rolled back).
    GMAIL_CLIENT_ID: Optional[str] = None
    GMAIL_CLIENT_SECRET: Optional[str] = None
    GMAIL_REFRESH_TOKEN: Optional[str] = None
    GMAIL_SENDER_EMAIL: Optional[str] = None
    GMAIL_NOTIFICATION_BCC: Optional[str] = None

    # ── Contact form / Sender.net ──
    # Sender.net REST API v2. The key must be set via the environment (Render
    # dashboard); never commit the key to the repository.
    SENDER_API_KEY: Optional[str] = None
    # Email the contact form submissions are associated with.
    SENDER_FROM_EMAIL: str = "info@aviasafesystems.com"
    # Optional Sender list/group id to add contacts to. Empty = account default.
    SENDER_LIST_ID: Optional[str] = None
    SENDER_API_BASE_URL: str = "https://api.sender.net/v2"

    # ── Server ──
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 1

    model_config = {"env_file": "backend/.env", "env_file_encoding": "utf-8", "case_sensitive": True, "extra": "ignore"}


settings = Settings()


# ============================================================================
# Canonical department model (2B.4a)
#
# ONE source of truth for department codes + labels. The per-classification
# scoping (OperationalScope.departments, app/models/tenant_profile.py) is a view
# over this union. Every department a classification declares is present here.
# ============================================================================
DEPARTMENT_CODES = [
    # Operator departments
    ("safety", "Safety"),
    ("flight_ops", "Flight Operations"),
    ("camo", "CAMO"),
    ("maintenance_145", "Part-145"),
    ("qa", "QA"),
    ("ground_ops", "Ground Operations"),
    # Aerodrome departments
    ("airside_ops", "Airside Operations"),
    ("arff", "ARFF (Rescue & Firefighting)"),
    # Regulator departments
    ("smd", "Safety Management Division"),
    ("fssd", "Flight Safety Standards Division"),
    ("assd", "Aerodrome Safety Standards Division"),
]

DEPARTMENT_LABELS = {code: label for code, label in DEPARTMENT_CODES}
DEPARTMENT_CODES_SET = {code for code, _ in DEPARTMENT_CODES}
# code-or-label (case/space/underscore-insensitive) -> canonical code.
_DEPT_LOOKUP = {}
for _code, _label in DEPARTMENT_CODES:
    _DEPT_LOOKUP[_code.lower().replace("_", " ")] = _code
    _DEPT_LOOKUP[_label.lower().replace("_", " ")] = _code


def department_code(value):
    """Resolve a code or label to its canonical department code (or the raw
    string when unknown/empty)."""
    raw = str(value or "").strip()
    if not raw:
        return ""
    return _DEPT_LOOKUP.get(raw.lower().replace("_", " "), raw)
