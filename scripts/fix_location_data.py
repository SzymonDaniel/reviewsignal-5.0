#!/usr/bin/env python3
"""
Fix location data quality issues.

Addresses three major gaps:
  1. Country: 89.9% empty -> extract from address + coordinates
  2. City: 31.3% missing -> extract from address
  3. Rating: 57.4% NULL -> compute from reviews table where possible

Uses modules/db.py shared connection pool.
"""

import os
import re
import sys
import time
from collections import defaultdict

# Ensure project root is importable
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

from modules.db import get_connection, return_connection

# ---------------------------------------------------------------------------
# Country name -> ISO 2-letter code mapping
# ---------------------------------------------------------------------------
COUNTRY_NAME_TO_ISO = {
    # Full names
    "united states": "US",
    "usa": "US",
    "u.s.a.": "US",
    "united states of america": "US",
    "united kingdom": "GB",
    "uk": "GB",
    "great britain": "GB",
    "england": "GB",
    "scotland": "GB",
    "wales": "GB",
    "northern ireland": "GB",
    "germany": "DE",
    "deutschland": "DE",
    "france": "FR",
    "italy": "IT",
    "italia": "IT",
    "spain": "ES",
    "españa": "ES",
    "canada": "CA",
    "australia": "AU",
    "new zealand": "NZ",
    "netherlands": "NL",
    "holland": "NL",
    "the netherlands": "NL",
    "belgium": "BE",
    "switzerland": "CH",
    "austria": "AT",
    "portugal": "PT",
    "ireland": "IE",
    "denmark": "DK",
    "sweden": "SE",
    "norway": "NO",
    "finland": "FI",
    "poland": "PL",
    "czech republic": "CZ",
    "czechia": "CZ",
    "hungary": "HU",
    "romania": "RO",
    "greece": "GR",
    "turkey": "TR",
    "türkiye": "TR",
    "japan": "JP",
    "south korea": "KR",
    "korea": "KR",
    "china": "CN",
    "india": "IN",
    "malaysia": "MY",
    "singapore": "SG",
    "thailand": "TH",
    "philippines": "PH",
    "indonesia": "ID",
    "taiwan": "TW",
    "hong kong": "HK",
    "mexico": "MX",
    "brasil": "BR",
    "brazil": "BR",
    "argentina": "AR",
    "colombia": "CO",
    "south africa": "ZA",
    "luxembourg": "LU",
    "croatia": "HR",
    "slovakia": "SK",
    "slovenia": "SI",
    "latvia": "LV",
    "lithuania": "LT",
    "estonia": "EE",
    "bulgaria": "BG",
    "serbia": "RS",
    "north macedonia": "MK",
    "macedonia": "MK",
    "montenegro": "ME",
    "bosnia and herzegovina": "BA",
    "albania": "AL",
    "malta": "MT",
    "cyprus": "CY",
    "iceland": "IS",
    "saudi arabia": "SA",
    "united arab emirates": "AE",
    "uae": "AE",
    "kuwait": "KW",
    "qatar": "QA",
    "bahrain": "BH",
    "oman": "OM",
    "israel": "IL",
    "vietnam": "VN",
    "chile": "CL",
    "peru": "PE",
    "venezuela": "VE",
    "bolivia": "BO",
    "uruguay": "UY",
    "paraguay": "PY",
    "costa rica": "CR",
    "panama": "PA",
    "puerto rico": "PR",
    "morocco": "MA",
    "egypt": "EG",
    "kenya": "KE",
    "nigeria": "NG",
    "russia": "RU",
    "ukraine": "UA",
    "belarus": "BY",
    "georgia": "GE",
    "armenia": "AM",
    "new caledonia": "NC",
    "monaco": "MC",
    "moldova": "MD",
    "isle of man": "IM",
    "ivory coast": "CI",
    "algeria": "DZ",
}

# ISO codes that are already valid (2 uppercase letters we've seen in data)
VALID_ISO_CODES = {
    "AM", "AR", "AT", "AU", "BE", "BO", "BR", "BY", "CA", "CH", "CI", "CL",
    "CN", "CZ", "DE", "DZ", "FI", "FR", "GB", "GE", "GR", "HK", "HR", "IE",
    "IM", "IN", "IQ", "IT", "KW", "LU", "LV", "MC", "MD", "MK", "MT", "MX",
    "MY", "NC", "NL", "NZ", "PH", "PL", "PR", "PT", "RO", "RU", "SE", "SK",
    "TR", "TW", "US", "VE", "VN", "ZA", "ID", "JP", "KR", "NO", "DK", "ES",
    "TH", "SG", "HU", "BG", "RS", "UA", "SA", "AE", "IL", "CO", "PE", "EG",
    "KE", "NG", "IS", "EE", "LT", "SI", "BA", "ME", "AL", "CY", "QA", "BH",
    "OM", "CR", "PA", "UY", "PY", "MA",
}

