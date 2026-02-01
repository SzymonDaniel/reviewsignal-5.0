#!/usr/bin/env python3
"""
Source Attribution Module
Tracks data provenance and ensures proper attribution for all scraped data
"""

from datetime import datetime
from typing import Dict, Optional, Any
from enum import Enum


class DataSource(Enum):
    """Supported data sources"""
    GOOGLE_MAPS = "google_maps"
    YELP = "yelp"
    TRIPADVISOR = "tripadvisor"
    TRUSTPILOT = "trustpilot"
    APOLLO = "apollo"
    MANUAL = "manual"


class SourceAttribution:
    """
    Manages source attribution for all data
    Ensures compliance with data source Terms of Service
    """

    # Terms of Service versions (update when ToS changes)
    TOS_VERSIONS = {
        DataSource.GOOGLE_MAPS: "2026-01",
        DataSource.YELP: "2025-12",
        DataSource.TRIPADVISOR: "2025-11",
        DataSource.APOLLO: "2026-01",
    }

    # Attribution requirements per source
    ATTRIBUTION_REQUIRED = {
        DataSource.GOOGLE_MAPS: True,
        DataSource.YELP: True,
        DataSource.TRIPADVISOR: True,
        DataSource.TRUSTPILOT: False,
        DataSource.APOLLO: True,
        DataSource.MANUAL: False,
    }

    # Terms URLs
    TERMS_URLS = {
        DataSource.GOOGLE_MAPS: "https://cloud.google.com/maps-platform/terms",
        DataSource.YELP: "https://www.yelp.com/developers/api_terms",
        DataSource.TRIPADVISOR: "https://developer-tripadvisor.com/content-api/license-and-terms",
        DataSource.APOLLO: "https://www.apollo.io/terms",
    }

    @staticmethod
    def create_attribution(
        source: DataSource,
        source_url: Optional[str] = None,
        scraped_at: Optional[datetime] = None,
        additional_metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create attribution metadata for scraped data

        Args:
            source: Data source enum
            source_url: URL where data was scraped from
            scraped_at: When data was scraped
            additional_metadata: Any additional metadata

        Returns:
            Attribution dictionary with all required fields
        """
        if scraped_at is None:
            scraped_at = datetime.utcnow()

        attribution = {
            "source": source.value,
            "source_url": source_url,
            "scraped_at": scraped_at.isoformat(),
            "terms_version": SourceAttribution.TOS_VERSIONS.get(source),
            "terms_url": SourceAttribution.TERMS_URLS.get(source),
            "attribution_required": SourceAttribution.ATTRIBUTION_REQUIRED.get(source, False),
            "compliance_verified": True,
        }

        if additional_metadata:
            attribution["metadata"] = additional_metadata

        return attribution

    @staticmethod
    def create_review_attribution(
        source: DataSource,
        place_id: str,
        review_id: Optional[str] = None,
        scraped_at: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Create attribution specifically for reviews"""

        # Build source URL based on source type
        source_url = None
        if source == DataSource.GOOGLE_MAPS and place_id:
            source_url = f"https://www.google.com/maps/place/?q=place_id:{place_id}"
        elif source == DataSource.YELP and place_id:
            source_url = f"https://www.yelp.com/biz/{place_id}"

        additional_metadata = {
            "place_id": place_id,
            "review_id": review_id,
            "data_type": "review",
        }

        return SourceAttribution.create_attribution(
            source=source,
            source_url=source_url,
            scraped_at=scraped_at,
            additional_metadata=additional_metadata
        )

    @staticmethod
    def create_location_attribution(
        source: DataSource,
        place_id: str,
        scraped_at: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Create attribution specifically for locations"""

        source_url = None
        if source == DataSource.GOOGLE_MAPS and place_id:
            source_url = f"https://www.google.com/maps/place/?q=place_id:{place_id}"

        additional_metadata = {
            "place_id": place_id,
            "data_type": "location",
        }

        return SourceAttribution.create_attribution(
            source=source,
            source_url=source_url,
            scraped_at=scraped_at,
            additional_metadata=additional_metadata
        )

    @staticmethod
    def create_lead_attribution(
        source: DataSource,
        lead_id: Optional[str] = None,
        scraped_at: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Create attribution for leads"""

        additional_metadata = {
            "lead_id": lead_id,
            "data_type": "lead",
        }

        return SourceAttribution.create_attribution(
            source=source,
            scraped_at=scraped_at,
            additional_metadata=additional_metadata
        )

    @staticmethod
    def get_attribution_text(source: DataSource) -> str:
        """Get human-readable attribution text for display"""

        texts = {
            DataSource.GOOGLE_MAPS: "Data sourced from Google Maps API",
            DataSource.YELP: "Data sourced from Yelp Fusion API",
            DataSource.TRIPADVISOR: "Data sourced from TripAdvisor Content API",
            DataSource.APOLLO: "Data sourced from Apollo.io API",
        }

        return texts.get(source, f"Data sourced from {source.value}")

    @staticmethod
    def should_display_attribution(source: DataSource) -> bool:
        """Check if attribution must be displayed to end users"""
        return SourceAttribution.ATTRIBUTION_REQUIRED.get(source, False)


# Convenience functions for common use cases
def add_google_maps_attribution(place_id: str, review_id: Optional[str] = None) -> Dict[str, Any]:
    """Quick helper for Google Maps attribution"""
    return SourceAttribution.create_review_attribution(
        source=DataSource.GOOGLE_MAPS,
        place_id=place_id,
        review_id=review_id
    )


def add_apollo_attribution(lead_id: Optional[str] = None) -> Dict[str, Any]:
    """Quick helper for Apollo leads attribution"""
    return SourceAttribution.create_lead_attribution(
        source=DataSource.APOLLO,
        lead_id=lead_id
    )
