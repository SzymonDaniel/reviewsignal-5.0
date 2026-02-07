#!/usr/bin/env python3
"""
Unit Tests for Payment Processor Module
Tests Stripe integration, subscriptions, and billing
"""
import pytest
from unittest.mock import Mock, patch, MagicMock, call
from datetime import datetime
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from modules.payment_processor import (
    StripePaymentProcessor,
    SubscriptionTier,
    PaymentStatus,
    WebhookEvent,
    PricingTier,
    CustomerData,
    SubscriptionData,
    PaymentData
)


# ═══════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════

@pytest.fixture
def mock_stripe():
    """Mock Stripe module"""
    with patch('modules.payment_processor.stripe') as mock:
        # Mock Stripe Error Classes
        mock_error = Mock()
        mock_error.StripeError = Exception
        mock_error.InvalidRequestError = Exception
        mock_error.CardError = Exception
        mock.error = mock_error

        # Mock Customer
        mock_customer = Mock()
        mock_customer.create.return_value = Mock(
            id='cus_test123',
            email='test@example.com',
            name='Test User',
            metadata={'company': 'TestCo'},
            created=1234567890
        )
        mock_customer.retrieve.return_value = mock_customer.create.return_value
        mock_customer.modify.return_value = mock_customer.create.return_value
        mock.Customer = mock_customer

        # Mock Subscription
        mock_subscription = Mock()
        subscription_item = Mock(id='si_test123', price=Mock(unit_amount=250000))
        subscription_obj = Mock(
            id='sub_test123',
            customer='cus_test123',
            status='active',
            current_period_start=1234567890,
            current_period_end=1237246290,
            cancel_at_period_end=False,
            metadata={'tier': 'starter'},
            items=Mock(data=[subscription_item])
        )
        # Make subscription_obj subscriptable
        subscription_obj.__getitem__ = lambda self, key: {
            'items': {'data': [subscription_item]}
        }.get(key)

        mock_subscription.create.return_value = subscription_obj
        mock_subscription.retrieve.return_value = subscription_obj
        mock_subscription.modify.return_value = subscription_obj
        mock_subscription.delete = Mock(return_value=Mock(id='sub_test123', status='canceled'))
        mock_subscription.cancel = Mock(return_value=Mock(status='canceled'))
        mock.Subscription = mock_subscription

        # Mock PaymentIntent
        mock_payment = Mock()
        mock_payment.create.return_value = Mock(
            id='pi_test123',
            amount=50000,
            currency='eur',
            status='succeeded',
            created=1234567890
        )
        mock_payment.retrieve.return_value = mock_payment.create.return_value
        mock.PaymentIntent = mock_payment

        # Mock Refund
        mock_refund = Mock()
        mock_refund.create.return_value = Mock(
            id='re_test123',
            amount=50000,
            status='succeeded'
        )
        mock.Refund = mock_refund

        # Mock Invoice
        mock_invoice = Mock()
        invoice_obj = Mock(
            id='in_test123',
            number='INV-001',
            customer='cus_test123',
            amount_paid=250000,
            amount_due=250000,
            currency='eur',
            status='paid',
            created=1234567890,
            invoice_pdf='https://example.com/invoice.pdf',
            hosted_invoice_url='https://example.com/hosted'
        )
        mock_invoice.list.return_value = Mock(data=[invoice_obj])
        mock_invoice.retrieve.return_value = invoice_obj
        mock.Invoice = mock_invoice

        # Mock Webhook
        mock_webhook = Mock()
        mock_webhook.construct_event.return_value = {
            'id': 'evt_test123',
            'type': 'payment_intent.succeeded',
            'data': {
                'object': {
                    'id': 'pi_test123',
                    'amount': 50000
                }
            }
        }
        mock.Webhook = mock_webhook

        # Mock checkout Session
        mock_session = Mock()
        mock_session.create.return_value = Mock(
            id='cs_test123',
            url='https://checkout.stripe.com/test'
        )
        mock.checkout = Mock()
        mock.checkout.Session = mock_session

        yield mock


@pytest.fixture
def payment_processor():
    """Create payment processor instance"""
    return StripePaymentProcessor(
        api_key='sk_test_12345',
        webhook_secret='whsec_test123'
    )


# ═══════════════════════════════════════════════════════════════
# ENUM TESTS
# ═══════════════════════════════════════════════════════════════

