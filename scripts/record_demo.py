"""Record the 3-minute SignLens demo with Playwright and burn in Chinese subtitles.

The pipeline itself finishes in about one second, so the recording delays the
analysis response to give each scene room to breathe. Everything shown in the
report comes from the real backend; no business code is touched.

Usage (backend already running on 127.0.0.1:8010):

    .venv/Scripts/python.exe scripts/record_demo.py

If ffmpeg is not on PATH, set FFMPEG_BIN to a binary. Without ffmpeg the script
still leaves a .webm recording and the UTF-8 SRT next to it.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

from playwright.async_api import Page, async_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:8010"
OUT = ROOT / ".shots" / "video"
VIEWPORT = {"width": 1440, "height": 900}
ANALYZE_DELAY = 12.0

SUBTITLES = [
    "一个学生创业者明天要给供应商打 20400 元预付款，他只看懂了合同总价。",
    "首页准备了三个脱敏的典型场景，我们选择 1688 供应商预付款这一单。",
    "合同全文、对方公司名和聊天记录已经自动载入，合同共 651 字。",
    "SignLens 会切分每一条条款，并标出付款、交付、免责和争议解决的关键位置。",
    "聊天记录不是装饰，它用来识别口头承诺和合同文本之间的落差。",
    "现在我们点击开始体检，真实流水线只需要大约一秒钟。",
    "服务端依次完成条款解析、主体核查、法条匹配和报告生成。",
    "报告第一句就是结论：先别签。它直接点出最要紧的两处，以及对方的被执行记录。",
    "下面不是一长串风险，而是几件需要对方答应的事。勾上一项，结论和风险一起变。",
    "对方书面补充交货日期和验收标准，九条高风险降到六条，结论里的原因也跟着换了。",
    "再加上预付款降到百分之十、争议改到公司所在地法院，高风险只剩两条。",
    "五项全部谈妥后，结论从建议不签变成先谈再签；但对方的执行记录还在，报告仍提醒你要担保。",
    "风险明细默认只展开最要紧的一条，其余收在后面，不用一次读完十二条。",
    "点开一条：为什么有风险、合同里的原话、建议改成什么、民法典原文，都在同一处。",
    "要看上下文，就打开合同全文，命中风险的条款已经按等级标色。",
    "点一下标色的句子，就回到对应的风险，不用来回翻找。",
    "对方是谁：两条未履行的被执行记录、一条虚假宣传的行政处罚，排在最前面。",
    "页脚只写一句：规则引擎生成，不构成法律意见；主体数据是脱敏的演示数据。",
    "谈到哪一步才能签，可以复制成谈判清单带去见对方，也可以导出 PDF。",
    "企查查回答这家公司是什么，SignLens 回答这单该不该签、谈到什么程度能签。",
]

SMOOTH_SCROLL_JS = """
({ selector, y, duration, offset }) => new Promise((resolve) => {
  const targetEl = selector ? document.querySelector(selector) : null;
  const targetY = targetEl
    ? targetEl.getBoundingClientRect().top + window.scrollY - offset
    : (y || 0);
  const startY = window.scrollY;
  const distance = targetY - startY;
  if (Math.abs(distance) < 2) { resolve(); return; }
  const started = performance.now();
  const easing = (p) => (p < 0.5 ? 2 * p * p : 1 - Math.pow(-2 * p + 2, 2) / 2);
  const step = (now) => {
    const p = Math.min(1, (now - started) / duration);
    window.scrollTo(0, startY + distance * easing(p));
    if (p < 1) requestAnimationFrame(step);
    else resolve();
  };
  requestAnimationFrame(step);
})
"""


SUBTITLE_JS = """
(text) => {
  let el = document.getElementById('__demo_sub');
  if (!el) {
    el = document.createElement('div');
    el.id = '__demo_sub';
    el.style.cssText = 'position:fixed;left:50%;bottom:20px;transform:translateX(-50%);'
      + 'max-width:1180px;padding:9px 22px;background:rgba(20,22,18,.84);color:#fff;'
      + 'font:500 23px/1.55 "Microsoft YaHei","PingFang SC",sans-serif;letter-spacing:.02em;'
      + 'text-align:center;border-radius:10px;z-index:2147483647;pointer-events:none';
    document.body.appendChild(el);
  }
  el.textContent = text || '';
  el.style.display = text ? 'block' : 'none';
}
"""


class Timeline:
    """Collects scene boundaries, so subtitles follow what is actually on screen."""

    def __init__(self, epoch: float) -> None:
        self.epoch = epoch
        self.scenes: list[tuple[float, float, str]] = []
        self._current: tuple[float, str] | None = None
        self.page: Page | None = None
        self._tasks: list[asyncio.Task] = []

    def _show(self, text: str) -> None:
        if self.page is None:
            return
        self._tasks.append(asyncio.get_running_loop().create_task(self.page.evaluate(SUBTITLE_JS, text)))

    def start(self, text: str) -> None:
        now = time.monotonic() - self.epoch
        if self._current is not None:
            start, previous = self._current
            self.scenes.append((start, max(start + 0.6, now - 0.12), previous))
        self._current = (now, text)
        self._show(text)

    def finish(self) -> None:
        if self._current is None:
            return
        now = time.monotonic() - self.epoch
        start, text = self._current
        self.scenes.append((start, max(start + 0.6, now), text))
        self._current = None
        self._show("")

    def srt(self, duration: float) -> str:
        blocks: list[str] = []
        for start, end, text in self.scenes:
            begin = max(0.0, start)
            stop = min(duration - 0.15, end)
            if stop <= begin + 0.2:
                continue
            blocks.append(
                f"{len(blocks) + 1}\n{_timestamp(begin)} --> {_timestamp(stop)}\n{text}\n"
            )
        return "\n".join(blocks)


def _timestamp(seconds: float) -> str:
    total = max(0, int(round(seconds * 1000)))
    hours, rest = divmod(total, 3_600_000)
    minutes, rest = divmod(rest, 60_000)
    secs, millis = divmod(rest, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


async def smooth_scroll(
    page: Page,
    selector: str | None = None,
    y: int | None = None,
    duration: int = 900,
    offset: int = 80,
) -> None:
    await page.evaluate(
        SMOOTH_SCROLL_JS,
        {"selector": selector, "y": y, "duration": duration, "offset": offset},
    )
    await page.wait_for_timeout(duration + 120)


async def record(timeline: Timeline) -> tuple[Path, float]:
    OUT.mkdir(parents=True, exist_ok=True)
    for stale in OUT.glob("*.webm"):
        stale.unlink(missing_ok=True)

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            channel="msedge",
            headless=True,
            args=[
                "--no-proxy-server",
                "--disable-gpu",
                "--hide-scrollbars",
                "--force-device-scale-factor=1",
            ],
        )
        context = await browser.new_context(
            viewport=VIEWPORT,
            record_video_dir=str(OUT),
            record_video_size=VIEWPORT,
            device_scale_factor=1,
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
        )
        timeline.epoch = time.monotonic()
        page = await context.new_page()
        timeline.page = page
        errors: list[str] = []
        page.on(
            "console",
            lambda msg: errors.append(msg.text) if msg.type == "error" else None,
        )
        page.on("pageerror", lambda exc: errors.append(str(exc)))

        async def slow_analyze(route):  # type: ignore[no-untyped-def]
            response = await route.fetch()
            await asyncio.sleep(ANALYZE_DELAY)
            await route.fulfill(response=response)

        await page.route("**/api/analyze", slow_analyze)

        await page.goto(f"{BASE}/", wait_until="networkidle")
        await page.wait_for_timeout(700)
        timeline.start(SUBTITLES[0])
        await page.wait_for_timeout(5200)

        # 首页 -> 演示案例
        await smooth_scroll(page, selector="#demo-cases", duration=1000)
        timeline.start(SUBTITLES[1])
        first_card = page.locator(".case-card").first
        await first_card.hover()
        await page.wait_for_timeout(2600)
        supplier = page.locator(".case-card").filter(has_text="1688 供应商")
        await supplier.hover()
        await page.wait_for_timeout(2400)

        # 演示案例 -> 输入
        await supplier.click()
        await page.locator(".intake-page").wait_for(state="visible", timeout=15000)
        await page.wait_for_timeout(900)
        timeline.start(SUBTITLES[2])
        await page.wait_for_timeout(5000)

        await smooth_scroll(page, selector="#contract-text", offset=280, duration=1000)
        timeline.start(SUBTITLES[3])
        await page.wait_for_timeout(6500)

        await smooth_scroll(page, selector="#chat-text", offset=280, duration=900)
        timeline.start(SUBTITLES[4])
        await page.wait_for_timeout(5500)

        await smooth_scroll(page, selector=".submit-block", offset=280, duration=900)
        timeline.start(SUBTITLES[5])
        await page.wait_for_timeout(1200)

        # 开始体检（放慢接口响应，让提交状态可读）
        await page.locator('button[type="submit"]').click()
        await page.wait_for_timeout(3000)
        timeline.start(SUBTITLES[6])
        await page.wait_for_timeout(8500)
        await page.locator(".bf-headline").wait_for(state="visible", timeout=30000)
        await page.wait_for_timeout(400)

        async def delta_then_top(hold_delta: int = 3200, hold_top: int = 3600) -> None:
            await smooth_scroll(page, selector=".bf-delta", offset=520, duration=800)
            await page.wait_for_timeout(hold_delta)
            await smooth_scroll(page, y=0, duration=800)
            await page.wait_for_timeout(hold_top)

        # 一句话结论
        await smooth_scroll(page, y=0, duration=700)
        await page.wait_for_timeout(500)
        timeline.start(SUBTITLES[7])
        await page.wait_for_timeout(7500)

        # 清单：勾选后结论实时变化
        await smooth_scroll(page, selector="#actions", offset=90, duration=1000)
        timeline.start(SUBTITLES[8])
        await page.wait_for_timeout(6000)

        checks = page.locator(".bf-check")
        await checks.nth(0).click()
        timeline.start(SUBTITLES[9])
        await page.wait_for_timeout(1500)
        await delta_then_top()

        await smooth_scroll(page, selector="#actions", offset=90, duration=900)
        await checks.nth(1).click()
        await page.wait_for_timeout(900)
        await checks.nth(2).click()
        timeline.start(SUBTITLES[10])
        await page.wait_for_timeout(1200)
        await delta_then_top()

        await smooth_scroll(page, selector="#actions", offset=90, duration=900)
        await page.get_by_role("button", name="全选").click()
        timeline.start(SUBTITLES[11])
        await page.wait_for_timeout(1200)
        await delta_then_top(hold_delta=3400, hold_top=5200)

        await smooth_scroll(page, selector="#actions", offset=90, duration=900)
        await page.get_by_role("button", name="清空").click()
        await page.wait_for_timeout(600)

        # 风险明细
        await smooth_scroll(page, selector="#risks", offset=70, duration=1100)
        timeline.start(SUBTITLES[12])
        await page.wait_for_timeout(7000)

        await smooth_scroll(page, selector=".bf-risk .bf-clause", offset=150, duration=900)
        timeline.start(SUBTITLES[13])
        await page.wait_for_timeout(8500)

        # 合同全文与风险联动
        await page.locator(".bf-clause .bf-link").first.click()
        await page.locator(".bf-drawer").wait_for(state="visible", timeout=10000)
        timeline.start(SUBTITLES[14])
        await page.wait_for_timeout(6500)
        await page.locator(".bf-mark").nth(3).click()
        timeline.start(SUBTITLES[15])
        await page.wait_for_timeout(6500)

        # 主体核查
        await smooth_scroll(page, selector="#company", offset=80, duration=1000)
        timeline.start(SUBTITLES[16])
        await page.wait_for_timeout(7500)

        # 页脚
        await smooth_scroll(page, selector=".bf-foot", offset=420, duration=1000)
        timeline.start(SUBTITLES[17])
        await page.wait_for_timeout(6500)

        # 带走
        await smooth_scroll(page, selector="#actions", offset=90, duration=1300)
        timeline.start(SUBTITLES[18])
        await page.wait_for_timeout(7000)

        await smooth_scroll(page, y=0, duration=1300)
        timeline.start(SUBTITLES[19])
        await page.wait_for_timeout(8500)

        timeline.finish()
        await asyncio.gather(*timeline._tasks, return_exceptions=True)
        await context.close()
        close_epoch = time.monotonic()
        record_path = await page.video.path()  # type: ignore[union-attr]
        raw = OUT / "demo_raw.webm"
        shutil.copyfile(record_path, raw)
        Path(record_path).unlink(missing_ok=True)
        await browser.close()

        if errors:
            print("console errors:", errors[:5])
        print(f"recorded {close_epoch - timeline.epoch:.1f}s of wall time")
        return raw, close_epoch


def find_ffmpeg() -> str | None:
    override = os.environ.get("FFMPEG_BIN")
    if override and Path(override).is_file():
        return override
    found = shutil.which("ffmpeg")
    if found:
        return found
    candidates = [
        Path("C:/ffmpeg/bin/ffmpeg.exe"),
        Path("C:/ProgramData/chocolatey/bin/ffmpeg.exe"),
        Path.home() / "scoop" / "shims" / "ffmpeg.exe",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    try:
        import imageio_ffmpeg  # type: ignore[import-not-found]

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def probe_duration(ffmpeg: str, path: Path) -> float:
    result = subprocess.run(
        [ffmpeg, "-hide_banner", "-i", str(path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    match = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", result.stderr)
    if not match:
        return 0.0
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def burn_subtitles(raw: Path, srt: Path, ffmpeg: str) -> Path | None:
    """Subtitles are already rendered into the page while recording; just transcode."""
    output = OUT / "demo_3min.mp4"
    command = [
        ffmpeg, "-y", "-hide_banner", "-loglevel", "warning",
        "-i", raw.name,
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-pix_fmt", "yuv420p", "-r", "30", "-movflags", "+faststart", "-an",
        output.name,
    ]
    result = subprocess.run(
        command, cwd=OUT, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    if result.returncode != 0:
        print("ffmpeg failed:", result.stderr[-3000:])
        return None
    print(f"wrote {output} ({probe_duration(ffmpeg, output):.1f}s)")
    return output


async def main() -> int:
    global BASE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default=BASE, help="SignLens base URL")
    args = parser.parse_args()
    BASE = args.base

    OUT.mkdir(parents=True, exist_ok=True)
    timeline = Timeline(time.monotonic())
    raw, close_epoch = await record(timeline)
    wall_duration = close_epoch - timeline.epoch
    binary = find_ffmpeg()

    if binary is None:
        shutil.copyfile(raw, OUT / "demo_3min.webm")
        srt_path = OUT / "demo_3min.srt"
        srt_path.write_text(timeline.srt(wall_duration), encoding="utf-8")
        print("ffmpeg not found: kept demo_3min.webm and demo_3min.srt")
        return 0

    # Scene marks are wall-clock times; Playwright's container clock drifts a
    # little and the tail padding is not a constant shift, so do not re-align.
    duration = probe_duration(binary, raw) or wall_duration

    srt_path = OUT / "demo_3min.srt"
    srt_path.write_text(timeline.srt(duration), encoding="utf-8")

    output = burn_subtitles(raw, srt_path, binary)
    if output is None:
        shutil.copyfile(raw, OUT / "demo_3min.webm")
        print("subtitle burn failed: kept demo_3min.webm and demo_3min.srt")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
