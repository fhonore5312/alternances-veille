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
        raise FileNotFoundError(f"Fichier de configuration introuvable : {TRACKS_FILE}")

    with open(TRACKS_FILE, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    tracks = data.get("tracks", {})

    if not tracks:
        raise ValueError("Aucun track défini dans tracks.yml")

    return tracks


def get_track(track_key):
    """Charge un track spécifique, lève une erreur claire si introuvable."""
    tracks = load_tracks()
    if track_key not in tracks:
        available = ", ".join(tracks.keys())
        raise ValueError(f"Track '{track_key}' introuvable. Disponibles : {available}")
    return tracks[track_key]
