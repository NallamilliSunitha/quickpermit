from django.utils import timezone
from datetime import timedelta

SUSPICIOUS_KEYWORDS = [
    "fake", "forged", "dummy", "edited", "photoshop", "proxy", "not real"
]

NEEDS_INFO_KEYWORDS = [
    "need permission", "please", "request", "leave"
]

def _contains_any(text, keywords):
    t = (text or "").lower()
    return any(k in t for k in keywords)

def compute_permission_insight(req):
    """
    Returns dict:
      score (0-100),
      recommendation: approve/reject/needs_info/review
      flags: list[str]
      summary: str
    """
    flags = []
    score = 60  # base score

    # ---- Basic validation flags ----
    if not req.from_date or not req.to_date:
        flags.append("missing_dates")
        score -= 25

    if req.from_date and req.to_date and req.to_date < req.from_date:
        flags.append("invalid_date_range")
        score -= 40

    # ---- Reason / Title quality ----
    reason = (req.reason or "").strip()
    title = (req.title or "").strip()

    if len(reason) < 20 and not req.file:
        flags.append("short_reason")
        score -= 12

    # suspicious keywords
    if _contains_any(reason, SUSPICIOUS_KEYWORDS) or _contains_any(title, SUSPICIOUS_KEYWORDS):
        flags.append("suspicious_keywords")
        score -= 30

    # ---- Urgent handling ----
    if getattr(req, "is_urgent", False) and req.status == "pending":
        flags.append("urgent")
        score += 8

        # near escalation warning
        esc = getattr(req, "escalate_at", None)
        if esc:
            mins = int((esc - timezone.now()).total_seconds() / 60)
            if mins <= 10:
                flags.append("near_escalation_10min")
                score += 6

    # ---- Frequent leave detection (history-based) ----
    # last 30 days requests by same student
    from permissions.models import PermissionRequest
    last_30 = timezone.now() - timedelta(days=30)
    recent_count = PermissionRequest.objects.filter(
        student=req.student,
        applied_at__gte=last_30
    ).exclude(id=req.id).count()

    if recent_count >= 3:
        flags.append("frequent_requests_30d")
        score -= 18

    # ---- Recommendation decision ----
    # clamp score
    score = max(0, min(100, score))

    if "invalid_date_range" in flags:
        recommendation = "reject"
        summary = "Invalid date range. To date is earlier than from date."
    elif "missing_dates" in flags:
        recommendation = "needs_info"
        summary = "Dates are missing. Ask student to provide correct from/to dates."
    elif "suspicious_keywords" in flags:
        recommendation = "needs_info"
        summary = "Suspicious wording detected. Request supporting proof or clarification."
    elif "short_reason" in flags and not req.file:
        recommendation = "needs_info"
        summary = "Reason is too short. Ask for more details or attach proof."
    else:
        # normal logic
        if score >= 75:
            recommendation = "approve"
            summary = "Request looks valid with sufficient details."
        elif score <= 40:
            recommendation = "needs_info"
            summary = "Request needs clarification or additional details."
        else:
            recommendation = "review"
            summary = "Review request details before deciding."

    return {
        "score": score,
        "recommendation": recommendation,
        "flags": flags,
        "summary": summary
    }
