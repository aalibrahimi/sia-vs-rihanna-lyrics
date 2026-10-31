import csv
import re
from pathlib import Path

from nltk.tokenize import RegexpTokenizer

SONGS_CSV = Path("songs.csv")
CLEAN_DIR = Path("lyrics/clean")
CHECK_FILE = Path("cleaning_check.csv")

TOKENIZER = RegexpTokenizer(r"[a-z0-9]+(?:'[a-z]+)*")

VOCABLE = re.compile(
    r"^(o+h*|o+w+|a+h+|e+h+|u+h+|n+a+|l+a+|d+a+|m+h*m+|h+m+|w+h*o+a+h*|w+o+a+h+|a+y+|y+e+a+h+)$"
)

JUNK_LINES = [
    re.compile(r"^\d*\s*Contributors?.*$", re.IGNORECASE),
    re.compile(r"^You might also like.*$", re.IGNORECASE),
    re.compile(r"^See .+ LiveGet tickets as low as \$\d+.*$", re.IGNORECASE),
    re.compile(r"^Translations?\b.*$", re.IGNORECASE),
]

HEADER = re.compile(r"^\[(.+)\]$")


def strip_genius_extras(text):
    text = text.replace("\r\n", "\n").strip()
    lines = text.split("\n")
    if lines and re.search(r"Contributors|Lyrics(\[|$)", lines[0]):
        lines[0] = lines[0].split("Lyrics", 1)[1] if "Lyrics" in lines[0] else ""
    if lines:
        lines[-1] = re.sub(r"\d*\s*Embed$", "", lines[-1])
    lines = [re.sub(r"You might also like(?=\[)", "", line) for line in lines]
    return [line for line in lines if not any(p.match(line.strip()) for p in JUNK_LINES)]


def section_singers(header):
    if ":" not in header:
        return None
    names = header.split(":", 1)[1]
    return [n.strip().lower() for n in re.split(r",|&|\band\b|\+|/", names) if n.strip()]


def keep_section(header, artist):
    singers = section_singers(header)
    if singers is None:
        return True
    return any(artist.lower() in name for name in singers)


def drop_guest_sections(lines, artist):
    kept = []
    keep = True
    for line in lines:
        match = HEADER.match(line.strip())
        if match:
            keep = keep_section(match.group(1), artist)
            continue
        if keep:
            kept.append(line)
    return kept


def normalize_line(line):
    line = line.lower()
    line = line.replace("’", "'").replace("‘", "'").replace("`", "'")
    line = line.replace("“", '"').replace("”", '"')
    line = re.sub(r"\(([^)]*)\)", r" \1 ", line)
    line = re.sub(r"[^\w\s']", " ", line)
    line = re.sub(r"(?<![a-z])'|'(?![a-z])", " ", line)
    return re.sub(r"\s+", " ", line).strip()


def is_vocable(token):
    return bool(VOCABLE.match(token))


def clean_song(raw_text, artist):
    lines = strip_genius_extras(raw_text)
    lines = drop_guest_sections(lines, artist)
    lines = [normalize_line(line) for line in lines]
    lines = [line for line in lines if line]
    tokens = [t for line in lines for t in TOKENIZER.tokenize(line)]
    words = [t for t in tokens if not is_vocable(t)]
    return lines, tokens, words


def raw_lyric_lines(raw_text):
    lines = strip_genius_extras(raw_text)
    return [l for l in lines if l.strip() and not HEADER.match(l.strip())]


def load_songs(path=SONGS_CSV):
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def clean_all():
    songs = load_songs()
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    checks = []
    for song in songs:
        raw = Path(song["raw_file"]).read_text(encoding="utf-8")
        lines, tokens, words = clean_song(raw, song["artist"])
        clean_path = CLEAN_DIR / Path(song["raw_file"]).relative_to("lyrics/raw")
        clean_path.parent.mkdir(parents=True, exist_ok=True)
        clean_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        song["clean_file"] = str(clean_path)
        song["lines"] = len(lines)
        song["tokens"] = len(tokens)
        song["tokens_no_vocables"] = len(words)
        raw_count = len(raw_lyric_lines(raw))
        kept = len(lines) / raw_count if raw_count else 0
        checks.append({
            "artist": song["artist"],
            "title": song["title"],
            "raw_lines": raw_count,
            "clean_lines": len(lines),
            "share_kept": round(kept, 3),
            "look_at_this": "yes" if kept < 0.8 or len(tokens) < 50 else "",
        })
    with SONGS_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(songs[0].keys()))
        writer.writeheader()
        writer.writerows(songs)
    with CHECK_FILE.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(checks[0].keys()))
        writer.writeheader()
        writer.writerows(checks)
    for artist in sorted({s["artist"] for s in songs}):
        train = [s for s in songs if s["artist"] == artist and s["split"] == "train"]
        total = sum(s["tokens"] for s in train)
        print(f"{artist}: {len(train)} songs, {total} tokens")
    flagged = [c for c in checks if c["look_at_this"]]
    print(f"{len(flagged)} songs flagged in {CHECK_FILE}")


if __name__ == "__main__":
    clean_all()
