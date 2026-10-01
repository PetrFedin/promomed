import contextlib
import functools
import os
import secrets
from urllib.parse import urlparse

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.sampling import TraceIdRatioBased
from opentelemetry.sdk.trace.export import BatchSpanProcessor

_CONFIGURED=False
_SERVICE=os.environ.get("OTEL_SERVICE_NAME","sostoyanie-promomed")
_RELEASE=os.environ.get("RENDER_GIT_COMMIT",os.environ.get("PROMOMED_RELEASE_SHA","unknown"))
_ENDPOINT=os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT","").strip()
_SAMPLE=float(os.environ.get("OTEL_TRACES_SAMPLER_ARG","0.10") or "0.10")

def configure_observability():
    global _CONFIGURED
    if _CONFIGURED:
        return
    provider=TracerProvider(
        resource=Resource.create({
            "service.name":_SERVICE,
            "service.version":_RELEASE,
            "deployment.environment":os.environ.get("PROMOMED_ENV","demo"),
        }),
        sampler=TraceIdRatioBased(max(0.0,min(_SAMPLE,1.0))),
    )
    if _ENDPOINT:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=_ENDPOINT)))
    trace.set_tracer_provider(provider)
    _CONFIGURED=True

def _tracer():
    configure_observability()
    return trace.get_tracer("promomed")

def observability_status():
    return {
        "enabled":True,
        "exporter_configured":bool(_ENDPOINT),
        "service":_SERVICE,
        "release_sha":_RELEASE,
        "sample_ratio":max(0.0,min(_SAMPLE,1.0)),
        "redaction":"allowlist_no_pii_no_free_text_no_secrets",
    }

def _correlation(headers):
    incoming=(headers.get("X-Correlation-ID","") if headers else "").strip()
    if incoming and len(incoming)<=80 and all(ch.isalnum() or ch in "-_." for ch in incoming):
        return incoming
    return secrets.token_hex(16)

def http_handler_trace(func):
    @functools.wraps(func)
    def wrapped(self,*args,**kwargs):
        path=urlparse(getattr(self,"path","/")).path
        method=getattr(self,"command",func.__name__.replace("do_",""))
        correlation=_correlation(getattr(self,"headers",None))
        self._correlation_id=correlation
        with _tracer().start_as_current_span("http.request") as span:
            span.set_attribute("http.request.method",method)
            span.set_attribute("http.route",path)
            span.set_attribute("promomed.correlation_id",correlation)
            span.set_attribute("promomed.release_sha",_RELEASE)
            try:
                return func(self,*args,**kwargs)
            except Exception as exc:
                # Record type only. Exception messages may contain user/provider text.
                span.set_attribute("error.type",exc.__class__.__name__)
                raise
    return wrapped

def set_response_status(status):
    span=trace.get_current_span()
    if span and span.is_recording():
        span.set_attribute("http.response.status_code",int(status))

def _db_shape(sql):
    text=" ".join(str(sql).strip().split())
    upper=text.upper()
    operation=(upper.split(" ",1)[0] if upper else "UNKNOWN")
    table="unknown"
    import re
    patterns=[
        r"^(?:SELECT).*?\bFROM\s+([A-Za-z_][A-Za-z0-9_]*)",
        r"^(?:INSERT)\s+INTO\s+([A-Za-z_][A-Za-z0-9_]*)",
        r"^(?:UPDATE)\s+([A-Za-z_][A-Za-z0-9_]*)",
        r"^(?:DELETE)\s+FROM\s+([A-Za-z_][A-Za-z0-9_]*)",
        r"^(?:CREATE)\s+(?:TABLE|INDEX)\s+(?:IF\s+NOT\s+EXISTS\s+)?([A-Za-z_][A-Za-z0-9_]*)",
    ]
    for pattern in patterns:
        m=re.search(pattern,text,re.I)
        if m:
            table=m.group(1); break
    return operation,table

@contextlib.contextmanager
def db_span(sql,backend):
    operation,table=_db_shape(sql)
    with _tracer().start_as_current_span("db.command") as span:
        span.set_attribute("db.system","postgresql" if backend=="postgres" else "sqlite")
        span.set_attribute("db.operation.name",operation)
        span.set_attribute("db.collection.name",table)
        # Deliberately no db.statement and no bind parameters.
        yield

@contextlib.contextmanager
def provider_span(url,method):
    host=urlparse(url).hostname or "provider"
    with _tracer().start_as_current_span("provider.request") as span:
        span.set_attribute("server.address",host)
        span.set_attribute("http.request.method",method)
        # Deliberately no URL query/body/credentials.
        try:
            yield span
        except Exception as exc:
            span.set_attribute("error.type",exc.__class__.__name__)
            raise
