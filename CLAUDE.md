# Friends guild – gear needs website

Context for Claude Code. Owner: Jaka, leader of the guild "Friends" on the Eclipse Kal
private KalOnline server (https://www.eclipsekal.com).

## What this repo does
- `update.py` runs in GitHub Actions (`.github/workflows/update.yml`) every 5 minutes, on
  workflow_dispatch and on every push to main. It writes `docs/data.json`, then the workflow
  uploads `docs/` with actions/upload-pages-artifact and deploys it with actions/deploy-pages
  (Pages source = GitHub Actions). The workflow does NOT commit data.json.
- Previous state (lastSeen, carried-over players) comes from the LIVE site's data.json
  (`PUBLISHED` in update.py, https://bernikjaka.github.io/Friends-gear/data.json), falling back to
  the repo's `docs/data.json`, which is only a stale seed. update.py must always write data.json
  (never skip the write), or the deploy would publish the stale repo copy.
- Roster (guild members, class, level and progress) comes only from the level ranking:
  - https://www.eclipsekal.com/api/v1/rankings -> `level: [{name,cls,level,expPct,guild,...}]`.
  - Player equipment comes from https://www.eclipsekal.com/api/v1/players/<name> in `equipment`;
    each entry has a `slot`, `name` and item `level` (grade). `gear_from_profile()` maps these
    to tracked slots and takes the highest grade. Knights' weapon name distinguishes Giant (2H)
    swords from standard (1H) swords. Honor ranking data is not used.
  - `expPct` is supplied by the rankings API and is the value shown on the rankings site; store it
    rounded to two decimals. The old `main.js`/EXP_TABLE endpoint is no longer reliable and is only
    a fallback for carried data that has no API progress value.
  - `class`: 0 Knight, 1 Mage, 2 Archer, 3 Thief. Specialty 7/11 names are in `SPECIALTY` in update.py.
    For Thieves the rankings have Hitman and I.Swordsman reversed, so `SPECIALTY` deliberately maps
    7 = Hitman, 11 = I.Swordsman (the opposite of the rankings site). Keep it that way.
- Gear comes only from the rankings player profiles (the guild Google Sheet is no longer used).
  Until the profile exposes equipment, every player has `source: "waiting"` ("waiting for game
  data" on the site). Use its `expPct` for progress; it is the rankings site's displayed value.
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
- Commander Knights need checks for 1H swords and shields; Vagabond Knights need checks for 2H swords.
- If the rankings API is down or empty, keep the previous roster - never wipe the site.
- `onRanking` means on `/api/v1/rankings` as a guild member; `lastSeen` (UTC ISO) is the last run they were.
- Guild members who drop off the ranking are kept (carried over from the previous docs/data.json)
  with their last known level, specialty, exp and gear and `onRanking: false`; the site shows them
  grey with "last seen on ranking: <local time>" (or "unknown") below the others.
- A player is removed when they ARE on the ranking with any guildName other than "Friends"
  (another guild, or no guild: empty, null, "-" or missing). Players not on the ranking at all are
  kept. If the ranking fails to load, nobody is removed and nobody's flags or lastSeen change.
- No third-party Python packages (plain urllib) so the Action stays simple.

## Dropped items and Discord names
- The Dropped items tab combines catalog items and current needers to produce `/wheel list ...`.
- The Dropped items tab shows items below G60 only until higher grades start dropping; updater tracking remains unchanged.
- Only players currently on the level ranking are selectable because carried-over gear is stale.
- Add Discord names to `docs/discord-users.json`, keyed by exact in-game name. Unmapped users
  appear as plain in-game names in the generated command.
