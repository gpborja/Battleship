# Battleship

Cognition ejemplo

A single-page Battleship game you play in the browser against the computer. Everything (HTML, CSS and JavaScript) lives in [`battleship.html`](battleship.html), with no build step. The game itself has no dependencies; the stock box at the bottom loads a [TradingView](https://www.tradingview.com/) widget and needs an internet connection.

## How to play

1. Open `battleship.html` in any modern browser (double-click the file, or serve the folder with e.g. `python3 -m http.server` and open `http://localhost:8000/battleship.html`).
2. **Place your fleet** on the *Your fleet* grid:
   - Click a cell to place the highlighted ship. A green preview means the spot is valid, red means it is not.
   - Press **R** or the **Rotate** button to switch between horizontal and vertical.
   - **Random placement** places the whole fleet for you; **Clear** removes it.
3. Press **Start battle**.
4. Click a cell in *Enemy waters* to fire. The computer fires back after each of your shots.
5. The first side to sink the entire enemy fleet wins. Press **Play again** to start over.

### Board legend

| Mark | Meaning |
| --- | --- |
| Grey cell | Your ship (on your grid) / enemy ship revealed at the end of the game |
| Dot | Miss |
| Red ✕ | Hit |
| Dark red ✕ | Part of a sunk ship |

Sunk ships are crossed out in the fleet list under each grid, and every shot is recorded in the log at the bottom.

Below the log, a **Magnificent 7 — live** box shows live quotes for the "Magnificent 7" tech stocks: NVIDIA, Microsoft, Apple, Alphabet, Amazon, Meta and Tesla. To change the list, edit the `symbols` array in the TradingView widget at the bottom of `battleship.html`.

## Rules

- 10×10 grid, columns **A–J** and rows **1–10**.
- Each side has the classic fleet of 5 ships (17 cells in total):

  | Ship | Size |
  | --- | --- |
  | Carrier | 5 |
  | Battleship | 4 |
  | Cruiser | 3 |
  | Submarine | 3 |
  | Destroyer | 2 |

- Ships are placed horizontally or vertically and cannot overlap.
- You always fire first; turns then alternate one shot each.
- A ship is sunk when all of its cells have been hit.

## The computer opponent

The enemy fleet is placed randomly. When choosing a shot (`aiPick()`), the computer:

- **Targets** after a hit: if it has two or more hits in a row on a ship that is not yet sunk, it keeps firing along that line; otherwise it tries the cells next to its hits.
- **Hunts** when it has no open hits: for every unshot cell it counts how many ways the remaining ships could still fit through it, and fires at the most likely cell.

It typically sinks a whole fleet in about 40–50 shots, so it is a tough opponent.

## Testing

The game was verified with automated browser tests (Playwright driving real clicks on the page) across 300 full games, with 0 errors. Placement was done both manually (with rotation) and with **Random placement**, and games were restarted with **Play again**. After every game the tests checked:

- no JavaScript errors;
- each fleet has 5 straight, non-overlapping ships covering 17 cells;
- no cell is ever shot twice, and clicks on already-shot cells are ignored;
- hit counts match the ships, and the correct winner is announced with the right turn order;
- the boards on screen match the game state, and the remaining enemy ships are revealed at the end.

| Player strategy | Games | Result |
| --- | --- | --- |
| Random shots | 100 | Computer won 100 (random shooting needs ~94 shots on average to finish) |
| Half random, half with knowledge of enemy positions | 100 | 50 / 50 |
| Same smart strategy as the computer (no hidden information) | 100 | Player 51, computer 49 |
