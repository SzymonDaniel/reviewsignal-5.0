#!/usr/bin/env python3
"""
Lead Enrichment Script - Fix data completeness gaps.

Enriches leads with:
1. company_domain extracted from email address
2. industry inferred from company name
3. company_size inferred from known companies
4. company_name populated from company field (if empty)
5. personalized_angle generated for leads missing one
6. enriched_at timestamp for all enriched leads
7. company backfilled from email domain mapping

Uses modules/db.py for connections.
"""

import os
import sys
from datetime import datetime, timezone

# Setup path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

from modules.db import get_connection, return_connection

# ---------------------------------------------------------------------------
# CONSTANTS
# ---------------------------------------------------------------------------

PERSONAL_DOMAINS = {
    'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 'icloud.com',
    'aol.com', 'protonmail.com', 'mail.com', 'live.com', 'msn.com',
    'ymail.com', 'zoho.com', 'gmx.com', 'gmx.de', 'web.de',
    'me.com', 'mac.com', 'pm.me',
}

# Educational/government domains (not personal, but not company either)
NON_CORPORATE_DOMAINS = {
    'edu', 'gov', 'mil', 'ac.uk', 'edu.au',
}

# Company domain -> company name mapping (for backfilling company from email)
DOMAIN_TO_COMPANY = {
    'mlp.com': 'Millennium',
    'bamfunds.com': 'Balyasny Asset Management L.P.',
    'bamelevate.com': 'Balyasny Asset Management L.P.',
    'morganstanley.com': 'Balyasny Asset Management L.P.',  # known secondee
    'twosigma.com': 'Two Sigma',
    'sightwaycapital.com': 'Two Sigma',
    'point72.com': 'Point72',
    'cubistsystematic.com': 'Point72',
    'howardhanna.com': 'Point72',
    'sig.com': 'Susquehanna International Group',
    'mwam.com': 'Marshall Wace',
    'schonfeld.com': 'Schonfeld',
    'cigna.com': 'Schonfeld',  # known secondee
    'exoduspoint.com': 'ExodusPoint Capital Management, LP',
    'brevanhoward.com': 'Brevan Howard',
    'centivacapital.com': 'Centiva Capital',
    'dymonasia.com': 'Dymon Asia Capital',
    'jainglobal.com': 'Jain Global',
    'tudor.com': 'THE TUDOR GROUP',
    'deshaw.com': 'The D. E. Shaw Group',
    'winton.com': 'Winton',
    'capulaglobal.com': 'Capula Investment Management LLP',
    'tiff.org': 'TIFF Investment Management',
    'symmetryinvestments.com': 'Symmetry Investments',
    'magnetar.com': 'Magnetar',
    'fasanara.com': 'Fasanara Capital',
    'laurioncap.com': 'Laurion Capital Management LP',
    'opim.com.hk': 'OP Investment Management',
    'polaramp.com': 'Polar Asset Management Partners Inc.',
    'citadel.com': 'Citadel',
    'elliottmgmt.com': 'Elliott Investment Management L.P.',
    'elliottadvisors.co.uk': 'Elliott Investment Management L.P.',
    'qinvestments.com': 'Q Investments',
    'gic.com.sg': 'GIC',
    'bluecrestcapital.com': 'BlueCrest Capital Management',
    'utimco.org': 'UTIMCO',
    'dpe.de': 'Deutsche Private Equity (DPE)',
    'mercia.co.uk': 'Mercia Asset Management PLC',
    'evgroup.uk.com': 'Mercia Asset Management PLC',
    'wellington.com': 'Wellington Management',
    'cfprivateequity.com': 'CF Private Equity',
    'hedgefundassoc.org': 'Hedge Fund Association',
    'boyucapital.com': 'Boyu Capital',
    'boyucap.com': 'Boyu Capital',
    'osam.com': "O'Shaughnessy Asset Management",
    'icmgroup.ca': 'ICM Asset Management',
    'alphasysglobal.com': 'AlphaSys Global',
    'commonfund.org': 'Commonfund',
    'rwb-ag.de': 'Munich Private Equity',
    'rwb-partners.de': 'Munich Private Equity',
    'munich-pe.com': 'Munich Private Equity',
    'aetos.com': 'Aetos Alternatives Management',
    'pinpointfund.com': 'Pinpoint Asset Management',
    'ubs.com': 'UBS',
    'sbw-invest.com': 'Schaper, Benz & Wise Investment Counsel, Inc.',
    'alliancebernstein.com': 'AllianceBernstein',
    'troweprice.com': 'T. Rowe Price',
    'fmr.com': 'Fidelity Investments',
    'blackrock.com': 'BlackRock',
    'statestreet.com': 'State Street Associates',
    'vanguard.co.uk': 'Vanguard',
    'prudential.com': 'Prudential Financial',
    'thecapitalgroup.com': 'Capital Group',
    'hartfordfunds.com': 'Hartford Funds',
    'franklintempleton.com': 'Franklin Templeton',
    'lazard.com': 'Lazard Asset Management',
    'coatue.com': 'Coatue Management',
    'fortress.com': 'Fortress Investment Group',
    'moorecap.com': 'Moore Capital Management',
    'persq.com': 'Pershing Square Capital Management, L.P.',
    'veritionfund.com': 'Verition Fund Management LLC',
    'arcmont.com': 'Arcmont Asset Management',
    'harbourvest.com': 'HarbourVest Partners',
    'generationim.com': 'Generation Investment Management',
    'bnpparibas.com': 'BNP Paribas Asset Management',
    'ca-cib.com': 'Credit Agricole CIB',
    'adyne.com': 'Alphadyne Asset Management',
    'stoneridgeam.com': 'Stone Ridge Asset Management',
    'tetragoninv.com': 'Tetragon',
    'oasiscm.com': 'Oasis Management Company Ltd.',
    'us.mufg.jp': 'MUFG',
    'natixis.com': 'Natixis Wealth Management',
    'oddo-bhf.com': 'ODDO BHF',
    'lbbw-am.de': 'LBBW Asset Management Investmentgesellschaft mbH',
    'ostrum.com': 'Ostrum Asset Management',
    'impaxam.com': 'Impax Asset Management',
    'dreyfusbank.ch': 'Dreyfus Sons & Co Ltd, Banquiers',
}

