from datetime import datetime, timezone


def calculate_priority_score(
    severity_score: int,       # 0-100, abhi ke liye dummy/fixed value (Asadullah se aayega)
    area_report_count: int,    # kitne reports isi area/category mein aa chuke hain
    confirmation_count: int,   # kitne distinct users ne confirm kiya (Community Validation wala count)
    created_at: datetime       # incident kab bana, time_sensitivity nikaalne ke liye
) -> tuple[int, str]:
    """
    Priority Score aur uska tier (BREAKING/HIGH/MEDIUM/LOW) calculate karta hai.
    """

    # --- area_report_count ko 0-100 scale pe lao (cap 10 reports = 100%) ---
    area_score = min(area_report_count * 10, 100)

    # --- confirmation_count ko bhi 0-100 scale pe lao (cap 5 confirmations = 100%) ---
    confirmation_score = min(confirmation_count * 20, 100)

    # --- time_sensitivity: jitna naya incident, utna zyada score (1 ghante ke andar = 100) ---
    age_minutes = (datetime.now(timezone.utc) - created_at.replace(tzinfo=timezone.utc)).total_seconds() / 60
    time_score = max(100 - (age_minutes / 60 * 100), 0)   # 60 min ke baad score 0 ho jayega
    time_score = min(time_score, 100)

    # --- Weighted Formula ---
    final_score = (
        (severity_score * 0.40)
        + (area_score * 0.30)
        + (confirmation_score * 0.20)
        + (time_score * 0.10)
    )

    final_score = round(final_score)

    # --- Tier Assignment ---
    if final_score >= 80:
        tier = "BREAKING"
    elif final_score >= 50:
        tier = "HIGH"
    elif final_score >= 20:
        tier = "MEDIUM"
    else:
        tier = "LOW"

    return final_score, tier