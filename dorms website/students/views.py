from __future__ import annotations

from functools import wraps

from django.contrib import messages
from django.contrib.auth.hashers import check_password, make_password
from django.core.exceptions import ValidationError
from django.db import DatabaseError, IntegrityError, transaction
from django.db.models import Prefetch, Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .auth import SESSION_USER_KEY, get_current_user, student_account_is_active, student_login_required
from .forms import (
    ComplaintForm,
    DormApplicationForm,
    EmergencyContactForm,
    LeavePermissionForm,
    LoginForm,
    LostAndFoundReportForm,
    MaintenanceRequestForm,
    ProfileUpdateForm,
    RoomTransferForm,
    StudentRegistrationForm,
    VisitorPermissionRequestForm,
)
from .models import (
    AcademicProgram,
    AccessLog,
    Blacklist,
    Complaint,
    DormService,
    IncidentReport,
    LaundryUsage,
    LeavePermission,
    LostAndFoundItem,
    MaintenanceLog,
    MaintenanceRequest,
    MealAttendance,
    MealSubscription,
    Notification,
    PaymentTransaction,
    Penalty,
    Registration,
    RoomAssignment,
    RoomInspection,
    RoomTransfer,
    StudentAnnouncement,
    SystemUser,
    VisitorPermission,
)
from .selectors import (
    get_active_announcements,
    get_active_notifications,
    get_current_assignment,
    get_dashboard_snapshot,
    get_room_catalog,
    get_roommates,
    get_student_penalty_summary,
    get_student_invoices_with_balances,
)


def _database_error_message(exc: Exception) -> str:
    for value in reversed(getattr(exc, "args", ())):
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "The database rejected this change. Please review the form and try again."


def _save_form_with_errors(form, *, request=None, success_message: str | None = None) -> bool:
    try:
        form.save()
    except ValidationError as exc:
        form.add_error(None, exc)
    except IntegrityError:
        form.add_error(None, "This request conflicts with an existing record.")
    except DatabaseError as exc:
        form.add_error(None, _database_error_message(exc))
    else:
        if request is not None and success_message:
            messages.success(request, success_message)
        return True
    return False


def accepted_accommodation_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if get_current_assignment(request.student) is None:
            url_name = getattr(getattr(request, "resolver_match", None), "url_name", "")
            if url_name.startswith("api_"):
                return JsonResponse(
                    {
                        "detail": (
                            "Accommodation must be accepted and assigned before this endpoint is available."
                        )
                    },
                    status=403,
                )
            messages.info(
                request,
                "These options become available after your accommodation is accepted and a room is assigned.",
            )
            return redirect("students:applications")
        return view_func(request, *args, **kwargs)

    return wrapper


def landing(request):
    if get_current_user(request):
        return redirect("students:dashboard")
    return render(request, "students/landing.html")


def register(request):
    if get_current_user(request):
        return redirect("students:dashboard")
    if request.method == "POST":
        form = StudentRegistrationForm(request.POST)
        if form.is_valid():
            try:
                user = form.save()
            except ValidationError as exc:
                form.add_error(None, exc)
            except IntegrityError:
                form.add_error(
                    None,
                    "The account could not be created because one of the submitted values already exists.",
                )
            except DatabaseError as exc:
                form.add_error(None, _database_error_message(exc))
            else:
                request.session.cycle_key()
                request.session[SESSION_USER_KEY] = user.user_id
                messages.success(request, "Your student portal account is ready.")
                return redirect("students:dashboard")
    else:
        form = StudentRegistrationForm()
    programs_by_faculty: dict[str, list[dict[str, str]]] = {}
    for program in AcademicProgram.objects.filter(status="Active").order_by("name"):
        programs_by_faculty.setdefault(str(program.faculty_id), []).append(
            {
                "id": str(program.program_id),
                "name": program.name,
            }
        )
    return render(
        request,
        "students/register.html",
        {
            "form": form,
            "programs_by_faculty": programs_by_faculty,
        },
    )


def login_view(request):
    if get_current_user(request):
        return redirect("students:dashboard")
    form = LoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = (
            SystemUser.objects.select_related("student", "role")
            .filter(email__iexact=form.cleaned_data["email"], status="Active", student__isnull=False)
            .first()
        )
        if (
            student_account_is_active(user)
            and check_password(
                form.cleaned_data["password"],
                user.password_hash,
                setter=lambda encoded: _upgrade_password_hash(user, encoded),
            )
        ):
            request.session.cycle_key()
            request.session[SESSION_USER_KEY] = user.user_id
            return redirect("students:dashboard")
        form.add_error(None, "Invalid student email or password.")
    return render(request, "students/login.html", {"form": form})


