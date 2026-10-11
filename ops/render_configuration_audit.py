"""Read-only, fail-closed configuration audit for existing Promomed Render services."""
import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO = "https://github.com/PetrFedin/promomed"
BUILD = "pip install -r requirements.txt && python -m py_compile server.py app/db.py"
START = "python server.py"
SERVICES = {
    "public": ("srv-daug7pnlot8c73b1aja0", "sostoyanie-promomed-live", "commit"),
    "admission": ("srv-davsqk942hec73e1vcr0", "sostoyanie-promomed-pg-admission", "off"),
}


def check(actual, role):
    if not isinstance(actual, dict):
        return ["INVALID_RESPONSE"]
    d = actual.get("serviceDetails") or {}
    r = d.get("envSpecificDetails") or {} if isinstance(d, dict) else {}
    if not isinstance(d, dict) or not isinstance(r, dict):
        return ["INVALID_DETAILS"]
    sid, name, deploy = SERVICES[role]
    mode = actual.get("autoDeployTrigger") or {"yes": "commit", "no": "off"}.get(actual.get("autoDeploy"))
    compact = lambda value: re.sub(r"\s+", " ", value.strip()) if isinstance(value, str) else ""
    repo = lambda value: value.strip().rstrip("/").removesuffix(".git").lower() if isinstance(value, str) else ""
    rules = {
        "ID": actual.get("id") == sid,
        "NAME": actual.get("name") == name,
        "REPOSITORY": repo(actual.get("repo")) == repo(REPO),
        "BRANCH": actual.get("branch") == "main",
        "TYPE": actual.get("type") == "web_service",
        "FREE_PLAN": d.get("plan") == "free",
        "REGION": d.get("region") == "frankfurt",
        "BUILD": compact(r.get("buildCommand")) == BUILD,
        "START": compact(r.get("startCommand")) == START,
        "HEALTH": d.get("healthCheckPath") == "/health",
        "AUTO_DEPLOY": mode == deploy,
    }
    return [field for field, ok in rules.items() if not ok]


def check_deploy(payload, sha):
    if isinstance(payload, list):
        payload = payload[0] if payload else None
    if isinstance(payload, dict) and "deploy" in payload:
        payload = payload["deploy"]
    if not isinstance(payload, dict):
        return ["MISSING_DEPLOY"]
    commit = payload.get("commit") or {}
    return (["DEPLOY_NOT_LIVE"] if payload.get("status") != "live" else []) + (
        ["DEPLOY_SHA_MISMATCH"] if not isinstance(commit, dict) or commit.get("id") != sha else []
    )


def api_get(path, token):
    request = urllib.request.Request(
        "https://api.render.com/v1/" + path,
        headers={"Authorization": "Bearer " + token, "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        raise RuntimeError("Render API HTTP " + str(error.code)) from None
    except (urllib.error.URLError, TimeoutError, ValueError):
        raise RuntimeError("Render API unavailable or invalid response") from None


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", choices=("public", "admission", "both"), default="both")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--live-api", action="store_true")
    source.add_argument("--snapshot-dir")
    parser.add_argument("--expected-sha")
    parser.add_argument("--report-json", help="Write redacted evidence (no payloads or tokens)")
    a = parser.parse_args(argv)
    blueprint = (Path(__file__).resolve().parents[1] / "render.yaml").read_text(encoding="utf-8")
    if not all(x in blueprint for x in ("buildCommand: " + BUILD, "startCommand: " + START, "healthCheckPath: /health", "plan: free")):
        print("RENDER_CONFIG_FAIL: checked-in render.yaml differs from contract")
        return 1
    token = os.getenv("RENDER_API_KEY", "") if a.live_api else ""
    if a.live_api and not token:
        print("RENDER_CONFIG_BLOCKED: missing RENDER_API_KEY")
        return 2
    fail = False
    report = {"schema_version": 1, "kind": "render_config_audit",
              "exact_sha_checked": bool(a.expected_sha), "services": []}
    for role in (SERVICES if a.target == "both" else (a.target,)):
        sid = SERVICES[role][0]
        try:
            def obtain(suffix):
                if a.live_api:
                    return api_get("services/" + sid + ("/deploys?limit=1" if suffix else ""), token)
                return json.loads((Path(a.snapshot_dir) / (role + suffix + ".json")).read_text(encoding="utf-8"))
            errors = check(obtain(""), role)
            if a.expected_sha:
                errors += check_deploy(obtain("-deploy"), a.expected_sha)
        except (RuntimeError, OSError, ValueError):
            errors = ["READ_FAILURE"]
        fail = fail or bool(errors)
        report["services"].append({"role": role, "service_id": sid,
                                   "status": "FAIL" if errors else "PASS",
                                   "codes": errors})
        print(role + ": " + (", ".join(errors) if errors else "CONFIG_PASS"))
    report["status"] = "FAIL" if fail else "PASS"
    report["postgres_admission_proven"] = False
    if a.report_json:
        target = Path(a.report_json)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, indent=2, sort_keys=True) + "\\n", encoding="utf-8")
    print("RENDER_CONFIG_FAIL" if fail else "RENDER_CONFIG_PASS (not PostgreSQL readiness)")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