# Industry mapping: company name patterns -> industry
# Order matters: more specific patterns first
INDUSTRY_RULES = [
    # Specific hedge funds
    (['Millennium', 'Balyasny', 'Point72', 'Two Sigma', 'Citadel',
      'Marshall Wace', 'ExodusPoint', 'Schonfeld', 'Brevan Howard',
      'Centiva Capital', 'Dymon Asia', 'Jain Global', 'Winton',
      'Capula', 'Magnetar', 'Fasanara', 'Laurion', 'BlueCrest',
      'Susquehanna', 'Tudor', 'D. E. Shaw', 'Pershing Square',
      'Verition', 'Moore Capital', 'Alphadyne', 'Stone Ridge',
      'Oasis Management', 'Elliott Investment', 'Polar Asset',
      'Symmetry Investments', 'Pinpoint Asset', 'SkyBridge',
      'private hedge fund', 'Hedge Fund Association',
      'AlphaSys', 'Polymer Capital', 'Quantedge', 'WizardQuant',
      'Q Investments'], 'Hedge Fund'),

    # Asset Management
    (['T. Rowe Price', 'Vanguard', 'Fidelity', 'BlackRock', 'Franklin Templeton',
      'Capital Group', 'Hartford Funds', 'Wellington', 'TIFF Investment',
      'Commonfund', 'Impax Asset', 'UTIMCO', 'OP Investment',
      'North Star Asset', "O'Shaughnessy", 'ICM Asset', 'Zacks Investment',
      'Mercia Asset', 'Aetos', 'Lazard Asset', 'BNP Paribas Asset',
      'LBBW Asset', 'Ostrum Asset', 'Natixis', 'Generation Investment',
      'ODDO BHF', 'State Street', 'Azur IM', 'Arcmont Asset',
      'Clearstead', 'Legacy Advisors', 'Baird Augustine',
      'Massachusetts Pension', 'Tennessee Consolidated',
      'Trans-Canada Capital', 'Coatue Management', 'Clocktower',
      'HarbourVest'], 'Asset Management'),

    # Private Equity
    (['Munich Private Equity', 'CF Private Equity', 'Deutsche Private Equity',
      'Carlyle', 'Fortress Investment', 'Gemspring', 'Boyu Capital',
      'Alpha Wave', 'Altrafin', 'Lindenstone', 'Mutares',
      'HFS', 'Caprock', 'Tetragon', 'Multiples Alternate',
      'Venture Capital'], 'Private Equity'),

    # Investment Banking
    (['Goldman Sachs', 'JPMorgan', 'Morgan Stanley', 'UBS', 'Credit Suisse',
      'MUFG', 'Credit Agricole', 'Dreyfus', 'Pragma'], 'Investment Banking'),

    # Pension / Sovereign Wealth
    (['GIC', 'Pension', 'Retirement'], 'Pension / Sovereign Wealth'),

    # Technology
    (['Databricks', 'Synquery'], 'Technology'),

    # Other Finance (generic)
    (['Schaper, Benz', 'JonesTrading', 'Equi', 'KEMOS',
      'Private Family Office', 'AllianceBernstein'], 'Financial Services'),
]

