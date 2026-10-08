"""Builds docs/data.json for the Friends gear website.

Everything comes from the Eclipse Kal rankings API: the roster (who is in the
guild, class, level) and, once the admins add it, each player's gear. Players
without gear on the rankings yet show as "waiting for game data".

Rule: a player only needs an item if they don't already have that slot at the
same or a higher grade. Players always need higher grades, never lower.

No third-party packages needed - runs on plain Python 3.
"""
import json, os, re, sys, urllib.request
from datetime import datetime, timezone

GUILD = os.environ.get("GUILD", "Friends")
MAIN_JS = "https://www.eclipsekal.com/static/js/main.js"   # has EXP_TABLE (index = level)
LEVEL_RANKING = "https://www.eclipsekal.com/api/rankings"        # decides onRanking
HONOR_RANKING = "https://www.eclipsekal.com/api/rankings/honor"
CLASSES = {0: "Knight", 1: "Mage", 2: "Archer", 3: "Thief"}
SPECIALTY = {
    0: {1: "Wandering Knight", 3: "Apprentice Knight", 7: "Vagabond", 11: "Commander", 15: "Two Job Knight"},
    1: {1: "Scholar", 3: "Literary Person", 7: "Hermit", 11: "C.J.B", 15: "Two Job Mage"},
    2: {1: "Wandering Archer", 3: "Apprentice Archer", 7: "Expert Archer", 11: "Imperial Commander", 15: "Two Job Archer"},
    # Thief 7/11 are deliberately swapped: the Eclipse Kal rankings mix up Hitman and I.Swordsman
    3: {1: "Wandering Thief", 3: "Thief Guild member", 7: "Hitman", 11: "I.Swordsman", 15: "Two Job Thief"},
}
HERE = os.path.dirname(os.path.abspath(__file__))
DOCS = os.path.join(HERE, "docs")
CATALOG = json.load(open(os.path.join(DOCS, "catalog.json")))
# some items exist under several Indexes in inititem.dat (variants of the same grade), see altItemIndex
BY_INDEX = {i: (cls, e) for cls, items in CATALOG.items() for e in items
            for i in [e["itemIndex"], *e.get("altItemIndex", [])]}


