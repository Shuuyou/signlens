from __future__ import annotations

import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "https://www.modelscope.cn/studios/Shuuyou/signlens"
OUT = Path(__file__).resolve().parents[1] / ".shots"
OUT.mkdir(exist_ok=True)


def find_app_frame(page, seconds: int = 60):
    for _ in range(seconds):
        for frame in page.frames:
            if frame == page.main_frame:
                continue
            try:
                if frame.get_by_text("先看演示案例").count() > 0:
                    return frame
            except Exception:
                continue
        time.sleep(1)
    return None


def main() -> int:
    errors: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(
            channel="msedge", headless=True, args=["--no-proxy-server", "--disable-gpu"]
        )
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        frame = find_app_frame(page)
        print("app frame found:", frame is not None)
        if frame is None:
            page.screenshot(path=str(OUT / "ms_fail.png"))
            browser.close()
            return 1

        frame.get_by_role("link", name="先看演示案例").click(timeout=45000)
        frame.get_by_role("button", name=re.compile("杭州云采供应链")).click(timeout=30000)
        time.sleep(2.5)
        frame.get_by_role("button", name=re.compile("开始体检")).click(timeout=30000)
        frame.locator(".bf-headline").wait_for(state="visible", timeout=45000)
        print("stamp   :", frame.locator(".bf-stamp").inner_text())
        print("headline:", frame.locator(".bf-headline").inner_text())
        frame.locator(".bf-check").nth(0).click()
        time.sleep(0.4)
        print("delta   :", frame.locator(".bf-delta").inner_text())
        page.screenshot(path=str(OUT / "ms_brief.png"))
        print("page errors:", errors[:3])
        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
