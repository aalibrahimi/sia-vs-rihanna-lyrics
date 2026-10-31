import csv
import os
import random
import re
import sys
import time
from datetime import date
from pathlib import Path

import lyricsgenius

SEED = 115
SONGS_PER_ALBUM = 5
TEST_SONG = "diamonds"
RAW_DIR = Path("lyrics/raw")
SONGS_CSV = Path("songs.csv")

ALBUMS = {
    "Sia": [
        ("Healing Is Difficult", 2001),
        ("Colour the Small One", 2004),
        ("Some People Have Real Problems", 2008),
        ("We Are Born", 2010),
        ("1000 Forms of Fear", 2014),
        ("This Is Acting", 2016),
        ("Music - Songs from and Inspired by the Motion Picture", 2021),
        ("Reasonable Woman", 2024),
    ],
    "Rihanna": [
        ("Music of the Sun", 2005),
        ("A Girl Like Me", 2006),
        ("Good Girl Gone Bad", 2007),
        ("Rated R", 2009),
        ("Loud", 2010),
        ("Talk That Talk", 2011),
        ("Unapologetic", 2012),
        ("ANTI", 2016),
    ],
}

ALBUM_IDS = {}

SKIP_TITLE = re.compile(
    r"\b(remix|mix|live|version|edit|acoustic|demo|instrumental|interlude|intro|outro|skit|"
    r"reprise|commentary|a cappella|acapella|karaoke|edition)\b",
    re.IGNORECASE,
)


def norm(text):
    text = text.lower().replace("’", "'").replace("&", "and")
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def slug(text):
    return norm(text).replace(" ", "-")


def connect():
    token = os.environ.get("GENIUS_ACCESS_TOKEN")
    if not token:
        sys.exit("Set GENIUS_ACCESS_TOKEN first. Get one at https://genius.com/api-clients")
    return lyricsgenius.Genius(
        token,
        timeout=20,
        retries=3,
        sleep_time=0.5,
        remove_section_headers=False,
        skip_non_songs=True,
        verbose=False,
    )


def album_hits(response):
    for section in response.get("sections", []):
        for hit in section.get("hits", []):
            yield hit.get("result", hit)


def find_album(genius, artist, name):
    if (artist, name) in ALBUM_IDS:
        return ALBUM_IDS[(artist, name)]
    response = genius.search_albums(f"{name} {artist}", per_page=20)
    candidates = [a for a in album_hits(response) if norm(a["artist"]["name"]) == norm(artist)]
    for album in candidates:
        if norm(album["name"]) == norm(name):
            return album["id"]
    for album in candidates:
        if norm(album["name"]).startswith(norm(name)):
            return album["id"]
    found = [a["name"] for a in candidates]
    sys.exit(f"Could not find {artist} - {name}. Genius returned {found}. Add the id to ALBUM_IDS.")


def album_songs(genius, album_id):
    songs = []
    page = 1
    while page:
        response = genius.album_tracks(album_id, per_page=50, page=page)
        songs.extend(track["song"] for track in response["tracks"])
        page = response.get("next_page")
    return songs


def song_details(genius, song_id):
    info = genius.song(song_id)["song"]
    writers = [w["name"] for w in info.get("writer_artists", [])]
    return info, writers


def is_lead(song, artist):
    return norm(song["primary_artist"]["name"]) == norm(artist)


def usable(song, artist):
    if not is_lead(song, artist):
        return False
    if SKIP_TITLE.search(song["title"]):
        return False
    if song.get("instrumental") or song.get("lyrics_state") != "complete":
        return False
    return True


def save_lyrics(artist, album, title, lyrics):
    folder = RAW_DIR / slug(artist)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{slug(album)}__{slug(title)}.txt"
    path.write_text(lyrics, encoding="utf-8")
    return path


def collect_song(genius, artist, album, year, song, split, writers=None, info=None):
    if info is None:
        info, writers = song_details(genius, song["id"])
    lyrics = genius.lyrics(song_url=info["url"])
    if not lyrics:
        return None
    path = save_lyrics(artist, album, info["title"], lyrics)
    return {
        "artist": artist,
        "title": info["title"],
        "album": album,
        "year": year,
        "writers": "; ".join(writers),
        "url": info["url"],
        "accessed": date.today().isoformat(),
        "split": split,
        "raw_file": str(path),
    }


def collect_album(genius, rng, artist, album, year):
    album_id = find_album(genius, artist, album)
    songs = [s for s in album_songs(genius, album_id) if usable(s, artist)]
    rows = []
    pool = []
    for song in songs:
        info, writers = song_details(genius, song["id"])
        if artist == "Rihanna" and norm(info["title"]) == TEST_SONG:
            row = collect_song(genius, artist, album, year, song, "test", writers, info)
            if row:
                rows.append(row)
            continue
        if artist == "Rihanna" and any(norm(w) == "sia" for w in writers):
            print(f"  dropping {info['title']} (Sia writing credit)")
            continue
        pool.append((song, info, writers))
    rng.shuffle(pool)
    kept = 0
    for song, info, writers in pool:
        if kept == SONGS_PER_ALBUM:
            break
        row = collect_song(genius, artist, album, year, song, "train", writers, info)
        if row:
            rows.append(row)
            kept += 1
    if kept < SONGS_PER_ALBUM:
        print(f"  only {kept} usable songs on {album}")
    return rows


def main():
    genius = connect()
    rows = []
    for artist, albums in ALBUMS.items():
        for album, year in albums:
            print(f"{artist} - {album}")
            rng = random.Random(f"{SEED}-{artist}-{album}")
            rows.extend(collect_album(genius, rng, artist, album, year))
            time.sleep(1)
    with SONGS_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    train = [r for r in rows if r["split"] == "train"]
    for artist in ALBUMS:
        print(f"{artist}: {sum(r['artist'] == artist for r in train)} songs")
    print(f"test songs: {[r['title'] for r in rows if r['split'] == 'test']}")


if __name__ == "__main__":
    main()
