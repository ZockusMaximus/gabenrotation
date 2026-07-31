# --- GITHUB AUTOMATISCHE SYNC FUNKTION (MIT FEHLER-DIAGNOSE) ---
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

        # 1. Aktuellen SHA der Datei abrufen
        get_res = requests.get(url, headers=headers, timeout=5)
        sha = get_res.json().get("sha") if get_res.status_code == 200 else None

        # 2. Datei codieren & hochladen
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
