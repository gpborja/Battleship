# Daily Battleship game log

This branch holds only the results of the daily automated game; the game itself lives on `main`.

- `play_daily.py` plays one full game of `battleship.html` (from `main`) in headless Chrome with Playwright, using real clicks: random fleet placement, then a mixed strategy (each shot is random 50% of the time, otherwise hunt/target using only what is visible on the enemy board).
- `game-log.csv` gets one row per game: winner, shots/hits/accuracy for both sides, ships left, duration, the result pop-up text and any JavaScript errors.

Run it by hand: `pip install playwright && git show origin/main:battleship.html > /tmp/battleship.html && python3 play_daily.py /tmp/battleship.html --commit $(git rev-parse origin/main)`
