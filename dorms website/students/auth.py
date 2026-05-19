from __future__ import annotations

from functools import wraps

from django.shortcuts import redirect

from .models import SystemUser


SESSION_USER_KEY = "student_user_id"


def user_has_student_role(user: SystemUser | None) -> bool:
    return bool(user and user.role and "student" in user.role.role_name.lower())


def student_account_is_active(user: SystemUser | None) -> bool:
    return bool(
        user
        and user.student
        and user.status == "Active"
        and user.student.status == "Active"
        and user_has_student_role(user)
    )


def get_current_user(request) -> SystemUser | None:
    user_id = request.session.get(SESSION_USER_KEY)
    if not user_id:
        return None
    user = (
        SystemUser.objects.select_related("student", "role")
        .filter(user_id=user_id, student__isnull=False, status="Active")
        .first()
    )
    return user if student_account_is_active(user) else None


def student_login_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        user = get_current_user(request)
        if user is None:
            request.session.flush()
            return redirect("students:login")
        request.student_user = user
        request.student = user.student
        return view_func(request, *args, **kwargs)

    return wrapper
