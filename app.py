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
        return {
            "status": "Not started",
            "season": None,
            "episode": None,
            "date": None
        }

    match = re.search(r"S(\d{2})E(\d{2})\s*←-→\s*(.+)", progress)
    if not match:
        return {
            "status": "Unknown",
            "season": None,
            "episode": None,
            "date": None
        }

    return {
        "status": "Watching",
        "season": int(match.group(1)),
        "episode": int(match.group(2)),
        "date": match.group(3)
    }

def parse_season_episodes(value):
    watched = 0
    total = 0

    if not value or value.strip() == "#N/A":
        return watched, total, 0

    for part in value.split("§"):
        try:
            w, t = part.split("/")
            watched += int(w)
            total += int(t)
        except ValueError:
            pass

    percent = round((watched / total) * 100, 1) if total > 0 else 0
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
# DATABASE QUERY
# =========================================================
def search_series(search_term):
    db_path = download_db()
    conn = sqlite3.connect(db_path)

    query = """
        SELECT
            NAAM,
            YEAR,
            PLOT,
            GENRE,
            TMDB_ID,
            PROGRESS,
            SEASONSEPISODES,
            RATING,
            UPDATED
        FROM tbl_Trakt
        WHERE NAAM LIKE ?
    """

    df = pd.read_sql_query(
        query,
        conn,
        params=(f"%{search_term}%",)
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

zoekterm = st.text_input(
    "Search series:",
    placeholder="e.g. Yellowstone, The Bear, …"
)

# =========================================================
# UI – RESULTS
# =========================================================
if zoekterm.strip():
    df = search_series(zoekterm)

    if df.empty:
        st.warning("No results found.")
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

                # POSTER
                with col1:
                    if poster_url:
                        st.image(poster_url, use_container_width=True)

                # INFO
                with col2:
                    st.subheader(f"{row['NAAM']} ({row['YEAR']})")

                    # STATUS
                    if status == "Completed":
                        st.markdown("🟢 **Completed**")
                    elif status == "Watching":
                        st.markdown("🔵 **Watching**")
                    else:
                        st.markdown("⚪ **Not started**")

                    # LAATST GEZIEN
                    if status == "Watching" and prog["season"] is not None:
                        last_seen_str = (
                            last_seen_dt.strftime("%d-%m-%Y %H:%M")
                            if last_seen_dt else prog["date"]
                        )

                        st.markdown(
                            f"👁️ **Laatst gezien:** "
                            f"S{prog['season']:02d}E{prog['episode']:02d} · {last_seen_str}"
                        )

                        # 🔑 EPISODES LEFT
                        st.markdown(
                            f"⏳ **Episodes left:** {episodes_left}"
                        )

                    # PROGRESS
                    st.progress(percent / 100)

                    st.markdown(
                        f"""
📊 **Progress:** {watched} / {total} ({percent}%)  
⭐ **Rating:** {row['RATING']}
                        """
                    )

                # DETAILS
                with st.expander("Details", expanded=True):
                    if row["GENRE"]:
                        st.markdown(f"**Genres:** {row['GENRE']}")

                    if row["PLOT"]:
                        st.markdown("**Plot:**")
                        st.write(row["PLOT"])

                    st.caption(f"Last updated: {row['UPDATED']}")
