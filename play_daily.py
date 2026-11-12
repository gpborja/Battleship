"""Play one Battleship game against the computer in a real browser and append the result to game-log.csv.

Usage: python3 play_daily.py path/to/battleship.html [--commit SHA]
The automated player uses a mixed strategy: each shot is random with 50% probability,
otherwise it uses hunt/target logic based only on what is visible on the enemy board.
"""
import argparse, csv, datetime, os, random, shutil, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright

N = 10
LOG = Path(__file__).with_name("game-log.csv")
FIELDS = ["date_utc", "main_commit", "strategy", "winner", "player_shots", "player_hits",
          "player_accuracy_pct", "random_shots", "smart_shots", "ai_shots", "ai_hits",
          "ai_accuracy_pct", "enemy_ships_left", "player_ships_left", "duration_s",
          "result_popup", "js_errors"]

READ_BOARD = """() => {
  const g = id => [...document.querySelectorAll(`#${id} .cell`)].map(e => e.className);
  return {enemy: g('enemy'), player: g('player'),
          eleft: [...document.querySelectorAll('#efleet span:not(.gone)')].map(s => +s.textContent.match(/\\((\\d)\\)/)[1]),
          pleft: document.querySelectorAll('#pfleet span:not(.gone)').length,
          active: document.querySelector('#enemy').classList.contains('active'),
          over: document.querySelector('#result').classList.contains('show')};
}"""


def smart_pick(enemy, remaining):
    st = lambda r, c: enemy[r * N + c]
    opened = lambda r, c: 0 <= r < N and 0 <= c < N and " miss" not in st(r, c) and " hit" not in st(r, c)
    hits = [(r, c) for r in range(N) for c in range(N) if " hit" in st(r, c) and "sunk" not in st(r, c)]
    if hits:
        hs = set(hits)
        line = []
        for r, c in hits:
            for dr, dc in ((0, 1), (1, 0)):
                if (r + dr, c + dc) in hs:
                    for sgn in (-1, 1):
                        rr, cc = r, c
                        while (rr, cc) in hs:
                            rr, cc = rr + sgn * dr, cc + sgn * dc
                        if opened(rr, cc):
                            line.append((rr, cc))
        if line:
            return random.choice(line)
        adj = [(r + dr, c + dc) for r, c in hits for dr, dc in ((0, 1), (1, 0), (0, -1), (-1, 0)) if opened(r + dr, c + dc)]
        if adj:
            return random.choice(adj)
    score = [[0] * N for _ in range(N)]
    for ln in remaining:
        for r in range(N):
            for c in range(N):
                for h in (True, False):
                    cells = [(r + (0 if h else i), c + (i if h else 0)) for i in range(ln)]
                    if all(opened(*x) for x in cells):
                        for x in cells:
                            score[x[0]][x[1]] += 1
    cands = [(score[r][c] + random.random() * 0.5, r, c) for r in range(N) for c in range(N) if opened(r, c)]
    _, r, c = max(cands)
    return r, c


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("html")
    ap.add_argument("--commit", default="")
    args = ap.parse_args()
    url = Path(args.html).resolve().as_uri()
    errors = []
    with sync_playwright() as p:
        exe = shutil.which("google-chrome") or shutil.which("chromium")
        browser = p.chromium.launch(executable_path=exe, headless=True) if exe else p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 1000})
        page.on("pageerror", lambda e: errors.append(str(e)))
        def on_console(m):
            where = m.text + (m.location or {}).get("url", "")
            if m.type == "error" and "tradingview" not in where.lower() and "Failed to load resource" not in m.text:
                errors.append(m.text)
        page.on("console", on_console)
        page.goto(url, wait_until="domcontentloaded")
        page.click("#random")
        page.click("#start")
        t0 = time.time()
        shots = rnd = smart = 0
        while True:
            b = page.evaluate(READ_BOARD)
            if b["over"]:
                break
            if not b["active"]:
                page.wait_for_timeout(100)
                if time.time() - t0 > 600:
                    raise SystemExit("timeout waiting for the computer's turn")
                continue
            if random.random() < 0.5:
                free = [(r, c) for r in range(N) for c in range(N) if " miss" not in b["enemy"][r * N + c] and " hit" not in b["enemy"][r * N + c]]
                r, c = random.choice(free); rnd += 1
            else:
                r, c = smart_pick(b["enemy"], b["eleft"]); smart += 1
            page.click(f'#enemy .cell[data-r="{r}"][data-c="{c}"]')
            shots += 1
            page.wait_for_function("() => !document.querySelector('#enemy').classList.contains('active') || document.querySelector('#result').classList.contains('show')")
        b = page.evaluate(READ_BOARD)
        popup = page.inner_text("#result-big")
        browser.close()
    ph = sum(" hit" in x for x in b["enemy"])
    ai_shots = sum(" miss" in x or " hit" in x for x in b["player"])
    ai_hits = sum(" hit" in x for x in b["player"])
    winner = "player" if not b["eleft"] else "computer"
    row = {"date_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M"),
           "main_commit": args.commit[:7], "strategy": "mixed", "winner": winner,
           "player_shots": shots, "player_hits": ph, "player_accuracy_pct": round(100 * ph / shots, 1),
           "random_shots": rnd, "smart_shots": smart, "ai_shots": ai_shots, "ai_hits": ai_hits,
           "ai_accuracy_pct": round(100 * ai_hits / max(ai_shots, 1), 1),
           "enemy_ships_left": len(b["eleft"]), "player_ships_left": b["pleft"],
           "duration_s": round(time.time() - t0, 1), "result_popup": popup,
           "js_errors": " | ".join(errors) or "none"}
    new = not LOG.exists()
    with LOG.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new:
            w.writeheader()
        w.writerow(row)
    print(row)
    consistent = (winner == "player") == (popup == "¡GANASTE!")
    sys.exit(0 if consistent and not errors else 1)


if __name__ == "__main__":
    main()
