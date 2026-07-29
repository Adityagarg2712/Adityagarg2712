#!/usr/bin/env python3
"""Render profile.svg: ASCII portrait + neofetch-style card, animated.

    python3 gen_profile.py                 # renders with stats as "--"
    GITHUB_TOKEN=... python3 gen_profile.py   # fetches live GitHub stats

stdlib only. The GitHub Action re-runs this on a cron and commits the SVG.
"""

import datetime as dt
import json
import os
import re
import time
import urllib.error
import urllib.request
import zlib

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


def rendered(label):
    """The value this label already shows in profile.svg, if the file exists."""
    try:
        svg = open(OUT).read()
    except FileNotFoundError:
        return None
    m = re.search(rf">{label}:</tspan>(?:<tspan[^>]*>[^<]*</tspan>)"
                  rf"<tspan[^>]*>([^<]*)</tspan>", svg)
    return m.group(1) if m else None


def stats():
    """(repos, stars, commits, followers) from the GitHub API, or dashes.

    Commits are all-time and include private work, which only the GraphQL
    contributions API exposes -- and only to a token owned by USER. The
    repo-scoped GITHUB_TOKEN sees public contributions only, so the Action
    needs a PAT (read:user) in secrets.PROFILE_TOKEN for the full number.
    """
    token = os.environ.get("PROFILE_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        return ["--"] * 5
    scopes = []   # filled in from X-OAuth-Scopes on the first response

    def api(path, body=None, tries=4):
        for _ in range(tries):
            req = urllib.request.Request(
                "https://api.github.com" + path,
                data=json.dumps(body).encode() if body else None,
                headers={"Authorization": f"Bearer {token}",
                         "Accept": "application/vnd.github+json",
                         "User-Agent": USER},
            )
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    raw = r.read()
                    if r.status == 202:      # stats still being generated
                        time.sleep(3)
                        continue
                    scopes[:] = [s.strip() for s
                                 in (r.headers.get("X-OAuth-Scopes") or "").split(",")]
                    return json.loads(raw) if raw else None
            except urllib.error.HTTPError as e:
                if e.code in (403, 404, 409):   # no access, or empty repo
                    return None
                raise
        return None

    def lines():
        """Additions/deletions credited to USER across every repo the token sees.

        Contributor stats are per-repo and private ones need `repo` scope, which
        a read:user PAT lacks -- hence the scope check before spending 20+ calls.
        """
        add = dele = 0
        page, missed = 1, []
        while True:
            batch = api(f"/user/repos?per_page=100&page={page}"
                        "&affiliation=owner,collaborator,organization_member")
            if not batch:
                break
            for r in batch:
                contrib = api(f"/repos/{r['full_name']}/stats/contributors")
                if contrib is None:
                    missed.append(r["full_name"])
                    continue
                for c in contrib:
                    if (c.get("author") or {}).get("login") != USER:
                        continue
                    add += sum(w["a"] for w in c["weeks"])
                    dele += sum(w["d"] for w in c["weeks"])
            if len(batch) < 100:
                break
            page += 1
        if missed:
            print(f"line counts exclude {len(missed)} repo(s) with no stats yet: "
                  + ", ".join(missed))
        return f"+{add:,} / -{dele:,}"

    def all_commits(created_year):
        """Sum of GitHub's own per-year contribution totals -- the same figure the
        profile graph shows, so the card always agrees with it. Private work is
        included once the account opts into showing it."""
        years = range(created_year, dt.date.today().year + 1)
        window = " ".join(
            f'y{y}: contributionsCollection(from:"{y}-01-01T00:00:00Z",'
            f' to:"{y}-12-31T23:59:59Z")'
            "{ contributionCalendar { totalContributions } }"
            for y in years)
        d = api("/graphql", {"query": f'{{ user(login:"{USER}") {{ {window} }} }}'})
        c = d["data"]["user"]
        return sum(c[f"y{y}"]["contributionCalendar"]["totalContributions"]
                   for y in years)

    try:
        user = api(f"/users/{USER}")
        repos = api(f"/users/{USER}/repos?per_page=100&type=owner")
        n = f"{all_commits(int(user['created_at'][:4])):,}"
        # ponytail: without a PAT the count silently drops to public-only, so keep
        # whatever the last good render had. Set PROFILE_TOKEN and this goes away.
        commits = n if os.environ.get("PROFILE_TOKEN") else (rendered("Commits") or n)
        # ponytail: private line counts need `repo` scope. Without it, keep the last
        # good figure rather than silently reporting public-only totals.
        loc = lines() if "repo" in scopes else (rendered("Lines of Code") or lines())
        return [f"{user['public_repos']:,} public",
                f"{sum(r['stargazers_count'] for r in repos):,}",
                commits,
                f"{user['followers']:,}",
                loc]
    except (urllib.error.URLError, urllib.error.HTTPError, KeyError, TimeoutError) as e:
        print(f"stats fetch failed ({e}); rendering dashes")
        return ["--"] * 5


_CARD = None


def card():
    global _CARD
    if _CARD:
        return _CARD
    repos, stars, commits, followers, loc = stats()
    _CARD = [
        ("head", f"{USER.lower()}@github"),
        ("gap",),
        ("kv", "OS", "Windows, macOS, Linux"),
        ("kv", "Uptime", uptime(UPTIME_SINCE)),
        ("kv", "Host", "Stanford University"),
        ("kv", "Kernel", "Physics + CS"),
        ("kv", "IDE", "Claude Code, Cursor, VS Code, Jupyter"),
        ("gap",),
        ("kv", "Languages.Programming", "Python, C++, JavaScript"),
        ("kv", "Languages.Real", "English, Hindi, French"),
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
        ("kv", "Lines of Code", loc),
    ]
    return _CARD

# ---------------------------------------------------------------- layout

ART_ROWS = 57      # rows to keep; the source art's tail is dithered noise
MIN_COLS = 54      # card width in characters; grows if a row needs it
CH = 0.6           # monospace advance / font-size
ART_FS = 6.4
ART_LH = ART_FS * CH * 2   # terminal cell is 1:2, so line height = 2x char advance
FS, LH = 14.0, 22.0
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

    o.append(f'<g clip-path="url(#scan)" font-size="{ART_FS}" fill="url(#g)">')
    for i, line in enumerate(art):
        # xml:space must sit on the text element -- it does NOT inherit from the g,
        # and without it every run of spaces collapses and the art shears.
        o.append(f'<text x="{art_x}" y="{art_y + i * ART_LH:.1f}"'
                 f' xml:space="preserve">{esc(line)}</text>')
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


def bump_readme(svg):
    """Point the img at a content-derived URL and keep its alt text truthful.

    GitHub's CDN caches /raw/main/profile.svg, so without a version that changes
    with the bytes the page keeps serving a stale render. Derived from the SVG,
    not the date, so an unchanged render produces no churn.
    """
    p = os.path.join(os.path.dirname(__file__), "README.md")
    kv = {r[1]: r[2] for r in card() if r[0] == "kv"}
    alt = (f"{USER.lower()}@github - {kv['Kernel']} at {kv['Host']}. {kv['OS']}. "
           f"{kv['Languages.Programming']}. {kv['Email']}")
    tag = (f'<img src="profile.svg?v={zlib.crc32(svg.encode()) & 0xffffffff:x}"'
           f' alt="{esc(alt)}" width="100%">')
    old = open(p).read()
    new = re.sub(r'<img src="profile\.svg[^>]*>', tag, old)
    if new != old:
        with open(p, "w") as f:
            f.write(new)
        print(f"bumped {p}")


if __name__ == "__main__":
    assert "Uptime" in [r[1] for r in card() if r[0] == "kv"]
    assert uptime("2024-09-23")  # date math doesn't blow up on today
    svg = build()
    assert svg.count("<clipPath") == svg.count("</clipPath>")
    with open(OUT, "w") as f:
        f.write(svg)
    print(f"wrote {OUT} ({len(svg):,} bytes)")
    bump_readme(svg)