# ---------------------------------------------------------------------------
# Coordinate bounding boxes for country detection
# Format: (lat_min, lat_max, lng_min, lng_max, country_code)
# Order matters: more specific boxes first
# ---------------------------------------------------------------------------
COORD_BOUNDING_BOXES = [
    # Specific regions first (order matters: more specific before broader)

    # Canary Islands -> Spain (must be before Portugal/Morocco)
    (27.5, 29.5, -18.2, -13.3, "ES"),
    # Azores -> Portugal
    (36.9, 39.8, -31.3, -24.8, "PT"),
    # Madeira -> Portugal
    (32.3, 33.2, -17.3, -16.2, "PT"),
    # Faroe Islands -> Denmark
    (61.3, 62.5, -7.5, -6.2, "DK"),

    # Cyprus (must be before Turkey/Israel)
    (34.5, 35.7, 32.2, 34.7, "CY"),
    # Lebanon
    (33.0, 34.7, 35.0, 36.7, "LB"),
    # Malta
    (35.7, 36.1, 14.2, 14.6, "MT"),

    # UK
    (49.9, 60.9, -8.2, 1.8, "GB"),
    # Ireland
    (51.4, 55.5, -10.5, -5.5, "IE"),
    # Iceland
    (63.0, 67.0, -24.5, -13.0, "IS"),
    # Portugal
    (36.9, 42.2, -9.6, -6.1, "PT"),
    # Spain
    (35.9, 43.8, -9.4, 4.4, "ES"),
    # France
    (41.3, 51.1, -5.2, 8.3, "FR"),
    # Belgium
    (49.5, 51.6, 2.5, 6.4, "BE"),
    # Netherlands
    (50.7, 53.6, 3.3, 7.3, "NL"),
    # Luxembourg
    (49.4, 50.2, 5.7, 6.5, "LU"),
    # Switzerland
    (45.8, 47.9, 5.9, 10.5, "CH"),
    # Austria
    (46.3, 49.1, 9.5, 17.2, "AT"),
    # Germany
    (47.2, 55.1, 5.8, 15.1, "DE"),
    # Denmark
    (54.5, 57.8, 8.0, 15.2, "DK"),
    # Norway
    (57.9, 71.2, 4.5, 31.2, "NO"),
    # Sweden
    (55.3, 69.1, 11.0, 24.2, "SE"),
    # Finland
    (59.7, 70.1, 20.5, 31.6, "FI"),
    # Poland
    (49.0, 54.9, 14.1, 24.2, "PL"),
    # Czech Republic
    (48.5, 51.1, 12.1, 18.9, "CZ"),
    # Slovakia
    (47.7, 49.7, 16.8, 22.6, "SK"),
    # Hungary
    (45.7, 48.6, 16.1, 22.9, "HU"),
    # Romania
    (43.6, 48.3, 20.2, 29.8, "RO"),
    # Bulgaria
    (41.2, 44.3, 22.3, 28.7, "BG"),
    # Greece
    (34.8, 41.8, 19.3, 29.7, "GR"),
    # Croatia
    (42.3, 46.6, 13.5, 19.5, "HR"),
    # Slovenia
    (45.4, 46.9, 13.3, 16.6, "SI"),
    # Serbia
    (42.2, 46.2, 18.8, 23.1, "RS"),
    # Italy (mainland + islands)
    (35.5, 47.1, 6.6, 18.6, "IT"),
    # Turkey
    (35.8, 42.2, 25.6, 44.8, "TR"),
    # Israel
    (29.4, 33.4, 34.2, 35.9, "IL"),
    # Japan
    (24.2, 45.6, 122.9, 153.0, "JP"),
    # South Korea
    (33.1, 38.6, 124.6, 131.9, "KR"),
    # Taiwan
    (21.9, 25.4, 119.3, 122.1, "TW"),
    # Hong Kong
    (22.1, 22.6, 113.8, 114.4, "HK"),
    # Singapore
    (1.2, 1.5, 103.6, 104.0, "SG"),
    # Malaysia (Peninsular)
    (1.0, 7.5, 99.5, 104.5, "MY"),
    # Thailand
    (5.6, 20.5, 97.3, 105.7, "TH"),
    # Vietnam
    (8.2, 23.4, 102.1, 109.5, "VN"),
    # Philippines
    (4.6, 21.2, 116.9, 126.6, "PH"),
    # Indonesia (Java/Sumatra)
    (-11.0, 6.0, 95.0, 141.0, "ID"),
    # India
    (6.5, 35.7, 68.1, 97.4, "IN"),
    # China (broad)
    (18.0, 53.6, 73.5, 134.8, "CN"),
    # Australia
    (-44.0, -10.0, 112.9, 154.0, "AU"),
    # New Zealand
    (-47.4, -34.3, 166.3, 178.6, "NZ"),

    # Caribbean / Central America (must be before US/Mexico)
    # Puerto Rico
    (17.9, 18.6, -67.3, -65.5, "PR"),
    # Jamaica
    (17.7, 18.6, -78.4, -76.1, "JM"),
    # Dominican Republic
    (17.5, 20.0, -72.0, -68.3, "DO"),
    # Haiti
    (18.0, 20.1, -74.5, -71.6, "HT"),
    # Cuba
    (19.8, 23.3, -85.0, -74.1, "CU"),
    # Trinidad & Tobago
    (10.0, 11.4, -62.0, -60.5, "TT"),
    # Martinique (France)
    (14.3, 14.9, -61.3, -60.8, "FR"),
    # Guadeloupe (France)
    (15.8, 16.6, -62.0, -60.9, "FR"),
    # Costa Rica
    (8.0, 11.2, -86.0, -82.5, "CR"),
    # Panama
    (7.2, 9.7, -83.1, -77.2, "PA"),
    # Honduras
    (12.9, 16.5, -89.4, -83.1, "HN"),
    # El Salvador
    (13.1, 14.5, -90.2, -87.6, "SV"),
    # Guatemala
    (13.7, 17.8, -92.3, -88.2, "GT"),
    # Nicaragua
    (10.7, 15.0, -87.7, -82.6, "NI"),
    # Curacao
    (12.0, 12.5, -69.2, -68.7, "CW"),

    # US (contiguous)
    (24.5, 49.4, -124.8, -66.9, "US"),
    # Alaska
    (51.2, 71.4, -179.2, -129.9, "US"),
    # Hawaii
    (18.9, 22.3, -160.3, -154.8, "US"),
    # Canada
    (41.7, 83.2, -141.0, -52.6, "CA"),
    # Mexico
    (14.5, 32.7, -118.5, -86.7, "MX"),

    # South America
    # Peru
    (-18.4, -0.0, -81.4, -68.7, "PE"),
    # Ecuador
    (-5.0, 1.5, -81.1, -75.2, "EC"),
    # Brazil (broad)
    (-33.8, 5.3, -73.9, -34.8, "BR"),
    # Argentina
    (-55.1, -21.8, -73.6, -53.6, "AR"),
    # Colombia
    (-4.2, 12.5, -79.0, -66.8, "CO"),
    # Chile
    (-56.0, -17.5, -75.7, -66.4, "CL"),
    # Venezuela
    (0.6, 12.2, -73.4, -59.8, "VE"),
    # Suriname
    (1.8, 6.1, -58.1, -53.9, "SR"),

    # Africa
    # Morocco
    (27.6, 36.0, -13.2, -1.0, "MA"),
    # Algeria
    (18.9, 37.1, -9.0, 12.0, "DZ"),
    # Libya
    (19.5, 33.2, 9.3, 25.2, "LY"),
    # Egypt
    (22.0, 31.7, 24.7, 36.9, "EG"),
    # Kenya
    (-4.7, 5.0, 33.9, 41.9, "KE"),
    # Uganda
    (-1.5, 4.2, 29.5, 35.0, "UG"),
    # Ghana
    (4.7, 11.2, -3.3, 1.2, "GH"),
    # Ivory Coast
    (4.3, 10.8, -8.6, -2.5, "CI"),
    # Nigeria
    (4.2, 13.9, 2.7, 14.7, "NG"),
    # Senegal
    (12.3, 16.7, -17.6, -11.3, "SN"),
    # Mauritania
    (14.7, 27.3, -17.1, -4.8, "MR"),
    # Ethiopia
    (3.4, 14.9, 33.0, 48.0, "ET"),
    # Congo (DRC)
    (-13.5, 5.4, 12.2, 31.3, "CD"),
    # South Africa
    (-35.0, -22.1, 16.4, 33.0, "ZA"),
    # Namibia
    (-28.9, -17.0, 11.7, 25.3, "NA"),
    # Zimbabwe
    (-22.5, -15.6, 25.2, 33.1, "ZW"),
    # Zambia
    (-18.1, -8.2, 21.9, 33.7, "ZM"),
    # Gabon
    (-4.0, 2.3, 8.6, 14.5, "GA"),
    # Mauritius
    (-20.6, -19.9, 57.3, 57.8, "MU"),
    # Reunion (France)
    (-21.4, -20.8, 55.2, 55.9, "FR"),
    # New Caledonia (France)
    (-22.7, -19.6, 163.6, 168.2, "FR"),
    # French Polynesia (France)
    (-17.9, -16.0, -152.0, -148.0, "FR"),
    # Fiji
    (-20.7, -12.5, 177.0, -179.8, "FJ"),

    # Middle East
    # Saudi Arabia
    (16.3, 32.2, 34.5, 55.7, "SA"),
    # UAE
    (22.6, 26.1, 51.5, 56.4, "AE"),
    # Oman
    (16.6, 26.4, 51.9, 59.9, "OM"),
    # Kuwait
    (28.5, 30.1, 46.5, 48.5, "KW"),
    # Bahrain
    (25.8, 26.3, 50.4, 50.7, "BH"),
    # Qatar
    (24.5, 26.2, 50.7, 51.7, "QA"),
    # Iraq
    (29.0, 37.4, 38.8, 48.6, "IQ"),
    # Iran
    (25.0, 39.8, 44.0, 63.3, "IR"),
    # Azerbaijan
    (38.4, 41.9, 44.8, 50.4, "AZ"),
    # Armenia
    (38.8, 41.3, 43.4, 46.6, "AM"),
    # Georgia
    (41.0, 43.6, 40.0, 46.7, "GE"),
    # Tajikistan
    (36.7, 41.1, 67.3, 75.2, "TJ"),

    # Russia (European part)
    (41.2, 82.0, 19.6, 180.0, "RU"),
]

