from datetime import datetime, timedelta
import json
import os
import random
import re
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


# --- DEUTSCHE ZEIT HILFSFUNKTION ---
def get_now():
    """Gibt die aktuelle Uhrzeit in der deutschen Zeitzone (Europe/Berlin) zurück."""
    return datetime.now(GERMANY_TZ)


# --- AUTOMATISCHER WIKIPEDIA COVER SCRAPER (OHNE API KEY) ---
def get_wikipedia_cover_url(game_name):
    """Sucht auf der deutschen und englischen Wikipedia nach dem Spiel-Cover/Logo."""
    headers = {"User-Agent": "GamingVotingBot/2.0 (contact@example.com)"}

    # Versuch 1: Deutsche Wikipedia
    for lang in ["de", "en"]:
        try:
            search_url = f"https://{lang}.wikipedia.org/w/api.php"
            # 1. Nach Artikel suchen
            search_params = {
                "action": "query",
                "list": "search",
                "srsearch": f"{game_name} video game",
                "format": "json",
            }
            res = requests.get(
                search_url, params=search_params, headers=headers, timeout=4
            ).json()
            search_results = res.get("query", {}).get("search", [])

            if search_results:
                page_title = search_results[0]["title"]

                # 2. Thumbnail des Artikels abrufen
                img_params = {
                    "action": "query",
                    "titles": page_title,
                    "prop": "pageimages",
                    "pithumbsize": 500,
                    "format": "json",
                }
                img_res = requests.get(
                    search_url, params=img_params, headers=headers, timeout=4
                ).json()
                pages = img_res.get("query", {}).get("pages", {})

                for page_id, page_data in pages.items():
                    if "thumbnail" in page_data:
                        return page_data["thumbnail"]["source"]
        except Exception:
            continue

    # Fallback-Bild, falls Wikipedia kein Bild findet (Stylisches Neon-Icon)
    return "https://images.unsplash.com/photo-1550745165-9bc0b252726f?w=400&q=80"


