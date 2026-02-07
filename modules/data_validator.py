#!/usr/bin/env python3
"""
Data Validation Gates for ReviewSignal.ai

Validates locations, reviews, and leads before database insertion.
Auto-fixes recoverable issues (missing country, missing sentiment).
Rejects data that fails hard requirements.

Usage:
    from modules.data_validator import LocationValidator, ReviewValidator, LeadValidator

    valid, issues = LocationValidator.validate(location_dict)
    valid, issues = ReviewValidator.validate(review_dict)
    valid, issues = LeadValidator.validate(lead_dict)
"""

import re
import structlog
from typing import Tuple, List, Optional

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Country helpers
# ---------------------------------------------------------------------------

# Common country name -> ISO 3166-1 alpha-2 code
_COUNTRY_ALIASES = {
    # English names
    "united states": "US", "united states of america": "US", "usa": "US",
    "u.s.a.": "US", "u.s.": "US", "us": "US", "america": "US",
    "united kingdom": "GB", "uk": "GB", "great britain": "GB",
    "england": "GB", "scotland": "GB", "wales": "GB",
    "canada": "CA",
    "germany": "DE", "deutschland": "DE",
    "france": "FR",
    "spain": "ES", "espana": "ES",
    "italy": "IT", "italia": "IT",
    "netherlands": "NL", "the netherlands": "NL", "holland": "NL",
    "belgium": "BE", "belgique": "BE",
    "austria": "AT", "osterreich": "AT",
    "switzerland": "CH", "suisse": "CH", "schweiz": "CH",
    "luxembourg": "LU",
    "poland": "PL", "polska": "PL",
    "czech republic": "CZ", "czechia": "CZ",
    "sweden": "SE", "sverige": "SE",
    "denmark": "DK", "danmark": "DK",
    "norway": "NO", "norge": "NO",
    "finland": "FI", "suomi": "FI",
    "ireland": "IE",
    "portugal": "PT",
    "greece": "GR", "hellas": "GR",
    "australia": "AU",
    "new zealand": "NZ",
    "japan": "JP",
    "south korea": "KR", "korea": "KR",
    "singapore": "SG",
    "hong kong": "HK",
    "taiwan": "TW",
    "thailand": "TH",
    "malaysia": "MY",
    "indonesia": "ID",
    "mexico": "MX",
    "brazil": "BR",
    "india": "IN",
    "china": "CN",
    "russia": "RU",
    "turkey": "TR",
    "south africa": "ZA",
    "saudi arabia": "SA",
    "united arab emirates": "AE", "uae": "AE",
    "israel": "IL",
    "philippines": "PH",
    "vietnam": "VN",
    "argentina": "AR",
    "colombia": "CO",
    "chile": "CL",
    "peru": "PE",
    "romania": "RO",
    "hungary": "HU",
    "croatia": "HR",
    "slovakia": "SK",
    "slovenia": "SI",
    "bulgaria": "BG",
    "serbia": "RS",
    "ukraine": "UA",
    "egypt": "EG",
    "nigeria": "NG",
    "kenya": "KE",
    "morocco": "MA",
}

# Reverse map: already-valid 2-letter codes
_VALID_ISO_CODES = set(_COUNTRY_ALIASES.values())

# US state abbreviations (for address parsing)
_US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
    "DC",
}

# Canadian province abbreviations
_CA_PROVINCES = {"AB", "BC", "MB", "NB", "NL", "NS", "NT", "NU", "ON", "PE", "QC", "SK", "YT"}

# Rough bounding boxes: (min_lat, max_lat, min_lng, max_lng) -> country code
_COUNTRY_BBOXES = [
    (24.5, 49.5, -125.0, -66.0, "US"),
    (41.0, 83.5, -141.0, -52.0, "CA"),
    (49.0, 61.0, -11.0, 2.0, "GB"),
    (47.0, 55.5, 5.5, 15.5, "DE"),
    (41.0, 51.5, -5.5, 10.0, "FR"),
    (36.0, 43.8, -9.5, 3.5, "ES"),
    (36.5, 47.1, 6.5, 18.6, "IT"),
    (50.7, 53.7, 3.3, 7.3, "NL"),
    (46.3, 49.1, 13.0, 17.2, "AT"),
    (45.8, 47.9, 5.9, 10.5, "CH"),
    (49.4, 55.0, 14.1, 24.2, "PL"),
    (55.3, 69.1, 11.0, 24.2, "SE"),
    (54.5, 57.8, 8.0, 15.2, "DK"),
    (57.9, 71.3, 4.5, 31.2, "NO"),
    (59.7, 70.1, 19.5, 31.6, "FI"),
    (51.3, 55.5, -10.5, -5.5, "IE"),
    (36.9, 42.2, -9.5, -6.2, "PT"),
    (34.8, 42.0, 19.3, 29.7, "GR"),
    (-44.0, -10.0, 112.0, 154.0, "AU"),
    (-47.3, -34.0, 166.0, 178.8, "NZ"),
    (24.0, 46.0, 122.9, 153.9, "JP"),
    (33.0, 38.7, 124.5, 132.0, "KR"),
    (1.1, 1.5, 103.6, 104.1, "SG"),
    (22.1, 22.6, 113.8, 114.4, "HK"),
    (21.8, 25.4, 120.0, 122.1, "TW"),
    (5.6, 20.5, 97.3, 105.6, "TH"),
    (0.8, 7.4, 99.6, 119.3, "MY"),
    (-11.0, 6.1, 95.0, 141.0, "ID"),
    (14.5, 32.7, -118.5, -86.5, "MX"),
]


