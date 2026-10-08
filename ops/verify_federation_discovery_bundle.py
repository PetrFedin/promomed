#!/usr/bin/env python3
"""Offline verifier for Promomed Federation Discovery Bundle v1.

Usage:
  python ops/verify_federation_discovery_bundle.py BUNDLE_JSON ISSUER_JSON

No Promomed database or private signing key is required.
"""

import json
import sys
from pathlib import Path

from app import federation_interop


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main(argv=None):
    argv=list(argv or sys.argv[1:])
    if len(argv)!=2:
        print(
            "usage: verify_federation_discovery_bundle.py BUNDLE_JSON ISSUER_JSON",
            file=sys.stderr,
        )
        return 2
    result=federation_interop.verify_discovery_bundle(
        _load(argv[0]),
        _load(argv[1]),
    )
    print(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2))
    return 0 if result.get("status")=="VALID_FEDERATION_DISCOVERY_BUNDLE" else 1


if __name__=="__main__":
    raise SystemExit(main())
