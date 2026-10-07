#!/usr/bin/env python3
"""Offline verifier for Promomed external contribution admission receipts.

Usage:
  python ops/verify_contribution_receipt.py receipt.json issuer.json

The verifier needs only public receipt material and a trusted issuer document.
It does not connect to the Promomed database and does not load a signing private key.
"""

import json
import sys
from pathlib import Path

from app import syndication_network


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main(argv=None):
    argv=list(argv or sys.argv[1:])
    if len(argv)!=2:
        print("usage: verify_contribution_receipt.py RECEIPT_JSON ISSUER_JSON",file=sys.stderr)
        return 2
    receipt=_load(argv[0])
    issuer=_load(argv[1])
    result=syndication_network.verify_contribution_receipt(receipt,issuer)
    print(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2))
    return 0 if result.get("status")=="VALID_CONTRIBUTION_ADMISSION_RECEIPT" else 1


if __name__=="__main__":
    raise SystemExit(main())