# ---------------------------------------------------------------------------
# Address-ending country patterns (last comma-separated token)
# ---------------------------------------------------------------------------
ADDRESS_COUNTRY_ENDINGS = {
    "USA": "US",
    "UK": "GB",
    "Canada": "CA",
    "Germany": "DE",
    "France": "FR",
    "Italy": "IT",
    "Spain": "ES",
    "Netherlands": "NL",
    "Switzerland": "CH",
    "Austria": "AT",
    "Japan": "JP",
    "Australia": "AU",
    "New Zealand": "NZ",
    "South Korea": "KR",
    "Malaysia": "MY",
    "Thailand": "TH",
    "Belgium": "BE",
    "Portugal": "PT",
    "Ireland": "IE",
    "Finland": "FI",
    "Norway": "NO",
    "Sweden": "SE",
    "Greece": "GR",
    "Czechia": "CZ",
    "Czech Republic": "CZ",
    "Denmark": "DK",
    "Hong Kong": "HK",
    "Mexico": "MX",
    "Poland": "PL",
    "Indonesia": "ID",
    "Luxembourg": "LU",
    "Hungary": "HU",
    "Romania": "RO",
    "Turkey": "TR",
    "Türkiye": "TR",
    "Brazil": "BR",
    "India": "IN",
    "China": "CN",
    "Singapore": "SG",
    "Philippines": "PH",
    "Colombia": "CO",
    "Argentina": "AR",
    "South Africa": "ZA",
    "Taiwan": "TW",
    "Saudi Arabia": "SA",
    "Israel": "IL",
    "Croatia": "HR",
    "Slovakia": "SK",
    "Slovenia": "SI",
    "Bulgaria": "BG",
    "Serbia": "RS",
    "Vietnam": "VN",
    "Russia": "RU",
    "Ukraine": "UA",
    "Chile": "CL",
}

