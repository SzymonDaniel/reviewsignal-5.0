"""
GDPR Data Rectifier
ReviewSignal 5.0

Data rectification support (Art. 16 GDPR).
Allows data subjects to correct inaccurate personal data.
"""

import structlog
from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import text, and_

from .models import AuditActionEnum
from .gdpr_audit import GDPRAuditLogger

logger = structlog.get_logger("gdpr.rectifier")


class DataRectifier:
    """
    Handles data rectification requests (Art. 16 GDPR).
    """

    # Tables containing personal data that can be rectified
    RECTIFIABLE_TABLES = {
        "leads": {
            "email_column": "email",
            "rectifiable_fields": [
                "name", "first_name", "last_name", "title", "company",
                "phone", "linkedin_url", "city", "country", "address"
            ]
        },
        "users": {
            "email_column": "email",
            "rectifiable_fields": [
                "full_name", "first_name", "last_name", "phone", "company_name",
                "job_title", "address", "city", "country", "timezone"
            ]
        },
        "gdpr_consents": {
            "email_column": "subject_email",
            "rectifiable_fields": []  # Email only, no other PII
        }
    }

    def __init__(self, session: Session):
        """
        Initialize Data Rectifier.

        Args:
            session: SQLAlchemy session
        """
        self.session = session
        self.audit_logger = GDPRAuditLogger(session)

    def get_rectifiable_fields(self, email: str) -> Dict[str, Any]:
        """
        Get all rectifiable data for a subject.

        Args:
            email: Subject's email

        Returns:
            Dict with current data by table
        """
        email = email.lower().strip()
        result = {"email": email, "tables": {}}

        for table_name, config in self.RECTIFIABLE_TABLES.items():
            email_col = config["email_column"]
            fields = config["rectifiable_fields"]

            if not fields:
                continue

            fields_sql = ", ".join(fields)

            try:
                query = text(f"""
                    SELECT {fields_sql}
                    FROM {table_name}
                    WHERE LOWER({email_col}) = :email
                    LIMIT 1
                """)
                row = self.session.execute(query, {"email": email}).fetchone()

                if row:
                    result["tables"][table_name] = {
                        "fields": {
                            field: getattr(row, field, None)
                            for field in fields
                        },
                        "rectifiable": True
                    }
            except Exception as e:
                logger.warning(
                    "rectifiable_fields_query_failed",
                    table=table_name,
                    error=str(e)
                )

        return result

    def rectify_data(
        self,
        email: str,
        rectifications: Dict[str, Dict[str, Any]],
        performed_by: Optional[str] = None,
        ip_address: Optional[str] = None,
        request_id: Optional[int] = None,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Rectify personal data across tables.

        Args:
            email: Subject's email
            rectifications: Dict of {table_name: {field: new_value}}
            performed_by: User performing rectification
            ip_address: Client IP for audit
            request_id: Associated GDPR request ID
            dry_run: If True, only preview changes

        Returns:
            Summary of rectifications
        """
        email = email.lower().strip()
        results = {
            "email": email,
            "dry_run": dry_run,
            "tables": {},
            "total_fields_updated": 0,
            "errors": []
        }

        for table_name, field_updates in rectifications.items():
            if table_name not in self.RECTIFIABLE_TABLES:
                results["errors"].append(f"Table '{table_name}' is not rectifiable")
                continue

            config = self.RECTIFIABLE_TABLES[table_name]
            allowed_fields = config["rectifiable_fields"]
            email_col = config["email_column"]

            # Validate fields
            invalid_fields = [f for f in field_updates.keys() if f not in allowed_fields]
            if invalid_fields:
                results["errors"].append(
                    f"Fields {invalid_fields} are not rectifiable in '{table_name}'"
                )
                continue

            # Get current values for audit
            old_values = {}
            try:
                fields_to_check = list(field_updates.keys())
                fields_sql = ", ".join(fields_to_check)
                query = text(f"""
                    SELECT {fields_sql}
                    FROM {table_name}
                    WHERE LOWER({email_col}) = :email
                """)
                rows = self.session.execute(query, {"email": email}).fetchall()

                if rows:
                    old_values = {
                        field: getattr(rows[0], field, None)
                        for field in fields_to_check
                    }
            except Exception as e:
                results["errors"].append(f"Failed to read current values from '{table_name}': {str(e)}")
                continue

            if not old_values:
                results["tables"][table_name] = {
                    "status": "no_records_found",
                    "updated": 0
                }
                continue

            if dry_run:
                results["tables"][table_name] = {
                    "status": "preview",
                    "current_values": old_values,
                    "new_values": field_updates,
                    "would_update": len(field_updates)
                }
                continue

            # Perform update
            try:
                set_clauses = []
                params = {"email": email}

                for field, value in field_updates.items():
                    set_clauses.append(f"{field} = :{field}")
                    params[field] = value

                update_sql = text(f"""
                    UPDATE {table_name}
                    SET {", ".join(set_clauses)}, updated_at = NOW()
                    WHERE LOWER({email_col}) = :email
                """)

                result = self.session.execute(update_sql, params)
                updated_count = result.rowcount

                results["tables"][table_name] = {
                    "status": "updated",
                    "old_values": old_values,
                    "new_values": field_updates,
                    "records_updated": updated_count
                }
                results["total_fields_updated"] += len(field_updates)

                logger.info(
                    "data_rectified",
                    email=email,
                    table=table_name,
                    fields=list(field_updates.keys()),
                    records=updated_count
                )

            except Exception as e:
                results["errors"].append(f"Failed to update '{table_name}': {str(e)}")
                logger.error(
                    "rectification_failed",
                    email=email,
                    table=table_name,
                    error=str(e)
                )

        # Commit if not dry run
        if not dry_run and results["total_fields_updated"] > 0:
            self.session.commit()

            # Audit log
            self.audit_logger.log(
                action=AuditActionEnum.data_accessed,  # Using closest available action
                subject_email=email,
                affected_tables=list(rectifications.keys()),
                affected_records_count=results["total_fields_updated"],
                performed_by=performed_by,
                ip_address=ip_address,
                request_id=request_id,
                details={
                    "operation": "rectification",
                    "rectifications": {
                        table: {
                            "old": results["tables"].get(table, {}).get("old_values"),
                            "new": results["tables"].get(table, {}).get("new_values")
                        }
                        for table in rectifications.keys()
                        if table in results["tables"]
                    }
                }
            )

        return results

    def rectify_email(
        self,
        old_email: str,
        new_email: str,
        performed_by: Optional[str] = None,
        ip_address: Optional[str] = None,
        request_id: Optional[int] = None,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Rectify email address across all tables.

        Args:
            old_email: Current email
            new_email: New email address
            performed_by: User performing rectification
            ip_address: Client IP for audit
            request_id: Associated GDPR request ID
            dry_run: If True, only preview changes

        Returns:
            Summary of email changes
        """
        old_email = old_email.lower().strip()
        new_email = new_email.lower().strip()

        if old_email == new_email:
            return {"error": "Old and new email are the same"}

        results = {
            "old_email": old_email,
            "new_email": new_email,
            "dry_run": dry_run,
            "tables": {},
            "total_updated": 0,
            "errors": []
        }

        for table_name, config in self.RECTIFIABLE_TABLES.items():
            email_col = config["email_column"]

            try:
                # Count records to update
                count_query = text(f"""
                    SELECT COUNT(*) as cnt
                    FROM {table_name}
                    WHERE LOWER({email_col}) = :old_email
                """)
                count_result = self.session.execute(count_query, {"old_email": old_email}).fetchone()
                record_count = count_result.cnt if count_result else 0

                if record_count == 0:
                    results["tables"][table_name] = {
                        "status": "no_records",
                        "count": 0
                    }
                    continue

                if dry_run:
                    results["tables"][table_name] = {
                        "status": "preview",
                        "would_update": record_count
                    }
                    continue

                # Update email
                update_query = text(f"""
                    UPDATE {table_name}
                    SET {email_col} = :new_email, updated_at = NOW()
                    WHERE LOWER({email_col}) = :old_email
                """)
                self.session.execute(update_query, {
                    "old_email": old_email,
                    "new_email": new_email
                })

                results["tables"][table_name] = {
                    "status": "updated",
                    "count": record_count
                }
                results["total_updated"] += record_count

            except Exception as e:
                results["errors"].append(f"Failed to update '{table_name}': {str(e)}")
                logger.error(
                    "email_rectification_failed",
                    table=table_name,
                    error=str(e)
                )

        # Commit if not dry run
        if not dry_run and results["total_updated"] > 0:
            self.session.commit()

            # Audit log
            self.audit_logger.log(
                action=AuditActionEnum.data_accessed,
                subject_email=new_email,
                affected_tables=list(self.RECTIFIABLE_TABLES.keys()),
                affected_records_count=results["total_updated"],
                performed_by=performed_by,
                ip_address=ip_address,
                request_id=request_id,
                details={
                    "operation": "email_rectification",
                    "old_email": old_email,
                    "new_email": new_email
                }
            )

            logger.info(
                "email_rectified",
                old_email=old_email,
                new_email=new_email,
                total_records=results["total_updated"]
            )

        return results

    def preview_rectification(self, email: str) -> Dict[str, Any]:
        """
        Preview what data can be rectified for a subject.

        Args:
            email: Subject's email

        Returns:
            Preview of rectifiable data
        """
        data = self.get_rectifiable_fields(email)
        data["allowed_fields_by_table"] = {
            table: config["rectifiable_fields"]
            for table, config in self.RECTIFIABLE_TABLES.items()
            if config["rectifiable_fields"]
        }
        return data
