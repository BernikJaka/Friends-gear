# Friends – gear needs website

A small website that shows, for every item, which **Friends** guild members still need it.
It updates itself every hour: no PC needs to be on.

- Guild members, class and level come from the Eclipse Kal rankings.
- Gear comes from the guild Google Sheet for now (Yes/No dropdowns), and from the
  rankings once the admins add gear there.
- A player is only listed for grades **higher** than what they already have.

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
4. **Turn on the website:** Settings → Pages → Source: *Deploy from a branch* →
   Branch `main`, folder `/docs` → Save. After a minute the site is live at
   `https://<your-username>.github.io/friends-gear/`.
5. **Run the first update:** Actions tab → *Update gear site* → **Run workflow**.
   From then on it runs every hour by itself.

That's it. Post the website link in Discord. Guildies keep filling in the Google Sheet;
the site picks it up within the hour.

### If the update fails
Open the failed run in the Actions tab and read the red step. Most likely causes:
- *Rankings offline* (server update): the site keeps the last known roster, nothing to do.
- *Sheet not readable*: the sheet must stay shared as "Anyone with the link".
- GitHub pauses scheduled runs after 60 days with no repo activity; click **Run workflow** once to restart.

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
