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
    "https://www.dropbox.com/scl/fi/"
    "bjy95x305s1r2fvgiddcv/Trakt_DBase.db"
    "?rlkey=kxev7chehu2mnvmag0ojt9n4g&raw=1"
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
# DOWNLOAD DB (CACHED)
# =========================================================
@st.cache_data(ttl=600)
def download_db():
    r = requests.get(DROPBOX_DB_URL, timeout=30)
    r.raise_for_status()
    with open(LOCAL_DB, "wb") as f:
        f.write(r.content)
    return LOCAL_DB

# =========================================================
# TMDB POSTER (CACHED)
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
    if not progress or progress.strip() == "#N/A":
        return {"season": None, "episode": None, "date": None}

    m = re.search(r"S(\d{2})E(\d{2})\s*←-→\s*(.+)", progress)
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

    if not value or value.strip() == "#N/A":
        return watched, total, 0.0

    for part in value.split("§"):
        try:
            w, t = part.split("/")
            watched += int(w)
            total += int(t)
        except ValueError:
            pass

    percent = round((watched / total) * 100, 1) if total > 0 else 0.0
    return watched, total, percent

def determine_status(watched, total):
    if total > 0 and watched == total:
        return "Completed"
    if watched > 0:
        return "Watching"
    return "Not started"

def parse_date(date_str):
    try:
        return datetime.strptime(date_str, "%d-%m-%Y %H:%M:%S")
    except Exception:
        return None

# =========================================================
# GENRES → BADGES
# =========================================================
def normalize_genres(raw):
    if not raw:
        return []
    result = []
    for g in [x.strip() for x in raw.split(",")]:
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
# DATABASE QUERY
# =========================================================
def search_series(term):
    conn = sqlite3.connect(download_db())
    df = pd.read_sql_query(
        """
        SELECT
            NAAM, YEAR, PLOT, GENRE, TMDB_ID,
            PROGRESS, SEASONSEPISODES, UPDATED
        FROM tbl_Trakt
        WHERE NAAM LIKE ?
        """,
        conn,
        params=(f"%{term}%",)
    )
    conn.close()
    return df

# =========================================================
# UI – TITLE
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

zoekterm = st.text_input("Search series:")

# =========================================================
# UI – RESULTS
# =========================================================
if zoekterm.strip():
    df = search_series(zoekterm)

    for _, row in df.iterrows():
        watched, total, percent = parse_season_episodes(row["SEASONSEPISODES"])
        status = determine_status(watched, total)
        episodes_left = max(total - watched, 0)

        prog = parse_progress(row["PROGRESS"])
        last_seen_dt = parse_date(prog["date"])
        poster_url = get_tmdb_poster(row["TMDB_ID"])

        with st.container(border=True):
            col1, col2 = st.columns([1, 2])

            # POSTER
            with col1:
                if poster_url:
                    st.image(poster_url, use_container_width=True)

            # INFO
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

                # -------- COMPACTE STATUSREGEL (FIX)
                status_line = (
                    f"⏳ **{episodes_left} left** &nbsp;&nbsp; "
                    f"📊 **{watched} / {total} ({percent}%)**"
                )
                st.markdown(status_line, unsafe_allow_html=True)

                # Progress bar eronder
                st.progress(percent / 100)

            # DETAILS
            with st.expander("Details", expanded=True):
                st.markdown(
                    render_genre_badges(row["GENRE"]),
                    unsafe_allow_html=True
                )

                if row["PLOT"]:
                    st.markdown("**Plot:**")
                    st.write(row["PLOT"])

                st.caption(f"Last updated: {row['UPDATED']}")
