"""
ReviewSignal Compliance Module
Ensures legal compliance for alternative data platform

Includes:
- audit: Audit logging for all operations
- data_sourcing: Data source compliance
- gdpr: GDPR compliance (Art. 15-22)
"""

from .gdpr import (
    GDPRService,
    DataExporter,
    DataEraser,
    ConsentManager,
    RetentionManager,
    GDPRAuditLogger,
    log_gdpr_action
)

__version__ = "1.1.0"

__all__ = [
    'GDPRService',
    'DataExporter',
    'DataEraser',
    'ConsentManager',
    'RetentionManager',
    'GDPRAuditLogger',
    'log_gdpr_action',
]
