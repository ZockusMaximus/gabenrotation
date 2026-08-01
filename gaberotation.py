import base64
from datetime import datetime, timedelta
import json
import os
import random
import urllib.parse
from zoneinfo import ZoneInfo
import requests
import streamlit as st

# Auto-Refresh Versuchen für den Live-Timer
try:
    from streamlit_autorun import autorun

    AUTORUN_AVAILABLE = True
except ImportError:
    AUTORUN_AVAILABLE = False

DATA_FILE = "data.json"
ADMIN_PASSWORD = "zm1234"
GERMANY_TZ = ZoneInfo("Europe/Berlin")
DEFAULT_IMAGE = (
    "https://images.unsplash.com/photo-1550745165-9bc0b252726f?w=400&q=80"
)
DEFAULT_USERS = ["Sascha", "Alexander", "Victor", "Marcel", "Jan", "Stefan"]

INITIAL_GAMES_LIST = [
    "Counter-Strike 2",
    "Team Fortress 2",
    "Day of Defeat: Source",
    "Age of Empires 4",
    "PEAK",
    "Repo",
    "MECCHA CHAMELEON",
    "Phasmophobia",
    "Tabletop Simulator",
    "OpenFront",
    "SM64 COOP dx",
]


# --- DEUTSCHE ZEIT HILFSFUNKTIONEN ---
def get_now():
    """Gibt die aktuelle Uhrzeit in der deutschen Zeitzone (Europe/Berlin) zurück."""
    return datetime.now(GERMANY_TZ)


def get_next_game_night():
    """Berechnet das Datum und die Uhrzeit (20:00 Uhr) der nächsten Game Night (Freitag)."""
    now = get_now()
    weekday = now.weekday()

    if weekday == 4 and now.hour < 20:
        days_ahead = 0
    else:
        days_ahead = (4 - weekday) % 7
        if days_ahead == 0:
            days_ahead = 7

    next_friday = now + timedelta(days=days_ahead)
    return next_friday.replace(hour=20, minute=0, second=0, microsecond=0)


# --- AUTOMATISCHER STEAM COVER SCRAPER & STORE-LINK ---
def get_steam_data(game_name):
    """Sucht auf Steam nach Cover-URL und Store-URL."""
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        search_url = f"https://store.steampowered.com/api/storesearch/?term={urllib.parse.quote(game_name)}&l=german&cc=DE"
        res = requests.get(search_url, headers=headers, timeout=4).json()

        if res.get("items") and len(res["items"]) > 0:
            app_id = res["items"][0]["id"]
            img_url = f"https://cdn.akamai.steamstatic.com/steam/apps/{app_id}/header.jpg"
            store_url = f"https://store.steampowered.com/app/{app_id}/"
            return img_url, store_url, True
    except Exception:
        pass

    clean_search = urllib.parse.quote(game_name)
    fallback_store = (
        f"https://store.steampowered.com/search/?term={clean_search}"
    )
    return DEFAULT_IMAGE, fallback_store, False


# --- GITHUB AUTOMATISCHE SYNC FUNKTION ---
def push_to_github(data_content):
    """Speichert die data.json automatisch direkt in das GitHub Repository."""
    try:
        token = st.secrets.get("GITHUB_TOKEN")
        repo = st.secrets.get("GITHUB_REPO")
        file_path = st.secrets.get("GITHUB_FILE_PATH", "data.json")

        if not token or not repo:
            st.session_state["github_error"] = (
                "GITHUB_TOKEN oder GITHUB_REPO Secret fehlt in Streamlit!"
            )
            return

        url = f"https://api.github.com/repos/{repo}/contents/{file_path}"
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
        }

        get_res = requests.get(url, headers=headers, timeout=5)
        sha = get_res.json().get("sha") if get_res.status_code == 200 else None

        json_str = json.dumps(data_content, ensure_ascii=False, indent=4)
        content_b64 = base64.b64encode(json_str.encode("utf-8")).decode("utf-8")

        payload = {
            "message": "Auto-update data.json via Streamlit Voting App",
            "content": content_b64,
        }
        if sha:
            payload["sha"] = sha

        put_res = requests.put(url, headers=headers, json=payload, timeout=5)

        if put_res.status_code in [200, 201]:
            st.session_state["github_error"] = None
        else:
            st.session_state["github_error"] = (
                f"GitHub API Fehler {put_res.status_code}: {put_res.json().get('message')}"
            )
    except Exception as e:
        st.session_state["github_error"] = f"Verbindungsfehler zu GitHub: {e}"


# --- DATENBANK FUNKTIONEN ---
def load_data():
    if not os.path.exists(DATA_FILE):
        initial_games = []
        for idx, g_name in enumerate(INITIAL_GAMES_LIST, start=1):
            img_url, store_url, is_steam = get_steam_data(g_name)
            initial_games.append(
                {
                    "id": idx,
                    "name": g_name,
                    "votes": 0,
                    "locked": False,
                    "approved": True,
                    "image_url": img_url,
                    "store_url": store_url,
                    "custom_store_url": "",
                    "note": "",
                }
            )

        default_data = {
            "players": DEFAULT_USERS,
            "games": initial_games,
            "suggestions": [],
            "ban_requests": [],
            "voted_users": {},
            "last_winner_ids": [],
            "override_winner_ids": [],
            "manual_status_override": "AUTO",
            "last_reset_kw": get_now().isocalendar()[1],
            "vote_history": [],
            "randomizer_logs": [],
            "admin_status_logs": [],
            "weekly_winner_history": [],
        }
        save_data(default_data)
        return default_data

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

        if "players" not in data or not isinstance(data.get("players"), list):
            data["players"] = DEFAULT_USERS
        if "suggestions" not in data:
            data["suggestions"] = []
        if "ban_requests" not in data:
            data["ban_requests"] = []
        if "last_reset_kw" not in data:
            data["last_reset_kw"] = 0

        for g in data.get("games", []):
            if "approved" not in g:
                g["approved"] = True
            if "custom_store_url" not in g:
                g["custom_store_url"] = ""
            if "note" not in g:
                g["note"] = ""
            if "store_url" not in g or not g["store_url"]:
                _, g["store_url"], _ = get_steam_data(g["name"])
            if "image_url" not in g or not g["image_url"]:
                g["image_url"], _, _ = get_steam_data(g["name"])

        for s in data.get("suggestions", []):
            if "voters" not in s:
                s["voters"] = []
            if "against_voters" not in s:
                s["against_voters"] = []
            if "custom_store_url" not in s:
                s["custom_store_url"] = ""
            if "note" not in s:
                s["note"] = ""
            if "reason" not in s:
                s["reason"] = ""
            if "author" not in s:
                s["author"] = "Unbekannt"
            if "store_url" not in s or not s["store_url"]:
                _, s["store_url"], _ = get_steam_data(s["name"])
            if "image_url" not in s or not s["image_url"]:
                s["image_url"], _, _ = get_steam_data(s["name"])

        for b in data.get("ban_requests", []):
            if "voters" not in b:
                b["voters"] = []
            if "against_voters" not in b:
                b["against_voters"] = []
            if "reason" not in b:
                b["reason"] = ""
            if "author" not in b:
                b["author"] = "Unbekannt"

        if isinstance(data.get("voted_users"), list):
            data["voted_users"] = {}
        if "manual_status_override" not in data:
            data["manual_status_override"] = "AUTO"
        if "vote_history" not in data or not isinstance(
            data.get("vote_history"), list
        ):
            data["vote_history"] = []
        if "randomizer_logs" not in data or not isinstance(
            data.get("randomizer_logs"), list
        ):
            data["randomizer_logs"] = []
        if "admin_status_logs" not in data or not isinstance(
            data.get("admin_status_logs"), list
        ):
            data["admin_status_logs"] = []
        if "weekly_winner_history" not in data or not isinstance(
            data.get("weekly_winner_history"), list
        ):
            data["weekly_winner_history"] = []
        if "override_winner_ids" not in data:
            data["override_winner_ids"] = []

        save_data(data)
        return data


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    push_to_github(data)


def recalculate_game_votes(data):
    """Berechnet die Gesamtstimmen pro Spiel neu basierend auf den voted_users Eintragungen."""
    vote_counts = {}
    for user_lower, g_ids in data.get("voted_users", {}).items():
        for g_id in g_ids:
            vote_counts[g_id] = vote_counts.get(g_id, 0) + 1

    for game in data.get("games", []):
        game["votes"] = vote_counts.get(game["id"], 0)


