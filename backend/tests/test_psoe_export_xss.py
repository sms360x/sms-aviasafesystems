# ============================================================================
# 3C.1B (F-P1-2) — PSOE HTML preview must render untrusted assessment fields
# as text, never as executable HTML. Pure-function test: no DB, no network.
# ============================================================================

from app.models.psoe import PSOEAssessment
from app.routes.psoe import _render_report_template


EVIL = (
    "'\"><script>alert('auditor')</script>"
    "<img src=x onerror=alert('tenant')>"
)


def _assessment(**overrides):
    base = {
        "id": "a1",
        "tenant_id": "tenant-x",
        "title": "Q1 audit",
        "template_version": "v1",
        "auditor_name": "Normal Auditor",
        "component_scores": {},
        "responses": [],
    }
    base.update(overrides)
    return PSOEAssessment(**base)


def test_auditor_name_rendered_as_text():
    html = _render_report_template(
        _assessment(auditor_name=EVIL), template=None)
    assert "<script>alert('auditor')</script>" not in html
    assert "<img src=x" not in html
    assert "&lt;script&gt;" in html


def test_tenant_id_rendered_as_text():
    html = _render_report_template(
        _assessment(tenant_id=EVIL), template=None)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_component_names_escaped():
    html = _render_report_template(
        _assessment(component_scores={
            "component_1": {"score_pct": 50.0, "score": 5, "max_score": 10},
        }),
        template=None,
    )
    # Server-side fixed names contain '&' — must render escaped, not raw.
    assert "Safety Policy &amp; Objectives" in html
    assert "Safety Policy & Objectives" not in html


def test_benign_report_unchanged_shape():
    html = _render_report_template(_assessment(), template=None)
    assert "Normal Auditor" in html
    assert "tenant-x" in html
    assert "text/html" not in html  # renderer returns body HTML, not headers
    assert "<table" in html or "<tr>" in html