# Company size mapping: company name -> employee range
COMPANY_SIZE_MAP = {
    # Mega (5000+)
    'BlackRock': '5001-10000',
    'Fidelity Investments': '5001-10000',
    'Vanguard': '5001-10000',
    'Franklin Templeton': '5001-10000',
    'T. Rowe Price': '5001-10000',
    'UBS': '5001-10000',
    'MUFG': '5001-10000',
    'BNP Paribas Asset Management': '5001-10000',
    'Prudential Financial': '5001-10000',
    'State Street Associates': '5001-10000',
    'GIC': '5001-10000',
    'Databricks': '5001-10000',
    'Credit Agricole CIB': '5001-10000',

    # Large (1001-5000)
    'Millennium': '1001-5000',
    'Two Sigma': '1001-5000',
    'Citadel': '1001-5000',
    'Point72': '1001-5000',
    'Balyasny Asset Management L.P.': '1001-5000',
    'Susquehanna International Group': '1001-5000',
    'The D. E. Shaw Group': '1001-5000',
    'Wellington Management': '1001-5000',
    'Capital Group': '1001-5000',
    'Brevan Howard': '1001-5000',
    'Lazard Asset Management': '1001-5000',
    'Hartford Funds': '1001-5000',
    'HarbourVest Partners': '1001-5000',
    'The Carlyle Group': '1001-5000',
    'Fortress Investment Group': '1001-5000',
    'Coatue Management': '1001-5000',
    'Elliott Investment Management L.P.': '1001-5000',
    'ODDO BHF': '1001-5000',
    'Natixis Wealth Management': '1001-5000',

    # Medium-Large (501-1000)
    'Marshall Wace': '501-1000',
    'Schonfeld': '501-1000',
    'Winton': '501-1000',
    'Moore Capital Management': '501-1000',
    'Pershing Square Capital Management, L.P.': '501-1000',
    'THE TUDOR GROUP': '501-1000',
    'Magnetar': '501-1000',
    'Capula Investment Management LLP': '501-1000',
    'Generation Investment Management': '501-1000',
    'Impax Asset Management': '501-1000',
    'AllianceBernstein': '501-1000',

    # Medium (201-500)
    'ExodusPoint Capital Management, LP': '201-500',
    'Centiva Capital': '201-500',
    'Jain Global': '201-500',
    'Dymon Asia Capital': '201-500',
    'BlueCrest Capital Management': '201-500',
    'Laurion Capital Management LP': '201-500',
    'Stone Ridge Asset Management': '201-500',
    'Verition Fund Management LLC': '201-500',
    'Alphadyne Asset Management': '201-500',
    'Fasanara Capital': '201-500',
    'Pinpoint Asset Management': '201-500',
    'SkyBridge Capital': '201-500',
    'Commonfund': '201-500',
    'TIFF Investment Management': '201-500',
    'Boyu Capital': '201-500',
    'North Star Asset Management': '201-500',
    'Mercia Asset Management PLC': '201-500',
    'Dreyfus Sons & Co Ltd, Banquiers': '201-500',
    'Mutares SE & Co. KGaA': '201-500',
    'LBBW Asset Management Investmentgesellschaft mbH': '201-500',
    'Ostrum Asset Management': '201-500',

    # Small-Medium (51-200)
    'Symmetry Investments': '51-200',
    'Polar Asset Management Partners Inc.': '51-200',
    'Q Investments': '51-200',
    'OP Investment Management': '51-200',
    "O'Shaughnessy Asset Management": '51-200',
    'ICM Asset Management': '51-200',
    'Aetos Alternatives Management': '51-200',
    'Oasis Management Company Ltd.': '51-200',
    'Quantedge': '51-200',
    'WizardQuant': '51-200',
    'Polymer Capital': '51-200',
    'AlphaSys Global': '51-200',
    'Clocktower Group': '51-200',
    'Gemspring Capital': '51-200',
    'Tetragon': '51-200',
    'Hedge Fund Association': '51-200',
    'Trans-Canada Capital': '51-200',
    'Alpha Wave Global': '51-200',
    'Arcmont Asset Management': '51-200',
    'UTIMCO': '51-200',
    'Tennessee Consolidated Retirement System': '51-200',
    'JonesTrading': '51-200',
    'Zacks Investment Management': '51-200',
    'Massachusetts Pension Reserves Investment Management': '51-200',
    'Multiples Alternate Asset Management': '51-200',
    'Pragma': '51-200',

    # Small (11-50) - default for small known funds
    'Arjuna Capital': '11-50',
    'Caprock': '11-50',
    'Legacy Advisors': '11-50',
    'Baird Augustine': '11-50',
    'Clearstead Avalon Trust': '11-50',
    'Lindenstone AG': '11-50',
    'Altrafin AG': '11-50',
    'Azur IM': '11-50',
    'HFS': '11-50',
    'Private Family Office': '11-50',
    'Equi': '11-50',
    'Schaper, Benz & Wise Investment Counsel, Inc.': '11-50',
    'Venture Capital': '11-50',
    'Venture Capital Properties': '11-50',
    'Venture Capital Trust Fund': '11-50',
    'KEMOS GROUP': '11-50',
    'Synquery': '11-50',
    'a private hedge fund': '11-50',
    'Intempo Health': '11-50',
}


