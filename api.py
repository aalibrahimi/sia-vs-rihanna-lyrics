import csv
import math
from pathlib import Path
from statistics import mean, median, stdev

from fastapi import FastAPI
from scipy.stats import mannwhitneyu

"""
Read only API for the React frontend.

This file reads songs.csv and keywords.csv. It does not change either file,
does not read the lyrics folders, and does not use a Genius token.

Run via: uvicorn api:app --reload --port 8000
"""

ROOT = Path(__file__).resolve().parent
SONGS_CSV = ROOT / "songs.csv"
KEYWORDS_CSV = ROOT / "keywords.csv"
ARTISTS = ("Sia", "Rihanna")

MEASURES = [
    {
        "key": "ttr",
        "label": "Type-token ratio",
        "short": "TTR",
        "help": "Unique words divided by total words. Lower means less variety.",
        "core": True,
    },
    {
        "key": "mtld",
        "label": "MTLD",
        "short": "MTLD",
        "help": "A word variety measure that depends less on song length. Higher means more variety.",
        "core": False,
    },
    {
        "key": "pronoun_rate",
        "label": "Pronoun rate",
        "short": "Pronouns",
        "help": "First- and second-person pronouns per 1,000 words.",
        "core": True,
    },
    {
        "key": "repeated_line_share",
        "label": "Repeated line share",
        "short": "Repeats",
        "help": "Share of lines that exactly match another line in the same song.",
        "core": True,
    },
    {
        "key": "keyword_score",
        "label": "Keyword score",
        "short": "Keywords",
        "help": "Sia keywords minus Rihanna keywords per 1,000 words. Positive leans Sia.",
        "core": True,
    },
]

app = FastAPI(title="Sia vs Rihanna lyrics")


def read_rows(path):
    with path.open(newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def number(value):
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def load_songs():
    songs = []
    for index, row in enumerate(read_rows(SONGS_CSV)):
        song = {
            "id": index,
            "artist": row["artist"],
            "title": row["title"],
            "album": row["album"],
            "year": number(row["year"]),
            "writers": row["writers"],
            "tokens": number(row.get("tokens")),
            "held_out": row["split"] == "test",
        }
        for measure in MEASURES:
            song[measure["key"]] = number(row.get(measure["key"]))
        songs.append(song)
    return songs


def load_keywords():
    keywords = {artist: [] for artist in ARTISTS}
    if KEYWORDS_CSV.exists():
        for row in read_rows(KEYWORDS_CSV):
            keywords[row["artist"]].append({
                "word": row["word"],
                "g2": number(row["g2"]),
                "songs": number(row["songs"]),
                "category": row.get("category") or None,
            })
    return keywords


def describe(values):
    if len(values) < 2:
        return None
    return {
        "n": len(values),
        "mean": mean(values),
        "median": median(values),
        "sd": stdev(values),
    }


def distance(value, stats):
    if value is None or not stats["sd"]:
        return None
    return (value - stats["mean"]) / stats["sd"]


def summarize(corpus, diamonds):
    summary = []
    for measure in MEASURES:
        key = measure["key"]
        groups = {
            artist: [s[key] for s in corpus if s["artist"] == artist and s[key] is not None]
            for artist in ARTISTS
        }
        stats = {artist: describe(groups[artist]) for artist in ARTISTS}
        if not all(stats.values()):
            continue

        test = mannwhitneyu(groups["Sia"], groups["Rihanna"], alternative="two-sided")
        value = diamonds[key] if diamonds else None
        z_scores = {artist: distance(value, stats[artist]) for artist in ARTISTS}
        closer = None
        if None not in z_scores.values():
            closer = min(ARTISTS, key=lambda artist: abs(z_scores[artist]))

        summary.append({
            "key": key,
            "label": measure["label"],
            "short": measure["short"],
            "help": measure["help"],
            "core": measure["core"],
            "stats": stats,
            "u": number(test.statistic),
            "p": number(test.pvalue),
            "diamonds": value,
            "z": z_scores,
            "closer": closer,
        })
    return summary


@app.get("/api/data")
def get_data():
    keywords = load_keywords()
    if not SONGS_CSV.exists():
        return {
            "songs": [],
            "diamonds": None,
            "summary": [],
            "keywords": keywords,
            "warnings": ["songs.csv was not found. Run collect.py, analyze.py and measures.py."],
        }

    all_songs = load_songs()
    diamonds = next((song for song in all_songs if song["held_out"]), None)
    corpus = [song for song in all_songs if not song["held_out"]]
    summary = summarize(corpus, diamonds)

    found = {measure["key"] for measure in summary}
    missing = [m["label"] for m in MEASURES if m["core"] and m["key"] not in found]

    warnings = []
    if not diamonds:
        warnings.append('No test song was found in songs.csv, so the "Diamonds" comparison is hidden.')
    if missing:
        warnings.append(f"Missing {', '.join(missing)}. Run python measures.py, then reload.")
    if not any(keywords.values()):
        warnings.append("keywords.csv was not found. Run python measures.py, then reload.")

    return {
        "songs": corpus,
        "diamonds": diamonds,
        "summary": summary,
        "keywords": keywords,
        "warnings": warnings,
    }
