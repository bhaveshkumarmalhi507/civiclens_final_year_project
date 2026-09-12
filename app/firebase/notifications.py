from firebase_admin import messaging


def send_push_notification(token: str, title: str, body: str):
    message = messaging.Message(
        notification=messaging.Notification(
            title=title,
            body=body
        ),
        token=token
    )

    try:
        response = messaging.send(message)
        return response
    except Exception as e:
        print(f"[FCM Error]: {e}")
        return None