def _is_personal_domain(domain: str) -> bool:
    """Check if domain is personal/non-corporate."""
    if domain in PERSONAL_DOMAINS:
        return True
    # Check TLD-based non-corporate
    for suffix in NON_CORPORATE_DOMAINS:
        if domain.endswith('.' + suffix):
            return True
    return False


def _infer_industry(company: str) -> str | None:
    """Infer industry from company name using pattern matching."""
    if not company:
        return None

    for patterns, industry in INDUSTRY_RULES:
        for pattern in patterns:
            if pattern.lower() in company.lower():
                return industry

    # Fallback heuristics based on company name keywords
    company_lower = company.lower()
    if any(kw in company_lower for kw in ['capital', 'partners', 'fund', 'investment']):
        return 'Investment Management'
    if any(kw in company_lower for kw in ['asset management', 'asset mgmt']):
        return 'Asset Management'
    if any(kw in company_lower for kw in ['private equity', 'pe ']):
        return 'Private Equity'
    if any(kw in company_lower for kw in ['venture capital', 'vc ', 'ventures']):
        return 'Venture Capital'
    if any(kw in company_lower for kw in ['bank', 'banking']):
        return 'Investment Banking'

    return None


def _infer_company_size(company: str) -> str | None:
    """Infer company_size from known companies."""
    if not company:
        return None

    # Exact match first
    if company in COMPANY_SIZE_MAP:
        return COMPANY_SIZE_MAP[company]

    # Partial match (for slight name variations)
    company_lower = company.lower()
    for known, size in COMPANY_SIZE_MAP.items():
        if known.lower() in company_lower or company_lower in known.lower():
            return size

    return None


def _generate_angle(title: str, company: str) -> str | None:
    """Generate personalized_angle from title and company."""
    if not title or title == 'None':
        if company:
            return (
                f"Your team at {company} likely tracks consumer sentiment "
                f"as an alternative data signal -- our platform covers 44,000+ "
                f"locations with real-time review analytics and anomaly detection."
            )
        return None

    if not company:
        return (
            f"As a {title}, you likely evaluate consumer sentiment "
            f"signals -- our platform provides real-time review analytics "
            f"across 44,000+ locations with ML-powered anomaly detection."
        )

    return (
        f"As a {title} at {company}, you likely track consumer sentiment "
        f"as an alternative data signal -- our platform covers 44,000+ "
        f"locations with real-time review analytics and anomaly detection."
    )


