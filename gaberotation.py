from datetime import datetime, timedelta
import json
import os
import random
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

# VORGEGEBENE SPIELERLISTE FÜR DAS DROPDOWN
ALLOWED_USERS = ["Sascha", "Alexander", "Victor", "Marcel", "Jan", "Stefan"]


# --- DEUTSCHE ZEIT HILFSFUNKTIONEN ---
def get_now():
    """Gibt die aktuelle Uhrzeit in der deutschen Zeitzone (Europe/Berlin) zurück."""
    return datetime.now(GERMANY_TZ)


def get_next_game_night():
    """Berechnet das Datum und die Uhrzeit (20:00 Uhr) der nächsten Game Night (Freitag)."""
    now = get_now()
    weekday = now.weekday()  # 0 = Mo, 4 = Fr, 6 = So

    if weekday == 4 and now.hour < 20:
        days_ahead = 0
    else:
        days_ahead = (4 - weekday) % 7
        if days_ahead == 0:
            days_ahead = 7

    next_friday = now + timedelta(days=days_ahead)
    return next_friday.replace(hour=20, minute=0, second=0, microsecond=0)


# --- OPTION 2: GITHUB AUTOMATISCHE SYNC FUNKTION ---
def push_to_github(data_content):
    """Speichert die data.json automatisch direkt in das GitHub Repository."""
    try:
        # Secrets prüfen
        token = st.secrets.get("GITHUB_TOKEN")
        repo = st.secrets.get("GITHUB_REPO")
        file_path = st.secrets.get("GITHUB_FILE_PATH", "data.json")

        if not token or not repo:
            return  # Falls Secrets nicht konfiguriert sind, überspringen

        url = f"https://api.github.com/repos/{repo}/contents/{file_path}"
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
        }

        # 1. Aktuellen SHA der Datei abrufen (erforderlich für Updates)
        get_res = requests.get(url, headers=headers, timeout=5)
        sha = get_res.json().get("sha") if get_res.status_code == 200 else None

        # 2. Datei codieren & hochladen
        import base64

        json_str = json.dumps(data_content, ensure_ascii=False, indent=4)
        content_b64 = base64.b64encode(json_str.encode("utf-8")).decode("utf-8")

        payload = {
            "message": "Auto-update data.json via Streamlit Voting App",
            "content": content_b64,
        }
        if sha:
            payload["sha"] = sha

        requests.put(url, headers=headers, json=payload, timeout=5)
    except Exception:
        pass  # Wenn der Sync fehlschlägt, läuft die App ohne Absturz lokal weiter


# --- DATENBANK FUNKTIONEN ---
def load_data():
    if not os.path.exists(DATA_FILE):
        default_data = {
            "games": [
                {
                    "id": 1,
                    "name": "Counter-Strike 2",
                    "votes": 0,
                    "locked": False,
                    "approved": True,
                    "image_url": "https://cdn.akamai.steamstatic.com/steam/apps/730/header.jpg",
                },
                {
                    "id": 2,
                    "name": "Peak",
                    "votes": 0,
                    "locked": False,
                    "approved": True,
                    "image_url": "https://cdn.akamai.steamstatic.com/steam/apps/3527290/header.jpg",
                },
                {
                    "id": 3,
                    "name": "Repo",
                    "votes": 0,
                    "locked": False,
                    "approved": True,
                    "image_url": "https://cdn.akamai.steamstatic.com/steam/apps/2822280/header.jpg",
                },
                {
                    "id": 4,
                    "name": "Meccha Chameleon",
                    "votes": 0,
                    "locked": False,
                    "approved": True,
                    "image_url": "https://cdn.akamai.steamstatic.com/steam/apps/4704690/header.jpg",
                },
                {
                    "id": 5,
                    "name": "Buckshot Roulette",
                    "votes": 0,
                    "locked": False,
                    "approved": True,
                    "image_url": "https://cdn.akamai.steamstatic.com/steam/apps/2835570/header.jpg",
                },
                {
                    "id": 6,
                    "name": "Team Fortress 2",
                    "votes": 0,
                    "locked": False,
                    "approved": True,
                    "image_url": "https://cdn.akamai.steamstatic.com/steam/apps/440/header.jpg",
                },
                {
                    "id": 7,
                    "name": "Worms W.M.D",
                    "votes": 0,
                    "locked": False,
                    "approved": True,
                    "image_url": "https://cdn.akamai.steamstatic.com/steam/apps/327030/header.jpg",
                },
                {
                    "id": 8,
                    "name": "SpeedRunners",
                    "votes": 0,
                    "locked": False,
                    "approved": True,
                    "image_url": "https://cdn.akamai.steamstatic.com/steam/apps/207140/header.jpg",
                },
            ],
            "voted_users": {},
            "last_winner_ids": [],
            "override_winner_ids": [],
            "manual_status_override": "AUTO",
            "vote_history": [],
            "randomizer_logs": [],
            "admin_status_logs": [],
            "weekly_winner_history": [],
        }
        save_data(default_data)
        return default_data

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

        for g in data.get("games", []):
            if "approved" not in g:
                g["approved"] = True
            if (
                "image_url" not in g
                or not g["image_url"]
                or g["image_url"] == "0"
                or str(g["image_url"]).isdigit()
            ):
                g["image_url"] = DEFAULT_IMAGE

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
    # Local speichern
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    # Option 2: Automatisch zu GitHub pushen
    push_to_github(data)