def _upgrade_password_hash(user: SystemUser, raw_password: str) -> None:
    user.password_hash = make_password(raw_password)
    user.save(update_fields=["password_hash"])


@require_POST
def logout_view(request):
    request.session.flush()
    messages.info(request, "You have been logged out.")
    return redirect("students:landing")


@student_login_required
def dashboard(request):
    announcements = get_active_announcements(request.student)[:3]
    latest_requests = list(
        MaintenanceRequest.objects.filter(reported_by_student=request.student).order_by("-reported_at")[:3]
    )
    snapshot = get_dashboard_snapshot(request.student)
    return render(
        request,
        "students/dashboard.html",
        {
            **snapshot,
            "announcements": announcements,
            "latest_requests": latest_requests,
        },
    )


@student_login_required
def my_room(request):
    assignment = get_current_assignment(request.student)
    room_transfers = (
        RoomTransfer.objects.select_related("from_room__building", "to_room__building")
        .filter(student=request.student)
        .order_by("-request_date", "-transfer_id")
    )
    return render(
        request,
        "students/my_room.html",
        {
            "assignment": assignment,
            "room_catalog": get_room_catalog(request.student),
            "room_transfers": room_transfers,
            "room_inspections": (
                RoomInspection.objects.filter(room=assignment.room)
                .order_by("-inspection_date", "-inspection_id")[:5]
                if assignment
                else []
            ),
        },
    )


@student_login_required
@accepted_accommodation_required
def roommates(request):
    return render(
        request,
        "students/roommates.html",
        {
            "assignment": get_current_assignment(request.student),
            "roommates": get_roommates(request.student),
        },
    )


@student_login_required
@accepted_accommodation_required
def requests_hub(request):
    maintenance_requests = (
        MaintenanceRequest.objects.filter(reported_by_student=request.student)
        .prefetch_related(
            Prefetch(
                "maintenance_logs",
                queryset=MaintenanceLog.objects.order_by("-logged_at", "-log_id"),
                to_attr="ordered_logs",
            )
        )
        .order_by("-reported_at")
    )
    complaints = Complaint.objects.filter(student=request.student).order_by("-submitted_at")
    return render(
        request,
        "students/requests.html",
        {
            "maintenance_requests": maintenance_requests,
            "complaints": complaints,
        },
    )


@student_login_required
@accepted_accommodation_required
def maintenance_create(request):
    assignment = get_current_assignment(request.student)
    form = MaintenanceRequestForm(
        request.POST or None,
        student=request.student,
        room=assignment.room if assignment else None,
    )
    if request.method == "POST" and form.is_valid() and _save_form_with_errors(
        form,
        request=request,
        success_message="Maintenance request submitted.",
    ):
        return redirect("students:requests")
    return render(
        request,
        "students/maintenance_form.html",
        {"form": form, "assignment": assignment},
    )


@student_login_required
@accepted_accommodation_required
def complaint_create(request):
    form = ComplaintForm(request.POST or None, student=request.student)
    if request.method == "POST" and form.is_valid() and _save_form_with_errors(
        form,
        request=request,
        success_message="Complaint submitted.",
    ):
        return redirect("students:requests")
    return render(request, "students/complaint_form.html", {"form": form})


@student_login_required
@accepted_accommodation_required
def announcements(request):
    return render(
        request,
        "students/announcements.html",
        {
            "announcements": get_active_announcements(request.student),
            "notifications": get_active_notifications(request.student),
        },
    )


@student_login_required
@accepted_accommodation_required
@require_POST
def mark_announcement_read(request, announcement_id: int):
    announcement = next(
        (
            item
            for item in get_active_announcements(request.student)
            if item.announcement_id == announcement_id
        ),
        None,
    )
    if announcement is None:
        raise Http404("Announcement not found.")
    with transaction.atomic():
        receipt, _ = StudentAnnouncement.objects.get_or_create(
            student=request.student,
            announcement=announcement,
            defaults={"is_read": True, "read_at": timezone.now()},
        )
        if not receipt.is_read:
            receipt.is_read = True
            receipt.read_at = timezone.now()
            receipt.save(update_fields=["is_read", "read_at"])
    return redirect("students:announcements")


