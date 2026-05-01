import streamlit as st
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
# GENRE NORMALISATIE
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
# GENRES
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
# UI TITLE
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
# CACHE RESET
# =========================================================
with st.expander("Onderhoud", expanded=False):
    if st.button("Cache reset"):
        st.cache_data.clear()
        st.rerun()

# =========================================================
# SEARCH UI
# =========================================================
all_series_names = load_all_series_names()

zoekterm = st.text_input("Search series:")

gekozen_serie = None

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
                st.write("NCIS-test:", [n for n in all_series_names if "ncis" in n.lower()])
                st.write("Eerste 50:", all_series_names[:50])
        else:
            st.markdown(f"**{len(matches)} resultaten:**")

            for i, name in enumerate(matches[:20]):
                if st.button(name, key=f"serie_{i}_{name}"):
                    st.session_state["gekozen_serie"] = name
                    st.rerun()

if "gekozen_serie" in st.session_state:
    gekozen_serie = st.session_state["gekozen_serie"]

# =========================================================
# RESULTS
# =========================================================
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

                        for s in seasons:
                            icon = (
                                "✅" if s["completed"]
                                else "🔵" if s["watched"] > 0
                                else "⚪"
                            )

                            line = (
                                f"{icon} **S{s['season']:02d}** — "
                                f"{s['watched']} / {s['total']} afleveringen"
                            )

                            if s["left"] > 0:
                                line += f" — **{s['left']} over**"

                            st.markdown(line)

                    if row["PLOT"]:
                        st.markdown("**Plot:**")
                        st.write(row["PLOT"])

                    st.caption(f"Last updated: {row['UPDATED']}")