# Regex for embedded country names that appear mid-address (e.g., "Taiwan 106")
EMBEDDED_COUNTRY_PATTERNS = [
    (re.compile(r"\bTaiwan\b", re.IGNORECASE), "TW"),
    (re.compile(r"\bHong Kong\b", re.IGNORECASE), "HK"),
    (re.compile(r"\bSingapore\b", re.IGNORECASE), "SG"),
    (re.compile(r"\bIndonesia\b", re.IGNORECASE), "ID"),
    (re.compile(r"\bMalaysia\b", re.IGNORECASE), "MY"),
    (re.compile(r"\bThailand\b", re.IGNORECASE), "TH"),
    (re.compile(r"\bPhilippines\b", re.IGNORECASE), "PH"),
    (re.compile(r"\bVietnam\b", re.IGNORECASE), "VN"),
    (re.compile(r"\bSouth Korea\b", re.IGNORECASE), "KR"),
    (re.compile(r"\bNorth Macedonia\b", re.IGNORECASE), "MK"),
]

# US state abbreviations (for city extraction from US addresses)
US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
    "DC",
}

# Canadian province abbreviations
CA_PROVINCES = {"AB", "BC", "MB", "NB", "NL", "NS", "NT", "NU", "ON", "PE", "QC", "SK", "YT"}


