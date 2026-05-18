"""
PLA Gray-Zone + Hidden Reach Locations Tracker
Persists last known status for 16 monitored sites across two analytical blocks.
Exposes build_context_block() for the digest LLM prompt.

Gray-Zone block: 8 AMTI / China Power Project locations
Hidden Reach block: 8 CSIS Hidden Reach locations
"""
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

TRACKER_FILE = Path(__file__).parent / "bp_tracker.json"

# ─────────────────────────────────────────────────────────────────────────────
# LOCATION DEFINITIONS (block / canonical name / CSIS product / coords)
# ─────────────────────────────────────────────────────────────────────────────

GRAY_ZONE_LOCATIONS = [
    {
        "name": "Taiwan Strait Median Line",
        "csis_product": "China Power Project — PLA incursion tracker",
        "watching": "PLAN / PLAAF crossings, ADIZ incursions",
    },
    {
        "name": "Scarborough Shoal",
        "csis_product": "AMTI",
        "watching": "CCG vs. Philippine BFAR, water cannon incidents",
    },
    {
        "name": "Second Thomas Shoal (Ayungin)",
        "csis_product": "AMTI",
        "watching": "BRP Sierra Madre resupply, CCG interdiction",
    },
    {
        "name": "Sandy Cay",
        "csis_product": "AMTI",
        "watching": "Recent PRC flag-planting; CCG presence",
    },
    {
        "name": "Mischief Reef",
        "csis_product": "AMTI Big Three Spratlys",
        "watching": "Militarization, vessel deployments",
    },
    {
        "name": "Fiery Cross Reef",
        "csis_product": "AMTI Big Three Spratlys",
        "watching": "Militarization, garrison rotation",
    },
    {
        "name": "Subi Reef",
        "csis_product": "AMTI Big Three Spratlys",
        "watching": "Militarization, militia vessel berthing",
    },
    {
        "name": "Senkaku / Diaoyu Islands",
        "csis_product": "AMTI East China Sea",
        "watching": "CCG patrol-days inside contiguous zone",
    },
]

HIDDEN_REACH_LOCATIONS = [
    {
        "name": "Chancay, Peru (COSCO)",
        "csis_product": "Hidden Reach — 'No Safe Harbor' (Jun 2025)",
        "watching": "COSCO mega-port operations, LAC flagship case",
    },
    {
        "name": "Cuba SIGINT (Bejucal / Wajay)",
        "csis_product": "Hidden Reach — May 2025 satellite update",
        "watching": "Antenna array construction, SIGINT facility expansion",
    },
    {
        "name": "Tier 1 Chinese shipyards (Jiangnan / Hudong-Zhonghua / Dalian)",
        "csis_product": "Hidden Reach — 'Ship Wars' / 'Murky Waters' (Mar 2025)",
        "watching": "Naval vessel construction, dual-use capacity",
    },
    {
        "name": "Djibouti PLA Support Base",
        "csis_product": "Hidden Reach — 'Dire Straits' (Feb 2023)",
        "watching": "PLAN vessel transits, base expansion",
    },
    {
        "name": "Khalifa Port, UAE",
        "csis_product": "Hidden Reach — 'Dire Straits'",
        "watching": "Alleged dual-use military facility, port construction",
    },
    {
        "name": "Ream Naval Base, Cambodia",
        "csis_product": "Hidden Reach — ongoing tracker",
        "watching": "PLAN access, dock expansion, vessel berthing",
    },
    {
        "name": "Hambantota / Bay of Bengal",
        "csis_product": "Hidden Reach — 'Surveying the Seas' (Jan 2024)",
        "watching": "China Merchants 99-year lease, research vessel calls",
    },
    {
        "name": "Russian Arctic + Polar Silk Road",
        "csis_product": "Hidden Reach — 'Frozen Frontiers' (Apr 2023)",
        "watching": "Murmansk, Sabetta, Indiga port development",
    },
]

ALL_LOCATIONS = [
    {**loc, "block": "gray_zone"} for loc in GRAY_ZONE_LOCATIONS
] + [
    {**loc, "block": "hidden_reach"} for loc in HIDDEN_REACH_LOCATIONS
]


# ─────────────────────────────────────────────────────────────────────────────
# STORAGE
# ─────────────────────────────────────────────────────────────────────────────

def _empty_status() -> dict:
    return {
        "status": "normal",       # normal | activity | elevated | alert
        "note": "No reporting yet",
        "last_source_date": None,
        "direction": "",          # up | down | ""
        "updated_at": None,
    }


def _load() -> dict:
    if not TRACKER_FILE.exists():
        return {
            "locations": {loc["name"]: _empty_status() for loc in ALL_LOCATIONS},
            "last_updated": None,
        }
    try:
        with open(TRACKER_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Ensure all current locations are present
        for loc in ALL_LOCATIONS:
            if loc["name"] not in data.get("locations", {}):
                data.setdefault("locations", {})[loc["name"]] = _empty_status()
        return data
    except (json.JSONDecodeError, OSError):
        return {
            "locations": {loc["name"]: _empty_status() for loc in ALL_LOCATIONS},
            "last_updated": None,
        }


def _save(data: dict) -> None:
    data["last_updated"] = datetime.now(timezone.utc).isoformat()
    with open(TRACKER_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def update_location(name: str, status: str, note: str, source_date: str,
                    direction: str = "") -> None:
    """Update a single location's last-known status."""
    data = _load()
    if name not in data["locations"]:
        data["locations"][name] = _empty_status()
    data["locations"][name].update({
        "status": status,
        "note": note,
        "last_source_date": source_date,
        "direction": direction,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })
    _save(data)


def get_status(name: str) -> dict:
    return _load()["locations"].get(name, _empty_status())


def build_context_block() -> str:
    """Build the prompt context block for digest.py with last-known status for each location."""
    data = _load()
    lines = [
        "MONITORED LOCATIONS HISTORY (persistent tracker — last known status for each site):",
        "",
        "Use these as GROUND TRUTH. If today's articles update a location, override.",
        "Otherwise CARRY FORWARD the note verbatim — do NOT replace with 'no new reporting'.",
        "",
    ]

    lines.append("── GRAY-ZONE MONITOR (AMTI / China Power Project) ──")
    for loc in GRAY_ZONE_LOCATIONS:
        s = data["locations"].get(loc["name"], _empty_status())
        date_str = s.get("last_source_date") or "—"
        lines.append(
            f"  • {loc['name']} [{s['status']}] (last: {date_str}, "
            f"dir: {s.get('direction') or '—'}): {s['note']}"
        )

    lines.append("")
    lines.append("── HIDDEN REACH MONITOR (CSIS Hidden Reach) ──")
    for loc in HIDDEN_REACH_LOCATIONS:
        s = data["locations"].get(loc["name"], _empty_status())
        date_str = s.get("last_source_date") or "—"
        lines.append(
            f"  • {loc['name']} [{s['status']}] (last: {date_str}, "
            f"dir: {s.get('direction') or '—'}): {s['note']}"
        )

    return "\n".join(lines)


def location_names_for_prompt() -> dict:
    """Return location names organized by block, for digest.py prompt."""
    return {
        "gray_zone": [loc["name"] for loc in GRAY_ZONE_LOCATIONS],
        "hidden_reach": [loc["name"] for loc in HIDDEN_REACH_LOCATIONS],
    }


if __name__ == "__main__":
    print(build_context_block())
