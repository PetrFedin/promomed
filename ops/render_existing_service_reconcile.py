"""Reconcile configuration ONLY for two existing Free Promomed Render services.

Uses the official PATCH /v1/services/{id} API. No deploy, env read or DB mutation.
Dry-run by default; --apply is explicit and only patches allowlisted fields.
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request

from render_configuration_audit import BUILD, SERVICES, check

API_BASE = "https://api.render.com/v1/"
EXPECTED_WORKSPACE = "tea-dagitrp5efls73apuv50"
APPLY_CONFIRMATION = "PROMOMED_FREE_EXISTING_ONLY"

LEGACY_PUBLIC_BUILD = "python -m py_compile server.py"
TARGET_HEALTH = "/health"
ALLOWED_HEALTH = ("", TARGET_HEALTH)


class ReconcileError(Exception):
    pass


def request_json(method, path, token, payload=None, opener=None):
    allowed_paths = {"services/" + sid for sid, _, _ in SERVICES.values()}
    if (path.split("?")[0].removesuffix("/deploys") not in allowed_paths
            or not token or not isinstance(token, str)):
        raise ReconcileError("RENDER_API_NOT_AUTHORIZED")
    if method not in ("GET", "PATCH"):
        raise ReconcileError("UNSUPPORTED_METHOD")
    if method == "PATCH":
        if path not in allowed_paths or not isinstance(payload, dict):
            raise ReconcileError("INVALID_PATCH")
        if set(payload) != {"serviceDetails"} or not isinstance(payload["serviceDetails"], dict):
            raise ReconcileError("INVALID_PATCH_FIELDS")
        details = payload["serviceDetails"]
        if not details or set(details) - {"healthCheckPath", "envSpecificDetails"}:
            raise ReconcileError("INVALID_PATCH_FIELDS")
        if details.get("healthCheckPath", TARGET_HEALTH) != TARGET_HEALTH:
            raise ReconcileError("INVALID_PATCH_HEALTH")
        if "envSpecificDetails" in details and details["envSpecificDetails"] != {"buildCommand": BUILD}:
            raise ReconcileError("INVALID_PATCH_BUILD")
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        API_BASE + path, data=body, method=method,
        headers={"Authorization": "Bearer " + token, "Accept": "application/json",
                 "Content-Type": "application/json"},
    )
    try:
        with (opener or urllib.request.urlopen)(request, timeout=20) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        raise ReconcileError("RENDER_API_HTTP_" + str(exc.code)) from None
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        raise ReconcileError("RENDER_API_UNAVAILABLE") from None


def plan_change(role, service):
    """Strict read-only preflight. Returns a minimal Render PATCH body."""
    if role not in SERVICES:
        raise ReconcileError("UNKNOWN_ROLE")
    if not isinstance(service, dict):
        raise ReconcileError("MALFORMED_SERVICE")
    if service.get("ownerId") != EXPECTED_WORKSPACE:
        raise ReconcileError("WRONG_RENDER_WORKSPACE")
    errors = check(service, role)
    unexpected = [e for e in errors if e not in ("BUILD", "HEALTH")]
    if unexpected:
        raise ReconcileError("UNEXPECTED_SERVICE_METADATA:" + ",".join(unexpected))
    details = service.get("serviceDetails")
    env = details.get("envSpecificDetails") if isinstance(details, dict) else None
    if not isinstance(env, dict):
        raise ReconcileError("MALFORMED_BUILD_SETTINGS")
    actual_build = env.get("buildCommand")
    actual_health = details.get("healthCheckPath")
    if actual_health not in ALLOWED_HEALTH:
        raise ReconcileError("UNEXPECTED_HEALTH_PATH")
    if role == "public":
        if actual_build not in (LEGACY_PUBLIC_BUILD, BUILD):
            raise ReconcileError("UNEXPECTED_PUBLIC_BUILD")
    elif actual_build != BUILD:
        raise ReconcileError("UNEXPECTED_ADMISSION_BUILD")
    patch_details = {}
    if actual_health != TARGET_HEALTH:
        patch_details["healthCheckPath"] = TARGET_HEALTH
    if role == "public" and actual_build != BUILD:
        patch_details["envSpecificDetails"] = {"buildCommand": BUILD}
    return {"serviceDetails": patch_details} if patch_details else {}


def latest_deploy_live(payload):
    if isinstance(payload, list):
        payload = payload[0] if payload else None
    if isinstance(payload, dict) and "deploy" in payload:
        payload = payload["deploy"]
    if not isinstance(payload, dict) or payload.get("status") != "live":
        raise ReconcileError("NO_LIVE_DEPLOY")
    commit = payload.get("commit")
    if not isinstance(commit, dict) or not isinstance(commit.get("id"), str):
        raise ReconcileError("MISSING_DEPLOY_SHA")
    return commit["id"]


def reconcile(role, token, apply=False, api=request_json):
    service_id = SERVICES[role][0]
    path = "services/" + service_id
    meta = api("GET", path, token)
    patch = plan_change(role, meta)
    latest_sha = latest_deploy_live(api("GET", path + "/deploys?limit=1", token))
    if not patch:
        return {"role": role, "status": "ALREADY_CONFORMANT", "deploy_sha": latest_sha,
                "patched_fields": []}
    fields = sorted(patch["serviceDetails"])
    if not apply:
        return {"role": role, "status": "DRIFT_DRY_RUN", "deploy_sha": latest_sha,
                "patched_fields": fields}
    api("PATCH", path, token, patch)
    actual = api("GET", path, token)
    if check(actual, role):
        raise ReconcileError("POST_PATCH_VERIFICATION_FAILED")
    return {"role": role, "status": "CONFIG_PATCH_VERIFIED_NOT_DEPLOYED",
            "deploy_sha": latest_sha, "patched_fields": fields}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", choices=("admission", "public", "both"), default="both")
    parser.add_argument("--apply", action="store_true", help="Mutate existing service config; no deploy")
    parser.add_argument("--confirm", default="", help="Explicit Promomed-only confirmation for one target")
    args = parser.parse_args(argv)
    if args.apply and (args.target == "both" or args.confirm != APPLY_CONFIRMATION):
        print("RENDER_RECONCILE_BLOCKED: apply requires single target and exact confirmation")
        return 2
    token = os.getenv("RENDER_API_KEY", "")
    if not token:
        print("RENDER_RECONCILE_BLOCKED: no scoped RENDER_API_KEY")
        return 2
    roles = ("admission", "public") if args.target == "both" else (args.target,)
    for role in roles:
        try:
            result = reconcile(role, token, apply=args.apply)
        except ReconcileError as exc:
            print(role + ": " + str(exc))
            return 1
        # Only public identifiers, status and fixed field names. Never print responses or tokens.
        print(role + ": " + result["status"] + " fields=" +
              ",".join(result["patched_fields"]) + " deploy_sha=" + result["deploy_sha"])
    print("RENDER_RECONCILE_OK (not a deployment or PostgreSQL admission)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
