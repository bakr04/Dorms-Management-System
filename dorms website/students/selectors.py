from __future__ import annotations

from decimal import Decimal

from django.db.models import Count, F, Prefetch, Q
from django.utils import timezone

from .choices import (
    OPEN_COMPLAINT_STATUSES,
    OPEN_MAINTENANCE_STATUSES,
    OUTSTANDING_INVOICE_STATUSES,
)
from .models import (
    Announcement,
    Blacklist,
    Complaint,
    IncidentReport,
    Invoice,
    MaintenanceRequest,
    Notification,
    PaymentTransaction,
    Penalty,
    Registration,
    Room,
    RoomAssignment,
    Student,
    StudentAnnouncement,
)


def get_current_assignment(student: Student) -> RoomAssignment | None:
    return (
        RoomAssignment.objects.select_related("room__building", "room__room_type", "bed_slot")
        .filter(student=student, status="Active")
        .order_by("-check_in_date", "-assignment_id")
        .first()
    )


def get_roommates(student: Student) -> list[Student]:
    assignment = get_current_assignment(student)
    if assignment is None:
        return []
    roommate_ids = (
        RoomAssignment.objects.filter(room=assignment.room, status="Active")
        .exclude(student=student)
        .values_list("student_id", flat=True)
    )
    return list(
        Student.objects.select_related("faculty", "program")
        .filter(student_id__in=roommate_ids)
        .order_by("first_name", "last_name")
    )


def get_available_rooms(student: Student):
    eligible_buildings = Q(building__gender_allowed="Mixed") | Q(
        building__gender_allowed=student.gender
    )
    return (
        Room.objects.select_related("building", "room_type")
        .annotate(
            total_bed_slots=Count("beds", distinct=True),
            free_bed_slots=Count(
                "beds",
                filter=Q(beds__is_occupied=False, beds__is_reserved=False),
                distinct=True,
            ),
        )
        .filter(status__in=["Available", "Occupied"])
        .filter(building__status="Active")
        .filter(eligible_buildings)
        .filter(
            Q(total_bed_slots=0, current_occupancy__isnull=True)
            | Q(total_bed_slots=0, current_occupancy__lt=F("capacity"))
            | Q(free_bed_slots__gt=0)
        )
        .order_by("building__building_name", "room_number")
    )


def get_room_catalog(student: Student) -> list[Room]:
    rooms = list(
        Room.objects.select_related("building", "room_type")
        .annotate(
            total_bed_slots=Count("beds", distinct=True),
            free_bed_slots=Count(
                "beds",
                filter=Q(beds__is_occupied=False, beds__is_reserved=False),
                distinct=True,
            ),
        )
        .order_by("building__building_name", "room_number")
    )
    for room in rooms:
        room.portal_label = room_portal_label(room, student)
        room.can_request = room_can_accept_student(room, student)
    return rooms


def room_eligibility_label(room: Room, student: Student) -> str:
    if room.building.status != "Active":
        return "Building unavailable"
    if room.building.gender_allowed not in {"Mixed", student.gender}:
        return "Building restricted"
    return "Eligible"


def room_can_accept_student(room: Room, student: Student) -> bool:
    return (
        room_eligibility_label(room, student) == "Eligible"
        and room.status in {"Available", "Occupied"}
        and room.available_beds > 0
        and room_has_assignable_bed(room)
    )


def room_portal_label(room: Room, student: Student) -> str:
    eligibility = room_eligibility_label(room, student)
    if eligibility != "Eligible":
        return eligibility
    if room.status not in {"Available", "Occupied"}:
        return "Unavailable"
    if room.available_beds < 1:
        return "Full"
    if not room_has_assignable_bed(room):
        return "No free bed slot"
    return "Can request"


def room_has_assignable_bed(room: Room) -> bool:
    total_bed_slots = getattr(room, "total_bed_slots", None)
    free_bed_slots = getattr(room, "free_bed_slots", None)
    if total_bed_slots is None or free_bed_slots is None:
        total_bed_slots = room.beds.count()
        free_bed_slots = room.beds.filter(is_occupied=False, is_reserved=False).count()
    return total_bed_slots == 0 or free_bed_slots > 0


