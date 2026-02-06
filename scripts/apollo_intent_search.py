#!/usr/bin/env python3
"""
Apollo Intent-Based Lead Search v2.0
=====================================
Advanced lead generation with Buying Intent filtering.

Features:
- Intent Data integration (intent_strength filtering)
- Smart scoring with intent boost
- Organization-level intent caching
- Dual-mode operation (intent-only vs intent-boost)
- Comprehensive analytics and reporting

Usage:
    # Standard mode (all leads, intent boost scoring)
    python3 apollo_intent_search.py --batch-size 63 --page 1

    # Intent-only mode (only high-intent leads)
    python3 apollo_intent_search.py --intent-only --min-intent 70

    # Dry run with intent analysis
    python3 apollo_intent_search.py --dry-run --analyze-intent

Schedule: 2x daily (9:00 UTC, 21:00 UTC)
Daily limit: 125 leads (within 4,000/month Apollo limit)

Author: ReviewSignal.ai
Version: 2.0.0
Last Updated: 2026-02-05
"""

import os
import sys
import json
import time
import argparse
import requests
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field, asdict
from collections import defaultdict
from functools import lru_cache
import hashlib

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# =============================================================================
# CONFIGURATION
# =============================================================================

APOLLO_API_KEY = os.getenv('APOLLO_API_KEY', 'koTQfXNe_OM599OsEpyEbA')
APOLLO_BASE_URL = "https://api.apollo.io/api/v1"
LEAD_RECEIVER_URL = os.getenv('LEAD_RECEIVER_URL', "http://localhost:8001/api/lead")

# Intent Topics configured in Apollo (2026-02-05)
INTENT_TOPICS = [
    "Customer Review",
    "Social Media Monitoring Software",
    "Reputation Management Services Providers",
    "Online Reputation Management Software",
    "Sentiment Analysis",
    "Product Reviews Software"
]

# Search filters - target hedge fund professionals
SEARCH_FILTERS = {
    "person_titles": [
        "Portfolio Manager",
        "Investment Analyst",
        "Quantitative Analyst",
        "Head of Alternative Data",
        "Data Scientist",
        "Head of Research",
        "CIO",
        "Managing Director",
        "Chief Investment Officer",
        "Director of Research",
        "Quantitative Researcher",
        "Head of Data",
        "VP Alternative Data",
        "Senior Analyst",
        "Research Director"
    ],
    "person_locations": [
        "Germany",
        "United States",
        "United Kingdom",
        "Switzerland",
        "Netherlands",
        "France",
        "Singapore",
        "Hong Kong",
        "Canada",
        "Australia"
    ],
    "organization_num_employees_ranges": [
        "51,200",
        "201,500",
        "501,1000",
        "1001,5000",
        "5001,10000",
        "10001+"
    ],
    "q_organization_keyword_tags": [
        "hedge fund",
        "asset management",
        "investment management",
        "private equity",
        "venture capital",
        "quantitative trading",
        "alternative investments"
    ]
}

# Scoring weights
SCORING_CONFIG = {
    "base_score": 50,
    "intent_weight": 0.3,          # Intent contributes 30% to final score
    "title_weight": 0.4,           # Title contributes 40%
    "company_size_weight": 0.2,    # Company size contributes 20%
    "location_weight": 0.1,        # Location contributes 10%
    "intent_boost_multiplier": 1.5, # High intent leads get 1.5x score
    "min_score_for_priority": 75,  # Score threshold for "high" priority
}


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class IntentSignal:
    """Represents buying intent data for an organization"""
    organization_id: str
    organization_name: str
    intent_strength: Optional[int] = None  # 0-100 scale
    has_intent_signal: bool = False
    intent_topics_matched: List[str] = field(default_factory=list)
    last_intent_date: Optional[str] = None

    @property
    def intent_level(self) -> str:
        """Categorize intent level"""
        if not self.intent_strength:
            return "none"
        if self.intent_strength >= 80:
            return "high"
        elif self.intent_strength >= 50:
            return "medium"
        elif self.intent_strength >= 20:
            return "low"
        return "minimal"

    @property
    def is_hot(self) -> bool:
        """Check if this is a hot lead (high intent)"""
        return self.intent_strength is not None and self.intent_strength >= 70


