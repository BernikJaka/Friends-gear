"""Watch the top 300 level-ranked players for equipped G62 weapons."""
import concurrent.futures
import json
import os
import urllib.request
from datetime import datetime, timezone
from urllib.parse import quote

ROOT = "https://www.eclipsekal.com/api/v1/"
PREVIOUS = "https://bernikjaka.github.io/Friends-gear/g62-watch.json"
OUT = os.path.join(os.path.dirname(__file__), "docs", "g62-watch.json")
WEAPONS = {"Golden Bow", "Golden Stick", "Golden Sword", "Golden Giant Sword", "Golden dagger"}

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "FriendsGearWatch/1.0", "Cache-Control": "no-cache"})
    with urllib.request.urlopen(req, timeout=15) as response:
        return json.load(response)

def check(player):
    name = str(player.get("name", ""))
    if not name:
        return None
    try:
        profile = fetch(ROOT + "players/" + quote(name))
        equipped = profile.get("equipment", [])
        if not isinstance(equipped, list):
            return None
        matches = []
        for item in equipped:
            if not isinstance(item, dict) or str(item.get("slot", "")).lower() != "weapon":
                continue
            weapon = str(item.get("name", ""))
            try:
                grade = int(item.get("level", 0))
            except (ValueError, TypeError):
                continue
            if grade == 62 or weapon.lower() in {w.lower() for w in WEAPONS}:
                matches.append(weapon or "G62 weapon")
        return {"name": name, "guild": player.get("guildName") or player.get("guild") or "No guild", "weapons": matches}
    except Exception as exc:
        print("Profile unavailable:", name, exc)
        return None

def main():
    try:
        ranking = fetch(ROOT + "rankings")
        top = (ranking.get("level") or ranking.get("players") or [])[:300]
        if not top:
            raise ValueError("Empty level ranking")
    except Exception as exc:
        print("Ranking unavailable:", exc)
        return
    try:
        previous = fetch(PREVIOUS)
    except Exception:
        try:
            with open(OUT, encoding="utf-8") as file:
                previous = json.load(file)
        except Exception:
            previous = {}
    history = previous.get("history", [])
    known = {(event["name"].lower(), event["weapon"].lower()) for event in history}
    now = datetime.now(timezone.utc).isoformat(timespec="minutes")
    current = []
    checked = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
        for result in pool.map(check, top):
            if result is None:
                continue
            checked += 1
            for weapon in result["weapons"]:
                event = {"name": result["name"], "guild": result["guild"], "weapon": weapon}
                current.append(event)
                key = (event["name"].lower(), weapon.lower())
                if key not in known:
                    history.insert(0, {**event, "firstSeen": now})
                    known.add(key)
                    print("NEW G62 WEAPON:", event)
    if checked < max(10, len(top) // 3):
        print("Too few successful profiles; preserving previous watch state")
        return
    with open(OUT, "w", encoding="utf-8") as file:
        json.dump({"checkedAt": now, "playersChecked": checked, "topCount": len(top),
                   "current": current, "history": history[:100]}, file, indent=2)
    print("G62 watch:", checked, "checked,", len(current), "currently equipped")

if __name__ == "__main__":
    main()