# --- ZEIT & SCHLIESS-LOGIK MIT AUTOMATISCHEM SAMSTAGS-RESET ---
def get_voting_time_status(data):
    now = get_now()
    weekday = now.weekday()
    hour = now.hour
    current_kw = now.isocalendar()[1]

    # AUTOMATISCHER RESET AM SAMSTAG AB 01:00 UHR
    if weekday == 5 and hour >= 1:
        if data.get("last_reset_kw") != current_kw:
            data["override_winner_ids"] = []
            data["last_winner_ids"] = []
            data["voted_users"] = {}
            data["last_reset_kw"] = current_kw
            recalculate_game_votes(data)
            save_data(data)

    override = data.get("manual_status_override", "AUTO")
    if override == "OPEN":
        return True, timedelta(0), "Manuell durch Admin geöffnet", True
    elif override == "CLOSED":
        return False, timedelta(0), "Manuell durch Admin geschlossen", True

    is_open = False
    if weekday in [6, 0, 1, 2]:  # So, Mo, Di, Mi
        is_open = True
    elif weekday == 5 and hour >= 1:  # Samstag ab 01:00 Uhr
        is_open = True

    if is_open:
        days_until_wed = (2 - weekday) % 7
        target_time = datetime(
            now.year, now.month, now.day, 23, 59, 59, tzinfo=GERMANY_TZ
        ) + timedelta(days=days_until_wed)
        label = "Voting schließt in:"
    else:
        days_until_sat = (5 - weekday) % 7
        if days_until_sat == 0 and hour >= 1:
            days_until_sat = 7
        target_time = datetime(
            now.year, now.month, now.day, 1, 0, 0, tzinfo=GERMANY_TZ
        ) + timedelta(days=days_until_sat)
        label = "Nächstes Voting öffnet in (Samstag 01:00 Uhr):"

    time_left = target_time - now
    return is_open, time_left, label, False


