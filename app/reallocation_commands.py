from app.commanding import custom,error
from app import reallocation_authority

ROUTES={"/api/reallocation/create-demo","/api/reallocation/accept-demo","/api/reallocation/reset-demo"}

def handle_command(c,route,role,email,data):
    if route not in ROUTES:return None
    if role not in ("sales","organizer"):return error("forbidden",403)
    if route=="/api/reallocation/reset-demo":
        reallocation_authority.reset_demo(c);return custom(reallocation_authority.snapshot(c))
    if route=="/api/reallocation/create-demo":
        reallocation_authority.create_demo_proposal(c,email);return custom(reallocation_authority.snapshot(c))
    try:reallocation_authority.accept_demo(c,str(data.get("approval_role") or "").strip(),email)
    except ValueError as e:return error(str(e),409)
    return custom(reallocation_authority.snapshot(c))
