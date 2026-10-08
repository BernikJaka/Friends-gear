# Friends – gear needs website

A small website that shows, for every item, which **Friends** guild members still need it.
It updates itself every 5 minutes (GitHub sometimes runs it a bit later): no PC needs to be on.

- Guild members, class and level come from the Eclipse Kal rankings.
- Gear comes from the rankings too, once the admins add it there. Until then every
  player shows as "waiting for game data".
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

## Hiding or showing grades

`docs/settings.json` decides which grades the website shows to everyone:

```json
{"hiddenGrades": [60, 62, 65, 70]}
```

Grades in this list are hidden for every visitor: no item cards, no toggle button, and
they don't count in **Missing** on the Roster tab. The script still tracks all grades,
so nothing is lost while a grade is hidden.

To **unhide a grade** (for example when the guild starts farming G60), open
`docs/settings.json` on GitHub, click the pencil icon, remove the number from the list
and click **Commit changes**:

```json
{"hiddenGrades": [62, 65, 70]}
```

To show every grade, use an empty list: `{"hiddenGrades": []}`. The site updates within
a minute or two (refresh the page). Keep the format exactly as above - numbers only,
separated by commas.

Every visitor can also turn grades off just for themselves with the G50 / G53 / ...
buttons above the item cards. That choice is saved in their own browser and doesn't
affect anyone else.

---

## When the rankings start showing gear (using Claude Code)

The script already looks for gear on the rankings, but nobody knows the exact format
yet. When the admins add it, let Claude Code adapt the script:

1. Install Claude Code: https://docs.claude.com/en/docs/claude-code/overview
2. Download the repo to your PC (green **Code** button → *Download ZIP*, or `git clone`).
3. Open a terminal in that folder and run `claude`.
4. Tell it: *"The Eclipse Kal rankings now show player gear. Update gear_from_api in
   update.py so the site uses it, test it, and push."*
   `CLAUDE.md` already explains the project and the higher-grade rule, so it knows the context.

After the push, the hourly GitHub Action uses the new code automatically.
