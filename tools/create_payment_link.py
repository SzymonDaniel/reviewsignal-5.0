#!/usr/bin/env python3
"""
PAYMENT LINK GENERATOR - Create Stripe Checkout links for customers
ReviewSignal 5.0

Usage:
    python create_payment_link.py --email "client@hedge.fund" --name "John Smith" --company "Hedge Fund LLC" --tier pro

    # Quick link for existing customer
    python create_payment_link.py --customer-id "cus_xxx" --tier enterprise
"""

import os
import sys
import argparse
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

import stripe
from modules.payment_processor import StripePaymentProcessor, SubscriptionTier

# Configuration
STRIPE_API_KEY = os.getenv('STRIPE_API_KEY')
STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET', '')

# URLs for checkout
SUCCESS_URL = os.getenv('CHECKOUT_SUCCESS_URL', 'https://reviewsignal.ai/welcome?session_id={CHECKOUT_SESSION_ID}')
CANCEL_URL = os.getenv('CHECKOUT_CANCEL_URL', 'https://reviewsignal.ai/pricing')


def create_payment_link(
    email: str = None,
    name: str = None,
    company: str = None,
    customer_id: str = None,
    tier: str = 'pro'
) -> dict:
    """
    Create a Stripe Checkout payment link for a customer.

    Args:
        email: Customer email (required if no customer_id)
        name: Customer name
        company: Company name
        customer_id: Existing Stripe customer ID
        tier: Subscription tier (trial, starter, pro, enterprise)

    Returns:
        dict with checkout_url, customer_id, tier, amount
    """
    if not STRIPE_API_KEY:
        return {"error": "STRIPE_API_KEY not configured in .env"}

    # Initialize processor
    processor = StripePaymentProcessor(
        api_key=STRIPE_API_KEY,
        webhook_secret=STRIPE_WEBHOOK_SECRET
    )

    # Get tier enum
    tier_map = {
        'trial': SubscriptionTier.TRIAL,
        'starter': SubscriptionTier.STARTER,
        'pro': SubscriptionTier.PRO,
        'enterprise': SubscriptionTier.ENTERPRISE
    }

    subscription_tier = tier_map.get(tier.lower())
    if not subscription_tier:
        return {"error": f"Invalid tier: {tier}. Valid options: trial, starter, pro, enterprise"}

    # Get pricing info
    pricing = processor.PRICING_TIERS.get(subscription_tier)

    # Create or get customer
    if customer_id:
        # Verify customer exists
        customer = processor.get_customer(customer_id)
        if not customer:
            return {"error": f"Customer not found: {customer_id}"}
    else:
        if not email:
            return {"error": "Email required to create new customer"}

        # Create new customer
        customer = processor.create_customer(
            email=email,
            name=name or "",
            company=company or "",
            metadata={"source": "payment_link_tool", "created": datetime.utcnow().isoformat()}
        )
        customer_id = customer.customer_id

    # Create checkout session
    checkout_url = processor.create_checkout_session(
        customer_id=customer_id,
        tier=subscription_tier,
        success_url=SUCCESS_URL,
        cancel_url=CANCEL_URL
    )

    if not checkout_url:
        return {"error": "Failed to create checkout session"}

    return {
        "success": True,
        "checkout_url": checkout_url,
        "customer_id": customer_id,
        "customer_email": email or (customer.email if hasattr(customer, 'email') else None),
        "tier": tier,
        "tier_name": pricing.name,
        "amount_eur": pricing.amount_eur,
        "interval": pricing.interval,
        "features": pricing.features
    }


def main():
    parser = argparse.ArgumentParser(
        description='Generate Stripe Checkout payment link for ReviewSignal customers',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create link for new customer
  %(prog)s --email "pm@hedgefund.com" --name "John Smith" --company "Alpha Capital" --tier pro

  # Create link for existing Stripe customer
  %(prog)s --customer-id "cus_abc123" --tier enterprise

  # List available tiers
  %(prog)s --list-tiers

Pricing Tiers:
  trial      - €0 (14-day trial, 100 API calls)
  starter    - €2,500/month (1,000 API calls, 5 cities)
  pro        - €5,000/month (10,000 API calls, 30 cities)
  enterprise - €10,000/month (unlimited)
        """
    )

    parser.add_argument('--email', '-e', help='Customer email')
    parser.add_argument('--name', '-n', help='Customer name')
    parser.add_argument('--company', '-c', help='Company name')
    parser.add_argument('--customer-id', help='Existing Stripe customer ID')
    parser.add_argument('--tier', '-t', default='pro',
                       choices=['trial', 'starter', 'pro', 'enterprise'],
                       help='Subscription tier (default: pro)')
    parser.add_argument('--list-tiers', action='store_true', help='List available pricing tiers')
    parser.add_argument('--json', action='store_true', help='Output as JSON')

    args = parser.parse_args()

    # List tiers
    if args.list_tiers:
        processor = StripePaymentProcessor(api_key=STRIPE_API_KEY or 'sk_test_dummy', webhook_secret='')
        print("\n" + "="*60)
        print("REVIEWSIGNAL PRICING TIERS")
        print("="*60)
        for tier, pricing in processor.PRICING_TIERS.items():
            print(f"\n{tier.value.upper()}:")
            print(f"  Price: €{pricing.amount_eur:,.0f}/{pricing.interval}")
            print(f"  API Calls: {pricing.api_calls_limit if pricing.api_calls_limit > 0 else 'Unlimited'}")
            print(f"  Reports: {pricing.reports_limit if pricing.reports_limit > 0 else 'Unlimited'}")
            print(f"  Cities: {pricing.cities_limit if pricing.cities_limit > 0 else 'All 111'}")
            print(f"  Features:")
            for feature in pricing.features[:3]:
                print(f"    • {feature}")
        print("\n" + "="*60)
        return

    # Validate inputs
    if not args.customer_id and not args.email:
        parser.error("Either --email or --customer-id is required")

    # Create payment link
    result = create_payment_link(
        email=args.email,
        name=args.name,
        company=args.company,
        customer_id=args.customer_id,
        tier=args.tier
    )

    # Output
    if args.json:
        import json
        print(json.dumps(result, indent=2))
    else:
        if result.get('error'):
            print(f"\n❌ ERROR: {result['error']}")
            sys.exit(1)

        print("\n" + "="*60)
        print("✅ PAYMENT LINK CREATED")
        print("="*60)
        print(f"\n📧 Customer: {result.get('customer_email', 'N/A')}")
        print(f"🆔 Customer ID: {result['customer_id']}")
        print(f"📊 Tier: {result['tier_name']} (€{result['amount_eur']:,.0f}/{result['interval']})")
        print(f"\n🔗 PAYMENT LINK:")
        print(f"   {result['checkout_url']}")
        print(f"\n📋 Features included:")
        for feature in result['features'][:5]:
            print(f"   • {feature}")
        print("\n" + "="*60)
        print("Send this link to the customer to complete payment.")
        print("="*60 + "\n")


if __name__ == "__main__":
    main()