# --- ZEIT & SCHLIESS-LOGIK ---
def get_voting_time_status(data):
    now = get_now()
    weekday = now.weekday()
    hour = now.hour

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
            return override_games, False, "Manuelles Override"

    active_games = [g for g in approved_games if g["votes"] > 0]
    if not active_games:
        return [], False, "Keine Stimmen abgegeben"

    sorted_games = sorted(active_games, key=lambda x: x["votes"], reverse=True)
    if len(sorted_games) <= 2:
        return sorted_games, False, "Eindeutiges Ergebnis"

    first_votes = sorted_games[0]["votes"]
    first_candidates = [g for g in sorted_games if g["votes"] == first_votes]

    if len(first_candidates) >= 2:
        selected = random.sample(first_candidates, 2)
        log_msg = f"Gleichstand Platz 1 ({first_votes} Stimmen). Gelost: {[g['name'] for g in selected]}"
        return selected, True, log_msg

    winner_1 = sorted_games[0]
    second_votes = sorted_games[1]["votes"]
    second_candidates = [g for g in sorted_games if g["votes"] == second_votes]

    if len(second_candidates) > 1:
        winner_2 = random.choice(second_candidates)
        log_msg = f"Gleichstand Platz 2 ({second_votes} Stimmen). Gelost: {winner_2['name']}"
        return [winner_1, winner_2], True, log_msg

    return [winner_1, sorted_games[1]], False, "Eindeutiges Ergebnis"


# --- APP STYLING (VAPORWAVE PALETTE) ---
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
    </style>
