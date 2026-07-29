#!/usr/bin/env python3
"""Render profile.svg: ASCII portrait + neofetch-style card, animated.

    python3 gen_profile.py                 # renders with stats as "--"
    GITHUB_TOKEN=... python3 gen_profile.py   # fetches live GitHub stats

stdlib only. The GitHub Action re-runs this on a cron and commits the SVG.
"""

import datetime as dt
import json
import os
import urllib.error
import urllib.request

USER = "Adityagarg2712"
UPTIME_SINCE = "2005-12-27"

ART = os.path.join(os.path.dirname(__file__), "ascii-art.txt")
OUT = os.path.join(os.path.dirname(__file__), "profile.svg")

# ---------------------------------------------------------------- content

def uptime(since):
    a, b = dt.date.fromisoformat(since), dt.date.today()
    years = b.year - a.year - ((b.month, b.day) < (a.month, a.day))
    months = (b.month - a.month - (b.day < a.day)) % 12
    anchor = a.replace(year=a.year + years)
    anchor = add_months(anchor, months)
    days = (b - anchor).days
    return ", ".join(f"{n} {u}" if n == 1 else f"{n} {u}s"
                     for n, u in ((years, "year"), (months, "month"), (days, "day")))


def add_months(d, n):
    m = d.month - 1 + n
    y, m = d.year + m // 12, m % 12 + 1
    day = min(d.day, [31, 29 if y % 4 == 0 and (y % 100 or y % 400 == 0) else 28,
                      31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1])
    return dt.date(y, m, day)


def stats():
    """(repos, stars, commits, followers) from the GitHub API, or dashes."""
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        return ["--"] * 4

    def get(path):
        req = urllib.request.Request(
            "https://api.github.com" + path,
            headers={"Authorization": f"Bearer {token}",
                     "Accept": "application/vnd.github+json",
                     "User-Agent": USER},
        )
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.load(r)

    try:
        user = get(f"/users/{USER}")
        repos = get(f"/users/{USER}/repos?per_page=100&type=owner")
        commits = get(f"/search/commits?q=author:{USER}&per_page=1")
        return [f"{user['public_repos']:,}",
                f"{sum(r['stargazers_count'] for r in repos):,}",
                f"{commits['total_count']:,}",
                f"{user['followers']:,}"]
    except (urllib.error.URLError, urllib.error.HTTPError, KeyError, TimeoutError) as e:
        print(f"stats fetch failed ({e}); rendering dashes")
        return ["--"] * 4


def card():
    repos, stars, commits, followers = stats()
    return [
        ("head", f"{USER.lower()}@github"),
        ("gap",),
        ("kv", "OS", "macOS, Linux"),
        ("kv", "Uptime", uptime(UPTIME_SINCE)),
        ("kv", "Host", "Stanford University"),
        ("kv", "Kernel", "Physics + ML / Hardware"),
        ("kv", "IDE", "Claude Code, Cursor, Jupyter"),
        ("gap",),
        ("kv", "Languages.Programming", "Python, C++, JavaScript"),
        ("kv", "Languages.Real", "English, Hindi, French, Gujarati"),
        ("kv", "Hobbies", "Sci-fi games, board games, finding loopholes"),
        ("gap",),
        ("sec", "Contact"),
        ("kv", "Email", "aditya27@stanford.edu"),
        ("kv", "LinkedIn", "in/Aditya27Garg"),
        ("gap",),
        ("sec", "GitHub Stats"),
        ("kv", "Repos", repos),
        ("kv", "Stars", stars),
        ("kv", "Commits", commits),
        ("kv", "Followers", followers),
    ]

# ---------------------------------------------------------------- layout

ART_ROWS = 57      # rows to keep; the source art's tail is dithered noise
MIN_COLS = 54      # card width in characters; grows if a row needs it
ART_FS, ART_LH = 6.4, 6.4
FS, LH = 14.0, 22.0
CH = 0.6           # monospace advance / font-size
PAD, GAP = 34.0, 46.0

C = {"bg": "#0d1117", "edge": "#30363d", "label": "#e3a869", "val": "#c9d1d9",
     "dot": "#3d444d", "head": "#58a6ff", "rule": "#30363d"}


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def art_lines():
    raw = [l.rstrip() for l in open(ART).read().split("\n")]
    while raw and not raw[0]:
        raw.pop(0)
    while raw and not raw[-1]:
        raw.pop()
    raw = raw[:ART_ROWS]
    indent = min(len(l) - len(l.lstrip()) for l in raw if l)
    return [l[indent:] for l in raw]


def cols(rows):
    return max([MIN_COLS] + [len(r[1]) + len(r[2]) + 4 for r in rows if r[0] == "kv"])


