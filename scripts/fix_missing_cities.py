#!/usr/bin/env python3
"""
Lead Segmentation Script
Automatically assigns segments to leads based on their titles
"""

import psycopg2
import os
from datetime import datetime

# Database config
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432'),
    'database': os.getenv('DB_NAME', 'reviewsignal'),
    'user': os.getenv('DB_USER', 'reviewsignal'),
    'password': os.getenv('DB_PASS', 'reviewsignal2026')
}

# Segmentation rules (order matters - first match wins)
SEGMENTATION_RULES = [
    # High Intent (check first - highest priority)
    {
        'segment': 'high_intent',
        'keywords': [],  # Will be set based on intent_strength
        'priority': 1
    },

    # CIO / C-Level
    {
        'segment': 'cio',
        'keywords': [
            'chief investment officer',
            'cio',
            'managing director',
            'md',
            'chief data officer',
            'cdo',
            'head of research',
            'director of research'
        ],
        'priority': 2
    },

    # Head of Alternative Data
    {
        'segment': 'head_alt_data',
        'keywords': [
            'head of alternative data',
            'alternative data',
            'alt data',
            'head of data',
            'director of data',
            'vp of data'
        ],
        'priority': 3
    },

    # Portfolio Manager
    {
        'segment': 'portfolio_manager',
        'keywords': [
            'portfolio manager',
            'pm',
            'senior pm',
            'associate pm',
            'investment analyst',
            'senior investment analyst'
        ],
        'priority': 4
    },

    # Quantitative Analyst
    {
        'segment': 'quant_analyst',
        'keywords': [
            'quantitative',
            'quant',
            'quantitative researcher',
            'quantitative analyst',
            'data scientist',
            'machine learning',
            'ml engineer'
        ],
        'priority': 5
    }
]


def get_segment_for_title(title, intent_strength=0):
    """
    Determine segment based on title and intent strength

    Args:
        title: Job title string
        intent_strength: Intent strength score (0-10)

    Returns:
        segment name or None
    """
    if not title:
        return None

    title_lower = title.lower()

    # Check high intent first (intent_strength >= 7)
    if intent_strength >= 7:
        return 'high_intent'

    # Check other segments
    for rule in SEGMENTATION_RULES[1:]:  # Skip high_intent rule
        for keyword in rule['keywords']:
            if keyword in title_lower:
                return rule['segment']

    return None


def segment_all_leads():
    """
    Segment all leads in the database
    """
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    try:
        # Get all leads with titles
        cur.execute("""
            SELECT id, title, email, lead_score
            FROM leads
            WHERE title IS NOT NULL
            AND email IS NOT NULL
        """)

        leads = cur.fetchall()

        print(f"\n{'='*70}")
        print(f"LEAD SEGMENTATION - {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
        print(f"{'='*70}\n")
        print(f"Total leads to segment: {len(leads)}\n")

        # Segment counts
        segment_counts = {
            'high_intent': 0,
            'cio': 0,
            'head_alt_data': 0,
            'portfolio_manager': 0,
            'quant_analyst': 0,
            'unclassified': 0
        }

        # Process each lead
        for lead_id, title, email, lead_score in leads:
            # Calculate intent_strength from lead_score (simple conversion)
            # lead_score 0-100 -> intent_strength 0-10
            intent_strength = (lead_score or 50) / 10 if lead_score else 5

            segment = get_segment_for_title(title, intent_strength)

            if segment:
                # Update lead with segment
                cur.execute("""
                    UPDATE leads
                    SET segment = %s
                    WHERE id = %s
                """, (segment, lead_id))

                segment_counts[segment] += 1
            else:
                segment_counts['unclassified'] += 1

        conn.commit()

        # Print results
        print("Segmentation Results:")
        print("-" * 70)
        for segment, count in segment_counts.items():
            percentage = (count / len(leads) * 100) if leads else 0
            campaign_id = get_campaign_id(segment)
            print(f"  {segment:20s}: {count:4d} leads ({percentage:5.1f}%) -> {campaign_id}")

        print("\n" + "="*70)
        print(f"✅ Segmentation complete! {len(leads)} leads processed.")
        print("="*70 + "\n")

        return segment_counts

    except Exception as e:
        conn.rollback()
        print(f"❌ Error: {e}")
        raise
    finally:
        cur.close()
        conn.close()


def get_campaign_id(segment):
    """Get Instantly campaign ID for segment"""
    campaign_map = {
        'portfolio_manager': os.getenv('INSTANTLY_CAMPAIGN_PM', 'NOT_SET'),
        'quant_analyst': os.getenv('INSTANTLY_CAMPAIGN_QUANT', 'NOT_SET'),
        'head_alt_data': os.getenv('INSTANTLY_CAMPAIGN_ALTDATA', 'NOT_SET'),
        'cio': os.getenv('INSTANTLY_CAMPAIGN_CIO', 'NOT_SET'),
        'high_intent': os.getenv('INSTANTLY_CAMPAIGN_INTENT', 'NOT_SET'),
    }
    return campaign_map.get(segment, 'unclassified')


def show_segment_stats():
    """Show detailed stats for each segment"""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    try:
        print("\n" + "="*70)
        print("DETAILED SEGMENT STATISTICS")
        print("="*70 + "\n")

        for segment in ['portfolio_manager', 'quant_analyst', 'head_alt_data', 'cio', 'high_intent']:
            cur.execute("""
                SELECT
                    COUNT(*) as total,
                    COUNT(DISTINCT company) as companies,
                    AVG(lead_score) as avg_score
                FROM leads
                WHERE segment = %s
                AND email IS NOT NULL
            """, (segment,))

            result = cur.fetchone()
            if result:
                total, companies, avg_score = result
                campaign_id = get_campaign_id(segment)

                print(f"{segment.upper().replace('_', ' ')}:")
                print(f"  Leads: {total}")
                print(f"  Companies: {companies}")
                print(f"  Avg Score: {avg_score:.1f}" if avg_score else "  Avg Score: N/A")
                print(f"  Campaign: {campaign_id}")
                print()

    finally:
        cur.close()
        conn.close()


if __name__ == '__main__':
    # Load environment
    from dotenv import load_dotenv
    load_dotenv()

    print("\n🎯 ReviewSignal Lead Segmentation Tool\n")

    # Segment all leads
    segment_counts = segment_all_leads()

    # Show detailed stats
    show_segment_stats()

    print("\n✅ Done! Leads are now segmented and ready for Instantly campaigns.\n")
