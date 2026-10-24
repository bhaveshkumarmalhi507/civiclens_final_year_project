from sqlalchemy import func, cast
from sqlalchemy.orm import Session
from geoalchemy2 import Geography
from geoalchemy2.functions import ST_DWithin

from app.models.incident import Incident
from app.services.priority_engine import calculate_priority_score
from app.services.notification_service import notify_matching_users

RADIUS_METERS = 500
VERIFY_THRESHOLD = 3
DUMMY_SEVERITY = 50   # TODO: Asadullah ka real NLP severity yahan aayega


def validate_and_rank(db: Session, new_incident: Incident, point):
    # Same category + 500m ke andar wali reports
    nearby = (
        Incident.category == new_incident.category,
        ST_DWithin(
            cast(Incident.location, Geography),
            cast(point, Geography),
            RADIUS_METERS,
        ),
    )

    distinct_users = (
        db.query(func.count(func.distinct(Incident.user_id)))
        .filter(*nearby)
        .scalar()
    )

    if distinct_users < VERIFY_THRESHOLD:
        return

    matching = db.query(Incident).filter(*nearby).all()

    score, tier = calculate_priority_score(
        severity_score=DUMMY_SEVERITY,
        area_report_count=len(matching),
        confirmation_count=distinct_users,
        created_at=new_incident.created_at,
    )

    for inc in matching:
        # Resolved/In Progress ko wapas Verified na karo
        if inc.status in ("Submitted", "Under Review"):
            inc.status = "Verified"
        inc.priority_score = score
        inc.priority_tier = tier

    db.commit()
    db.refresh(new_incident)

    if tier == "BREAKING":
        notify_matching_users(db, new_incident)