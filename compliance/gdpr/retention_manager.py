"""
GDPR Retention Manager
ReviewSignal 5.0

Manages automatic data retention and cleanup based on configured policies.
"""

import structlog
from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import text, and_

from .models import DataRetentionPolicy, RetentionActionEnum, AuditActionEnum
from .gdpr_audit import GDPRAuditLogger
from .data_eraser import DataEraser

logger = structlog.get_logger("gdpr.retention")


class RetentionManager:
    """
    Manages data retention policies and automatic cleanup.
    """

    def __init__(self, session: Session):
        """
        Initialize Retention Manager.

        Args:
            session: SQLAlchemy session
        """
        self.session = session
        self.audit_logger = GDPRAuditLogger(session)
        self.data_eraser = DataEraser(session)

    def get_policies(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """
        Get all retention policies.

        Args:
            active_only: If True, only return active policies

        Returns:
            List of policy dicts
        """
        query = self.session.query(DataRetentionPolicy)
        if active_only:
            query = query.filter(DataRetentionPolicy.is_active == True)

        policies = query.all()
        return [p.to_dict() for p in policies]

    def get_policy(self, table_name: str) -> Optional[Dict[str, Any]]:
        """
        Get retention policy for a specific table.

        Args:
            table_name: Name of the table

        Returns:
            Policy dict or None
        """
        policy = self.session.query(DataRetentionPolicy).filter(
            DataRetentionPolicy.table_name == table_name
        ).first()

        return policy.to_dict() if policy else None

    def create_policy(
        self,
        table_name: str,
        retention_days: int,
        action: RetentionActionEnum = RetentionActionEnum.delete,
        condition_column: Optional[str] = None,
        condition_value: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new retention policy.

        Args:
            table_name: Name of the table
            retention_days: Days to retain data
            action: Action to take (delete/anonymize/archive)
            condition_column: Column to filter on
            condition_value: Value to filter by

        Returns:
            Created policy dict
        """
        # Check if policy already exists
        existing = self.session.query(DataRetentionPolicy).filter(
            DataRetentionPolicy.table_name == table_name
        ).first()

        if existing:
            raise ValueError(f"Policy already exists for table: {table_name}")

        policy = DataRetentionPolicy(
            table_name=table_name,
            retention_days=retention_days,
            action=action,
            condition_column=condition_column,
            condition_value=condition_value,
            is_active=True
        )

        self.session.add(policy)
        self.session.commit()

        # Audit log
        self.audit_logger.log(
            action=AuditActionEnum.policy_updated,
            affected_tables=[table_name],
            performed_by="system",
            details={
                "policy_action": "created",
                "retention_days": retention_days,
                "action": action.value
            }
        )

        logger.info(
            "retention_policy_created",
            table=table_name,
            retention_days=retention_days,
            action=action.value
        )

        return policy.to_dict()

    def update_policy(
        self,
        table_name: str,
        retention_days: Optional[int] = None,
        action: Optional[RetentionActionEnum] = None,
        condition_column: Optional[str] = None,
        condition_value: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        Update an existing retention policy.

        Args:
            table_name: Name of the table
            retention_days: New retention period
            action: New action
            condition_column: New condition column
            condition_value: New condition value
            is_active: Enable/disable policy

        Returns:
            Updated policy dict
        """
        policy = self.session.query(DataRetentionPolicy).filter(
            DataRetentionPolicy.table_name == table_name
        ).first()

        if not policy:
            raise ValueError(f"No policy found for table: {table_name}")

        if retention_days is not None:
            policy.retention_days = retention_days
        if action is not None:
            policy.action = action
        if condition_column is not None:
            policy.condition_column = condition_column
        if condition_value is not None:
            policy.condition_value = condition_value
        if is_active is not None:
            policy.is_active = is_active

        self.session.commit()

        # Audit log
        self.audit_logger.log(
            action=AuditActionEnum.policy_updated,
            affected_tables=[table_name],
            performed_by="system",
            details={"policy_action": "updated"}
        )

        logger.info("retention_policy_updated", table=table_name)

        return policy.to_dict()

    def delete_policy(self, table_name: str) -> bool:
        """
        Delete a retention policy.

        Args:
            table_name: Name of the table

        Returns:
            True if deleted, False if not found
        """
        policy = self.session.query(DataRetentionPolicy).filter(
            DataRetentionPolicy.table_name == table_name
        ).first()

        if not policy:
            return False

        self.session.delete(policy)
        self.session.commit()

        logger.info("retention_policy_deleted", table=table_name)

        return True

    def run_cleanup(
        self,
        table_name: Optional[str] = None,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Run retention cleanup for specified table or all tables.

        Args:
            table_name: Specific table to clean, or None for all
            dry_run: If True, only preview what would be cleaned

        Returns:
            Dict with cleanup results
        """
        results = {
            "timestamp": datetime.utcnow().isoformat(),
            "dry_run": dry_run,
            "tables": {},
            "total_affected": 0,
            "errors": []
        }

        # Get policies to process
        query = self.session.query(DataRetentionPolicy).filter(
            DataRetentionPolicy.is_active == True
        )
        if table_name:
            query = query.filter(DataRetentionPolicy.table_name == table_name)

        policies = query.all()

        for policy in policies:
            try:
                table_result = self._cleanup_table(policy, dry_run)
                results["tables"][policy.table_name] = table_result
                results["total_affected"] += table_result.get("count", 0)

                # Update policy last run info if not dry run
                if not dry_run and table_result.get("count", 0) > 0:
                    policy.last_run_at = datetime.utcnow()
                    policy.last_run_count = table_result["count"]

            except Exception as e:
                error_msg = f"Error cleaning {policy.table_name}: {str(e)}"
                results["errors"].append(error_msg)
                logger.error("cleanup_error", table=policy.table_name, error=str(e))

        if not dry_run:
            self.session.commit()

        logger.info(
            "retention_cleanup_complete" if not dry_run else "retention_cleanup_preview",
            total_affected=results["total_affected"],
            tables=list(results["tables"].keys())
        )

        return results

    def _cleanup_table(
        self,
        policy: DataRetentionPolicy,
        dry_run: bool
    ) -> Dict[str, Any]:
        """
        Clean up a single table based on policy.

        Args:
            policy: Retention policy
            dry_run: Whether to only preview

        Returns:
            Dict with cleanup results for this table
        """
        table_name = policy.table_name
        retention_days = policy.retention_days
        action = policy.action

        # Check if table exists
        check_query = text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = :table_name
            )
        """)
        result = self.session.execute(check_query, {"table_name": table_name})
        if not result.scalar():
            return {"count": 0, "reason": "table_not_found"}

        # Build WHERE clause
        where_conditions = [f"created_at < NOW() - INTERVAL '{retention_days} days'"]

        if policy.condition_column and policy.condition_value:
            where_conditions.append(f"{policy.condition_column} = '{policy.condition_value}'")

        where_clause = " AND ".join(where_conditions)

        # Count records to be affected
        count_query = text(f"SELECT COUNT(*) FROM {table_name} WHERE {where_clause}")
        result = self.session.execute(count_query)
        count = result.scalar()

        if count == 0:
            return {"count": 0, "action": action.value, "reason": "no_records_match"}

        if dry_run:
            return {
                "count": count,
                "action": action.value,
                "would_affect": count,
                "retention_days": retention_days
            }

        # Perform cleanup based on action
        if action == RetentionActionEnum.delete:
            delete_query = text(f"DELETE FROM {table_name} WHERE {where_clause}")
            self.session.execute(delete_query)

        elif action == RetentionActionEnum.anonymize:
            # Get PII columns from DataEraser config
            if table_name in self.data_eraser.PII_TABLES:
                pii_columns = self.data_eraser.PII_TABLES[table_name].get("pii_columns", [])
                if pii_columns:
                    set_clauses = [f"{col} = NULL" for col in pii_columns]
                    set_clause = ", ".join(set_clauses)
                    update_query = text(f"UPDATE {table_name} SET {set_clause} WHERE {where_clause}")
                    self.session.execute(update_query)

        elif action == RetentionActionEnum.archive:
            # Archive to separate table (create if not exists)
            archive_table = f"{table_name}_archive"
            self._ensure_archive_table(table_name, archive_table)

            # Move records to archive
            insert_query = text(f"""
                INSERT INTO {archive_table}
                SELECT *, NOW() as archived_at FROM {table_name}
                WHERE {where_clause}
            """)
            self.session.execute(insert_query)

            # Delete from main table
            delete_query = text(f"DELETE FROM {table_name} WHERE {where_clause}")
            self.session.execute(delete_query)

        # Audit log
        self.audit_logger.log_retention_cleanup(
            table_name=table_name,
            record_count=count,
            action=action.value
        )

        return {
            "count": count,
            "action": action.value,
            "retention_days": retention_days
        }

    def _ensure_archive_table(self, source_table: str, archive_table: str) -> None:
        """
        Ensure archive table exists with same structure plus archived_at column.

        Args:
            source_table: Source table name
            archive_table: Archive table name
        """
        check_query = text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = :table_name
            )
        """)
        result = self.session.execute(check_query, {"table_name": archive_table})

        if not result.scalar():
            create_query = text(f"""
                CREATE TABLE {archive_table} AS
                SELECT *, NOW() as archived_at FROM {source_table}
                WHERE false
            """)
            self.session.execute(create_query)

    def get_cleanup_preview(
        self,
        table_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Preview what would be cleaned up.

        Args:
            table_name: Specific table or None for all

        Returns:
            Preview results
        """
        return self.run_cleanup(table_name=table_name, dry_run=True)

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get retention statistics.

        Returns:
            Dict with statistics
        """
        policies = self.session.query(DataRetentionPolicy).all()

        stats = {
            "total_policies": len(policies),
            "active_policies": sum(1 for p in policies if p.is_active),
            "policies": []
        }

        for policy in policies:
            policy_stat = policy.to_dict()

            # Get current count of records that would be affected
            if policy.is_active:
                preview = self._cleanup_table(policy, dry_run=True)
                policy_stat["pending_cleanup"] = preview.get("count", 0)
            else:
                policy_stat["pending_cleanup"] = 0

            stats["policies"].append(policy_stat)

        return stats