def row(item, x, y, w, COLS):
    """-> svg for one card row at (x, y). w = card width in px."""
    if item[0] == "gap":
        return ""
    if item[0] in ("head", "sec"):
        txt = esc(item[1])
        lead = txt if item[0] == "head" else "&#8212; " + txt
        x0 = x + (len(txt) + (2 if item[0] == "head" else 4)) * FS * CH
        ry = y - FS * 0.32
        return (f'<text x="{x:.1f}" y="{y:.1f}" fill="{C["head"]}">{lead}</text>'
                f'<line x1="{x0:.1f}" y1="{ry:.1f}" x2="{x + w:.1f}"'
                f' y2="{ry:.1f}" stroke="{C["rule"]}"/>')

    label, val = esc(item[1]) + ":", esc(item[2])
    fill = max(1, COLS - len(label) - len(val) - 2)
    dots = ("".join(" ." for _ in range(fill // 2 + 1)))[:fill]
    return (f'<text x="{x:.1f}" y="{y:.1f}" xml:space="preserve">'
            f'<tspan fill="{C["label"]}">{label}</tspan>'
            f'<tspan fill="{C["dot"]}"> {dots} </tspan>'
            f'<tspan fill="{C["val"]}">{val}</tspan></text>')


def build():
    art = art_lines()
    art_w = max(len(l) for l in art) * ART_FS * CH
    art_h = len(art) * ART_LH
    rows = card()
    COLS = cols(rows)
    card_w = COLS * FS * CH
    card_h = len(rows) * LH

    w = PAD * 2 + art_w + GAP + card_w
    h = max(art_h, card_h) + PAD * 2
    art_x = PAD
    art_y = (h - art_h) / 2 + ART_FS
    card_x = PAD + art_w + GAP
    card_y = (h - card_h) / 2 + FS

    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.0f}" height="{h:.0f}" '
         f'viewBox="0 0 {w:.0f} {h:.0f}" font-family="ui-monospace,SFMono-Regular,'
         f'Menlo,DejaVu Sans Mono,Consolas,monospace">',
         '<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
         '<stop offset="0" stop-color="#7ee0d3"/><stop offset="0.55" stop-color="#6c8cff"/>'
         '<stop offset="1" stop-color="#b78cff"/></linearGradient>',
         # art draws top-to-bottom
         f'<clipPath id="scan"><rect x="0" y="{art_y - ART_LH:.1f}" width="{w:.0f}" height="0">'
         f'<animate attributeName="height" from="0" to="{art_h + ART_LH:.1f}"'
         f' dur="2.4s" begin="0.2s" fill="freeze"/></rect></clipPath>']

    # per-row typewriter clips
    t = 0.5
    for i, it in enumerate(rows):
        if it[0] == "gap":
            t += 0.06
            continue
        y = card_y + i * LH
        o.append(f'<clipPath id="r{i}"><rect x="{card_x - 2:.1f}" y="{y - LH:.1f}"'
                 f' width="0" height="{LH * 1.4:.1f}">'
                 f'<animate attributeName="width" from="0" to="{card_w + 8:.1f}"'
                 f' dur="0.42s" begin="{t:.2f}s" fill="freeze"/></rect></clipPath>')
        t += 0.19
    o.append("</defs>")

    o.append(f'<rect width="{w:.0f}" height="{h:.0f}" rx="16" fill="{C["bg"]}"/>')
    o.append(f'<rect x="10" y="10" width="{w - 20:.0f}" height="{h - 20:.0f}" rx="12"'
             f' fill="none" stroke="{C["edge"]}"/>')

    o.append(f'<g clip-path="url(#scan)" font-size="{ART_FS}" fill="url(#g)"'
             f' xml:space="preserve">')
    for i, line in enumerate(art):
        o.append(f'<text x="{art_x}" y="{art_y + i * ART_LH:.1f}">{esc(line)}</text>')
    # scanline riding the reveal
    o.append(f'<rect x="{art_x}" y="{art_y:.1f}" width="{art_w:.1f}" height="2"'
             f' fill="#7ee0d3" opacity="0">'
             f'<animate attributeName="y" from="{art_y - ART_LH:.1f}"'
             f' to="{art_y + art_h:.1f}" dur="2.4s" begin="0.2s" fill="freeze"/>'
             f'<animate attributeName="opacity" values="0;0.55;0.55;0" dur="2.6s"'
             f' begin="0.2s" fill="freeze"/></rect>')
    o.append("</g>")

    o.append(f'<g font-size="{FS}" fill="{C["val"]}">')
    for i, it in enumerate(rows):
        svg = row(it, card_x, card_y + i * LH, card_w, COLS)
        if svg:
            o.append(f'<g clip-path="url(#r{i})">{svg}</g>')
    # cursor keeps blinking once typing lands
    cy = card_y + (len(rows) - 1) * LH
    o.append(f'<rect x="{card_x + card_w + 6:.1f}" y="{cy - FS * 0.8:.1f}"'
             f' width="{FS * CH:.1f}" height="{FS:.1f}" fill="{C["head"]}" opacity="0">'
             f'<animate attributeName="opacity" values="0;1;1;0;0" dur="1.1s"'
             f' begin="{t:.2f}s" repeatCount="indefinite"/></rect>')
    o.append("</g></svg>")
    return "\n".join(o)


if __name__ == "__main__":
    assert "Uptime" in [r[1] for r in card() if r[0] == "kv"]
    assert uptime("2024-09-23")  # date math doesn't blow up on today
    svg = build()
    assert svg.count("<clipPath") == svg.count("</clipPath>")
    with open(OUT, "w") as f:
        f.write(svg)
    print(f"wrote {OUT} ({len(svg):,} bytes)")
