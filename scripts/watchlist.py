#!/usr/bin/env python3
"""
Shared TV Watchlist
A record of every show two people have watched together, what each of them
thought of it, and what that says about what they should watch next.

Data lives in data/shows.json. Metadata (year, genres, network, episode
counts, posters) is filled in from TMDB when TMDB_API_KEY is set.

Usage:
    python scripts/watchlist.py add "The Bear" --ratings a=9,b=7 --status finished
    python scripts/watchlist.py import my_shows.txt
    python scripts/watchlist.py rate "The Bear" a=9 b=8
    python scripts/watchlist.py enrich
    python scripts/watchlist.py stats
    python scripts/watchlist.py recommend -n 15
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_FILE = DATA_DIR / "shows.json"

TMDB_BASE = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w342"

# Rated 1-10. Anything unrated is stored as null and skipped by the stats.
RATING_MIN, RATING_MAX = 1, 10

STATUSES = ("finished", "watching", "paused", "abandoned")

# Average score -> how we describe it. Ordered high to low.
VERDICTS = (
    (9.0, "loved"),
    (7.5, "great"),
    (6.0, "liked"),
    (4.0, "fine"),
    (0.0, "disliked"),
)


# ============================================================
# Data layer
# ============================================================

def slugify(title: str) -> str:
    """Turn a show title into a stable lookup key."""
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug or "untitled"


def empty_data() -> dict:
    return {
        "lastUpdated": None,
        "viewers": {"a": {"name": "Me"}, "b": {"name": "Her"}},
        "shows": [],
    }


def load_data() -> dict:
    """Read the watchlist, tolerating a missing file on first run."""
    if not DATA_FILE.exists():
        return empty_data()
    with DATA_FILE.open(encoding="utf-8") as f:
        data = json.load(f)
    data.setdefault("viewers", empty_data()["viewers"])
    data.setdefault("shows", [])
    return data


def save_data(data: dict) -> None:
    data["lastUpdated"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    DATA_DIR.mkdir(exist_ok=True)
    with DATA_FILE.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def viewer_ids(data: dict) -> list:
    return list(data["viewers"].keys())


def viewer_name(data: dict, vid: str) -> str:
    return data["viewers"].get(vid, {}).get("name", vid)


def find_show(data: dict, query: str):
    """Look a show up by slug, exact title, then unique substring."""
    slug = slugify(query)
    for show in data["shows"]:
        if show["slug"] == slug:
            return show

    lowered = query.lower().strip()
    matches = [s for s in data["shows"] if lowered in s["title"].lower()]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        titles = ", ".join(s["title"] for s in matches[:5])
        raise SystemExit(f"❌ '{query}' matches several shows: {titles}")
    return None


def new_show(title: str) -> dict:
    return {
        "title": title.strip(),
        "slug": slugify(title),
        "status": "finished",
        "ratings": {},
        "tags": [],
        "note": "",
        "started": None,
        "finished": None,
        "rewatched": False,
        "tmdb": None,
    }


def parse_ratings(pairs, data: dict) -> dict:
    """Parse 'a=9 b=7' or 'a=9,b=7' into {'a': 9, 'b': 7}."""
    ratings = {}
    tokens = []
    for chunk in pairs:
        tokens.extend(t for t in chunk.split(",") if t.strip())

    known = viewer_ids(data)
    for token in tokens:
        if "=" not in token:
            raise SystemExit(f"❌ Ratings look like a=9 b=7, got '{token}'")
        vid, raw = token.split("=", 1)
        vid, raw = vid.strip(), raw.strip()
        if vid not in known:
            raise SystemExit(f"❌ Unknown viewer '{vid}'. Known: {', '.join(known)}")
        if raw.lower() in ("", "none", "null", "-"):
            ratings[vid] = None
            continue
        try:
            score = float(raw)
        except ValueError:
            raise SystemExit(f"❌ '{raw}' is not a number")
        if not RATING_MIN <= score <= RATING_MAX:
            raise SystemExit(f"❌ Ratings run {RATING_MIN}-{RATING_MAX}, got {raw}")
        ratings[vid] = int(score) if score.is_integer() else score
    return ratings


# ============================================================
# Derived values
# ============================================================

def scores(show: dict) -> list:
    """Every rating actually given for a show."""
    return [v for v in show.get("ratings", {}).values() if isinstance(v, (int, float))]


def average(show: dict):
    vals = scores(show)
    return round(sum(vals) / len(vals), 2) if vals else None


def spread(show: dict):
    """How far apart the two of them were. None unless both rated it."""
    vals = scores(show)
    return round(max(vals) - min(vals), 2) if len(vals) > 1 else None


def verdict(show: dict) -> str:
    if show.get("status") == "abandoned":
        return "bailed"
    avg = average(show)
    if avg is None:
        return "unrated"
    for threshold, label in VERDICTS:
        if avg >= threshold:
            return label
    return "disliked"


def episode_count(show: dict) -> int:
    tmdb = show.get("tmdb") or {}
    return tmdb.get("episodes") or 0


def hours(show: dict) -> float:
    tmdb = show.get("tmdb") or {}
    runtime = tmdb.get("runtime") or 0
    return round(episode_count(show) * runtime / 60, 1)


def genres_of(show: dict) -> list:
    return (show.get("tmdb") or {}).get("genres") or []


# ============================================================
# TMDB
# ============================================================

def tmdb_key() -> str:
    key = os.environ.get("TMDB_API_KEY")
    if not key:
        raise SystemExit(
            "❌ TMDB_API_KEY is not set.\n"
            "   Get a free key at https://www.themoviedb.org/settings/api\n"
            "   then: export TMDB_API_KEY=your_key"
        )
    return key


def tmdb_get(path: str, key: str, **params):
    """One TMDB call. Returns None on any error so a long run doesn't die."""
    try:
        import requests
    except ImportError:
        raise SystemExit("❌ This command needs requests: pip install requests")

    params["api_key"] = key
    try:
        response = requests.get(f"{TMDB_BASE}{path}", params=params, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as exc:  # network, rate limit, bad id
        print(f"  ⚠️  TMDB {path}: {exc}")
        return None


def tmdb_details(tv_id: int, key: str):
    """Fetch the fields we actually display."""
    detail = tmdb_get(f"/tv/{tv_id}", key)
    if not detail:
        return None

    runtimes = detail.get("episode_run_time") or []
    air_date = detail.get("first_air_date") or ""
    poster = detail.get("poster_path")

    return {
        "id": detail.get("id"),
        "name": detail.get("name"),
        "year": int(air_date[:4]) if air_date[:4].isdigit() else None,
        "genres": [g["name"] for g in detail.get("genres", [])],
        "networks": [n["name"] for n in detail.get("networks", [])],
        "seasons": detail.get("number_of_seasons"),
        "episodes": detail.get("number_of_episodes"),
        "runtime": runtimes[0] if runtimes else None,
        "poster": f"{TMDB_IMAGE_BASE}{poster}" if poster else None,
        "overview": detail.get("overview") or "",
        "tmdbScore": round(detail.get("vote_average") or 0, 1),
        "showStatus": detail.get("status"),
    }


# ============================================================
# Commands
# ============================================================

def cmd_add(args):
    data = load_data()
    if find_show(data, args.title):
        raise SystemExit(f"❌ '{args.title}' is already on the list. Use `rate` or `set`.")

    show = new_show(args.title)
    if args.ratings:
        show["ratings"] = parse_ratings(args.ratings, data)
    show["status"] = args.status
    show["note"] = args.note or ""
    show["tags"] = [t.strip() for t in (args.tags or "").split(",") if t.strip()]
    show["started"] = args.started
    show["finished"] = args.finished
    show["rewatched"] = args.rewatched

    data["shows"].append(show)
    save_data(data)
    print(f"✅ Added {show['title']} ({verdict(show)})")


def parse_import_line(line: str, data: dict):
    """One show per line:  Title | 9 | 7 | status | note

    Everything after the title is optional, so a bare list of titles works.
    """
    parts = [p.strip() for p in line.split("|")]
    title = parts[0]
    if not title:
        return None

    show = new_show(title)
    known = viewer_ids(data)

    for index, value in enumerate(parts[1:]):
        if not value:
            continue
        if index < len(known):
            # Positional ratings, in viewer order.
            try:
                score = float(value)
            except ValueError:
                show["note"] = value
                continue
            if RATING_MIN <= score <= RATING_MAX:
                show["ratings"][known[index]] = int(score) if score.is_integer() else score
        elif value.lower() in STATUSES:
            show["status"] = value.lower()
        else:
            show["note"] = value
    return show


def cmd_import(args):
    data = load_data()
    source = sys.stdin if args.file == "-" else open(args.file, encoding="utf-8")
    added, skipped = 0, 0

    with source as handle:
        for raw in handle:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            show = parse_import_line(line, data)
            if show is None:
                continue
            if find_show(data, show["title"]):
                print(f"  ↷ already listed: {show['title']}")
                skipped += 1
                continue
            data["shows"].append(show)
            added += 1
            print(f"  + {show['title']}")

    save_data(data)
    print(f"\n✅ Imported {added} show(s), skipped {skipped} duplicate(s)")


def cmd_rate(args):
    data = load_data()
    show = find_show(data, args.title)
    if not show:
        raise SystemExit(f"❌ '{args.title}' is not on the list. Add it first.")

    show["ratings"].update(parse_ratings(args.ratings, data))
    save_data(data)

    given = ", ".join(
        f"{viewer_name(data, vid)} {show['ratings'][vid]}"
        for vid in viewer_ids(data)
        if show["ratings"].get(vid) is not None
    )
    print(f"✅ {show['title']}: {given} → {verdict(show)}")


def cmd_set(args):
    data = load_data()
    show = find_show(data, args.title)
    if not show:
        raise SystemExit(f"❌ '{args.title}' is not on the list.")

    changed = []
    for field in ("status", "note", "started", "finished"):
        value = getattr(args, field)
        if value is not None:
            show[field] = value
            changed.append(field)
    if args.tags is not None:
        show["tags"] = [t.strip() for t in args.tags.split(",") if t.strip()]
        changed.append("tags")
    if args.rewatched:
        show["rewatched"] = True
        changed.append("rewatched")

    if not changed:
        raise SystemExit("❌ Nothing to change.")
    save_data(data)
    print(f"✅ {show['title']}: updated {', '.join(changed)}")


def cmd_remove(args):
    data = load_data()
    show = find_show(data, args.title)
    if not show:
        raise SystemExit(f"❌ '{args.title}' is not on the list.")
    data["shows"].remove(show)
    save_data(data)
    print(f"🗑️  Removed {show['title']}")


def cmd_list(args):
    data = load_data()
    shows = data["shows"]
    if args.status:
        shows = [s for s in shows if s["status"] == args.status]

    if args.sort == "rating":
        shows = sorted(shows, key=lambda s: average(s) or -1, reverse=True)
    elif args.sort == "spread":
        shows = sorted(shows, key=lambda s: spread(s) or -1, reverse=True)
    elif args.sort == "year":
        shows = sorted(shows, key=lambda s: (s.get("tmdb") or {}).get("year") or 0)
    else:
        shows = sorted(shows, key=lambda s: s["title"].lower())

    if not shows:
        print("Nothing on the list yet. Add one with:")
        print('  python scripts/watchlist.py add "Show Name" --ratings a=9,b=8')
        return

    ids = viewer_ids(data)
    header = f"{'Title':<38} {'Yr':<5}"
    for vid in ids:
        header += f"{viewer_name(data, vid)[:5]:>6}"
    header += f"{'Avg':>6}  Verdict"
    print(header)
    print("─" * len(header))

    for show in shows:
        year = (show.get("tmdb") or {}).get("year") or "—"
        row = f"{show['title'][:37]:<38} {str(year):<5}"
        for vid in ids:
            score = show["ratings"].get(vid)
            row += f"{(score if score is not None else '—'):>6}"
        avg = average(show)
        row += f"{(avg if avg is not None else '—'):>6}  {verdict(show)}"
        print(row)

    print(f"\n{len(shows)} show(s)")


def cmd_enrich(args):
    """Fill in year/genres/network/episodes/poster from TMDB."""
    key = tmdb_key()
    data = load_data()
    targets = [s for s in data["shows"] if args.force or not s.get("tmdb")]

    if not targets:
        print("✅ Everything is already enriched. Use --force to refresh.")
        return

    print(f"🔍 Looking up {len(targets)} show(s) on TMDB\n")
    found, missed = 0, []

    for show in targets:
        query = show["title"]
        results = tmdb_get("/search/tv", key, query=query)
        hits = (results or {}).get("results") or []
        if not hits:
            print(f"  ❌ no match: {query}")
            missed.append(query)
            continue

        details = tmdb_details(hits[0]["id"], key)
        if not details:
            missed.append(query)
            continue

        show["tmdb"] = details
        found += 1
        genres = ", ".join(details["genres"]) or "—"
        print(f"  ✅ {details['name']} ({details['year']}) | {genres} | {details['episodes']} eps")
        save_data(data)

    print(f"\n✅ Enriched {found} show(s)")
    if missed:
        print(f"⚠️  No match for: {', '.join(missed)}")
        print("   Fix the title spelling and re-run, or leave them manual.")


def cmd_stats(args):
    data = load_data()
    shows = data["shows"]
    if not shows:
        raise SystemExit("Nothing on the list yet.")

    ids = viewer_ids(data)
    rated = [s for s in shows if scores(s)]
    both = [s for s in shows if spread(s) is not None]

    def rule(label):
        print(f"\n{label}\n" + "─" * 52)

    print("═" * 52)
    print("  📺  WHAT WE'VE WATCHED")
    print("═" * 52)

    finished = [s for s in shows if s["status"] == "finished"]
    bailed = [s for s in shows if s["status"] == "abandoned"]
    watching = [s for s in shows if s["status"] == "watching"]
    total_eps = sum(episode_count(s) for s in shows)
    total_hours = sum(hours(s) for s in shows)

    print(f"  {len(shows)} shows · {len(finished)} finished · "
          f"{len(watching)} in progress · {len(bailed)} bailed on")
    if total_eps:
        print(f"  {total_eps} episodes · about {total_hours:,.0f} hours "
              f"({total_hours / 24:,.1f} days) together")

    # --- Whose taste runs hotter -------------------------------------
    rule("  TASTE PROFILE")
    for vid in ids:
        vals = [s["ratings"][vid] for s in shows
                if isinstance(s["ratings"].get(vid), (int, float))]
        if not vals:
            print(f"  {viewer_name(data, vid):<12} no ratings yet")
            continue
        print(f"  {viewer_name(data, vid):<12} avg {sum(vals) / len(vals):.2f} "
              f"across {len(vals)} shows (high {max(vals)}, low {min(vals)})")

    if both:
        avg_spread = sum(spread(s) for s in both) / len(both)
        agree = sum(1 for s in both if spread(s) <= 1)
        print(f"  {'Agreement':<12} within 1 point on {agree}/{len(both)} shows "
              f"(avg gap {avg_spread:.2f})")

    # --- The shows that actually worked ------------------------------
    rule("  BOTH OF YOU LOVED")
    mutual = sorted(
        [s for s in both if min(scores(s)) >= 8],
        key=lambda s: average(s), reverse=True,
    )
    if mutual:
        for show in mutual[:10]:
            genres = ", ".join(genres_of(show)[:2]) or "—"
            print(f"  {average(show):>5}  {show['title'][:32]:<33} {genres}")
    else:
        print("  Nothing you both scored 8+ yet.")

    # --- Where your tastes split -------------------------------------
    rule("  BIGGEST DISAGREEMENTS")
    splits = sorted([s for s in both if spread(s) >= 2],
                    key=lambda s: spread(s), reverse=True)
    if splits:
        for show in splits[:10]:
            detail = " vs ".join(
                f"{viewer_name(data, vid)} {show['ratings'][vid]}"
                for vid in ids if show["ratings"].get(vid) is not None
            )
            print(f"  {spread(show):>5}  {show['title'][:32]:<33} {detail}")
    else:
        print("  You two agree on everything so far.")

    # --- What the genres say -----------------------------------------
    buckets = {}
    for show in rated:
        for genre in genres_of(show):
            buckets.setdefault(genre, []).append(average(show))

    if buckets:
        rule("  GENRES, BEST TO WORST")
        ranked = sorted(
            ((g, sum(v) / len(v), len(v)) for g, v in buckets.items() if len(v) >= args.min_count),
            key=lambda row: row[1], reverse=True,
        )
        for genre, avg, count in ranked:
            bar = "█" * int(round(avg))
            noun = "show" if count == 1 else "shows"
            print(f"  {genre[:18]:<19} {avg:>5.2f}  {bar:<10} ({count} {noun})")
        if ranked:
            print(f"\n  → Lean into {ranked[0][0]}. Be wary of {ranked[-1][0]}.")
    else:
        rule("  GENRES")
        print("  Run `enrich` first to pull genres from TMDB.")

    if bailed:
        rule("  BAILED ON")
        for show in bailed:
            note = f" — {show['note']}" if show.get("note") else ""
            print(f"  {show['title'][:36]:<37}{note}")
    print()


def cmd_recommend(args):
    """Ask TMDB what pairs with the shows you both rated highly."""
    key = tmdb_key()
    data = load_data()

    seeds = [s for s in data["shows"]
             if (s.get("tmdb") or {}).get("id") and (average(s) or 0) >= args.threshold]
    if not seeds:
        raise SystemExit(
            f"❌ No enriched shows rated {args.threshold}+ to work from.\n"
            "   Run `enrich`, add some ratings, or lower --threshold."
        )

    watched_ids = {(s.get("tmdb") or {}).get("id") for s in data["shows"]}
    watched_titles = {slugify(s["title"]) for s in data["shows"]}
    pool = {}

    print(f"🎯 Building suggestions from {len(seeds)} show(s) you rated "
          f"{args.threshold}+\n")

    for seed in seeds:
        payload = tmdb_get(f"/tv/{seed['tmdb']['id']}/recommendations", key)
        for candidate in (payload or {}).get("results", [])[:12]:
            cid = candidate.get("id")
            if cid in watched_ids or slugify(candidate.get("name", "")) in watched_titles:
                continue
            entry = pool.setdefault(cid, {
                "name": candidate.get("name"),
                "year": (candidate.get("first_air_date") or "")[:4],
                "score": 0.0,
                "tmdbScore": round(candidate.get("vote_average") or 0, 1),
                "because": [],
            })
            # A show you rated 9 pulls harder than one you rated 7.
            entry["score"] += (average(seed) - 5)
            if len(entry["because"]) < 3:
                entry["because"].append(seed["title"])

    if not pool:
        raise SystemExit("❌ TMDB returned no suggestions. Try again later.")

    ranked = sorted(pool.values(), key=lambda e: (e["score"], e["tmdbScore"]), reverse=True)

    print(f"{'Suggestion':<36} {'Yr':<6}{'TMDB':>5}   Because you liked")
    print("─" * 88)
    for entry in ranked[:args.number]:
        because = ", ".join(entry["because"])
        print(f"{(entry['name'] or '?')[:35]:<36} {entry['year'] or '—':<6}"
              f"{entry['tmdbScore']:>5}   {because[:30]}")

    if args.save:
        DATA_DIR.mkdir(exist_ok=True)
        out = DATA_DIR / "recommendations.json"
        with out.open("w", encoding="utf-8") as f:
            json.dump({
                "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "threshold": args.threshold,
                "suggestions": ranked[:args.number],
            }, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print(f"\n💾 Saved to {out}")


def cmd_export(args):
    """Dump to CSV for a spreadsheet."""
    import csv

    data = load_data()
    ids = viewer_ids(data)
    columns = (["title", "year", "status"] + [viewer_name(data, v) for v in ids]
               + ["average", "spread", "verdict", "genres", "networks",
                  "episodes", "hours", "tags", "note"])

    writer = csv.writer(sys.stdout if args.output == "-" else open(args.output, "w", newline="", encoding="utf-8"))
    writer.writerow(columns)
    for show in sorted(data["shows"], key=lambda s: s["title"].lower()):
        tmdb = show.get("tmdb") or {}
        writer.writerow(
            [show["title"], tmdb.get("year") or "", show["status"]]
            + [show["ratings"].get(v, "") for v in ids]
            + [average(show) or "", spread(show) or "", verdict(show),
               "; ".join(tmdb.get("genres") or []),
               "; ".join(tmdb.get("networks") or []),
               tmdb.get("episodes") or "", hours(show) or "",
               "; ".join(show.get("tags") or []), show.get("note", "")]
        )
    if args.output != "-":
        print(f"✅ Wrote {args.output}")


def cmd_viewers(args):
    """Rename the two of you so the site and stats read properly."""
    data = load_data()
    for pair in args.names:
        if "=" not in pair:
            raise SystemExit(f"❌ Expected id=Name, got '{pair}'")
        vid, name = pair.split("=", 1)
        data["viewers"].setdefault(vid.strip(), {})["name"] = name.strip()
        print(f"✅ {vid.strip()} → {name.strip()}")
    save_data(data)


# ============================================================
# CLI
# ============================================================

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="A shared record of every show you've watched together.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_add = sub.add_parser("add", help="add one show")
    p_add.add_argument("title")
    p_add.add_argument("--ratings", nargs="+", metavar="ID=SCORE",
                       help="e.g. a=9 b=7")
    p_add.add_argument("--status", choices=STATUSES, default="finished")
    p_add.add_argument("--note", help="why you liked or hated it")
    p_add.add_argument("--tags", help="comma separated")
    p_add.add_argument("--started", help="YYYY-MM")
    p_add.add_argument("--finished", help="YYYY-MM")
    p_add.add_argument("--rewatched", action="store_true")
    p_add.set_defaults(func=cmd_add)

    p_import = sub.add_parser(
        "import", help="bulk add from a text file (one show per line)")
    p_import.add_argument("file", help="path, or - for stdin")
    p_import.set_defaults(func=cmd_import)

    p_rate = sub.add_parser("rate", help="score a show you've already added")
    p_rate.add_argument("title")
    p_rate.add_argument("ratings", nargs="+", metavar="ID=SCORE")
    p_rate.set_defaults(func=cmd_rate)

    p_set = sub.add_parser("set", help="edit a show's fields")
    p_set.add_argument("title")
    p_set.add_argument("--status", choices=STATUSES)
    p_set.add_argument("--note")
    p_set.add_argument("--tags")
    p_set.add_argument("--started")
    p_set.add_argument("--finished")
    p_set.add_argument("--rewatched", action="store_true")
    p_set.set_defaults(func=cmd_set)

    p_rm = sub.add_parser("rm", help="remove a show")
    p_rm.add_argument("title")
    p_rm.set_defaults(func=cmd_remove)

    p_list = sub.add_parser("list", help="print the whole list")
    p_list.add_argument("--sort", choices=("title", "rating", "spread", "year"),
                        default="title")
    p_list.add_argument("--status", choices=STATUSES)
    p_list.set_defaults(func=cmd_list)

    p_enrich = sub.add_parser("enrich", help="fill in metadata from TMDB")
    p_enrich.add_argument("--force", action="store_true",
                          help="refresh shows that already have metadata")
    p_enrich.set_defaults(func=cmd_enrich)

    p_stats = sub.add_parser("stats", help="what your ratings say about your taste")
    p_stats.add_argument("--min-count", type=int, default=2,
                         help="genres need this many shows to rank (default 2)")
    p_stats.set_defaults(func=cmd_stats)

    p_rec = sub.add_parser("recommend", help="what to watch next, from TMDB")
    p_rec.add_argument("-n", "--number", type=int, default=15)
    p_rec.add_argument("--threshold", type=float, default=7.5,
                       help="only build on shows averaging this or better")
    p_rec.add_argument("--save", action="store_true",
                       help="also write data/recommendations.json")
    p_rec.set_defaults(func=cmd_recommend)

    p_export = sub.add_parser("export", help="write CSV")
    p_export.add_argument("-o", "--output", default="-")
    p_export.set_defaults(func=cmd_export)

    p_viewers = sub.add_parser("viewers", help="set your display names")
    p_viewers.add_argument("names", nargs="+", metavar="ID=NAME")
    p_viewers.set_defaults(func=cmd_viewers)

    return parser


def main():
    args = build_parser().parse_args()
    try:
        args.func(args)
    except BrokenPipeError:
        # Piping into head/less closes the stream early; that is not an error.
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        sys.exit(0)
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
