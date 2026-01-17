#!/usr/bin/env python3
"""
LINKEDIN LEAD HUNTER - Find Decision Makers at Hedge Funds & PE
System 5.0.2 - Identifies and enriches leads from target financial firms

Author: ReviewSignal Team
Version: 5.0.2
Date: January 2026
"""

import asyncio
import re
import time
import csv
import json
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict, field
from enum import Enum
import structlog
from playwright.async_api import async_playwright, Browser, Page
import httpx

logger = structlog.get_logger()


# ═══════════════════════════════════════════════════════════════════
# ENUMS
# ═══════════════════════════════════════════════════════════════════

class CompanyTier(Enum):
    """Company tier classification for prioritization"""
    TIER_1 = "tier_1"  # Top hedge funds: Citadel, Bridgewater, Renaissance
    TIER_2 = "tier_2"  # Mid-size funds: Viking, Lone Pine, Tiger Global
    TIER_3 = "tier_3"  # Smaller funds and boutiques
    UNKNOWN = "unknown"


class LeadStatus(Enum):
    """Lead pipeline status"""
    NEW = "new"
    CONTACTED = "contacted"
    RESPONDED = "responded"
    MEETING_SCHEDULED = "meeting_scheduled"
    CONVERTED = "converted"
    REJECTED = "rejected"


# ═══════════════════════════════════════════════════════════════════
# DATACLASSES
# ═══════════════════════════════════════════════════════════════════

@dataclass
class EmailPattern:
    """Email pattern with confidence score"""
    pattern: str
    confidence: float
    examples: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class CompanyData:
    """Company information"""
    name: str
    industry: str
    size: str
    headquarters: str
    linkedin_url: str
    tier: CompanyTier
    domain: str = ""
    
    def to_dict(self) -> Dict:
        data = asdict(self)
        data['tier'] = self.tier.value
        return data


@dataclass
class LeadData:
    """Lead/contact information"""
    name: str
    first_name: str
    last_name: str
    title: str
    company: str
    company_tier: CompanyTier
    linkedin_url: str
    linkedin_profile_id: str
    email_guess: str
    email_confidence: float
    location: str
    industry: str
    outreach_priority: int
    priority_reasons: List[str]
    found_at: str
    status: LeadStatus = LeadStatus.NEW
    
    def to_dict(self) -> Dict:
        data = asdict(self)
        data['company_tier'] = self.company_tier.value
        data['status'] = self.status.value
        return data


# ═══════════════════════════════════════════════════════════════════
# HELPER CLASSES
# ═══════════════════════════════════════════════════════════════════

