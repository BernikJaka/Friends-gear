# Friends – gear needs website

A small website that shows, for every item, which **Friends** guild members still need it.
It updates itself every 5 minutes (GitHub sometimes runs it a bit later): no PC needs to be on.

- Guild members, class, level and EXP progress come from the Eclipse Kal level rankings.
- Equipped gear comes from each player's rankings profile. Until a player profile exposes
  equipment, that player shows as "waiting for game data".
- A player is only listed for grades **higher** than what they already have.
- Members who drop off the level ranking stay on the site, greyed out with the time they were
  last seen on it. They are removed when the ranking shows them in another guild or without a
  guild.

---

## Setup (one time, about 10 minutes)

1. **Create a GitHub account** at https://github.com (free).
2. **New repository** → name it e.g. `friends-gear` → Public → Create.
3. On the new repo page click **"uploading an existing file"** and drag in everything
   from this folder (`update.py`, `README.md`, `CLAUDE.md`, the `docs` folder and the
   `.github` folder). Click **Commit changes**.
   - The `.github` folder is hidden on Windows/Mac. If you can't drag it, create the file
     on GitHub instead: **Add file → Create new file**, name it
     `.github/workflows/update.yml`, paste the contents, commit.
4. **Turn on the website:** Settings → Pages → Build and deployment → Source:
   **GitHub Actions**. (Not "Deploy from a branch" - the workflow publishes the site itself.)
5. **Run the first update:** Actions tab → *Update gear site* → **Run workflow**.
   After a minute the site is live at `https://<your-username>.github.io/friends-gear/`.
   From then on it runs every 5 minutes by itself, and every push to `main` publishes
   website changes right away.
6. If your username or repo name is different, change `PUBLISHED` near the top of
   `update.py` to your site's `.../data.json` address (see "How the data is kept" below).

That's it. Post the website link in Discord. Nobody has to fill anything in: the site
picks up guild members (and later their gear) from the rankings within minutes.

### How the data is kept
The workflow runs `update.py`, then uploads the `docs` folder to GitHub Pages and deploys it.
It does **not** commit `docs/data.json` back to the repo any more. To remember things between
runs (who dropped off the ranking and when they were last seen), `update.py` first downloads
the live site's `data.json` and builds on it. If that fails it falls back to the
`docs/data.json` in the repo, which is only an old starting copy.

### If the update fails
Open the failed run in the Actions tab and read the red step. Most likely causes:
- *Rankings offline* (server update): the site keeps the last known roster, nothing to do.
- *Deploy step fails* ("Get Pages site failed" / not configured): Settings → Pages → Source
  must be **GitHub Actions**. Then click **Run workflow**.
- GitHub pauses scheduled runs after 60 days with no repo activity. The workflow no longer
  commits, so this can now happen if nobody pushes for 2 months: click **Run workflow** (or
  re-enable the workflow in the Actions tab) to restart.

---

## Hiding grades and individual items

`docs/settings.json` controls what everyone sees. Grades in `hiddenGrades` are hidden globally. Individual items in `hiddenItems` are hidden by class and catalog column (`Class:col`), so selected pieces can be hidden without hiding a whole grade:

```json
{
  "hiddenGrades": [70],
  "hiddenItems": ["Archer:W", "Archer:Y", "Mage:W", "Mage:Y", "Knight:AF", "Knight:AH", "Thief:W", "Thief:Y"]
}
```

The hidden G65 chest and shorts stay out of item cards, player missing-item counts, and Dropped items. Remove an entry from `hiddenItems` when that specific piece is ready to track. To show a hidden grade, remove its number from `hiddenGrades`.

Each visitor can also turn visible grades off just for themselves with the grade buttons above the item cards. That choice is saved in their browser and does not affect anyone else.

---

## Dropped items and Discord wheel commands

Open **Dropped items**, search or filter by class, then select the item that dropped. The
site lists ranked guild members who still need that slot and grade, and creates a copyable
`/wheel list ...` command. The list uses current gear from the rankings profiles; members
who drop off the level ranking stay eligible for up to five days after their last seen time, then disappear from item need lists and wheel candidates.

Discord names are kept in `docs/discord-users.json`, keyed by the exact in-game name. For
example:

```json
{
  "Monkey": "@Monkey",
  "AnotherPlayer": "@anotherdiscordname"
}
```

Add or update entries and commit the file. Until a Discord name is added, the command uses
that player's in-game name as plain text and the tab identifies the missing mappings.
The tab tracks G50–G59 gear, G60 armor, G62 weapons, and G65 helmets, gloves, boots, and weapons. G65 Knight shields are tracked for Commanders. Other higher-grade catalog items remain catalog-only until their drop groups are added.
Items with no current needers are omitted. In each class tab, armor and shields and weapons have
separate grade controls. A grade with no needers in that class and category is dimmed by default;
each visitor can turn it back on or save their own choices for that category.

---

Gear and progress update every five minutes from the current level rankings and player profiles.
