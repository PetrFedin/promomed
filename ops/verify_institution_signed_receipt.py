#!/usr/bin/env python3
"""Offline verifier for Promomed institution-signed trust verification receipts.

Usage:
  python ops/verify_institution_signed_receipt.py \
    RECEIPT_JSON BUNDLE_JSON ANCHOR_STATUS_JSON PROMOMED_ISSUER_JSON

The verifier checks:
  Promomed-signed anchor status -> institution public key -> institution receipt ->
  exact Partner Trust Bundle verification result.

No Promomed database, Promomed signing private key, or institution private key is used.
"""

import json
import sys
from pathlib import Path

from app import federated_trust


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main(argv=None):
    argv=list(argv or sys.argv[1:])
    if len(argv)!=4:
        print(
            "usage: verify_institution_signed_receipt.py "
            "RECEIPT_JSON BUNDLE_JSON ANCHOR_STATUS_JSON PROMOMED_ISSUER_JSON",
            file=sys.stderr,
        )
        return 2
    result=federated_trust.verify_signed_receipt_portable(
        _load(argv[0]),
        _load(argv[1]),
        _load(argv[2]),
        _load(argv[3]),
    )
    print(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2))
    return 0 if result.get("status")=="VALID_INSTITUTION_SIGNED_RECEIPT" else 1


if __name__=="__main__":
    raise SystemExit(main())
