"""
GDPR Notification System
ReviewSignal 5.0

Email notifications for GDPR compliance:
- Request creation confirmation
- Request completion notification
- Overdue request alerts (to DPO/admin)
- Consent expiration warnings
"""

import structlog
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import and_
import os

from .models import GDPRRequest, GDPRConsent, RequestStatusEnum, ConsentStatusEnum

logger = structlog.get_logger("gdpr.notifications")


class GDPRNotificationService:
    """
    Handles email notifications for GDPR events.
    """

    def __init__(
        self,
        session: Session,
        smtp_host: Optional[str] = None,
        smtp_port: int = 587,
        smtp_user: Optional[str] = None,
        smtp_password: Optional[str] = None,
        from_email: str = "gdpr@reviewsignal.ai",
        dpo_email: Optional[str] = None
    ):
        """
        Initialize notification service.

        Args:
            session: SQLAlchemy session
            smtp_host: SMTP server host
            smtp_port: SMTP server port
            smtp_user: SMTP username
            smtp_password: SMTP password
            from_email: Sender email address
            dpo_email: Data Protection Officer email for alerts
        """
        self.session = session
        self.smtp_host = smtp_host or os.getenv("SMTP_HOST", "mailserver.purelymail.com")
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user or os.getenv("SMTP_USER", "team@reviewsignal.ai")
        self.smtp_password = smtp_password or os.getenv("SMTP_PASSWORD")
        self.from_email = from_email
        self.dpo_email = dpo_email or os.getenv("DPO_EMAIL", "team@reviewsignal.ai")
        self.company_name = "ReviewSignal.ai"
        self.support_email = "team@reviewsignal.ai"

    def _send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None
    ) -> bool:
        """
        Send email via SMTP.

        Args:
            to_email: Recipient email
            subject: Email subject
            html_content: HTML body
            text_content: Plain text body (optional)

        Returns:
            True if sent successfully
        """
        if not self.smtp_password:
            logger.warning("smtp_password_not_configured", to=to_email, subject=subject)
            return False

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{self.company_name} GDPR <{self.from_email}>"
            msg["To"] = to_email

            # Plain text version
            if text_content:
                msg.attach(MIMEText(text_content, "plain"))

            # HTML version
            msg.attach(MIMEText(html_content, "html"))

            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.sendmail(self.from_email, to_email, msg.as_string())

            logger.info("email_sent", to=to_email, subject=subject)
            return True

        except Exception as e:
            logger.error("email_send_failed", to=to_email, subject=subject, error=str(e))
            return False

    def notify_request_created(self, request: GDPRRequest) -> bool:
        """
        Send notification when a GDPR request is created.

        Args:
            request: The created request

        Returns:
            True if notification sent
        """
        subject = f"[GDPR] Your {request.request_type.value.replace('_', ' ').title()} Request - #{request.request_id}"

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: #2563eb; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; background: #f9fafb; }}
                .info-box {{ background: white; border: 1px solid #e5e7eb; padding: 15px; margin: 10px 0; border-radius: 5px; }}
                .footer {{ padding: 20px; text-align: center; font-size: 12px; color: #6b7280; }}
                .highlight {{ color: #2563eb; font-weight: bold; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>GDPR Request Confirmation</h1>
                </div>
                <div class="content">
                    <p>Dear Data Subject,</p>
                    <p>We have received your GDPR request. Below are the details:</p>

                    <div class="info-box">
                        <p><strong>Request ID:</strong> <span class="highlight">#{request.request_id}</span></p>
                        <p><strong>Request Type:</strong> {request.request_type.value.replace('_', ' ').title()}</p>
                        <p><strong>Email:</strong> {request.subject_email}</p>
                        <p><strong>Submitted:</strong> {request.created_at.strftime('%Y-%m-%d %H:%M UTC') if request.created_at else 'N/A'}</p>
                        <p><strong>Deadline:</strong> {request.deadline_at.strftime('%Y-%m-%d %H:%M UTC') if request.deadline_at else 'N/A'}</p>
                    </div>

                    <p>Under GDPR Article 12, we are required to respond to your request within <strong>30 days</strong>.</p>
                    <p>We will notify you once your request has been processed.</p>

                    <p>If you have any questions, please contact us at <a href="mailto:{self.support_email}">{self.support_email}</a>.</p>
                </div>
                <div class="footer">
                    <p>&copy; {datetime.now().year} {self.company_name}. All rights reserved.</p>
                    <p>This email was sent regarding your GDPR request.</p>
                </div>
            </div>
        </body>
        </html>
        """

        return self._send_email(request.subject_email, subject, html_content)

    def notify_request_completed(
        self,
        request: GDPRRequest,
        download_url: Optional[str] = None
    ) -> bool:
        """
        Send notification when a GDPR request is completed.

        Args:
            request: The completed request
            download_url: URL to download exported data (if applicable)

        Returns:
            True if notification sent
        """
        subject = f"[GDPR] Your {request.request_type.value.replace('_', ' ').title()} Request Completed - #{request.request_id}"

        download_section = ""
        if download_url:
            download_section = f"""
            <div class="info-box" style="background: #ecfdf5; border-color: #10b981;">
                <p><strong>Download Your Data:</strong></p>
                <p><a href="{download_url}" style="color: #10b981;">Click here to download your data</a></p>
                <p><small>This link will expire in 7 days.</small></p>
            </div>
            """

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: #10b981; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; background: #f9fafb; }}
                .info-box {{ background: white; border: 1px solid #e5e7eb; padding: 15px; margin: 10px 0; border-radius: 5px; }}
                .footer {{ padding: 20px; text-align: center; font-size: 12px; color: #6b7280; }}
                .highlight {{ color: #10b981; font-weight: bold; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Request Completed</h1>
                </div>
                <div class="content">
                    <p>Dear Data Subject,</p>
                    <p>Your GDPR request has been <span class="highlight">successfully completed</span>.</p>

                    <div class="info-box">
                        <p><strong>Request ID:</strong> #{request.request_id}</p>
                        <p><strong>Request Type:</strong> {request.request_type.value.replace('_', ' ').title()}</p>
                        <p><strong>Completed:</strong> {request.completed_at.strftime('%Y-%m-%d %H:%M UTC') if request.completed_at else datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</p>
                        <p><strong>Processed By:</strong> {request.processed_by or 'System'}</p>
                    </div>

                    {download_section}

                    <p>If you have any questions about this request, please contact us at <a href="mailto:{self.support_email}">{self.support_email}</a>.</p>
                </div>
                <div class="footer">
                    <p>&copy; {datetime.now().year} {self.company_name}. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """

        return self._send_email(request.subject_email, subject, html_content)

    def notify_request_rejected(
        self,
        request: GDPRRequest,
        reason: str
    ) -> bool:
        """
        Send notification when a GDPR request is rejected.

        Args:
            request: The rejected request
            reason: Rejection reason

        Returns:
            True if notification sent
        """
        subject = f"[GDPR] Update on Your Request - #{request.request_id}"

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: #ef4444; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; background: #f9fafb; }}
                .info-box {{ background: white; border: 1px solid #e5e7eb; padding: 15px; margin: 10px 0; border-radius: 5px; }}
                .reason-box {{ background: #fef2f2; border: 1px solid #fecaca; padding: 15px; margin: 10px 0; border-radius: 5px; }}
                .footer {{ padding: 20px; text-align: center; font-size: 12px; color: #6b7280; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Request Update</h1>
                </div>
                <div class="content">
                    <p>Dear Data Subject,</p>
                    <p>We regret to inform you that we were unable to fulfill your GDPR request.</p>

                    <div class="info-box">
                        <p><strong>Request ID:</strong> #{request.request_id}</p>
                        <p><strong>Request Type:</strong> {request.request_type.value.replace('_', ' ').title()}</p>
                    </div>

                    <div class="reason-box">
                        <p><strong>Reason:</strong></p>
                        <p>{reason}</p>
                    </div>

                    <p>Under GDPR, you have the right to lodge a complaint with your local supervisory authority if you believe your rights have not been respected.</p>

                    <p>If you have questions or believe this decision was made in error, please contact us at <a href="mailto:{self.support_email}">{self.support_email}</a>.</p>
                </div>
                <div class="footer">
                    <p>&copy; {datetime.now().year} {self.company_name}. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """

        return self._send_email(request.subject_email, subject, html_content)

    def notify_overdue_requests(self) -> Dict[str, Any]:
        """
        Send alert to DPO about overdue requests.

        Returns:
            Summary of notifications sent
        """
        now = datetime.utcnow()

        overdue_requests = self.session.query(GDPRRequest).filter(
            and_(
                GDPRRequest.status.in_([RequestStatusEnum.pending, RequestStatusEnum.in_progress]),
                GDPRRequest.deadline_at < now
            )
        ).all()

        if not overdue_requests:
            return {"overdue_count": 0, "notification_sent": False}

        # Build alert email
        subject = f"[GDPR ALERT] {len(overdue_requests)} Overdue Request(s) Require Attention"

        requests_html = ""
        for req in overdue_requests:
            days_overdue = (now - req.deadline_at.replace(tzinfo=None) if req.deadline_at.tzinfo else req.deadline_at).days
            requests_html += f"""
            <tr>
                <td>#{req.request_id}</td>
                <td>{req.subject_email}</td>
                <td>{req.request_type.value}</td>
                <td style="color: #ef4444; font-weight: bold;">{days_overdue} days</td>
                <td>{req.status.value}</td>
            </tr>
            """

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 700px; margin: 0 auto; padding: 20px; }}
                .header {{ background: #ef4444; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; background: #f9fafb; }}
                .alert-box {{ background: #fef2f2; border: 2px solid #ef4444; padding: 15px; margin: 10px 0; border-radius: 5px; }}
                table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
                th, td {{ padding: 10px; border: 1px solid #e5e7eb; text-align: left; }}
                th {{ background: #f3f4f6; }}
                .footer {{ padding: 20px; text-align: center; font-size: 12px; color: #6b7280; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>GDPR Compliance Alert</h1>
                </div>
                <div class="content">
                    <div class="alert-box">
                        <p><strong>URGENT:</strong> The following GDPR requests are past their 30-day deadline and require immediate attention.</p>
                    </div>

                    <table>
                        <thead>
                            <tr>
                                <th>Request ID</th>
                                <th>Email</th>
                                <th>Type</th>
                                <th>Overdue</th>
                                <th>Status</th>
                            </tr>
                        </thead>
                        <tbody>
                            {requests_html}
                        </tbody>
                    </table>

                    <p><strong>Action Required:</strong> Please process these requests immediately to ensure GDPR compliance.</p>
                    <p>Non-compliance may result in supervisory authority penalties.</p>
                </div>
                <div class="footer">
                    <p>This is an automated alert from the GDPR Compliance System.</p>
                    <p>Generated at: {now.strftime('%Y-%m-%d %H:%M UTC')}</p>
                </div>
            </div>
        </body>
        </html>
        """

        sent = self._send_email(self.dpo_email, subject, html_content)

        logger.warning(
            "overdue_requests_alert",
            overdue_count=len(overdue_requests),
            dpo_notified=sent
        )

        return {
            "overdue_count": len(overdue_requests),
            "notification_sent": sent,
            "requests": [r.to_dict() for r in overdue_requests]
        }

    def notify_consent_expiring_soon(self, days_before: int = 30) -> Dict[str, Any]:
        """
        Notify subjects whose consent is expiring soon.

        Args:
            days_before: Days before expiration to notify

        Returns:
            Summary of notifications sent
        """
        now = datetime.utcnow()
        expiry_threshold = now + timedelta(days=days_before)

        expiring_consents = self.session.query(GDPRConsent).filter(
            and_(
                GDPRConsent.status == ConsentStatusEnum.granted,
                GDPRConsent.expires_at.isnot(None),
                GDPRConsent.expires_at > now,
                GDPRConsent.expires_at <= expiry_threshold
            )
        ).all()

        sent_count = 0
        for consent in expiring_consents:
            subject = f"[GDPR] Your Consent is Expiring Soon - {consent.consent_type.value.title()}"

            days_until = (consent.expires_at.replace(tzinfo=None) - now).days if consent.expires_at else 0

            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                    .header {{ background: #f59e0b; color: white; padding: 20px; text-align: center; }}
                    .content {{ padding: 20px; background: #f9fafb; }}
                    .info-box {{ background: white; border: 1px solid #e5e7eb; padding: 15px; margin: 10px 0; border-radius: 5px; }}
                    .btn {{ display: inline-block; background: #2563eb; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; margin: 10px 0; }}
                    .footer {{ padding: 20px; text-align: center; font-size: 12px; color: #6b7280; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>Consent Expiring Soon</h1>
                    </div>
                    <div class="content">
                        <p>Dear {consent.subject_email},</p>
                        <p>Your consent for <strong>{consent.consent_type.value.replace('_', ' ')}</strong> will expire in <strong>{days_until} days</strong>.</p>

                        <div class="info-box">
                            <p><strong>Consent Type:</strong> {consent.consent_type.value.replace('_', ' ').title()}</p>
                            <p><strong>Expires:</strong> {consent.expires_at.strftime('%Y-%m-%d') if consent.expires_at else 'N/A'}</p>
                        </div>

                        <p>If you wish to continue receiving our services, please renew your consent before it expires.</p>

                        <p>If you do not wish to renew, no action is needed and your consent will automatically expire.</p>

                        <p>Questions? Contact us at <a href="mailto:{self.support_email}">{self.support_email}</a>.</p>
                    </div>
                    <div class="footer">
                        <p>&copy; {datetime.now().year} {self.company_name}. All rights reserved.</p>
                    </div>
                </div>
            </body>
            </html>
            """

            if self._send_email(consent.subject_email, subject, html_content):
                sent_count += 1

        logger.info(
            "consent_expiry_notifications_sent",
            total_expiring=len(expiring_consents),
            sent_count=sent_count
        )

        return {
            "expiring_count": len(expiring_consents),
            "notifications_sent": sent_count
        }
