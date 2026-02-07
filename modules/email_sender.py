#!/usr/bin/env python3
"""
Email Sender Module - Transactional Email Delivery

Handles sending transactional emails with PDF attachments:
- Monthly reports
- Anomaly alerts
- Invoices
- Welcome emails
- Trial ending warnings
- Payment failed (dunning)
- Password resets

Supports multiple providers:
- Resend (recommended, €8/month for 10k emails)
- SendGrid (€15/month for 40k emails)
- Postmark (€11/month for 10k emails)

Author: ReviewSignal Team
Version: 2.0
Date: 2026-02-07
"""

import os
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from enum import Enum
import structlog
from datetime import datetime
import base64

logger = structlog.get_logger(__name__)


class EmailProvider(Enum):
    """Supported email providers"""
    RESEND = "resend"
    SENDGRID = "sendgrid"
    POSTMARK = "postmark"


class EmailTemplate(Enum):
    """Available email templates"""
    MONTHLY_REPORT = "monthly_report"
    ANOMALY_ALERT = "anomaly_alert"
    INVOICE = "invoice"
    WELCOME = "welcome"
    PASSWORD_RESET = "password_reset"
    TRIAL_ENDING = "trial_ending"
    PAYMENT_FAILED = "payment_failed"


@dataclass
class EmailAttachment:
    """Email attachment data"""
    filename: str
    content: bytes
    content_type: str = "application/pdf"


@dataclass
class EmailMessage:
    """Email message structure"""
    to_email: str
    to_name: str
    subject: str
    html_body: str
    text_body: Optional[str] = None
    attachments: Optional[List[EmailAttachment]] = None
    reply_to: Optional[str] = None
    tags: Optional[List[str]] = None