def normalize_country(value: str) -> str:
    """Normalize a country value to ISO 2-letter code."""
    if not value:
        return ""
    value = value.strip()
    # Already a valid 2-letter ISO code
    if len(value) == 2 and value.upper() in VALID_ISO_CODES:
        return value.upper()
    # Lookup by name
    lower = value.lower()
    if lower in COUNTRY_NAME_TO_ISO:
        return COUNTRY_NAME_TO_ISO[lower]
    return value  # return as-is if unrecognized


def extract_country_from_address(address: str) -> str:
    """Extract country ISO code from address string."""
    if not address:
        return ""
    address = address.strip()

    # 1. Try last comma-separated token
    parts = [p.strip() for p in address.split(",")]
    if len(parts) >= 2:
        last_token = parts[-1].strip()
        # Remove postal codes from the end: "USA", "UK", "Germany"
        # Some addresses end with "Country POSTCODE" like "Thailand 10110"
        # Clean the token: remove trailing digits/spaces
        clean_last = re.sub(r"\s*\d[\d\s-]*$", "", last_token).strip()
        if clean_last in ADDRESS_COUNTRY_ENDINGS:
            return ADDRESS_COUNTRY_ENDINGS[clean_last]
        # Try the raw token too
        if last_token in ADDRESS_COUNTRY_ENDINGS:
            return ADDRESS_COUNTRY_ENDINGS[last_token]

    # 2. Try embedded country patterns (e.g., "Taipei City, Taiwan 10565")
    for pattern, code in EMBEDDED_COUNTRY_PATTERNS:
        if pattern.search(address):
            return code

    return ""


def extract_country_from_coords(lat: float, lng: float) -> str:
    """Extract country ISO code from latitude/longitude using bounding boxes."""
    if lat is None or lng is None:
        return ""
    lat = float(lat)
    lng = float(lng)
    for lat_min, lat_max, lng_min, lng_max, code in COORD_BOUNDING_BOXES:
        if lat_min <= lat <= lat_max and lng_min <= lng <= lng_max:
            return code
    return ""