def get_active_announcements(student: Student):
    now = timezone.now()
    read_ids = set(
        StudentAnnouncement.objects.filter(student=student, is_read=True).values_list(
            "announcement_id", flat=True
        )
    )
    announcements = list(
        Announcement.objects.filter(status="Published", publish_date__lte=now)
        .filter(Q(expiry_date__isnull=True) | Q(expiry_date__gte=now))
        .order_by("-publish_date")
    )
    for announcement in announcements:
        announcement.is_read_for_student = announcement.announcement_id in read_ids
    return announcements


def get_active_notifications(student: Student):
    now = timezone.now()
    return (
        Notification.objects.filter(student=student)
        .filter(publish_date__lte=now)
        .filter(Q(expiry_date__isnull=True) | Q(expiry_date__gte=now))
        .exclude(status="Failed")
        .order_by("-publish_date", "-notification_id")
    )


def get_unread_notice_counts(student: Student) -> dict[str, int]:
    active_announcements = get_active_announcements(student)
    return {
        "announcements": sum(1 for item in active_announcements if not item.is_read_for_student),
        "notifications": get_active_notifications(student).filter(is_read=False).count(),
    }


def get_student_invoices_with_balances(student: Student):
    invoices = list(
        Invoice.objects.filter(student=student)
        .prefetch_related(
            Prefetch(
                "transactions",
                queryset=PaymentTransaction.objects.filter(payment_status="Completed"),
                to_attr="completed_transactions",
            )
        )
        .order_by("-due_date", "-invoice_id")
    )
    for invoice in invoices:
        paid_amount = sum(
            (transaction.payment_amount for transaction in invoice.completed_transactions),
            Decimal("0.00"),
        )
        invoice.paid_amount = paid_amount
        invoice.balance_due = (
            Decimal("0.00")
            if invoice.payment_status not in OUTSTANDING_INVOICE_STATUSES
            else max(invoice.billed_total - paid_amount, Decimal("0.00"))
        )
    return invoices


def get_student_penalty_summary(student: Student) -> dict:
    penalties = Penalty.objects.filter(student=student)
    open_penalties = penalties.filter(status__in=["Pending", "Overdue"])
    return {
        "pending_penalty_total": sum(
            (penalty.amount for penalty in open_penalties),
            Decimal("0.00"),
        ),
        "pending_penalty_count": open_penalties.count(),
    }


def get_student_records_snapshot(student: Student) -> dict:
    active_blacklist = Blacklist.objects.filter(student=student, status="Active").first()
    return {
        "active_blacklist": active_blacklist,
        "open_incident_count": IncidentReport.objects.filter(
            student=student,
            status__in=["Open", "Investigating"],
        ).count(),
        **get_student_penalty_summary(student),
    }


def get_dashboard_snapshot(student: Student) -> dict:
    assignment = get_current_assignment(student)
    unpaid_total = sum(
        (
            invoice.balance_due
            for invoice in get_student_invoices_with_balances(student)
            if invoice.payment_status in OUTSTANDING_INVOICE_STATUSES
        ),
        Decimal("0.00"),
    )
    unread_counts = get_unread_notice_counts(student)
    latest_application = (
        Registration.objects.filter(student=student).order_by("-application_date", "-application_id").first()
    )
    records_snapshot = get_student_records_snapshot(student)
    return {
        "assignment": assignment,
        "active_maintenance_count": MaintenanceRequest.objects.filter(
            reported_by_student=student,
            status__in=OPEN_MAINTENANCE_STATUSES,
        )
        .count(),
        "open_complaint_count": Complaint.objects.filter(
            student=student,
            status__in=OPEN_COMPLAINT_STATUSES,
        ).count(),
        "unpaid_total": unpaid_total,
        "unread_announcements": unread_counts["announcements"],
        "unread_notifications": unread_counts["notifications"],
        "latest_application": latest_application,
        **records_snapshot,
    }