def format_timedelta(td):
    days = td.days
    hours, remainder = divmod(td.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if days > 0:
        return f"{days}d {hours:02d}h {minutes:02d}m {seconds:02d}s"
    return f"{hours:02d}h {minutes:02d}m {seconds:02d}s"


# --- GEWINNER ERMITTLUNG ---
def get_top_winners(data):
    recalculate_game_votes(data)
    approved_games = [g for g in data["games"] if g.get("approved", True)]

    if data.get("override_winner_ids"):
        override_games = [
            g for g in approved_games if g["id"] in data["override_winner_ids"]
        ]
        if override_games:
            return override_games, False, "Manuelles Override", True

    active_games = [g for g in approved_games if g["votes"] > 0]
    if not active_games:
        return [], False, "Keine Stimmen abgegeben", False

    sorted_games = sorted(active_games, key=lambda x: x["votes"], reverse=True)
    if len(sorted_games) <= 2:
        return sorted_games, False, "Eindeutiges Ergebnis", False

    first_votes = sorted_games[0]["votes"]
    first_candidates = [g for g in sorted_games if g["votes"] == first_votes]

    if len(first_candidates) >= 2:
        selected = random.sample(first_candidates, 2)
        log_msg = f"Gleichstand Platz 1 ({first_votes} Stimmen). Gelost: {[g['name'] for g in selected]}"
        return selected, True, log_msg, False

    winner_1 = sorted_games[0]
    second_votes = sorted_games[1]["votes"]
    second_candidates = [g for g in sorted_games if g["votes"] == second_votes]

    if len(second_candidates) > 1:
        winner_2 = random.choice(second_candidates)
        log_msg = f"Gleichstand Platz 2 ({second_votes} Stimmen). Gelost: {winner_2['name']}"
        return [winner_1, winner_2], True, log_msg, False

    return [winner_1, sorted_games[1]], False, "Eindeutiges Ergebnis", False


# --- APP STYLING ---
st.set_page_config(
    page_title="Zockus Maximus - Friday Game Night",
    page_icon="🎮",
    layout="centered",
    initial_sidebar_state="collapsed",
)

if AUTORUN_AVAILABLE:
    autorun(interval=1000, key="live_clock_refresher")

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@700;900&family=Rajdhani:wght@600;700&display=swap');

    .stApp {
        background: radial-gradient(circle at 50% 10%, #1e1035 0%, #0d0b1e 70%);
        color: #f1f5f9;
        font-family: 'Rajdhani', sans-serif;
    }

    .brand-banner {
        background: linear-gradient(135deg, #ff007f 0%, #7928ca 50%, #00f0ff 100%);
        border: 2px solid #00f0ff;
        border-radius: 16px;
        padding: 30px 15px;
        text-align: center;
        box-shadow: 0 0 25px rgba(255, 0, 127, 0.45), inset 0 0 15px rgba(0, 240, 255, 0.3);
        margin-bottom: 25px;
    }
    .brand-title {
        font-family: 'Montserrat', sans-serif;
        font-size: 2.5rem;
        font-weight: 900;
        color: #ffffff;
        text-shadow: 0 0 12px #ff007f, 0 0 25px #00f0ff;
        letter-spacing: 3px;
        margin: 0;
        text-transform: uppercase;
    }
    .brand-subtitle {
        color: #e2e8f0;
        font-size: 1.2rem;
        font-weight: 700;
        margin-top: 5px;
        letter-spacing: 2px;
        text-shadow: 0 0 8px rgba(0,0,0,0.8);
        text-transform: uppercase;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: rgba(22, 16, 44, 0.6);
        padding: 8px;
        border-radius: 12px;
        border: 1px solid #7928ca;
    }

    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: rgba(35, 25, 66, 0.8);
        border-radius: 8px;
        color: #cbd5e1;
        font-family: 'Montserrat', sans-serif;
        font-weight: 700;
        font-size: 0.95rem;
        padding: 0px 16px;
        border: 1px solid #3b2d6b;
        transition: all 0.2s ease;
    }

    .stTabs [data-baseweb="tab"]:hover {
        background-color: rgba(121, 40, 202, 0.4);
        color: #ffffff;
        border-color: #00f0ff;
    }

    .stTabs [aria-selected="true"] {
        background: linear-gradient(90deg, #ff007f 0%, #7928ca 100%) !important;
        color: #ffffff !important;
        border-color: #00f0ff !important;
        box-shadow: 0 0 12px rgba(255, 0, 127, 0.5);
    }

    div.stButton > button {
        background: linear-gradient(90deg, #ff007f 0%, #b800ff 100%);
        color: #ffffff !important;
        font-family: 'Montserrat', sans-serif;
        font-weight: 700;
        border-radius: 8px;
        border: 1px solid #ff77d6;
        box-shadow: 0 0 10px rgba(255, 0, 127, 0.3);
        transition: all 0.2s ease-in-out;
        width: 100%;
        padding: 8px;
    }
    div.stButton > button:hover {
        background: linear-gradient(90deg, #00f0ff 0%, #ff007f 100%);
        box-shadow: 0 0 20px #00f0ff;
        border-color: #ffffff;
        transform: translateY(-2px);
    }

    .steam-btn {
        display: inline-block;
        background: linear-gradient(90deg, #171a21 0%, #2a475e 100%);
        color: #c6d4df !important;
        font-family: 'Montserrat', sans-serif;
        font-size: 0.8rem;
        font-weight: 700;
        padding: 6px 12px;
        border-radius: 6px;
        border: 1px solid #66c0f4;
        text-decoration: none;
        text-align: center;
        margin-top: 4px;
        box-shadow: 0 0 8px rgba(102, 192, 244, 0.3);
    }
    .steam-btn:hover {
        background: #66c0f4;
        color: #171a21 !important;
        box-shadow: 0 0 15px #66c0f4;
    }

    .custom-web-btn {
        display: inline-block;
        background: linear-gradient(90deg, #7928ca 0%, #ff007f 100%);
        color: #ffffff !important;
        font-family: 'Montserrat', sans-serif;
        font-size: 0.8rem;
        font-weight: 700;
        padding: 6px 12px;
        border-radius: 6px;
        border: 1px solid #00f0ff;
        text-decoration: none;
        text-align: center;
        margin-top: 4px;
        box-shadow: 0 0 8px rgba(0, 240, 255, 0.4);
    }
    .custom-web-btn:hover {
        background: #00f0ff;
        color: #0d0b1e !important;
        box-shadow: 0 0 15px #00f0ff;
    }

    .game-note-badge {
        background: rgba(255, 0, 127, 0.15);
        border: 1px solid #ff007f;
        color: #ff77d6;
        padding: 4px 8px;
        border-radius: 6px;
        font-size: 0.85rem;
        font-weight: bold;
        margin-top: 4px;
        display: inline-block;
    }

    /* NEON BOXEN FÜR BEGRÜNDUNGEN & VERTEIDIGUNGEN */
    .reason-box-green {
        background: rgba(16, 185, 129, 0.1);
        border: 1px solid #10b981;
        border-radius: 8px;
        padding: 8px 12px;
        color: #6ee7b7;
        font-size: 0.9rem;
        margin-top: 6px;
        box-shadow: 0 0 10px rgba(16, 185, 129, 0.2);
    }
    .reason-box-red {
        background: rgba(239, 68, 68, 0.1);
        border: 1px solid #ef4444;
        border-radius: 8px;
        padding: 8px 12px;
        color: #fca5a5;
        font-size: 0.9rem;
        margin-top: 6px;
        box-shadow: 0 0 10px rgba(239, 68, 68, 0.2);
    }

    /* NEON NEU-STYLING FÜR STREAMLIT BORDER CONTAINER */
    [data-testid="stVerticalBlockBorderWrapper"] {
        border: 2px solid #00f0ff !important;
        border-radius: 12px !important;
        background: rgba(22, 16, 44, 0.85) !important;
        box-shadow: 0 0 18px rgba(0, 240, 255, 0.35), inset 0 0 10px rgba(0, 240, 255, 0.15) !important;
        padding: 10px !important;
    }

    .time-header-box {
        background: rgba(22, 16, 44, 0.85);
        border: 1px solid #7928ca;
        border-radius: 12px;
        padding: 15px;
        text-align: center;
        margin-bottom: 20px;
        box-shadow: 0 0 15px rgba(121, 40, 202, 0.25);
    }
    .clock-text { font-size: 1.1rem; color: #cbd5e1; margin-bottom: 5px; }
    .countdown-display { 
        font-family: 'Montserrat', sans-serif;
        font-size: 2rem; 
        font-weight: 800; 
        color: #00f0ff; 
        text-shadow: 0 0 10px #00f0ff;
    }
    .next-gamenight-box {
        margin-top: 10px;
        padding-top: 8px;
        border-top: 1px solid #3b2d6b;
        font-size: 1.1rem;
        font-weight: bold;
        color: #ff77d6;
        letter-spacing: 1px;
    }

    .status-card {
        padding: 12px; border-radius: 8px; font-weight: bold; text-align: center; margin-bottom: 15px;
        font-family: 'Montserrat', sans-serif; font-size: 1rem;
    }
    .open { 
        background-color: rgba(16, 185, 129, 0.15); 
        border: 1px solid #10b981; 
        color: #34d399; 
        box-shadow: 0 0 10px rgba(16, 185, 129, 0.3);
    }
    .closed { 
        background-color: rgba(239, 68, 68, 0.15); 
        border: 1px solid #ef4444; 
        color: #f87171; 
        box-shadow: 0 0 10px rgba(239, 68, 68, 0.3);
    }

    .winner-box {
        background: linear-gradient(135deg, rgba(255, 0, 127, 0.15), rgba(0, 240, 255, 0.15));
        border: 2px solid #ff007f;
        padding: 15px; border-radius: 12px;
        text-align: center; margin-bottom: 20px;
        box-shadow: 0 0 20px rgba(255, 0, 127, 0.3);
    }

    .stat-card {
        background: rgba(22, 16, 44, 0.7);
        border: 1px solid #3b2d6b;
        border-radius: 10px;
        padding: 12px;
        margin-bottom: 10px;
    }
    </style>
""",
    unsafe_allow_html=True,
)

data = load_data()
recalculate_game_votes(data)

# NAVIGATION
menu = st.sidebar.radio("Navigation", ["🎮 Hauptseite", "⚙️ Admin-Bereich"])

# BANNER
st.markdown(
    """
    <div class="brand-banner">
        <h1 class="brand-title">ZOCKUS MAXIMUS</h1>
        <div class="brand-subtitle">FRIDAY GAME NIGHT</div>
    </div>
""",
    unsafe_allow_html=True,
)

# ==========================================
# SEITE 1: HAUPTSEITE
# ==========================================
if menu == "🎮 Hauptseite":
    now = get_now()
    next_gn = get_next_game_night()
    is_open, time_left, countdown_label, is_manual_override = (
        get_voting_time_status(data)
    )

    st.markdown(
        f"""
        <div class="time-header-box">
            <div class="clock-text">📅 Aktuelle Zeit (DE): <strong>{now.strftime("%A, %d.%m.%Y - %H:%M:%S")} Uhr</strong></div>
            <hr style="border-color:#3b2d6b; margin:8px 0;">
            <div style="font-size:0.9rem; color:#a78bfa;">{countdown_label}</div>
            <div class="countdown-display">{"--" if is_manual_override else format_timedelta(time_left)}</div>
            <div class="next-gamenight-box">
                🕹️ Nächste Game Night: <strong>{next_gn.strftime("%A, %d.%m.%Y um 20:00 Uhr")}</strong>
            </div>
        </div>
    """,
        unsafe_allow_html=True,
    )

    if is_manual_override:
        st.markdown(
            f'<div class="status-card closed">⚠️ HINWEIS: Das Voting wurde vom Admin MANUELL {"GEÖFFNET" if is_open else "GESCHLOSSEN"}!</div>',
            unsafe_allow_html=True,
        )

    status_class = "open" if is_open else "closed"
    status_text = (
        "🟢 VOTING IST AKTUELL GEÖFFNET!"
        if is_open
        else "🔴 VOTING IST AKTUELL GESCHLOSSEN (Start: Samstag 01:00 Uhr)"
    )
    st.markdown(
        f'<div class="status-card {status_class}">{status_text}</div>',
        unsafe_allow_html=True,
    )

    tab_vote, tab_suggestions, tab_history, tab_stats = st.tabs(
        [
            "🗳️ Aktuelle Abstimmung",
            "💡 Vorschläge & Banns",
            "🏆 Gewinner-Historie",
            "📊 Statistik & Picks",
        ]
    )

    # TAB 1: AKTUELLE ABSTIMMUNG
    with tab_vote:
        top_winners, tie_occurred, tie_msg, is_override_active = get_top_winners(
            data
        )

        if top_winners:
            box_title = (
                "👑 FESTGELEGTE GEWINNER (ADMIN OVERRIDE)"
                if is_override_active
                else "🏆 AKTUELLE TOP-2 FAVORITEN"
            )

            st.markdown(
                f"""
                <div class="winner-box">
                    <h3 style="color:#00f0ff; margin:0; font-family:'Montserrat'; font-weight:800;">{box_title}</h3>
                </div>
            """,
                unsafe_allow_html=True,
            )

            cols_w = st.columns(len(top_winners))
            for w_idx, win_game in enumerate(top_winners):
                with cols_w[w_idx]:
                    img_src = win_game.get("image_url", DEFAULT_IMAGE)
                    g_name = win_game["name"]
                    g_votes = win_game["votes"]
                    g_note = win_game.get("note", "").strip()

                    c_link = win_game.get("custom_store_url", "").strip()
                    s_link = win_game.get("store_url", "").strip()

                    with st.container(border=True):
                        st.markdown(
                            """<div style="height: 3px; background: #00f0ff; border-radius: 4px; box-shadow: 0 0 8px #00f0ff; margin-bottom: 8px;"></div>""",
                            unsafe_allow_html=True,
                        )
                        st.image(img_src, use_container_width=True)
                        st.markdown(
                            f"<h3 style='margin:5px 0; text-align:center;'>{g_name}</h3>",
                            unsafe_allow_html=True,
                        )

                        if g_note:
                            st.markdown(
                                f"<div style='text-align:center; margin-bottom:5px;'><span class='game-note-badge'>💬 {g_note}</span></div>",
                                unsafe_allow_html=True,
                            )

                        st.markdown(
                            f"<div style='color:#cbd5e1; font-size:0.95rem; text-align:center; margin:6px 0;'>📊 <b>{g_votes}</b> Stimmen</div>",
                            unsafe_allow_html=True,
                        )

                        if c_link:
                            st.markdown(
                                f"<div style='text-align:center;'><a href='{c_link}' target='_blank' class='custom-web-btn'>🌐 Website / Store</a></div>",
                                unsafe_allow_html=True,
                            )
                        elif s_link:
                            st.markdown(
                                f"<div style='text-align:center;'><a href='{s_link}' target='_blank' class='steam-btn'>🛒 Steam Store</a></div>",
                                unsafe_allow_html=True,
                            )

                        st.markdown(
                            """<div style="height: 3px; background: #00f0ff; border-radius: 4px; box-shadow: 0 0 8px #00f0ff; margin-top: 10px;"></div>""",
                            unsafe_allow_html=True,
                        )

        st.write("---")
        st.subheader("🎮 Spieleliste & Checkbox-Voting")
        st.write(
            "Wähle deinen Namen aus, hake **alle Spiele an, die du mitzocken möchtest**, und klicke unten auf **„💾 Meine Votes speichern“**! Du kannst deine Auswahl jederzeit bearbeiten, solange das Voting offen ist."
        )

        # DROPDOWN MIT REMINDER "SCHON GEVOTET"
        player_options_formatted = ["-- Bitte wählen --"]
        voted_users_map = data.get("voted_users", {})

        for p_name in data.get("players", DEFAULT_USERS):
            if p_name.lower() in voted_users_map and len(voted_users_map[p_name.lower()]) > 0:
                player_options_formatted.append(f"{p_name} (Bereits gevotet ✅)")
            else:
                player_options_formatted.append(p_name)

        selected_formatted_user = st.selectbox(
            "Wähle deinen Namen aus:",
            options=player_options_formatted,
            key="user_select_main_vote",
        )

        if selected_formatted_user == "-- Bitte wählen --":
            user_name = ""
        else:
            user_name = selected_formatted_user.replace(" (Bereits gevotet ✅)", "").strip()

        user_voted_g_ids = (
            data["voted_users"].get(user_name.lower(), []) if user_name else []
        )
        public_games = [g for g in data["games"] if g.get("approved", True)]

        selected_game_ids = []

        for game in public_games:
            col_img, col1, col2, col3 = st.columns([1.5, 2.5, 1, 2])
            is_locked = game["locked"] or game["id"] in data.get(
                "last_winner_ids", []
            )

            with col_img:
                st.image(
                    game.get("image_url", DEFAULT_IMAGE),
                    use_container_width=True,
                )

                c_link = game.get("custom_store_url", "").strip()
                s_link = game.get("store_url", "").strip()

                if c_link:
                    st.markdown(
                        f'<a href="{c_link}" target="_blank" class="custom-web-btn">🌐 Website / Store</a>',
                        unsafe_allow_html=True,
                    )
                elif s_link:
                    st.markdown(
                        f'<a href="{s_link}" target="_blank" class="steam-btn">🛒 Steam Store</a>',
                        unsafe_allow_html=True,
                    )

            with col1:
                if is_locked:
                    st.markdown(f"**{game['name']}** 🚫 *(Vorwoche Gewinner)*")
                else:
                    st.markdown(f"### {game['name']}")

                if game.get("note", "").strip():
                    st.markdown(
                        f'<div class="game-note-badge">💬 {game["note"].strip()}</div>',
                        unsafe_allow_html=True,
                    )

            with col2:
                st.caption(f"📊 **{game['votes']}** Stimmen")

            with col3:
                is_checked_default = game["id"] in user_voted_g_ids
                cb_disabled = not is_open or is_locked or not user_name

                is_checked = st.checkbox(
                    "Mitzocken 👍",
                    value=is_checked_default,
                    key=f"cb_game_{game['id']}_{user_name}",
                    disabled=cb_disabled,
                )
                if is_checked:
                    selected_game_ids.append(game["id"])

            st.markdown(
                '<hr style="border-color:#2a244d; margin:5px 0 15px 0;">',
                unsafe_allow_html=True,
            )

        if user_name and is_open:
            st.write("---")
            if st.button("💾 Meine Votes speichern / aktualisieren", key="save_user_checkbox_votes"):
                data["voted_users"][user_name.lower()] = selected_game_ids

                # Voting Log erfassen
                log_entry = {
                    "timestamp": get_now().strftime("%Y-%m-%d %H:%M:%S"),
                    "kw": get_now().isocalendar()[1],
                    "user": user_name,
                    "voted_games_count": len(selected_game_ids),
                }
                data["vote_history"].append(log_entry)

                recalculate_game_votes(data)
                save_data(data)
                st.success(f"Votes von {user_name} erfolgreich gespeichert ({len(selected_game_ids)} Spiele ausgewählt)!")
                st.rerun()

    # TAB 2: SPIELVORSCHLÄGE & BANNS MIT DYNAMISCHER MEHRHEIT
    with tab_suggestions:
        player_list = data.get("players", DEFAULT_USERS)
        # DYNAMISCHE MEHRHEIT (MEHR ALS 50% DER SPIELER)
        needed_votes = (len(player_list) // 2) + 1

        st.subheader("💡 Spielvorschläge")
        st.write(
            f"Schlagt hier neue Spiele vor! Sobald die **Mehrheit ({needed_votes} von {len(player_list)} Spielern)** dafür gestimmt hat, wandert das Spiel **automatisch in die Haupt-Spieleliste**!"
        )

        with st.expander("➕ Neues Spiel vorschlagen", expanded=False):
            sug_author = st.selectbox(
                "Dein Name (Ersteller):",
                options=["-- Bitte wählen --"] + player_list,
                key="sug_author_select",
            )
            col_s1, col_s2 = st.columns(2)
            with col_s1:
                suggested_name = st.text_input(
                    "Spielname eingeben:",
                    key="tab_sug_name_in",
                    placeholder="z.B. Valheim",
                )
                suggested_note = st.text_input(
                    "Notiz / Kommentar (z.B. 6 Player Mod):",
                    key="tab_sug_note_in",
                )
                suggested_reason = st.text_area(
                    "Begründung / Meinung (Warum sollte es hinzugefügt werden?):",
                    key="tab_sug_reason_in",
                    placeholder="Erhöht den Spaß, hat super Koop-Modus...",
                )
            with col_s2:
                suggested_img = st.text_input(
                    "Cover Bild-URL (optional):",
                    key="tab_sug_url_in",
                    placeholder="Leer für Steam",
                )
                suggested_link = st.text_input(
                    "Website / Store Link (optional):",
                    key="tab_sug_link_in",
                    placeholder="https://...",
                )

            if st.button("Vorschlag einreichen", key="submit_sug_tab_btn"):
                if sug_author == "-- Bitte wählen --":
                    st.error(
                        "Bitte wähle deinen Namen aus, um den Vorschlag einzureichen!"
                    )
                elif suggested_name.strip():
                    existing_games = [
                        g["name"].lower() for g in data.get("games", [])
                    ]
                    existing_suggs = [
                        s["name"].lower() for s in data.get("suggestions", [])
                    ]
                    clean_name = suggested_name.strip()

                    if (
                        clean_name.lower() in existing_games
                        or clean_name.lower() in existing_suggs
                    ):
                        st.warning("Dieses Spiel existiert bereits in der Liste oder bei Vorschlägen!")
                    else:
                        with st.spinner("Lade Spieldaten von Steam..."):
                            img_url_auto, store_url_auto, _ = get_steam_data(
                                clean_name
                            )
                            img_final = (
                                suggested_img.strip()
                                if suggested_img.strip()
                                else img_url_auto
                            )

                        new_s_id = (
                            max(
                                [s["id"] for s in data.get("suggestions", [])],
                                default=0,
                            )
                            + 1
                        )
                        data["suggestions"].append(
                            {
                                "id": new_s_id,
                                "name": clean_name,
                                "author": sug_author,
                                "image_url": img_final,
                                "store_url": store_url_auto,
                                "custom_store_url": suggested_link.strip(),
                                "note": suggested_note.strip(),
                                "reason": suggested_reason.strip(),
                                "voters": [sug_author],
                                "against_voters": [],
                            }
                        )
                        save_data(data)
                        st.success(
                            f"Vorschlag '{clean_name}' von {sug_author} eingereicht!"
                        )
                        st.rerun()

        st.write("---")
        selected_s_user = st.selectbox(
            "Wähle deinen Namen für Abstimmung von Vorschlägen & Banns:",
            options=["-- Bitte wählen --"] + player_list,
            key="tab_sug_user_select",
        )
        s_user_name = (
            "" if selected_s_user == "-- Bitte wählen --" else selected_s_user
        )

        if data.get("suggestions"):
            st.markdown("### Ausstehende Spielvorschläge")
            for s_idx, sugg in enumerate(list(data["suggestions"])):
                sc_img, sc_info, sc_vote = st.columns([1.5, 2.5, 2])
                voters_for = sugg.get("voters", [])
                voters_against = sugg.get("against_voters", [])

                has_voted_for = (
                    s_user_name.lower() in [v.lower() for v in voters_for]
                    if s_user_name
                    else False
                )
                has_voted_against = (
                    s_user_name.lower() in [v.lower() for v in voters_against]
                    if s_user_name
                    else False
                )

                with sc_img:
                    st.image(
                        sugg.get("image_url", DEFAULT_IMAGE),
                        use_container_width=True,
                    )

                with sc_info:
                    st.markdown(f"### {sugg['name']}")
                    st.caption(f"👤 Erstellt von: **{sugg.get('author', 'Unbekannt')}**")

                    if sugg.get("note", "").strip():
                        st.markdown(
                            f'<div class="game-note-badge">💬 {sugg["note"].strip()}</div>',
                            unsafe_allow_html=True,
                        )
                    if sugg.get("reason", "").strip():
                        st.markdown(
                            f'<div class="reason-box-green">🟢 <b>Begründung:</b> {sugg["reason"].strip()}</div>',
                            unsafe_allow_html=True,
                        )

                    st.caption(
                        f"👍 **{len(voters_for)} / {needed_votes}** Stimmen für Mehrheit | 👎 **{len(voters_against)}** Dagegen"
                    )
                    if voters_for:
                        st.write(f"Dafür: *{', '.join(voters_for)}*")
                    if voters_against:
                        st.write(f"Dagegen: *{', '.join(voters_against)}*")

                with sc_vote:
                    c_btn1, c_btn2 = st.columns(2)
                    with c_btn1:
                        if st.button(
                            "Dafür 👍",
                            key=f"tab_sug_for_{sugg['id']}",
                            disabled=not s_user_name or has_voted_for,
                        ):
                            if s_user_name in voters_against:
                                voters_against.remove(s_user_name)
                            if s_user_name not in voters_for:
                                voters_for.append(s_user_name)

                            # DYNAMISCHE MEHRHEITS-PRÜFUNG
                            if len(voters_for) >= needed_votes:
                                new_g_id = max([g["id"] for g in data["games"]], default=0) + 1
                                data["games"].append(
                                    {
                                        "id": new_g_id,
                                        "name": sugg["name"],
                                        "votes": 0,
                                        "locked": False,
                                        "approved": True,
                                        "image_url": sugg.get("image_url", DEFAULT_IMAGE),
                                        "store_url": sugg.get("store_url", ""),
                                        "custom_store_url": sugg.get("custom_store_url", ""),
                                        "note": sugg.get("note", ""),
                                    }
                                )
                                data["suggestions"].pop(s_idx)
                                save_data(data)
                                st.balloons()
                                st.success(f"🎉 MEHRHEIT ERREICHT! '{sugg['name']}' wurde in die Hauptliste aufgenommen!")
                                st.rerun()
                            else:
                                save_data(data)
                                st.success(f"Stimme (Dafür) von {s_user_name} registriert!")
                                st.rerun()

                    with c_btn2:
                        if st.button(
                            "Dagegen 👎",
                            key=f"tab_sug_against_{sugg['id']}",
                            disabled=not s_user_name or has_voted_against,
                        ):
                            if s_user_name in voters_for:
                                voters_for.remove(s_user_name)
                            if s_user_name not in voters_against:
                                voters_against.append(s_user_name)

                            save_data(data)
                            st.info(f"Stimme (Dagegen) von {s_user_name} registriert.")
                            st.rerun()

                st.markdown(
                    '<hr style="border-color:#2a244d; margin:8px 0;">',
                    unsafe_allow_html=True,
                )

        # SPIELE BANNEN (MEHRERE ERLAUBT)
        st.write("---")
        st.subheader("🚫 Spiele aus dem Voting verbannen (Bannen)")
        st.write(
            f"Hier könnt ihr dafür stimmen, ein Spiel komplett aus der Hauptliste zu entfernen. "
            f"Wenn die **Mehrheit ({needed_votes} von {len(player_list)} Spielern)** dafür stimmt, wird das Spiel **automatisch gelöscht**!"
        )

        with st.expander("➕ Spiel zum Bannen vorschlagen", expanded=False):
            ban_author = st.selectbox(
                "Dein Name (Antragsteller):",
                options=["-- Bitte wählen --"] + player_list,
                key="ban_author_select",
            )
            active_game_names = [
                g["name"]
                for g in data.get("games", [])
                if g.get("approved", True)
            ]
            selected_ban_game = st.selectbox(
                "Wähle das Spiel, das gebannt werden soll:",
                options=["-- Bitte wählen --"] + active_game_names,
                key="select_game_to_ban",
            )
            ban_reason_input = st.text_area(
                "Begründung / Verteidigung (Warum sollte es gebannt werden?):",
                key="ban_reason_in",
                placeholder="Spielt keiner mehr, veraltet, macht keinen Spaß...",
            )

            if st.button("Bann-Antrag stellen"):
                if ban_author == "-- Bitte wählen --":
                    st.error("Bitte wähle deinen Namen aus!")
                elif selected_ban_game != "-- Bitte wählen --":
                    data["ban_requests"].append(
                        {
                            "id": max(
                                [
                                    b["id"]
                                    for b in data.get("ban_requests", [])
                                ],
                                default=0,
                            )
                            + 1,
                            "name": selected_ban_game,
                            "author": ban_author,
                            "reason": ban_reason_input.strip(),
                            "voters": [ban_author],
                            "against_voters": [],
                        }
                    )
                    save_data(data)
                    st.success(
                        f"Bann-Antrag für '{selected_ban_game}' von {ban_author} erstellt!"
                    )
                    st.rerun()

        if data.get("ban_requests"):
            st.markdown("### Aktive Bann-Anträge")
            for b_idx, ban in enumerate(list(data["ban_requests"])):
                cb_a, cb_b = st.columns([3, 2])
                ban_voters_for = ban.get("voters", [])
                ban_voters_against = ban.get("against_voters", [])

                has_voted_ban_for = (
                    s_user_name.lower() in [v.lower() for v in ban_voters_for]
                    if s_user_name
                    else False
                )
                has_voted_ban_against = (
                    s_user_name.lower() in [v.lower() for v in ban_voters_against]
                    if s_user_name
                    else False
                )

                with cb_a:
                    st.markdown(f"🚫 **{ban['name']}**")
                    st.caption(f"👤 Antrag von: **{ban.get('author', 'Unbekannt')}**")
                    if ban.get("reason", "").strip():
                        st.markdown(
                            f'<div class="reason-box-red">🔴 <b>Verteidigung / Grund:</b> {ban["reason"].strip()}</div>',
                            unsafe_allow_html=True,
                        )

                    st.caption(
                        f"👍 **{len(ban_voters_for)} / {needed_votes}** Für Bann (Mehrheit) | 👎 **{len(ban_voters_against)}** Gegen Bann"
                    )
                    if ban_voters_for:
                        st.write(f"Für Bann: *{', '.join(ban_voters_for)}*")
                    if ban_voters_against:
                        st.write(f"Gegen Bann: *{', '.join(ban_voters_against)}*")

                with cb_b:
                    cb_btn1, cb_btn2 = st.columns(2)
                    with cb_btn1:
                        if st.button(
                            "Für Bann 🚫",
                            key=f"ban_for_{ban['id']}",
                            disabled=not s_user_name or has_voted_ban_for,
                        ):
                            if s_user_name in ban_voters_against:
                                ban_voters_against.remove(s_user_name)
                            if s_user_name not in ban_voters_for:
                                ban_voters_for.append(s_user_name)

                            # DYNAMISCHE MEHRHEITS-PRÜFUNG FÜR BANN
                            if len(ban_voters_for) >= needed_votes:
                                data["games"] = [
                                    g
                                    for g in data["games"]
                                    if g["name"].lower() != ban["name"].lower()
                                ]
                                data["ban_requests"].pop(b_idx)
                                save_data(data)
                                st.warning(
                                    f"🚫 MEHRHEIT ERREICHT! '{ban['name']}' wurde gebannt und aus der Liste entfernt!"
                                )
                                st.rerun()
                            else:
                                save_data(data)
                                st.success(f"Bann-Stimme von {s_user_name} registriert!")
                                st.rerun()

                    with cb_btn2:
                        if st.button(
                            "Gegen Bann 🛡️",
                            key=f"ban_against_{ban['id']}",
                            disabled=not s_user_name or has_voted_ban_against,
                        ):
                            if s_user_name in ban_voters_for:
                                ban_voters_for.remove(s_user_name)
                            if s_user_name not in ban_voters_against:
                                ban_voters_against.append(s_user_name)

                            save_data(data)
                            st.info(f"Stimme gegen Bann von {s_user_name} registriert.")
                            st.rerun()

                st.markdown(
                    '<hr style="border-color:#2a244d; margin:4px 0;">',
                    unsafe_allow_html=True,
                )

    # TAB 3: GEWINNER-HISTORIE
    with tab_history:
        st.subheader("🏆 Gewinner-Historie")
        if data.get("weekly_winner_history"):
            for h in reversed(data["weekly_winner_history"]):
                with st.expander(
                    f"🗓️ KW {h['kw']} ({h['date']}) — Gewinner: {', '.join(h['winners'])}"
                ):
                    for w_name in h["winners"]:
                        voters = h["voters"].get(w_name, [])
                        voters_str = (
                            ", ".join(voters)
                            if voters
                            else "Keine Stimmen zugewiesen"
                        )
                        st.markdown(
                            f"- 🎮 **{w_name}** — Gevotet von: *{voters_str}*"
                        )
        else:
            st.info("Noch keine Wochen im Verlauf gespeichert.")

    # TAB 4: VISUELLE PICK-STATISTIK
    with tab_stats:
        st.subheader("📊 Spiele-Pick-Statistik & Gesamtwins")
        history = data.get("weekly_winner_history", [])

        if not history:
            st.info(
                "Noch nicht genügend Daten vorhanden. Die Statistik baut sich mit den absolvierten Wochen automatisch auf!"
            )
        else:
            winner_counts = {}
            for entry in history:
                for winner in entry.get("winners", []):
                    clean_w_name = winner.replace(" *(Admin Override)*", "")
                    winner_counts[clean_w_name] = (
                        winner_counts.get(clean_w_name, 0) + 1
                    )

            total_weeks = len(history)

            st.markdown(f"### 🏆 Gewinner-Rangliste (Aus {total_weeks} Wochen)")
            sorted_winners = sorted(
                winner_counts.items(), key=lambda x: x[1], reverse=True
            )

            for g_name, win_cnt in sorted_winners:
                win_percentage = int((win_cnt / total_weeks) * 100)
                st.markdown(
                    f"""
                    <div class="stat-card">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <span style="font-size:1.2rem; font-weight:bold; color:#00f0ff;">🎮 {g_name}</span>
                            <span style="font-size:1.1rem; font-weight:bold; color:#ff77d6;">{win_cnt}x Gewonnen ({win_percentage}%)</span>
                        </div>
                    </div>
                """,
                    unsafe_allow_html=True,
                )
                st.progress(win_percentage / 100)

            st.write("---")
            st.markdown("### 📈 Stimmen-Verteilung aus der Historie")
            all_history_votes = data.get("vote_history", [])
            if all_history_votes:
                game_vote_counts = {}
                for v in all_history_votes:
                    g_n = v.get("game_name", "Unbekannt")
                    game_vote_counts[g_n] = game_vote_counts.get(g_n, 0) + 1

                sorted_votes = sorted(
                    game_vote_counts.items(), key=lambda x: x[1], reverse=True
                )
                total_all_votes = len(all_history_votes)

                for g_n, v_cnt in sorted_votes[:8]:
                    pct = int((v_cnt / total_all_votes) * 100)
                    st.caption(
                        f"**{g_n}** — {v_cnt} Stimmen insgesamt ({pct}%)"
                    )
                    st.progress(pct / 100)
            else:
                st.caption(
                    "Noch keine Stimmen-Logs für die Verteilung vorhanden."
                )

# ==========================================
# SEITE 2: ADMIN-BEREICH
# ==========================================
elif menu == "⚙️ Admin-Bereich":
    st.title("⚙️ Admin Dashboard")

    if st.session_state.get("github_error"):
        st.error(f"⚠️ GitHub-Sync Problem: {st.session_state['github_error']}")

    pwd_input = st.text_input(
        "🔒 Admin-Passwort eingeben:", type="password", key="admin_pwd"
    )

    if pwd_input != ADMIN_PASSWORD:
        if pwd_input != "":
            st.error("Falsches Passwort!")
        else:
            st.info("Bitte Passwort eingeben, um Einstellungen zu öffnen.")
    else:
        st.success("Erfolgreich eingeloggt!")

        tab_adm_games, tab_adm_players, tab_adm_suggs, tab_adm_win_override, tab_adm_status_override, tab_adm_close_week, tab_adm_logs, tab_adm_edit_history, tab_adm_backup = st.tabs(
            [
                "🎮 Spiele verwalten",
                "👥 Spieler-Verwaltung & Votes",
                "📩 Vorschläge & Banns",
                "👑 Gewinner Override",
                "🔓 Vote Status Override",
                "🔄 Woche Abschließen",
                "📊 Index & Logs",
                "✏️ Historie & Stats bearbeiten",
                "💾 Backup & Recovery",
            ]
        )

        with tab_adm_games:
            st.subheader(
                "🎮 Spiele verwalten, Bilder, Links & Notizen anpassen"
            )

            st.markdown("#### Neues Spiel direkt hinzufügen")
            col_add1, col_add2 = st.columns(2)
            with col_add1:
                new_game = st.text_input("Spielname:", key="admin_add_game")
                new_note = st.text_input(
                    "Notiz / Kommentar (z.B. 6 Player Mod):",
                    key="admin_add_note",
                )
            with col_add2:
                new_img_url = st.text_input(
                    "Bild-URL (optional):",
                    key="admin_add_img_url",
                    placeholder="Leer für Steam",
                )
                new_custom_link = st.text_input(
                    "Store/Web Link Override (optional):",
                    key="admin_add_custom_link",
                    placeholder="https://...",
                )

            if st.button("Direkt Hinzufügen (Sofort Aktiv)"):
                if new_game.strip():
                    with st.spinner("Lade Steam-Daten..."):
                        img_auto, store_auto, _ = get_steam_data(
                            new_game.strip()
                        )
                        img_to_use = (
                            new_img_url.strip()
                            if new_img_url.strip()
                            else img_auto
                        )

                    new_id = (
                        max([g["id"] for g in data["games"]], default=0) + 1
                    )
                    data["games"].append(
                        {
                            "id": new_id,
                            "name": new_game.strip(),
                            "votes": 0,
                            "locked": False,
                            "approved": True,
                            "image_url": img_to_use,
                            "store_url": store_auto,
                            "custom_store_url": new_custom_link.strip(),
                            "note": new_note.strip(),
                        }
                    )
                    save_data(data)
                    st.success(f"'{new_game}' hinzugefügt!")
                    st.rerun()

            st.write("---")
            st.markdown("#### Aktuelle Spieleliste, Links & Kommentare")
            for idx, game in enumerate(data["games"]):
                c_img, c_name, c_urls, c_actions = st.columns(
                    [1, 1.5, 2.5, 1.2]
                )
                with c_img:
                    st.image(
                        game.get("image_url", DEFAULT_IMAGE),
                        use_container_width=True,
                    )
                with c_name:
                    st.write(f"**{game['name']}**")
                    if st.button(
                        "🔄 Steam-Daten neu laden",
                        key=f"reload_steam_{game['id']}",
                    ):
                        (
                            game["image_url"],
                            game["store_url"],
                            _,
                        ) = get_steam_data(game["name"])
                        save_data(data)
                        st.success("Steam-Daten aktualisiert!")
                        st.rerun()

                with c_urls:
                    curr_img = game.get("image_url", "")
                    curr_cust_link = game.get("custom_store_url", "")
                    curr_note = game.get("note", "")

                    new_img_val = st.text_input(
                        "Bild-URL Override:",
                        value=str(curr_img),
                        key=f"url_input_{game['id']}",
                    )
                    new_cust_link_val = st.text_input(
                        "Store/Web Link Override:",
                        value=str(curr_cust_link),
                        key=f"custom_link_input_{game['id']}",
                        placeholder="https://...",
                    )
                    new_note_val = st.text_input(
                        "Notiz / Kommentar:",
                        value=str(curr_note),
                        key=f"note_input_{game['id']}",
                        placeholder="z.B. 6 Player Mod",
                    )

                    if st.button(
                        "💾 Änderungen Speichern", key=f"save_urls_{game['id']}"
                    ):
                        game["image_url"] = new_img_val.strip()
                        game["custom_store_url"] = new_cust_link_val.strip()
                        game["note"] = new_note_val.strip()
                        save_data(data)
                        st.success("Spieldaten gespeichert!")
                        st.rerun()

                with c_actions:
                    lock_status = game["locked"] or game["id"] in data.get(
                        "last_winner_ids", []
                    )
                    if st.button(
                        "Entsperren" if lock_status else "Sperren",
                        key=f"admin_lock_{game['id']}",
                    ):
                        game["locked"] = not lock_status
                        if game["id"] in data.get("last_winner_ids", []):
                            data["last_winner_ids"].remove(game["id"])
                        save_data(data)
                        st.rerun()

                    if st.button("🗑️ Löschen", key=f"admin_del_{game['id']}"):
                        data["games"].pop(idx)
                        save_data(data)
                        st.rerun()

                st.markdown(
                    '<hr style="border-color:#2a244d; margin:8px 0;">',
                    unsafe_allow_html=True,
                )

        # TAB 2: SPIELER VERWALTEN UND DIREKTE VOTES PRO SPIELER BEARBEITEN
        with tab_adm_players:
            st.subheader("👥 Spieler-Verwaltung & Einzelne Votes bearbeiten")
            st.write(
                "Hier kannst du Spieler hinzufügen/entfernen und **die abgegebenen Votes für jeden Spieler direkt einsehen und anpassen**!"
            )

            col_p_add1, col_p_add2 = st.columns([2, 1])
            with col_p_add1:
                new_player_name = st.text_input(
                    "Neuen Spielernamen hinzufügen:", key="add_player_in"
                )
            with col_p_add2:
                st.write("")
                st.write("")
                if st.button("➕ Spieler Hinzufügen"):
                    if new_player_name.strip():
                        p_name_clean = new_player_name.strip()
                        if p_name_clean.lower() not in [
                            p.lower() for p in data.get("players", [])
                        ]:
                            data["players"].append(p_name_clean)
                            save_data(data)
                            st.success(f"'{p_name_clean}' wurde hinzugefügt!")
                            st.rerun()
                        else:
                            st.warning("Dieser Name existiert bereits!")

            st.write("---")
            st.markdown("### ✏️ Votes der Spieler bearbeiten")

            all_games_dict = {
                g["id"]: g["name"]
                for g in data.get("games", [])
                if g.get("approved", True)
            }
            game_options_list = list(all_games_dict.keys())

            for p_idx, p_name in enumerate(data.get("players", [])):
                p_lower = p_name.lower()
                curr_voted_ids = data["voted_users"].get(p_lower, [])

                with st.expander(f"👤 Spieler: {p_name} ({len(curr_voted_ids)} Spiele gewählt)"):
                    cp_a, cp_b = st.columns([3, 1])
                    with cp_a:
                        selected_for_p = st.multiselect(
                            f"Ausgewählte Spiele für {p_name}:",
                            options=game_options_list,
                            default=[gid for gid in curr_voted_ids if gid in all_games_dict],
                            format_func=lambda x: all_games_dict.get(x, f"ID {x}"),
                            key=f"adm_multisel_player_{p_idx}",
                        )

                        if st.button(f"💾 Votes für {p_name} speichern", key=f"save_p_votes_{p_idx}"):
                            data["voted_users"][p_lower] = selected_for_p
                            recalculate_game_votes(data)
                            save_data(data)
                            st.success(f"Votes von {p_name} aktualisiert!")
                            st.rerun()

                    with cp_b:
                        if st.button("🗑️ Spieler Löschen", key=f"del_player_{p_idx}"):
                            data["players"].pop(p_idx)
                            if p_lower in data["voted_users"]:
                                del data["voted_users"][p_lower]
                            recalculate_game_votes(data)
                            save_data(data)
                            st.success(f"'{p_name}' entfernt.")
                            st.rerun()

        # TAB 3: VORSCHLÄGE & BANNS FREIGEBEN
        with tab_adm_suggs:
            st.subheader("📩 Ausstehende Vorschläge & Banns verwalten")

            st.markdown("### 💡 Spielvorschläge")
            if data.get("suggestions"):
                for s_idx, sugg in enumerate(list(data["suggestions"])):
                    ca_img, ca, cb, cc = st.columns([1, 2, 1, 1])
                    with ca_img:
                        st.image(
                            sugg.get("image_url", DEFAULT_IMAGE),
                            use_container_width=True,
                        )
                    with ca:
                        st.write(f"🎮 **{sugg['name']}**")
                        st.caption(f"👤 Erstellt von: **{sugg.get('author', 'Unbekannt')}**")
                        if sugg.get("note", "").strip():
                            st.caption(f"💬 Notiz: {sugg['note'].strip()}")
                        if sugg.get("reason", "").strip():
                            st.markdown(
                                f'<div class="reason-box-green">🟢 <b>Begründung:</b> {sugg["reason"].strip()}</div>',
                                unsafe_allow_html=True,
                            )
                    with cb:
                        if st.button(
                            "✅ Sofort Freigeben", key=f"appr_{sugg['id']}"
                        ):
                            new_g_id = (
                                max([g["id"] for g in data["games"]], default=0)
                                + 1
                            )
                            data["games"].append(
                                {
                                    "id": new_g_id,
                                    "name": sugg["name"],
                                    "votes": 0,
                                    "locked": False,
                                    "approved": True,
                                    "image_url": sugg.get(
                                        "image_url", DEFAULT_IMAGE
                                    ),
                                    "store_url": sugg.get("store_url", ""),
                                    "custom_store_url": sugg.get(
                                        "custom_store_url", ""
                                    ),
                                    "note": sugg.get("note", ""),
                                }
                            )
                            data["suggestions"].pop(s_idx)
                            save_data(data)
                            st.success(f"'{sugg['name']}' manuell freigegeben!")
                            st.rerun()
                    with cc:
                        if st.button("❌ Ablehnen", key=f"rej_{sugg['id']}"):
                            data["suggestions"].pop(s_idx)
                            save_data(data)
                            st.info(f"'{sugg['name']}' abgelehnt.")
                            st.rerun()
            else:
                st.info("Keine Vorschläge vorhanden.")

            st.write("---")
            st.markdown("### 🚫 Bann-Anträge")
            if data.get("ban_requests"):
                for b_idx, ban in enumerate(list(data["ban_requests"])):
                    cba, cbb, cbc = st.columns([3, 1, 1])
                    with cba:
                        st.write(f"🚫 **{ban['name']}**")
                        st.caption(f"👤 Antrag von: **{ban.get('author', 'Unbekannt')}**")
                        if ban.get("reason", "").strip():
                            st.markdown(
                                f'<div class="reason-box-red">🔴 <b>Verteidigung / Grund:</b> {ban["reason"].strip()}</div>',
                                unsafe_allow_html=True,
                            )
                        st.caption(
                            f"Stimmen: {len(ban.get('voters', []))} Dafür / {len(ban.get('against_voters', []))} Dagegen"
                        )
                    with cbb:
                        if st.button(
                            "✅ Sofort Bannen", key=f"appr_ban_{ban['id']}"
                        ):
                            data["games"] = [
                                g
                                for g in data["games"]
                                if g["name"].lower() != ban["name"].lower()
                            ]
                            data["ban_requests"].pop(b_idx)
                            save_data(data)
                            st.warning(f"'{ban['name']}' wurde gebannt!")
                            st.rerun()
                    with cbc:
                        if st.button(
                            "❌ Bann Ablehnen", key=f"rej_ban_{ban['id']}"
                        ):
                            data["ban_requests"].pop(b_idx)
                            save_data(data)
                            st.info(f"Bann-Antrag für '{ban['name']}' abgelehnt.")
                            st.rerun()
            else:
                st.info("Keine aktiven Bann-Anträge.")

        with tab_adm_win_override:
            st.subheader("👑 Gewinner manuell festlegen")
            game_options = {
                g["name"]: g["id"]
                for g in data["games"]
                if g.get("approved", True)
            }
            current_override = [
                g["name"]
                for g in data["games"]
                if g["id"] in data.get("override_winner_ids", [])
            ]

            selected_overrides = st.multiselect(
                "Wähle Spiele als feste Gewinner:",
                options=list(game_options.keys()),
                default=current_override,
                max_selections=2,
            )

            col_ov1, col_ov2 = st.columns(2)
            with col_ov1:
                if st.button("💾 Gewinner-Override Speichern"):
                    data["override_winner_ids"] = [
                        game_options[name] for name in selected_overrides
                    ]
                    save_data(data)
                    st.success("Override gespeichert!")
                    st.rerun()

            with col_ov2:
                if st.button("❌ Override Aufheben"):
                    data["override_winner_ids"] = []
                    save_data(data)
                    st.info(
                        "Override entfernt. Es zählen wieder normale Stimmen."
                    )
                    st.rerun()

        with tab_adm_status_override:
            st.subheader("🔓 Manuelles Öffnen / Schließen des Votings")
            current_status = data.get("manual_status_override", "AUTO")
            st.write(f"Aktueller Modus: **{current_status}**")

            col_status1, col_status2, col_status3 = st.columns(3)

            with col_status1:
                if st.button("🟢 Immer ÖFFNEN"):
                    data["manual_status_override"] = "OPEN"
                    data["admin_status_logs"].append(
                        {
                            "timestamp": get_now().strftime(
                                "%Y-%m-%d %H:%M:%S"
                            ),
                            "action": "Voting MANUELL GEÖFFNET",
                        }
                    )
                    save_data(data)
                    st.success("Voting ist nun manuell geöffnet!")
                    st.rerun()

            with col_status2:
                if st.button("🔴 Immer SPERREN"):
                    data["manual_status_override"] = "CLOSED"
                    data["admin_status_logs"].append(
                        {
                            "timestamp": get_now().strftime(
                                "%Y-%m-%d %H:%M:%S"
                            ),
                            "action": "Voting MANUELL GESCHLOSSEN",
                        }
                    )
                    save_data(data)
                    st.warning("Voting ist nun manuell gesperrt!")
                    st.rerun()

            with col_status3:
                if st.button("🔄 AUTOMATIK (Zeitplan)"):
                    data["manual_status_override"] = "AUTO"
                    data["admin_status_logs"].append(
                        {
                            "timestamp": get_now().strftime(
                                "%Y-%m-%d %H:%M:%S"
                            ),
                            "action": "Zurück auf AUTOMATISCHEN Zeitplan",
                        }
                    )
                    save_data(data)
                    st.info("Automatischer Zeitplan wiederhergestellt.")
                    st.rerun()

        with tab_adm_close_week:
            st.subheader("🔄 Woche Abschließen & Historie Speichern")
            st.write(
                "Beim Abschließen werden die Gewinner ermittelt, in der Historie gespeichert, in der Statistik erfasst, für 1 Woche gesperrt und **das Voting wird geschlossen**."
            )

            if st.button("Woche JETZT abschließen"):
                winners, tie_occurred, tie_msg, is_ov_active = get_top_winners(
                    data
                )
                winner_ids = [w["id"] for w in winners]

                winner_names_history = []
                voters_map = {}

                for w in winners:
                    w_name = w["name"]
                    w_name_recorded = (
                        f"{w_name} *(Admin Override)*"
                        if is_ov_active
                        else w_name
                    )
                    winner_names_history.append(w_name_recorded)

                    voters_map[w_name_recorded] = []
                    w_id = w["id"]
                    for user, voted_g_ids in data["voted_users"].items():
                        if w_id in voted_g_ids:
                            voters_map[w_name_recorded].append(user.capitalize())

                history_entry = {
                    "date": get_now().strftime("%d.%m.%Y"),
                    "kw": get_now().isocalendar()[1],
                    "winners": winner_names_history,
                    "voters": voters_map,
                }
                data["weekly_winner_history"].append(history_entry)

                if tie_occurred:
                    data["randomizer_logs"].append(
                        {
                            "timestamp": get_now().strftime(
                                "%Y-%m-%d %H:%M:%S"
                            ),
                            "kw": get_now().isocalendar()[1],
                            "message": tie_msg,
                        }
                    )

                data["last_winner_ids"] = winner_ids
                data["override_winner_ids"] = []
                data["voted_users"] = {}
                data["manual_status_override"] = "CLOSED"
                data["admin_status_logs"].append(
                    {
                        "timestamp": get_now().strftime("%Y-%m-%d %H:%M:%S"),
                        "action": f"Woche abgeschlossen -> Gewinner: {', '.join(winner_names_history)}",
                    }
                )

                for g in data["games"]:
                    g["votes"] = 0

                save_data(data)
                st.success(
                    "Woche abgeschlossen! Gewinner in Historie & Statistik erfasst, gesperrt & Voting auf GESCHLOSSEN gesetzt."
                )
                st.rerun()

        with tab_adm_logs:
            st.subheader("📋 Registrierter Voting-Index")
            if data["vote_history"]:
                st.dataframe(
                    list(reversed(data["vote_history"])),
                    use_container_width=True,
                )
            else:
                st.info("Keine Einträge.")

            st.write("---")
            st.subheader("⚠️ Admin-Status Override Logs")
            if data.get("admin_status_logs"):
                for a_log in reversed(data["admin_status_logs"]):
                    st.caption(f"**[{a_log['timestamp']}]:** {a_log['action']}")
            else:
                st.caption("Keine Status-Übersteuerungen vorhanden.")

        # TAB: HISTORIE & STATISTIK-BEARBEITUNG
        with tab_adm_edit_history:
            st.subheader(
                "✏️ Gewinner-Historie & Statistik-Daten verwalten"
            )
            st.write(
                "Hier kannst du vergangene Gewinner manuell zur Historie hinzufügen, gelistete Spieler pro Spiel anpassen oder Einträge löschen. "
                "**Verknüpft mit deiner aktuellen Spieler-Verwaltung!**"
            )

            current_player_list = data.get("players", DEFAULT_USERS)

            # FORMULAR: NEUEN HISTORIEN-EINTRAG HINZUFÜGEN
            with st.expander(
                "➕ Gewinner manuell zur Historie/Statistik hinzufügen",
                expanded=False,
            ):
                all_game_names = [
                    g["name"]
                    for g in data.get("games", [])
                    if g.get("approved", True)
                ]

                col_h_add1, col_h_add2 = st.columns(2)
                with col_h_add1:
                    manual_date = st.text_input(
                        "Datum (z.B. DD.MM.YYYY):",
                        value=get_now().strftime("%d.%m.%Y"),
                        key="man_h_date",
                    )
                    manual_kw = st.number_input(
                        "Kalenderwoche (KW):",
                        value=get_now().isocalendar()[1],
                        min_value=1,
                        max_value=53,
                        key="man_h_kw",
                    )
                with col_h_add2:
                    manual_winners = st.multiselect(
                        "Gewinner-Spiele wählen (max. 2):",
                        options=all_game_names,
                        max_selections=2,
                        key="man_h_winners",
                    )

                voters_map_man = {}
                if manual_winners:
                    st.write("**Spieler für ausgewählte Gewinner zuweisen:**")
                    for m_w in manual_winners:
                        sel_v = st.multiselect(
                            f"👥 Wer hat gestimmt für '{m_w}'?",
                            options=current_player_list,
                            key=f"man_voters_{m_w}",
                        )
                        voters_map_man[m_w] = sel_v

                if st.button("➕ Gewinner in Historie Speichern"):
                    if manual_winners:
                        new_h_entry = {
                            "date": manual_date.strip(),
                            "kw": int(manual_kw),
                            "winners": manual_winners,
                            "voters": voters_map_man,
                        }
                        data["weekly_winner_history"].append(new_h_entry)
                        save_data(data)
                        st.success(
                            f"Gewinner {', '.join(manual_winners)} erfolgreich zur Historie hinzugefügt!"
                        )
                        st.rerun()
                    else:
                        st.warning("Bitte wähle mindestens 1 Gewinner-Spiel aus!")

            st.write("---")
            st.markdown("### 🏆 Vorhandene Wochen-Historie bearbeiten")
            weekly_hist = data.get("weekly_winner_history", [])

            if not weekly_hist:
                st.info("Keine Wochen-Historie vorhanden.")
            else:
                for idx_h, h_entry in enumerate(list(reversed(weekly_hist))):
                    real_idx = len(weekly_hist) - 1 - idx_h

                    with st.expander(
                        f"🗓️ KW {h_entry.get('kw')} ({h_entry.get('date')}) — Gewinner: {', '.join(h_entry.get('winners', []))}"
                    ):
                        st.markdown("#### Spieler pro Spiel anpassen:")

                        if "voters" not in h_entry:
                            h_entry["voters"] = {}

                        updated_voters_map = {}
                        for w_game in h_entry.get("winners", []):
                            curr_voters = h_entry["voters"].get(w_game, [])
                            valid_defaults = [
                                v for v in curr_voters if v in current_player_list
                            ]

                            new_voters_sel = st.multiselect(
                                f"👥 Spieler für '{w_game}':",
                                options=current_player_list,
                                default=valid_defaults,
                                key=f"edit_voters_{real_idx}_{w_game}",
                            )
                            updated_voters_map[w_game] = new_voters_sel

                        col_eh1, col_eh2 = st.columns(2)
                        with col_eh1:
                            if st.button(
                                "💾 Spieler-Änderungen Speichern",
                                key=f"save_h_voters_{real_idx}",
                            ):
                                h_entry["voters"] = updated_voters_map
                                save_data(data)
                                st.success("Änderungen gespeichert!")
                                st.rerun()

                        with col_eh2:
                            if st.button(
                                "🗑️ Ganze Woche löschen",
                                key=f"del_hist_{real_idx}",
                            ):
                                data["weekly_winner_history"].pop(real_idx)
                                save_data(data)
                                st.success("Wochen-Eintrag gelöscht!")
                                st.rerun()

            st.write("---")
            st.markdown("### 📈 Stimmen-Logs bereinigen")
            v_hist = data.get("vote_history", [])

            if not v_hist:
                st.info("Keine Voting-Logs vorhanden.")
            else:
                with st.expander("Einzelne Stimmen einsehen & löschen"):
                    for idx_v, v_entry in enumerate(list(reversed(v_hist))):
                        real_v_idx = len(v_hist) - 1 - idx_v
                        cv_a, cv_b = st.columns([3, 1])
                        with cv_a:
                            st.caption(
                                f"[{v_entry.get('timestamp')}] User: **{v_entry.get('user')}** ➔ Games: **{v_entry.get('voted_games_count', 1)}** (KW {v_entry.get('kw')})"
                            )
                        with cv_b:
                            if st.button(
                                "🗑️ Löschen", key=f"del_vote_log_{real_v_idx}"
                            ):
                                data["vote_history"].pop(real_v_idx)
                                save_data(data)
                                st.success("Stimm-Log gelöscht!")
                                st.rerun()

        with tab_adm_backup:
            st.subheader("💾 Manuelles Daten-Backup & Wiederherstellung")
            col_bk1, col_bk2 = st.columns(2)

            with col_bk1:
                st.markdown("### 📥 Backup Herunterladen")
                json_data = json.dumps(data, ensure_ascii=False, indent=4)
                st.download_button(
                    label="💾 data.json herunterladen",
                    data=json_data,
                    file_name=f"data_backup_{get_now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json",
                )

            with col_bk2:
                st.markdown("### 📤 Backup Wiederherstellen")
                uploaded_file = st.file_uploader(
                    "Lade eine data.json hoch:", type=["json"]
                )
                if uploaded_file is not None:
                    try:
                        restored_data = json.load(uploaded_file)
                        if st.button("⚠️ Backup JETZT einspielen"):
                            save_data(restored_data)
                            st.success("Daten erfolgreich wiederhergestellt!")
                            st.rerun()
                    except Exception as e:
                        st.error(f"Fehler beim Lesen der Datei: {e}")
