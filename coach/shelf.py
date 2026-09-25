"""The Reading page's own pieces: the 14-day line for the book she is
reading, and the bookshelf of the books she finished or stopped. Pure
HTML builders over the book records (nothing here changes a book), so
they can be tested."""
import html
import re
from datetime import date

from coach import books


def _e(text) -> str:
    return html.escape(str(text or ""), quote=True)


def _day(iso: str) -> str:
    """"Sep 30" (no year: the shelf is recent books)."""
    d = date.fromisoformat(iso)
    return f"{d:%b} {d.day}"


# ------------------------------------------------------------
# The book being read: the same thin liquid line as Today's lessons
# ------------------------------------------------------------

def day_states(book: dict) -> list:
    """For each of the 14 days: done (passed, or a rest day already behind
    her), current (the next day to read) or ahead."""
    current = books.next_day(book)
    out = []
    for d in range(1, books.DAYS + 1):
        passed = str(d) in book["checks"]
        rest_behind = not book["plan"][d - 1] and current is not None and d < current
        out.append("done" if passed or rest_behind else "current" if d == current else "ahead")
    return out


def line_label(book: dict) -> str:
    reading_days = [d for d in range(1, books.DAYS + 1) if book["plan"][d - 1]]
    done = sum(1 for d in reading_days if str(d) in book["checks"])
    current = books.next_day(book)
    head = f"Day {current} of {books.DAYS}" if current else f"All {books.DAYS} days"
    return f"{head} · {done} of {len(reading_days)} reading days done"


def line_html(book: dict, flowing: bool = False) -> str:
    """Fourteen stretches of one glass tube: the liquid fills the days done
    (one after another when arriving), the next day's number is bold, the
    days ahead are faded."""
    states = day_states(book)
    segs = []
    for i, s in enumerate(states):
        end = s == "done" and (i + 1 == len(states) or states[i + 1] != "done")
        rest = " rest" if not book["plan"][i] else ""      # no chapters that day: no tick
        segs.append(f'<span class="bk-seg {s}{rest}{" end" if end else ""}" style="--i:{i}"><i>{i + 1}</i></span>')
    return (f'<div class="bk-line{" flowing" if flowing else ""}" role="img" aria-label="{_e(line_label(book))}">'
            + "".join(segs) + "</div>"
            + f'<div class="lq-meta"><span>{_e(line_label(book))}</span></div>')


def today_html(book: dict, today: date) -> str:
    """Today's reading: the next day's chapters, or when it opens."""
    day = books.next_day(book)
    if day is None:
        return ""
    if books.is_open(book, day, today):
        return (f'<div class="bk-today"><span class="bk-k">Today · Day {day}</span>'
                f'<span class="bk-v">{_e(books.day_description(book, day))}</span></div>')
    opens = books.opens_on(book, day)
    return (f'<div class="bk-today"><span class="bk-k">Done for today</span>'
            f'<span class="bk-v">Day {day} opens on {opens:%B} {opens.day}: {_e(books.day_description(book, day))}</span></div>')


# ------------------------------------------------------------
# The bookshelf
# ------------------------------------------------------------

def on_shelf(all_books: list) -> list:
    """Books finished or stopped, most recent first."""
    shelf = [b for b in all_books if b["status"] in ("finished", "switched")]
    return sorted(shelf, key=lambda b: b.get("finished_on") or b.get("last_active_on") or b.get("started_on") or "",
                  reverse=True)


def status(book: dict) -> str:
    if book["status"] == "finished" and book.get("finished_on"):
        return f"Finished · {_day(book['finished_on'])}"
    if book["status"] == "finished":
        return "Finished"
    reached = max((int(d) for d in book["checks"]), default=1)
    return f"Stopped at day {reached}"


def _text(md: str) -> str:
    """Enough Markdown for the wrap-up: paragraphs, lists, bold, headings."""
    out, items = [], []

    def inline(s):
        s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", _e(s))
        return re.sub(r"(?<![*\w])[*_](\S(?:.*?\S)?)[*_](?![*\w])", r"<em>\1</em>", s)

    def flush():
        if items:
            out.append("<ul>" + "".join(f"<li>{inline(i)}</li>" for i in items) + "</ul>")
            items.clear()

    for block in re.split(r"\n\s*\n", (md or "").strip()):
        for line in block.splitlines():
            line = line.strip()
            if re.match(r"^[-*•]\s+", line):
                items.append(re.sub(r"^[-*•]\s+", "", line))
                continue
            flush()
            if line.startswith("#"):
                out.append(f"<p><strong>{inline(line.lstrip('#').strip())}</strong></p>")
            elif line:
                out.append(f"<p>{inline(line)}</p>")
        flush()
    return "".join(out)


def _days(book: dict) -> str:
    """The days of a book on the shelf. A finished book shows all fourteen.
    A stopped one shows the days she read; the rest wait behind one quiet
    line ("9 days not read") that opens the whole fortnight in place."""
    finished = book["status"] == "finished"
    rows, later = [], 0
    for d in range(1, books.DAYS + 1):
        check = book["checks"].get(str(d))
        if not book["plan"][d - 1]:
            state, cls = "Rest", "rest"
        elif check:
            state, cls = f"Passed · {_day(check['passed_on'])}", "passed"
        else:
            state, cls = "Not read", "unread"
        if not check and not finished:
            cls += " later"
            later += 1
        words = f'<p class="bk-words">{_e(check["summary"])}</p>' if check and check.get("summary") else ""
        rows.append(f'<li class="{cls}"><span class="bk-d">Day {d}</span>'
                    f'<span class="bk-r">{_e(books.day_description(book, d))}</span>'
                    f'<span class="bk-s">{state}</span>{words}</li>')
    more = (f'<details class="bk-more"><summary><span class="bk-more-show">{later} {"day" if later == 1 else "days"} not read</span>'
            '<span class="bk-more-hide">Show only the days read</span></summary></details>') if later else ""
    return '<ol class="bk-days">' + "".join(rows) + "</ol>" + more


def shelf_html(all_books: list, open_id: str = "") -> str:
    """One row per book; a tap opens it in place (native details: no
    reload) to its days, what she wrote each day and whether it passed,
    and the wrap-up for a finished book. Open, the row offers Close."""
    shelf = on_shelf(all_books)
    if not shelf:
        return '<p class="bk-empty">Books you finish will appear here.</p>'
    rows = []
    for b in shelf:
        author = f'<span class="bk-author">{_e(b["author"])}</span>' if b.get("author") else ""
        wrap = (f'<div class="bk-wrap"><span class="bk-k">Wrap-up</span>{_text(b["final_summary"])}</div>'
                if b.get("final_summary") else "")
        rows.append(
            f'<details class="bk-book"{" open" if b["id"] == open_id else ""}>'
            f'<summary><span class="bk-name"><span class="bk-title">{_e(b["title"] or "(untitled)")}</span>{author}</span>'
            f'<span class="bk-side"><span class="bk-state">{_e(status(b))}</span><span class="bk-close">Close</span></span></summary>'
            f'<div class="bk-open">{_days(b)}{wrap}</div></details>')
    return '<div class="bk-shelf">' + "".join(rows) + "</div>"