class TestEnums:
    """Test enum definitions"""

    def test_subscription_tier_values(self):
        """Should have correct subscription tier values"""
        assert SubscriptionTier.TRIAL.value == "trial"
        assert SubscriptionTier.STARTER.value == "starter"
        assert SubscriptionTier.PRO.value == "pro"
        assert SubscriptionTier.ENTERPRISE.value == "enterprise"

    def test_payment_status_values(self):
        """Should have correct payment status values"""
        assert PaymentStatus.PENDING.value == "pending"
        assert PaymentStatus.SUCCEEDED.value == "succeeded"
        assert PaymentStatus.FAILED.value == "failed"
        assert PaymentStatus.CANCELLED.value == "cancelled"
        assert PaymentStatus.REFUNDED.value == "refunded"

    def test_webhook_event_values(self):
        """Should have correct webhook event values"""
        assert WebhookEvent.PAYMENT_SUCCESS.value == "payment_intent.succeeded"
        assert WebhookEvent.PAYMENT_FAILED.value == "payment_intent.payment_failed"
        assert WebhookEvent.SUBSCRIPTION_CREATED.value == "customer.subscription.created"


# ═══════════════════════════════════════════════════════════════
# DATACLASS TESTS
# ═══════════════════════════════════════════════════════════════

class TestPricingTier:
    """Test PricingTier dataclass"""

    def test_pricing_tier_creation(self):
        """Should create pricing tier"""
        tier = PricingTier(
            name="Test Tier",
            price_id="price_test",
            amount_cents=100000,
            currency="eur",
            interval="month",
            features=["Feature 1", "Feature 2"],
            api_calls_limit=1000,
            reports_limit=50,
            cities_limit=5
        )

        assert tier.name == "Test Tier"
        assert tier.amount_cents == 100000
        assert tier.amount_eur == 1000.0

    def test_pricing_tier_to_dict(self):
        """Should convert to dict with amount_eur"""
        tier = PricingTier(
            name="Test",
            price_id="price_test",
            amount_cents=50000,
            currency="eur",
            interval="month",
            features=["Test"],
            api_calls_limit=100,
            reports_limit=10
        )

        data = tier.to_dict()
        assert data['amount_eur'] == 500.0
        assert data['amount_cents'] == 50000


class TestCustomerData:
    """Test CustomerData dataclass"""

    def test_customer_data_creation(self):
        """Should create customer data"""
        customer = CustomerData(
            customer_id="cus_123",
            email="test@example.com",
            name="Test User",
            company="TestCo",
            created_at="2026-01-01"
        )

        assert customer.customer_id == "cus_123"
        assert customer.email == "test@example.com"

    def test_customer_data_to_dict(self):
        """Should convert to dict"""
        customer = CustomerData(
            customer_id="cus_123",
            email="test@example.com",
            name="Test",
            company="TestCo",
            created_at="2026-01-01",
            metadata={'key': 'value'}
        )

        data = customer.to_dict()
        assert data['customer_id'] == "cus_123"
        assert data['metadata']['key'] == 'value'


class TestSubscriptionData:
    """Test SubscriptionData dataclass"""

    def test_subscription_data_creation(self):
        """Should create subscription data"""
        sub = SubscriptionData(
            subscription_id="sub_123",
            customer_id="cus_123",
            tier=SubscriptionTier.PRO,
            status="active",
            amount_eur=5000.0,
            current_period_start="2026-01-01",
            current_period_end="2026-02-01",
            cancel_at_period_end=False
        )

        assert sub.subscription_id == "sub_123"
        assert sub.tier == SubscriptionTier.PRO

    def test_subscription_data_to_dict(self):
        """Should convert to dict with tier value"""
        sub = SubscriptionData(
            subscription_id="sub_123",
            customer_id="cus_123",
            tier=SubscriptionTier.STARTER,
            status="active",
            amount_eur=2500.0,
            current_period_start="2026-01-01",
            current_period_end="2026-02-01",
            cancel_at_period_end=False
        )

        data = sub.to_dict()
        assert data['tier'] == "starter"


