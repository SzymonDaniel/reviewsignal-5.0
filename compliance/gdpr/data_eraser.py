"""
GDPR Data Eraser
ReviewSignal 5.0

Handles data deletion and anonymization (Art. 17 GDPR - Right to Erasure).
"""

import structlog
import hashlib
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import text

from .models import AuditActionEnum
from .gdpr_audit import GDPRAuditLogger

logger = structlog.get_logger("gdpr.eraser")


class DataEraser:
    """
    Handles data deletion and anonymization for GDPR compliance.
    """

    # Tables and their PII columns for deletion/anonymization
    PII_TABLES = {
        "users": {
            "email_column": "email",
            "pii_columns": ["email", "password_hash", "name", "company"],
            "can_delete": True,
            "cascade_to": ["user_sessions", "api_keys"]
        },
        "leads": {
            "email_column": "email",
            "pii_columns": ["email", "name", "phone", "linkedin_url", "title"],
            "can_delete": True,
            "cascade_to": ["outreach_log"]
        },
        "reviews": {
            "email_column": None,
            "author_column": "author_name",
            "pii_columns": ["author_name", "author_url"],
            "can_delete": False,  # Anonymize instead
            "anonymize_to": {
                "author_name": "Anonymous User",
                "author_url": None
            }
        },
        "locations": {
            "email_column": None,
            "pii_columns": ["phone", "website"],
            "can_delete": False,  # Business data, keep
            "skip": True
        },
        "outreach_log": {
            "email_column": "lead_email",
            "pii_columns": ["lead_email"],
            "can_delete": True,
            "cascade_from": "leads"
        },
        "gdpr_consents": {
            "email_column": "subject_email",
            "pii_columns": [],  # Keep for audit, but anonymize
            "can_delete": False,
            "anonymize_to": {
                "ip_address": None,
                "user_agent": None
            }
        },
        "gdpr_requests": {
            "email_column": "subject_email",
            "pii_columns": [],  # Keep for audit
            "can_delete": False,
            "anonymize_to": {
                "ip_address": None,
                "user_agent": None
            }
        }
    }

    def __init__(self, session: Session):
        """
        Initialize Data Eraser.

        Args:
            session: SQLAlchemy session
        """
        self.session = session
        self.audit_logger = GDPRAuditLogger(session)

    def erase_data(
        self,
        email: str,
        dry_run: bool = True,
        request_id: Optional[int] = None,
        performed_by: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Erase all personal data for a subject.

        Args:
            email: Subject's email
            dry_run: If True, only preview what would be deleted
            request_id: Related GDPR request ID
            performed_by: User performing erasure
            ip_address: Client IP for audit

        Returns:
            Dict with erasure results
        """
        email = email.lower().strip()

        results = {
            "email": email,
            "dry_run": dry_run,
            "timestamp": datetime.utcnow().isoformat(),
            "tables": {},
            "total_deleted": 0,
            "total_anonymized": 0,
            "errors": []
        }

        affected_tables = []

        for table_name, config in self.PII_TABLES.items():
            if config.get("skip"):
                continue

            try:
                table_result = self._process_table(
                    email=email,
                    table_name=table_name,
                    config=config,
                    dry_run=dry_run
                )

                if table_result["count"] > 0:
                    results["tables"][table_name] = table_result
                    affected_tables.append(table_name)

                    if table_result["action"] == "delete":
                        results["total_deleted"] += table_result["count"]
                    else:
                        results["total_anonymized"] += table_result["count"]

            except Exception as e:
                error_msg = f"Error processing {table_name}: {str(e)}"
                results["errors"].append(error_msg)
                logger.error("erase_table_error", table=table_name, error=str(e))

        # Commit if not dry run
        if not dry_run and results["total_deleted"] + results["total_anonymized"] > 0:
            self.session.commit()

            # Audit log
            self.audit_logger.log_data_deleted(
                subject_email=email,
                tables=affected_tables,
                record_count=results["total_deleted"] + results["total_anonymized"],
                request_id=request_id,
                performed_by=performed_by,
                ip_address=ip_address,
                dry_run=False
            )

        logger.info(
            "data_erased" if not dry_run else "data_erase_preview",
            email=email,
            deleted=results["total_deleted"],
            anonymized=results["total_anonymized"],
            tables=affected_tables
        )

        return results

    def _process_table(
        self,
        email: str,
        table_name: str,
        config: Dict[str, Any],
        dry_run: bool
    ) -> Dict[str, Any]:
        """
        Process deletion/anonymization for a single table.

        Args:
            email: Subject's email
            table_name: Name of table
            config: Table configuration
            dry_run: Whether to only preview

        Returns:
            Dict with table processing results
        """
        email_column = config.get("email_column")
        author_column = config.get("author_column")
        can_delete = config.get("can_delete", False)
        anonymize_to = config.get("anonymize_to", {})

        # Check if table exists
        check_query = text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = :table_name
            )
        """)
        result = self.session.execute(check_query, {"table_name": table_name})
        if not result.scalar():
            return {"count": 0, "action": "skip", "reason": "table_not_found"}

        # Count records
        if email_column:
            count_query = text(f"""
                SELECT COUNT(*)
                FROM {table_name}
                WHERE LOWER({email_column}) = LOWER(:email)
            """)
            result = self.session.execute(count_query, {"email": email})
        elif author_column:
            username = email.split("@")[0]
            count_query = text(f"""
                SELECT COUNT(*)
                FROM {table_name}
                WHERE LOWER({author_column}) LIKE LOWER(:pattern)
            """)
            result = self.session.execute(count_query, {"pattern": f"%{username}%"})
        else:
            return {"count": 0, "action": "skip", "reason": "no_identifier"}

        count = result.scalar()

        if count == 0:
            return {"count": 0, "action": "none", "reason": "no_records_found"}

        if dry_run:
            action = "delete" if can_delete else "anonymize"
            return {
                "count": count,
                "action": action,
                "would_affect": count,
                "pii_columns": config.get("pii_columns", [])
            }

        # Perform deletion or anonymization
        if can_delete:
            # Delete records
            if email_column:
                delete_query = text(f"""
                    DELETE FROM {table_name}
                    WHERE LOWER({email_column}) = LOWER(:email)
                """)
                self.session.execute(delete_query, {"email": email})
            return {"count": count, "action": "delete"}
        else:
            # Anonymize records
            return self._anonymize_records(
                email=email,
                table_name=table_name,
                config=config,
                count=count
            )

    def _anonymize_records(
        self,
        email: str,
        table_name: str,
        config: Dict[str, Any],
        count: int
    ) -> Dict[str, Any]:
        """
        Anonymize records in a table.

        Args:
            email: Subject's email
            table_name: Table name
            config: Table configuration
            count: Number of records to anonymize

        Returns:
            Dict with anonymization results
        """
        email_column = config.get("email_column")
        author_column = config.get("author_column")
        anonymize_to = config.get("anonymize_to", {})
        pii_columns = config.get("pii_columns", [])

        # Build SET clause for anonymization
        set_clauses = []

        # Anonymize specified columns
        for col, value in anonymize_to.items():
            if value is None:
                set_clauses.append(f"{col} = NULL")
            else:
                set_clauses.append(f"{col} = '{value}'")

        # Anonymize email column if it's a PII column
        if email_column and email_column in pii_columns:
            anon_email = self._generate_anonymous_email(email)
            set_clauses.append(f"{email_column} = '{anon_email}'")

        if not set_clauses:
            return {"count": count, "action": "skip", "reason": "no_columns_to_anonymize"}

        set_clause = ", ".join(set_clauses)

        if email_column:
            update_query = text(f"""
                UPDATE {table_name}
                SET {set_clause}
                WHERE LOWER({email_column}) = LOWER(:email)
            """)
            self.session.execute(update_query, {"email": email})
        elif author_column:
            username = email.split("@")[0]
            update_query = text(f"""
                UPDATE {table_name}
                SET {set_clause}
                WHERE LOWER({author_column}) LIKE LOWER(:pattern)
            """)
            self.session.execute(update_query, {"pattern": f"%{username}%"})

        return {
            "count": count,
            "action": "anonymize",
            "columns_anonymized": list(anonymize_to.keys()) + ([email_column] if email_column in pii_columns else [])
        }

    def _generate_anonymous_email(self, email: str) -> str:
        """
        Generate anonymized email placeholder.

        Args:
            email: Original email

        Returns:
            Anonymized email
        """
        hash_value = hashlib.sha256(email.encode()).hexdigest()[:8]
        return f"deleted_{hash_value}@anonymized.local"

    def preview_erasure(self, email: str) -> Dict[str, Any]:
        """
        Preview what data would be erased.

        Args:
            email: Subject's email

        Returns:
            Dict with preview of erasure
        """
        return self.erase_data(email=email, dry_run=True)

    def anonymize_old_data(
        self,
        table_name: str,
        age_days: int,
        date_column: str = "created_at"
    ) -> Dict[str, Any]:
        """
        Anonymize data older than specified days.

        Args:
            table_name: Table to process
            age_days: Age threshold in days
            date_column: Column to check for age

        Returns:
            Dict with results
        """
        if table_name not in self.PII_TABLES:
            return {"error": f"Unknown table: {table_name}"}

        config = self.PII_TABLES[table_name]
        pii_columns = config.get("pii_columns", [])

        if not pii_columns:
            return {"count": 0, "reason": "no_pii_columns"}

        # Build anonymization query
        set_clauses = []
        for col in pii_columns:
            set_clauses.append(f"{col} = NULL")

        set_clause = ", ".join(set_clauses)

        query = text(f"""
            UPDATE {table_name}
            SET {set_clause}
            WHERE {date_column} < NOW() - INTERVAL '{age_days} days'
            AND {pii_columns[0]} IS NOT NULL
        """)

        result = self.session.execute(query)
        self.session.commit()

        count = result.rowcount

        if count > 0:
            self.audit_logger.log_data_anonymized(
                subject_email=None,
                tables=[table_name],
                record_count=count,
                performed_by="system"
            )

        logger.info(
            "old_data_anonymized",
            table=table_name,
            count=count,
            age_days=age_days
        )

        return {
            "table": table_name,
            "count": count,
            "age_days": age_days,
            "columns_anonymized": pii_columns
        }