class EmailSender:
    """
    Main email sender class.
    Handles transactional email delivery with attachments.
    """

    def __init__(
        self,
        provider: Optional[EmailProvider] = None,
        api_key: Optional[str] = None,
        from_email: Optional[str] = None,
        from_name: Optional[str] = None
    ):
        """
        Initialize email sender.

        Args:
            provider: Email provider (resend, sendgrid, postmark)
            api_key: Provider API key
            from_email: Sender email address
            from_name: Sender name
        """
        # Load from environment if not provided
        self.provider = provider or EmailProvider(os.getenv("EMAIL_SERVICE", "resend"))
        self.api_key = api_key or os.getenv("RESEND_API_KEY", "")
        self.from_email = from_email or os.getenv("FROM_EMAIL", "reports@reviewsignal.ai")
        self.from_name = from_name or os.getenv("FROM_NAME", "ReviewSignal Analytics")

        if not self.api_key:
            logger.warning("email_sender_no_api_key", provider=self.provider.value)

        # Initialize provider client
        self.client = self._init_provider()

        logger.info(
            "email_sender_initialized",
            provider=self.provider.value,
            from_email=self.from_email,
            has_api_key=bool(self.api_key)
        )

    def _init_provider(self) -> Any:
        """Initialize provider-specific client"""
        if self.provider == EmailProvider.RESEND:
            try:
                import resend
                resend.api_key = self.api_key
                return resend
            except ImportError:
                logger.error("resend_not_installed", message="Run: pip install resend")
                return None

        elif self.provider == EmailProvider.SENDGRID:
            try:
                from sendgrid import SendGridAPIClient
                return SendGridAPIClient(self.api_key)
            except ImportError:
                logger.error("sendgrid_not_installed", message="Run: pip install sendgrid")
                return None

        elif self.provider == EmailProvider.POSTMARK:
            try:
                from postmarker.core import PostmarkClient
                return PostmarkClient(server_token=self.api_key)
            except ImportError:
                logger.error("postmark_not_installed", message="Run: pip install postmarker")
                return None

        return None

    def send_email(self, message: EmailMessage) -> Dict[str, Any]:
        """
        Send email message.

        Args:
            message: EmailMessage object with all email data

        Returns:
            Dict with status and message_id
        """
        if not self.client:
            logger.error("email_client_not_initialized")
            return {"success": False, "error": "Email client not initialized"}

        try:
            if self.provider == EmailProvider.RESEND:
                result = self._send_resend(message)
            elif self.provider == EmailProvider.SENDGRID:
                result = self._send_sendgrid(message)
            elif self.provider == EmailProvider.POSTMARK:
                result = self._send_postmark(message)
            else:
                result = {"success": False, "error": "Unsupported provider"}

            logger.info(
                "email_sent",
                to_email=message.to_email,
                subject=message.subject,
                provider=self.provider.value,
                success=result.get("success")
            )

            return result

        except Exception as e:
            logger.error(
                "email_send_failed",
                to_email=message.to_email,
                error=str(e),
                provider=self.provider.value
            )
            return {"success": False, "error": str(e)}

    def _send_resend(self, message: EmailMessage) -> Dict[str, Any]:
        """Send email via Resend"""
        params = {
            "from": f"{self.from_name} <{self.from_email}>",
            "to": [message.to_email],
            "subject": message.subject,
            "html": message.html_body,
        }

        if message.text_body:
            params["text"] = message.text_body

        if message.reply_to:
            params["reply_to"] = message.reply_to

        if message.tags:
            params["tags"] = [{"name": tag} for tag in message.tags]

        # Add attachments
        if message.attachments:
            params["attachments"] = []
            for attachment in message.attachments:
                params["attachments"].append({
                    "filename": attachment.filename,
                    "content": base64.b64encode(attachment.content).decode('utf-8'),
                })

        try:
            response = self.client.Emails.send(params)
            return {
                "success": True,
                "message_id": response.get("id"),
                "provider": "resend"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _send_sendgrid(self, message: EmailMessage) -> Dict[str, Any]:
        """Send email via SendGrid"""
        from sendgrid.helpers.mail import (
            Mail, Email, To, Content, Attachment,
            FileContent, FileName, FileType, Disposition
        )

        mail = Mail(
            from_email=Email(self.from_email, self.from_name),
            to_emails=To(message.to_email, message.to_name),
            subject=message.subject,
            html_content=Content("text/html", message.html_body)
        )

        if message.text_body:
            mail.add_content(Content("text/plain", message.text_body))

        # Add attachments
        if message.attachments:
            for attachment in message.attachments:
                file_content = base64.b64encode(attachment.content).decode('utf-8')
                attached_file = Attachment(
                    FileContent(file_content),
                    FileName(attachment.filename),
                    FileType(attachment.content_type),
                    Disposition('attachment')
                )
                mail.add_attachment(attached_file)

        try:
            response = self.client.send(mail)
            return {
                "success": response.status_code in [200, 202],
                "message_id": response.headers.get("X-Message-Id"),
                "status_code": response.status_code,
                "provider": "sendgrid"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _send_postmark(self, message: EmailMessage) -> Dict[str, Any]:
        """Send email via Postmark"""
        params = {
            "From": f"{self.from_name} <{self.from_email}>",
            "To": f"{message.to_name} <{message.to_email}>",
            "Subject": message.subject,
            "HtmlBody": message.html_body,
        }

        if message.text_body:
            params["TextBody"] = message.text_body

        # Add attachments
        if message.attachments:
            params["Attachments"] = []
            for attachment in message.attachments:
                params["Attachments"].append({
                    "Name": attachment.filename,
                    "Content": base64.b64encode(attachment.content).decode('utf-8'),
                    "ContentType": attachment.content_type
                })

        try:
            response = self.client.emails.send(**params)
            return {
                "success": True,
                "message_id": response.get("MessageID"),
                "provider": "postmark"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}


    # ---------------------------------------------------------------
    # SUBSCRIPTION LIFECYCLE EMAILS
    # ---------------------------------------------------------------

    def send_welcome_email(
        self,
        customer_email: str,
        customer_name: str,
        tier_name: str,
        features: List[str]
    ) -> Dict[str, Any]:
        """
        Send welcome email when a new subscription is created.

        Args:
            customer_email: Customer email address
            customer_name: Customer name
            tier_name: Subscription tier name (e.g., 'Starter', 'Pro', 'Enterprise')
            features: List of features included in the tier

        Returns:
            Dict with send status
        """
        features_html = "".join(f"<li>{feature}</li>" for feature in features)

        html_body = f"""<!DOCTYPE html>
<html><head><style>
body {{{{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}}}
.container {{{{ max-width: 600px; margin: 0 auto; padding: 20px; }}}}
.header {{{{ background-color: #2d3748; color: white; padding: 20px; text-align: center; }}}}
.content {{{{ padding: 30px 20px; background-color: #f7fafc; }}}}
.tier-badge {{{{ display: inline-block; padding: 8px 20px; background-color: #4299e1; color: white; border-radius: 20px; font-weight: bold; font-size: 14px; margin: 10px 0; }}}}
.features-box {{{{ background-color: #ebf8ff; border-left: 4px solid #4299e1; padding: 15px; margin: 20px 0; }}}}
.features-box ul {{{{ margin: 10px 0; padding-left: 20px; }}}}
.quickstart {{{{ background-color: #f0fff4; border-left: 4px solid #48bb78; padding: 15px; margin: 20px 0; }}}}
.button {{{{ display: inline-block; padding: 12px 30px; background-color: #4299e1; color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; }}}}
.footer {{{{ padding: 20px; text-align: center; font-size: 12px; color: #718096; }}}}
</style></head><body><div class="container">
<div class="header"><h1>Welcome to ReviewSignal</h1><p>Your alternative data journey starts now</p></div>
<div class="content">
<p>Dear {customer_name},</p>
<p>Thank you for subscribing to ReviewSignal! We are excited to have you on board.</p>
<p>Your subscription plan:</p><div class="tier-badge">{tier_name}</div>
<div class="features-box"><strong>What's included in your plan:</strong><ul>{features_html}</ul></div>
<div class="quickstart"><strong>Quick Start Guide:</strong><ol>
<li>Access the API documentation at <a href="https://api.reviewsignal.ai/docs">api.reviewsignal.ai/docs</a></li>
<li>Your API key will be sent in a separate secure email</li>
<li>Check out sample reports in your dashboard</li>
<li>Set up your first alert for sentiment changes</li></ol></div>
<a href="https://api.reviewsignal.ai/dashboard" class="button">Go to Dashboard</a>
<p>If you have any questions, our team is here to help:</p>
<ul><li>Email: <a href="mailto:team@reviewsignal.ai">team@reviewsignal.ai</a></li>
<li>Documentation: <a href="https://api.reviewsignal.ai/docs">api.reviewsignal.ai/docs</a></li></ul>
<p>Best regards,<br>The ReviewSignal Team</p></div>
<div class="footer"><p>&copy; 2026 ReviewSignal Analytics. All rights reserved.</p>
<p><a href="https://reviewsignal.ai">reviewsignal.ai</a></p></div></div></body></html>"""

        features_text = "\n".join(f"- {f}" for f in features)
        text_body = (
            f"Welcome to ReviewSignal!\n\nDear {customer_name},\n\n"
            f"Thank you for subscribing!\nYour plan: {tier_name}\n\n"
            f"What's included:\n{features_text}\n\n"
            f"Quick Start: https://api.reviewsignal.ai/docs\n"
            f"Dashboard: https://api.reviewsignal.ai/dashboard\n\n"
            f"Need help? team@reviewsignal.ai\n\nBest regards,\nThe ReviewSignal Team\n"
        )

        message = EmailMessage(
            to_email=customer_email, to_name=customer_name,
            subject=f"Welcome to ReviewSignal - {tier_name} Plan",
            html_body=html_body, text_body=text_body,
            tags=["welcome", f"tier-{tier_name.lower()}"]
        )
        return self.send_email(message)

    def send_trial_ending_email(
        self,
        customer_email: str,
        customer_name: str,
        days_remaining: int,
        tier_recommendation: str
    ) -> Dict[str, Any]:
        """
        Send trial ending warning email.

        Args:
            customer_email: Customer email address
            customer_name: Customer name
            days_remaining: Days remaining in trial
            tier_recommendation: Recommended paid tier name

        Returns:
            Dict with send status
        """
        urgency_color = "#c53030" if days_remaining <= 1 else "#ed8936" if days_remaining <= 3 else "#4299e1"
        urgency_text = "expires tomorrow" if days_remaining <= 1 else f"expires in {days_remaining} days"
        days_label = "day" if days_remaining == 1 else "days"

        html_body = f"""<!DOCTYPE html>
<html><head><style>
body {{{{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}}}
.container {{{{ max-width: 600px; margin: 0 auto; padding: 20px; }}}}
.header {{{{ background-color: {urgency_color}; color: white; padding: 20px; text-align: center; }}}}
.content {{{{ padding: 30px 20px; background-color: #f7fafc; }}}}
.countdown {{{{ text-align: center; font-size: 48px; font-weight: bold; color: {urgency_color}; margin: 20px 0; }}}}
.countdown-label {{{{ text-align: center; font-size: 14px; color: #718096; margin-bottom: 20px; }}}}
.lose-box {{{{ background-color: #fff5f5; border-left: 4px solid #f56565; padding: 15px; margin: 20px 0; }}}}
.upgrade-box {{{{ background-color: #f0fff4; border-left: 4px solid #48bb78; padding: 15px; margin: 20px 0; }}}}
.button {{{{ display: inline-block; padding: 14px 40px; background-color: {urgency_color}; color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; font-weight: bold; font-size: 16px; }}}}
.footer {{{{ padding: 20px; text-align: center; font-size: 12px; color: #718096; }}}}
</style></head><body><div class="container">
<div class="header"><h1>Your Trial {urgency_text.title()}</h1><p>Don't lose access to your data insights</p></div>
<div class="content"><p>Dear {customer_name},</p>
<div class="countdown">{days_remaining}</div>
<div class="countdown-label">{days_label} remaining in your trial</div>
<div class="lose-box"><strong>When your trial ends, you will lose access to:</strong><ul>
<li>Real-time sentiment analysis across all locations</li>
<li>Anomaly detection alerts</li><li>Monthly PDF reports</li>
<li>API access for data integration</li><li>Historical data and trend analysis</li></ul></div>
<div class="upgrade-box"><strong>Recommended for you: {tier_recommendation} Plan</strong>
<p>Based on your trial usage, we recommend the {tier_recommendation} plan to continue getting actionable insights.</p></div>
<p style="text-align: center;"><a href="https://api.reviewsignal.ai/dashboard/billing" class="button">Upgrade Now</a></p>
<p>Questions? Contact us at <a href="mailto:team@reviewsignal.ai">team@reviewsignal.ai</a>.</p>
<p>Best regards,<br>The ReviewSignal Team</p></div>
<div class="footer"><p>&copy; 2026 ReviewSignal Analytics. All rights reserved.</p>
<p><a href="https://reviewsignal.ai">reviewsignal.ai</a></p></div></div></body></html>"""

        text_body = (
            f"Your trial {urgency_text}\n\nDear {customer_name},\n\n"
            f"You have {days_remaining} {days_label} remaining in your ReviewSignal trial.\n\n"
            f"When your trial ends, you will lose access to:\n"
            f"- Real-time sentiment analysis\n- Anomaly detection alerts\n"
            f"- Monthly PDF reports\n- API access\n- Historical data\n\n"
            f"Recommended: {tier_recommendation} Plan\n"
            f"Upgrade: https://api.reviewsignal.ai/dashboard/billing\n\n"
            f"Best regards,\nThe ReviewSignal Team\n"
        )

        subject_prefix = "URGENT: " if days_remaining <= 1 else ""
        message = EmailMessage(
            to_email=customer_email, to_name=customer_name,
            subject=f"{subject_prefix}Your ReviewSignal trial {urgency_text}",
            html_body=html_body, text_body=text_body,
            tags=["trial-ending", f"days-{days_remaining}"]
        )
        return self.send_email(message)

    def send_payment_failed_email(
        self,
        customer_email: str,
        customer_name: str,
        amount: float,
        retry_date: str
    ) -> Dict[str, Any]:
        """
        Send payment failed (dunning) email.

        Args:
            customer_email: Customer email address
            customer_name: Customer name
            amount: Failed payment amount in EUR
            retry_date: Date of next payment retry

        Returns:
            Dict with send status
        """
        html_body = f"""<!DOCTYPE html>
<html><head><style>
body {{{{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}}}
.container {{{{ max-width: 600px; margin: 0 auto; padding: 20px; }}}}
.header {{{{ background-color: #f56565; color: white; padding: 20px; text-align: center; }}}}
.content {{{{ padding: 30px 20px; background-color: #f7fafc; }}}}
.alert-box {{{{ background-color: #fff5f5; border: 2px solid #f56565; border-radius: 8px; padding: 20px; margin: 20px 0; text-align: center; }}}}
.amount {{{{ font-size: 32px; font-weight: bold; color: #c53030; }}}}
.retry-info {{{{ background-color: #fffff0; border-left: 4px solid #ed8936; padding: 15px; margin: 20px 0; }}}}
.warning {{{{ background-color: #fff5f5; border-left: 4px solid #f56565; padding: 15px; margin: 20px 0; }}}}
.button {{{{ display: inline-block; padding: 14px 40px; background-color: #4299e1; color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; font-weight: bold; }}}}
.footer {{{{ padding: 20px; text-align: center; font-size: 12px; color: #718096; }}}}
</style></head><body><div class="container">
<div class="header"><h1>Payment Failed</h1><p>Action required to maintain your service</p></div>
<div class="content"><p>Dear {customer_name},</p>
<p>We were unable to process your latest payment for ReviewSignal.</p>
<div class="alert-box"><p>Failed payment amount:</p><p class="amount">&euro;{amount:,.2f}</p></div>
<div class="retry-info"><strong>Next retry date: {retry_date}</strong>
<p>We will automatically retry the payment. Please ensure your payment method is up to date.</p></div>
<p style="text-align: center;"><a href="https://api.reviewsignal.ai/dashboard/billing" class="button">Update Payment Method</a></p>
<div class="warning"><strong>Important:</strong> If payment fails after multiple retries, your subscription will be suspended and you will lose access to:<ul>
<li>API access and data feeds</li><li>Sentiment analysis reports</li>
<li>Anomaly detection alerts</li><li>Dashboard and historical data</li></ul></div>
<p>Questions? Contact <a href="mailto:team@reviewsignal.ai">team@reviewsignal.ai</a>.</p>
<p>Best regards,<br>The ReviewSignal Team</p></div>
<div class="footer"><p>&copy; 2026 ReviewSignal Analytics.</p>
<p><a href="https://reviewsignal.ai">reviewsignal.ai</a></p></div></div></body></html>"""

        text_body = (
            f"Payment Failed\n\nDear {customer_name},\n\n"
            f"Failed amount: EUR {amount:,.2f}\nNext retry: {retry_date}\n\n"
            f"Update payment: https://api.reviewsignal.ai/dashboard/billing\n\n"
            f"Best regards,\nThe ReviewSignal Team\n"
        )

        message = EmailMessage(
            to_email=customer_email, to_name=customer_name,
            subject="Payment Failed - Update your payment method for ReviewSignal",
            html_body=html_body, text_body=text_body,
            tags=["payment-failed", "dunning"]
        )
        return self.send_email(message)

    def send_invoice_email(
        self,
        customer_email: str,
        customer_name: str,
        invoice_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Send invoice receipt email.

        Args:
            customer_email: Customer email address
            customer_name: Customer name
            invoice_data: Dict with keys: invoice_number, date, amount, currency,
                         tier, period, payment_method, invoice_pdf_url

        Returns:
            Dict with send status
        """
        invoice_number = invoice_data.get('invoice_number', 'N/A')
        invoice_date = invoice_data.get('date', datetime.now().strftime('%Y-%m-%d'))
        amount = invoice_data.get('amount', 0)
        currency = invoice_data.get('currency', 'EUR').upper()
        tier = invoice_data.get('tier', 'Pro')
        period = invoice_data.get('period', 'Monthly')
        payment_method = invoice_data.get('payment_method', 'Card ending in ****')
        invoice_pdf_url = invoice_data.get('invoice_pdf_url', '')

        download_link = ""
        if invoice_pdf_url:
            download_link = f'<p style="text-align: center;"><a href="{invoice_pdf_url}" class="button">Download Invoice PDF</a></p>'

        html_body = f"""<!DOCTYPE html>
<html><head><style>
body {{{{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}}}
.container {{{{ max-width: 600px; margin: 0 auto; padding: 20px; }}}}
.header {{{{ background-color: #2d3748; color: white; padding: 20px; text-align: center; }}}}
.content {{{{ padding: 30px 20px; background-color: #f7fafc; }}}}
.invoice-box {{{{ background-color: white; border: 1px solid #e2e8f0; border-radius: 8px; padding: 25px; margin: 20px 0; }}}}
.paid-badge {{{{ display: inline-block; padding: 6px 16px; background-color: #48bb78; color: white; border-radius: 20px; font-weight: bold; font-size: 12px; }}}}
.button {{{{ display: inline-block; padding: 12px 30px; background-color: #4299e1; color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; }}}}
.footer {{{{ padding: 20px; text-align: center; font-size: 12px; color: #718096; }}}}
table.invoice-table {{{{ width: 100%; border-collapse: collapse; }}}}
table.invoice-table td {{{{ padding: 8px 0; }}}}
table.invoice-table td.label {{{{ color: #718096; }}}}
table.invoice-table td.value {{{{ text-align: right; font-weight: bold; }}}}
table.invoice-table tr.total td {{{{ border-top: 2px solid #2d3748; padding-top: 12px; font-size: 18px; }}}}
</style></head><body><div class="container">
<div class="header"><h1>Payment Receipt</h1><p>Invoice #{invoice_number}</p></div>
<div class="content"><p>Dear {customer_name},</p>
<p>Thank you for your payment. Here is your invoice receipt.</p>
<div class="invoice-box"><table class="invoice-table">
<tr><td class="label">Invoice Number</td><td class="value">#{invoice_number}</td></tr>
<tr><td class="label">Date</td><td class="value">{invoice_date}</td></tr>
<tr><td class="label">Subscription</td><td class="value">ReviewSignal {tier} Plan</td></tr>
<tr><td class="label">Billing Period</td><td class="value">{period}</td></tr>
<tr><td class="label">Payment Method</td><td class="value">{payment_method}</td></tr>
<tr><td class="label">Status</td><td class="value"><span class="paid-badge">PAID</span></td></tr>
<tr class="total"><td class="label">Total</td><td class="value">{currency} {amount:,.2f}</td></tr>
</table></div>{download_link}
<p>View invoices: <a href="https://api.reviewsignal.ai/dashboard/billing">billing dashboard</a>.</p>
<p>Questions? <a href="mailto:team@reviewsignal.ai">team@reviewsignal.ai</a>.</p>
<p>Best regards,<br>The ReviewSignal Team</p></div>
<div class="footer"><p>&copy; 2026 ReviewSignal Analytics.</p>
<p><a href="https://reviewsignal.ai">reviewsignal.ai</a></p></div></div></body></html>"""

        pdf_line = f"Download: {invoice_pdf_url}\n" if invoice_pdf_url else ""
        text_body = (
            f"Payment Receipt - Invoice #{invoice_number}\n\nDear {customer_name},\n\n"
            f"Invoice: #{invoice_number}\nDate: {invoice_date}\n"
            f"Subscription: ReviewSignal {tier} Plan\nPeriod: {period}\n"
            f"Payment: {payment_method}\nTotal: {currency} {amount:,.2f}\n\n"
            f"{pdf_line}"
            f"View invoices: https://api.reviewsignal.ai/dashboard/billing\n\n"
            f"Best regards,\nThe ReviewSignal Team\n"
        )

        message = EmailMessage(
            to_email=customer_email, to_name=customer_name,
            subject=f"Payment Receipt - Invoice #{invoice_number} ({currency} {amount:,.2f})",
            html_body=html_body, text_body=text_body,
            tags=["invoice", f"invoice-{invoice_number}"]
        )
        return self.send_email(message)

    # ---------------------------------------------------------------
    # EXISTING REPORT & ALERT EMAILS
    # ---------------------------------------------------------------

    def send_monthly_report(
        self,
        to_email: str,
        to_name: str,
        company: str,
        report_path: Path,
        period: str
    ) -> Dict[str, Any]:
        """
        Send monthly report email with PDF attachment.

        Args:
            to_email: Recipient email
            to_name: Recipient name
            company: Company name
            report_path: Path to PDF report
            period: Report period (e.g., "January 2026")

        Returns:
            Dict with send status
        """
        # Read PDF file
        with open(report_path, 'rb') as f:
            pdf_content = f.read()

        attachment = EmailAttachment(
            filename=report_path.name,
            content=pdf_content,
            content_type="application/pdf"
        )

        # Create email content
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: #2d3748; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 30px 20px; background-color: #f7fafc; }}
                .button {{ display: inline-block; padding: 12px 30px; background-color: #4299e1; color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
                .footer {{ padding: 20px; text-align: center; font-size: 12px; color: #718096; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>ReviewSignal Analytics</h1>
                    <p>Monthly Sentiment Report</p>
                </div>
                <div class="content">
                    <p>Dear {to_name},</p>

                    <p>Your monthly sentiment analysis report for <strong>{period}</strong> is ready.</p>

                    <p>This comprehensive report includes:</p>
                    <ul>
                        <li>Overall sentiment trends and analysis</li>
                        <li>Key themes from customer reviews</li>
                        <li>Positive and negative feedback highlights</li>
                        <li>Strategic recommendations</li>
                    </ul>

                    <p>The full report is attached as a PDF to this email.</p>

                    <p>If you have any questions about this report, please don't hesitate to reach out to our team.</p>

                    <p>Best regards,<br>
                    The ReviewSignal Team</p>
                </div>
                <div class="footer">
                    <p>&copy; 2026 ReviewSignal Analytics. All rights reserved.</p>
                    <p><a href="https://reviewsignal.ai">reviewsignal.ai</a></p>
                    <p><small>CONFIDENTIAL: This report contains proprietary data intended solely for {company}.</small></p>
                </div>
            </div>
        </body>
        </html>
        """

        text_body = f"""
        ReviewSignal Analytics - Monthly Report

        Dear {to_name},

        Your monthly sentiment analysis report for {period} is ready.

        This report includes:
        - Overall sentiment trends and analysis
        - Key themes from customer reviews
        - Positive and negative feedback highlights
        - Strategic recommendations

        The full report is attached as a PDF to this email.

        If you have any questions, please contact our team.

        Best regards,
        The ReviewSignal Team

        ---
        ReviewSignal Analytics
        https://reviewsignal.ai

        CONFIDENTIAL: This report contains proprietary data intended solely for {company}.
        """

        message = EmailMessage(
            to_email=to_email,
            to_name=to_name,
            subject=f"Monthly Sentiment Report - {period}",
            html_body=html_body,
            text_body=text_body,
            attachments=[attachment],
            tags=["monthly-report", period.lower().replace(" ", "-")]
        )

        return self.send_email(message)

    def send_anomaly_alert(
        self,
        to_email: str,
        to_name: str,
        alert_type: str,
        alert_description: str,
        severity: str
    ) -> Dict[str, Any]:
        """
        Send anomaly detection alert email.

        Args:
            to_email: Recipient email
            to_name: Recipient name
            alert_type: Type of anomaly detected
            alert_description: Description of the anomaly
            severity: Alert severity (low, medium, high, critical)

        Returns:
            Dict with send status
        """
        severity_colors = {
            "low": "#48bb78",
            "medium": "#ed8936",
            "high": "#f56565",
            "critical": "#c53030"
        }
        color = severity_colors.get(severity.lower(), "#718096")

        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: {color}; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 30px 20px; background-color: #f7fafc; }}
                .alert-box {{ background-color: #fff5f5; border-left: 4px solid {color}; padding: 15px; margin: 20px 0; }}
                .button {{ display: inline-block; padding: 12px 30px; background-color: #4299e1; color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
                .footer {{ padding: 20px; text-align: center; font-size: 12px; color: #718096; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>⚠️ Anomaly Alert</h1>
                    <p>Severity: {severity.upper()}</p>
                </div>
                <div class="content">
                    <p>Dear {to_name},</p>

                    <p>Our system has detected an anomaly that requires your attention:</p>

                    <div class="alert-box">
                        <h3>{alert_type}</h3>
                        <p>{alert_description}</p>
                    </div>

                    <p>We recommend reviewing this alert and taking appropriate action.</p>

                    <a href="https://api.reviewsignal.ai/dashboard/alerts" class="button">View Alert Details</a>

                    <p>Best regards,<br>
                    The ReviewSignal Team</p>
                </div>
                <div class="footer">
                    <p>&copy; 2026 ReviewSignal Analytics. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """

        message = EmailMessage(
            to_email=to_email,
            to_name=to_name,
            subject=f"⚠️ Anomaly Alert: {alert_type} ({severity.upper()})",
            html_body=html_body,
            tags=["anomaly-alert", severity.lower()]
        )

        return self.send_email(message)


# Convenience functions
def send_monthly_report(
    to_email: str,
    to_name: str,
    company: str,
    report_path: Path,
    period: str
) -> Dict[str, Any]:
    """
    Convenience function to send monthly report.
    Uses default email sender configuration from environment.
    """
    sender = EmailSender()
    return sender.send_monthly_report(to_email, to_name, company, report_path, period)


def send_anomaly_alert(
    to_email: str,
    to_name: str,
    alert_type: str,
    alert_description: str,
    severity: str = "medium"
) -> Dict[str, Any]:
    """
    Convenience function to send anomaly alert.
    Uses default email sender configuration from environment.
    """
    sender = EmailSender()
    return sender.send_anomaly_alert(to_email, to_name, alert_type, alert_description, severity)


if __name__ == "__main__":
    # Test email sender
    logger.info("email_sender_module_loaded")

    # Check if configured
    sender = EmailSender()
    if sender.client:
        print(f"✅ Email sender configured: {sender.provider.value}")
        print(f"   From: {sender.from_email}")
    else:
        print("❌ Email sender not configured")
        print("   Set EMAIL_SERVICE, RESEND_API_KEY, FROM_EMAIL in .env")

    print("\nTo install providers:")
    print("  Resend:    pip install resend")
    print("  SendGrid:  pip install sendgrid")
    print("  Postmark:  pip install postmarker")
