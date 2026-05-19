from .auth import get_current_user
from .selectors import get_current_assignment, get_unread_notice_counts


def student_portal_context(request):
    user = get_current_user(request)
    if user is None or user.student is None:
        return {
            "current_student_user": None,
            "current_student": None,
            "nav_unread_notices": 0,
            "student_accommodation_is_accepted": False,
        }
    unread_counts = get_unread_notice_counts(user.student)
    current_assignment = get_current_assignment(user.student)
    return {
        "current_student_user": user,
        "current_student": user.student,
        "nav_unread_notices": unread_counts["announcements"] + unread_counts["notifications"],
        "student_accommodation_is_accepted": current_assignment is not None,
    }
