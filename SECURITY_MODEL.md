# Security model

This file describes the security model of this repository. Security scans start from it.

## System overview

A single-page Battleship game you play in the browser against a computer opponent. Everything (HTML, CSS and JavaScript) lives in `battleship.html`, and `README.md` documents it. The game has no dependencies, no build step, no third-party scripts, no network requests, no backend, no accounts and no storage (no `localStorage`, no cookies).

## Components

| Name | Covers |
| --- | --- |
| **Game UI** | `battleship.html`: markup, CSS, DOM rendering (`buildGrid`, `render`, `renderFleet`, `setStatus`, `log`), event handlers and controls |
| **Game logic & AI** | the `battleship.html` `<script>`: board and fleet model (`newBoard`, `canPlace`, `place`, `randomFleet`, `fire`, `allSunk`), turn flow (`playerFire`, `aiTurn`), AI (`aiPick`) |
| **Docs** | `README.md` |

## Trust boundaries and entry points

- The only boundary is the browser tab. The only inputs are the local user's clicks on grid cells and buttons, and the `R` key.
- Nothing is read from URL parameters, `postMessage`, fetch/XHR, storage or any other external source.
- DOM sinks: `renderFleet` writes `innerHTML`, but only from the constant `FLEET` array. `log` and `setStatus` use `textContent`.

## Deployment

The README says to open the game as a local file or through a local static server. There is no infrastructure or deployment configuration.

## Assets

- The integrity of the game in the user's own tab (the hidden enemy fleet, the turn order). The game handles no personal data, credentials or secrets.

## Attacker profiles

- **Remote web attacker** injecting script into the page: this only matters if untrusted data ever reaches a DOM sink. None does today.
- **Local player cheating**: in a client-only game, DevTools always shows `state.enemy`, so this cannot be prevented.
- **Supply chain**: the game has no dependencies or external scripts.

## Existing controls

- Log and status text use `textContent`. `innerHTML` is only used with constant data.
- Input validation: `canPlace` checks bounds and overlap, and `playerFire` ignores clicks on cells already shot and clicks made out of turn.

## Out of scope / accepted risk

None stated yet.

## Open questions

- How is the game served: locally only, on public static hosting, or embedded in another site?
- Will cheating by the local player matter (for example, future scores, leaderboards or multiplayer)?
