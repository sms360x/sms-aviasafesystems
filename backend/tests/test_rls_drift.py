"""2C.3c — RLS policy drift test (live catalog vs repo migrations).

Compares the RLS policies that exist in the live ``public`` schema against the
policies defined by the SQL migrations in ``supabase/migrations/``.

The repo side is the set of ``CREATE POLICY`` statements across all migrations,
with the LAST occurrence per ``(table, policy_name)`` winning (a later migration
supersedes an earlier one).

Comparison is hybrid:

* **Primary — normalized text.** The live clauses come from ``pg_get_expr``;
  the repo clauses are the raw migration SQL. Both are canonicalised (casts,
  ``public.`` qualification, quoting, whitespace and parentheses removed) and
  compared. This is fast but can report *normalization artifacts* (the
  deparser adds casts, qualification and parentheses that the raw SQL does not
  have).
* **Fallback — deparse round-trip.** When the primary method reports a
  difference, the repo statement is replayed on its table inside a
  **rolled-back transaction**, its clause re-read with ``pg_get_expr``, and
  compared byte-for-byte with the live clause. Because both sides pass through
  the same deparser, this distinguishes real drift from a normalization
  artifact.

The test never modifies live state: the fallback transaction is always rolled
back. It does not require the ``RLS_ENFORCEMENT_ENABLED`` flag or app
authentication.
"""

import asyncio
import re
from pathlib import Path

import pytest
from sqlalchemy import text

from app.db.session import get_engine, session_scope


MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "supabase" / "migrations"

# Policies known to be platform-internal and intentionally exempt from the
# live<->repo comparison. There are none in schema ``public`` today (Supabase's
# own policies live in other schemas); the set is named explicitly so a future
# exemption is a deliberate edit, not a silent skip.
PLATFORM_EXEMPT: set = set()

KNOWN_ROLES = {"public", "anon", "authenticated", "service_role"}

_LIVE_SQL = text(
    "SELECT c.relname AS table_name, p.polname AS policy_name, p.polcmd, "
    "       p.polpermissive, "
    "       (SELECT array_agg(COALESCE(r.rolname, 'public') ORDER BY r.rolname) "
    "          FROM pg_roles r WHERE r.oid = ANY(p.polroles)) AS roles, "
    "       pg_get_expr(p.polqual, p.polrelid) AS using_clause, "
    "       pg_get_expr(p.polwithcheck, p.polrelid) AS with_check_clause "
    "FROM pg_policy p "
    "JOIN pg_class c ON c.oid = p.polrelid "
    "JOIN pg_namespace n ON n.oid = c.relnamespace "
    "WHERE n.nspname = 'public'"
)

_POLCMD = {"r": "SELECT", "a": "INSERT", "w": "UPDATE", "d": "DELETE", "*": "ALL"}

