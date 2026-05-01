import streamlit as st
from st_keyup import st_keyup

import sqlite3
import requests
import pandas as pd
import re
from datetime import datetime

# =========================================================
# CONFIG
# =========================================================
st.set_page_config(
    page_title="Series Progress",
    layout="centered"
)

DROPBOX_DB_URL = (
    "https://www.dropbox.com/scl/fi/o7buaqqcqycet7twqzd2l/"
    "Series_Trakt_DBase.db?rlkey=zq40pf1obor3pb7b70sw24mxl&raw=1"
)

LOCAL_DB = "Trakt_DBase.db"

TMDB_API_KEY = st.secrets["TMDB_API_KEY"]
TMDB_IMG_BASE = "https://image.tmdb.org/t/p/w300"

# =========================================================
# GENRES
# =========================================================
GENRE_CANONICAL = {
    "action": "Action",
    "adventure": "Adventure",
    "animation": "Animation",
    "children": "Children",
    "family": "Family",
    "drama": "Drama",
    "thriller": "Thriller",
    "suspense": "Suspense",
    "mystery": "Mystery",
    "crime": "Crime",
    "fantasy": "Fantasy",
    "horror": "Horror",
    "science-fiction": "Sci-Fi",
    "scifi": "Sci-Fi",
    "comedy": "Comedy",
    "romance": "Romance",
    "reality": "Reality",
    "documentary": "Documentary",
    "documentaire": "Documentary",
    "doctor": "Medical",
    "doctors": "Medical",
    "lawyers": "Legal",
    "cops": "Police",
    "fbi": "FBI",
    "cia": "CIA",
    "spy": "Spy",
    "marvel": "Marvel",
    "dc comics": "DC Comics",
    "star wars": "Star Wars",
    "star trek": "Star Trek",
    "superhero": "Superhero",
    "heroes": "Heroes",
    "vampires": "Vampires",
    "zombies": "Zombies",
    "monsters": "Monsters",
    "war": "War",
    "western": "Western",
    "sport": "Sport",
    "music": "Music",
    "history": "History",
    "holiday": "Holiday",
    "talk-show": "Talk Show",
    "game-show": "Game Show",
    "special-interest": "Special Interest",
}

GENRE_BLACKLIST = {
    "delete",
    "delete?",
    "delete!?",
    "selecteer genres...",
    ""
}

# =========================================================
# DOWNLOAD DB
# =========================================================
@st.cache_data(ttl=600)
def download_db():
    r = requests.get(DROPBOX_DB_URL, timeout=30)
    r.raise_for_status()

    with open(LOCAL_DB, "wb") as f:
        f.write(r.content)

    return LOCAL_DB

# =========================================================
# TMDB POSTER
# =========================================================
@st.cache_data(ttl=86400)
def get_tmdb_poster(tmdb_id):
    if not tmdb_id:
        return None

    try:
        r = requests.get(
            f"https://api.themoviedb.org/3/tv/{tmdb_id}",
            params={"api_key": TMDB_API_KEY},
            timeout=10
        )
        r.raise_for_status()

        data = r.json()
        poster_path = data.get("poster_path")

        if poster_path:
            return TMDB_IMG_BASE + poster_path

    except Exception:
        pass

    return None

# =========================================================
# PARSERS
# =========================================================
def parse_progress(progress):
    if not progress or str(progress).strip() == "#N/A":
        return {"season": None, "episode": None, "date": None}

    m = re.search(r"S(\d{2})E(\d{2})\s*←-→\s*(.+)", str(progress))

    if not m:
        return {"season": None, "episode": None, "date": None}

    return {
        "season": int(m.group(1)),
        "episode": int(m.group(2)),
        "date": m.group(3)
    }


def parse_season_episodes(value):
    watched = 0
    total = 0

    if not value or str(value).strip() == "#N/A":
        return watched, total, 0.0

    for part in str(value).split("§"):
        try:
            w, t = part.split("/")
            watched += int(w)
            total += int(t)
        except Exception:
            pass

    percent = round((watched / total) * 100, 1) if total > 0 else 0.0
    return watched, total, percent


def parse_seasons(value):
    seasons = []

    if not value or str(value).strip() == "#N/A":
        return seasons

    parts = str(value).split("§")

    for idx, part in enumerate(parts, start=1):
        try:
            watched, total = part.split("/")
            watched = int(watched)
            total = int(total)

            left = max(total - watched, 0)
            percent = round((watched / total) * 100, 1) if total > 0 else 0.0

            seasons.append({
                "season": idx,
                "watched": watched,
                "total": total,
                "left": left,
                "percent": percent,
                "completed": total > 0 and watched == total
            })

        except Exception:
            pass

    return seasons


