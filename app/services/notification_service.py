from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models.user import User
from app.models.preference import UserPreference
from app.firebase.notifications import send_push_notification


def notify_matching_users(db: Session, incident):
    """
    Incident ki category/area se match karne wale users ko dhoondh kar
    unhe push notification bhejta hai (agar unke paas FCM token hai).
    """
    matching_prefs = (
        db.query(UserPreference)
        .filter(
            or_(
                UserPreference.preferred_categories.any(incident.category),
                UserPreference.preferred_areas.any(incident.area_name)
            )
        )
        .all()
    )

    sent_count = 0

    for pref in matching_prefs:
        user = db.query(User).filter(User.id == pref.user_id).first()

        if user and user.fcm_token:
            title = f"{incident.priority_tier or 'Alert'}: {incident.category}"
            body = incident.description[:100]

            send_push_notification(user.fcm_token, title, body)
            sent_count += 1

    return sent_count