@dataclass
class LeadData:
    """Structured lead data"""
    email: str
    first_name: str
    last_name: str
    title: str
    company: str
    city: str = ""
    state: str = ""
    country: str = ""
    linkedin_url: str = ""
    lead_score: int = 50
    intent_score: int = 0
    intent_level: str = "none"
    priority: str = "medium"
    personalized_angle: str = ""
    source: str = "apollo_intent_search_v2"

    @property
    def name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    def to_dict(self) -> Dict:
        """Convert to dictionary for API submission"""
        return {
            "email": self.email,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "name": self.name,
            "title": self.title,
            "company": self.company,
            "city": self.city,
            "state": self.state,
            "country": self.country,
            "linkedin_url": self.linkedin_url,
            "lead_score": self.lead_score,
            "intent_score": self.intent_score,
            "intent_level": self.intent_level,
            "priority": self.priority,
            "personalized_angle": self.personalized_angle,
            "source": self.source
        }


@dataclass
class ProcessingStats:
    """Track processing statistics"""
    total_searched: int = 0
    total_with_intent: int = 0
    high_intent_count: int = 0
    medium_intent_count: int = 0
    low_intent_count: int = 0
    no_intent_count: int = 0
    saved_count: int = 0
    exists_count: int = 0
    failed_count: int = 0
    skipped_low_intent: int = 0
    api_calls: int = 0
    start_time: datetime = field(default_factory=datetime.now)

    @property
    def duration_seconds(self) -> float:
        return (datetime.now() - self.start_time).total_seconds()

    @property
    def success_rate(self) -> float:
        total = self.saved_count + self.exists_count + self.failed_count
        return (self.saved_count / total * 100) if total > 0 else 0

    @property
    def intent_rate(self) -> float:
        return (self.total_with_intent / self.total_searched * 100) if self.total_searched > 0 else 0


# =============================================================================
# APOLLO API CLIENT
# =============================================================================

