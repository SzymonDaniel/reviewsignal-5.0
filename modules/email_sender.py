#!/usr/bin/env python3
"""
Email Sender Module - Transactional Email Delivery

Handles sending transactional emails with PDF attachments:
- Monthly reports
- Anomaly alerts
- Invoices
- Welcome emails
- Password resets

Supports multiple providers:
- Resend (recommended, €8/month for 10k emails)
- SendGrid (€15/month for 40k emails)
- Postmark (€11/month for 10k emails)

Author: ReviewSignal Team
Version: 1.0
Date: 2026-01-31
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