class EmailGuesser:
    """Guess professional email addresses based on patterns"""
    
    PATTERNS = [
        ("{first}.{last}@{domain}", 0.85),
        ("{first}{last}@{domain}", 0.75),
        ("{f}{last}@{domain}", 0.70),
        ("{first}@{domain}", 0.60),
        ("{last}.{first}@{domain}", 0.55),
        ("{f}.{last}@{domain}", 0.65),
        ("{first}_{last}@{domain}", 0.50),
    ]
    
    # Known company domains
    COMPANY_DOMAINS = {
        "citadel": "citadel.com",
        "bridgewater": "bridgewater.com",
        "bridgewater associates": "bridgewater.com",
        "renaissance technologies": "rentec.com",
        "two sigma": "twosigma.com",
        "d.e. shaw": "deshaw.com",
        "de shaw": "deshaw.com",
        "millennium": "mlp.com",
        "millennium management": "mlp.com",
        "point72": "point72.com",
        "aqr": "aqr.com",
        "aqr capital": "aqr.com",
        "man group": "man.com",
        "baupost": "baupost.com",
        "baupost group": "baupost.com",
        "elliott": "elliottmgmt.com",
        "elliott management": "elliottmgmt.com",
        "blackstone": "blackstone.com",
        "kkr": "kkr.com",
        "carlyle": "carlyle.com",
        "carlyle group": "carlyle.com",
        "apollo": "apollo.com",
        "apollo global": "apollo.com",
        "tpg": "tpg.com",
        "tpg capital": "tpg.com",
        "warburg pincus": "warburgpincus.com",
        "advent": "adventinternational.com",
        "advent international": "adventinternational.com",
        "bain capital": "baincapital.com",
        "goldman sachs": "gs.com",
        "morgan stanley": "morganstanley.com",
        "jp morgan": "jpmorgan.com",
        "jpmorgan": "jpmorgan.com",
        "blackrock": "blackrock.com",
        "vanguard": "vanguard.com",
        "fidelity": "fidelity.com",
        "state street": "statestreet.com",
        "viking global": "vikingglobal.com",
        "lone pine": "lonepinecapital.com",
        "tiger global": "tigerglobal.com",
        "coatue": "coatue.com",
        "third point": "thirdpoint.com",
        "pershing square": "pershingsquareholdings.com",
        "greenlight": "greenlightcapital.com",
    }
    
    @classmethod
    def guess_email(
        cls,
        first_name: str,
        last_name: str,
        company_name: str
    ) -> List[EmailPattern]:
        """
        Guess possible email addresses for a person.
        
        Returns list of EmailPattern objects sorted by confidence.
        """
        domain = cls._get_company_domain(company_name)
        if not domain:
            return []
        
        first = first_name.lower().strip()
        last = last_name.lower().strip()
        f = first[0] if first else ""
        
        results = []
        for pattern_template, confidence in cls.PATTERNS:
            try:
                email = pattern_template.format(
                    first=first,
                    last=last,
                    f=f,
                    domain=domain
                )
                # Clean email
                email = re.sub(r'[^a-z0-9@._-]', '', email.lower())
                
                results.append(EmailPattern(
                    pattern=pattern_template,
                    confidence=confidence,
                    examples=[email]
                ))
            except Exception:
                continue
        
        return sorted(results, key=lambda x: x.confidence, reverse=True)
    
    @classmethod
    def _get_company_domain(cls, company_name: str) -> str:
        """Get company domain from known mappings"""
        company_lower = company_name.lower().strip()
        
        # Direct match
        if company_lower in cls.COMPANY_DOMAINS:
            return cls.COMPANY_DOMAINS[company_lower]
        
        # Partial match
        for key, domain in cls.COMPANY_DOMAINS.items():
            if key in company_lower or company_lower in key:
                return domain
        
        # Generate from company name
        clean_name = re.sub(r'[^a-z0-9]', '', company_lower)
        return f"{clean_name}.com"


class PriorityScorer:
    """Calculate lead priority score based on title and company tier"""
    
    TITLE_SCORES = {
        # C-Suite
        "ceo": 100,
        "chief executive": 100,
        "cio": 95,
        "chief investment": 95,
        "cto": 90,
        "chief technology": 90,
        "cdo": 90,
        "chief data": 90,
        "coo": 85,
        "cfo": 85,
        
        # Founders/Partners
        "founder": 95,
        "co-founder": 95,
        "partner": 90,
        "managing partner": 95,
        "general partner": 90,
        "principal": 85,
        
        # Directors
        "managing director": 85,
        "director": 80,
        "head of": 80,
        "vp": 75,
        "vice president": 75,
        
        # Managers
        "portfolio manager": 85,
        "pm": 80,
        "senior manager": 70,
        "manager": 60,
        
        # Analysts/Researchers
        "senior analyst": 55,
        "research": 50,
        "analyst": 45,
        "quant": 70,
        "quantitative": 70,
        
        # Data specific
        "data": 65,
        "alternative data": 90,
        "alt data": 90,
        "data science": 70,
        "machine learning": 65,
    }
    
    TIER_MULTIPLIERS = {
        CompanyTier.TIER_1: 1.5,
        CompanyTier.TIER_2: 1.2,
        CompanyTier.TIER_3: 1.0,
        CompanyTier.UNKNOWN: 0.8,
    }
    
    @classmethod
    def calculate_priority(cls, lead: LeadData) -> int:
        """
        Calculate priority score (0-150) for a lead.
        Higher score = higher priority for outreach.
        """
        base_score = cls._score_title(lead.title)
        multiplier = cls.TIER_MULTIPLIERS.get(lead.company_tier, 1.0)
        
        final_score = int(base_score * multiplier)
        return min(final_score, 150)
    
    @classmethod
    def _score_title(cls, title: str) -> int:
        """Score a job title"""
        title_lower = title.lower()
        
        # Check for matches
        best_score = 0
        for keyword, score in cls.TITLE_SCORES.items():
            if keyword in title_lower:
                best_score = max(best_score, score)
        
        return best_score if best_score > 0 else 30  # Default score
    
    @classmethod
    def get_priority_reasons(cls, lead: LeadData) -> List[str]:
        """Get reasons why this lead is prioritized"""
        reasons = []
        title_lower = lead.title.lower()
        
        # Check title keywords
        if any(x in title_lower for x in ["cio", "chief investment", "cdo", "chief data"]):
            reasons.append("Decision maker for data purchases")
        
        if any(x in title_lower for x in ["alternative data", "alt data"]):
            reasons.append("Alternative data specialist")
        
        if any(x in title_lower for x in ["quant", "quantitative"]):
            reasons.append("Quantitative focus - likely data buyer")
        
        if any(x in title_lower for x in ["portfolio manager", "pm"]):
            reasons.append("Portfolio manager - influences data tools")
        
        # Company tier
        if lead.company_tier == CompanyTier.TIER_1:
            reasons.append("Tier 1 firm - high budget potential")
        elif lead.company_tier == CompanyTier.TIER_2:
            reasons.append("Tier 2 firm - good budget potential")
        
        return reasons if reasons else ["Standard lead"]


