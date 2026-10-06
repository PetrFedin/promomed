#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))

from app import db, reviewer_authority


def fail(code,**extra):
    payload={"ok":False,"error":code}
    payload.update(extra)
    print(json.dumps(payload,ensure_ascii=False))
    raise SystemExit(1)


def parse_until(value):
    if not value:
        return None
    try:
        d=dt.datetime.strptime(value,"%Y-%m-%d").replace(tzinfo=dt.timezone.utc,hour=23,minute=59,second=59)
        return int(d.timestamp())
    except Exception:
        fail("valid_until_must_be_yyyy_mm_dd")


def main():
    p=argparse.ArgumentParser(description="Attest a production medical/scientific reviewer profile and scope.")
    p.add_argument("--email",required=True)
    p.add_argument("--name",required=True)
    p.add_argument("--credential-ref",required=True)
    p.add_argument("--issuer",required=True)
    p.add_argument("--scope",default=reviewer_authority.DEFAULT_SCOPE)
    p.add_argument("--valid-until",default="")
    p.add_argument("--independent-attested",action="store_true")
    args=p.parse_args()

    if db.backend_name()!="postgres":
        fail("postgres_required",backend=db.backend_name())
    if not db.require_postgres() or db.demo_seed_enabled():
        fail("production_database_flags_required")
    if not db.readiness()["production_ready"]:
        fail("database_not_production_ready")
    verifier=os.environ.get("PROMOMED_REVIEWER_VERIFIED_BY","").strip().lower()
    if not verifier:
        fail("PROMOMED_REVIEWER_VERIFIED_BY_required")
    c=db.connect()
    try:
        reviewer_id=reviewer_authority.register_verified_reviewer(
            c,args.email.strip().lower(),args.name.strip(),args.credential_ref.strip(),args.issuer.strip(),
            args.scope.strip(),verifier,parse_until(args.valid_until),args.independent_attested,
        )
        c.commit()
    except ValueError as exc:
        c.rollback(); fail(str(exc))
    except Exception as exc:
        c.rollback(); fail("reviewer_profile_write_failed",detail=type(exc).__name__)
    finally:
        c.close()
    print(json.dumps({"ok":True,"reviewer_id":reviewer_id,"email":args.email.strip().lower(),"scope":args.scope.strip(),"independent_attested":bool(args.independent_attested)},ensure_ascii=False))


if __name__=="__main__":
    main()
