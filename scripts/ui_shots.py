from __future__ import annotations

import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8010"
OUT = Path(__file__).resolve().parents[1] / ".shots"
OUT.mkdir(exist_ok=True)


def open_report(page) -> None:
    page.goto(BASE, wait_until="domcontentloaded")
    page.get_by_role("link", name="先看演示案例").click()
    page.get_by_role("button", name=re.compile("杭州云采供应链")).click()
    page.wait_for_timeout(2500)
    page.get_by_role("button", name=re.compile("开始体检")).click()
    page.locator(".bf-headline").wait_for(state="visible", timeout=30000)
    page.wait_for_timeout(500)


def main() -> int:
    errors: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(
            channel="msedge",
            headless=True,
            args=["--no-proxy-server", "--disable-gpu"],
        )

        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(str(e)))
        open_report(page)

        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(200)
        page.screenshot(path=str(OUT / "brief_1_top.png"))
        before = page.locator(".bf-stamp").inner_text()
        headline_before = page.locator(".bf-headline").inner_text()

        page.locator("#actions").scroll_into_view_if_needed()
        page.wait_for_timeout(200)
        page.screenshot(path=str(OUT / "brief_2_actions.png"))

        page.locator(".bf-check").nth(0).click()
        page.locator(".bf-check").nth(1).click()
        page.locator(".bf-check").nth(2).click()
        page.wait_for_timeout(500)
        page.screenshot(path=str(OUT / "brief_3_checked.png"))
        after = page.locator(".bf-stamp").inner_text()
        headline_after = page.locator(".bf-headline").inner_text()
        print("stamp:", before, "->", after)
        print("headline before:", headline_before)
        print("headline after :", headline_after)
        print("delta:", page.locator(".bf-delta").inner_text() if page.locator(".bf-delta").count() else "-")

        page.locator("#risks").scroll_into_view_if_needed()
        page.wait_for_timeout(200)
        page.screenshot(path=str(OUT / "brief_4_risks.png"))

        page.get_by_role("button", name=re.compile("还有 \\d+ 条风险")).click()
        page.wait_for_timeout(300)
        print("risk rows:", page.locator(".bf-risk").count())

        page.get_by_role("button", name="打开合同原文").click()
        page.locator(".bf-drawer").wait_for(state="visible")
        page.wait_for_timeout(600)
        page.screenshot(path=str(OUT / "brief_5_drawer.png"))
        page.locator(".bf-mark").first.click()
        page.wait_for_timeout(900)
        print("drawer closed after mark click:", page.locator(".bf-drawer").count() == 0)
        page.screenshot(path=str(OUT / "brief_6_focus.png"))

        page.locator("#company").scroll_into_view_if_needed()
        page.wait_for_timeout(200)
        page.screenshot(path=str(OUT / "brief_7_company.png"))
        page.close()

        mobile = browser.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=2)
        mobile.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        mobile.on("pageerror", lambda e: errors.append(str(e)))
        open_report(mobile)
        mobile.evaluate("window.scrollTo(0, 0)")
        mobile.wait_for_timeout(200)
        mobile.screenshot(path=str(OUT / "brief_m1_top.png"))
        mobile.locator("#risks").scroll_into_view_if_needed()
        mobile.wait_for_timeout(200)
        mobile.screenshot(path=str(OUT / "brief_m2_risks.png"))
        overflow = mobile.evaluate(
            "document.documentElement.scrollWidth - document.documentElement.clientWidth"
        )
        print("mobile horizontal overflow px:", overflow)
        mobile.close()

        browser.close()

    print("console errors:", errors[:5])
    return 0


if __name__ == "__main__":
    sys.exit(main())