def get(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": "FriendsGuildGearBot/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8")


def fetch_ranking(url):
    """{lowercase name: player} from one rankings page, or None if it failed or came back empty."""
    try:
        page = json.loads(get(url)).get("players") or []
    except Exception as e:  # site down / updating
        print(f"! {url}: {e}", file=sys.stderr)
        return None
    if not page:
        print(f"! {url}: no players", file=sys.stderr)
        return None
    return {str(p.get("name", "")).lower(): p for p in page}


def fetch_exp_table():
    """EXP needed for each level (index = level) from the rankings site's main.js, or None."""
    try:
        m = re.search(r"EXP_TABLE\s*=\s*\[([^\]]*)\]", get(MAIN_JS))
        table = [int(x) for x in re.findall(r"\d+", m.group(1))] if m else []
        if table:
            return table
        print("! EXP_TABLE not found in main.js", file=sys.stderr)
    except Exception as e:
        print(f"! {MAIN_JS}: {e}", file=sys.stderr)
    return None


def exp_progress(table, level, exp):
    """Percent of the current level done: exp / EXP_TABLE[level] * 100, capped 0-100."""
    if not table or level is None or exp is None or not 0 <= level < len(table) or table[level] <= 0:
        return None
    return round(max(0.0, min(100.0, exp / table[level] * 100)), 1)


def gear_from_api(p):
    """Return {slot: highest grade owned} from the rankings API, or None if the API
    has no gear for this player yet. When the admins add gear, adjust this to the
    real field name/format (ask Claude Code - see CLAUDE.md)."""
    raw = next((p[k] for k in ("gear", "equipment", "equip", "items", "inventory") if p.get(k)), None)
    if not raw:
        return None
    owned = {}
    entries = raw.values() if isinstance(raw, dict) else raw
    for it in entries:
        idx = it if isinstance(it, int) else next(
            (it.get(k) for k in ("itemIndex", "index", "item_index", "id", "itemId") if isinstance(it, dict) and it.get(k) is not None), None)
        try:
            idx = int(idx)
        except (TypeError, ValueError):
            continue
        if idx in BY_INDEX:
            _, e = BY_INDEX[idx]
            owned[e["slot"]] = max(owned.get(e["slot"], 0), e["grade"])
    return owned


def needs_from_gear(cls, owned):
    return [e["col"] for e in CATALOG[cls] if e["grade"] > owned.get(e["slot"], 0)]


def main():
    out_path = os.path.join(DOCS, "data.json")
    previous = json.load(open(out_path)) if os.path.exists(out_path) else {}
    now = datetime.now(timezone.utc).isoformat(timespec="minutes")
    level_rank, honor_rank = fetch_ranking(LEVEL_RANKING), fetch_ranking(HONOR_RANKING)
    ranked = {k: {**(honor_rank or {}).get(k, {}), **(level_rank or {}).get(k, {})}
              for k in {*(level_rank or {}), *(honor_rank or {})}}
    exp_table = fetch_exp_table()
    prev = {pl["name"].lower(): (c, pl) for c, block in previous.get("classes", {}).items()
            for pl in block.get("players", [])}

    def last_seen(pl):
        """When this player was last on the level ranking, from the previous data.json."""
        if "onHonorRanking" not in pl and pl.get("onRanking", True) and pl.get("exp") is None:
            return None   # saved before this rule while only on the honor ranking (no exp): never seen on level
        return pl.get("lastSeen", previous.get("updated"))

    # onRanking = on the LEVEL ranking. If a page failed to load, keep what we knew before.
    def on_level(key, old):
        return key in level_rank if level_rank is not None else old.get("onRanking", True)
    def on_honor(key, old):
        return key in honor_rank if honor_rank is not None else old.get("onHonorRanking", False)

    roster = {c: [] for c in CATALOG}
    seen = set()
    for key, p in ranked.items():
        c = int(p.get("class", -1))
        if p.get("guildName") != GUILD or c not in CLASSES:
            continue
        old = prev.get(key, (None, {}))[1]
        lvl, in_level = p.get("level"), on_level(key, old)
        if key in (level_rank or {}):
            exp = p.get("exp")
        else:  # only the level ranking has exp; the old value is only valid for the same level
            exp = old.get("exp") if old.get("level") == lvl else None
        roster[CLASSES[c]].append({
            "name": p["name"], "level": lvl, "exp": exp,
            "specialty": SPECIALTY.get(c, {}).get(int(p.get("specialty") or 0), CLASSES[c]),
            "honor": p["honor"] if "honor" in p else old.get("honor"),
            "gear": gear_from_api(p) or old.get("gear"),
            "onRanking": in_level, "onHonorRanking": on_honor(key, old),
            "lastSeen": now if key in (level_rank or {}) else last_seen(old) if old else None})
        seen.add(key)

    # Carry over everyone from the last run who isn't on either ranking now, with their last known
    # level/specialty/exp/gear. Only drop a player when the rankings show them in another guild.
    for key, (c, pl) in prev.items():
        if key in seen or c not in roster:
            continue
        other = (ranked.get(key) or {}).get("guildName")
        if other and other != GUILD:
            print(f"- {pl['name']} is now in guild {other}, removed")
            continue
        old = {k: v for k, v in pl.items() if k not in ("needs", "source")}
        # not on either ranking as a guild member; if a page failed to load, keep what we knew before
        old.update(lastSeen=last_seen(pl),
                   onRanking=False if level_rank is not None else pl.get("onRanking", True),
                   onHonorRanking=False if honor_rank is not None else pl.get("onHonorRanking", False))
        roster[c].append(old)
        seen.add(key)

    old_progress = {pl["name"].lower(): pl.get("progress")
                    for block in previous.get("classes", {}).values() for pl in block.get("players", [])}
    classes = {}
    for cls in CATALOG:
        players = []
        # players still on the rankings first, then those who dropped off; highest level first
        for p in sorted(roster[cls], key=lambda x: (not x.get("onRanking", True), -(x.get("level") or 0))):
            if p.get("gear"):
                needs, source = needs_from_gear(cls, p["gear"]), "game"
            else:
                needs, source = [], "waiting"
            p = {**p, "progress": exp_progress(exp_table, p.get("level"), p.get("exp")) if exp_table
                 else p.get("progress", old_progress.get(p["name"].lower()))}   # main.js down: keep last known
            players.append({**p, "needs": needs, "source": source})
        items = [{**e, "needers": [p["name"] for p in players if e["col"] in p["needs"]]}
                 for e in CATALOG[cls]]
        classes[cls] = {"players": players, "items": items}

    data = {"guild": GUILD, "updated": now,
            "rankingsOnline": bool(ranked), "classes": classes}
    if previous.get("classes") == classes:
        print("No changes.")
        return
    json.dump(data, open(out_path, "w"), indent=1, ensure_ascii=False)
    print("Updated", out_path, {c: len(v["players"]) for c, v in classes.items()})


if __name__ == "__main__":
    main()
