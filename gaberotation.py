from datetime import datetime
import json
import os
import streamlit as st

# Dateipfad für die Datenbank
DATA_FILE = "data.json"


# --- DATENBANK FUNKTIONEN ---
def load_data():
    """Lädt die Daten aus der JSON-Datei oder erstellt Standardwerte."""
    if not os.path.exists(DATA_FILE):
        default_data = {
            "games": [
                {"id": 1, "name": "Beispiel 1", "votes": 0, "locked": False},
                {"id": 2, "name": "Beispiel 2", "votes": 0, "locked": False},
                {"id": 3, "name": "Beispiel 3", "votes": 0, "locked": False},
                {"id": 4, "name": "Beispiel 4", "votes": 0, "locked": False},
                {"id": 5, "name": "Beispiel 5", "votes": 0, "locked": False},
                {"id": 6, "name": "Beispiel 6", "votes": 0, "locked": False},
            ],
            "voted_users": [],  # Speichert Votings der aktuellen Woche
            "last_winner_ids": [],  # Gesperrte Gewinner der letzten Woche
        }
        save_data(default_data)
        return default_data

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data):
    """Speichert die Daten in die JSON-Datei."""
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


# --- HILFSFUNKTIONEN ---
def is_wednesday():
    """Prüft, ob heute Mittwoch ist (0 = Mo, 2 = Mi, 6 = So)."""
    return datetime.now().weekday() == 2


# --- APP SETUP & DESIGN ---
st.set_page_config(
    page_title="Gaming Voting",
    page_icon="🎮",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# Custom CSS für Dark-Gaming-Look
st.markdown(
    """
    <style>
    .stApp {
        background-color: #0f111a;
        color: #ffffff;
    }
    div.stButton > button {
        background-color: #7289da;
        color: white;
        font-weight: bold;
        border-radius: 8px;
        border: none;
        width: 100%;
        padding: 10px;
    }
    div.stButton > button:hover {
        background-color: #5b6eae;
        color: white;
    }
    .status-card {
        padding: 15px;
        border-radius: 10px;
        margin-bottom: 20px;
        font-weight: bold;
        text-align: center;
    }
    .open {
        background-color: #1e2230;
        border-left: 5px solid #2ecc71;
    }
    .closed {
        background-color: #1e2230;
        border-left: 5px solid #e74c3c;
    }
    .winner-box {
        background: linear-gradient(135deg, #2c2505, #1e2230);
        border: 2px solid #f1c40f;
        padding: 15px;
        border-radius: 10px;
        text-align: center;
        margin-bottom: 20px;
    }
    </style>
""",
    unsafe_allow_html=True,
)

data = load_data()

# Navigation zwischen Abstimmung und Admin
menu = st.sidebar.radio("Navigation", [" Abstimmung", "⚙️ Admin-Bereich"])

# ==========================================
# SEITE 1: ABSTIMMUNG
# ==========================================
if menu == " Abstimmung":
    st.title("🎮 Freitag Gaming Voting")

    today_is_mi = is_wednesday()

    # Status-Anzeige
    if today_is_mi:
        st.markdown(
            '<div class="status-card open">🟢 Voting ist HEUTE geöffnet!</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div class="status-card closed">🔴 Voting ist heute geschlossen. Gewählt werden kann immer Mittwochs!</div>',
            unsafe_allow_html=True,
        )

    # Gewinner ermitteln & anzeigen (Höchste Stimmen)
    sorted_games = sorted(
        data["games"], key=lambda x: x["votes"], reverse=True
    )
    top_winners = [g for g in sorted_games[:2] if g["votes"] > 0]

    if top_winners:
        st.markdown(
            """
            <div class="winner-box">
                <h3 style="color:#f1c40f; margin:0;">🏆 Aktuelle Top-Favoriten</h3>
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
    st.subheader("Spieleliste")

    # Vorbereitung Version 2: Namensabfrage
    user_name = st.text_input(
        "Dein Name / Alias (für die Abstimmung):",
        placeholder="z. B. GamerX",
    )

    for game in data["games"]:
        col1, col2, col3 = st.columns([3, 1, 1])

        # Status für gesperrte Spiele
        is_locked = game["locked"] or game["id"] in data.get(
            "last_winner_ids", []
        )

        with col1:
            if is_locked:
                st.markdown(
                    f"**{game['name']}** 🚫 *(Gesperrt aus Vorwoche)*"
                )
            else:
                st.markdown(f"**{game['name']}**")

        with col2:
            st.caption(f"📊 {game['votes']} Stimmen")

        with col3:
            vote_disabled = not today_is_mi or is_locked or not user_name.strip()

            if st.button("Voten", key=f"vote_{game['id']}", disabled=vote_disabled):
                # Doppel-Voting prüfen
                if user_name.strip().lower() in [
                    u.lower() for u in data["voted_users"]
                ]:
                    st.error("Du hast diese Woche bereits abgestimmt!")
                else:
                    game["votes"] += 1
                    data["voted_users"].append(user_name.strip())
                    save_data(data)
                    st.success(f"Danke für deine Stimme für {game['name']}!")
                    st.rerun()

# ==========================================
# SEITE 2: ADMIN-BEREICH
# ==========================================
elif menu == "⚙️ Admin-Bereich":
    st.title("⚙️ Admin-Bereich")

    # Neues Spiel hinzufügen
    st.subheader("Neues Spiel hinzufügen")
    new_game = st.text_input("Name des Spiels")
    if st.button("Spiel hinzufügen"):
        if new_game.strip():
            new_id = (
                max([g["id"] for g in data["games"]], default=0) + 1
            )
            data["games"].append(
                {
                    "id": new_id,
                    "name": new_game.strip(),
                    "votes": 0,
                    "locked": False,
                }
            )
            save_data(data)
            st.success(f"'{new_game}' hinzugefügt!")
            st.rerun()

    st.write("---")

    # Woche abschließen & Gewinner sperren
    st.subheader("🔄 Woche abschließen")
    st.info(
        "Setzt alle Stimmen zurück und sperrt die TOP 2 Gewinner automatisch für die nächste Woche."
    )
    if st.button("Woche jetzt zurücksetzen & Gewinner sperren"):
        sorted_games = sorted(
            data["games"], key=lambda x: x["votes"], reverse=True
        )
        winners = [g["id"] for g in sorted_games[:2] if g["votes"] > 0]

        # Gewinner der Vorwoche sperren
        data["last_winner_ids"] = winners
        data["voted_users"] = []

        # Stimmen auf 0 setzen
        for g in data["games"]:
            g["votes"] = 0

        save_data(data)
        st.success(
            "Woche erfolgreich zurückgesetzt! Die Gewinner sind nun für 1 Woche gesperrt."
        )
        st.rerun()

    st.write("---")

    # Spiele verwalten
    st.subheader("Spiele bearbeiten / löschen")
    for idx, game in enumerate(data["games"]):
        c1, c2, c3 = st.columns([2, 1, 1])
        with c1:
            st.write(f"**{game['name']}**")
        with c2:
            # Manuelles Sperren/Entsperren
            lock_status = game["locked"] or game["id"] in data.get(
                "last_winner_ids", []
            )
            if st.button(
                "Entsperren" if lock_status else "Sperren",
                key=f"lock_{game['id']}",
            ):
                game["locked"] = not lock_status
                if game["id"] in data.get("last_winner_ids", []):
                    data["last_winner_ids"].remove(game["id"])
                save_data(data)
                st.rerun()
        with c3:
            if st.button("🗑️ Löschen", key=f"del_{game['id']}"):
                data["games"].pop(idx)
                save_data(data)
                st.rerun()
