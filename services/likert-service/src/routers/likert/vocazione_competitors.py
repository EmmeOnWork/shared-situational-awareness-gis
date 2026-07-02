"""Vocazione → competitor POI categories — the slug↔Foursquare-taxonomy bridge.

**Strangler copy** of the monolith's ``routers/pois/vocazione_competitors.py``
(ADR-0001: the shared DB is read by id/name only, and monolith *code* is never
imported). Kept verbatim so the Scala Likert reads the **same** competitor set the
Concorrenza map layer paints; if the editorial mapping changes, both copies move
together.

The 16 Vocazioni are a closed front-end catalog (the Vocazione Selector), not stored
in the DB. POIs carry the Foursquare taxonomy in
``pois.metadata->>'fsq_category_labels'`` (a JSON-string array of hierarchical paths
like "Business and Professional Services > Health and Beauty Service > Spa"). No
column links the two — this module IS that link.

Keyed by the SAME stable slug the selection bus carries (``praim:selection:
vocazione``); each value is a list of FSQ category-label **prefixes**, matched by
prefix so a 2nd-level prefix (".. > Health and Beauty Service") captures all its
children (Spa, Massage, Hair/Nail Salon, ...). The civic Vocazioni (Osservatorio,
Protezione Civile, Hub Servizi/Diritti) have no real market competitor and map only
to institutional proxies — keep that caveat in mind before leaning on their reading.
"""

from typing import List

# slug (bus value `Vocazione.id`) -> exact FSQ category-label prefixes (matched with
# `label LIKE prefix || '%'`). Keep the prefixes verbatim from the live taxonomy.
VOCAZIONE_COMPETITORS = {
    "dimora-del-benessere": [
        "Business and Professional Services > Health and Beauty Service",
        "Sports and Recreation > Gym and Studio",
        "Health and Medicine > Alternative Medicine Clinic",
        "Health and Medicine > Nutritionist",
    ],
    "atelier-di-ricordi": [
        "Business and Professional Services > Photography Service",
        "Retail > Framing Store",
        "Retail > Print Store",
        "Arts and Entertainment > Art Gallery",
        "Business and Professional Services > Design Studio",
    ],
    "incubatore-rurale-di-comunita": [
        "Business and Professional Services > Office",
        "Business and Professional Services > Business Service",
        "Business and Professional Services > Technology Business",
        "Business and Professional Services > Business Center",
    ],
    "re-star-borgo": [
        "Travel and Transportation > Lodging",
        "Travel and Transportation > Tourist Information and Service",
        "Travel and Transportation > Travel Agency",
    ],
    "ostello-rurale-di-comunita": [
        "Travel and Transportation > Lodging",
        "Landmarks and Outdoors > Campground",
    ],
    "rural-futures": [
        "Business and Professional Services > Agriculture and Forestry Service",
        "Landmarks and Outdoors > Farm",
        "Business and Professional Services > Technology Business",
        "Business and Professional Services > Research Laboratory",
    ],
    "botteghe-intergenerazionali": [
        "Retail > Arts and Crafts Store",
        "Business and Professional Services > Tailor",
        "Retail > Antique Store",
        "Retail > Vintage and Thrift Store",
        "Retail > Boutique",
        "Business and Professional Services > Repair Service",
    ],
    "borgo-lab": [
        "Business and Professional Services > Office > Coworking Space",
        "Business and Professional Services > Technology Business",
        "Business and Professional Services > Design Studio",
        "Arts and Entertainment > Internet Cafe",
    ],
    "radici-visive": [
        "Arts and Entertainment > Art Gallery",
        "Arts and Entertainment > Museum",
        "Arts and Entertainment > Performing Arts Venue",
        "Community and Government > Cultural Center",
        "Landmarks and Outdoors > Historic and Protected Site",
    ],
    "accoglienza-educativa": [
        "Community and Government > Education",
        "Business and Professional Services > Child Care Service",
        "Sports and Recreation > Indoor Play Area",
        "Community and Government > Assisted Living",
    ],
    "presidio-medico-integrato": [
        "Health and Medicine > Medical Center",
        "Health and Medicine > Healthcare Clinic",
        "Health and Medicine > Physician",
        "Health and Medicine > Hospital",
        "Health and Medicine > Physical Therapy Clinic",
        "Retail > Pharmacy",
    ],
    "hub-dei-servizi-di-prossimita-e-dei-diritti": [
        "Community and Government > Government Building",
        "Community and Government > Organization",
        "Business and Professional Services > Legal Service",
        "Community and Government > Public and Social Service",
    ],
    "laboratorio-di-economia-circolare-e-filiere-locali": [
        "Business and Professional Services > Waste Management Service",
        "Retail > Food and Beverage Retail",
        "Landmarks and Outdoors > Farm",
        "Retail > Market",
        "Business and Professional Services > Food and Beverage Service",
    ],
    "hub-della-mobilita-rurale-lenta-e-condivisa": [
        "Travel and Transportation > Transport Hub",
        "Travel and Transportation > Transportation Service",
        "Travel and Transportation > Parking",
        "Travel and Transportation > Electric Vehicle Charging Station",
        "Business and Professional Services > Rental Service",
    ],
    "osservatorio-territoriale-e-centro-dati-di-comunita": [
        "Business and Professional Services > Research Laboratory",
        "Business and Professional Services > Technology Business",
        "Business and Professional Services > Market Research and Consulting Service",
    ],
    "presidio-di-comunita-per-la-resilienza-e-la-protezione-civile": [
        "Health and Medicine > Emergency Service",
        "Community and Government > Government Building",
        "Community and Government > Organization",
        "Community and Government > Community Center",
    ],
}


def get_competitor_category_prefixes(vocazione_slug: str) -> List[str]:
    """Resolve a Vocazione slug to its competitor FSQ category prefixes.

    Args:
        vocazione_slug: the bus value `Vocazione.id` (e.g. "dimora-del-benessere").

    Returns:
        The list of FSQ category-label prefixes for that Vocazione, or an empty list
        for an unknown/empty slug — which the route reads as "no market competitor".
    """
    if not vocazione_slug:
        return []
    return VOCAZIONE_COMPETITORS.get(vocazione_slug, [])