# ═══════════════════════════════════════════════════════════════════
# MAIN CLASS
# ═══════════════════════════════════════════════════════════════════

class LinkedInLeadHunter:
    """
    LinkedIn Lead Hunter for finding decision makers at hedge funds.
    Uses Playwright for browser automation.
    """
    
    # Tier 1 companies (highest priority)
    TIER_1_COMPANIES = [
        "Citadel", "Bridgewater", "Renaissance Technologies",
        "Two Sigma", "D.E. Shaw", "Millennium", "Point72",
        "AQR Capital", "Man Group", "Baupost", "Elliott Management",
        "Blackstone", "KKR", "Carlyle", "Apollo Global", "TPG",
        "Warburg Pincus", "Advent International", "Bain Capital",
        "Goldman Sachs", "Morgan Stanley", "JP Morgan", "BlackRock",
        "Vanguard", "Fidelity", "State Street"
    ]
    
    # Tier 2 companies
    TIER_2_COMPANIES = [
        "Viking Global", "Lone Pine", "Tiger Global", "Coatue",
        "Third Point", "Pershing Square", "Greenlight Capital",
        "Och-Ziff", "Canyon Capital", "Cerberus", "Fortress",
        "Oaktree Capital", "PIMCO", "Wellington", "Capital Group"
    ]
    
    # Target job titles for lead search
    TARGET_TITLES = [
        "Chief Investment Officer",
        "Chief Data Officer", 
        "Head of Alternative Data",
        "VP Alternative Data",
        "Director of Research",
        "Portfolio Manager",
        "Quantitative Researcher",
        "Data Science Lead",
        "Head of Quantitative Research",
    ]
    
    def __init__(
        self,
        session_cookie: str = None,
        proxy_url: str = None,
        rate_limit: int = 10,
        headless: bool = True
    ):
        """
        Initialize LinkedIn Lead Hunter.
        
        Args:
            session_cookie: LinkedIn li_at session cookie
            proxy_url: Proxy URL for requests
            rate_limit: Max requests per minute
            headless: Run browser in headless mode
        """
        self.session_cookie = session_cookie
        self.proxy_url = proxy_url
        self.rate_limit = rate_limit
        self.headless = headless
        self.min_delay = 60.0 / rate_limit
        self.last_request = 0.0
        
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        
        logger.info(
            "lead_hunter_initialized",
            rate_limit=rate_limit,
            headless=headless
        )
    
    # ───────────────────────────────────────────────────────────────
    # PUBLIC METHODS
    # ───────────────────────────────────────────────────────────────
    
    async def search_leads(
        self,
        query: str,
        location: str = None,
        filters: Dict = None
    ) -> List[LeadData]:
        """
        Search for leads matching query.
        
        Args:
            query: Search query (e.g., "Alternative Data")
            location: Location filter (e.g., "New York")
            filters: Additional filters
        
        Returns:
            List of LeadData objects
        """
        await self._ensure_browser()
        await self._rate_limit()
        
        leads = []
        
        try:
            # Build search URL
            search_url = self._build_search_url(query, location, filters)
            
            # Navigate to search
            await self.page.goto(search_url, wait_until='networkidle')
            await asyncio.sleep(2)
            
            # Parse results
            profiles = await self.page.query_selector_all('.search-result__info')
            
            for profile in profiles[:20]:  # Limit to 20 per search
                try:
                    lead = await self._parse_profile_card(profile)
                    if lead:
                        leads.append(lead)
                except Exception as e:
                    logger.warning("profile_parse_error", error=str(e))
                    continue
            
            logger.info(
                "search_complete",
                query=query,
                results=len(leads)
            )
            
        except Exception as e:
            logger.error("search_error", query=query, error=str(e))
        
        return leads
    
    async def search_by_company(
        self,
        company_name: str,
        titles: List[str] = None
    ) -> List[LeadData]:
        """
        Search for leads at a specific company.
        
        Args:
            company_name: Company name
            titles: Target job titles (optional)
        
        Returns:
            List of LeadData objects
        """
        titles = titles or self.TARGET_TITLES
        all_leads = []
        
        for title in titles:
            query = f"{title} {company_name}"
            leads = await self.search_leads(query)
            all_leads.extend(leads)
            await asyncio.sleep(self.min_delay)
        
        # Deduplicate
        seen_urls = set()
        unique_leads = []
        for lead in all_leads:
            if lead.linkedin_url not in seen_urls:
                seen_urls.add(lead.linkedin_url)
                unique_leads.append(lead)
        
        return unique_leads
    
    async def search_by_title(
        self,
        title: str,
        industry: str = "Investment Management"
    ) -> List[LeadData]:
        """
        Search for leads by job title.
        
        Args:
            title: Job title to search
            industry: Industry filter
        
        Returns:
            List of LeadData objects
        """
        query = f"{title}"
        filters = {"industry": industry}
        return await self.search_leads(query, filters=filters)
    
    async def get_lead_details(self, linkedin_url: str) -> Optional[LeadData]:
        """
        Get detailed information about a lead from their profile.
        
        Args:
            linkedin_url: LinkedIn profile URL
        
        Returns:
            LeadData object or None
        """
        await self._ensure_browser()
        await self._rate_limit()
        
        try:
            await self.page.goto(linkedin_url, wait_until='networkidle')
            await asyncio.sleep(2)
            
            return await self._parse_full_profile()
            
        except Exception as e:
            logger.error("profile_fetch_error", url=linkedin_url, error=str(e))
            return None
    
    def enrich_lead(self, lead: LeadData) -> LeadData:
        """
        Enrich lead with email guess and priority score.
        
        Args:
            lead: LeadData object
        
        Returns:
            Enriched LeadData object
        """
        # Guess email
        email_guesses = EmailGuesser.guess_email(
            lead.first_name,
            lead.last_name,
            lead.company
        )
        
        if email_guesses:
            lead.email_guess = email_guesses[0].examples[0]
            lead.email_confidence = email_guesses[0].confidence
        
        # Calculate priority
        lead.outreach_priority = PriorityScorer.calculate_priority(lead)
        lead.priority_reasons = PriorityScorer.get_priority_reasons(lead)
        
        return lead
    
    def export_leads(
        self,
        leads: List[LeadData],
        format: str = "csv"
    ) -> str:
        """
        Export leads to file.
        
        Args:
            leads: List of LeadData objects
            format: Export format ('csv' or 'json')
        
        Returns:
            File path
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if format == "csv":
            filename = f"leads_export_{timestamp}.csv"
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                if leads:
                    writer = csv.DictWriter(f, fieldnames=leads[0].to_dict().keys())
                    writer.writeheader()
                    for lead in leads:
                        writer.writerow(lead.to_dict())
        
        elif format == "json":
            filename = f"leads_export_{timestamp}.json"
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump([lead.to_dict() for lead in leads], f, indent=2)
        
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        logger.info("leads_exported", filename=filename, count=len(leads))
        return filename
    
    async def hunt_all_tiers(self) -> Dict[str, List[LeadData]]:
        """
        Hunt leads from all tier companies.
        
        Returns:
            Dict with tier keys and lead lists
        """
        results = {
            "tier_1": [],
            "tier_2": [],
        }
        
        # Tier 1
        for company in self.TIER_1_COMPANIES[:5]:  # Limit for safety
            leads = await self.search_by_company(company)
            for lead in leads:
                lead.company_tier = CompanyTier.TIER_1
                lead = self.enrich_lead(lead)
            results["tier_1"].extend(leads)
            await asyncio.sleep(5)
        
        # Tier 2
        for company in self.TIER_2_COMPANIES[:5]:
            leads = await self.search_by_company(company)
            for lead in leads:
                lead.company_tier = CompanyTier.TIER_2
                lead = self.enrich_lead(lead)
            results["tier_2"].extend(leads)
            await asyncio.sleep(5)
        
        return results
    
    # ───────────────────────────────────────────────────────────────
    # PRIVATE METHODS
    # ───────────────────────────────────────────────────────────────
    
    async def _ensure_browser(self) -> None:
        """Ensure browser is initialized"""
        if not self.browser:
            playwright = await async_playwright().start()
            
            browser_args = {"headless": self.headless}
            if self.proxy_url:
                browser_args["proxy"] = {"server": self.proxy_url}
            
            self.browser = await playwright.chromium.launch(**browser_args)
            self.page = await self.browser.new_page()
            
            # Set session cookie if provided
            if self.session_cookie:
                await self.page.context.add_cookies([{
                    "name": "li_at",
                    "value": self.session_cookie,
                    "domain": ".linkedin.com",
                    "path": "/"
                }])
            
            logger.info("browser_initialized")
    
    async def _rate_limit(self) -> None:
        """Apply rate limiting"""
        now = time.time()
        elapsed = now - self.last_request
        if elapsed < self.min_delay:
            await asyncio.sleep(self.min_delay - elapsed)
        self.last_request = time.time()
    
    def _build_search_url(
        self,
        query: str,
        location: str = None,
        filters: Dict = None
    ) -> str:
        """Build LinkedIn search URL"""
        base = "https://www.linkedin.com/search/results/people/?"
        params = [f"keywords={query.replace(' ', '%20')}"]
        
        if location:
            params.append(f"geoUrn={location}")
        
        if filters:
            if filters.get("industry"):
                params.append(f"industry={filters['industry']}")
        
        return base + "&".join(params)
    
    async def _parse_profile_card(self, element) -> Optional[LeadData]:
        """Parse a profile card from search results"""
        try:
            name_elem = await element.query_selector('.actor-name')
            name = await name_elem.inner_text() if name_elem else ""
            
            title_elem = await element.query_selector('.subline-level-1')
            title = await title_elem.inner_text() if title_elem else ""
            
            location_elem = await element.query_selector('.subline-level-2')
            location = await location_elem.inner_text() if location_elem else ""
            
            link_elem = await element.query_selector('a.search-result__result-link')
            linkedin_url = await link_elem.get_attribute('href') if link_elem else ""
            
            # Parse name
            name_parts = name.split()
            first_name = name_parts[0] if name_parts else ""
            last_name = name_parts[-1] if len(name_parts) > 1 else ""
            
            # Extract company from title
            company = ""
            if " at " in title:
                company = title.split(" at ")[-1].strip()
            elif " @ " in title:
                company = title.split(" @ ")[-1].strip()
            
            # Determine company tier
            company_tier = self._determine_company_tier(company)
            
            lead = LeadData(
                name=name,
                first_name=first_name,
                last_name=last_name,
                title=title,
                company=company,
                company_tier=company_tier,
                linkedin_url=linkedin_url,
                linkedin_profile_id=linkedin_url.split("/in/")[-1].rstrip("/") if "/in/" in linkedin_url else "",
                email_guess="",
                email_confidence=0.0,
                location=location,
                industry="Finance",
                outreach_priority=0,
                priority_reasons=[],
                found_at=datetime.utcnow().isoformat()
            )
            
            return self.enrich_lead(lead)
            
        except Exception as e:
            logger.warning("profile_card_parse_error", error=str(e))
            return None
    
    async def _parse_full_profile(self) -> Optional[LeadData]:
        """Parse full profile page"""
        try:
            name_elem = await self.page.query_selector('h1.text-heading-xlarge')
            name = await name_elem.inner_text() if name_elem else ""
            
            title_elem = await self.page.query_selector('.text-body-medium')
            title = await title_elem.inner_text() if title_elem else ""
            
            location_elem = await self.page.query_selector('.text-body-small.inline')
            location = await location_elem.inner_text() if location_elem else ""
            
            # Parse company from experience section
            company = ""
            exp_elem = await self.page.query_selector('.experience-item__subtitle')
            if exp_elem:
                company = await exp_elem.inner_text()
            
            name_parts = name.split()
            first_name = name_parts[0] if name_parts else ""
            last_name = name_parts[-1] if len(name_parts) > 1 else ""
            
            company_tier = self._determine_company_tier(company)
            
            lead = LeadData(
                name=name,
                first_name=first_name,
                last_name=last_name,
                title=title,
                company=company,
                company_tier=company_tier,
                linkedin_url=self.page.url,
                linkedin_profile_id=self.page.url.split("/in/")[-1].rstrip("/"),
                email_guess="",
                email_confidence=0.0,
                location=location,
                industry="Finance",
                outreach_priority=0,
                priority_reasons=[],
                found_at=datetime.utcnow().isoformat()
            )
            
            return self.enrich_lead(lead)
            
        except Exception as e:
            logger.error("full_profile_parse_error", error=str(e))
            return None
    
    def _determine_company_tier(self, company_name: str) -> CompanyTier:
        """Determine company tier from name"""
        company_lower = company_name.lower()
        
        for tier1 in self.TIER_1_COMPANIES:
            if tier1.lower() in company_lower:
                return CompanyTier.TIER_1
        
        for tier2 in self.TIER_2_COMPANIES:
            if tier2.lower() in company_lower:
                return CompanyTier.TIER_2
        
        # Check for finance keywords
        finance_keywords = ["capital", "partners", "asset", "investment", "fund", "hedge"]
        if any(kw in company_lower for kw in finance_keywords):
            return CompanyTier.TIER_3
        
        return CompanyTier.UNKNOWN
    
    async def close(self) -> None:
        """Close browser"""
        if self.browser:
            await self.browser.close()
            self.browser = None
            self.page = None
            logger.info("browser_closed")


# ═══════════════════════════════════════════════════════════════════
# CLI / MAIN
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    async def main():
        print("\n" + "="*60)
        print("🎯 LINKEDIN LEAD HUNTER - TEST RUN")
        print("="*60)
        
        # Initialize hunter (without session cookie for demo)
        hunter = LinkedInLeadHunter(
            rate_limit=5,
            headless=True
        )
        
        # Demo: Show email guessing
        print("\n📧 Email Guessing Demo:")
        guesses = EmailGuesser.guess_email("John", "Smith", "Citadel")
        for g in guesses[:3]:
            print(f"  • {g.examples[0]} (confidence: {g.confidence:.0%})")
        
        # Demo: Show priority scoring
        print("\n📊 Priority Scoring Demo:")
        demo_lead = LeadData(
            name="John Smith",
            first_name="John",
            last_name="Smith",
            title="Chief Investment Officer",
            company="Citadel",
            company_tier=CompanyTier.TIER_1,
            linkedin_url="https://linkedin.com/in/johnsmith",
            linkedin_profile_id="johnsmith",
            email_guess="",
            email_confidence=0,
            location="New York",
            industry="Finance",
            outreach_priority=0,
            priority_reasons=[],
            found_at=datetime.utcnow().isoformat()
        )
        
        enriched = hunter.enrich_lead(demo_lead)
        print(f"  Lead: {enriched.name} @ {enriched.company}")
        print(f"  Priority Score: {enriched.outreach_priority}/150")
        print(f"  Email Guess: {enriched.email_guess}")
        print(f"  Reasons: {', '.join(enriched.priority_reasons)}")
        
        await hunter.close()
        
        print("\n" + "="*60)
        print("✅ Lead Hunter test complete!")
        print("="*60)
    
    asyncio.run(main())
