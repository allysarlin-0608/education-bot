"""Monkey test: random clicks, typing (odd text included), keys, scrolling,
Back/Forward, reloads and window sizes on every page, for a while each.
It fails on any server traceback, JavaScript error, alert() (an injected
script running), horizontal scroll, or a page that stops answering.

    python tests/e2e/monkey.py                    # 10 minutes per page
    python tests/e2e/monkey.py --minutes 1 --seed 7

Everything it does is logged with the seed, so a failure can be replayed.
Sign out, account deletion and links that leave the app are never pressed.
"""
import argparse
import json
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import conftest  # noqa: E402
import flows  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

PAGES = ["/", "/records", "/settings", "/reading", "/subject?subject=philosophy"]
AVOID = ("Sign out", "Delete", "Continue with Google", "Download")
TEXTS = ["hello", "", "   ", "a" * 3000, "<script>alert(1)</script>", "<img src=x onerror=alert(2)>",
         "Ünïcødé ✓ 漢字 🙂", "' OR 1=1 --", "12", "yes", "I've finished today's reading", "0", "-5", "9" * 40,
         "Chapter 1: One\nChapter 2: Two\nChapter 3: Three", "looks good", "‮ reversed", "DELETE"]


def pick_target(page, rng):
    return page.evaluate("""(avoid) => {
        const vis = e => { const r = e.getBoundingClientRect(); const s = getComputedStyle(e);
            return r.width > 2 && r.height > 2 && s.visibility !== 'hidden' && s.display !== 'none'; };
        const all = [...document.querySelectorAll('button:not(:disabled), a[href], [role=tab], [role=radio], summary, input, textarea, [role=switch]')]
            .filter(vis).filter(e => !avoid.some(a => (e.innerText || e.getAttribute('aria-label') || '').includes(a)))
            .filter(e => !(e.tagName === 'A' && e.href && !e.href.startsWith(location.origin)));
        all.forEach((e, i) => e.setAttribute('data-monkey', i));
        return all.length; }""", list(AVOID))


def step(p, app, rng, log):
    page = p.page
    n = pick_target(page, rng)
    roll = rng.random()
    if roll < 0.05:
        act = ("reload",)
        page.reload()
    elif roll < 0.08:
        act = ("back",)
        page.go_back()
    elif roll < 0.10:
        act = ("forward",)
        page.go_forward()
    elif roll < 0.13:
        w = rng.choice(list(conftest.WIDTHS))
        act = ("resize", w)
        page.set_viewport_size({"width": w, "height": conftest.WIDTHS[w]})
        p.width = w
    elif roll < 0.18:
        act = ("scroll",)
        page.mouse.wheel(0, rng.randint(-1500, 1500))
    elif roll < 0.24:
        key = rng.choice(["Enter", "Escape", "Tab", "Shift+Tab", "ArrowDown", "Space"])
        act = ("key", key)
        page.keyboard.press(key)
    elif n:
        k = rng.randrange(n)
        el = page.locator(f'[data-monkey="{k}"]').first
        tag = el.evaluate("e => e.tagName + (e.type ? ':' + e.type : '')")
        label = el.evaluate("e => (e.innerText || e.getAttribute('aria-label') || e.placeholder || '').slice(0, 40)")
        if tag.startswith(("INPUT:text", "INPUT:email", "INPUT:password", "INPUT:search", "TEXTAREA", "INPUT:number")):
            t = rng.choice(TEXTS)
            act = ("type", label, t[:30])
            el.fill(t, timeout=3000)
            if rng.random() < 0.5:
                page.keyboard.press("Enter")
        else:
            act = ("click", tag, label)
            el.click(timeout=3000)
    else:
        act = ("idle",)
    log.append(act)
    flows.idle(page, 20)
    if not page.url.startswith(app.url):
        log.append(("left the app, back", page.url[:80]))
        page.goto(app.url + "/")
        flows.idle(page, 30)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=float, default=10.0, help="per page")
    ap.add_argument("--seed", type=int, default=int(time.time()))
    a = ap.parse_args(argv)
    rng = random.Random(a.seed)
    app = conftest.App("public")
    report = {"seed": a.seed, "minutes_per_page": a.minutes, "pages": {}, "problems": []}
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=conftest.EXE)
            for path in PAGES:
                p = conftest.Page(browser, width=1440)
                email = f"monkey-{path.strip('/').split('?')[0] or 'today'}-{a.seed}@example.com"
                flows.sign_in(p, app, email=email)
                flows.onboard(p, reading=True)
                flows.open_app(p, app, path)
                app.set_llm(delay=0.2)
                log, steps, before = [], 0, len(app.log_text())
                end = time.time() + a.minutes * 60
                while time.time() < end:
                    try:
                        step(p, app, rng, log)
                    except Exception as e:           # a click on something that went away: note it, go on
                        log.append(("step failed", type(e).__name__, str(e)[:120]))
                        try:
                            flows.idle(p.page, 20)
                        except Exception:
                            p.page.goto(app.url + path)
                    steps += 1
                    if steps % 25 == 0 and not p.page.evaluate(
                            "document.documentElement.scrollWidth <= window.innerWidth + 1"):
                        report["problems"].append({"page": path, "what": "horizontal scroll", "after": log[-5:]})
                new = app.log_text()[before:]
                if "Traceback (most recent call last)" in new:
                    report["problems"].append({"page": path, "what": "server traceback", "log": new[-3000:],
                                               "after": log[-15:]})
                if p.errors:
                    report["problems"].append({"page": path, "what": "JavaScript errors", "errors": p.errors[:5]})
                if p.dialogs:
                    report["problems"].append({"page": path, "what": "alert() ran", "dialogs": p.dialogs[:5]})
                report["pages"][path] = {"steps": steps, "actions": log[-400:]}
                p.close()
            browser.close()
    finally:
        app.stop()
    out = conftest.RESULTS / "monkey.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1, ensure_ascii=False))
    print(f"seed {a.seed}: " + ", ".join(f"{k} {v['steps']} steps" for k, v in report["pages"].items()))
    print(f"{len(report['problems'])} problems" + (f": {json.dumps(report['problems'], ensure_ascii=False)[:3000]}"
                                                  if report["problems"] else ""))
    sys.exit(1 if report["problems"] else 0)


if __name__ == "__main__":
    main()
