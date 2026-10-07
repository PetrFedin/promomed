#!/usr/bin/env python3
"""Offline/public-material verifier for Promomed Evidence Checkpoints.

Usage:
  python ops/verify_evidence_checkpoint.py envelope.json issuer.json [status.json]

The verifier needs only the checkpoint envelope, a trusted issuer document and,
optionally, the latest status list. It never loads the issuer private key.
"""

import json
import sys
from pathlib import Path

from app import evidence_checkpoint


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main(argv=None):
    argv=list(argv or sys.argv[1:])
    if len(argv) not in (2,3):
        print("usage: verify_evidence_checkpoint.py ENVELOPE_JSON ISSUER_JSON [STATUS_JSON]",file=sys.stderr)
        return 2

    envelope=_load(argv[0])
    issuer=_load(argv[1])
    status=_load(argv[2]) if len(argv)==3 else {}
    result=evidence_checkpoint.verify_portable(envelope,issuer,status)
    print(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2))
    return 0 if result.get("status")=="VALID_PORTABLE" else 1


if __name__=="__main__":
    raise SystemExit(main())