@student_login_required
@accepted_accommodation_required
@require_POST
def mark_notification_read(request, notification_id: int):
    notification = get_object_or_404(
        Notification,
        notification_id=notification_id,
        student=request.student,
    )
    if not notification.is_read:
        notification.is_read = True
        notification.status = "Read"
        notification.save(update_fields=["is_read", "status"])
    return redirect("students:announcements")


@student_login_required
def profile(request):
    form = ProfileUpdateForm(request.POST or None, instance=request.student)
    if request.method == "POST" and form.is_valid() and _save_form_with_errors(
        form,
        request=request,
        success_message="Profile updated.",
    ):
        return redirect("students:profile")
    emergency_contacts = request.student.emergency_contacts.filter(is_active=True)
    assignment = get_current_assignment(request.student)
    return render(
        request,
        "students/profile.html",
        {
            "form": form,
            "emergency_contacts": emergency_contacts,
            "assignment": assignment,
        },
    )


@student_login_required
def emergency_contact_create(request):
    form = EmergencyContactForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            form.save_for_student(request.student)
        except IntegrityError:
            form.add_error(None, "This emergency contact conflicts with an existing record.")
        except DatabaseError as exc:
            form.add_error(None, _database_error_message(exc))
        else:
            messages.success(request, "Emergency contact added.")
            return redirect("students:profile")
    return render(request, "students/emergency_contact_form.html", {"form": form})


@student_login_required
@require_POST
def emergency_contact_deactivate(request, contact_id: int):
    contact = get_object_or_404(
        request.student.emergency_contacts,
        contact_id=contact_id,
        is_active=True,
    )
    contact.is_active = False
    contact.save(update_fields=["is_active"])
    messages.info(request, "Emergency contact removed.")
    return redirect("students:profile")


@student_login_required
@accepted_accommodation_required
def payments(request):
    invoices = get_student_invoices_with_balances(request.student)
    transactions = PaymentTransaction.objects.filter(student=request.student).order_by(
        "-payment_date",
        "-transaction_id",
    )
    penalties = Penalty.objects.filter(student=request.student).order_by(
        "-penalty_date",
        "-penalty_id",
    )
    return render(
        request,
        "students/payments.html",
        {
            "invoices": invoices,
            "transactions": transactions,
            "penalties": penalties,
            **get_student_penalty_summary(request.student),
        },
    )


@student_login_required
@accepted_accommodation_required
def records(request):
    return render(
        request,
        "students/records.html",
        {
            "penalties": Penalty.objects.filter(student=request.student).order_by(
                "-penalty_date",
                "-penalty_id",
            ),
            "blacklist_record": Blacklist.objects.filter(student=request.student).first(),
            "incidents": IncidentReport.objects.filter(student=request.student).order_by(
                "-incident_date",
                "-report_id",
            ),
        },
    )


@student_login_required
def applications(request):
    return render(
        request,
        "students/applications.html",
        {
            "applications": Registration.objects.filter(student=request.student)
            .prefetch_related(
                Prefetch(
                    "room_assignments",
                    queryset=(
                        RoomAssignment.objects.select_related("room__building")
                        .order_by("-check_in_date", "-assignment_id")
                    ),
                    to_attr="ordered_assignments",
                )
            )
            .order_by("-application_date", "-application_id")
        },
    )


@student_login_required
def application_create(request):
    form = DormApplicationForm(request.POST or None, student=request.student)
    if request.method == "POST" and form.is_valid() and _save_form_with_errors(
        form,
        request=request,
        success_message="Dorm application submitted.",
    ):
        return redirect("students:applications")
    return render(request, "students/application_form.html", {"form": form})


@student_login_required
@accepted_accommodation_required
def permissions(request):
    return render(
        request,
        "students/permissions.html",
        {
            "leave_permissions": LeavePermission.objects.filter(student=request.student).order_by(
                "-request_date",
                "-permission_id",
            ),
            "visitor_permissions": VisitorPermission.objects.select_related("visitor")
            .filter(student=request.student)
            .order_by("-request_date", "-permission_id"),
        },
    )


@student_login_required
@accepted_accommodation_required
def leave_permission_create(request):
    form = LeavePermissionForm(request.POST or None, student=request.student)
    if request.method == "POST" and form.is_valid() and _save_form_with_errors(
        form,
        request=request,
        success_message="Leave request submitted.",
    ):
        return redirect("students:permissions")
    return render(request, "students/leave_form.html", {"form": form})


