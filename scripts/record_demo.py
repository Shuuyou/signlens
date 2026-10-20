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
    "首页准备了三个已脱敏的真实场景，我们选择 1688 供应商预付款这一单。",
    "合同全文、对方公司名和聊天记录已经自动载入，合同共 651 字。",
    "SignLens 会切分每一条条款，并标出付款、交付、免责和争议解决的关键位置。",
    "聊天记录不是装饰，它用来识别口头承诺和合同文本之间的落差。",
    "现在我们点击开始体检，真实流水线只需要大约一秒钟。",
    "服务端依次完成条款解析、主体核查、法条匹配和报告生成。",
    "报告结论是建议不签，置信度百分之九十。",
    "九条高风险集中在预付款、交付、免责和违约责任上。",
    "每一条风险都写清了为什么、对应条款原文和可以直接使用的改法。",
    "你点开法条依据，就可以查看民法典原文和官方来源。",
    "主体核查显示对方有两条未履行的被执行记录，实缴资本为零。",
    "接下来我们演示如果对方让步，结论会怎样变化。",
    "对方书面补充交货日期与验收标准后，风险敞口从百分之百降到百分之七十一。",
    "预付款降到百分之十并把尾款放到验收之后，敞口继续降到百分之四十七。",
    "争议解决改到公司所在地法院后，风险敞口降到百分之二十七。",
    "我们点击模拟全部让步，五项让步把风险敞口降到零，结论从建议不签变为可以谈。",
    "风险卡片同步标记推演中已缓释，说明结论会随着证据改变。",
    "谈判清单按 P0 和 P1 分级，一共八条，可以直接拿去谈。",
    "报告可以打印成一页纸谈判单，也可以导出完整 PDF。",
    "每一条结论都能回到 gsxt、zxgk 和裁判文书网等公开来源。",
    "企查查回答这家公司是什么，SignLens 回答这单该不该做、什么会改变结论。",
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


class Timeline:
    """Collects scene boundaries, so subtitles follow what is actually on screen."""

    def __init__(self, epoch: float) -> None:
        self.epoch = epoch
        self.scenes: list[tuple[float, float, str]] = []
        self._current: tuple[float, str] | None = None

    def start(self, text: str) -> None:
        now = time.monotonic() - self.epoch
        if self._current is not None:
            start, previous = self._current
            self.scenes.append((start, max(start + 0.6, now - 0.12), previous))
        self._current = (now, text)

    def finish(self) -> None:
        if self._current is None:
            return
        now = time.monotonic() - self.epoch
        start, text = self._current
        self.scenes.append((start, max(start + 0.6, now), text))
        self._current = None

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
        await page.locator(".verdict-banner").wait_for(state="visible", timeout=30000)
        await page.wait_for_timeout(400)

        # 报告结论
        await smooth_scroll(page, y=0, duration=700)
        await page.wait_for_timeout(500)
        timeline.start(SUBTITLES[7])
        await page.wait_for_timeout(7000)

        # 风险清单
        await smooth_scroll(page, selector="#risks", offset=70, duration=1000)
        timeline.start(SUBTITLES[8])
        await page.wait_for_timeout(7500)

        # 展开第一条风险与法条
        await smooth_scroll(page, selector=".risk-card", offset=80, duration=700)
        first_risk = page.locator(".risk-card").first
        await first_risk.locator(".law-fold summary").click()
        await smooth_scroll(page, selector=".risk-card .law-fold", offset=260, duration=700)
        timeline.start(SUBTITLES[9])
        await page.wait_for_timeout(4000)
        timeline.start(SUBTITLES[10])
        await page.wait_for_timeout(4000)

        # 主体核查
        await smooth_scroll(page, selector=".company-panel", offset=110, duration=1000)
        timeline.start(SUBTITLES[11])
        await page.wait_for_timeout(7500)

        # 如果…会怎样
        await smooth_scroll(page, selector=".whatif-panel", offset=70, duration=1200)
        timeline.start(SUBTITLES[12])
        await page.wait_for_timeout(5200)

        scenarios = page.locator(".scenario")
        for index, subtitle in enumerate(SUBTITLES[13:16]):
            await scenarios.nth(index).click()
            timeline.start(subtitle)
            await page.wait_for_timeout(5200)

        await smooth_scroll(page, selector=".whatif-actions", offset=150, duration=700)
        timeline.start(SUBTITLES[16])
        await page.wait_for_timeout(700)
        await page.get_by_role("button", name="模拟全部让步").click()
        await page.wait_for_timeout(6200)

        # 风险卡片缓释标记
        await smooth_scroll(page, selector="#risks", offset=60, duration=1400)
        timeline.start(SUBTITLES[17])
        await page.wait_for_timeout(7500)

        # 谈判清单
        await smooth_scroll(page, selector="#negotiation", offset=70, duration=1300)
        timeline.start(SUBTITLES[18])
        await page.wait_for_timeout(8500)

        # 打印入口
        await smooth_scroll(page, selector=".aside-actions", offset=320, duration=1200)
        timeline.start(SUBTITLES[19])
        await page.wait_for_timeout(6500)

        # 来源列表
        await smooth_scroll(page, selector=".source-panel", offset=140, duration=900)
        timeline.start(SUBTITLES[20])
        await page.wait_for_timeout(5500)

        # 收尾回到谈判清单
        await smooth_scroll(page, selector="#negotiation", offset=70, duration=1400)
        timeline.start(SUBTITLES[21])
        await page.wait_for_timeout(8500)

        timeline.finish()
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
    output = OUT / "demo_3min.mp4"
    style = (
        "FontName=Microsoft YaHei,FontSize=10,PrimaryColour=&H00FFFFFF,"
        "SecondaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
        "BackColour=&H00000000,BorderStyle=3,Outline=1,Shadow=0,"
        "Alignment=2,MarginV=10"
    )
    video_filter = f"subtitles={srt.name}:force_style='{style}'"
    command = [
        ffmpeg,
        "-y",
        "-hide_banner",
        "-loglevel",
        "warning",
        "-i",
        raw.name,
        "-vf",
        video_filter,
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
        "-r",
        "30",
        "-movflags",
        "+faststart",
        "-an",
        output.name,
    ]
    result = subprocess.run(
        command,
        cwd=OUT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        print("ffmpeg failed:\n", result.stderr[-3000:])
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
