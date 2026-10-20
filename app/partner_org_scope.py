"""Membership-gated partner project scope.

No user-supplied organization is trusted until an active, verified membership
is confirmed against the institution authority and the authenticated account.
Legacy unscoped demo projects are isolated from real production admission.
"""
import re
import time
from app import db

ORG_ID=re.compile(r"^[A-Za-z0-9][A-Za-z0-9:_-]{0,99}$")


def org_id(value):
    return value.strip() if isinstance(value,str) and ORG_ID.fullmatch(value.strip()) else ""


def legacy_demo_allowed():
    return db.backend_name()=="sqlite" or db.demo_seed_enabled()


def member(c, organization_id, email):
    """Return active membership projection, or None with no existence leakage."""
    now=int(time.time())
    return c.execute(
        """SELECT o.id organization_id,o.name,o.demo_only,m.member_role
           FROM institutional_organizations o
           JOIN institutional_memberships m ON m.organization_id=o.id
           JOIN accounts a ON a.email=m.account_email
           WHERE o.id=? AND o.status='active'
             AND m.account_email=? AND a.status='active' AND a.role='partner'
             AND m.status='active'
             AND m.member_role IN ('operator','administrator')
             AND m.effective_at<=?
             AND (m.expires_at IS NULL OR m.expires_at>?)
             AND m.demo_only=o.demo_only
             AND LENGTH(TRIM(m.verification_ref))>0
             AND (o.demo_only=1 OR m.account_email NOT LIKE ?)
           ORDER BY CASE m.member_role WHEN 'administrator' THEN 1 ELSE 2 END
           LIMIT 1""",
        (organization_id,str(email or "").strip().lower(),now,now,"%@demo.ru"),
    ).fetchone()


def valid_scope(c, project_id, project_demo_only, role, email):
    """Return scope identifier, False if forbidden, None for legacy demo."""
    s=c.execute(
        "SELECT organization_id,demo_only FROM partner_collab_project_scopes WHERE project_id=?",
        (project_id,),
    ).fetchone()
    if not s:
        return None if project_demo_only and legacy_demo_allowed() else False
    org=c.execute(
        "SELECT status,demo_only FROM institutional_organizations WHERE id=?",
        (s["organization_id"],),
    ).fetchone()
    if not org or org["status"]!="active" or int(org["demo_only"])!=int(s["demo_only"]) or int(org["demo_only"])!=int(project_demo_only):
        return False
    if role=="organizer":
        authorized=c.execute("SELECT 1 FROM accounts WHERE email=? AND role='organizer' AND status='active'",
                             (str(email or "").strip().lower(),)).fetchone()
        return s["organization_id"] if authorized else False
    m=member(c,s["organization_id"],email)
    return s["organization_id"] if m and int(m["demo_only"])==int(project_demo_only) else False


def accessible_project(c,row,role,email):
    if row is None:
        return False
    scope=valid_scope(c,row["id"],int(row["demo_only"]),role,email)
    if scope is False:
        return False
    if scope is None:
        return role=="organizer" or row["owner_email"]==email
    return role=="organizer" or role=="partner"


def partner_organizations(c,email):
    """Only organizations already admitted by the governance member authority."""
    now=int(time.time())
    q=c.execute(
        """SELECT DISTINCT o.id,o.name,o.demo_only
           FROM institutional_organizations o
           JOIN institutional_memberships m ON m.organization_id=o.id
           JOIN accounts a ON a.email=m.account_email
           WHERE m.account_email=? AND a.status='active' AND a.role='partner'
             AND o.status='active' AND m.status='active'
             AND m.member_role IN ('operator','administrator')
             AND m.effective_at<=?
             AND (m.expires_at IS NULL OR m.expires_at>?)
             AND m.demo_only=o.demo_only
             AND LENGTH(TRIM(m.verification_ref))>0
             AND (o.demo_only=1 OR m.account_email NOT LIKE ?)
           ORDER BY o.name,o.id LIMIT 100""",
        (str(email or "").strip().lower(),now,now,"%@demo.ru"),
    )
    # At this stage the collaboration lifecycle is demonstrational only.
    return [dict(row) for row in q if int(row["demo_only"])==1]


def commercial_member(c, organization_id, email):
    """Partner-scoped commercial authority requires a current partner binding.

    Verified membership alone does not authorize access after a partner is
    unassigned from the organization. Other collaboration authorities keep
    their existing, independent membership rules.
    """
    admission = member(c, organization_id, email)
    if admission is None:
        return None
    row = c.execute(
        "SELECT partner_id,demo_only FROM institutional_organizations "
        "WHERE id=? AND status='active'", (organization_id,),
    ).fetchone()
    if not row or not isinstance(row["partner_id"], str) or not row["partner_id"].strip():
        return None
    if not db.demo_seed_enabled() and int(row["demo_only"] or 0) != 0:
        return None
    return admission
