"""Business logic for alert rules."""

from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from src.db.models import AlertRule


class AlertRulesService:
    """Handles CRUD operations for user alert rules."""

    def __init__(self, db: Session):
        self.db = db

    def list_alerts(self, user_id: UUID) -> list[dict[str, Any]]:
        alerts = (
            self.db.query(AlertRule)
            .filter(AlertRule.user_id == user_id)
            .order_by(AlertRule.created_at.desc())
            .all()
        )
        return [
            {
                "id": str(a.id),
                "user_id": str(a.user_id),
                "name": a.name,
                "condition_type": a.condition_type,
                "condition_config": a.condition_config or {},
                "is_active": a.is_active,
                "last_triggered_at": a.last_triggered_at.isoformat() if a.last_triggered_at else None,
                "created_at": a.created_at.isoformat(),
            }
            for a in alerts
        ]

    def create_alert(
        self,
        user_id: UUID,
        name: str,
        condition_type: str,
        condition_config: dict[str, Any],
        is_active: bool,
    ) -> dict[str, Any]:
        alert = AlertRule(
            user_id=user_id,
            name=name,
            condition_type=condition_type,
            condition_config=condition_config,
            is_active=is_active,
        )
        self.db.add(alert)
        self.db.commit()
        self.db.refresh(alert)
        return {
            "id": str(alert.id),
            "name": alert.name,
            "condition_type": alert.condition_type,
            "is_active": alert.is_active,
            "created_at": alert.created_at.isoformat(),
        }

    def delete_alert(self, alert_id: UUID) -> None:
        alert = self.db.query(AlertRule).filter(AlertRule.id == alert_id).first()
        if not alert:
            raise HTTPException(status_code=404, detail="Alert not found")
        self.db.delete(alert)
        self.db.commit()