def extract_city_from_address(address: str, country_code: str) -> str:
    """Extract city from address string based on known patterns.

    Typical address formats:
      US:  "123 Main St, City, ST 12345, USA"
      UK:  "123 High St, City POSTCODE, UK"
      EU:  "Strasse 5, POSTCODE City, Country"
    """
    if not address:
        return ""
    address = address.strip()
    parts = [p.strip() for p in address.split(",")]
    if len(parts) < 2:
        return ""

    if country_code == "US":
        # US pattern: "street, City, ST ZIP, USA"
        # The city is typically 2nd-to-last before "ST ZIP" or 3rd-to-last before "USA"
        if len(parts) >= 3:
            # Find the part with state abbreviation + zip
            for i in range(len(parts) - 1, 0, -1):
                token = parts[i].strip()
                # Match "ST 12345" or "ST12345"
                m = re.match(r"^([A-Z]{2})\s+\d{5}", token)
                if m and m.group(1) in US_STATES:
                    # City is the part before this
                    city_candidate = parts[i - 1].strip()
                    if city_candidate and not re.match(r"^\d", city_candidate):
                        return city_candidate
        return ""

    elif country_code == "CA":
        # Canada: "street, City, PROV POSTAL, Canada"
        if len(parts) >= 3:
            for i in range(len(parts) - 1, 0, -1):
                token = parts[i].strip()
                # Match "ON M2N 7G9" style
                m = re.match(r"^([A-Z]{2})\s+[A-Z]\d[A-Z]", token)
                if m and m.group(1) in CA_PROVINCES:
                    city_candidate = parts[i - 1].strip()
                    if city_candidate and not re.match(r"^\d", city_candidate):
                        return city_candidate
        return ""

    elif country_code == "GB":
        # UK: "street, area, City POSTCODE, UK"
        # Postcode pattern: "XX## #XX" or similar
        if len(parts) >= 2:
            for i in range(len(parts) - 1, -1, -1):
                token = parts[i].strip()
                # Remove UK postcode and see what's left
                cleaned = re.sub(
                    r"\s*[A-Z]{1,2}\d{1,2}[A-Z]?\s+\d[A-Z]{2}\s*$", "", token
                ).strip()
                if cleaned and not re.match(r"^\d", cleaned) and len(cleaned) > 1:
                    # Skip if it looks like a street
                    if not re.search(r"\b(St|Rd|Ave|Blvd|Lane|Way|Dr|Ct|Pk|Pl|Close|Crescent|Terrace)\b", cleaned, re.IGNORECASE):
                        return cleaned
        return ""

    elif country_code in ("DE", "AT", "CH", "PL", "CZ", "HU", "SK"):
        # Continental Europe: "Strasse 5, POSTCODE City, Country"
        if len(parts) >= 2:
            # Try second-to-last part (before country)
            candidate = parts[-2].strip() if parts[-1].strip() in ADDRESS_COUNTRY_ENDINGS else parts[-1].strip()
            # Remove postal code prefix: "10117 Berlin" -> "Berlin"
            cleaned = re.sub(r"^\d{4,5}\s+", "", candidate).strip()
            # Also handle "DE-10117 Berlin"
            cleaned = re.sub(r"^[A-Z]{2}-?\d{4,5}\s+", "", cleaned).strip()
            if cleaned and not re.match(r"^\d", cleaned) and len(cleaned) > 1:
                return cleaned
        return ""

    elif country_code in ("FR", "ES", "IT", "PT", "NL", "BE", "LU"):
        # Similar European pattern
        if len(parts) >= 2:
            candidate = parts[-2].strip() if parts[-1].strip() in ADDRESS_COUNTRY_ENDINGS else parts[-1].strip()
            cleaned = re.sub(r"^\d{4,5}\s+", "", candidate).strip()
            cleaned = re.sub(r"^[A-Z]{2}-?\d{4,5}\s+", "", cleaned).strip()
            if cleaned and not re.match(r"^\d", cleaned) and len(cleaned) > 1:
                return cleaned
        return ""

    elif country_code in ("AU", "NZ"):
        # Australia: "street, City STATE POSTCODE, Australia"
        if len(parts) >= 2:
            for i in range(len(parts) - 1, 0, -1):
                token = parts[i].strip()
                # Match "City STATE POSTCODE" like "Perth WA 6000"
                m = re.match(r"^(.+?)\s+(?:NSW|VIC|QLD|SA|WA|TAS|NT|ACT)\s+\d{4}", token)
                if m:
                    return m.group(1).strip()
        return ""

    else:
        # Generic fallback: try second-to-last comma part
        if len(parts) >= 3:
            candidate = parts[-2].strip()
            # Remove postal codes
            cleaned = re.sub(r"^\d{3,6}\s+", "", candidate).strip()
            cleaned = re.sub(r"\s+\d{3,6}$", "", cleaned).strip()
            if cleaned and not re.match(r"^\d", cleaned) and len(cleaned) > 1:
                return cleaned

    return ""


