import streamlit as st
import sqlite3
import requests
import pandas as pd
import re

# =========================================================
# CONFIG
# =========================================================
st.set_page_config(
    page_title="Trakt – Series Progress",
    layout="centered"
)

DROPBOX_DB_URL = (
    "https://www.dropbox.com/scl/fi/"
    "bjy95x305s1r2fvgiddcv/Trakt_DBase.db"
    "?rlkey=kxev7chehu2mnvmag0ojt9n4g&raw=1"
)

LOCAL_DB = "Trakt_DBase.db"

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
# PARSERS
# =========================================================
def parse_progress(progress):
    if not progress or progress.strip() == "#N/A":
        return {
            "status": "Niet gestart",
            "season": None,
            "episode": None,
            "date": None
        }

    match = re.search(
        r"S(\d{2})E(\d{2})\s*←-→\s*(.+)",
        progress
    )

    if not match:
        return {
            "status": "Onbekend",
            "season": None,
            "episode": None,
            "date": None
        }

    return {
        "status": "Bezig",
        "season": int(match.group(1)),
        "episode": int(match.group(2)),
        "date": match.group(3)
    }

def parse_season_episodes(value):
    watched = 0
    total = 0

    if not value or value.strip() == "#N/A":
        return watched, total, 0

    parts = value.split("§")
    for part in parts:
        try:
            w, t = part.split("/")
            watched += int(w)
            total += int(t)
        except ValueError:
            pass

    percent = round((watched / total) * 100, 1) if total > 0 else 0
    return watched, total, percent

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
            PROGRESS,
            SEASONSEPISODES,
            VIEWSTATUS,
            RATING,
            UPDATED
        FROM tbl_Trakt
        WHERE NAAM LIKE ?
        ORDER BY NAAM
    """

    df = pd.read_sql_query(
        query,
        conn,
        params=(f"%{search_term}%",)
    )

    conn.close()
    return df

# =========================================================
# UI
# =========================================================
st.title("📺 Trakt – Series Progress")

zoekterm = st.text_input(
    "Zoek een serie (deel van naam):",
    placeholder="bv. Yellowstone, The Bear, …"
)

if zoekterm.strip():
    df = search_series(zoekterm)

    if df.empty:
        st.warning("Geen resultaten gevonden.")
    else:
        for _, row in df.iterrows():
            prog = parse_progress(row["PROGRESS"])
            watched, total, percent = parse_season_episodes(
                row["SEASONSEPISODES"]
            )

            with st.container(border=True):
                st.subheader(f"{row['NAAM']} ({row['YEAR']})")

                if prog["status"] == "Niet gestart":
                    st.markdown("🟡 **Niet gestart**")
                else:
                    st.markdown(
                        f"""
🟢 **Laatst bekeken:**  
Seizoen {prog['season']} · Episode {prog['episode']}  
🕒 {prog['date']}
                        """
                    )

                st.progress(percent / 100)

                st.markdown(
                    f"""
📊 **Voortgang:** {watched} / {total}  
📈 **Percentage:** {percent}%  

**Viewstatus:** `{row['VIEWSTATUS']}`  
**Rating:** `{row['RATING']}`  
**Laatste update:** `{row['UPDATED']}`
                    """
                )
