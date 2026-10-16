"""Browser proof for public-state-only guest surface."""
import os
import sys
import time
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
DB=os.environ.get("PROMOMED_BROWSER_QA_SQLITE_PATH","/tmp/promomed-browser-qa.db")
BASE=os.environ.get("PROMOMED_BASE_URL","http://127.0.0.1:10000").rstrip("/")
OUT=Path(os.environ.get("PROMOMED_SCREENSHOT_DIR","artifacts/browser-qa"))/"public-guest"

os.environ["SQLITE_PATH"]=DB
from app import db, public_state


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    c=db.connect()
    admitted=[]
    try:
        content=c.execute(
            "SELECT id,kind,theme,title,dek,duration,author,partner "
            "FROM content_catalog WHERE status='published' ORDER BY id LIMIT 1"
        ).fetchone()
        event=c.execute(
            'SELECT id,start,"end",venue,track,format,title,audience,capacity,stream,replay,partner '
            "FROM program_items ORDER BY id LIMIT 1"
        ).fetchone()
        assert content is not None
        assert event is not None
        now=int(time.time())
        for kind,row in (("content",content),("event",event)):
            digest=public_state.payload_sha256(kind,row)
            c.execute(
                "INSERT INTO public_artifact_admissions("
                "artifact_kind,artifact_ref,payload_sha256,status,reviewer_ref,source_ref,"
                "admitted_at,demo_only) VALUES(?,?,?,'admitted','browser:review','browser:source',?,1)",
                (kind,str(row["id"]),digest,now),
            )
            admitted.append((kind,str(row["id"]),digest))
        c.commit()

        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True)
            try:
                for name,width,height in (
                    ("phone",390,844),
                    ("tablet",820,1180),
                    ("desktop",1440,900),
                ):
                    page=browser.new_page(viewport={"width":width,"height":height},locale="ru-RU")
                    errors=[]
                    page.on("pageerror",lambda e: errors.append(str(e)))
                    page.goto(BASE+"/explore/",wait_until="networkidle")
                    expect(page.locator("#agenda")).to_contain_text(event["title"])
                    expect(page.locator("#content")).to_contain_text(content["title"])
                    expect(page.locator("#agenda-count")).to_have_text("1")
                    expect(page.locator("#content-count")).to_have_text("1")
                    expect(page.locator("body")).not_to_contain_text("participant@demo.ru")
                    assert page.evaluate("localStorage.length")==0
                    assert page.evaluate("sessionStorage.length")==0
                    overflow=page.evaluate(
                        "document.documentElement.scrollWidth-document.documentElement.clientWidth"
                    )
                    assert overflow<=1,(name,overflow)
                    assert not errors,errors
                    page.screenshot(path=str(OUT/(name+"-public.png")),full_page=True)
                    page.close()
            finally:
                browser.close()
    finally:
        for kind,ref,digest in admitted:
            c.execute(
                "DELETE FROM public_artifact_admissions "
                "WHERE artifact_kind=? AND artifact_ref=? AND payload_sha256=?",
                (kind,ref,digest),
            )
        c.commit()
        c.close()


if __name__=="__main__":
    main()