class ApolloIntentClient:
    """
    Advanced Apollo.io API client with Intent Data support.

    Features:
    - Organization intent data fetching
    - LRU caching for organizations
    - Rate limiting
    - Comprehensive error handling
    """

    def __init__(self, api_key: str, rate_limit_delay: float = 0.7):
        self.api_key = api_key
        self.rate_limit_delay = rate_limit_delay
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Cache-Control': 'no-cache',
            'X-Api-Key': api_key
        })
        self._org_intent_cache: Dict[str, IntentSignal] = {}
        self._api_call_count = 0

    @property
    def api_calls(self) -> int:
        return self._api_call_count

    def _make_request(self, method: str, url: str, **kwargs) -> Optional[Dict]:
        """Make API request with error handling and rate limiting"""
        self._api_call_count += 1

        try:
            if method == 'POST':
                response = self.session.post(url, **kwargs)
            else:
                response = self.session.get(url, **kwargs)

            if response.status_code == 429:
                print("  ⏳ Rate limited, waiting 60s...")
                time.sleep(60)
                return self._make_request(method, url, **kwargs)

            response.raise_for_status()
            time.sleep(self.rate_limit_delay)
            return response.json()

        except requests.exceptions.RequestException as e:
            print(f"  ❌ API error: {e}")
            return None

    def search_people(self, batch_size: int = 63, page: int = 1) -> Dict:
        """
        Search for people matching criteria.

        Args:
            batch_size: Results per page (max 100)
            page: Page number

        Returns:
            API response with people data
        """
        url = f"{APOLLO_BASE_URL}/mixed_people/api_search"
        payload = {
            "page": page,
            "per_page": min(batch_size, 100),
            **SEARCH_FILTERS
        }

        result = self._make_request('POST', url, json=payload, timeout=30)
        return result or {}

    def get_organization_intent(self, org_domain: str, org_name: str = "") -> IntentSignal:
        """
        Fetch intent data for an organization.

        Attempts to fetch by domain first, falls back to name search.

        Args:
            org_domain: Organization's primary domain
            org_name: Organization name (for cache key fallback)

        Returns:
            IntentSignal with intent data
        """
        # Clean inputs
        org_domain = (org_domain or "").strip()
        org_name = (org_name or "").strip()

        # Check cache first
        cache_key = org_domain or org_name
        if not cache_key:
            return IntentSignal(
                organization_id="",
                organization_name="Unknown",
                intent_strength=None,
                has_intent_signal=False
            )

        if cache_key in self._org_intent_cache:
            return self._org_intent_cache[cache_key]

        result = None
        url = f"{APOLLO_BASE_URL}/organizations/enrich"

        # Try domain first (if available)
        if org_domain:
            try:
                self._api_call_count += 1
                response = self.session.post(
                    url,
                    json={"domain": org_domain},
                    timeout=30
                )
                if response.status_code == 200:
                    result = response.json()
                time.sleep(self.rate_limit_delay)
            except requests.exceptions.RequestException:
                pass  # Silently fall through to name search

        # Fallback to name search if domain failed
        if not result and org_name:
            try:
                self._api_call_count += 1
                response = self.session.post(
                    url,
                    json={"name": org_name},
                    timeout=30
                )
                if response.status_code == 200:
                    result = response.json()
                time.sleep(self.rate_limit_delay)
            except requests.exceptions.RequestException:
                pass  # Silent failure

        # Build IntentSignal from result
        if not result or 'organization' not in result:
            signal = IntentSignal(
                organization_id="",
                organization_name=org_name or "Unknown",
                intent_strength=None,
                has_intent_signal=False
            )
        else:
            org = result['organization']
            signal = IntentSignal(
                organization_id=org.get('id', ''),
                organization_name=org.get('name', org_name),
                intent_strength=org.get('intent_strength'),
                has_intent_signal=org.get('has_intent_signal_account', False),
                intent_topics_matched=org.get('intent_topics', []) or []
            )

        # Cache result
        self._org_intent_cache[cache_key] = signal
        return signal

    def search_organizations_with_intent(
        self,
        batch_size: int = 25,
        page: int = 1,
        min_intent: int = 0
    ) -> List[IntentSignal]:
        """
        Search organizations and get their intent data.

        Args:
            batch_size: Results per page
            page: Page number
            min_intent: Minimum intent strength filter

        Returns:
            List of IntentSignal objects
        """
        url = f"{APOLLO_BASE_URL}/mixed_companies/search"
        payload = {
            "page": page,
            "per_page": min(batch_size, 100),
            "organization_num_employees_ranges": SEARCH_FILTERS["organization_num_employees_ranges"],
            "q_organization_keyword_tags": SEARCH_FILTERS["q_organization_keyword_tags"]
        }

        result = self._make_request('POST', url, json=payload, timeout=30)

        if not result:
            return []

        signals = []
        for org in result.get('organizations', []):
            signal = IntentSignal(
                organization_id=org.get('id', ''),
                organization_name=org.get('name', ''),
                intent_strength=org.get('intent_strength'),
                has_intent_signal=org.get('has_intent_signal_account', False)
            )

            # Filter by minimum intent
            if signal.intent_strength is not None and signal.intent_strength >= min_intent:
                signals.append(signal)
            elif min_intent == 0:
                signals.append(signal)

        return signals

    def enrich_person(self, person_id: str) -> Optional[Dict]:
        """
        Enrich person with full data (email, LinkedIn, etc).

        Args:
            person_id: Apollo person ID

        Returns:
            Enriched person data or None
        """
        url = f"{APOLLO_BASE_URL}/people/match"
        payload = {
            "id": person_id,
            "reveal_personal_emails": True,
            "reveal_phone_number": False
        }

        result = self._make_request('POST', url, json=payload, timeout=30)
        return result.get('person') if result else None


# =============================================================================
# LEAD PROCESSOR WITH INTENT SCORING
# =============================================================================

