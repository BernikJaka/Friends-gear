# Friends guild – gear needs website

Context for Claude Code. Owner: Jaka, leader of the guild "Friends" on the Eclipse Kal
private KalOnline server (https://www.eclipsekal.com).

## What this repo does
- `update.py` runs every hour in GitHub Actions (`.github/workflows/update.yml`) and writes
  `docs/data.json`. GitHub Pages serves `docs/` as the website (`docs/index.html`).
- Roster (guild members, class, level, specialty) comes from the public rankings API:
  - https://www.eclipsekal.com/api/rankings        -> `{"players":[{name,class,specialty,level,guildName,...}]}` (top 200 by level)
  - https://www.eclipsekal.com/api/rankings/honor  -> same shape plus honor/kills/deaths (top 200 by honor)
  - EXP progress: `EXP_TABLE` (index = level) is parsed from https://www.eclipsekal.com/static/js/main.js;
    `progress` = exp / EXP_TABLE[level] * 100, capped 0-100 (exp is per level). Only `/api/rankings`
    has `exp`, so players only on the honor ranking have no progress. If main.js fails, keep the last value.
  - `class`: 0 Knight, 1 Mage, 2 Archer, 3 Thief. Specialty 7/11 names are in `SPECIALTY` in update.py.
    For Thieves the rankings have Hitman and I.Swordsman reversed, so `SPECIALTY` deliberately maps
    7 = Hitman, 11 = I.Swordsman (the opposite of the rankings site). Keep it that way.
- Gear comes only from the rankings API (the guild Google Sheet is no longer used). Until the
  API shows gear, every player has `source: "waiting"` ("waiting for game data" on the site).
- `docs/catalog.json` lists the tracked items per class (G50-G70 armor, weapons, Knight shields):
  col (unique item id, originally the sheet column), group, label, slot, grade, in-game name,
  `itemIndex` (the item's Index in Bango's inititem.dat), optional `altItemIndex` (other Indexes
  that count as owning that slot+grade) and icon URL.
- Item data and icons come from https://github.com/stribidi/kal-atlas (`bango_data/ITEMS.csv`,
  icons at https://stribidi.github.io/kal-atlas/assets/icons/<image lowercase>.png). Use the normal
  weapon versions for display, not Imperial or Soo-Ra.
- Any weapon of the same type and grade counts as having that grade (Imperial, Soo-Ra, special
  Mage sticks, Guardian, Darkness...): list their Indexes in that weapon's `altItemIndex`.

## Rules that must not change
- Players always need HIGHER grades, never lower. If a player has a slot at grade X,
  they need every tracked item in that slot with grade > X and nothing at or below X.
- Knights (Commander specialty) are the only class with shields.
- If the rankings API is down or empty, keep the previous roster - never wipe the site.
- `onRanking` means on the LEVEL ranking (/api/rankings) as a guild member. `lastSeen` (UTC ISO) is
  the last run they were on it. Members only on the honor ranking are still kept and updated
  (level, honor, guild) with `onRanking: false, onHonorRanking: true`; the site shows them grey
  with "not on level ranking · last seen: <local time>". Exp is only on the level ranking, so it
  is kept only while the level is unchanged.
- Guild members who drop off both rankings are kept (carried over from the previous docs/data.json)
  with their last known level, specialty, exp and gear and `onRanking: false`; the site shows
  "last seen on ranking: <local time>". Grey players sort below the others.
- A player is only removed when the rankings show them in a different guild (a ranked player with
  no guild is kept). If a rankings page fails to load, nobody's flags or lastSeen change.
- No third-party Python packages (plain urllib) so the Action stays simple.

## Planned change: gear on the rankings
The server admins said the rankings will show player gear. When that happens:
1. Fetch the API and look at the new field (`curl -s https://www.eclipsekal.com/api/rankings | head -c 3000`).
2. Update `gear_from_api()` in update.py so it returns `{slot: highest grade owned}`.
   Match items by `itemIndex` from catalog.json where possible.
3. Players with game gear get `source: "game"`; everyone else stays `source: "waiting"`.
4. Run `python update.py` locally, check docs/data.json, commit and push.