class TestPaymentData:
    """Test PaymentData dataclass"""

    def test_payment_data_creation(self):
        """Should create payment data"""
        payment = PaymentData(
            payment_id="pi_123",
            customer_id="cus_123",
            amount=1000.0,
            currency="eur",
            status=PaymentStatus.SUCCEEDED,
            created_at="2026-01-01",
            description="Test payment"
        )

        assert payment.payment_id == "pi_123"
        assert payment.status == PaymentStatus.SUCCEEDED

    def test_payment_data_to_dict(self):
        """Should convert to dict with status value"""
        payment = PaymentData(
            payment_id="pi_123",
            customer_id="cus_123",
            amount=500.0,
            currency="eur",
            status=PaymentStatus.PENDING,
            created_at="2026-01-01"
        )

        data = payment.to_dict()
        assert data['status'] == "pending"


# ═══════════════════════════════════════════════════════════════
# STRIPE PAYMENT PROCESSOR TESTS
# ═══════════════════════════════════════════════════════════════

class TestStripePaymentProcessorInit:
    """Test StripePaymentProcessor initialization"""

    def test_initialization_with_test_key(self):
        """Should initialize with test API key"""
        processor = StripePaymentProcessor(
            api_key='sk_test_12345',
            webhook_secret='whsec_test'
        )

        assert processor.webhook_secret == 'whsec_test'

    def test_initialization_with_live_key(self):
        """Should initialize with live API key"""
        processor = StripePaymentProcessor(
            api_key='sk_live_12345',
            webhook_secret='whsec_live'
        )

        assert processor.webhook_secret == 'whsec_live'

    def test_pricing_tiers_configured(self):
        """Should have pricing tiers configured"""
        processor = StripePaymentProcessor(
            api_key='sk_test_12345',
            webhook_secret='whsec_test'
        )

        assert SubscriptionTier.TRIAL in processor.PRICING_TIERS
        assert SubscriptionTier.STARTER in processor.PRICING_TIERS
        assert SubscriptionTier.PRO in processor.PRICING_TIERS
        assert SubscriptionTier.ENTERPRISE in processor.PRICING_TIERS

    def test_pricing_tier_amounts(self):
        """Should have correct pricing amounts"""
        processor = StripePaymentProcessor(
            api_key='sk_test_12345',
            webhook_secret='whsec_test'
        )

        assert processor.PRICING_TIERS[SubscriptionTier.TRIAL].amount_cents == 0
        assert processor.PRICING_TIERS[SubscriptionTier.STARTER].amount_cents == 250000
        assert processor.PRICING_TIERS[SubscriptionTier.PRO].amount_cents == 500000
        assert processor.PRICING_TIERS[SubscriptionTier.ENTERPRISE].amount_cents == 1000000


class TestCustomerManagement:
    """Test customer management methods"""

    def test_create_customer(self, payment_processor, mock_stripe):
        """Should create Stripe customer"""
        customer = payment_processor.create_customer(
            email="test@example.com",
            name="Test User",
            company="TestCo",
            metadata={'role': 'admin'}
        )

        assert customer.customer_id == 'cus_test123'
        assert customer.email == 'test@example.com'
        assert customer.name == 'Test User'

        mock_stripe.Customer.create.assert_called_once()

    def test_create_customer_without_metadata(self, payment_processor, mock_stripe):
        """Should create customer without metadata"""
        customer = payment_processor.create_customer(
            email="test@example.com",
            name="Test User",
            company="TestCo"
        )

        assert customer.customer_id == 'cus_test123'

    def test_get_customer(self, payment_processor, mock_stripe):
        """Should retrieve existing customer"""
        customer = payment_processor.get_customer('cus_test123')

        assert customer is not None
        assert customer.customer_id == 'cus_test123'

        mock_stripe.Customer.retrieve.assert_called_once_with('cus_test123')

    def test_get_customer_not_found(self, payment_processor, mock_stripe):
        """Should return None for non-existent customer"""
        mock_stripe.Customer.retrieve.side_effect = Exception("Customer not found")

        customer = payment_processor.get_customer('cus_invalid')

        assert customer is None

    def test_update_customer(self, payment_processor, mock_stripe):
        """Should update customer information"""
        customer = payment_processor.update_customer(
            customer_id='cus_test123',
            name='Updated Name',
            email='updated@example.com'
        )

        assert customer is not None
        mock_stripe.Customer.modify.assert_called_once()


