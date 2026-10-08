#!/usr/bin/env python3
"""Offline verifier for Promomed Partner Trust Bundle v1.

Usage:
  python ops/verify_partner_trust_bundle.py BUNDLE_JSON
  python ops/verify_partner_trust_bundle.py BUNDLE_JSON STATUS_JSON ISSUER_JSON

The one-file mode verifies bundle integrity and the signed status material embedded
at packaging time. It intentionally reports currentPromomedStateVerified=false.

The three-file mode additionally verifies against fresh signed snapshot-status
material and a fresh trusted issuer document.
"""

import json
import sys
from pathlib import Path

from app import trust_bundle


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main(argv=None):
    argv=list(argv or sys.argv[1:])
    if len(argv) not in (1,3):
        print(
            "usage: verify_partner_trust_bundle.py BUNDLE_JSON "
            "[STATUS_JSON ISSUER_JSON]",
            file=sys.stderr,
        )
        return 2
    bundle=_load(argv[0])
    status=_load(argv[1]) if len(argv)==3 else None
    issuer=_load(argv[2]) if len(argv)==3 else None
    result=trust_bundle.verify_bundle_portable(
        bundle,
        current_status_statement=status,
        current_issuer_document=issuer,
    )
    print(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2))
    return 0 if result.get("status")=="VALID_TRUST_BUNDLE" else 1


if __name__=="__main__":
    raise SystemExit(main())
