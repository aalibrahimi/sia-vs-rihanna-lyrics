import csv
import math
import re
import sys
from collections import Counter
from pathlib import Path

from analyze import SONGS_CSV, TOKENIZER, is_vocable, load_songs

KEYWORDS_CSV = Path("keywords.csv")
ARTISTS = ("Sia", "Rihanna")
MIN_SONGS = 5
TOP_KEYWORDS = 50
MTLD_THRESHOLD = 0.72

PRONOUNS = {
    "i", "me", "my", "mine", "myself",
    "we", "us", "our", "ours",
    "you", "your", "yours", "yourself", "ya",
}
PRONOUN_CONTRACTION = re.compile(r"^(i|we|you|ya)'[a-z]+$")

KEYWORD_FIELDS = [
    "artist", "word", "g2", "songs", "sia_count", "rihanna_count", "category",
]


def read_song(song):
    path = Path(song["clean_file"].replace("\\", "/"))
    text = path.read_text(encoding="utf-8")
    lines = [line for line in text.splitlines() if line.strip()]
    tokens = [token for line in lines for token in TOKENIZER.tokenize(line)]
    words = [token for token in tokens if not is_vocable(token)]
    return lines, words


def type_token_ratio(words):
    return len(set(words)) / len(words) if words else None


def factor_count(words):
    factors = 0.0
    seen = set()
    length = 0
    for word in words:
        seen.add(word)
        length += 1
        if len(seen) / length < MTLD_THRESHOLD:
            factors += 1
            seen = set()
            length = 0
    if length:
        factors += (1 - len(seen) / length) / (1 - MTLD_THRESHOLD)
    return factors


def mtld(words):
    factors = (factor_count(words) + factor_count(words[::-1])) / 2
    return len(words) / factors if factors else None


def pronoun_rate(words):
    if not words:
        return None
    count = sum(
        word in PRONOUNS or bool(PRONOUN_CONTRACTION.match(word))
        for word in words
    )
    return count / len(words) * 1000


def repeated_line_share(lines):
    if not lines:
        return None
    counts = Counter(lines)
    repeated = sum(count for count in counts.values() if count >= 2)
    return repeated / len(lines)


def log_likelihood(count_a, count_b, size_a, size_b):
    total = count_a + count_b
    expected_a = size_a * total / (size_a + size_b)
    expected_b = size_b * total / (size_a + size_b)
    score = 0.0
    if count_a:
        score += count_a * math.log(count_a / expected_a)
    if count_b:
        score += count_b * math.log(count_b / expected_b)
    return 2 * score


def saved_categories():
    if not KEYWORDS_CSV.exists():
        return {}
    with KEYWORDS_CSV.open(newline="", encoding="utf-8") as file:
        return {
            (row["artist"], row["word"]): row.get("category", "")
            for row in csv.DictReader(file)
        }


def build_keywords(songs, parsed):
    frequency = {artist: Counter() for artist in ARTISTS}
    song_counts = {artist: Counter() for artist in ARTISTS}

    for song, (_, words) in zip(songs, parsed):
        if song["split"] == "train":
            frequency[song["artist"]].update(words)
            song_counts[song["artist"]].update(set(words))

    sizes = {artist: sum(frequency[artist].values()) for artist in ARTISTS}
    if not all(sizes.values()):
        sys.exit("Both artists need training songs before keywords can be calculated.")

    categories = saved_categories()
    keywords = []

    for artist, other in zip(ARTISTS, ARTISTS[::-1]):
        rows = []
        for word, count in frequency[artist].items():
            other_count = frequency[other][word]
            if song_counts[artist][word] < MIN_SONGS:
                continue
            if count / sizes[artist] <= other_count / sizes[other]:
                continue
            rows.append({
                "artist": artist,
                "word": word,
                "g2": round(log_likelihood(count, other_count, sizes[artist], sizes[other]), 3),
                "songs": song_counts[artist][word],
                "sia_count": frequency["Sia"][word],
                "rihanna_count": frequency["Rihanna"][word],
                "category": categories.get((artist, word), ""),
            })
        rows.sort(key=lambda row: row["g2"], reverse=True)
        keywords.extend(rows[:TOP_KEYWORDS])

    return keywords


def keyword_score(words, keyword_sets):
    if not words:
        return None
    sia = sum(word in keyword_sets["Sia"] for word in words)
    rihanna = sum(word in keyword_sets["Rihanna"] for word in words)
    return (sia - rihanna) / len(words) * 1000


def rounded(value):
    return "" if value is None else round(value, 4)


def write_csv(path, rows, fieldnames):
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
  """
  Calculate the per-song measures from section 3.4 of the project update.
  
  Runs after analysis ( analyze.py ). This adds the measures to songs.csv and writes keywords.csv. It reuses the tokenizer and vocable rule from analyze.py without changing that file.
  """
    if not SONGS_CSV.exists():
        sys.exit("songs.csv was not found. Run collect.py and analyze.py first.")

    songs = load_songs()
    if not songs or "clean_file" not in songs[0]:
        sys.exit("songs.csv has no cleaned files listed. Run analyze.py first.")

    parsed = [read_song(song) for song in songs]
    keywords = build_keywords(songs, parsed)
    keyword_sets = {
        artist: {row["word"] for row in keywords if row["artist"] == artist}
        for artist in ARTISTS
    }

    for song, (lines, words) in zip(songs, parsed):
        song["ttr"] = rounded(type_token_ratio(words))
        song["mtld"] = rounded(mtld(words))
        song["pronoun_rate"] = rounded(pronoun_rate(words))
        song["repeated_line_share"] = rounded(repeated_line_share(lines))
        song["keyword_score"] = rounded(keyword_score(words, keyword_sets))

    write_csv(SONGS_CSV, songs, list(songs[0].keys()))
    write_csv(KEYWORDS_CSV, keywords, KEYWORD_FIELDS)

    for artist in ARTISTS:
        print(f"{artist}: {len(keyword_sets[artist])} keywords")
    print(f"Updated {SONGS_CSV} and wrote {KEYWORDS_CSV}")


if __name__ == "__main__":
    main()
