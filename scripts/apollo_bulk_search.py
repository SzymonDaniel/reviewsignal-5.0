#!/usr/bin/env python3
"""
Apollo Bulk Lead Search
Fetches 125 leads per day from Apollo.io and saves to PostgreSQL

Usage:
    python3 apollo_bulk_search.py [--batch-size 63] [--dry-run]

Schedule: 2x daily (9:00 UTC, 21:00 UTC)
Daily limit: 125 leads (within 4,000/month Apollo limit)
"""

import os
import sys
import json
import time
import argparse
import requests
from datetime import datetime
from typing import List, Dict, Optional

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configuration
APOLLO_API_KEY = os.getenv('APOLLO_API_KEY', 'koTQfXNe_OM599OsEpyEbA')
APOLLO_BASE_URL = "https://api.apollo.io/api/v1"
LEAD_RECEIVER_URL = "http://localhost:8001/api/lead"

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
        "VP Alternative Data"
    ],
    "person_locations": [
        "Germany",
        "United States",
        "United Kingdom",
        "Switzerland",
        "Netherlands",
        "France",
        "Singapore",
        "Hong Kong"
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
        "venture capital"
    ]
}


class ApolloLeadFetcher:
    """Fetches leads from Apollo.io API"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Cache-Control': 'no-cache',
            'X-Api-Key': api_key
        })

    def search_people(self, batch_size: int = 63, page: int = 1) -> Dict:
        """
        Search for people matching our criteria

        Args:
            batch_size: Number of results per page (max 100)
            page: Page number to fetch

        Returns:
            API response dict with people data
        """
        url = f"{APOLLO_BASE_URL}/mixed_people/api_search"

        payload = {
            "page": page,
            "per_page": min(batch_size, 100),
            **SEARCH_FILTERS
        }

        try:
            response = self.session.post(url, json=payload, timeout=30)
            if response.status_code != 200:
                print(f"❌ Apollo search failed: {response.status_code}")
                print(f"Response: {response.text}")
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"❌ Apollo search failed: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response body: {e.response.text}")
            return {}

    def enrich_person(self, person_id: str) -> Optional[Dict]:
        """
        Enrich a person with full data (email, LinkedIn, etc)

        Args:
            person_id: Apollo person ID

        Returns:
            Enriched person data or None if failed
        """
        url = f"{APOLLO_BASE_URL}/people/match"

        payload = {
            "id": person_id,
            "reveal_personal_emails": True,
            "reveal_phone_number": False
        }

        try:
            response = self.session.post(url, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()
            return data.get('person')
        except requests.exceptions.RequestException as e:
            print(f"⚠️  Enrichment failed for {person_id}: {e}")
            return None


class LeadProcessor:
    """Processes and saves leads to database"""

    def __init__(self, lead_receiver_url: str):
        self.lead_receiver_url = lead_receiver_url
        self.session = requests.Session()
        self.session.headers.update({'Content-Type': 'application/json'})

    def process_lead(self, person: Dict) -> Optional[Dict]:
        """
        Transform Apollo person data to our lead format

        Args:
            person: Apollo person object

        Returns:
            Lead data dict or None if invalid
        """
        # Extract email
        email = person.get('email')
        if not email:
            # Try sanitized email
            email = person.get('sanitized_email')

        if not email or '@' not in email:
            return None

        # Extract basic info
        first_name = person.get('first_name', '')
        last_name = person.get('last_name', '')
        title = person.get('title', '')

        # Organization info
        org = person.get('organization') or {}
        company = org.get('name', '')

        # Location
        city = person.get('city', '')
        state = person.get('state', '')
        country = person.get('country', '')

        # LinkedIn
        linkedin_url = person.get('linkedin_url', '')

        # Calculate lead score based on title
        lead_score = 50  # default
        title_lower = title.lower() if title else ""
        if 'head' in title_lower or 'chief' in title_lower or 'director' in title_lower:
            lead_score = 90
        elif 'portfolio manager' in title_lower or 'cio' in title_lower:
            lead_score = 85
        elif 'quantitative' in title_lower or 'quant' in title_lower:
            lead_score = 80
        elif 'analyst' in title_lower:
            lead_score = 70

        lead_data = {
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            "name": f"{first_name} {last_name}".strip(),
            "title": title,
            "company": company,
            "city": city,
            "state": state,
            "country": country,
            "linkedin_url": linkedin_url,
            "lead_score": lead_score,
            "priority": "high" if lead_score >= 80 else "medium",
            "personalized_angle": self._generate_angle(title, company)
        }

        return lead_data

    def _generate_angle(self, title: str, company: str) -> str:
        """Generate personalized outreach angle"""
        if not title:
            return f"Alternative data platform for institutional investors: Consumer sentiment signals from millions of reviews..."
        title_lower = title.lower()

        if 'alternative data' in title_lower or 'alt data' in title_lower:
            return f"As {title} at {company}, you understand the value of alternative data signals. Our sentiment analysis platform..."
        elif 'quantitative' in title_lower or 'quant' in title_lower:
            return f"Quantitative edge for {company}: Real-time consumer sentiment data from 500k+ locations..."
        elif 'portfolio manager' in title_lower:
            return f"Enhanced alpha generation for {company}: Alternative data signals with proven correlation to stock performance..."
        else:
            return f"Alternative data platform for institutional investors: Consumer sentiment signals from millions of reviews..."

    def save_lead(self, lead: Dict, dry_run: bool = False) -> bool:
        """
        Save lead to database via Lead Receiver API

        Args:
            lead: Lead data dict
            dry_run: If True, don't actually save

        Returns:
            True if saved successfully
        """
        if dry_run:
            print(f"  [DRY RUN] Would save: {lead['email']} - {lead['company']}")
            return True

        try:
            response = self.session.post(self.lead_receiver_url, json=lead, timeout=10)

            if response.status_code == 200:
                print(f"  ✅ Saved: {lead['email']} - {lead['company']} ({lead['title']})")
                return True
            elif response.status_code == 409:
                print(f"  ⏭️  Exists: {lead['email']}")
                return False
            else:
                print(f"  ❌ Failed to save {lead['email']}: {response.status_code}")
                return False

        except requests.exceptions.RequestException as e:
            print(f"  ❌ Error saving {lead['email']}: {e}")
            return False


def main():
    parser = argparse.ArgumentParser(description='Apollo Bulk Lead Search')
    parser.add_argument('--batch-size', type=int, default=63,
                       help='Number of leads to fetch (default: 63)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Print leads without saving to database')
    parser.add_argument('--page', type=int, default=1,
                       help='Page number to fetch (for pagination)')
    args = parser.parse_args()

    print(f"\n{'='*70}")
    print(f"🚀 Apollo Bulk Lead Search")
    print(f"{'='*70}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"Batch size: {args.batch_size}")
    print(f"Page: {args.page}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    print(f"{'='*70}\n")

    # Initialize
    fetcher = ApolloLeadFetcher(APOLLO_API_KEY)
    processor = LeadProcessor(LEAD_RECEIVER_URL)

    # Search for people
    print("📡 Searching Apollo.io...")
    search_results = fetcher.search_people(batch_size=args.batch_size, page=args.page)

    if not search_results or 'people' not in search_results:
        print("❌ No results from Apollo search")
        return 1

    people = search_results.get('people', [])
    total_found = search_results.get('total_entries', 0)

    print(f"✅ Found {len(people)} people (total available: {total_found:,})\n")

    # Process each person
    saved_count = 0
    exists_count = 0
    failed_count = 0

    for i, person in enumerate(people, 1):
        person_id = person.get('id')
        name = f"{person.get('first_name', '')} {person.get('last_name', '')}".strip()
        company = person.get('organization', {}).get('name', 'Unknown')

        print(f"\n[{i}/{len(people)}] {name} @ {company}")

        # Enrich person (get full data with email)
        print("  🔍 Enriching...")
        enriched = fetcher.enrich_person(person_id)

        if not enriched:
            print("  ❌ Enrichment failed")
            failed_count += 1
            continue

        # Process lead
        lead = processor.process_lead(enriched)

        if not lead:
            print("  ⚠️  No email found")
            failed_count += 1
            continue

        # Save lead
        if processor.save_lead(lead, dry_run=args.dry_run):
            saved_count += 1
        else:
            exists_count += 1

        # Rate limiting (Apollo allows 100 requests/minute)
        time.sleep(0.7)  # ~85 requests/minute

    # Summary
    print(f"\n{'='*70}")
    print(f"📊 SUMMARY")
    print(f"{'='*70}")
    print(f"✅ New leads saved: {saved_count}")
    print(f"⏭️  Already exists: {exists_count}")
    print(f"❌ Failed: {failed_count}")
    print(f"📊 Total processed: {len(people)}")

    if not args.dry_run:
        print(f"\n💾 Database updated successfully!")

    print(f"{'='*70}\n")

    return 0


if __name__ == '__main__':
    sys.exit(main())
