import { useEffect, useMemo, useState } from "react";

const ARTISTS = ["Sia", "Rihanna"];
const WIDTH = 920;
const HEIGHT = 310;
const LEFT = 92;
const RIGHT = 28;
const AXIS_Y = 278;
const LANES = { Sia: 105, Rihanna: 215 };

const fmt = (value) => {
  if (value == null) return "–";
  const size = Math.abs(value);
  return value.toFixed(size >= 100 ? 1 : size >= 10 ? 2 : 3);
};

const fmtP = (p) => {
  if (p == null) return "–";
  return p < 0.001 ? "< .001" : p.toFixed(3).replace(/^0/, "");
};

const jitter = (id) => (((id * 37) % 11) - 5) * 7;
const groupOf = (song) => (song.held_out ? "Held out" : song.artist);

function compareValues(a, b) {
  if (typeof a === "number" && typeof b === "number") return a - b;
  return String(a ?? "").localeCompare(String(b ?? ""));
}

function StripPlot({ songs, diamonds, measure, selectedId, onSelect }) {
  const { key, stats } = measure;
  const plotted = songs.filter((song) => song[key] != null);
  const gem = diamonds?.[key] ?? null;
  const values = plotted.map((song) => song[key]);
  if (gem != null) values.push(gem);
  if (!values.length) return <p>No values to plot for this measure.</p>;

  const low = Math.min(...values);
  const high = Math.max(...values);
  const pad = (high - low) * 0.06 || 1;
  const x = (value) =>
    LEFT + ((value - low + pad) / (high - low + 2 * pad)) * (WIDTH - LEFT - RIGHT);
  const ticks = Array.from({ length: 5 }, (_, i) => low + ((high - low) * i) / 4);
  const gemX = gem == null ? null : x(gem);

  return (
    <div className="plot">
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        role="img"
        aria-label={`${measure.label} for every song, grouped by artist`}
      >
        {ARTISTS.map((artist) => (
          <g key={artist}>
            <text className={`lane ${artist.toLowerCase()}`} x="0" y={LANES[artist] + 6}>
              {artist}
            </text>
            <line
              className={`mean ${artist.toLowerCase()}`}
              x1={x(stats[artist].mean)}
              x2={x(stats[artist].mean)}
              y1={LANES[artist] - 42}
              y2={LANES[artist] + 42}
            />
            <text
              className="mean-label"
              x={x(stats[artist].mean)}
              y={LANES[artist] - 48}
              textAnchor="middle"
            >
              mean {fmt(stats[artist].mean)}
            </text>
          </g>
        ))}

        {plotted.map((song) => (
          <circle
            key={song.id}
            className={`dot ${song.artist.toLowerCase()} ${
              song.id === selectedId ? "selected" : ""
            }`}
            cx={x(song[key])}
            cy={LANES[song.artist] + jitter(song.id)}
            r={song.id === selectedId ? 10 : 7}
            onClick={() => onSelect(song.id)}
          >
            <title>{`${song.title}: ${fmt(song[key])}`}</title>
          </circle>
        ))}

        {gem != null && (
          <g>
            <line className="gem-line" x1={gemX} x2={gemX} y1="46" y2={AXIS_Y} />
            <path
              className="gem"
              d={`M${gemX} 20 L${gemX + 13} 33 L${gemX} 46 L${gemX - 13} 33 Z`}
              onClick={() => onSelect(diamonds.id)}
            >
              <title>{`Diamonds: ${fmt(gem)}`}</title>
            </path>
            <text
              className="gem-label"
              x={gemX}
              y="13"
              textAnchor={gemX > WIDTH - 130 ? "end" : "middle"}
            >
              “Diamonds” {fmt(gem)}
            </text>
          </g>
        )}

        <line className="axis" x1={LEFT} x2={WIDTH - RIGHT} y1={AXIS_Y} y2={AXIS_Y} />
        {ticks.map((tick, index) => (
          <text key={index} className="tick" x={x(tick)} y={AXIS_Y + 22} textAnchor="middle">
            {fmt(tick)}
          </text>
        ))}
      </svg>
    </div>
  );
}

