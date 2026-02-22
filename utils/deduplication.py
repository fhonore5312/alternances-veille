#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
utils/deduplication.py
Déduplication robuste des offres : URL + titre/entreprise normalisés
"""

import re
import unicodedata


def normalize(text):
    """Normalise une chaîne : minuscules, sans accents, sans caractères spéciaux."""
    if not text:
        return ""
    # Supprimer les accents
    nfkd = unicodedata.normalize("NFKD", str(text))
    text = "".join(c for c in nfkd if not unicodedata.combining(c))
    # Minuscules, strip, espaces multiples → simple
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def generate_offer_id(offer):
    """
    Génère un ID de déduplication sur titre + entreprise + ville normalisés.
    Utilisé pour la déduplication cross-source (LBA vs Perplexity).
    """
    titre = normalize(offer.get("titre", ""))
    entreprise = normalize(offer.get("entreprise", ""))
    ville = normalize(offer.get("ville", ""))
    return f"{titre}|{entreprise}|{ville}"


def get_url_key(offer):
    """
    Retourne l'URL nettoyée pour déduplication par URL.
    Priorité sur generate_offer_id car 2 offres avec même URL = même offre.
    """
    url = offer.get("url_candidature", "").strip().rstrip("/")
    # Supprimer les paramètres UTM/tracking
    url = re.sub(r"[?&](utm_[^&]*|ref=[^&]*|source=[^&]*)", "", url)
    return url.lower() if url and url != "#" else None


def deduplicate_offers(offers):
    """
    Déduplique une liste d'offres.
    Stratégie :
      1. URL identique → doublon
      2. titre + entreprise + ville normalisés → doublon
    Retourne (offres_uniques, nb_doublons)
    """
    seen_ids = set()
    seen_urls = set()
    unique = []
    duplicates = 0

    for offer in offers:
        url_key = get_url_key(offer)
        offer_id = generate_offer_id(offer)

        # Dédup par URL (plus fiable)
        if url_key and url_key in seen_urls:
            duplicates += 1
            continue

        # Dédup par titre+entreprise+ville normalisés
        if offer_id in seen_ids:
            duplicates += 1
            continue

        unique.append(offer)
        seen_ids.add(offer_id)
        if url_key:
            seen_urls.add(url_key)

    return unique, duplicates
