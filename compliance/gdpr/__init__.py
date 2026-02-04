"""
GDPR Compliance Module
ReviewSignal 5.0

Implements GDPR requirements:
- Art. 7: Consent Management
- Art. 15: Right of Access
- Art. 16: Right to Rectification
- Art. 17: Right to Erasure
- Art. 18: Right to Restriction of Processing
- Art. 20: Right to Data Portability
- Art. 30: Records of Processing Activities
"""

from .models import GDPRConsent, GDPRRequest, GDPRAuditLog, DataRetentionPolicy
from .gdpr_service import GDPRService
from .data_exporter import DataExporter
from .data_eraser import DataEraser
from .data_rectifier import DataRectifier
from .consent_manager import ConsentManager
from .retention_manager import RetentionManager
from .processing_restriction import ProcessingRestriction, ProcessingRestrictionManager, is_processing_allowed
from .gdpr_audit import GDPRAuditLogger, log_gdpr_action
from .gdpr_notifications import GDPRNotificationService
from .gdpr_webhooks import GDPRWebhookDispatcher, WebhookEventType

__all__ = [
    # Models
    'GDPRConsent',
    'GDPRRequest',
    'GDPRAuditLog',
    'DataRetentionPolicy',
    'ProcessingRestriction',
    # Services
    'GDPRService',
    'DataExporter',
    'DataEraser',
    'DataRectifier',
    'ConsentManager',
    'RetentionManager',
    'ProcessingRestrictionManager',
    'GDPRAuditLogger',
    'GDPRNotificationService',
    'GDPRWebhookDispatcher',
    # Enums
    'WebhookEventType',
    # Utilities
    'log_gdpr_action',
    'is_processing_allowed',
]

__version__ = '2.0.0'