function MeasuresTable({ summary }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Measure</th>
            <th className="num">Sia mean (SD)</th>
            <th className="num">Rihanna mean (SD)</th>
            <th className="num">U</th>
            <th className="num">p</th>
            <th className="num">“Diamonds”</th>
            <th className="num">SDs from Sia</th>
            <th className="num">SDs from Rihanna</th>
            <th>Closer to</th>
          </tr>
        </thead>
        <tbody>
          {summary.map((measure) => (
            <tr key={measure.key}>
              <th scope="row">{measure.label}</th>
              {ARTISTS.map((artist) => (
                <td key={artist} className="num">
                  {fmt(measure.stats[artist].mean)} ({fmt(measure.stats[artist].sd)})
                </td>
              ))}
              <td className="num">{fmt(measure.u)}</td>
              <td className="num">{fmtP(measure.p)}</td>
              <td className="num">{fmt(measure.diamonds)}</td>
              <td className="num">{fmt(measure.z.Sia)}</td>
              <td className="num">{fmt(measure.z.Rihanna)}</td>
              <td>{measure.closer ?? "–"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Keywords({ keywords }) {
  const [category, setCategory] = useState("All");
  const categories = [
    ...new Set(
      Object.values(keywords)
        .flat()
        .map((item) => item.category)
        .filter(Boolean)
    ),
  ].sort();

  return (
    <>
      {categories.length > 0 && (
        <label className="control">
          Category
          <select value={category} onChange={(event) => setCategory(event.target.value)}>
            <option>All</option>
            {categories.map((name) => (
              <option key={name}>{name}</option>
            ))}
          </select>
        </label>
      )}
      <div className="keyword-columns">
        {ARTISTS.map((artist) => {
          const all = keywords[artist] ?? [];
          const shown = all.filter((item) => category === "All" || item.category === category);
          const largest = Math.max(...all.map((item) => item.g2 ?? 0), 1);

          return (
            <section key={artist}>
              <h3 className={artist.toLowerCase()}>{artist}</h3>
              {shown.length === 0 ? (
                <p className="note">No keywords to show.</p>
              ) : (
                <ol className="keywords">
                  {shown.map((item) => (
                    <li key={item.word}>
                      <span>{item.word}</span>
                      <span className="track">
                        <span
                          className={`bar ${artist.toLowerCase()}`}
                          style={{ width: `${((item.g2 ?? 0) / largest) * 100}%` }}
                        />
                      </span>
                      <span className="num">{fmt(item.g2)}</span>
                      <span className="num note">
                        {item.songs == null ? "" : `${item.songs} songs`}
                      </span>
                    </li>
                  ))}
                </ol>
              )}
            </section>
          );
        })}
      </div>
    </>
  );
}

function SongTable({ songs, summary, selectedId, onSelect }) {
  const [query, setQuery] = useState("");
  const [group, setGroup] = useState("All");
  const [sort, setSort] = useState({ key: "title", direction: 1 });

  const columns = [
    { key: "title", label: "Song" },
    { key: "artist", label: "Group" },
    { key: "album", label: "Album" },
    { key: "year", label: "Year", numeric: true },
    { key: "tokens", label: "Tokens", numeric: true },
    ...summary.map((measure) => ({ key: measure.key, label: measure.short, numeric: true })),
  ];

  const rows = useMemo(() => {
    const value = (song, key) => (key === "artist" ? groupOf(song) : song[key]);
    const text = query.trim().toLowerCase();

    return songs
      .filter((song) => group === "All" || groupOf(song) === group)
      .filter((song) =>
        `${song.title ?? ""} ${song.album ?? ""} ${song.writers ?? ""}`
          .toLowerCase()
          .includes(text)
      )
      .sort((a, b) => compareValues(value(a, sort.key), value(b, sort.key)) * sort.direction);
  }, [songs, query, group, sort]);

  const changeSort = (key) =>
    setSort((current) => ({
      key,
      direction: current.key === key ? -current.direction : 1,
    }));

  return (
    <>
      <div className="controls">
        <label className="control">
          Search
          <input
            type="search"
            value={query}
            placeholder="Song, album or writer"
            onChange={(event) => setQuery(event.target.value)}
          />
        </label>
        <label className="control">
          Group
          <select value={group} onChange={(event) => setGroup(event.target.value)}>
            <option>All</option>
            <option>Sia</option>
            <option>Rihanna</option>
            <option>Held out</option>
          </select>
        </label>
        <span className="note">Showing {rows.length} of {songs.length}</span>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              {columns.map((column) => (
                <th
                  key={column.key}
                  className={column.numeric ? "num" : ""}
                  aria-sort={
                    sort.key === column.key
                      ? sort.direction === 1
                        ? "ascending"
                        : "descending"
                      : "none"
                  }
                >
                  <button className="sort" onClick={() => changeSort(column.key)}>
                    {column.label}
                    {sort.key === column.key ? (sort.direction === 1 ? " ↑" : " ↓") : ""}
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((song) => (
              <tr
                key={song.id}
                className={song.id === selectedId ? "selected-row" : ""}
                onClick={() => onSelect(song.id)}
              >
                <td>
                  <button className="song">{song.title ?? "Untitled"}</button>
                </td>
                <td>{groupOf(song)}</td>
                <td>{song.album ?? "–"}</td>
                <td className="num">{song.year ?? "–"}</td>
                <td className="num">{song.tokens ?? "–"}</td>
                {summary.map((measure) => (
                  <td key={measure.key} className="num">
                    {fmt(song[measure.key])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

export default function App() {
  const [data, setData] = useState(null);
  const [failed, setFailed] = useState(false);
  const [measureKey, setMeasureKey] = useState(null);
  const [selectedId, setSelectedId] = useState(null);

  useEffect(() => {
    fetch("/api/data")
      .then((response) => {
        if (!response.ok) throw new Error("Request failed");
        return response.json();
      })
      .then(setData)
      .catch(() => setFailed(true));
  }, []);

  if (failed) {
    return (
      <main>
        <h1>The Python API is not responding</h1>
        <p className="lede">
          From the repo root, run <code>uvicorn api:app --reload --port 8000</code>, then
          reload this page.
        </p>
      </main>
    );
  }

  if (!data) return <main><p className="lede">Loading the analysis…</p></main>;

  const { songs, diamonds, summary, keywords, warnings } = data;
  const allSongs = diamonds ? [...songs, diamonds] : songs;
  const measure = summary.find((item) => item.key === measureKey) ?? summary[0];
  const selected = allSongs.find((song) => song.id === selectedId);
  const core = summary.filter((item) => item.core && item.closer);
  const nearSia = core.filter((item) => item.closer === "Sia").length;
  const counts = ARTISTS.map(
    (artist) => `${songs.filter((song) => song.artist === artist).length} ${artist}`
  ).join(" and ");

  return (
    <main>
      <header className="hero">
        <h1>Does Sia write differently from Rihanna?</h1>
        <p className="lede">
          {core.length > 0
            ? `“Diamonds”, co-written by Sia and sung by Rihanna, sits closer to Sia on ${nearSia} of ${core.length} measures. We predicted all four.`
            : "Compare both collections across the measures from our keyness study."}
        </p>
        <p className="note">
          Based on {counts} songs. This is an exploratory comparison of two collections, not
          proof of a writing fingerprint.
        </p>
      </header>

      {warnings.length > 0 && (
        <ul className="warnings">
          {warnings.map((warning) => (
            <li key={warning}>{warning}</li>
          ))}
        </ul>
      )}

      {measure && (
        <section>
          <div className="tabs" aria-label="Choose a measure">
            {summary.map((item) => (
              <button
                key={item.key}
                aria-pressed={item.key === measure.key}
                onClick={() => setMeasureKey(item.key)}
              >
                {item.label}
              </button>
            ))}
          </div>
          <p className="help">{measure.help}</p>
          <StripPlot
            songs={songs}
            diamonds={diamonds}
            measure={measure}
            selectedId={selectedId}
            onSelect={setSelectedId}
          />
          <p className="readout" aria-live="polite">
            {selected
              ? `${selected.title ?? "Untitled"}${selected.album ? `, ${selected.album}` : ""}${
                  selected.year ? ` (${selected.year})` : ""
                }: ${fmt(selected[measure.key])}.${
                  selected.writers ? ` Written by ${selected.writers}.` : ""
                }`
              : "Select a dot or a song to see its details."}
          </p>
        </section>
      )}

      {summary.length > 0 && (
        <section>
          <h2>All measures</h2>
          <MeasuresTable summary={summary} />
          <p className="note">
            Mann-Whitney U, two-sided. The keyword score p-value is descriptive because the
            keyword lists were built from these same songs. “Diamonds” was not used to build
            them.
          </p>
        </section>
      )}

      <section>
        <h2>Keywords</h2>
        <Keywords keywords={keywords} />
      </section>

      <section>
        <h2>Songs</h2>
        <SongTable
          songs={allSongs}
          summary={summary}
          selectedId={selectedId}
          onSelect={setSelectedId}
        />
      </section>
    </main>
  );
}
