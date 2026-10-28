"""Builds docs/data.json for the Friends gear website.

Everything comes from the Eclipse Kal rankings API: the roster (who is in the
guild, class, level) and, once the admins add it, each player's gear. Players
without gear on the rankings yet show as "waiting for game data".

Rule: a player only needs an item if they don't already have that slot at the
same or a higher grade. Players always need higher grades, never lower.

No third-party packages needed - runs on plain Python 3.
"""
import json, os, re, sys, time, urllib.request
from urllib.parse import quote
from datetime import datetime, timezone

GUILD = os.environ.get("GUILD", "Friends")
EXCLUDED_PLAYERS = {"codename", "exoticalpha"}  # confirmed former guild members
# The live site's data.json is the previous run's state (lastSeen, carried-over players): the Action
# deploys to GitHub Pages and no longer commits docs/data.json, so the copy in the repo is only a fallback.
PUBLISHED = os.environ.get("PUBLISHED_DATA", "https://bernikjaka.github.io/Friends-gear/data.json")
MAIN_JS = "https://www.eclipsekal.com/static/js/main.js"   # has EXP_TABLE (index = level)
RANKING = "https://www.eclipsekal.com/api/v1/rankings"   # level ranking; the only roster source
PLAYER_API = "https://www.eclipsekal.com/api/v1/players/"
CLASSES = {0: "Knight", 1: "Mage", 2: "Archer", 3: "Thief"}
SPECIALTY = {
    0: {1: "Wandering Knight", 3: "Apprentice Knight", 7: "Vagabond", 11: "Commander", 15: "Two Job Knight"},
    1: {1: "Scholar", 3: "Literary Person", 7: "Hermit", 11: "C.J.B", 15: "Two Job Mage"},
    2: {1: "Wandering Archer", 3: "Apprentice Archer", 7: "Expert Archer", 11: "Imperial Commander", 15: "Two Job Archer"},
    # Thief 7/11 are deliberately swapped: the Eclipse Kal rankings mix up Hitman and I.Swordsman
    3: {1: "Wandering Thief", 3: "Thief Guild member", 7: "Hitman", 11: "I.Swordsman", 15: "Two Job Thief"},
}
# Confirmed corrections from the in-game rankings; these take precedence over API code mappings.
SPECIALTY_OVERRIDES = {
    "roki": "Hermit",
    "holycjb": "C.J.B",
    "dinkler": "Commander",
    "pringles": "Commander",
}
HERE = os.path.dirname(os.path.abspath(__file__))
DOCS = os.path.join(HERE, "docs")
EXP_TABLE_FILE = os.path.join(DOCS, "exp-table.json")
CATALOG = json.load(open(os.path.join(DOCS, "catalog.json")))
# some items exist under several Indexes in inititem.dat (variants of the same grade), see altItemIndex
BY_INDEX = {i: (cls, e) for cls, items in CATALOG.items() for e in items
            for i in [e["itemIndex"], *e.get("altItemIndex", [])]}
SETTINGS = json.load(open(os.path.join(DOCS, "settings.json"), encoding="utf-8"))
HIDDEN_ITEMS = set(SETTINGS.get("hiddenItems", []))