class IntentLeadProcessor:
    """
    Advanced lead processor with intent-based scoring.

    Scoring Algorithm:
    - Base score from title (40%)
    - Intent score boost (30%)
    - Company size factor (20%)
    - Location tier (10%)
    """

    TITLE_SCORES = {
        # C-Level & Head positions (90-100)
        'chief investment officer': 100,
        'cio': 100,
        'head of alternative data': 98,
        'head of research': 95,
        'head of data': 95,
        'managing director': 92,
        'director of research': 90,

        # Senior positions (80-89)
        'portfolio manager': 88,
        'vp alternative data': 86,
        'senior analyst': 82,
        'research director': 85,

        # Mid-level (70-79)
        'quantitative analyst': 78,
        'quantitative researcher': 78,
        'investment analyst': 75,
        'data scientist': 75,

        # Default
        'default': 60
    }

    TIER1_LOCATIONS = ['united states', 'united kingdom', 'germany', 'switzerland']
    TIER2_LOCATIONS = ['france', 'netherlands', 'singapore', 'hong kong', 'canada']

    def __init__(self, lead_receiver_url: str):
        self.lead_receiver_url = lead_receiver_url
        self.session = requests.Session()
        self.session.headers.update({'Content-Type': 'application/json'})

    def calculate_title_score(self, title: str) -> int:
        """Calculate score based on job title"""
        if not title:
            return self.TITLE_SCORES['default']

        title_lower = title.lower()

        # Check exact matches first
        for key, score in self.TITLE_SCORES.items():
            if key in title_lower:
                return score

        # Keyword-based scoring
        if any(k in title_lower for k in ['head', 'chief', 'director', 'vp']):
            return 90
        elif any(k in title_lower for k in ['portfolio', 'senior', 'principal']):
            return 85
        elif any(k in title_lower for k in ['quant', 'analyst', 'researcher']):
            return 75

        return self.TITLE_SCORES['default']

    def calculate_location_score(self, country: str) -> int:
        """Calculate score based on location tier"""
        if not country:
            return 50

        country_lower = country.lower()

        if any(loc in country_lower for loc in self.TIER1_LOCATIONS):
            return 100
        elif any(loc in country_lower for loc in self.TIER2_LOCATIONS):
            return 80

        return 60

    def calculate_final_score(
        self,
        title: str,
        country: str,
        intent_signal: IntentSignal
    ) -> Tuple[int, int]:
        """
        Calculate final lead score with intent boost.

        Returns:
            Tuple of (final_score, intent_contribution)
        """
        title_score = self.calculate_title_score(title)
        location_score = self.calculate_location_score(country)

        # Intent score (0-100)
        intent_score = intent_signal.intent_strength or 0

        # Weighted calculation
        base = (
            title_score * SCORING_CONFIG['title_weight'] +
            location_score * SCORING_CONFIG['location_weight'] +
            SCORING_CONFIG['base_score'] * 0.3
        )

        # Intent boost
        intent_contribution = int(intent_score * SCORING_CONFIG['intent_weight'])

        # Apply multiplier for high intent
        if intent_signal.is_hot:
            base *= SCORING_CONFIG['intent_boost_multiplier']

        final_score = min(100, int(base + intent_contribution))

        return final_score, intent_contribution

    def generate_personalized_angle(
        self,
        title: str,
        company: str,
        intent_signal: IntentSignal
    ) -> str:
        """Generate intent-aware personalized outreach angle"""
        company = company or "your organization"

        # Intent-specific angles (these are HOT leads!)
        if intent_signal.is_hot:
            if 'sentiment' in str(intent_signal.intent_topics_matched).lower():
                return (
                    f"I noticed {company} is researching sentiment analysis solutions. "
                    f"ReviewSignal provides real-time consumer sentiment data from 500k+ locations "
                    f"with proven correlation to stock performance. Would love to share our methodology."
                )
            elif 'review' in str(intent_signal.intent_topics_matched).lower():
                return (
                    f"Saw that {company} is evaluating product review platforms. "
                    f"Our alternative data platform turns millions of consumer reviews into "
                    f"actionable investment signals. Happy to demo how hedge funds use this data."
                )
            elif 'reputation' in str(intent_signal.intent_topics_matched).lower():
                return (
                    f"I understand {company} is looking into reputation monitoring. "
                    f"ReviewSignal's sentiment tracking has helped quant funds identify "
                    f"brand perception shifts weeks before they hit financial reports."
                )
            else:
                return (
                    f"Based on {company}'s research interests, thought you might find value in "
                    f"our alternative data platform - real-time sentiment signals from 500k+ locations "
                    f"that institutional investors use for alpha generation."
                )

        # Title-based angles (cold leads)
        if not title:
            return (
                f"Alternative data platform for institutional investors: "
                f"Consumer sentiment signals from millions of reviews..."
            )

        title_lower = title.lower()

        if 'alternative data' in title_lower or 'alt data' in title_lower:
            return (
                f"As {title} at {company}, you understand the value of alternative data signals. "
                f"Our sentiment analysis platform tracks 500k+ locations in real-time..."
            )
        elif 'quantitative' in title_lower or 'quant' in title_lower:
            return (
                f"Quantitative edge for {company}: Real-time consumer sentiment data "
                f"from 500k+ locations with proven correlation to stock performance..."
            )
        elif 'portfolio manager' in title_lower:
            return (
                f"Enhanced alpha generation for {company}: Alternative data signals "
                f"with documented predictive power for consumer discretionary sector..."
            )
        elif 'head' in title_lower or 'director' in title_lower:
            return (
                f"Strategic data asset for {company}: Institutional-grade sentiment analytics "
                f"covering major retail, restaurant, and hospitality chains globally..."
            )

        return (
            f"Alternative data platform for institutional investors: "
            f"Consumer sentiment signals from millions of reviews..."
        )

    def process_lead(
        self,
        person: Dict,
        intent_signal: IntentSignal
    ) -> Optional[LeadData]:
        """
        Transform Apollo person data with intent scoring.

        Args:
            person: Apollo person object
            intent_signal: Organization's intent data

        Returns:
            LeadData object or None if invalid
        """
        # Extract email
        email = person.get('email') or person.get('sanitized_email')
        if not email or '@' not in email:
            return None

        # Extract basic info (with null safety)
        first_name = person.get('first_name') or ''
        last_name = person.get('last_name') or ''
        title = person.get('title') or ''

        # Organization info
        org = person.get('organization') or {}
        company = org.get('name') or ''

        # Location
        city = person.get('city') or ''
        state = person.get('state') or ''
        country = person.get('country') or ''

        # LinkedIn
        linkedin_url = person.get('linkedin_url') or ''

        # Calculate scores
        final_score, intent_contribution = self.calculate_final_score(
            title, country, intent_signal
        )

        # Determine priority
        if intent_signal.is_hot:
            priority = "critical"  # Hot intent leads
        elif final_score >= SCORING_CONFIG['min_score_for_priority']:
            priority = "high"
        elif final_score >= 60:
            priority = "medium"
        else:
            priority = "low"

        return LeadData(
            email=email,
            first_name=first_name,
            last_name=last_name,
            title=title,
            company=company,
            city=city,
            state=state,
            country=country,
            linkedin_url=linkedin_url,
            lead_score=final_score,
            intent_score=intent_signal.intent_strength or 0,
            intent_level=intent_signal.intent_level,
            priority=priority,
            personalized_angle=self.generate_personalized_angle(
                title, company, intent_signal
            )
        )

    def save_lead(self, lead: LeadData, dry_run: bool = False) -> bool:
        """Save lead to database via Lead Receiver API"""
        if dry_run:
            intent_badge = "🔥" if lead.intent_level in ['high', 'medium'] else ""
            print(f"  [DRY RUN] {intent_badge} {lead.email} - {lead.company} "
                  f"(score: {lead.lead_score}, intent: {lead.intent_level})")
            return True

        try:
            response = self.session.post(
                self.lead_receiver_url,
                json=lead.to_dict(),
                timeout=10
            )

            if response.status_code == 200:
                intent_badge = "🔥" if lead.intent_level in ['high', 'medium'] else "✅"
                print(f"  {intent_badge} Saved: {lead.email} - {lead.company} "
                      f"(score: {lead.lead_score}, intent: {lead.intent_level})")
                return True
            elif response.status_code == 409:
                print(f"  ⏭️  Exists: {lead.email}")
                return False
            else:
                print(f"  ❌ Failed: {lead.email} ({response.status_code})")
                return False

        except requests.exceptions.RequestException as e:
            print(f"  ❌ Error: {lead.email} - {e}")
            return False