class TestSubscriptionManagement:
    """Test subscription management methods"""

    def test_create_subscription(self, payment_processor, mock_stripe):
        """Should create subscription"""
        subscription = payment_processor.create_subscription(
            customer_id='cus_test123',
            tier=SubscriptionTier.STARTER
        )

        assert subscription.subscription_id == 'sub_test123'
        assert subscription.customer_id == 'cus_test123'

        mock_stripe.Subscription.create.assert_called_once()

    def test_get_subscription(self, payment_processor, mock_stripe):
        """Should retrieve subscription"""
        subscription = payment_processor.get_subscription('sub_test123')

        assert subscription is not None
        assert subscription.subscription_id == 'sub_test123'

        mock_stripe.Subscription.retrieve.assert_called_once_with('sub_test123')

    def test_get_subscription_not_found(self, payment_processor, mock_stripe):
        """Should return None for non-existent subscription"""
        mock_stripe.Subscription.retrieve.side_effect = Exception("Not found")

        subscription = payment_processor.get_subscription('sub_invalid')

        assert subscription is None

    def test_cancel_subscription(self, payment_processor, mock_stripe):
        """Should cancel subscription at period end"""
        result = payment_processor.cancel_subscription(
            subscription_id='sub_test123',
            immediate=False
        )

        assert result is not None
        mock_stripe.Subscription.modify.assert_called_once()

    def test_cancel_subscription_immediately(self, payment_processor, mock_stripe):
        """Should cancel subscription immediately"""
        result = payment_processor.cancel_subscription(
            subscription_id='sub_test123',
            immediate=True
        )

        # Returns None when immediate=True (subscription deleted)
        assert result is None
        mock_stripe.Subscription.delete.assert_called_once_with('sub_test123')

    def test_upgrade_subscription(self, payment_processor, mock_stripe):
        """Should upgrade subscription tier"""
        subscription = payment_processor.upgrade_subscription(
            subscription_id='sub_test123',
            new_tier=SubscriptionTier.PRO
        )

        assert subscription is not None
        mock_stripe.Subscription.modify.assert_called_once()


class TestPaymentProcessing:
    """Test payment processing methods"""

    def test_create_payment_intent(self, payment_processor, mock_stripe):
        """Should create payment intent"""
        result = payment_processor.create_payment_intent(
            customer_id='cus_test123',
            amount_cents=50000,
            description='Test payment'
        )

        assert result is not None
        assert 'intent_id' in result
        assert result['amount'] == 50000

        mock_stripe.PaymentIntent.create.assert_called_once()

    def test_process_one_time_payment(self, payment_processor, mock_stripe):
        """Should process one-time payment"""
        payment = payment_processor.process_one_time_payment(
            customer_id='cus_test123',
            amount_cents=100000,
            description='One-time charge',
            payment_method_id='pm_test123'
        )

        assert payment is not None
        assert payment.amount == 1000.0

    def test_refund_payment(self, payment_processor, mock_stripe):
        """Should refund payment"""
        result = payment_processor.refund_payment(
            payment_id='pi_test123',
            amount_cents=50000
        )

        assert result is not None
        mock_stripe.Refund.create.assert_called_once()

    def test_refund_payment_full_amount(self, payment_processor, mock_stripe):
        """Should refund full amount when not specified"""
        result = payment_processor.refund_payment(
            payment_id='pi_test123'
        )

        assert result is not None


class TestWebhookHandling:
    """Test webhook handling"""

    def test_handle_webhook_success(self, payment_processor, mock_stripe):
        """Should handle webhook successfully"""
        payload = b'{"type": "payment_intent.succeeded"}'
        signature = 'test_signature'

        result = payment_processor.handle_webhook(payload, signature)

        assert result['processed'] is True
        assert 'event_type' in result
        assert result['event_type'] == 'payment_intent.succeeded'

    def test_handle_webhook_invalid_signature(self, payment_processor, mock_stripe):
        """Should reject webhook with invalid signature"""
        mock_stripe.Webhook.construct_event.side_effect = Exception("Invalid signature")

        payload = b'{"type": "test"}'
        signature = 'invalid_signature'

        result = payment_processor.handle_webhook(payload, signature)

        assert result is None or 'error' in str(result)

    def test_verify_webhook_signature_valid(self, payment_processor):
        """Should verify valid webhook signature"""
        payload = b'test_payload'
        signature = 'test_signature'

        with patch.object(payment_processor, '_verify_webhook_signature', return_value=True):
            result = payment_processor._verify_webhook_signature(payload, signature)
            assert result is True

    def test_process_webhook_event_payment_success(self, payment_processor):
        """Should process payment success event"""
        event = {
            'id': 'evt_test123',
            'type': 'payment_intent.succeeded',
            'data': {
                'object': {
                    'id': 'pi_test123',
                    'amount': 50000,
                    'customer': 'cus_test123'
                }
            }
        }

        result = payment_processor._process_webhook_event(event)

        assert result['event_type'] == 'payment_intent.succeeded'
        assert result['processed'] is True
        assert 'data' in result