""",
    unsafe_allow_html=True,
)

data = load_data()
menu = st.sidebar.radio("Navigation", ["🎮 Abstimmung", "⚙️ Admin-Bereich"])

# ==========================================
# SEITE 1: ABSTIMMUNG
# ==========================================
if menu == "🎮 Abstimmung":
    st.markdown(
        """
        <div class="brand-banner">
            <h1 class="brand-title">ZOCKUS MAXIMUS</h1>
            <div class="brand-subtitle">FRIDAY GAME NIGHT</div>
        </div>
    """,
        unsafe_allow_html=True,
    )

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

    tab_vote, tab_history = st.tabs(
        ["🗳️ Aktuelle Abstimmung", "🏆 Öffentliche Gewinner-Historie"]
    )

    with tab_vote:
        top_winners, tie_occurred, tie_msg = get_top_winners(data)
        if top_winners:
            st.markdown(
                """
                <div class="winner-box">
                    <h3 style="color:#00f0ff; margin:0; font-family:'Montserrat'; font-weight:800;">🏆 AKTUELLE TOP-2 FAVORITEN</h3>
                </div>
            """,
                unsafe_allow_html=True,
            )
            col_w1, col_w2 = st.columns(2)
            if len(top_winners) > 0:
                col_w1.metric(
                    label="Platz 1",
                    value=top_winners[0]["name"],
                    delta=f"{top_winners[0]['votes']} Stimmen",
                )
            if len(top_winners) > 1:
                col_w2.metric(
                    label="Platz 2",
                    value=top_winners[1]["name"],
                    delta=f"{top_winners[1]['votes']} Stimmen",
                )

        st.write("---")

        with st.expander("➕ Neues Spiel vorschlagen", expanded=False):
            suggested_game = st.text_input(
                "Spielname eingeben:",
                key="suggest_input",
                placeholder="z.B. Valheim",
            )
            if st.button("Vorschlag einreichen"):
                if suggested_game.strip():
                    existing_names = [g["name"].lower() for g in data["games"]]
                    if suggested_game.strip().lower() in existing_names:
                        st.warning("Dieses Spiel steht bereits auf der Liste!")
                    else:
                        new_id = (
                            max([g["id"] for g in data["games"]], default=0) + 1
                        )
                        data["games"].append(
                            {
                                "id": new_id,
                                "name": suggested_game.strip(),
                                "votes": 0,
                                "locked": False,
                                "approved": False,
                                "image_url": DEFAULT_IMAGE,
                            }
                        )
                        save_data(data)
                        st.info(
                            f"Vorschlag '{suggested_game.strip()}' eingereicht! Wartet auf Admin-Freigabe."
                        )
                        st.rerun()

        st.subheader("🎮 Spieleliste")

        already_voted_users = [
            u.lower() for u in data.get("voted_users", {}).keys()
        ]
        available_users = [
            name
            for name in ALLOWED_USERS
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

            with col1:
                if is_locked:
                    st.markdown(f"**{game['name']}** 🚫 *(Vorwoche Gewinner)*")
                else:
                    st.markdown(f"### {game['name']}")

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

    with tab_history:
        st.subheader("📜 Gewinner vergangener Wochen")
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

# ==========================================
# SEITE 2: ADMIN-BEREICH (PASSWORTGESCHÜTZT)
# ==========================================
elif menu == "⚙️ Admin-Bereich":
    st.title("⚙️ Admin Dashboard")

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

        tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(
            [
                "🔓 Vote Status Override",
                "📩 Vorschläge freigeben",
                "📊 Voting Index & Logs",
                "👑 Gewinner Override",
                "🔄 Woche Abschließen",
                "🎮 Spiele Verwalten",
                "💾 Backup & Recovery",  # OPTION 3: MANUELLES BACKUP
            ]
        )

        with tab1:
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

        with tab2:
            st.subheader("📩 Eingereichte Spielvorschläge")
            unapproved_games = [
                g for g in data["games"] if not g.get("approved", True)
            ]

            if unapproved_games:
                st.write(
                    f"Es liegen **{len(unapproved_games)}** Vorschlag/Vorschläge vor:"
                )
                for un_game in unapproved_games:
                    ca_img, ca, cb, cc = st.columns([1, 2, 1, 1])
                    with ca_img:
                        st.image(
                            un_game.get("image_url", DEFAULT_IMAGE),
                            use_container_width=True,
                        )
                    with ca:
                        st.write(f"🎮 **{un_game['name']}**")
                    with cb:
                        if st.button(
                            "✅ Freigeben", key=f"appr_{un_game['id']}"
                        ):
                            un_game["approved"] = True
                            save_data(data)
                            st.success(f"'{un_game['name']}' wurde freigegeben!")
                            st.rerun()
                    with cc:
                        if st.button("❌ Ablehnen", key=f"rej_{un_game['id']}"):
                            data["games"] = [
                                g
                                for g in data["games"]
                                if g["id"] != un_game["id"]
                            ]
                            save_data(data)
                            st.info(f"'{un_game['name']}' wurde abgelehnt.")
                            st.rerun()
            else:
                st.info("Keine ausstehenden Vorschläge vorhanden.")

        with tab3:
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

            st.write("---")
            st.subheader("🎲 Randomizer Logs")
            if data["randomizer_logs"]:
                for r_log in reversed(data["randomizer_logs"]):
                    st.warning(f"**[{r_log['timestamp']}]:** {r_log['message']}")

        with tab4:
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
                "Wähle 2 Spiele als feste Gewinner:",
                options=list(game_options.keys()),
                default=current_override,
                max_selections=2,
            )

            if st.button("Gewinner-Override Speichern"):
                data["override_winner_ids"] = [
                    game_options[name] for name in selected_overrides
                ]
                save_data(data)
                st.success("Gespeichert!")
                st.rerun()

        with tab5:
            st.subheader("🔄 Woche Abschließen & Historie Speichern")
            st.write(
                "Beim Abschließen werden die Gewinner ermittelt, in der Historie gespeichert, für 1 Woche gesperrt und **das Voting wird automatisch manuell geschlossen**."
            )

            if st.button("Woche JETZT abschließen"):
                winners, tie_occurred, tie_msg = get_top_winners(data)
                winner_ids = [w["id"] for w in winners]
                winner_names = [w["name"] for w in winners]

                voters_map = {}
                for w_name in winner_names:
                    voters_map[w_name] = []
                    w_id = [
                        g["id"] for g in data["games"] if g["name"] == w_name
                    ][0]
                    for user, voted_g_ids in data["voted_users"].items():
                        if w_id in voted_g_ids:
                            voters_map[w_name].append(user)

                history_entry = {
                    "date": get_now().strftime("%d.%m.%Y"),
                    "kw": get_now().isocalendar()[1],
                    "winners": winner_names,
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
                        "action": "Woche abgeschlossen -> Voting AUTOMATISCH MANUELL GESCHLOSSEN",
                    }
                )

                for g in data["games"]:
                    g["votes"] = 0

                save_data(data)
                st.success(
                    "Woche abgeschlossen! Gewinner gesperrt & Voting auf MANUELL GESCHLOSSEN gesetzt."
                )
                st.rerun()

        with tab6:
            st.subheader("Neues Spiel direkt hinzufügen")
            col_add1, col_add2 = st.columns([2, 2])
            with col_add1:
                new_game = st.text_input("Spielname:", key="admin_add_game")
            with col_add2:
                new_img_url = st.text_input(
                    "Bild-URL / Cover-Link (optional):",
                    key="admin_add_img_url",
                    placeholder="https://.../cover.jpg",
                )

            if st.button("Direkt Hinzufügen (Sofort Aktiv)"):
                if new_game.strip():
                    img_to_use = (
                        new_img_url.strip()
                        if new_img_url.strip()
                        else DEFAULT_IMAGE
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
                        }
                    )
                    save_data(data)
                    st.success(f"'{new_game}' mit Bild hinzugefügt!")
                    st.rerun()

            st.write("---")
            st.subheader("Spiele verwalten & Bild-URLs anpassen")
            for idx, game in enumerate(data["games"]):
                c_img, c_name, c_url, c_actions = st.columns([1, 1.5, 2, 1.5])
                with c_img:
                    st.image(
                        game.get("image_url", DEFAULT_IMAGE),
                        use_container_width=True,
                    )
                with c_name:
                    status_badge = (
                        "🟢 Freigegeben"
                        if game.get("approved", True)
                        else "🟠 Wartet auf Freigabe"
                    )
                    st.write(f"**{game['name']}**")
                    st.caption(status_badge)

                with c_url:
                    current_url = game.get("image_url", "")
                    new_url_val = st.text_input(
                        "Bild-URL:",
                        value=str(current_url),
                        key=f"url_input_{game['id']}",
                    )
                    if st.button(
                        "💾 Bild-URL Speichern", key=f"save_url_{game['id']}"
                    ):
                        game["image_url"] = new_url_val.strip()
                        save_data(data)
                        st.success("Bild-URL aktualisiert!")
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

        # TAB 7: OPTION 3 - MANUELLES BACKUP / RESTORE
        with tab7:
            st.subheader("💾 Manuelles Daten-Backup & Wiederherstellung")
            st.write(
                "Hier kannst du deinen aktuellen Stand als Datei herunterladen oder ein altes Backup hochladen."
            )

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
                            st.success(
                                "Daten erfolgreich wiederhergestellt!"
                            )
                            st.rerun()
                    except Exception as e:
                        st.error(f"Fehler beim Lesen der Datei: {e}")