def normalize_country(country: str) -> str:
    """
    Convert a country name or partial code to ISO 3166-1 alpha-2.
    Returns original value if no mapping found.
    """
    if not country:
        return ""
    stripped = country.strip()
    upper = stripped.upper()
    # Already a valid 2-letter code
    if len(upper) == 2 and upper in _VALID_ISO_CODES:
        return upper
    # Lookup by lowercase alias
    result = _COUNTRY_ALIASES.get(stripped.lower())
    if result:
        return result
    return stripped  # Return as-is if we cannot map


def extract_country_from_address(address: str) -> str:
    """
    Parse the last segment of a comma-separated address to infer country.
    Examples:
        "123 Main St, New York, NY 10001, USA" -> "US"
        "Berliner Str 5, 10115 Berlin, Germany" -> "DE"
    """
    if not address:
        return ""
    parts = [p.strip() for p in address.split(",")]
    if not parts:
        return ""

    last = parts[-1].strip()
    # Try normalizing directly
    country = normalize_country(last)
    if country != last:
        return country

    # Check if last part looks like "STATE ZIP" (US pattern)
    match = re.match(r"^([A-Z]{2})\s+\d{5}", last)
    if match and match.group(1) in _US_STATES:
        return "US"

    # Check second-to-last for country
    if len(parts) >= 2:
        second_last = parts[-2].strip()
        country = normalize_country(second_last)
        if country != second_last:
            return country
        # Check "STATE ZIP" pattern in second-to-last
        match = re.match(r"^([A-Z]{2})\s+\d{5}", second_last)
        if match and match.group(1) in _US_STATES:
            return "US"
        # Canadian pattern: "Province PostalCode"
        match = re.match(r"^([A-Z]{2})\s+[A-Z]\d[A-Z]", second_last)
        if match and match.group(1) in _CA_PROVINCES:
            return "CA"

    return ""


def extract_country_from_coords(lat: Optional[float], lng: Optional[float]) -> str:
    """
    Simple bounding-box lookup for country based on latitude/longitude.
    Returns ISO 2-letter code or empty string.
    """
    if lat is None or lng is None:
        return ""
    try:
        lat_f = float(lat)
        lng_f = float(lng)
    except (TypeError, ValueError):
        return ""
    for min_lat, max_lat, min_lng, max_lng, code in _COUNTRY_BBOXES:
        if min_lat <= lat_f <= max_lat and min_lng <= lng_f <= max_lng:
            return code
    return ""


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------

class LocationValidator:
    """Validates location data before database insertion."""

    @staticmethod
    def validate(location_data: dict) -> Tuple[bool, List[str]]:
        """
        Validate location data dict. Mutates the dict in-place to auto-fix
        recoverable issues (e.g. missing country derived from address/coords,
        country normalization).

        Returns (is_valid, list_of_issues).
        Hard issues (name, place_id missing) make is_valid=False.
        Soft issues are logged as warnings but still pass validation.
        """
        issues: List[str] = []
        warnings: List[str] = []

        # --- Hard requirements ---
        name = location_data.get("name")
        if not name or (isinstance(name, str) and not name.strip()):
            issues.append("missing name")

        place_id = location_data.get("place_id")
        if not place_id or (isinstance(place_id, str) and not place_id.strip()):
            issues.append("missing place_id")

        # --- Country auto-fix ---
        country = location_data.get("country")
        if not country or (isinstance(country, str) and not country.strip()):
            # Try from address
            addr = location_data.get("address", "")
            derived = extract_country_from_address(addr)
            if derived:
                location_data["country"] = derived
            else:
                # Try from coordinates
                derived = extract_country_from_coords(
                    location_data.get("latitude"),
                    location_data.get("longitude"),
                )
                if derived:
                    location_data["country"] = derived
                else:
                    warnings.append("missing country (could not derive)")
        else:
            # Normalize existing country to ISO
            location_data["country"] = normalize_country(country)

        # --- Latitude / Longitude sanity ---
        lat = location_data.get("latitude")
        lng = location_data.get("longitude")
        if lat is not None and lng is not None:
            try:
                lat_f = float(lat)
                lng_f = float(lng)
                if not (-90 <= lat_f <= 90):
                    issues.append(f"latitude out of range: {lat_f}")
                if not (-180 <= lng_f <= 180):
                    issues.append(f"longitude out of range: {lng_f}")
            except (TypeError, ValueError):
                issues.append("invalid latitude/longitude type")

        # --- Rating sanity ---
        rating = location_data.get("rating")
        if rating is not None:
            try:
                r = float(rating)
                if not (0 <= r <= 5):
                    warnings.append(f"rating out of range: {r}")
            except (TypeError, ValueError):
                warnings.append("invalid rating type")

        # Log warnings for monitoring
        if warnings:
            logger.warning(
                "location_validation_warnings",
                place_id=place_id,
                name=name,
                warnings=warnings,
            )

        is_valid = len(issues) == 0
        return (is_valid, issues + warnings)


