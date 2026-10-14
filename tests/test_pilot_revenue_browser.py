"""Read-only browser proof for the institutional commercial evidence ladder.

CI uses local SQLite demo only. A login rejection must never reveal organization
metadata or accidentally claim payments or contract acceptance.
"""
import os
import json
import re
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

BASE = os.environ.get("PROMOMED_BASE_URL", "http://127.0.0.1:10000")
OUT = Path(os.environ.get("PROMOMED_SCREENSHOT_DIR", "artifacts/browser-qa"))
OUT.mkdir(parents=True, exist_ok=True)

DEVICES = [("phone",375,812), ("tablet",820,1180), ("desktop",1440,900)]

def main():
    with sync_playwright() as playwright:
        browser=playwright.chromium.launch()
        try:
            for device,width,height in DEVICES:
                page=browser.new_page(viewport={"width":width,"height":height})
                errors=[]
                page.on("pageerror", lambda exc: errors.append(str(exc)))
                response=page.goto(BASE+"/pilot-revenue-ladder.html",wait_until="domcontentloaded")
                assert response and response.status == 200
                expect(page.get_by_role("heading",name="Семь этапов доказательства")).to_be_visible()
                expect(page.get_by_role("button",name=re.compile("06.*Finance"))).to_be_visible()
                expect(page.locator("#scopedProof")).to_be_hidden()
                assert page.locator(".stage-control").count()==7
                assert page.locator(".stage-control[aria-pressed=true]").count()==1

                page.locator('[data-step="finance"]').click()
                expect(page.locator("#stageTitle")).to_contain_text("Finance acceptance")
                expect(page.locator("#stageBadge")).to_have_text("GATED")
                expect(page.locator("#requiredList li")).to_have_count(4)
                page.locator('[data-step="renewal"]').click()
                expect(page.locator("#stageTitle")).to_contain_text("Repeatable contract")
                expect(page.locator("#stageBadge")).to_have_text("GATED")
                expect(page.locator("#metricRevenue")).to_have_text("—")
                page.locator("#loginEmail").fill("unverified@example.test")
                page.locator("#loginPassword").fill("invalid-only")
                page.locator("#organizationId").fill("UNKNOWN-TENANT")
                page.locator('#proofForm button[type="submit"]').click()
                expect(page.locator("#proofStatus")).to_contain_text(
                    "Не удалось подтвердить доступ"
                )
                expect(page.locator("#scopedProof")).to_be_hidden()
                expect(page.locator("#loginPassword")).to_have_value("")
                page.locator("#logoutButton").click()
                expect(page.locator("#loginEmail")).to_have_value("")
                assert page.locator("#scopedProof").is_hidden()
                # Deliberately synthetic, strictly in-memory mocked authority.
                # This tests UI truth boundaries without a real financial login.
                stage_ids=["pilot_acceptance","contract","delivery","invoice",
                           "cash","finance","renewal"]
                mock={
                    "version":"promomed-pilot-to-revenue-evidence-ladder-v1",
                    "organization":{"id":"MOCK-ORG-DEMO","name":"Synthetic diligence fixture",
                                    "demoOnly":True},
                    "sourceSignals":{
                        "nonDemoIdentityMetadata":False,
                        "technicalEvidenceAcknowledgements":0,
                        "candidateContractVersions":1,
                        "candidateDocumentVersions":1,
                        "candidateAuditRecords":2
                    },
                    "stages":[{"id":stage,"state":"GATED",
                               "whyBlocked":"Synthetic fixture — external acceptance unavailable.",
                               "requiredEvidence":["Signed external acceptance is required"]}
                              for stage in stage_ids],
                    "acceptanceSummary":{
                        "capitalReleaseAuthorized":False,"financeAccepted":False,
                        "acceptedStages":0,"totalStages":7
                    },
                    "truthBoundary":{"readOnly":True},
                    "candidatePortfolio":{
                        "version":"candidate-custody-summary-v1",
                        "scope":"EXACT_ORGANIZATION",
                        "sourceState":"CANDIDATE_ONLY",
                        "financialAuthority":"NONE",
                        "approvalAuthority":"NONE",
                        "eventCountsAreVersions":True,
                        "displayed":1,"truncated":False,
                        "items":[{
                            "contractDocumentId":"cc:"+("a"*26),
                            "version":1,"demoOnly":True,
                            "sourceState":"CANDIDATE_ONLY",
                            "externalCommercialAcceptance":False,
                            "signedContractVerified":False,
                            "financialActuals":None,
                            "eventVersions":{
                                "obligation":1,"delivery":0,"invoice":0,
                                "credit_note":0,"settlement":0,
                                "allocation":0,"refund":0,
                                "direct_cost":0,"recognition":0,
                                "finance_review":0,"renewal":0
                            }
                        }]
                    },
                    "evidenceRequestPack":{
                        "sha256":"f"*64,"document":{"source":"synthetic-browser-only"}
                    }
                }
                page.route("**/api/login",lambda route: route.fulfill(
                    status=200,content_type="application/json",
                    body=json.dumps({"role":"organizer","token":"synthetic-browser-test-token-not-real"})))
                page.route("**/api/pilot-revenue-ladder/MOCK-ORG-DEMO",
                    lambda route: route.fulfill(
                        status=200,content_type="application/json",
                        body=json.dumps(mock)))
                page.locator("#loginEmail").fill("synthetic-browser@example.test")
                page.locator("#loginPassword").fill("synthetic-pass-no-access")
                page.locator("#organizationId").fill("MOCK-ORG-DEMO")
                page.locator('#proofForm button[type="submit"]').click()
                expect(page.locator("#scopedProof")).to_be_visible()
                expect(page.locator("#candidateCards .candidate-card")).to_have_count(1)
                expect(page.locator("#candidateStatus")).to_contain_text("1 версий договоров-кандидатов")
                expect(page.locator("#orgMode")).to_have_text("DEMO ORGANIZATION")
                expect(page.locator("#metricRevenue")).to_have_text("—")
                expect(page.locator("#acceptanceStatus")).to_contain_text("CAPITAL: HOLD")
                expect(page.locator("#candidateCards")).to_contain_text("Коммерческая приёмка: НЕ ПОДТВЕРЖДЕНА")
                page.screenshot(
                    path=str(OUT/f"commercial-candidate-coverage-{device}.png"),
                    full_page=True)
                page.locator("#logoutButton").click()
                expect(page.locator("#scopedProof")).to_be_hidden()
                expect(page.locator("#candidateCards .candidate-card")).to_have_count(0)
                dims=page.evaluate("() => ({scroll:document.documentElement.scrollWidth,body:document.body.scrollWidth,window:innerWidth})")
                assert dims["scroll"] <= width+1 and dims["body"] <= width+1, (device,dims)
                page.screenshot(path=str(OUT/f"investor-revenue-ladder-{device}.png"),full_page=True)
                assert not errors, (device,errors)
                page.close()
        finally:
            browser.close()


if __name__=="__main__":
    main()