# --- DATENBANK FUNKTIONEN ---
def load_data():
    if not os.path.exists(DATA_FILE):
        default_data = {
            "games": [
                {
                    "id": 1,
                    "name": "GTA Vice City",
                    "votes": 0,
                    "locked": False,
                    "approved": True,
                    "image_url": "https://upload.wikimedia.org/wikipedia/en/c/ce/Vice-city-cover.jpg",
                },
                {
                    "id": 2,
                    "name": "Cyberpunk 2077",
                    "votes": 0,
                    "locked": False,
                    "approved": True,
                    "image_url": "https://upload.wikimedia.org/wikipedia/en/9/9f/Cyberpunk_2077_box_art.jpg",
                },
                {
                    "id": 3,
                    "name": "Valheim",
                    "votes": 0,
                    "locked": False,
                    "approved": True,
                    "image_url": "https://upload.wikimedia.org/wikipedia/en/0/06/Valheim_logo.jpg",
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

        # Abwärtskompatibilität für Cover-URLs & Approval
        for g in data.get("games", []):
            if "approved" not in g:
                g["approved"] = True
            if "image_url" not in g or not g["image_url"]:
                g["image_url"] = get_wikipedia_cover_url(g["name"])

        save_data(data)
        return data


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


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


# --- APP STYLING (VAPORWAVE / SYNTHWAVE / CYBERPUNK THEME) ---
st.set_page_config(
    page_title="Gaming Voting - Vaporwave Edition",
    page_icon="⚡",
    layout="centered",
    initial_sidebar_state="collapsed",
)

if AUTORUN_AVAILABLE:
    autorun(interval=1000, key="live_clock_refresher")

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@600;800;900&family=Rajdhani:wght@600;700&display=swap');

    /* Global Dark Cyber Background */
    .stApp {
        background: radial-gradient(circle at 50% 10%, #1e1035 0%, #0d0b1e 70%);
        color: #f1f5f9;
        font-family: 'Rajdhani', sans-serif;
    }

    /* Synthwave Header Banner */
    .synth-banner {
        background: linear-gradient(135deg, #ff007f 0%, #7928ca 50%, #00f0ff 100%);
        border: 2px solid #00f0ff;
        border-radius: 16px;
        padding: 25px 15px;
        text-align: center;
        box-shadow: 0 0 25px rgba(255, 0, 127, 0.45), inset 0 0 15px rgba(0, 240, 255, 0.3);
        margin-bottom: 25px;
    }
    .synth-title {
        font-family: 'Orbitron', sans-serif;
        font-size: 2.2rem;
        font-weight: 900;
        color: #ffffff;
        text-shadow: 0 0 12px #ff007f, 0 0 25px #00f0ff;
        letter-spacing: 2px;
        margin: 0;
        text-transform: uppercase;
    }
    .synth-subtitle {
        color: #e2e8f0;
        font-size: 1.1rem;
        font-weight: 700;
        margin-top: 5px;
        text-shadow: 0 0 8px rgba(0,0,0,0.8);
        letter-spacing: 1px;
    }

    /* Buttons Style */
    div.stButton > button {
        background: linear-gradient(90deg, #ff007f 0%, #b800ff 100%);
        color: #ffffff !important;
        font-family: 'Orbitron', sans-serif;
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

    /* Live Time Box */
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
        font-family: 'Orbitron', sans-serif;
        font-size: 2rem; 
        font-weight: 800; 
        color: #00f0ff; 
        text-shadow: 0 0 10px #00f0ff;
    }

    /* Status Badges */
    .status-card {
        padding: 12px; border-radius: 8px; font-weight: bold; text-align: center; margin-bottom: 15px;
        font-family: 'Orbitron', sans-serif; font-size: 1rem;
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

    /* Winner Box */
    .winner-box {
        background: linear-gradient(135deg, rgba(255, 0, 127, 0.15), rgba(0, 240, 255, 0.15));
        border: 2px solid #ff007f;
        padding: 15px; border-radius: 12px;
        text-align: center; margin-bottom: 20px;
        box-shadow: 0 0 20px rgba(255, 0, 127, 0.3);
    }

    /* Game List Row Box */
    .game-card {
        background: rgba(26, 20, 50, 0.7);
        border: 1px solid #3b2d6b;
        border-radius: 10px;
        padding: 10px;
        margin-bottom: 12px;
        display: flex;
        align-items: center;
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
    # 80s VAPORWAVE HERO BANNER
    st.markdown(
        """
        <div class="synth-banner">
            <h1 class="synth-title">⚡ FREITAG GAMING VOTING ⚡</h1>
            <div class="synth-subtitle">VICE CITY & CYBERPUNK EDITION</div>
        </div>
    """,
        unsafe_allow_html=True,
    )

    now = get_now()
    is_open, time_left, countdown_label, is_manual_override = (
        get_voting_time_status(data)
    )

    # ECHTZEIT & COUNTDOWN
    st.markdown(
        f"""
        <div class="time-header-box">
            <div class="clock-text">📅 Aktuelle Zeit (DE): <strong>{now.strftime("%A, %d.%m.%Y - %H:%M:%S")} Uhr</strong></div>
            <hr style="border-color:#3b2d6b; margin:8px 0;">
            <div style="font-size:0.9rem; color:#a78bfa;">{countdown_label}</div>
            <div class="countdown-display">{"--" if is_manual_override else format_timedelta(time_left)}</div>
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
                    <h3 style="color:#00f0ff; margin:0; font-family:'Orbitron'; font-weight:800;">🏆 AKTUELLE TOP-2 FAVORITEN</h3>
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

        # SPIEL VORSCHLAGEN BEREICH
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
                        with st.spinner(
                            "Suche nach Cover-Bild auf Wikipedia..."
                        ):
                            cover_img = get_wikipedia_cover_url(
                                suggested_game.strip()
                            )

                        new_id = (
                            max([g["id"] for g in data["games"]], default=0) + 1
                        )
                        data["games"].append(
                            {
                                "id": new_id,
                                "name": suggested_game.strip(),
                                "votes": 0,
                                "locked": False,
                                "approved": False,  # Benötigt Admin Freigabe
                                "image_url": cover_img,
                            }
                        )
                        save_data(data)
                        st.info(
                            f"Vorschlag '{suggested_game.strip()}' mit Cover eingereicht! Wartet auf Admin-Freigabe."
                        )
                        st.rerun()

        st.subheader("🎮 Spieleliste")
        user_name = st.text_input(
            "Dein Name / Alias (erforderlich zum Voten):",
            placeholder="z. B. GamerX",
        ).strip()
        user_voted_games = data["voted_users"].get(user_name.lower(), [])

        public_games = [g for g in data["games"] if g.get("approved", True)]

        # SPIELELISTE RENDERN (MIT WIKIPEDIA COVER THUMBNAILS)
        for game in public_games:
            col_img, col1, col2, col3 = st.columns([1.2, 3, 1, 2])
            is_locked = game["locked"] or game["id"] in data.get(
                "last_winner_ids", []
            )
            has_voted_this_game = game["id"] in user_voted_games

            with col_img:
                # Thumbnail anzeigen
                st.image(
                    game.get(
                        "image_url",
                        "https://images.unsplash.com/photo-1550745165-9bc0b252726f?w=400&q=80",
                    ),
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
                button_label = "Gevotet ✅" if has_voted_this_game else "Voten ⚡"

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
                    st.success(f"Stimme für '{game['name']}' registriert!")
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

        tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
            [
                "🔓 Vote Status Override",
                "📩 Vorschläge freigeben",
                "📊 Voting Index & Logs",
                "👑 Gewinner Override",
                "🔄 Woche Abschließen",
                "🎮 Spiele Verwalten",
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
                            un_game.get(
                                "image_url",
                                "https://images.unsplash.com/photo-1550745165-9bc0b252726f?w=400&q=80",
                            ),
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
            new_game = st.text_input("Spielname:", key="admin_add_game")
            if st.button("Direkt Hinzufügen (Sofort Aktiv)"):
                if new_game.strip():
                    with st.spinner("Suche nach Wikipedia Cover..."):
                        cover_img = get_wikipedia_cover_url(new_game.strip())

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
                            "image_url": cover_img,
                        }
                    )
                    save_data(data)
                    st.success(f"'{new_game}' mit Cover hinzugefügt!")
                    st.rerun()

            st.write("---")
            st.subheader("Spiele verwalten & Cover anpassen")
            for idx, game in enumerate(data["games"]):
                c_img, c1, c2, c3 = st.columns([1, 2, 1, 1])
                with c_img:
                    st.image(
                        game.get(
                            "image_url",
                            "https://images.unsplash.com/photo-1550745165-9bc0b252726f?w=400&q=80",
                        ),
                        use_container_width=True,
                    )
                with c1:
                    status_badge = (
                        "🟢 Freigegeben"
                        if game.get("approved", True)
                        else "🟠 Wartet auf Freigabe"
                    )
                    st.write(f"**{game['name']}** ({status_badge})")
                    if st.button(
                        "🌐 Cover von Wikipedia neu laden",
                        key=f"reload_img_{game['id']}",
                    ):
                        game["image_url"] = get_wikipedia_cover_url(
                            game["name"]
                        )
                        save_data(data)
                        st.success("Cover aktualisiert!")
                        st.rerun()
                with c2:
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
                with c3:
                    if st.button("🗑️ Löschen", key=f"admin_del_{game['id']}"):
                        data["games"].pop(idx)
                        save_data(data)
                        st.rerun()