@student_login_required
@accepted_accommodation_required
def visitor_permission_create(request):
    form = VisitorPermissionRequestForm(request.POST or None, student=request.student)
    if request.method == "POST" and form.is_valid() and _save_form_with_errors(
        form,
        request=request,
        success_message="Visitor permission request submitted.",
    ):
        return redirect("students:permissions")
    return render(request, "students/visitor_permission_form.html", {"form": form})


@student_login_required
@accepted_accommodation_required
def services(request):
    assignment = get_current_assignment(request.student)
    active_services = DormService.objects.select_related("building").filter(status="Active")
    if assignment:
        active_services = active_services.filter(
            Q(building__isnull=True) | Q(building=assignment.room.building)
        )
    return render(
        request,
        "students/services.html",
        {
            "active_services": active_services.order_by("name"),
            "meal_subscriptions": MealSubscription.objects.filter(student=request.student).order_by(
                "-start_date",
                "-subscription_id",
            ),
            "meal_attendance": MealAttendance.objects.filter(student=request.student)
            .select_related("subscription")
            .order_by("-meal_date", "-check_in_date_time")[:10],
            "laundry_usage": LaundryUsage.objects.select_related("laundry__building", "laundry__service")
            .filter(student=request.student)
            .order_by("-usage_date", "-usage_id")[:10],
            "lost_found_reports": LostAndFoundItem.objects.filter(
                reported_by=request.student
            ).order_by("-report_date", "-item_id"),
            "access_logs": AccessLog.objects.select_related("building")
            .filter(student=request.student)
            .order_by("-log_time", "-log_id")[:10],
        },
    )


@student_login_required
@accepted_accommodation_required
def lost_found_create(request):
    form = LostAndFoundReportForm(request.POST or None, student=request.student)
    if request.method == "POST" and form.is_valid() and _save_form_with_errors(
        form,
        request=request,
        success_message="Lost and found report submitted.",
    ):
        return redirect("students:services")
    return render(request, "students/lost_found_form.html", {"form": form})


@student_login_required
def room_transfer_create(request):
    assignment = get_current_assignment(request.student)
    if assignment is None:
        messages.error(request, "You need an active room assignment before requesting a transfer.")
        return redirect("students:my_room")
    form = RoomTransferForm(
        request.POST or None,
        student=request.student,
        from_room=assignment.room,
    )
    if request.method == "POST" and form.is_valid() and _save_form_with_errors(
        form,
        request=request,
        success_message="Room transfer request submitted.",
    ):
        return redirect("students:my_room")
    return render(
        request,
        "students/transfer_form.html",
        {"form": form, "assignment": assignment},
    )


@student_login_required
def api_me(request):
    student = request.student
    return JsonResponse(
        {
            "student_id": student.student_id,
            "first_name": student.first_name,
            "last_name": student.last_name,
            "email": student.email,
            "gpa": str(student.gpa) if student.gpa is not None else None,
            "status": student.status,
            "faculty": student.faculty.name if student.faculty else None,
            "program": student.program.name if student.program else None,
        }
    )


@student_login_required
def api_my_room(request):
    assignment = get_current_assignment(request.student)
    if assignment is None:
        return JsonResponse({"assignment": None})
    return JsonResponse(
        {
            "assignment": {
                "room": assignment.room.room_number,
                "building": assignment.room.building.building_name,
                "floor": assignment.room.floor_number,
                "bed": assignment.bed_slot.bed_number if assignment.bed_slot else None,
                "status": assignment.status,
                "check_in_date": assignment.check_in_date.isoformat(),
            }
        }
    )


@student_login_required
@accepted_accommodation_required
def api_requests(request):
    maintenance = list(
        MaintenanceRequest.objects.filter(reported_by_student=request.student)
        .order_by("-reported_at")
        .values("request_id", "title", "category", "priority", "status", "reported_at")
    )
    complaints = list(
        Complaint.objects.filter(student=request.student)
        .order_by("-submitted_at")
        .values("complaint_id", "subject", "category", "priority", "status", "submitted_at")
    )
    return JsonResponse({"maintenance": maintenance, "complaints": complaints})


@student_login_required
@accepted_accommodation_required
def api_announcements(request):
    payload = [
        {
            "announcement_id": item.announcement_id,
            "title": item.title,
            "type": item.type,
            "priority_level": item.priority_level,
            "publish_date": item.publish_date.isoformat(),
            "is_read": item.is_read_for_student,
        }
        for item in get_active_announcements(request.student)
    ]
    return JsonResponse({"announcements": payload})


