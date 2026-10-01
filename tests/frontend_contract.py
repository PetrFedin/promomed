import re
from pathlib import Path

html=Path("public/index.html").read_text(encoding="utf-8")

required=[
    'name="viewport"',
    'viewport-fit=cover',
    'vjs.zencdn.net/8.24.0',
    'maplibre-gl@6.11.2',
    'id="continueJourney"',
    'id="venueMapCanvas"',
    'id="expertRooms"',
    'id="integrationProof"',
    'id="publicationAuthority"',
    'id="programmeProductionDesk"',
    'id="expertAuthority"',
    'id="partnerWorkspaceAuthority"',
    "/api/recommendations",
    "/api/search",
    "/api/virtual-rooms",
    "/api/venue-map",
    "/api/integration-proof",
    "source_hash",
    "human review",
    "Не официальный продукт компании",
]
missing=[x for x in required if x not in html]
assert not missing, f"frontend contract missing: {missing}"

scripts=re.findall(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>",html,re.S|re.I)
assert scripts, "inline application script missing"
Path("/tmp/promomed-inline.js").write_text("\n".join(scripts),encoding="utf-8")
print("PROMOMED frontend static contract PASS")
