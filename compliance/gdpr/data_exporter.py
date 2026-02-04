"""
GDPR Data Exporter
ReviewSignal 5.0

Exports personal data for data subjects (Art. 20 GDPR - Right to Data Portability).
Supports JSON and CSV formats.
"""

import structlog
import json
import csv
import os
import hashlib
from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import text
from pathlib import Path

from .models import AuditActionEnum
from .gdpr_audit import GDPRAuditLogger

logger = structlog.get_logger("gdpr.exporter")

# Base export directory
EXPORTS_DIR = Path("/home/info_betsim/reviewsignal-5.0/exports")


class DataExporter:
    """
    Exports personal data for GDPR compliance.
    """

    # Tables containing PII and their email column names
    PII_TABLES = {
        "users": {
            "email_column": "email",
            "columns": ["id", "email", "name", "company", "role", "status", "created_at", "last_login"]
        },
        "leads": {
            "email_column": "email",
            "columns": ["id", "email", "name", "title", "company", "linkedin_url", "lead_score", "status", "created_at"]
        },
        "reviews": {
            "email_column": None,  # No direct email, but author_name may be PII
            "author_column": "author_name",
            "columns": ["id", "author_name", "author_url", "rating", "text", "time_posted", "source"]
        },
        "locations": {
            "email_column": None,
            "columns": ["location_id", "name", "address", "phone", "website", "city", "country"]
        },
        "outreach_log": {
            "email_column": "lead_email",
            "columns": ["id", "lead_email", "campaign", "status", "sent_at", "opened_at", "clicked_at"]
        },
        "gdpr_consents": {
            "email_column": "subject_email",
            "columns": ["consent_id", "subject_email", "consent_type", "status", "granted_at", "expires_at"]
        },
        "gdpr_requests": {
            "email_column": "subject_email",
            "columns": ["request_id", "subject_email", "request_type", "status", "created_at", "completed_at"]
        }
    }

    def __init__(self, session: Session):
        """
        Initialize Data Exporter.

        Args:
            session: SQLAlchemy session
        """
        self.session = session
        self.audit_logger = GDPRAuditLogger(session)

        # Ensure exports directory exists
        EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

    def export_data(
        self,
        email: str,
        format: str = "json",
        request_id: Optional[int] = None,
        performed_by: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Export all personal data for a subject.

        Args:
            email: Subject's email
            format: Export format ('json' or 'csv')
            request_id: Related GDPR request ID
            performed_by: User performing export
            ip_address: Client IP for audit

        Returns:
            Dict with export results including file path
        """
        email = email.lower().strip()
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

        # Generate unique filename
        email_hash = hashlib.sha256(email.encode()).hexdigest()[:12]
        filename = f"gdpr_export_{email_hash}_{timestamp}"

        # Collect data from all tables
        export_data = {
            "subject_email": email,
            "export_timestamp": datetime.utcnow().isoformat(),
            "format": format,
            "data": {}
        }

        total_records = 0
        affected_tables = []

        for table_name, config in self.PII_TABLES.items():
            table_data = self._export_table(email, table_name, config)
            if table_data:
                export_data["data"][table_name] = table_data
                total_records += len(table_data)
                affected_tables.append(table_name)

        # Write export file
        if format == "json":
            file_path = EXPORTS_DIR / f"{filename}.json"
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(export_data, f, indent=2, default=str)
        elif format == "csv":
            file_path = EXPORTS_DIR / f"{filename}.csv"
            self._write_csv_export(file_path, export_data)
        else:
            raise ValueError(f"Unsupported export format: {format}")

        file_size = os.path.getsize(file_path)

        # Audit log
        self.audit_logger.log_data_exported(
            subject_email=email,
            tables=affected_tables,
            record_count=total_records,
            file_url=str(file_path),
            request_id=request_id,
            performed_by=performed_by,
            ip_address=ip_address
        )

        logger.info(
            "data_exported",
            email=email,
            format=format,
            total_records=total_records,
            tables=affected_tables,
            file_path=str(file_path)
        )

        return {
            "success": True,
            "email": email,
            "format": format,
            "file_path": str(file_path),
            "file_size": file_size,
            "total_records": total_records,
            "tables_exported": affected_tables,
            "export_timestamp": export_data["export_timestamp"]
        }

    def _export_table(
        self,
        email: str,
        table_name: str,
        config: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Export data from a single table.

        Args:
            email: Subject's email
            table_name: Name of table to export
            config: Table configuration

        Returns:
            List of records as dicts
        """
        email_column = config.get("email_column")
        author_column = config.get("author_column")
        columns = config.get("columns", ["*"])

        if not email_column and not author_column:
            return []

        # Check if table exists
        try:
            check_query = text(f"""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = :table_name
                )
            """)
            result = self.session.execute(check_query, {"table_name": table_name})
            if not result.scalar():
                return []
        except Exception:
            return []

        # Build query
        columns_str = ", ".join(columns) if columns != ["*"] else "*"

        if email_column:
            query = text(f"""
                SELECT {columns_str}
                FROM {table_name}
                WHERE LOWER({email_column}) = LOWER(:email)
            """)
        elif author_column:
            # For reviews, search by author name containing email username
            username = email.split("@")[0]
            query = text(f"""
                SELECT {columns_str}
                FROM {table_name}
                WHERE LOWER({author_column}) LIKE LOWER(:pattern)
            """)
            result = self.session.execute(query, {"pattern": f"%{username}%"})
            rows = result.fetchall()
            return [dict(row._mapping) for row in rows]

        try:
            result = self.session.execute(query, {"email": email})
            rows = result.fetchall()
            return [dict(row._mapping) for row in rows]
        except Exception as e:
            logger.warning(f"Failed to export from {table_name}: {e}")
            return []

    def _write_csv_export(
        self,
        file_path: Path,
        export_data: Dict[str, Any]
    ) -> None:
        """
        Write export data to CSV file.

        Args:
            file_path: Path to output file
            export_data: Data to export
        """
        with open(file_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)

            # Write metadata
            writer.writerow(["GDPR Data Export"])
            writer.writerow(["Subject Email", export_data["subject_email"]])
            writer.writerow(["Export Timestamp", export_data["export_timestamp"]])
            writer.writerow([])

            # Write each table's data
            for table_name, records in export_data["data"].items():
                if not records:
                    continue

                writer.writerow([f"=== {table_name.upper()} ==="])
                writer.writerow([])

                # Headers
                headers = list(records[0].keys())
                writer.writerow(headers)

                # Data rows
                for record in records:
                    writer.writerow([str(record.get(h, "")) for h in headers])

                writer.writerow([])

    def preview_export(
        self,
        email: str
    ) -> Dict[str, Any]:
        """
        Preview what data would be exported without creating a file.

        Args:
            email: Subject's email

        Returns:
            Dict with preview of data counts per table
        """
        email = email.lower().strip()

        preview = {
            "email": email,
            "tables": {},
            "total_records": 0
        }

        for table_name, config in self.PII_TABLES.items():
            table_data = self._export_table(email, table_name, config)
            count = len(table_data)
            preview["tables"][table_name] = {
                "record_count": count,
                "sample": table_data[0] if table_data else None
            }
            preview["total_records"] += count

        return preview

    def get_export_file(
        self,
        email: str,
        timestamp: str
    ) -> Optional[Path]:
        """
        Get path to an existing export file.

        Args:
            email: Subject's email
            timestamp: Export timestamp

        Returns:
            Path to file if exists, None otherwise
        """
        email_hash = hashlib.sha256(email.lower().encode()).hexdigest()[:12]

        for ext in ["json", "csv"]:
            file_path = EXPORTS_DIR / f"gdpr_export_{email_hash}_{timestamp}.{ext}"
            if file_path.exists():
                return file_path

        return None

    def cleanup_old_exports(
        self,
        days: int = 7
    ) -> int:
        """
        Remove export files older than specified days.

        Args:
            days: Age threshold in days

        Returns:
            Number of files removed
        """
        import time

        threshold = time.time() - (days * 86400)
        removed = 0

        for file_path in EXPORTS_DIR.glob("gdpr_export_*"):
            if file_path.stat().st_mtime < threshold:
                file_path.unlink()
                removed += 1

        if removed > 0:
            logger.info("old_exports_cleaned", removed=removed)

        return removed