# ── Student delete / cancel views ──

@student_login_required
@require_POST
def application_cancel(request, application_id: int):
    application = get_object_or_404(
        Registration,
        application_id=application_id,
        student=request.student,
    )
    if application.status not in {"Pending", "Waitlisted"}:
        messages.error(request, "Only pending or waitlisted applications can be cancelled.")
        return redirect("students:applications")
    application.status = "Cancelled"
    application.approval_date = timezone.localdate()
    application.save(update_fields=["status", "approval_date"])
    messages.success(request, "Application cancelled.")
    return redirect("students:applications")


@student_login_required
@accepted_accommodation_required
@require_POST
def maintenance_request_cancel(request, request_id: int):
    maintenance = get_object_or_404(
        MaintenanceRequest,
        request_id=request_id,
        reported_by_student=request.student,
    )
    if maintenance.status not in {"Open", "In Progress"}:
        messages.error(request, "Only open or in-progress requests can be cancelled.")
        return redirect("students:requests")
    maintenance.status = "Cancelled"
    maintenance.resolved_at = timezone.now()
    maintenance.save(update_fields=["status", "resolved_at"])
    messages.success(request, "Maintenance request cancelled.")
    return redirect("students:requests")


@student_login_required
@accepted_accommodation_required
@require_POST
def complaint_cancel(request, complaint_id: int):
    complaint = get_object_or_404(
        Complaint,
        complaint_id=complaint_id,
        student=request.student,
    )
    if complaint.status not in {"Open", "In Progress"}:
        messages.error(request, "Only open or in-progress complaints can be cancelled.")
        return redirect("students:requests")
    complaint.status = "Cancelled"
    complaint.closed_at = timezone.now()
    complaint.save(update_fields=["status", "closed_at"])
    messages.success(request, "Complaint cancelled.")
    return redirect("students:requests")


@student_login_required
@require_POST
def room_transfer_cancel(request, transfer_id: int):
    transfer = get_object_or_404(
        RoomTransfer,
        transfer_id=transfer_id,
        student=request.student,
    )
    if transfer.status not in {"Pending", "Approved"}:
        messages.error(request, "Only pending or approved transfers can be cancelled.")
        return redirect("students:my_room")
    transfer.status = "Cancelled"
    transfer.approval_date = timezone.localdate()
    transfer.save(update_fields=["status", "approval_date"])
    messages.success(request, "Room transfer request cancelled.")
    return redirect("students:my_room")


@student_login_required
@accepted_accommodation_required
@require_POST
def leave_permission_cancel(request, permission_id: int):
    permission = get_object_or_404(
        LeavePermission,
        permission_id=permission_id,
        student=request.student,
    )
    if permission.status not in {"Pending", "Approved"}:
        messages.error(request, "Only pending or approved leave permissions can be cancelled.")
        return redirect("students:permissions")
    permission.status = "Cancelled"
    permission.approval_date = timezone.localdate()
    permission.save(update_fields=["status", "approval_date"])
    messages.success(request, "Leave permission cancelled.")
    return redirect("students:permissions")


@student_login_required
@accepted_accommodation_required
@require_POST
def visitor_permission_cancel(request, permission_id: int):
    permission = get_object_or_404(
        VisitorPermission,
        permission_id=permission_id,
        student=request.student,
    )
    if permission.status not in {"Pending", "Approved"}:
        messages.error(request, "Only pending or approved visitor permissions can be cancelled.")
        return redirect("students:permissions")
    permission.status = "Cancelled"
    permission.approval_date = timezone.localdate()
    permission.save(update_fields=["status", "approval_date"])
    messages.success(request, "Visitor permission cancelled.")
    return redirect("students:permissions")


@student_login_required
@accepted_accommodation_required
@require_POST
def lost_found_cancel(request, item_id: int):
    item = get_object_or_404(
        LostAndFoundItem,
        item_id=item_id,
        reported_by=request.student,
    )
    if item.status not in {"Open", "Pending"}:
        messages.error(request, "Only open or pending reports can be cancelled.")
        return redirect("students:services")
    item.status = "Cancelled"
    item.save(update_fields=["status"])
    messages.success(request, "Lost and found report cancelled.")
    return redirect("students:services")