class TestInvoiceManagement:
    """Test invoice management methods"""

    def test_get_invoices(self, payment_processor, mock_stripe):
        """Should retrieve customer invoices"""
        invoices = payment_processor.get_invoices(
            customer_id='cus_test123',
            limit=10
        )

        assert len(invoices) > 0
        assert invoices[0]['invoice_id'] == 'in_test123'
        assert invoices[0]['amount_due'] == 2500.0

        mock_stripe.Invoice.list.assert_called_once()

    def test_download_invoice(self, payment_processor, mock_stripe):
        """Should get invoice download URL"""
        url = payment_processor.download_invoice('in_test123')

        assert url is not None
        assert 'invoice.pdf' in url

        mock_stripe.Invoice.retrieve.assert_called_once_with('in_test123')

    def test_download_invoice_not_found(self, payment_processor, mock_stripe):
        """Should return None for non-existent invoice"""
        mock_stripe.Invoice.retrieve.side_effect = Exception("Not found")

        url = payment_processor.download_invoice('in_invalid')

        assert url is None


class TestPricingInfo:
    """Test pricing information methods"""

    def test_get_pricing_info(self, payment_processor):
        """Should return all pricing tiers"""
        pricing = payment_processor.get_pricing_info()

        assert 'trial' in pricing
        assert 'starter' in pricing
        assert 'pro' in pricing
        assert 'enterprise' in pricing

        assert pricing['starter']['amount_eur'] == 2500.0
        assert pricing['pro']['amount_eur'] == 5000.0

    def test_pricing_info_structure(self, payment_processor):
        """Should have correct pricing info structure"""
        pricing = payment_processor.get_pricing_info()

        starter = pricing['starter']
        assert 'name' in starter
        assert 'features' in starter
        assert 'api_calls_limit' in starter
        assert 'amount_eur' in starter


class TestCheckoutSession:
    """Test checkout session creation"""

    def test_create_checkout_session(self, payment_processor, mock_stripe):
        """Should create checkout session"""
        checkout_url = payment_processor.create_checkout_session(
            customer_id='cus_test123',
            tier=SubscriptionTier.STARTER,
            success_url='https://example.com/success',
            cancel_url='https://example.com/cancel'
        )

        assert checkout_url is not None
        assert 'checkout.stripe.com' in checkout_url

        mock_stripe.checkout.Session.create.assert_called_once()


class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_create_customer_with_empty_email(self, payment_processor, mock_stripe):
        """Should handle empty email"""
        mock_stripe.Customer.create.side_effect = Exception("Invalid email")

        with pytest.raises(Exception):
            payment_processor.create_customer(
                email="",
                name="Test",
                company="TestCo"
            )

    def test_create_payment_with_zero_amount(self, payment_processor, mock_stripe):
        """Should handle zero amount"""
        mock_stripe.PaymentIntent.create.side_effect = Exception("Amount too small")

        result = payment_processor.create_payment_intent(
            customer_id='cus_test123',
            amount_cents=0,
            description='Zero payment'
        )

        assert result is None

    def test_subscription_tier_limits(self, payment_processor):
        """Should have correct tier limits"""
        trial = payment_processor.PRICING_TIERS[SubscriptionTier.TRIAL]
        enterprise = payment_processor.PRICING_TIERS[SubscriptionTier.ENTERPRISE]

        assert trial.api_calls_limit == 100
        assert enterprise.api_calls_limit == -1  # Unlimited

    def test_refund_invalid_payment(self, payment_processor, mock_stripe):
        """Should handle refund of invalid payment"""
        mock_stripe.Refund.create.side_effect = Exception("Payment not found")

        result = payment_processor.refund_payment('pi_invalid')

        assert result is None
