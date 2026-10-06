#!/usr/bin/env python3
import json
import os

from app import db, evidence_monitor


def main():
    if db.backend_name() != "postgres":
        raise RuntimeError("evidence monitor worker requires PostgreSQL authority")
    c=db.connect()
    try:
        db.migrate(c)
        result=evidence_monitor.run_due_jobs(
            c,
            actor=os.environ.get("PROMOMED_EVIDENCE_WORKER_ACTOR","evidence-monitor-worker"),
            limit=int(os.environ.get("PROMOMED_EVIDENCE_WORKER_LIMIT","20")),
            tool=os.environ.get("NCBI_TOOL","promomed-sostoyanie"),
            email=os.environ.get("NCBI_EMAIL",""),
        )
        c.commit()
        print(json.dumps(result,ensure_ascii=False,sort_keys=True))
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()


if __name__=="__main__":
    main()