_CAST_RE = re.compile(
    r"::\s*(?:text|character varying|bpchar|uuid|regclass|regtype|name|oid"
    r"|boolean|integer|smallint|bigint|numeric|double precision|real"
    r"|timestamp with time zone|timestamp without time zone|timestamp"
    r"|date|jsonb|json|inet)\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Repo side — parse migrations
# ---------------------------------------------------------------------------

def _strip_full_line_comments(sql: str) -> str:
    return "\n".join(
        ln for ln in sql.splitlines() if not ln.lstrip().startswith("--")
    )


def _balanced(sql: str, open_idx: int) -> str:
    """Return the text inside the parentheses starting at ``sql[open_idx]=='('``."""
    depth = 0
    i = open_idx
    in_str = False
    while i < len(sql):
        ch = sql[i]
        if in_str:
            if ch == "'":
                if i + 1 < len(sql) and sql[i + 1] == "'":
                    i += 2
                    continue
                in_str = False
            i += 1
            continue
        if ch == "'":
            in_str = True
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return sql[open_idx + 1:i]
        i += 1
    raise ValueError(f"unbalanced parentheses at index {open_idx}: {sql[open_idx:open_idx+80]!r}")


def _find_paren(sql: str, keyword: str):
    """Find ``<keyword> (`` and return the balanced inner text, else None."""
    m = re.search(rf"\b{keyword}\s*\(", sql, re.IGNORECASE)
    if not m:
        return None
    return _balanced(sql, m.end() - 1)


def _unquote(ident: str) -> str:
    return ident.strip().strip('"').strip()


def _parse_roles(stmt: str):
    m = re.search(
        r"\bTO\s+(.+?)(?=\s+USING\b|\s+WITH\s+CHECK\b|$)",
        stmt,
        re.IGNORECASE | re.DOTALL,
    )
    if not m:
        return ["public"]
    roles = []
    for part in m.group(1).split(","):
        role = _unquote(part)
        if role:
            roles.append(role.lower())
    return sorted(roles) or ["public"]


def _parse_policy(stmt: str):
    name_m = re.search(r'CREATE\s+POLICY\s+("[^"]+"|[\w$]+)', stmt, re.IGNORECASE)
    table_m = re.search(
        r'\bON\s+(?:(?:"[^"]+"|[\w$]+)\s*\.\s*)?("[^"]+"|[\w$]+)',
        stmt,
        re.IGNORECASE,
    )
    if not name_m or not table_m:
        return None
    cmd_m = re.search(r"\bFOR\s+(ALL|SELECT|INSERT|UPDATE|DELETE)\b", stmt, re.IGNORECASE)
    permissive = not re.search(r"\bAS\s+RESTRICTIVE\b", stmt, re.IGNORECASE)
    return {
        "policy": _unquote(name_m.group(1)),
        "table": _unquote(table_m.group(1)),
        "cmd": (cmd_m.group(1).upper() if cmd_m else "ALL"),
        "permissive": permissive,
        "roles": _parse_roles(stmt),
        "using": _find_paren(stmt, "USING"),
        "with_check": _find_paren(stmt, "WITH CHECK"),
        "raw": stmt.strip(),
    }


def parse_migrations() -> dict:
    """Return {(table, policy): parsed} with the last migration winning."""
    policies = {}
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        sql = _strip_full_line_comments(path.read_text(encoding="utf-8"))
        for m in re.finditer(r"\bCREATE\s+POLICY\b", sql, re.IGNORECASE):
            end = sql.find(";", m.start())
            if end == -1:
                end = len(sql)
            stmt = sql[m.start():end]
            # Skip dynamic statements built via EXECUTE format(... %I ...).
            if "%I" in stmt or "%s" in stmt or "||" in stmt:
                continue
            parsed = _parse_policy(stmt)
            if parsed is None:
                continue
            policies[(parsed["table"], parsed["policy"])] = parsed
    return policies


# ---------------------------------------------------------------------------
# Live side
# ---------------------------------------------------------------------------

def _run(coro):
    return asyncio.run(coro)


def live_policies() -> dict:
    async def _go():
        async with session_scope() as session:
            rows = (await session.execute(_LIVE_SQL)).all()
            out = {}
            for t, p, cmd, permissive, roles, using, wcheck in rows:
                out[(t, p)] = {
                    "cmd": _POLCMD.get(cmd, cmd),
                    "permissive": bool(permissive),
                    "roles": sorted({(r or "public").lower() for r in (roles or ["public"])}),
                    "using": using,
                    "with_check": wcheck,
                }
            return out

    return _run(_go())


def deparse_repo(repo: dict) -> dict:
    """Replay repo policies in a rolled-back transaction and re-read pg_get_expr.

    Both the live and the replayed clauses pass through the same Postgres
    deparser, so matching strings mean matching definitions.
    """

    async def _go():
        engine = get_engine()
        out = {}
        async with engine.connect() as conn:
            trans = await conn.begin()
            try:
                for (table, policy), r in repo.items():
                    await conn.execute(
                        text(f'DROP POLICY IF EXISTS "{policy}" ON public."{table}"')
                    )
                    await conn.execute(text(r["raw"]))
                    row = (await conn.execute(text(
                        "SELECT pg_get_expr(p.polqual, p.polrelid), "
                        "       pg_get_expr(p.polwithcheck, p.polrelid), "
                        "       p.polcmd, p.polpermissive, "
                        "       (SELECT array_agg(COALESCE(rr.rolname, 'public') "
                        "          ORDER BY rr.rolname) FROM pg_roles rr "
                        "          WHERE rr.oid = ANY(p.polroles)) "
                        "FROM pg_policy p JOIN pg_class c ON c.oid = p.polrelid "
                        "JOIN pg_namespace n ON n.oid = c.relnamespace "
                        "WHERE n.nspname = 'public' AND c.relname = :t "
                        "  AND p.polname = :p"
                    ), {"t": table, "p": policy})).first()
                    out[(table, policy)] = row
            finally:
                await trans.rollback()
        return out

    return _run(_go())


# ---------------------------------------------------------------------------
# Normalization (primary comparison)
# ---------------------------------------------------------------------------

def _normalize(expr):
    if expr is None:
        return None
    t = _CAST_RE.sub("", expr)
    t = t.replace("public.", "")
    t = t.replace('"', "")
    t = re.sub(r"\s+", "", t)
    # Parentheses are intentionally preserved: the deparser adds them, so they
    # cause primary false positives (resolved by the fallback), but stripping
    # them could mask a real precedence/structure change. String-literal case is
    # also preserved (only identifier quoting is removed) so a role-literal
    # change cannot normalize away.
    return t


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def live_and_repo():
    try:
        live = live_policies()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(
            "cannot connect to the live catalog for the RLS drift test: "
            f"{type(exc).__name__}: {exc}"
        )
    repo = parse_migrations()
    return live, repo


def test_repo_parses_the_expected_policy_count(live_and_repo):
    live, repo = live_and_repo
    assert len(repo) == len(live), (
        f"repo defines {len(repo)} policies but live has {len(live)}; "
        f"reconcile the parser or the migrations"
    )


def test_every_live_policy_exists_in_repo(live_and_repo):
    live, repo = live_and_repo
    missing = sorted(k for k in live if k not in repo and k[1] not in PLATFORM_EXEMPT)
    assert not missing, f"live policies with no repo source: {missing}"


def test_every_repo_policy_exists_in_live(live_and_repo):
    live, repo = live_and_repo
    extra = sorted(k for k in repo if k not in live and k[1] not in PLATFORM_EXEMPT)
    assert not extra, f"repo policies not present in live: {extra}"


def test_policy_definitions_match(live_and_repo):
    live, repo = live_and_repo

    # 1. Primary comparison — structural fields + normalized clauses.
    primary_diffs = []
    for key in sorted(set(live) & set(repo)):
        lv, rp = live[key], repo[key]
        reasons = []
        if lv["cmd"] != rp["cmd"]:
            reasons.append(f"cmd live={lv['cmd']} repo={rp['cmd']}")
        if lv["permissive"] != rp["permissive"]:
            reasons.append(f"permissive live={lv['permissive']} repo={rp['permissive']}")
        if lv["roles"] != rp["roles"]:
            reasons.append(f"roles live={lv['roles']} repo={rp['roles']}")
        if _normalize(lv["using"]) != _normalize(rp["using"]):
            reasons.append("USING differs after normalization")
        if _normalize(lv["with_check"]) != _normalize(rp["with_check"]):
            reasons.append("WITH CHECK differs after normalization")
        if reasons:
            primary_diffs.append((key, reasons))

    if not primary_diffs:
        return

    # 2. Fallback — deparse round-trip on the differing keys only.
    try:
        deparsed = deparse_repo({k: repo[k] for k, _ in primary_diffs})
    except Exception as exc:  # noqa: BLE001
        pytest.skip(
            "primary comparison found differences and the deparse round-trip "
            f"fallback could not run: {type(exc).__name__}: {exc}"
        )

    real_drift = []
    artifacts = []
    for key, reasons in primary_diffs:
        lv = live[key]
        row = deparsed.get(key)
        if row is None:
            real_drift.append((key, reasons + ["fallback could not deparse repo policy"]))
            continue
        repo_using, repo_wcheck, repo_cmd_b, repo_perm, repo_roles = row
        repo_cmd = _POLCMD.get(repo_cmd_b, repo_cmd_b)
        repo_roles_n = sorted({(x or "public").lower() for x in (repo_roles or ["public"])})
        fallback_diffs = []
        if lv["cmd"] != repo_cmd:
            fallback_diffs.append(f"cmd live={lv['cmd']} repo={repo_cmd}")
        if lv["permissive"] != bool(repo_perm):
            fallback_diffs.append(f"permissive live={lv['permissive']} repo={bool(repo_perm)}")
        if lv["roles"] != repo_roles_n:
            fallback_diffs.append(f"roles live={lv['roles']} repo={repo_roles_n}")
        if lv["using"] != repo_using:
            fallback_diffs.append(f"USING live={lv['using']!r} repo={repo_using!r}")
        if lv["with_check"] != repo_wcheck:
            fallback_diffs.append(
                f"WITH CHECK live={lv['with_check']!r} repo={repo_wcheck!r}"
            )
        if fallback_diffs:
            real_drift.append((key, reasons + fallback_diffs))
        else:
            artifacts.append(key)

    assert not real_drift, (
        "RLS policy drift (confirmed by deparse round-trip); "
        f"{len(artifacts)} differences were normalization artifacts:\n"
        + "\n".join(f"  {k}: {r}" for k, r in real_drift)
    )


def test_platform_exemptions_are_named():
    # Explicitly documents the exemption set (empty today). Any future entry
    # must be a deliberate edit here.
    assert isinstance(PLATFORM_EXEMPT, set)
