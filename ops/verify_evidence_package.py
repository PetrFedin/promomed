#!/usr/bin/env python3
"""Offline verifier for Promomed Institutional Evidence Packages.

Usage:
  python ops/verify_evidence_package.py package.json issuer.json [status.json]

The verifier requires only public package material, a trusted issuer document and
optionally a current status list. It does not connect to the Promomed database and
does not load a signing private key.
"""

import json
import sys
from pathlib import Path

from app import evidence_interchange


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main(argv=None):
    argv=list(argv or sys.argv[1:])
    if len(argv) not in (2,3):
        print("usage: verify_evidence_package.py PACKAGE_JSON ISSUER_JSON [STATUS_JSON]",file=sys.stderr)
        return 2

    package=_load(argv[0])
    issuer=_load(argv[1])
    status=_load(argv[2]) if len(argv)==3 else {}
    result=evidence_interchange.verify_package_portable(package,issuer,status)
    print(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2))
    return 0 if result.get("status")=="VALID_PORTABLE_PACKAGE" else 1


if __name__=="__main__":
    raise SystemExit(main())