def fix_countries(conn) -> dict:
    """Fix missing country values. Returns stats dict."""
    stats = {
        "from_address": 0,
        "from_coords": 0,
        "normalized": 0,
        "total_fixed": 0,
    }
    cur = conn.cursor()

    # Step 1: Normalize existing country values
    print("\n[1/3] Normalizing existing country values...")
    cur.execute(
        "SELECT DISTINCT country FROM locations "
        "WHERE country IS NOT NULL AND length(country) > 0"
    )
    existing_countries = [row[0] for row in cur.fetchall()]
    for country_val in existing_countries:
        normalized = normalize_country(country_val)
        if normalized != country_val:
            cur.execute(
                "UPDATE locations SET country = %s WHERE country = %s",
                (normalized, country_val),
            )
            count = cur.rowcount
            if count > 0:
                print(f"  Normalized '{country_val}' -> '{normalized}': {count} rows")
                stats["normalized"] += count
    conn.commit()

    # Step 2: Extract country from address
    print("\n[2/3] Extracting country from address...")
    cur.execute(
        "SELECT id, address, latitude, longitude FROM locations "
        "WHERE (country IS NULL OR country = '') "
        "AND address IS NOT NULL AND length(address) > 5"
    )
    rows = cur.fetchall()
    print(f"  Processing {len(rows)} rows with address...")

    batch = []
    batch_size = 500
    count_addr = 0
    for loc_id, address, lat, lng in rows:
        country = extract_country_from_address(address)
        if not country and lat is not None and lng is not None:
            country = extract_country_from_coords(float(lat), float(lng))
            if country:
                stats["from_coords"] += 1
        if country:
            batch.append((country, loc_id))
            if not country:
                pass
            else:
                count_addr += 1
                stats["from_address"] += 1

        if len(batch) >= batch_size:
            cur.executemany(
                "UPDATE locations SET country = %s WHERE id = %s", batch
            )
            conn.commit()
            batch = []

    if batch:
        cur.executemany(
            "UPDATE locations SET country = %s WHERE id = %s", batch
        )
        conn.commit()
    # Correct stats: from_address includes coord fallback, adjust
    stats["from_address"] = count_addr - stats["from_coords"]
    print(f"  Fixed from address text: {stats['from_address']}")
    print(f"  Fixed from coords fallback: {stats['from_coords']}")

    # Step 3: Extract country from coordinates only (no address)
    print("\n[3/3] Extracting country from coordinates (no address)...")
    cur.execute(
        "SELECT id, latitude, longitude FROM locations "
        "WHERE (country IS NULL OR country = '') "
        "AND latitude IS NOT NULL AND longitude IS NOT NULL"
    )
    rows = cur.fetchall()
    print(f"  Processing {len(rows)} rows with coords only...")

    batch = []
    count_coords = 0
    for loc_id, lat, lng in rows:
        country = extract_country_from_coords(float(lat), float(lng))
        if country:
            batch.append((country, loc_id))
            count_coords += 1

        if len(batch) >= batch_size:
            cur.executemany(
                "UPDATE locations SET country = %s WHERE id = %s", batch
            )
            conn.commit()
            batch = []

    if batch:
        cur.executemany(
            "UPDATE locations SET country = %s WHERE id = %s", batch
        )
        conn.commit()
    stats["from_coords"] += count_coords
    print(f"  Fixed from coordinates: {count_coords}")

    stats["total_fixed"] = stats["from_address"] + stats["from_coords"] + stats["normalized"]
    cur.close()
    return stats


def fix_cities(conn) -> dict:
    """Fix missing city values. Returns stats dict."""
    stats = {"from_address": 0, "total_fixed": 0}
    cur = conn.cursor()

    print("\n[CITY] Extracting city from address...")
    cur.execute(
        "SELECT id, address, country FROM locations "
        "WHERE (city IS NULL OR city = '') "
        "AND address IS NOT NULL AND length(address) > 5"
    )
    rows = cur.fetchall()
    print(f"  Processing {len(rows)} rows...")

    batch = []
    batch_size = 500
    for loc_id, address, country in rows:
        country_code = normalize_country(country) if country else ""
        city = extract_city_from_address(address, country_code)
        if city and len(city) <= 100:
            batch.append((city, loc_id))
            stats["from_address"] += 1

        if len(batch) >= batch_size:
            cur.executemany(
                "UPDATE locations SET city = %s WHERE id = %s", batch
            )
            conn.commit()
            batch = []

    if batch:
        cur.executemany(
            "UPDATE locations SET city = %s WHERE id = %s", batch
        )
        conn.commit()

    stats["total_fixed"] = stats["from_address"]
    cur.close()
    return stats


def fix_ratings(conn) -> dict:
    """Fix NULL ratings by computing from reviews table. Returns stats dict."""
    stats = {"from_reviews": 0, "rating_zero_cleared": 0, "total_fixed": 0}
    cur = conn.cursor()

    # Step 1: Compute average rating from reviews for locations with NULL rating
    print("\n[RATING] Computing ratings from reviews table...")
    cur.execute("""
        UPDATE locations l
        SET rating = sub.avg_rating
        FROM (
            SELECT r.location_id, ROUND(AVG(r.rating)::numeric, 1) as avg_rating
            FROM reviews r
            JOIN locations loc ON loc.id = r.location_id
            WHERE loc.rating IS NULL
            GROUP BY r.location_id
            HAVING COUNT(r.id) >= 1
        ) sub
        WHERE l.id = sub.location_id
    """)
    stats["from_reviews"] = cur.rowcount
    conn.commit()
    print(f"  Updated from reviews: {stats['from_reviews']}")

    # Step 2: Also update review_count where it's wrong
    print("\n[RATING] Updating review_count from actual reviews...")
    cur.execute("""
        UPDATE locations l
        SET review_count = sub.actual_count
        FROM (
            SELECT r.location_id, COUNT(r.id) as actual_count
            FROM reviews r
            GROUP BY r.location_id
        ) sub
        WHERE l.id = sub.location_id
          AND (l.review_count IS NULL OR l.review_count <> sub.actual_count)
    """)
    review_count_fixed = cur.rowcount
    conn.commit()
    print(f"  Review counts corrected: {review_count_fixed}")

    stats["total_fixed"] = stats["from_reviews"]
    cur.close()
    return stats