# =============================================================================
# MAIN EXECUTION
# =============================================================================

def print_banner():
    """Print startup banner"""
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║     █████╗ ██████╗  ██████╗ ██╗     ██╗      ██████╗                        ║
║    ██╔══██╗██╔══██╗██╔═══██╗██║     ██║     ██╔═══██╗                       ║
║    ███████║██████╔╝██║   ██║██║     ██║     ██║   ██║                       ║
║    ██╔══██║██╔═══╝ ██║   ██║██║     ██║     ██║   ██║                       ║
║    ██║  ██║██║     ╚██████╔╝███████╗███████╗╚██████╔╝                       ║
║    ╚═╝  ╚═╝╚═╝      ╚═════╝ ╚══════╝╚══════╝ ╚═════╝                        ║
║                                                                              ║
║    ██╗███╗   ██╗████████╗███████╗███╗   ██╗████████╗                        ║
║    ██║████╗  ██║╚══██╔══╝██╔════╝████╗  ██║╚══██╔══╝                        ║
║    ██║██╔██╗ ██║   ██║   █████╗  ██╔██╗ ██║   ██║                           ║
║    ██║██║╚██╗██║   ██║   ██╔══╝  ██║╚██╗██║   ██║                           ║
║    ██║██║ ╚████║   ██║   ███████╗██║ ╚████║   ██║                           ║
║    ╚═╝╚═╝  ╚═══╝   ╚═╝   ╚══════╝╚═╝  ╚═══╝   ╚═╝                           ║
║                                                                              ║
║    SEARCH v2.0 - Buying Intent Powered Lead Generation                      ║
║    ReviewSignal.ai - Alternative Data for Hedge Funds                       ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
""")


def print_intent_topics():
    """Print configured intent topics"""
    print("\n📊 Configured Intent Topics:")
    print("─" * 50)
    for i, topic in enumerate(INTENT_TOPICS, 1):
        print(f"  {i}. {topic}")
    print("─" * 50)


def print_stats(stats: ProcessingStats):
    """Print processing statistics"""
    print(f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                           📊 PROCESSING SUMMARY                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  LEADS PROCESSED                                                             ║
║  ├─ Total searched:     {stats.total_searched:>6}                                           ║
║  ├─ With intent data:   {stats.total_with_intent:>6} ({stats.intent_rate:>5.1f}%)                                  ║
║  └─ Skipped (low):      {stats.skipped_low_intent:>6}                                           ║
║                                                                              ║
║  INTENT BREAKDOWN                                                            ║
║  ├─ 🔥 High intent:     {stats.high_intent_count:>6}                                           ║
║  ├─ 🟡 Medium intent:   {stats.medium_intent_count:>6}                                           ║
║  ├─ 🔵 Low intent:      {stats.low_intent_count:>6}                                           ║
║  └─ ⚪ No intent:       {stats.no_intent_count:>6}                                           ║
║                                                                              ║
║  RESULTS                                                                     ║
║  ├─ ✅ New leads saved: {stats.saved_count:>6}                                           ║
║  ├─ ⏭️  Already exists:  {stats.exists_count:>6}                                           ║
║  └─ ❌ Failed:          {stats.failed_count:>6}                                           ║
║                                                                              ║
║  PERFORMANCE                                                                 ║
║  ├─ Duration:           {stats.duration_seconds:>6.1f}s                                          ║
║  ├─ API calls:          {stats.api_calls:>6}                                           ║
║  └─ Success rate:       {stats.success_rate:>5.1f}%                                          ║
╚══════════════════════════════════════════════════════════════════════════════╝
""")