class ReviewValidator:
    """Validates review data before database insertion."""

    # Lazy-loaded sentiment analyzer (heavy import)
    _sentiment_analyzer = None

    @classmethod
    def _get_sentiment_analyzer(cls):
        if cls._sentiment_analyzer is None:
            from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
            cls._sentiment_analyzer = SentimentIntensityAnalyzer()
        return cls._sentiment_analyzer

    @staticmethod
    def validate(review_data: dict) -> Tuple[bool, List[str]]:
        """
        Validate review data dict. Mutates in-place to auto-score sentiment
        if missing.

        Returns (is_valid, list_of_issues).
        """
        issues: List[str] = []
        warnings: List[str] = []

        # --- Text ---
        text = review_data.get("text")
        if not text or (isinstance(text, str) and len(text.strip()) < 3):
            issues.append("missing or too short text")

        # --- Rating ---
        rating = review_data.get("rating")
        if rating is None:
            issues.append("missing rating")
        else:
            try:
                r = float(rating)
                if not (1 <= r <= 5):
                    issues.append(f"invalid rating: {r} (must be 1-5)")
            except (TypeError, ValueError):
                issues.append(f"non-numeric rating: {rating}")

        # --- Author ---
        author = review_data.get("author_name")
        if not author or (isinstance(author, str) and not author.strip()):
            warnings.append("missing author_name")

        # --- Auto-score sentiment if missing ---
        if review_data.get("sentiment_score") is None and text and isinstance(text, str) and len(text.strip()) >= 3:
            try:
                analyzer = ReviewValidator._get_sentiment_analyzer()
                score = analyzer.polarity_scores(text)["compound"]
                review_data["sentiment_score"] = round(score, 4)
            except Exception:
                warnings.append("sentiment scoring failed")

        if warnings:
            logger.debug(
                "review_validation_warnings",
                text_preview=str(text)[:50] if text else "",
                warnings=warnings,
            )

        is_valid = len(issues) == 0
        return (is_valid, issues + warnings)


class LeadValidator:
    """Validates lead data before database insertion."""

    # Domains that indicate test/fake leads
    _BLOCKED_DOMAINS = {
        "example.com", "example.org", "example.net",
        "test.com", "testing.com",
        "mailinator.com", "guerrillamail.com", "sharklasers.com",
        "tempmail.com", "throwaway.email", "fakeinbox.com",
        "yopmail.com", "dispostable.com", "maildrop.cc",
    }

    # Prefixes that indicate test accounts
    _BLOCKED_PREFIXES = ("test.", "test+", "fake.", "noreply", "no-reply", "donotreply")

    @staticmethod
    def validate(lead_data: dict) -> Tuple[bool, List[str]]:
        """
        Validate lead data dict.

        Returns (is_valid, list_of_issues).
        """
        issues: List[str] = []
        warnings: List[str] = []

        # --- Email (hard requirement) ---
        email = lead_data.get("email")
        if not email or (isinstance(email, str) and not email.strip()):
            issues.append("missing email")
        elif isinstance(email, str):
            email = email.strip().lower()
            lead_data["email"] = email  # normalize

            # Basic format check
            if "@" not in email:
                issues.append("invalid email format: missing @")
            else:
                local, _, domain = email.partition("@")
                if not local:
                    issues.append("invalid email format: empty local part")
                elif "." not in domain:
                    issues.append(f"invalid email format: domain '{domain}' has no dot")
                else:
                    # Check blocked domains
                    if domain in LeadValidator._BLOCKED_DOMAINS:
                        issues.append(f"test/fake lead: blocked domain '{domain}'")
                    # Check blocked prefixes
                    if any(local.startswith(p) for p in LeadValidator._BLOCKED_PREFIXES):
                        issues.append(f"test/fake lead: blocked prefix '{local}'")

        # --- Name ---
        name = lead_data.get("name")
        first_name = lead_data.get("first_name")
        last_name = lead_data.get("last_name")
        if not name and not (first_name and last_name):
            warnings.append("missing name (no name, first_name, or last_name)")

        # --- Company ---
        company = lead_data.get("company")
        if not company or (isinstance(company, str) and not company.strip()):
            warnings.append("missing company")

        # --- Title ---
        title = lead_data.get("title")
        if not title or (isinstance(title, str) and not title.strip()):
            warnings.append("missing title")

        if warnings:
            logger.info(
                "lead_validation_warnings",
                email=email,
                warnings=warnings,
            )

        is_valid = len(issues) == 0
        return (is_valid, issues + warnings)
