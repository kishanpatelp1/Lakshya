"""Profile persistence service — local JSON files + MongoDB sync."""

import json
import logging
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# user-profiles/ sits two levels above backend-ai/src/domains/profiles/
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
PROFILES_ROOT = os.getenv(
    "USER_PROFILES_DIR",
    os.path.normpath(os.path.join(_THIS_DIR, "..", "..", "..", "..", "user-profiles")),
)

AVATAR_COLORS = [
    "#E50914",  # Netflix red
    "#2563EB",  # blue
    "#16A34A",  # green
    "#D97706",  # amber
    "#7C3AED",  # violet
    "#0891B2",  # cyan
    "#BE185D",  # pink
]


def _profile_dir(profile_id: str) -> str:
    return os.path.join(PROFILES_ROOT, profile_id)


def _read_json(path: str, default: Any = None) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def _write_json(path: str, data: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, default=str)


class ProfilesService:
    """Manages user profiles stored as JSON files locally, synced to MongoDB."""

    # ------------------------------------------------------------------ #
    #  Local file helpers                                                  #
    # ------------------------------------------------------------------ #

    def list_profiles(self) -> List[Dict[str, Any]]:
        os.makedirs(PROFILES_ROOT, exist_ok=True)
        profiles = []
        for name in sorted(os.listdir(PROFILES_ROOT)):
            profile_path = os.path.join(PROFILES_ROOT, name, "profile.json")
            if os.path.isfile(profile_path):
                data = _read_json(profile_path, {})
                if data:
                    profiles.append(data)
        return profiles

    def create_profile(self, name: str, avatar_color: Optional[str] = None) -> Dict[str, Any]:
        profile_id = str(uuid.uuid4())
        color = avatar_color or AVATAR_COLORS[len(self.list_profiles()) % len(AVATAR_COLORS)]
        profile = {
            "id": profile_id,
            "name": name,
            "avatar_color": color,
            "created_at": datetime.utcnow().isoformat(),
        }
        _write_json(os.path.join(_profile_dir(profile_id), "profile.json"), profile)
        # Seed empty data files
        for fname in ("chat_history.json", "portfolio.json", "watchlists.json", "bookmarks.json"):
            _write_json(os.path.join(_profile_dir(profile_id), fname), [])
        return profile

    def get_profile(self, profile_id: str) -> Optional[Dict[str, Any]]:
        path = os.path.join(_profile_dir(profile_id), "profile.json")
        return _read_json(path)

    def get_profile_data(self, profile_id: str) -> Dict[str, Any]:
        base = _profile_dir(profile_id)
        profile = _read_json(os.path.join(base, "profile.json"), {})
        chat_history = _read_json(os.path.join(base, "chat_history.json"), [])
        portfolio = _read_json(os.path.join(base, "portfolio.json"), [])
        watchlists = _read_json(os.path.join(base, "watchlists.json"), [])
        bookmarks = _read_json(os.path.join(base, "bookmarks.json"), [])
        return {
            "profile": profile,
            "chat_history": chat_history,
            "portfolio": portfolio,
            "watchlists": watchlists,
            "bookmarks": bookmarks,
        }

    def sync_profile(
        self, profile_id: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Save profile data to local files and push to MongoDB if available."""
        base = _profile_dir(profile_id)
        os.makedirs(base, exist_ok=True)

        if "profile" in payload:
            _write_json(os.path.join(base, "profile.json"), payload["profile"])
        if "chat_history" in payload:
            _write_json(os.path.join(base, "chat_history.json"), payload["chat_history"])
        if "portfolio" in payload:
            _write_json(os.path.join(base, "portfolio.json"), payload["portfolio"])
        if "watchlists" in payload:
            _write_json(os.path.join(base, "watchlists.json"), payload["watchlists"])
        if "bookmarks" in payload:
            _write_json(os.path.join(base, "bookmarks.json"), payload["bookmarks"])

        mongo_status = "skipped"
        try:
            import asyncio
            from src.db.mongo_client import get_mongo_db
            db = get_mongo_db()
            if db is not None:
                asyncio.get_event_loop().run_until_complete(
                    self._mongo_upsert(db, profile_id, payload)
                )
                mongo_status = "synced"
        except Exception as exc:
            logger.warning("MongoDB sync failed for profile %s: %s", profile_id, exc)
            mongo_status = f"error: {exc}"

        return {"status": "saved", "profile_id": profile_id, "mongodb": mongo_status}

    def delete_profile(self, profile_id: str) -> Dict[str, Any]:
        import shutil
        path = _profile_dir(profile_id)
        if os.path.isdir(path):
            shutil.rmtree(path)
        return {"status": "deleted", "profile_id": profile_id}

    # ------------------------------------------------------------------ #
    #  MongoDB helpers                                                     #
    # ------------------------------------------------------------------ #

    async def _mongo_upsert(self, db: Any, profile_id: str, payload: Dict[str, Any]) -> None:
        now = datetime.utcnow()
        for key, collection_name in [
            ("profile", "profiles"),
            ("chat_history", "chat_sessions"),
            ("portfolio", "portfolios"),
            ("watchlists", "watchlists"),
            ("bookmarks", "bookmarks"),
        ]:
            if key not in payload:
                continue
            collection = db[collection_name]
            await collection.update_one(
                {"profile_id": profile_id},
                {"$set": {"profile_id": profile_id, "data": payload[key], "updated_at": now}},
                upsert=True,
            )
