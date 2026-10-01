import json
import os
from urllib import request, error

def request_json(url,payload=None,method="POST",headers=None,timeout=4):
    if not url:
        return {"ok":False,"error":"provider_not_configured"}
    data=None if payload is None else json.dumps(payload,ensure_ascii=False).encode("utf-8")
    req=request.Request(url,data=data,method=method,headers={"Content-Type":"application/json",**(headers or {})})
    try:
        with request.urlopen(req,timeout=timeout) as res:
            raw=res.read().decode("utf-8","replace")
            try: body=json.loads(raw) if raw else {}
            except Exception: body={"raw":raw[:500]}
            return {"ok":200<=res.status<300,"status":res.status,"body":body}
    except error.HTTPError as exc:
        return {"ok":False,"status":exc.code,"error":"provider_http_error"}
    except Exception:
        return {"ok":False,"error":"provider_unavailable"}

def post_json(url,payload,headers=None,timeout=4):
    return request_json(url,payload,"POST",headers,timeout)

def env_status():
    return {
        "directus":bool(os.environ.get("DIRECTUS_URL")),
        "meilisearch":bool(os.environ.get("MEILISEARCH_URL")),
        "metarank":bool(os.environ.get("METARANK_URL")),
        "owncast":bool(os.environ.get("OWNCAST_BASE_URL")),
        "jitsi":bool(os.environ.get("JITSI_BASE_URL")),
        "pretalx":bool(os.environ.get("PRETALX_URL")),
        "novu":bool(os.environ.get("NOVU_API_URL")),
        "umami":bool(os.environ.get("UMAMI_API_URL")),
        "semantic":bool(os.environ.get("SEMANTIC_RETRIEVAL_URL")),
    }