def determine_status(watched, total):
    if total > 0 and watched == total:
        return "Completed"

    if watched > 0:
        return "Watching"

    return "Not started"


def parse_date(date_str):
    if not date_str:
        return None

    try:
        return datetime.strptime(str(date_str), "%d-%m-%Y %H:%M:%S")
    except Exception:
        return None

# =========================================================
# GENRE BADGES
# =========================================================
def normalize_genres(raw):
    if not raw:
        return []

    result = []

    for g in [x.strip() for x in str(raw).split(",")]:
        key = g.lower()

        if key in GENRE_BLACKLIST:
            continue

        canon = GENRE_CANONICAL.get(key, g.title())

        if canon not in result:
            result.append(canon)

    return result


def render_genre_badges(raw):
    genres = normalize_genres(raw)

    if not genres:
        return ""

    html = ""

    for g in genres:
        html += (
            '<span style="'
            'display:inline-block;'
            'background:#eef2f7;'
            'color:#333;'
            'padding:4px 10px;'
            'margin:2px 6px 2px 0;'
            'border-radius:12px;'
            'font-size:0.8rem;'
            'white-space:nowrap;'
            '">'
            f'{g}</span>'
        )

    return f'<div style="margin-top:6px;">{html}</div>'

# =========================================================
# SEASON BLOKJES
# =========================================================
def render_season_blocks(seasons):
    st.markdown(
        """
        <style>
        .season-line {
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 11px;
            flex-wrap: wrap;
        }

        .season-label {
            font-weight: 700;
            min-width: 43px;
            white-space: nowrap;
        }

        .episode-boxes {
            display: flex;
            flex-wrap: wrap;
            gap: 3px;
            max-width: 100%;
        }

        .episode-box {
            width: 12px;
            height: 12px;
            border-radius: 3px;
            display: inline-block;
        }

        .green {
            background-color: #2ecc71;
        }

        .red {
            background-color: #e74c3c;
        }

        .blue {
            background-color: #3498db;
        }

        .season-count {
            font-weight: 600;
            white-space: nowrap;
            font-size: 0.88rem;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    for s in seasons:
        episode_boxes = ""

        for ep in range(1, s["total"] + 1):
            if s["watched"] == 0:
                css_class = "blue"
            elif ep <= s["watched"]:
                css_class = "green"
            else:
                css_class = "red"

            episode_boxes += (
                f'<span class="episode-box {css_class}" '
                f'title="S{s["season"]:02d}E{ep:02d}"></span>'
            )

        html = f"""
        <div class="season-line">
            <div class="season-label">S{s["season"]:02d} -</div>
            <div class="episode-boxes">{episode_boxes}</div>
            <div class="season-count">{s["watched"]} / {s["total"]} afleveringen</div>
        </div>
        """

        st.markdown(html, unsafe_allow_html=True)

# =========================================================
# DATABASE
# =========================================================
@st.cache_data(ttl=600)
def load_all_series_names():
    conn = sqlite3.connect(download_db())

    df = pd.read_sql_query(
        """
        SELECT DISTINCT NAAM
        FROM tbl_Trakt
        WHERE NAAM IS NOT NULL
          AND TRIM(NAAM) <> ''
        ORDER BY NAAM
        """,
        conn
    )

    conn.close()

    names = []

    for name in df["NAAM"].tolist():
        if name:
            clean = str(name).strip()
            if clean:
                names.append(clean)

    return sorted(set(names), key=str.lower)


def search_series_exact(series_name):
    conn = sqlite3.connect(download_db())

    df = pd.read_sql_query(
        """
        SELECT
            NAAM,
            YEAR,
            PLOT,
            GENRE,
            TMDB_ID,
            PROGRESS,
            SEASONSEPISODES,
            UPDATED
        FROM tbl_Trakt
        WHERE TRIM(NAAM) = ?
        ORDER BY NAAM
        """,
        conn,
        params=(series_name.strip(),)
    )

    conn.close()
    return df

# =========================================================
# MAIN TITLE
# =========================================================
st.markdown(
    """
    <h1 style="margin-bottom:0.2em;">📺 Series Progress</h1>
    <p style="color:#666; margin-top:0;">
        Track what you're watching, what's next, and what's done.
    </p>
    """,
    unsafe_allow_html=True
)

# =========================================================
# SESSION STATE
# =========================================================
if "gekozen_serie" not in st.session_state:
    st.session_state["gekozen_serie"] = None

if "zoeken_actief" not in st.session_state:
    st.session_state["zoeken_actief"] = True

# =========================================================
# ONDERHOUD
# =========================================================
with st.expander("Onderhoud", expanded=False):
    if st.button("Cache reset", use_container_width=True):
        st.cache_data.clear()
        st.session_state.clear()
        st.rerun()

# =========================================================
# SEARCH UI - MOBIEL
# =========================================================
all_series_names = load_all_series_names()

if st.session_state["gekozen_serie"] and not st.session_state["zoeken_actief"]:
    col_a, col_b = st.columns([2, 1])

    with col_a:
        st.success(f"Gekozen: {st.session_state['gekozen_serie']}")

    with col_b:
        if st.button("Andere zoeken", use_container_width=True):
            st.session_state["zoeken_actief"] = True
            st.rerun()

if st.session_state["zoeken_actief"]:
    zoekterm = st_keyup(
        "Search series:",
        debounce=150,
        key="live_search"
    )

    if zoekterm:
        term = zoekterm.strip().lower()

        if len(term) < 3:
            st.info("Typ minstens 3 karakters...")
        else:
            matches = [
                name
                for name in all_series_names
                if term in name.lower()
            ]

            if not matches:
                st.warning("Geen series gevonden.")

                with st.expander("Debug"):
                    st.write("Zoekterm:", term)
                    st.write("Aantal geladen serienamen:", len(all_series_names))
                    st.write(
                        "NCIS-test:",
                        [n for n in all_series_names if "ncis" in n.lower()]
                    )
                    st.write("Eerste 50:", all_series_names[:50])

            else:
                st.caption(f"{len(matches)} resultaten gevonden")

                with st.expander(f"Alle {len(matches)} resultaten tonen", expanded=True):
                    for i, name in enumerate(matches):
                        if st.button(name, key=f"serie_{i}_{name}", use_container_width=True):
                            st.session_state["gekozen_serie"] = name
                            st.session_state["zoeken_actief"] = False
                            st.rerun()

gekozen_serie = st.session_state.get("gekozen_serie")

# =========================================================
# RESULTS
# =========================================================
if not gekozen_serie:
    st.info("Typ minstens 3 letters en kies een serie.")

if gekozen_serie:
    df = search_series_exact(gekozen_serie)

    if df.empty:
        st.warning("Geen gegevens gevonden voor deze serie.")
    else:
        for _, row in df.iterrows():
            watched, total, percent = parse_season_episodes(row["SEASONSEPISODES"])
            status = determine_status(watched, total)
            episodes_left = max(total - watched, 0)

            prog = parse_progress(row["PROGRESS"])
            last_seen_dt = parse_date(prog["date"])
            poster_url = get_tmdb_poster(row["TMDB_ID"])

            with st.container(border=True):
                col1, col2 = st.columns([1, 2])

                with col1:
                    if poster_url:
                        st.image(poster_url, use_container_width=True)

                with col2:
                    st.subheader(f"{row['NAAM']} ({row['YEAR']})")

                    st.markdown(
                        "🟢 **Completed**" if status == "Completed"
                        else "🔵 **Watching**" if status == "Watching"
                        else "⚪ **Not started**"
                    )

                    if status == "Watching" and prog["season"] is not None:
                        seen = (
                            last_seen_dt.strftime("%d-%m-%Y %H:%M")
                            if last_seen_dt else prog["date"]
                        )

                        st.markdown(
                            f"👁️ **Laatst gezien:** "
                            f"S{prog['season']:02d}E{prog['episode']:02d} · {seen}"
                        )

                    status_line = (
                        f"⏳ **{episodes_left} left** &nbsp;&nbsp; "
                        f"📊 **{watched} / {total} ({percent}%)**"
                    )

                    st.markdown(status_line, unsafe_allow_html=True)
                    st.progress(percent / 100)

                with st.expander("Details", expanded=True):
                    st.markdown(
                        render_genre_badges(row["GENRE"]),
                        unsafe_allow_html=True
                    )

                    seasons = parse_seasons(row["SEASONSEPISODES"])

                    if seasons:
                        st.markdown("### Seizoenen")
                        render_season_blocks(seasons)

                    if row["PLOT"]:
                        st.markdown("**Plot:**")
                        st.write(row["PLOT"])

                    st.caption(f"Last updated: {row['UPDATED']}")
