# utils/config_loader.py
from pathlib import Path
import yaml

SCRIPT_DIR = Path(__file__).parent
BASE_DIR = SCRIPT_DIR.parent
CONFIG_DIR = BASE_DIR / "config"
TRACKS_FILE = CONFIG_DIR / "tracks.yml"


def load_tracks():
    """Charge la configuration des tracks depuis config/tracks.yml"""
    if not TRACKS_FILE.exists():
        raise FileNotFoundError(f"Fichier de configuration introuvable: {TRACKS_FILE}")

    with open(TRACKS_FILE, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    tracks = data.get("tracks", {})
    if "digital_marketing" not in tracks:
        raise ValueError("Track 'digital_marketing' manquant dans tracks.yml")

    return tracks
