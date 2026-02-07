#!/usr/bin/env python3
"""
Export Leads to CSV for Instantly Import
Generates CSV files ready for direct upload to Instantly campaigns
"""

import psycopg2
import csv
import os
from datetime import datetime
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

# Database config
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432'),
    'database': os.getenv('DB_NAME', 'reviewsignal'),
    'user': os.getenv('DB_USER', 'reviewsignal'),
    'password': os.getenv('DB_PASS')
}

SEGMENTS = {
    'portfolio_manager': 'Portfolio Manager Outreach',
    'quant_analyst': 'Quant Analyst Outreach',
    'head_alt_data': 'Head of Alternative Data Outreach',
    'cio': 'CIO / Chief Investment Officer Outreach',
    'high_intent': 'High Intent Lead Outreach'
}

OUTPUT_DIR = 'exports/instantly/leads'


def ensure_output_dir():
    """Create output directory if it doesn't exist"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def export_segment_to_csv(segment_name, campaign_name):
    """
    Export leads for a specific segment to CSV

    Args:
        segment_name: Segment identifier (e.g., 'portfolio_manager')
        campaign_name: Human-readable campaign name
    """
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    try:
        # Get leads for this segment
        cur.execute("""
            SELECT
                email,
                name,
                SPLIT_PART(name, ' ', 1) as first_name,
                SPLIT_PART(name, ' ', 2) as last_name,
                title,
                company,
                linkedin_url,
                lead_score,
                personalized_angle
            FROM leads
            WHERE segment = %s
            AND email IS NOT NULL
            ORDER BY lead_score DESC, company
        """, (segment_name,))

        leads = cur.fetchall()

        if not leads:
            print(f"  ⚠️  No leads found for segment: {segment_name}")
            return 0

        # Write to CSV
        filename = f"{OUTPUT_DIR}/{segment_name}_leads.csv"

        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)

            # Header row (Instantly format)
            writer.writerow([
                'email',
                'firstName',
                'lastName',
                'companyName',
                'customVariables',  # JSON with extra fields
            ])

            # Data rows
            for lead in leads:
                email, name, first_name, last_name, title, company, linkedin, score, angle = lead

                # Build custom variables JSON
                custom_vars = {
                    'title': title or '',
                    'linkedin_url': linkedin or '',
                    'lead_score': score or 50,
                    'personalized_angle': angle or ''
                }

                # Format as JSON string
                import json
                custom_vars_json = json.dumps(custom_vars)

                writer.writerow([
                    email,
                    first_name or 'there',
                    last_name or '',
                    company or 'your firm',
                    custom_vars_json
                ])

        print(f"  ✅ {campaign_name}: {len(leads)} leads → {filename}")
        return len(leads)

    finally:
        cur.close()
        conn.close()


def export_all_segments():
    """Export all segments to CSV files"""
    print("\n" + "="*70)
    print("LEAD EXPORT TO INSTANTLY CSV FORMAT")
    print(f"Date: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    print("="*70 + "\n")

    ensure_output_dir()

    total_leads = 0

    for segment, campaign_name in SEGMENTS.items():
        count = export_segment_to_csv(segment, campaign_name)
        total_leads += count

    print("\n" + "="*70)
    print(f"✅ Export complete! {total_leads} total leads exported.")
    print(f"📁 Files saved to: {OUTPUT_DIR}/")
    print("="*70 + "\n")

    # Show file listing
    print("📄 Generated Files:\n")
    for segment in SEGMENTS.keys():
        filename = f"{segment}_leads.csv"
        filepath = os.path.join(OUTPUT_DIR, filename)
        if os.path.exists(filepath):
            size = os.path.getsize(filepath)
            print(f"  • {filename} ({size:,} bytes)")

    print("\n💡 Next Steps:")
    print("  1. Go to https://app.instantly.ai/app/campaigns")
    print("  2. Open each campaign")
    print("  3. Click 'Add Leads' → 'Upload CSV'")
    print("  4. Upload the corresponding CSV file")
    print("  5. Map columns: email, firstName, companyName")
    print("\n")


def show_segment_summary():
    """Show summary stats for each segment"""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    try:
        print("\n" + "="*70)
        print("SEGMENT SUMMARY")
        print("="*70 + "\n")

        for segment, campaign_name in SEGMENTS.items():
            cur.execute("""
                SELECT
                    COUNT(*) as total,
                    COUNT(DISTINCT company) as companies,
                    AVG(lead_score) as avg_score,
                    MIN(created_at) as oldest,
                    MAX(created_at) as newest
                FROM leads
                WHERE segment = %s
                AND email IS NOT NULL
            """, (segment,))

            result = cur.fetchone()
            if result:
                total, companies, avg_score, oldest, newest = result

                print(f"📊 {campaign_name}")
                print(f"   Leads: {total}")
                print(f"   Companies: {companies}")
                print(f"   Avg Score: {avg_score:.1f}" if avg_score else "   Avg Score: N/A")
                print(f"   Date Range: {oldest.strftime('%Y-%m-%d') if oldest else 'N/A'} to {newest.strftime('%Y-%m-%d') if newest else 'N/A'}")
                print()

    finally:
        cur.close()
        conn.close()


if __name__ == '__main__':
    # Load environment
    from dotenv import load_dotenv
    load_dotenv()

    print("\n🎯 ReviewSignal Lead Export Tool\n")

    # Show summary
    show_segment_summary()

    # Export all segments
    export_all_segments()

    print("✅ Done!\n")