def enrich_leads() -> dict:
    """
    Main enrichment function. Returns stats dict.
    """
    conn = get_connection()
    cur = conn.cursor()

    now = datetime.now(timezone.utc)
    stats = {
        'total': 0,
        'company_domain_set': 0,
        'industry_set': 0,
        'company_size_set': 0,
        'company_name_set': 0,
        'company_backfilled': 0,
        'angle_generated': 0,
        'enriched_at_set': 0,
    }

    try:
        # Fetch all leads
        cur.execute("""
            SELECT id, email, name, company, title,
                   company_domain, industry, company_size,
                   company_name, personalized_angle, enriched_at
            FROM leads
            ORDER BY id
        """)
        leads = cur.fetchall()
        stats['total'] = len(leads)

        print(f"\n{'='*70}")
        print(f"LEAD ENRICHMENT - {now.strftime('%Y-%m-%d %H:%M UTC')}")
        print(f"{'='*70}")
        print(f"\nTotal leads: {len(leads)}\n")

        updates = []  # (id, fields_dict)

        for row in leads:
            (lid, email, name, company, title,
             company_domain, industry, company_size,
             company_name, personalized_angle, enriched_at) = row

            fields = {}

            # --- 1. Extract company_domain from email ---
            if (not company_domain or company_domain.strip() == '') and email:
                parts = email.split('@')
                if len(parts) == 2:
                    domain = parts[1].lower().strip()
                    if not _is_personal_domain(domain):
                        fields['company_domain'] = domain
                        stats['company_domain_set'] += 1

            # --- 2. Backfill company from email domain ---
            if (not company or company.strip() == '') and email:
                domain = email.split('@')[1].lower().strip() if '@' in email else ''
                if domain in DOMAIN_TO_COMPANY:
                    fields['company'] = DOMAIN_TO_COMPANY[domain]
                    stats['company_backfilled'] += 1
                    # Use backfilled company for further enrichment
                    company = fields['company']

            # --- 3. Populate company_name from company ---
            if (not company_name or company_name.strip() == '') and company:
                fields['company_name'] = company.strip()
                stats['company_name_set'] += 1

            # --- 4. Infer industry ---
            if not industry or industry.strip() == '':
                inferred = _infer_industry(company)
                if inferred:
                    fields['industry'] = inferred
                    stats['industry_set'] += 1

            # --- 5. Infer company_size ---
            if not company_size or company_size.strip() == '':
                inferred = _infer_company_size(company)
                if inferred:
                    fields['company_size'] = inferred
                    stats['company_size_set'] += 1

            # --- 6. Generate personalized_angle ---
            effective_title = title if title and title != 'None' else None
            if not personalized_angle or personalized_angle.strip() == '':
                angle = _generate_angle(effective_title, company)
                if angle:
                    fields['personalized_angle'] = angle
                    stats['angle_generated'] += 1

            # --- 7. Set enriched_at ---
            if fields:
                fields['enriched_at'] = now
                stats['enriched_at_set'] += 1

            if fields:
                updates.append((lid, fields))

        # Apply updates
        print(f"Applying {len(updates)} updates...\n")

        for lid, fields in updates:
            set_clauses = []
            values = []
            for col, val in fields.items():
                set_clauses.append(f"{col} = %s")
                values.append(val)
            values.append(lid)

            sql = f"UPDATE leads SET {', '.join(set_clauses)} WHERE id = %s"
            cur.execute(sql, values)

        conn.commit()

        # Print results
        print("Enrichment Results:")
        print("-" * 70)
        print(f"  {'Total leads':30s}: {stats['total']:6d}")
        print(f"  {'Leads updated':30s}: {len(updates):6d}")
        print(f"  {'company_domain set':30s}: {stats['company_domain_set']:6d}")
        print(f"  {'company backfilled (from email)':30s}: {stats['company_backfilled']:6d}")
        print(f"  {'company_name populated':30s}: {stats['company_name_set']:6d}")
        print(f"  {'industry inferred':30s}: {stats['industry_set']:6d}")
        print(f"  {'company_size inferred':30s}: {stats['company_size_set']:6d}")
        print(f"  {'personalized_angle generated':30s}: {stats['angle_generated']:6d}")
        print(f"  {'enriched_at set':30s}: {stats['enriched_at_set']:6d}")
        print("-" * 70)

        return stats

    except Exception as e:
        conn.rollback()
        print(f"ERROR: {e}")
        raise
    finally:
        cur.close()
        return_connection(conn)


