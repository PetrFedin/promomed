#!/usr/bin/env python3
"""Process due Promomed partner delivery events.

This worker reads durable event state, dispatches due events through the signed
Partner Delivery Protocol v2, reconciles SLA evidence, and exits. Scheduling
belongs to the deployment platform.
"""

import json
import os
import sys

from app import db, delivery_protocol


def main():
    limit=max(1,min(int(os.environ.get("PROMOMED_DELIVERY_WORKER_LIMIT","100")),500))
    c=db.connect()
    try:
        results=delivery_protocol.dispatch_due(c,limit=limit)
        reconciliation=delivery_protocol.reconcile_sla(c)
        c.commit()
        print(json.dumps({
            "processed":len(results),
            "results":results,
            "reconciliation":reconciliation,
        },ensure_ascii=False,sort_keys=True))
        return 0
    except Exception as exc:
        c.rollback()
        print(json.dumps({
            "error":type(exc).__name__,
            "message":str(exc)[:500],
        },ensure_ascii=False,sort_keys=True),file=sys.stderr)
        return 1
    finally:
        c.close()


if __name__=="__main__":
    raise SystemExit(main())