def get(url, timeout=30):
    req = urllib.request.Request(url, headers={
        "User-Agent": "FriendsGuildGearBot/1.0", "Cache-Control": "no-cache", "Pragma": "no-cache"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8")


def fetch_ranking(url):
    """{lowercase name: player} from the level ranking, or None if it failed/was empty."""
    try:
        response = json.loads(get(url))
        page = response.get("level") or response.get("players") or []
    except Exception as e:  # site down / updating
        print(f"! {url}: {e}", file=sys.stderr)
        return None
    if not page:
        print(f"! {url}: no players", file=sys.stderr)
        return None
    return {str(p.get("name", "")).lower(): p for p in page}


def fetch_player_profile(name):
    try:
        return json.loads(get(PLAYER_API + quote(name)))
    except Exception as e:
        print(f"! player profile {name}: {e}", file=sys.stderr)
        return None


def fetch_exp_table():
    """Fetch EXP_TABLE; on a transient failure use the last deployed or checked-in table."""
    table = None
    for attempt in range(3):
        try:
            url = MAIN_JS + "?_=" + str(int(time.time()))  # avoid a stale CDN copy
            m = re.search(r"EXP_TABLE\s*=\s*\[([^\]]*)\]", get(url))
            table = [int(x) for x in re.findall(r"\d+", m.group(1))] if m else None
            if table:
                print("EXP table: fetched from rankings main.js")
                break
            print("! EXP_TABLE not found in main.js", file=sys.stderr)
        except Exception as e:
            print(f"! {MAIN_JS} (attempt {attempt + 1}/3): {e}", file=sys.stderr)
        if attempt < 2:
            time.sleep(2)

    if not table:
        # This asset is deployed alongside data.json, so Actions can recalculate against the last
        # successful table even when the game site's JS endpoint is temporarily unreachable.
        deployed = PUBLISHED.rsplit("/", 1)[0] + "/exp-table.json"
        try:
            candidate = json.loads(get(deployed))
            if isinstance(candidate, list) and candidate and all(isinstance(x, int) for x in candidate):
                table = candidate
                print("EXP table: using last deployed cache", file=sys.stderr)
        except Exception as e:
            print(f"! {deployed}: {e}", file=sys.stderr)
    if not table and os.path.exists(EXP_TABLE_FILE):
        try:
            candidate = json.load(open(EXP_TABLE_FILE, encoding="utf-8"))
            if isinstance(candidate, list) and candidate and all(isinstance(x, int) for x in candidate):
                table = candidate
                print("EXP table: using checked-in cache", file=sys.stderr)
        except Exception as e:
            print(f"! {EXP_TABLE_FILE}: {e}", file=sys.stderr)

    if table:
        json.dump(table, open(EXP_TABLE_FILE, "w", encoding="utf-8"), separators=(",", ":"))
        return table
    return None


def exp_progress(table, level, exp):
    """Percent of the current level done, the same way the rankings site's progressPct() does it:
    exp / EXP_TABLE[level] * 100, but exp above the level's requirement is treated as total exp
    (minus all previous levels), capped 0-100. Rounded to 2 decimals like the site."""
    if not table or level is None or exp is None or not 0 <= level < len(table) or table[level] <= 0:
        return None
    req = table[level]
    per_level = max(0, exp - sum(table[:level])) if exp > req else exp
    return round(max(0.0, min(100.0, per_level / req * 100)), 2)


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


def gear_from_profile(cls, profile):
    """Return highest owned grade by tracked slot from the rankings site's equipment list."""
    if not isinstance(profile, dict) or not isinstance(profile.get("equipment"), list):
        return None
    owned = {}
    armor_slots = {"helmet": "helmet", "chest": "chest", "gloves": "gloves",
                   "pants": "shorts", "shorts": "shorts", "boots": "boots", "shield": "shield"}
    weapon_slot = {"Knight": "weapon_1hsword", "Mage": "weapon_stick",
                   "Archer": "weapon_bow", "Thief": "weapon_dagger"}.get(cls)
    for item in profile["equipment"]:
        if not isinstance(item, dict):
            continue
        slot = str(item.get("slot", "")).strip().lower()
        target = armor_slots.get(slot)
        if slot == "weapon":
            target = weapon_slot
            # Knights can equip either sword type. The item name identifies two-handed swords.
            if cls == "Knight" and any(word in str(item.get("name", "")).lower()
                                         for word in ("giant", "two-handed", "2h")):
                target = "weapon_2hsword"
        try:
            grade = int(item.get("level"))
        except (TypeError, ValueError):
            continue
        if target:
            owned[target] = max(owned.get(target, 0), grade)
    return owned


def load_previous(out_path):
    """The previous run's data: the published site's data.json, else the local docs/data.json."""
    try:
        data = json.loads(get(PUBLISHED))
        if isinstance(data, dict) and isinstance(data.get("classes"), dict):
            print("Previous data: published site")
            return data
        print(f"! {PUBLISHED}: no classes in it", file=sys.stderr)
    except Exception as e:
        print(f"! {PUBLISHED}: {e}", file=sys.stderr)
    if os.path.exists(out_path):
        print("Previous data: docs/data.json (fallback)")
        return json.load(open(out_path, encoding="utf-8"))
    return {}


def needs_from_gear(cls, owned, specialty=None):
    excluded_slots = set()
    if cls == "Knight":
        # Use the specialization when available; otherwise infer the track from equipped gear.
        if specialty == "Commander" or (specialty != "Vagabond" and
                                          ("weapon_1hsword" in owned or "shield" in owned)):
            excluded_slots.add("weapon_2hsword")
        elif specialty == "Vagabond" or "weapon_2hsword" in owned:
            excluded_slots.update(("weapon_1hsword", "shield"))
    return [e["col"] for e in CATALOG[cls]
            if (e["grade"] <= 55
                or (e["grade"] == 60 and e["slot"] in ("helmet", "chest", "gloves", "shorts", "boots"))
                or (e["grade"] == 62 and e["slot"].startswith("weapon_"))
                or (e["grade"] == 65 and (e["slot"] in ("helmet", "chest", "gloves", "shorts", "boots")
                                          or e["slot"].startswith("weapon_"))))
            and f'{cls}:{e["col"]}' not in HIDDEN_ITEMS
            and e["grade"] > owned.get(e["slot"], 0) and e["slot"] not in excluded_slots]


def main():
    out_path = os.path.join(DOCS, "data.json")
    previous = load_previous(out_path)
    now = datetime.now(timezone.utc).isoformat(timespec="minutes")
    ranked = fetch_ranking(RANKING)
    exp_table = None
    if ranked and any(p.get("expPct") is None and p.get("guildName", p.get("guild")) == GUILD
                      for p in ranked.values()):
        exp_table = fetch_exp_table()
    prev = {pl["name"].lower(): (c, pl) for c, block in previous.get("classes", {}).items()
            for pl in block.get("players", [])}
    if ranked is None:
        print("! rankings unavailable, keeping the previous roster as it was", file=sys.stderr)

    roster = {c: [] for c in CATALOG}
    seen = set()
    for key, p in (ranked or {}).items():
        if key in EXCLUDED_PLAYERS:
            continue
        c = int(p.get("class", p.get("cls", -1)))
        guild = p.get("guildName", p.get("guild"))
        if guild != GUILD or c not in CLASSES:
            continue
        old = prev.get(key, (None, {}))[1]
        cls = CLASSES[c]
        profile = fetch_player_profile(p["name"])
        profile_player = (profile or {}).get("player", {})
        live_gear = gear_from_profile(cls, profile)
        if live_gear is None:
            live_gear = gear_from_api(p)
        exp_pct = p.get("expPct", profile_player.get("expPct"))
        roster[CLASSES[c]].append({
            "name": p["name"], "level": p.get("level"), "exp": p.get("exp"),
            "progress": round(float(exp_pct), 2) if exp_pct is not None else old.get("progress"),
            "specialty": (SPECIALTY_OVERRIDES.get(str(p.get("name", "")).lower())
                          or SPECIALTY.get(c, {}).get(int(p.get("specialty") or 0))
                          or profile_player.get("specialty") or old.get("specialty") or CLASSES[c]),
            "gear": live_gear if live_gear is not None else old.get("gear"),
            "onRanking": True, "lastSeen": now})
        seen.add(key)

    # Carry over everyone from the last run who isn't on the ranking now, with their last known
    # level/specialty/exp/gear. A player who IS on the ranking with any guildName other than GUILD
    # (another guild, or no guild: empty, null, "-" or missing) has left and is removed.
    for key, (c, pl) in prev.items():
        if key in EXCLUDED_PLAYERS:
            continue
        if key in seen or c not in roster:
            continue
        if ranked and key in ranked and ranked[key].get("guildName", ranked[key].get("guild")) != GUILD:
            print(f"- {pl['name']} left the guild (now: {ranked[key].get('guildName', ranked[key].get('guild')) or 'no guild'}), removed")
            continue
        old = {k: v for k, v in pl.items() if k not in ("needs", "source")}
        old.setdefault("lastSeen", None)
        # ranking down: keep what we knew before instead of marking everyone as dropped off
        old["onRanking"] = False if ranked is not None else pl.get("onRanking", True)
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
                needs, source = needs_from_gear(cls, p["gear"], p.get("specialty")), "game"
            else:
                needs, source = [], "waiting"
            p = {**p, "progress": p.get("progress") if p.get("progress") is not None else
                 (exp_progress(exp_table, p.get("level"), p.get("exp")) if exp_table
                  else old_progress.get(p["name"].lower()))}   # preserve ranking progress if EXP data is absent
            players.append({**p, "needs": needs, "source": source})
        items = [{**e, "needers": [p["name"] for p in players if e["col"] in p["needs"]]}
                 for e in CATALOG[cls]]
        classes[cls] = {"players": players, "items": items}

    data = {"guild": GUILD, "updated": now,
            "rankingsOnline": ranked is not None, "classes": classes}
    # always write: the Action deploys docs/ as it is, so a skipped write would publish the repo's stale copy
    json.dump(data, open(out_path, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print("No changes." if previous.get("classes") == classes else "Updated", out_path,
          {c: len(v["players"]) for c, v in classes.items()})


if __name__ == "__main__":
    main()
