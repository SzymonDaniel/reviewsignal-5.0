#!/usr/bin/env python3
"""
STRIPE PAYMENT PROCESSOR - Subscription & Payment Management
System 5.0.4 - Handles all payment operations for ReviewSignal

Author: ReviewSignal Team
Version: 5.0.4
Date: January 2026
"""

import stripe
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict, field
from enum import Enum
from datetime import datetime
import structlog
import json
import hmac
import hashlib

logger = structlog.get_logger()


# ═══════════════════════════════════════════════════════════════════
# ENUMS
# ═══════════════════════════════════════════════════════════════════

class SubscriptionTier(Enum):
    """Subscription tier levels"""
    TRIAL = "trial"
    STARTER = "starter"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class PaymentStatus(Enum):
    """Payment status"""
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class WebhookEvent(Enum):
    """Stripe webhook event types we handle"""
    PAYMENT_SUCCESS = "payment_intent.succeeded"
    PAYMENT_FAILED = "payment_intent.payment_failed"
    SUBSCRIPTION_CREATED = "customer.subscription.created"
    SUBSCRIPTION_UPDATED = "customer.subscription.updated"
    SUBSCRIPTION_CANCELLED = "customer.subscription.deleted"
    INVOICE_PAID = "invoice.paid"
    INVOICE_FAILED = "invoice.payment_failed"
    REFUND_CREATED = "charge.refunded"


# ═══════════════════════════════════════════════════════════════════
# DATACLASSES
# ═══════════════════════════════════════════════════════════════════

@dataclass
class PricingTier:
    """Pricing tier configuration"""
    name: str
    price_id: str
    amount_cents: int
    currency: str
    interval: str
    features: List[str]
    api_calls_limit: int
    reports_limit: int
    cities_limit: int = -1
    
    @property
    def amount_eur(self) -> float:
        return self.amount_cents / 100
    
    def to_dict(self) -> Dict:
        data = asdict(self)
        data['amount_eur'] = self.amount_eur
        return data


@dataclass
class CustomerData:
    """Customer information"""
    customer_id: str
    email: str
    name: str
    company: str
    created_at: str
    metadata: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class SubscriptionData:
    """Subscription information"""
    subscription_id: str
    customer_id: str
    tier: SubscriptionTier
    status: str
    amount_eur: float
    current_period_start: str
    current_period_end: str
    cancel_at_period_end: bool
    
    def to_dict(self) -> Dict:
        data = asdict(self)
        data['tier'] = self.tier.value
        return data


@dataclass
class PaymentData:
    """Payment information"""
    payment_id: str
    customer_id: str
    amount: float
    currency: str
    status: PaymentStatus
    created_at: str
    description: str = ""
    invoice_id: str = ""
    
    def to_dict(self) -> Dict:
        data = asdict(self)
        data['status'] = self.status.value
        return data


# ═══════════════════════════════════════════════════════════════════
# MAIN CLASS
# ═══════════════════════════════════════════════════════════════════

