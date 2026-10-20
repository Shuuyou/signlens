from __future__ import annotations

import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8010"
OUT = Path(__file__).resolve().parents[1] / ".shots"
OUT.mkdir(exist_ok=True)


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch(
            channel="msedge",
            headless=True,
            args=["--no-proxy-server", "--disable-gpu"],
        )
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        errors: list[str] = []
        page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
        page.on("pageerror", lambda exc: errors.append(str(exc)))

        page.goto(f"{BASE}/?ui=1", wait_until="networkidle")
        page.screenshot(path=str(OUT / "ui_home.png"), full_page=False)

        page.get_by_role("link", name="先看演示案例").click()
        page.get_by_role("button", name=re.compile("杭州云采供应链")).click()
        page.get_by_role("button", name=re.compile("开始体检")).click()
        page.locator(".whatif-panel").wait_for(state="visible", timeout=30000)
        page.wait_for_timeout(400)

        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(200)
        page.screenshot(path=str(OUT / "ui_report_top.png"), full_page=False)

        page.locator(".risk-card").first.scroll_into_view_if_needed()
        page.wait_for_timeout(200)
        page.screenshot(path=str(OUT / "ui_report_risks.png"), full_page=False)

        panel = page.locator(".whatif-panel")
        panel.scroll_into_view_if_needed()
        page.wait_for_timeout(200)
        panel.screenshot(path=str(OUT / "ui_whatif.png"))

        print("errors:", errors[:5])
        print("url:", page.url)
        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