def print_final_stats(conn):
    """Print final data quality statistics."""
    cur = conn.cursor()
    cur.execute("""
        SELECT
            COUNT(*) as total,
            COUNT(CASE WHEN country IS NOT NULL AND length(country) > 0 THEN 1 END) as has_country,
            COUNT(CASE WHEN city IS NOT NULL AND length(city) > 0 THEN 1 END) as has_city,
            COUNT(CASE WHEN rating IS NOT NULL THEN 1 END) as has_rating,
            COUNT(CASE WHEN chain_id IS NOT NULL THEN 1 END) as has_chain_id,
            COUNT(CASE WHEN latitude IS NOT NULL THEN 1 END) as has_coords,
            COUNT(CASE WHEN place_id IS NOT NULL AND length(place_id) > 0 THEN 1 END) as has_place_id,
            COUNT(CASE WHEN name IS NOT NULL AND length(name) > 0 THEN 1 END) as has_name
        FROM locations
    """)
    row = cur.fetchone()
    total = row[0]

    print("\n" + "=" * 70)
    print("FINAL DATA QUALITY REPORT")
    print("=" * 70)
    labels = ["country", "city", "rating", "chain_id", "coordinates", "place_id", "name"]
    for i, label in enumerate(labels):
        val = row[i + 1]
        pct = (val / total * 100) if total > 0 else 0
        print(f"  {label:15s}: {val:>6d} / {total} ({pct:5.1f}%)")

    # Country distribution
    print("\nTop 15 countries:")
    cur.execute("""
        SELECT country, COUNT(*) as cnt
        FROM locations
        WHERE country IS NOT NULL AND length(country) > 0
        GROUP BY country
        ORDER BY cnt DESC
        LIMIT 15
    """)
    for country, cnt in cur.fetchall():
        pct = cnt / total * 100
        print(f"  {country:5s}: {cnt:>6d} ({pct:4.1f}%)")

    # Remaining missing
    cur.execute("""
        SELECT COUNT(*) FROM locations
        WHERE country IS NULL OR country = ''
    """)
    still_missing = cur.fetchone()[0]
    print(f"\nStill missing country: {still_missing} ({still_missing/total*100:.1f}%)")

    cur.execute("""
        SELECT COUNT(*) FROM locations
        WHERE city IS NULL OR city = ''
    """)
    city_missing = cur.fetchone()[0]
    print(f"Still missing city: {city_missing} ({city_missing/total*100:.1f}%)")

    cur.execute("""
        SELECT COUNT(*) FROM locations WHERE rating IS NULL
    """)
    rating_missing = cur.fetchone()[0]
    print(f"Still missing rating: {rating_missing} ({rating_missing/total*100:.1f}%)")

    cur.close()


def main():
    start = time.time()
    print("=" * 70)
    print("LOCATION DATA QUALITY FIXER")
    print("=" * 70)

    conn = get_connection()
    try:
        # Pre-fix stats
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM locations")
        total = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM locations WHERE country IS NOT NULL AND length(country) > 0")
        pre_country = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM locations WHERE city IS NOT NULL AND length(city) > 0")
        pre_city = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM locations WHERE rating IS NOT NULL")
        pre_rating = cur.fetchone()[0]
        cur.close()

        print(f"\nTotal locations: {total}")
        print(f"BEFORE - Country: {pre_country}/{total} ({pre_country/total*100:.1f}%)")
        print(f"BEFORE - City:    {pre_city}/{total} ({pre_city/total*100:.1f}%)")
        print(f"BEFORE - Rating:  {pre_rating}/{total} ({pre_rating/total*100:.1f}%)")

        # Fix countries
        country_stats = fix_countries(conn)
        print(f"\n--- Country fix summary ---")
        print(f"  Normalized existing: {country_stats['normalized']}")
        print(f"  From address text:   {country_stats['from_address']}")
        print(f"  From coordinates:    {country_stats['from_coords']}")
        print(f"  Total country fixes: {country_stats['total_fixed']}")

        # Fix cities
        city_stats = fix_cities(conn)
        print(f"\n--- City fix summary ---")
        print(f"  From address: {city_stats['from_address']}")

        # Fix ratings
        rating_stats = fix_ratings(conn)
        print(f"\n--- Rating fix summary ---")
        print(f"  From reviews: {rating_stats['from_reviews']}")

        # Final report
        print_final_stats(conn)

        elapsed = time.time() - start
        print(f"\nCompleted in {elapsed:.1f} seconds.")

    finally:
        return_connection(conn)


if __name__ == "__main__":
    main()