class StripePaymentProcessor:
    """
    Stripe Payment Processor for ReviewSignal.
    Handles subscriptions, payments, webhooks, and invoices.
    """
    
    # Pricing tiers configuration (EUR)
    PRICING_TIERS = {
        SubscriptionTier.TRIAL: PricingTier(
            name="Trial",
            price_id="price_trial_free",
            amount_cents=0,
            currency="eur",
            interval="once",
            features=[
                "100 API calls",
                "5 reports",
                "1 city coverage",
                "14 days access",
                "Email support"
            ],
            api_calls_limit=100,
            reports_limit=5,
            cities_limit=1
        ),
        SubscriptionTier.STARTER: PricingTier(
            name="Starter",
            price_id="price_1Sw5V3GMD6tutrJ2ltkgycJ6",
            amount_cents=250000,  # €2,500
            currency="eur",
            interval="month",
            features=[
                "1,000 API calls/month",
                "50 reports/month",
                "5 cities coverage",
                "Email support",
                "Weekly data updates"
            ],
            api_calls_limit=1000,
            reports_limit=50,
            cities_limit=5
        ),
        SubscriptionTier.PRO: PricingTier(
            name="Pro",
            price_id="price_1Sw5WFGMD6tutrJ2UpJzwGLb",
            amount_cents=500000,  # €5,000
            currency="eur",
            interval="month",
            features=[
                "10,000 API calls/month",
                "500 reports/month",
                "30 cities coverage",
                "Priority support",
                "Daily data updates",
                "Custom alerts",
                "API access"
            ],
            api_calls_limit=10000,
            reports_limit=500,
            cities_limit=30
        ),
        SubscriptionTier.ENTERPRISE: PricingTier(
            name="Enterprise",
            price_id="price_1Sw5WqGMD6tutrJ2VMdKw9UZ",
            amount_cents=1000000,  # €10,000
            currency="eur",
            interval="month",
            features=[
                "Unlimited API calls",
                "Unlimited reports",
                "All 111 cities",
                "Dedicated support",
                "Real-time data",
                "Custom integrations",
                "White-label reports",
                "SLA guarantee"
            ],
            api_calls_limit=-1,  # Unlimited
            reports_limit=-1,
            cities_limit=-1
        )
    }
    
    def __init__(self, api_key: str, webhook_secret: str):
        """
        Initialize Stripe Payment Processor.
        
        Args:
            api_key: Stripe API key (sk_live_xxx or sk_test_xxx)
            webhook_secret: Stripe webhook signing secret (whsec_xxx)
        """
        stripe.api_key = api_key
        self.webhook_secret = webhook_secret
        
        logger.info(
            "payment_processor_initialized",
            mode="live" if "live" in api_key else "test"
        )
    
    # ───────────────────────────────────────────────────────────────
    # CUSTOMER MANAGEMENT
    # ───────────────────────────────────────────────────────────────
    
    def create_customer(
        self,
        email: str,
        name: str,
        company: str,
        metadata: Dict = None
    ) -> CustomerData:
        """
        Create a new Stripe customer.
        
        Args:
            email: Customer email
            name: Customer name
            company: Company name
            metadata: Additional metadata
        
        Returns:
            CustomerData object
        """
        try:
            customer = stripe.Customer.create(
                email=email,
                name=name,
                metadata={
                    "company": company,
                    "source": "reviewsignal",
                    **(metadata or {})
                }
            )
            
            logger.info(
                "customer_created",
                customer_id=customer.id,
                email=email
            )
            
            return CustomerData(
                customer_id=customer.id,
                email=email,
                name=name,
                company=company,
                created_at=datetime.utcnow().isoformat(),
                metadata=metadata or {}
            )
            
        except stripe.error.StripeError as e:
            logger.error("customer_create_error", error=str(e))
            raise
    
    def get_customer(self, customer_id: str) -> Optional[CustomerData]:
        """
        Get customer by ID.
        
        Args:
            customer_id: Stripe customer ID
        
        Returns:
            CustomerData or None
        """
        try:
            customer = stripe.Customer.retrieve(customer_id)
            
            return CustomerData(
                customer_id=customer.id,
                email=customer.email,
                name=customer.name or "",
                company=customer.metadata.get("company", ""),
                created_at=datetime.fromtimestamp(customer.created).isoformat(),
                metadata=dict(customer.metadata)
            )
            
        except stripe.error.StripeError as e:
            logger.error("customer_get_error", customer_id=customer_id, error=str(e))
            return None
    
    def update_customer(
        self,
        customer_id: str,
        **kwargs
    ) -> Optional[CustomerData]:
        """
        Update customer information.
        
        Args:
            customer_id: Stripe customer ID
            **kwargs: Fields to update (email, name, metadata)
        
        Returns:
            Updated CustomerData or None
        """
        try:
            customer = stripe.Customer.modify(customer_id, **kwargs)
            
            logger.info("customer_updated", customer_id=customer_id)
            
            return CustomerData(
                customer_id=customer.id,
                email=customer.email,
                name=customer.name or "",
                company=customer.metadata.get("company", ""),
                created_at=datetime.fromtimestamp(customer.created).isoformat(),
                metadata=dict(customer.metadata)
            )
            
        except stripe.error.StripeError as e:
            logger.error("customer_update_error", customer_id=customer_id, error=str(e))
            return None
    
    # ───────────────────────────────────────────────────────────────
    # SUBSCRIPTION MANAGEMENT
    # ───────────────────────────────────────────────────────────────
    
    def create_subscription(
        self,
        customer_id: str,
        tier: SubscriptionTier,
        trial_days: int = 0
    ) -> Optional[SubscriptionData]:
        """
        Create a new subscription.
        
        Args:
            customer_id: Stripe customer ID
            tier: Subscription tier
            trial_days: Trial period in days (default: 0)
        
        Returns:
            SubscriptionData or None
        """
        pricing = self.PRICING_TIERS.get(tier)
        if not pricing:
            logger.error("invalid_tier", tier=tier.value)
            return None
        
        try:
            subscription_params = {
                "customer": customer_id,
                "items": [{"price": pricing.price_id}],
                "metadata": {
                    "tier": tier.value,
                    "source": "reviewsignal"
                }
            }
            
            if trial_days > 0:
                subscription_params["trial_period_days"] = trial_days
            
            subscription = stripe.Subscription.create(**subscription_params)
            
            logger.info(
                "subscription_created",
                subscription_id=subscription.id,
                customer_id=customer_id,
                tier=tier.value
            )
            
            return SubscriptionData(
                subscription_id=subscription.id,
                customer_id=customer_id,
                tier=tier,
                status=subscription.status,
                amount_eur=pricing.amount_eur,
                current_period_start=datetime.fromtimestamp(
                    subscription.current_period_start
                ).isoformat(),
                current_period_end=datetime.fromtimestamp(
                    subscription.current_period_end
                ).isoformat(),
                cancel_at_period_end=subscription.cancel_at_period_end
            )
            
        except stripe.error.StripeError as e:
            logger.error(
                "subscription_create_error",
                customer_id=customer_id,
                error=str(e)
            )
            return None
    
    def get_subscription(self, subscription_id: str) -> Optional[SubscriptionData]:
        """
        Get subscription by ID.
        
        Args:
            subscription_id: Stripe subscription ID
        
        Returns:
            SubscriptionData or None
        """
        try:
            subscription = stripe.Subscription.retrieve(subscription_id)
            tier_value = subscription.metadata.get("tier", "starter")
            tier = SubscriptionTier(tier_value)
            pricing = self.PRICING_TIERS.get(tier)
            
            return SubscriptionData(
                subscription_id=subscription.id,
                customer_id=subscription.customer,
                tier=tier,
                status=subscription.status,
                amount_eur=pricing.amount_eur if pricing else 0,
                current_period_start=datetime.fromtimestamp(
                    subscription.current_period_start
                ).isoformat(),
                current_period_end=datetime.fromtimestamp(
                    subscription.current_period_end
                ).isoformat(),
                cancel_at_period_end=subscription.cancel_at_period_end
            )
            
        except stripe.error.StripeError as e:
            logger.error("subscription_get_error", subscription_id=subscription_id, error=str(e))
            return None
    
    def cancel_subscription(
        self,
        subscription_id: str,
        immediate: bool = False
    ) -> Optional[SubscriptionData]:
        """
        Cancel a subscription.
        
        Args:
            subscription_id: Stripe subscription ID
            immediate: Cancel immediately (True) or at period end (False)
        
        Returns:
            Updated SubscriptionData or None
        """
        try:
            if immediate:
                subscription = stripe.Subscription.delete(subscription_id)
            else:
                subscription = stripe.Subscription.modify(
                    subscription_id,
                    cancel_at_period_end=True
                )
            
            logger.info(
                "subscription_cancelled",
                subscription_id=subscription_id,
                immediate=immediate
            )
            
            return self.get_subscription(subscription_id) if not immediate else None
            
        except stripe.error.StripeError as e:
            logger.error(
                "subscription_cancel_error",
                subscription_id=subscription_id,
                error=str(e)
            )
            return None
    
    def upgrade_subscription(
        self,
        subscription_id: str,
        new_tier: SubscriptionTier
    ) -> Optional[SubscriptionData]:
        """
        Upgrade/downgrade subscription to new tier.
        
        Args:
            subscription_id: Stripe subscription ID
            new_tier: New subscription tier
        
        Returns:
            Updated SubscriptionData or None
        """
        pricing = self.PRICING_TIERS.get(new_tier)
        if not pricing:
            logger.error("invalid_tier", tier=new_tier.value)
            return None
        
        try:
            subscription = stripe.Subscription.retrieve(subscription_id)
            
            # Update the subscription item
            stripe.Subscription.modify(
                subscription_id,
                items=[{
                    "id": subscription["items"]["data"][0].id,
                    "price": pricing.price_id
                }],
                metadata={"tier": new_tier.value},
                proration_behavior="create_prorations"
            )
            
            logger.info(
                "subscription_upgraded",
                subscription_id=subscription_id,
                new_tier=new_tier.value
            )
            
            return self.get_subscription(subscription_id)
            
        except stripe.error.StripeError as e:
            logger.error(
                "subscription_upgrade_error",
                subscription_id=subscription_id,
                error=str(e)
            )
            return None
    
    # ───────────────────────────────────────────────────────────────
    # PAYMENTS
    # ───────────────────────────────────────────────────────────────
    
    def create_payment_intent(
        self,
        customer_id: str,
        amount_cents: int,
        currency: str = "eur",
        description: str = ""
    ) -> Optional[Dict]:
        """
        Create a payment intent for one-time payment.
        
        Args:
            customer_id: Stripe customer ID
            amount_cents: Amount in cents
            currency: Currency code (default: eur)
            description: Payment description
        
        Returns:
            Payment intent dict with client_secret or None
        """
        try:
            intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency=currency,
                customer=customer_id,
                description=description,
                metadata={"source": "reviewsignal"}
            )
            
            logger.info(
                "payment_intent_created",
                intent_id=intent.id,
                amount=amount_cents
            )
            
            return {
                "intent_id": intent.id,
                "client_secret": intent.client_secret,
                "amount": amount_cents,
                "currency": currency,
                "status": intent.status
            }
            
        except stripe.error.StripeError as e:
            logger.error("payment_intent_error", error=str(e))
            return None
    
    def process_one_time_payment(
        self,
        customer_id: str,
        amount_cents: int,
        description: str,
        payment_method_id: str
    ) -> Optional[PaymentData]:
        """
        Process a one-time payment.
        
        Args:
            customer_id: Stripe customer ID
            amount_cents: Amount in cents
            description: Payment description
            payment_method_id: Payment method ID
        
        Returns:
            PaymentData or None
        """
        try:
            intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency="eur",
                customer=customer_id,
                payment_method=payment_method_id,
                description=description,
                confirm=True,
                metadata={"source": "reviewsignal"}
            )
            
            status = PaymentStatus.SUCCEEDED if intent.status == "succeeded" else PaymentStatus.PENDING
            
            logger.info(
                "payment_processed",
                intent_id=intent.id,
                status=status.value
            )
            
            return PaymentData(
                payment_id=intent.id,
                customer_id=customer_id,
                amount=amount_cents / 100,
                currency="eur",
                status=status,
                created_at=datetime.utcnow().isoformat(),
                description=description
            )
            
        except stripe.error.StripeError as e:
            logger.error("payment_process_error", error=str(e))
            return None
    
    def refund_payment(
        self,
        payment_id: str,
        amount_cents: int = None
    ) -> Optional[PaymentData]:
        """
        Refund a payment (full or partial).
        
        Args:
            payment_id: Payment intent ID
            amount_cents: Amount to refund (None for full refund)
        
        Returns:
            PaymentData with refund status or None
        """
        try:
            refund_params = {"payment_intent": payment_id}
            if amount_cents:
                refund_params["amount"] = amount_cents
            
            refund = stripe.Refund.create(**refund_params)
            
            logger.info(
                "payment_refunded",
                payment_id=payment_id,
                refund_id=refund.id,
                amount=refund.amount
            )
            
            return PaymentData(
                payment_id=payment_id,
                customer_id="",
                amount=refund.amount / 100,
                currency=refund.currency,
                status=PaymentStatus.REFUNDED,
                created_at=datetime.utcnow().isoformat(),
                description=f"Refund: {refund.id}"
            )
            
        except stripe.error.StripeError as e:
            logger.error("refund_error", payment_id=payment_id, error=str(e))
            return None
    
    # ───────────────────────────────────────────────────────────────
    # WEBHOOKS
    # ───────────────────────────────────────────────────────────────
    
    def handle_webhook(self, payload: bytes, signature: str) -> Dict:
        """
        Handle incoming Stripe webhook.
        
        Args:
            payload: Raw webhook payload bytes
            signature: Stripe signature header
        
        Returns:
            Dict with event type and processed data
        """
        # Verify signature
        if not self._verify_webhook_signature(payload, signature):
            logger.warning("webhook_invalid_signature")
            return {"error": "Invalid signature"}
        
        try:
            event = stripe.Webhook.construct_event(
                payload,
                signature,
                self.webhook_secret
            )
            
            return self._process_webhook_event(event)
            
        except ValueError as e:
            logger.error("webhook_parse_error", error=str(e))
            return {"error": "Invalid payload"}
        except stripe.error.SignatureVerificationError as e:
            logger.error("webhook_signature_error", error=str(e))
            return {"error": "Invalid signature"}
    
    def _verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """
        Verify webhook signature.
        """
        try:
            stripe.Webhook.construct_event(
                payload,
                signature,
                self.webhook_secret
            )
            return True
        except Exception:
            return False
    
    def _process_webhook_event(self, event) -> Dict:
        """
        Process a webhook event.
        """
        event_type = event["type"]
        data = event["data"]["object"]
        
        logger.info("webhook_received", event_type=event_type)
        
        result = {
            "event_type": event_type,
            "event_id": event["id"],
            "processed": True,
            "data": {}
        }
        
        # Handle different event types
        if event_type == WebhookEvent.PAYMENT_SUCCESS.value:
            result["data"] = {
                "payment_intent": data["id"],
                "amount": data["amount"],
                "customer": data.get("customer")
            }
            
        elif event_type == WebhookEvent.PAYMENT_FAILED.value:
            result["data"] = {
                "payment_intent": data["id"],
                "error": data.get("last_payment_error", {}).get("message")
            }
            
        elif event_type == WebhookEvent.SUBSCRIPTION_CREATED.value:
            result["data"] = {
                "subscription_id": data["id"],
                "customer": data["customer"],
                "status": data["status"]
            }
            
        elif event_type == WebhookEvent.SUBSCRIPTION_CANCELLED.value:
            result["data"] = {
                "subscription_id": data["id"],
                "customer": data["customer"],
                "cancelled_at": data.get("canceled_at")
            }
            
        elif event_type == WebhookEvent.INVOICE_PAID.value:
            result["data"] = {
                "invoice_id": data["id"],
                "customer": data["customer"],
                "amount_paid": data["amount_paid"],
                "subscription": data.get("subscription")
            }
            
        elif event_type == WebhookEvent.REFUND_CREATED.value:
            result["data"] = {
                "charge_id": data["id"],
                "amount_refunded": data["amount_refunded"]
            }
        
        return result
    
    # ───────────────────────────────────────────────────────────────
    # INVOICES
    # ───────────────────────────────────────────────────────────────
    
    def get_invoices(
        self,
        customer_id: str,
        limit: int = 10
    ) -> List[Dict]:
        """
        Get invoices for a customer.
        
        Args:
            customer_id: Stripe customer ID
            limit: Max invoices to return
        
        Returns:
            List of invoice dicts
        """
        try:
            invoices = stripe.Invoice.list(
                customer=customer_id,
                limit=limit
            )
            
            return [{
                "invoice_id": inv.id,
                "number": inv.number,
                "amount_due": inv.amount_due / 100,
                "amount_paid": inv.amount_paid / 100,
                "currency": inv.currency,
                "status": inv.status,
                "created": datetime.fromtimestamp(inv.created).isoformat(),
                "pdf_url": inv.invoice_pdf,
                "hosted_url": inv.hosted_invoice_url
            } for inv in invoices.data]
            
        except stripe.error.StripeError as e:
            logger.error("invoices_get_error", customer_id=customer_id, error=str(e))
            return []
    
    def download_invoice(self, invoice_id: str) -> Optional[str]:
        """
        Get invoice PDF URL.
        
        Args:
            invoice_id: Stripe invoice ID
        
        Returns:
            PDF URL or None
        """
        try:
            invoice = stripe.Invoice.retrieve(invoice_id)
            return invoice.invoice_pdf
            
        except stripe.error.StripeError as e:
            logger.error("invoice_download_error", invoice_id=invoice_id, error=str(e))
            return None
    
    # ───────────────────────────────────────────────────────────────
    # UTILITIES
    # ───────────────────────────────────────────────────────────────
    
    def get_pricing_info(self) -> Dict[str, Dict]:
        """
        Get all pricing tier information.
        
        Returns:
            Dict of tier info
        """
        return {
            tier.value: pricing.to_dict()
            for tier, pricing in self.PRICING_TIERS.items()
        }
    
    def create_checkout_session(
        self,
        customer_id: str,
        tier: SubscriptionTier,
        success_url: str,
        cancel_url: str
    ) -> Optional[str]:
        """
        Create Stripe Checkout session for subscription.
        
        Args:
            customer_id: Stripe customer ID
            tier: Subscription tier
            success_url: Redirect URL on success
            cancel_url: Redirect URL on cancel
        
        Returns:
            Checkout session URL or None
        """
        pricing = self.PRICING_TIERS.get(tier)
        if not pricing:
            return None
        
        try:
            session = stripe.checkout.Session.create(
                customer=customer_id,
                mode="subscription",
                line_items=[{"price": pricing.price_id, "quantity": 1}],
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={"tier": tier.value}
            )
            
            logger.info(
                "checkout_session_created",
                session_id=session.id,
                tier=tier.value
            )
            
            return session.url
            
        except stripe.error.StripeError as e:
            logger.error("checkout_session_error", error=str(e))
            return None


# ═══════════════════════════════════════════════════════════════════
# CLI / MAIN
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("\n" + "="*60)
    print("💳 STRIPE PAYMENT PROCESSOR - TEST RUN")
    print("="*60)
    
    # Show pricing tiers
    print("\n📊 Pricing Tiers:")
    for tier, pricing in StripePaymentProcessor.PRICING_TIERS.items():
        print(f"\n   {tier.value.upper()}:")
        print(f"      Price: €{pricing.amount_eur:,.0f}/month")
        print(f"      API Calls: {pricing.api_calls_limit if pricing.api_calls_limit > 0 else 'Unlimited'}")
        print(f"      Reports: {pricing.reports_limit if pricing.reports_limit > 0 else 'Unlimited'}")
        print(f"      Cities: {pricing.cities_limit if pricing.cities_limit > 0 else 'All 111'}")
        print(f"      Features:")
        for feature in pricing.features[:3]:
            print(f"         • {feature}")
    
    print("\n" + "="*60)
    print("✅ Payment Processor ready for integration!")
    print("   Set STRIPE_API_KEY and STRIPE_WEBHOOK_SECRET in .env")
    print("="*60)
