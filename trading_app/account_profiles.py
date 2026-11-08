from __future__ import annotations

import json
import os
from pathlib import Path

SERVICE = "DRTradingTerminal"


def profiles_path() -> Path:
    base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    return base / SERVICE / "broker_profiles.json"


def load_profiles() -> list[dict]:
    try:
        data = json.loads(profiles_path().read_text(encoding="utf-8"))
        rows = data.get("profiles", []) if isinstance(data, dict) else []
        return [p for p in rows if isinstance(p, dict) and p.get("broker") and p.get("login") and p.get("server")]
    except (OSError, ValueError, TypeError):
        return []


def save_profiles(profiles: list[dict]) -> None:
    clean = []
    seen = set()
    for item in profiles:
        broker = str(item.get("broker", "")).strip()[:100]
        login = str(item.get("login", "")).strip()
        server = str(item.get("server", "")).strip()[:160]
        email = str(item.get("email", "")).strip()[:160]
        if not broker or not login.isdigit() or not server:
            continue
        key = (broker.casefold(), login, server.casefold())
        if key in seen:
            continue
        seen.add(key)
        clean.append({"broker": broker, "email": email, "login": login, "server": server})
    path = profiles_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps({"version": 1, "profiles": clean}, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def credential_key(broker: str, login: str, server: str) -> str:
    return f"{broker.strip()}|{login.strip()}|{server.strip()}"


def save_password(broker: str, login: str, server: str, password: str) -> None:
    if not password:
        raise ValueError("Password cannot be empty.")
    try:
        import keyring
        keyring.set_password(SERVICE, credential_key(broker, login, server), password)
    except Exception as exc:
        raise RuntimeError(f"Windows Credential Manager could not save this password: {exc}") from exc


def get_password(broker: str, login: str, server: str) -> str | None:
    try:
        import keyring
        return keyring.get_password(SERVICE, credential_key(broker, login, server))
    except Exception:
        return None


def delete_password(broker: str, login: str, server: str) -> None:
    try:
        import keyring
        keyring.delete_password(SERVICE, credential_key(broker, login, server))
    except Exception:
        pass
