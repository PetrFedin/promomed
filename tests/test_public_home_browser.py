"""Browser proof for the isolated non-demo public home.

Seeds one synthetic exact-admitted event/content version into a local SQLite
authority. This is publication plumbing evidence, not real Promomed content approval.
"""
import importlib
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from playwright.sync_api import expect,sync_playwright

ROOT=Path(__file__).resolve().parents[1]
OUT=Path(os.environ.get("PROMOMED_SCREENSHOT_DIR","artifacts/browser-qa"))/"public-home"


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory() as work:
        db_path=str(Path(work)/"public-home.db")
        port="10002"
        env=dict(os.environ)
        env.update({
            "SQLITE_PATH":db_path,
            "DATABASE_URL":"",
            "PROMOMED_SEED_DEMO":"false",
            "PROMOMED_REQUIRE_POSTGRES":"false",
            "PORT":port,
        })
        os.environ.update({
            "SQLITE_PATH":db_path,
            "DATABASE_URL":"",
            "PROMOMED_SEED_DEMO":"false",
            "PROMOMED_REQUIRE_POSTGRES":"false",
        })
        from app import db,public_state
        importlib.reload(db);importlib.reload(public_state)
        c=db.connect()
        try:
            db.migrate(c)
            now=int(time.time())
            c.execute(
                "INSERT INTO content_catalog"
                "(id,kind,theme,title,dek,duration,author,reviewer,partner,status) "
                "VALUES('HOME-C1','guide','science','Проверенный материал',"
                "'Синтетический контент browser QA','5 мин','QA Editorial','QA','',"
                "'published')"
            )
            c.execute(
                'INSERT INTO program_items(id,start,"end",venue,track,format,title,audience,'
                "capacity,stream,replay,partner) VALUES("
                "'HOME-E1','10:00','10:40','Главный зал','Science','talk',"
                "'Проверенная программа','all',100,1,1,'')"
            )
            content_row=c.execute(
                "SELECT id,kind,theme,title,dek,duration,author,partner "
                "FROM content_catalog WHERE id='HOME-C1'"
            ).fetchone()
            event_row=c.execute(
                'SELECT id,start,"end",venue,track,format,title,audience,capacity,stream,replay,partner '
                "FROM program_items WHERE id='HOME-E1'"
            ).fetchone()
            for kind,ref,row in (
                ("content","HOME-C1",content_row),("event","HOME-E1",event_row)
            ):
                c.execute(
                    "INSERT INTO public_artifact_admissions("
                    "artifact_kind,artifact_ref,payload_sha256,status,reviewer_ref,source_ref,"
                    "admitted_at,demo_only) VALUES(?,?,?,'admitted','review:browser',"
                    "'source:browser',?,0)",
                    (kind,ref,public_state.payload_sha256(kind,row),now),
                )
            c.commit()
        finally:
            c.close()

        proc=subprocess.Popen(
            [sys.executable,"server.py"],cwd=str(ROOT),env=env,
            stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,
        )
        try:
            import urllib.request
            for _ in range(40):
                try:
                    urllib.request.urlopen("http://127.0.0.1:"+port+"/health",timeout=1).read()
                    break
                except Exception:
                    time.sleep(.25)
            else:
                raise AssertionError("server_not_ready")

            with sync_playwright() as p:
                browser=p.chromium.launch(headless=True)
                try:
                    for name,width,height in (
                        ("phone",390,844),("tablet",820,1180),("desktop",1440,900)
                    ):
                        page=browser.new_page(
                            viewport={"width":width,"height":height},locale="ru-RU"
                        )
                        requested=[]
                        errors=[]
                        page.on("request",lambda req: requested.append(req.url))
                        page.on("pageerror",lambda err: errors.append(str(err)))
                        page.goto(
                            "http://127.0.0.1:"+port+"/",
                            wait_until="networkidle",
                        )
                        expect(page.locator("h1")).to_contain_text("Здоровье")
                        expect(page.locator("#agenda-list")).to_contain_text(
                            "Проверенная программа"
                        )
                        expect(page.locator("#content-list")).to_contain_text(
                            "Проверенный материал"
                        )
                        expect(page.locator("a.account")).to_have_attribute("href","/personal/")
                        assert not any("/api/state" in url for url in requested),requested
                        assert not any("/api/discovery" in url for url in requested),requested
                        assert any("/api/public-state/v1" in url for url in requested),requested
                        assert page.evaluate("localStorage.length")==0
                        assert page.evaluate("sessionStorage.length")==0
                        overflow=page.evaluate(
                            "document.documentElement.scrollWidth-"
                            "document.documentElement.clientWidth"
                        )
                        assert overflow<=1,(name,overflow)
                        assert not errors,errors
                        page.screenshot(
                            path=str(OUT/(name+"-public-home.png")),full_page=True
                        )
                        page.close()
                finally:
                    browser.close()
        finally:
            proc.terminate()
            try:proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill();proc.wait(timeout=5)


if __name__=="__main__":
    main()
