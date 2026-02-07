#!/usr/bin/env python3
"""
Add all email accounts to all Instantly campaigns.
Run: python3 scripts/add_accounts_to_campaigns.py
"""

import requests
import os
from dotenv import load_dotenv

# Load environment
load_dotenv('/home/info_betsim/reviewsignal-5.0/.env')

API_KEY = os.getenv('INSTANTLY_API_KEY')
BASE_URL = "https://api.instantly.ai/api/v2"

# Headers for API requests
headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

# 8 email accounts to add
EMAIL_ACCOUNTS = [
    "simon@reviewsignal.cc",
    "simon@reviewsignal.net",
    "simon@reviewsignal.org",
    "simon@reviewsignal.review",
    "simon@reviewsignal.work",
    "simon@reviewsignal.xyz",
    "team@reviewsignal.ai",
    "betsim@betsim.io"
]

# 5 campaigns (from .env)
CAMPAIGNS = {
    "PM (Portfolio Manager)": os.getenv('INSTANTLY_CAMPAIGN_PM'),
    "Quant Analyst": os.getenv('INSTANTLY_CAMPAIGN_QUANT'),
    "Alt Data Head": os.getenv('INSTANTLY_CAMPAIGN_ALTDATA'),
    "CIO": os.getenv('INSTANTLY_CAMPAIGN_CIO'),
    "High Intent": os.getenv('INSTANTLY_CAMPAIGN_INTENT')
}


def get_all_accounts():
    """Get all email accounts from Instantly."""
    print("\n[1/3] Pobieranie listy kont email z Instantly...")

    url = f"{BASE_URL}/accounts"
    response = requests.get(url, headers=headers, params={"limit": 100})

    if response.status_code == 200:
        data = response.json()
        accounts = data.get('items', data) if isinstance(data, dict) else data
        print(f"    Znaleziono {len(accounts)} kont w Instantly")
        return accounts
    else:
        print(f"    ERROR: {response.status_code} - {response.text}")
        return []


def get_campaign_details(campaign_id, campaign_name):
    """Get campaign details including linked accounts."""
    url = f"{BASE_URL}/campaigns/{campaign_id}"
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        return response.json()
    else:
        print(f"    Nie mozna pobrac kampanii {campaign_name}: {response.status_code}")
        return None


def add_accounts_to_campaign(campaign_id, campaign_name, account_emails):
    """Add email accounts to a campaign using PATCH."""
    print(f"\n    Dodawanie {len(account_emails)} kont do kampanii '{campaign_name}'...")

    # Try method 1: PATCH campaign with email_list
    url = f"{BASE_URL}/campaigns/{campaign_id}"

    payload = {
        "email_list": account_emails
    }

    response = requests.patch(url, headers=headers, json=payload)

    if response.status_code in [200, 201]:
        print(f"    ✅ Sukces! Dodano konta do '{campaign_name}'")
        return True
    elif response.status_code == 409:
        print(f"    ⚠️  Konta juz istnieja w '{campaign_name}'")
        return True
    else:
        print(f"    ❌ PATCH Blad: {response.status_code}")

        # Try method 2: PUT with full campaign update
        # First GET the campaign, then PUT with updated email_list
        get_response = requests.get(url, headers=headers)
        if get_response.status_code == 200:
            campaign_data = get_response.json()
            # Update email_list
            campaign_data['email_list'] = account_emails

            put_response = requests.put(url, headers=headers, json=campaign_data)
            if put_response.status_code in [200, 201]:
                print(f"    ✅ Sukces (PUT)! Dodano konta do '{campaign_name}'")
                return True
            else:
                print(f"    ❌ PUT Blad: {put_response.status_code} - {put_response.text[:200]}")

        # Try method 3: API V1 style (different endpoint)
        v1_url = f"https://api.instantly.ai/api/v1/campaign/set/accounts"
        v1_params = {
            "api_key": API_KEY.split(":")[0] if ":" in API_KEY else API_KEY,
            "campaign_id": campaign_id
        }
        v1_payload = {"emails": account_emails}

        v1_response = requests.post(v1_url, params=v1_params, json=v1_payload)
        if v1_response.status_code in [200, 201]:
            print(f"    ✅ Sukces (V1)! Dodano konta do '{campaign_name}'")
            return True
        else:
            print(f"    ❌ V1 Blad: {v1_response.status_code} - {v1_response.text[:200]}")

        return False


def main():
    print("=" * 60)
    print("INSTANTLY: Dodawanie kont email do kampanii")
    print("=" * 60)

    # Step 1: Get existing accounts
    accounts = get_all_accounts()

    if accounts:
        print("\n    Konta w Instantly:")
        for acc in accounts:
            email = acc.get('email', 'N/A')
            status = acc.get('status', 'unknown')
            warmup = acc.get('warmup_status', 'unknown')
            print(f"      - {email} (status: {status}, warmup: {warmup})")

    # Step 2: Match our accounts with Instantly accounts
    print("\n[2/3] Sprawdzanie naszych kont...")
    our_accounts_in_instantly = []

    for email in EMAIL_ACCOUNTS:
        found = any(acc.get('email') == email for acc in accounts)
        if found:
            print(f"    ✅ {email} - znalezione")
            our_accounts_in_instantly.append(email)
        else:
            print(f"    ❌ {email} - NIE ZNALEZIONE w Instantly!")

    if not our_accounts_in_instantly:
        print("\n❌ Zadne z naszych kont nie jest w Instantly. Dodaj je najpierw!")
        return

    # Step 3: Add accounts to each campaign
    print("\n[3/3] Dodawanie kont do kampanii...")

    results = []
    for campaign_name, campaign_id in CAMPAIGNS.items():
        if not campaign_id:
            print(f"\n    ⚠️  Brak ID dla kampanii '{campaign_name}'")
            continue

        success = add_accounts_to_campaign(
            campaign_id,
            campaign_name,
            our_accounts_in_instantly
        )
        results.append((campaign_name, success))

    # Summary
    print("\n" + "=" * 60)
    print("PODSUMOWANIE")
    print("=" * 60)
    print(f"\nKonta dodane: {len(our_accounts_in_instantly)}/{len(EMAIL_ACCOUNTS)}")
    print(f"Kampanie: {len([r for r in results if r[1]])}/{len(CAMPAIGNS)}")

    print("\nSzczegoly kampanii:")
    for name, success in results:
        status = "✅" if success else "❌"
        print(f"  {status} {name}")

    print("\n" + "=" * 60)
    print("GOTOWE! Sprawdz Instantly dashboard: https://app.instantly.ai")
    print("=" * 60)


if __name__ == "__main__":
    main()