def main():
    parser = argparse.ArgumentParser(
        description='Apollo Intent-Based Lead Search v2.0',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Standard mode (all leads with intent scoring):
    python3 apollo_intent_search.py --batch-size 63 --page 1

  Intent-only mode (only high-intent leads):
    python3 apollo_intent_search.py --intent-only --min-intent 70

  Dry run with intent analysis:
    python3 apollo_intent_search.py --dry-run --analyze-intent
        """
    )

    parser.add_argument(
        '--batch-size', type=int, default=63,
        help='Number of leads to fetch per page (default: 63)'
    )
    parser.add_argument(
        '--page', type=int, default=1,
        help='Page number to fetch (default: 1)'
    )
    parser.add_argument(
        '--dry-run', action='store_true',
        help='Print leads without saving to database'
    )
    parser.add_argument(
        '--intent-only', action='store_true',
        help='Only process leads with intent data above threshold'
    )
    parser.add_argument(
        '--min-intent', type=int, default=50,
        help='Minimum intent score threshold (default: 50, used with --intent-only)'
    )
    parser.add_argument(
        '--analyze-intent', action='store_true',
        help='Print detailed intent analysis for each lead'
    )
    parser.add_argument(
        '--show-topics', action='store_true',
        help='Show configured intent topics and exit'
    )

    args = parser.parse_args()

    # Print banner
    print_banner()

    # Show topics and exit if requested
    if args.show_topics:
        print_intent_topics()
        return 0

    # Print configuration
    print(f"{'═'*78}")
    print(f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"📄 Page: {args.page}")
    print(f"📦 Batch size: {args.batch_size}")
    print(f"🎯 Mode: {'INTENT-ONLY' if args.intent_only else 'STANDARD'} "
          f"{'(DRY RUN)' if args.dry_run else '(LIVE)'}")
    if args.intent_only:
        print(f"🔥 Min intent threshold: {args.min_intent}")
    print(f"{'═'*78}\n")

    # Show intent topics
    print_intent_topics()

    # Initialize
    stats = ProcessingStats()
    client = ApolloIntentClient(APOLLO_API_KEY)
    processor = IntentLeadProcessor(LEAD_RECEIVER_URL)

    # Search for people
    print("\n📡 Searching Apollo.io for people...")
    search_results = client.search_people(batch_size=args.batch_size, page=args.page)

    if not search_results or 'people' not in search_results:
        print("❌ No results from Apollo search")
        return 1

    people = search_results.get('people', [])
    total_found = search_results.get('total_entries', 0)

    print(f"✅ Found {len(people)} people (total available: {total_found:,})\n")

    stats.total_searched = len(people)

    # Process each person
    for i, person in enumerate(people, 1):
        person_id = person.get('id')
        name = f"{person.get('first_name', '')} {person.get('last_name', '')}".strip()
        org_data = person.get('organization', {}) or {}
        company = org_data.get('name', 'Unknown')

        print(f"\n[{i}/{len(people)}] {name} @ {company}")

        # Get organization intent data
        org_domain = org_data.get('primary_domain', '')
        print(f"  🎯 Fetching intent data...")

        intent_signal = client.get_organization_intent(org_domain, company)

        # Track intent stats
        if intent_signal.intent_strength is not None:
            stats.total_with_intent += 1
            if intent_signal.intent_level == 'high':
                stats.high_intent_count += 1
            elif intent_signal.intent_level == 'medium':
                stats.medium_intent_count += 1
            else:
                stats.low_intent_count += 1
        else:
            stats.no_intent_count += 1

        # Print intent analysis if requested
        if args.analyze_intent:
            print(f"  📊 Intent: {intent_signal.intent_level.upper()} "
                  f"(strength: {intent_signal.intent_strength or 'N/A'})")
            if intent_signal.intent_topics_matched:
                print(f"  📌 Topics: {', '.join(intent_signal.intent_topics_matched[:3])}")

        # Skip if intent-only mode and below threshold
        if args.intent_only:
            if not intent_signal.intent_strength or intent_signal.intent_strength < args.min_intent:
                print(f"  ⏭️  Skipped: Intent below threshold ({args.min_intent})")
                stats.skipped_low_intent += 1
                continue

        # Enrich person (get full data with email)
        print("  🔍 Enriching person data...")
        enriched = client.enrich_person(person_id)

        if not enriched:
            print("  ❌ Enrichment failed")
            stats.failed_count += 1
            continue

        # Process lead with intent data
        lead = processor.process_lead(enriched, intent_signal)

        if not lead:
            print("  ⚠️  No email found")
            stats.failed_count += 1
            continue

        # Save lead
        if processor.save_lead(lead, dry_run=args.dry_run):
            stats.saved_count += 1
        else:
            stats.exists_count += 1

    # Update stats
    stats.api_calls = client.api_calls

    # Print summary
    print_stats(stats)

    # Success message
    if not args.dry_run and stats.saved_count > 0:
        print("💾 Database updated successfully!")
        if stats.high_intent_count > 0:
            print(f"🔥 {stats.high_intent_count} HIGH-INTENT leads ready for Instantly!")

    print(f"\n{'═'*78}\n")

    return 0


if __name__ == '__main__':
    sys.exit(main())
