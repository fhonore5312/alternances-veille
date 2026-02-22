import json
from utils.config_loader import load_tracks

with open('data/offres_merged.json', encoding='utf-8') as f:
    data = json.load(f)

offers = data['offres']
tracks_cfg = load_tracks()

for track_key in tracks_cfg.keys():
    track_offers = [o for o in offers if o.get('track', 'digital_marketing') == track_key]
    print(f'Track: {track_key} -> {len(track_offers)} offres')
    paris_offers = [o for o in track_offers if o.get('ville_recherche') == 'Paris']
    print(f'  dont Paris: {len(paris_offers)}')
    for o in paris_offers:
        print(f'    - {o["entreprise"]}')
