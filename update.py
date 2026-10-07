"""Builds docs/data.json for the Friends gear website.

Everything comes from the Eclipse Kal rankings API: the roster (who is in the
guild, class, level) and, once the admins add it, each player's gear. Players
without gear on the rankings yet show as "waiting for game data".

Rule: a player only needs an item if they don't already have that slot at the
same or a higher grade. Players always need higher grades, never lower.

No third-party packages needed - runs on plain Python 3.
"""
import json, os, sys, urllib.request
from datetime import datetime, timezone

GUILD = os.environ.get("GUILD", "Friends")
RANKINGS = ["https://www.eclipsekal.com/api/rankings",
            "https://www.eclipsekal.com/api/rankings/honor"]
CLASSES = {0: "Knight", 1: "Mage", 2: "Archer", 3: "Thief"}
SPECIALTY = {
    0: {1: "Wandering Knight", 3: "Apprentice Knight", 7: "Vagabond", 11: "Commander", 15: "Two Job Knight"},
    1: {1: "Scholar", 3: "Literary Person", 7: "Hermit", 11: "C.J.B", 15: "Two Job Mage"},
    2: {1: "Wandering Archer", 3: "Apprentice Archer", 7: "Expert Archer", 11: "Imperial Commander", 15: "Two Job Archer"},
    3: {1: "Wandering Thief", 3: "Thief Guild member", 7: "I.Swordsman", 11: "Hitman", 15: "Two Job Thief"},
}
HERE = os.path.dirname(os.path.abspath(__file__))
DOCS = os.path.join(HERE, "docs")
CATALOG = json.load(open(os.path.join(DOCS, "catalog.json")))
# some items exist under several Indexes in inititem.dat (same name/grade), see altItemIndex
BY_INDEX = {i: (cls, e) for cls, items in CATALOG.items() for e in items
            for i in [e["itemIndex"], *e.get("altItemIndex", [])]}


def get(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": "FriendsGuildGearBot/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8")


def fetch_rankings():
    players = {}
    for url in RANKINGS:
        try:
            for p in json.loads(get(url)).get("players") or []:
                key = str(p.get("name", "")).lower()
                players[key] = {**players.get(key, {}), **p}
        except Exception as e:  # site down / updating
            print(f"! {url}: {e}", file=sys.stderr)
    return list(players.values())


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
    ranked = fetch_rankings()
    members = [p for p in ranked if p.get("guildName") == GUILD]

    roster = {c: [] for c in CATALOG}
    if members:
        for p in members:
            c = int(p.get("class", -1))
            if c in CLASSES:
                roster[CLASSES[c]].append({
                    "name": p["name"], "level": p.get("level"),
                    "specialty": SPECIALTY.get(c, {}).get(int(p.get("specialty") or 0), CLASSES[c]),
                    "honor": p.get("honor"), "gear": gear_from_api(p)})
    else:  # rankings offline - keep the last known roster instead of wiping the site
        print("! no guild members from rankings, keeping previous roster", file=sys.stderr)
        for c, block in previous.get("classes", {}).items():
            roster[c] = [{k: v for k, v in pl.items() if k != "needs"} for pl in block.get("players", [])]

    classes = {}
    for cls in CATALOG:
        players = []
        for p in sorted(roster[cls], key=lambda x: -(x.get("level") or 0)):
            if p.get("gear"):
                needs, source = needs_from_gear(cls, p["gear"]), "game"
            else:
                needs, source = [], "waiting"
            players.append({**{k: v for k, v in p.items() if k != "gear"}, "needs": needs, "source": source})
        items = [{**e, "needers": [p["name"] for p in players if e["col"] in p["needs"]]}
                 for e in CATALOG[cls]]
        classes[cls] = {"players": players, "items": items}

    data = {"guild": GUILD, "updated": datetime.now(timezone.utc).isoformat(timespec="minutes"),
            "rankingsOnline": bool(ranked), "classes": classes}
    if previous.get("classes") == classes:
        print("No changes.")
        return
    json.dump(data, open(out_path, "w"), indent=1, ensure_ascii=False)
    print("Updated", out_path, {c: len(v["players"]) for c, v in classes.items()})


if __name__ == "__main__":
    main()