def print_final_completeness():
    """Print final field completeness after enrichment."""
    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT
              COUNT(*) as total,
              COUNT(CASE WHEN email IS NOT NULL AND length(email) > 0 THEN 1 END),
              COUNT(CASE WHEN name IS NOT NULL AND length(name) > 0 THEN 1 END),
              COUNT(CASE WHEN company IS NOT NULL AND length(company) > 0 THEN 1 END),
              COUNT(CASE WHEN title IS NOT NULL AND length(title) > 0
                         AND title <> 'None' THEN 1 END),
              COUNT(CASE WHEN linkedin_url IS NOT NULL AND length(linkedin_url) > 0 THEN 1 END),
              COUNT(CASE WHEN segment IS NOT NULL AND length(segment) > 0 THEN 1 END),
              COUNT(CASE WHEN personalized_angle IS NOT NULL AND length(personalized_angle) > 0 THEN 1 END),
              COUNT(CASE WHEN lead_score IS NOT NULL THEN 1 END),
              COUNT(CASE WHEN industry IS NOT NULL AND length(industry) > 0 THEN 1 END),
              COUNT(CASE WHEN company_domain IS NOT NULL AND length(company_domain) > 0 THEN 1 END),
              COUNT(CASE WHEN company_size IS NOT NULL AND length(company_size) > 0 THEN 1 END),
              COUNT(CASE WHEN phone IS NOT NULL AND length(phone) > 0 THEN 1 END),
              COUNT(CASE WHEN enriched_at IS NOT NULL THEN 1 END),
              COUNT(CASE WHEN company_name IS NOT NULL AND length(company_name) > 0 THEN 1 END)
            FROM leads
        """)
        row = cur.fetchone()
        total = row[0]

        fields = [
            ('email', row[1]),
            ('name', row[2]),
            ('company', row[3]),
            ('title (non-None)', row[4]),
            ('linkedin_url', row[5]),
            ('segment', row[6]),
            ('personalized_angle', row[7]),
            ('lead_score', row[8]),
            ('industry', row[9]),
            ('company_domain', row[10]),
            ('company_size', row[11]),
            ('phone', row[12]),
            ('enriched_at', row[13]),
            ('company_name', row[14]),
        ]

        print(f"\n{'='*70}")
        print(f"FINAL FIELD COMPLETENESS (total: {total} leads)")
        print(f"{'='*70}\n")

        for fname, count in fields:
            pct = count / total * 100 if total > 0 else 0
            bar = '#' * int(pct // 2.5)
            print(f"  {fname:25s}: {count:6d}/{total:6d} ({pct:5.1f}%) |{bar}")

        # Show industry breakdown
        cur.execute("""
            SELECT industry, COUNT(*)
            FROM leads
            WHERE industry IS NOT NULL AND length(industry) > 0
            GROUP BY industry
            ORDER BY COUNT(*) DESC
        """)
        print(f"\n{'='*70}")
        print("INDUSTRY BREAKDOWN")
        print(f"{'='*70}\n")
        for row in cur.fetchall():
            print(f"  {row[0]:30s}: {row[1]:4d}")

        # Show company_size breakdown
        cur.execute("""
            SELECT company_size, COUNT(*)
            FROM leads
            WHERE company_size IS NOT NULL AND length(company_size) > 0
            GROUP BY company_size
            ORDER BY COUNT(*) DESC
        """)
        print(f"\n{'='*70}")
        print("COMPANY SIZE BREAKDOWN")
        print(f"{'='*70}\n")
        for row in cur.fetchall():
            print(f"  {row[0]:20s}: {row[1]:4d}")

    finally:
        cur.close()
        return_connection(conn)


if __name__ == '__main__':
    print("\nReviewSignal Lead Enrichment Tool\n")

    # Run enrichment
    stats = enrich_leads()

    # Show final completeness
    print_final_completeness()

    print(f"\nDone! {stats['enriched_at_set']} leads enriched.\n")
