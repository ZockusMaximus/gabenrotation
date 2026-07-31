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
            if "custom_store_url" not in s:
                s["custom_store_url"] = ""
            if "note" not in s:
                s["note"] = ""
            if "store_url" not in s or not s["store_url"]:
                _, s["store_url"], _ = get_steam_data(s["name"])
            if "image_url" not in s or not s["image_url"]:
                s["image_url"], _, _ = get_steam_data(s["name"])

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
            "💡 Spielvorschläge",
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

                    # CONTAINER FÜR GEWINNERKARTE MIT NEON BORDERN
                    with st.container():
                        st.markdown(
                            """<div style="height: 4px; background: #00f0ff; border-radius: 4px; box-shadow: 0 0 8px #00f0ff; margin-bottom: 8px;"></div>""",
                            unsafe_allow_html=True,
                        )
                        st.image(img_src, use_container_width=True)
                        st.markdown(
                            f"<h3 style='margin:5px 0; text-align:center;'>{g_name}</h3>",
                            unsafe_allow_html=True,
                        )

                        if g_note:
                            st.markdown(
                                f"<div style='text-align:center;'><span class='game-note-badge'>💬 {g_note}</span></div>",
                                unsafe_allow_html=True,
                            )

                        st.markdown(
                            f"<div style='color:#cbd5e1; font-size:0.95rem; text-align:center; margin:8px 0;'>📊 <b>{g_votes}</b> Stimmen</div>",
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
                            """<div style="height: 4px; background: #00f0ff; border-radius: 4px; box-shadow: 0 0 8px #00f0ff; margin-top: 12px; margin-bottom: 15px;"></div>""",
                            unsafe_allow_html=True,
                        )

        st.write("---")
        st.subheader("🎮 Spieleliste")

        already_voted_users = [
            u.lower() for u in data.get("voted_users", {}).keys()
        ]
        available_users = [
            name
            for name in data.get("players", DEFAULT_USERS)
            if name.lower() not in already_voted_users
        ]

        if available_users:
            user_name = st.selectbox(
                "Wähle deinen Namen aus (erforderlich zum Voten):",
                options=["-- Bitte wählen --"] + available_users,
            )
            if user_name == "-- Bitte wählen --":
                user_name = ""
        else:
            st.info("🎉 Alle Spieler haben in dieser Woche bereits abgestimmt!")
            user_name = ""

        user_voted_games = (
            data["voted_users"].get(user_name.lower(), []) if user_name else []
        )
        public_games = [g for g in data["games"] if g.get("approved", True)]

        for game in public_games:
            col_img, col1, col2, col3 = st.columns([1.5, 2.5, 1, 2])
            is_locked = game["locked"] or game["id"] in data.get(
                "last_winner_ids", []
            )
            has_voted_this_game = (
                game["id"] in user_voted_games if user_name else False
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
                button_disabled = (
                    not is_open
                    or is_locked
                    or not user_name
                    or has_voted_this_game
                )
                button_label = "Gevotet ✅" if has_voted_this_game else "Voten"

                if st.button(
                    button_label,
                    key=f"vote_{game['id']}",
                    disabled=button_disabled,
                ):
                    game["votes"] += 1
                    if user_name.lower() not in data["voted_users"]:
                        data["voted_users"][user_name.lower()] = []
                    data["voted_users"][user_name.lower()].append(game["id"])

                    log_entry = {
                        "timestamp": get_now().strftime("%Y-%m-%d %H:%M:%S"),
                        "kw": get_now().isocalendar()[1],
                        "user": user_name,
                        "game_id": game["id"],
                        "game_name": game["name"],
                    }
                    data["vote_history"].append(log_entry)

                    save_data(data)
                    st.success(
                        f"Stimme von {user_name} für '{game['name']}' registriert!"
                    )
                    st.rerun()

            st.markdown(
                '<hr style="border-color:#2a244d; margin:5px 0 15px 0;">',
                unsafe_allow_html=True,
            )

    # TAB 2: SPIELVORSCHLÄGE
    with tab_suggestions:
        st.subheader("💡 Spielvorschläge")
        st.write(
            "Schlagt hier neue Spiele vor! Sobald **ALLE Spieler einstimmig** für einen Vorschlag gestimmt haben, wandert das Spiel **automatisch in die Haupt-Spieleliste**!"
        )

        with st.expander("➕ Neues Spiel vorschlagen", expanded=False):
            col_s1, col_s2 = st.columns(2)
            with col_s1:
                suggested_name = st.text_input(
                    "Spielname eingeben:",
                    key="tab_sug_name_in",
                    placeholder="z.B. Valheim",
                )
                suggested_note = st.text_input(
                    "Notiz / Kommentar (optional):",
                    key="tab_sug_note_in",
                    placeholder="z.B. 6 Player Mod",
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
                if suggested_name.strip():
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
                        st.warning("Dieses Spiel existiert bereits!")
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
                                "image_url": img_final,
                                "store_url": store_url_auto,
                                "custom_store_url": suggested_link.strip(),
                                "note": suggested_note.strip(),
                                "voters": [],
                            }
                        )
                        save_data(data)
                        st.success(f"Vorschlag '{clean_name}' eingereicht!")
                        st.rerun()

        st.write("---")
        player_list = data.get("players", DEFAULT_USERS)
        selected_s_user = st.selectbox(
            "Wähle deinen Namen zum Abstimmen für Vorschläge:",
            options=["-- Bitte wählen --"] + player_list,
            key="tab_sug_user_select",
        )
        s_user_name = (
            "" if selected_s_user == "-- Bitte wählen --" else selected_s_user
        )

        if not data.get("suggestions"):
            st.info("Aktuell gibt es keine offenen Spielvorschläge.")
        else:
            total_players_needed = len(player_list)

            for s_idx, sugg in enumerate(list(data["suggestions"])):
                sc_img, sc_info, sc_vote = st.columns([1.5, 3, 2])
                has_voted_sugg = (
                    s_user_name.lower()
                    in [v.lower() for v in sugg.get("voters", [])]
                    if s_user_name
                    else False
                )
                voters_count = len(sugg.get("voters", []))

                with sc_img:
                    st.image(
                        sugg.get("image_url", DEFAULT_IMAGE),
                        use_container_width=True,
                    )

                    c_sugg_link = sugg.get("custom_store_url", "").strip()
                    s_sugg_link = sugg.get("store_url", "").strip()

                    if c_sugg_link:
                        st.markdown(
                            f'<a href="{c_sugg_link}" target="_blank" class="custom-web-btn">🌐 Website / Store</a>',
                            unsafe_allow_html=True,
                        )
                    elif s_sugg_link:
                        st.markdown(
                            f'<a href="{s_sugg_link}" target="_blank" class="steam-btn">🛒 Steam Store</a>',
                            unsafe_allow_html=True,
                        )

                with sc_info:
                    st.markdown(f"### {sugg['name']}")
                    if sugg.get("note", "").strip():
                        st.markdown(
                            f'<div class="game-note-badge">💬 {sugg["note"].strip()}</div>',
                            unsafe_allow_html=True,
                        )
                    st.caption(
                        f"👍 **{voters_count} / {total_players_needed}** Stimmen für Einstimmigkeit"
                    )
                    if sugg.get("voters"):
                        st.write(
                            f"Bisher dafür gestimmt: *{', '.join(sugg['voters'])}*"
                        )
                    else:
                        st.write("*Noch keine Stimmen abgegeben*")

                with sc_vote:
                    btn_disabled = not s_user_name or has_voted_sugg
                    btn_txt = (
                        "Dafür gestimmt ✅"
                        if has_voted_sugg
                        else "Dafür stimmen 👍"
                    )

                    if st.button(
                        btn_txt,
                        key=f"tab_sug_btn_{sugg['id']}",
                        disabled=btn_disabled,
                    ):
                        sugg["voters"].append(s_user_name)

                        current_voters_lower = [
                            v.lower() for v in sugg["voters"]
                        ]
                        all_players_lower = [p.lower() for p in player_list]

                        is_unanimous = all(
                            p in current_voters_lower for p in all_players_lower
                        )

                        if is_unanimous:
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
                            st.balloons()
                            st.success(
                                f"🎉 EINSTIMMIG! '{sugg['name']}' wurde in die Hauptliste aufgenommen!"
                            )
                            st.rerun()
                        else:
                            save_data(data)
                            st.success(
                                f"Stimme von {s_user_name} registriert!"
                            )
                            st.rerun()

                st.markdown(
                    '<hr style="border-color:#2a244d; margin:8px 0;">',
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
                    # KORREKTUR: BEREINIGUNG DES OVERRIDE TGS FÜR STATISTIK
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

        tab_adm_games, tab_adm_players, tab_adm_suggs, tab_adm_win_override, tab_adm_status_override, tab_adm_close_week, tab_adm_logs, tab_adm_backup = st.tabs(
            [
                "🎮 Spiele verwalten",
                "👥 Spieler-Verwaltung",
                "📩 Vorschläge freigeben",
                "👑 Gewinner Override",
                "🔓 Vote Status Override",
                "🔄 Woche Abschließen",
                "📊 Index & Logs",
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

        with tab_adm_players:
            st.subheader("👥 Spieler-Verwaltung (Dropdown & Einstimmigkeit)")
            st.write(
                "Hier kannst du die Spielernamen verwalten. Diese Liste bestimmt, welche Namen im Dropdown auswählbar sind "
                "und wie viele Stimmen für eine Einstimmigkeit bei Vorschlägen benötigt werden."
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
            st.subheader("Aktuelle Spielerliste")
            for p_idx, p_name in enumerate(data.get("players", [])):
                cp1, cp2 = st.columns([3, 1])
                with cp1:
                    st.markdown(f"👤 **{p_name}**")
                with cp2:
                    if st.button("🗑️ Entfernen", key=f"del_player_{p_idx}"):
                        data["players"].pop(p_idx)
                        save_data(data)
                        st.success(f"'{p_name}' entfernt.")
                        st.rerun()

        with tab_adm_suggs:
            st.subheader("📩 Ausstehende Vorschläge manuell freigeben")
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
                        if sugg.get("note", "").strip():
                            st.caption(f"💬 Notiz: {sugg['note'].strip()}")
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

        # TAB 6: WOCHE ABSCHLIESSEN (ERWEITERT UM OVERRIDE IN HISTORIE & STATISTIK)
        with tab_adm_close_week:
            st.subheader("🔄 Woche Abschließen & Historie Speichern")
            st.write(
                "Beim Abschließen werden die Gewinner ermittelt (inkl. evtl. aktiver Admin-Overrides), in der Historie gespeichert, in der Statistik erfasst, für 1 Woche gesperrt und **das Voting wird geschlossen**."
            )

            if st.button("Woche JETZT abschließen"):
                winners, tie_occurred, tie_msg, is_ov_active = get_top_winners(
                    data
                )
                winner_ids = [w["id"] for w in winners]

                # Richtiges Speichern für Historie
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
                            voters_map[w_name_recorded].append(user)

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
