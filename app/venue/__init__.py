from app.domain import audit, dump, hash_text, now, uid

def create_asset(c,data,actor):
    geojson=data.get("geojson") or {"type":"FeatureCollection","features":[]}
    if not isinstance(geojson,dict) or geojson.get("type")!="FeatureCollection":
        raise ValueError("feature_collection_required")
    raw=dump(geojson)
    version=(c.execute("SELECT COUNT(*) n FROM venue_assets").fetchone()["n"] or 0)+1
    aid=str(data.get("id") or uid("venue_asset"))
    c.execute("INSERT INTO venue_assets(id,version,geojson,asset_hash,state,created_at) VALUES(?,?,?,?,?,?)",
              (aid,version,raw,hash_text(raw),str(data.get("state") or "approved"),now()))
    audit(c,"venue_asset_created",actor,{"asset_id":aid,"version":version})
    return get_asset(c,aid)

def add_poi(c,asset_id,data,actor):
    if not c.execute("SELECT 1 FROM venue_assets WHERE id=?",(asset_id,)).fetchone():
        raise LookupError("asset_not_found")
    pid=str(data.get("id") or uid("poi"))
    c.execute("INSERT INTO venue_pois(id,asset_id,kind,label,properties_json,created_at) VALUES(?,?,?,?,?,?)",
              (pid,asset_id,str(data.get("kind") or "poi"),str(data.get("label") or "")[:160],dump(data.get("properties") or {}),now()))
    audit(c,"venue_poi_created",actor,{"asset_id":asset_id,"poi_id":pid})
    return pid

def get_asset(c,asset_id=None):
    if asset_id:
        row=c.execute("SELECT * FROM venue_assets WHERE id=?",(asset_id,)).fetchone()
    else:
        row=c.execute("SELECT * FROM venue_assets WHERE state='approved' ORDER BY version DESC LIMIT 1").fetchone()
    if not row:return None
    import json
    d=dict(row); d["geojson"]=json.loads(d.pop("geojson"))
    d["pois"]=[dict(r) for r in c.execute("SELECT * FROM venue_pois WHERE asset_id=? ORDER BY kind,label",(d["id"],))]
    d["live"]=[dict(r) for r in c.execute("SELECT venue,capacity,occupied,status,next_change,updated FROM venue_state ORDER BY venue")]
    d["incidents"]=[dict(r) for r in c.execute("SELECT id,venue,severity,title,status,recovery,ts,resolved FROM incidents WHERE status='open' ORDER BY severity,ts")]
    return d
