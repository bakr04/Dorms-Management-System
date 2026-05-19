"""Reusable values that mirror enums already present in the MySQL schema."""

GENDER_CHOICES = (("Male", "Male"), ("Female", "Female"))
VISITOR_GENDER_CHOICES = (("Male", "Male"), ("Female", "Female"), ("Other", "Other"))

ACADEMIC_PROGRAM_STATUSES = ("Active", "Inactive", "Suspended")
ACADEMIC_SEMESTER_STATUSES = ("Upcoming", "Active", "Completed")
BUILDING_STATUSES = ("Active", "Under Maintenance", "Closed")

STUDENT_STATUSES = ("Active", "Inactive", "Graduated", "Suspended")
DISCIPLINARY_STATUSES = ("Clear", "Warning", "Probation", "Suspended")
SYSTEM_USER_STATUSES = ("Active", "Inactive", "Suspended")

APPLICATION_STATUSES = ("Pending", "Approved", "Rejected", "Cancelled", "Waitlisted")
ACTIVE_APPLICATION_STATUSES = ("Pending", "Approved", "Waitlisted")

ROOM_STATUSES = ("Available", "Occupied", "Maintenance", "Reserved", "Closed")
ROOM_ASSIGNMENT_STATUSES = ("Active", "Completed", "Cancelled", "Pending")

MAINTENANCE_PRIORITIES = ("Low", "Medium", "High", "Critical")
MAINTENANCE_STATUSES = ("Open", "In Progress", "Resolved", "Closed", "Cancelled")
OPEN_MAINTENANCE_STATUSES = ("Open", "In Progress")

COMPLAINT_PRIORITIES = ("Low", "Medium", "High", "Urgent")
COMPLAINT_STATUSES = ("Open", "In Progress", "Resolved", "Closed", "Rejected")
OPEN_COMPLAINT_STATUSES = ("Open", "In Progress")

TRANSFER_PRIORITIES = ("Low", "Normal", "High", "Urgent")
TRANSFER_STATUSES = ("Pending", "Approved", "Rejected", "Completed", "Cancelled")
ACTIVE_TRANSFER_STATUSES = ("Pending", "Approved")

INVOICE_PAYMENT_STATUSES = ("Unpaid", "Partial", "Paid", "Overdue", "Cancelled")
OUTSTANDING_INVOICE_STATUSES = ("Unpaid", "Partial", "Overdue")
PAYMENT_TRANSACTION_STATUSES = ("Pending", "Completed", "Failed", "Refunded")

ANNOUNCEMENT_PRIORITIES = ("Low", "Normal", "High", "Urgent")
ANNOUNCEMENT_STATUSES = ("Draft", "Published", "Expired", "Cancelled")

NOTIFICATION_CHANNELS = ("Email", "SMS", "Push", "In-App")
NOTIFICATION_STATUSES = ("Sent", "Delivered", "Read", "Failed")

LEAVE_PERMISSION_STATUSES = ("Pending", "Approved", "Rejected", "Cancelled")
VISITOR_PERMISSION_STATUSES = ("Pending", "Approved", "Rejected", "Expired")
MEAL_SUBSCRIPTION_STATUSES = ("Active", "Paused", "Cancelled", "Expired")
MEAL_TYPES = ("Breakfast", "Lunch", "Dinner", "Snack")
MEAL_ATTENDANCE_STATUSES = ("Present", "Absent", "Late")
ACCESS_TYPES = ("Entry", "Exit")
ACCESS_STATUSES = ("Granted", "Denied")
ACCESS_METHODS = ("Card", "Biometric", "Manual", "QR")
LAUNDRY_TYPES = ("Washer", "Dryer", "Combined")
LOST_FOUND_STATUSES = ("Found", "Claimed", "Unclaimed", "Disposed", "Cancelled")
PENALTY_STATUSES = ("Pending", "Paid", "Waived", "Overdue")
BLACKLIST_SEVERITIES = ("Low", "Medium", "High", "Critical")
BLACKLIST_STATUSES = ("Active", "Removed", "Appealing")
BLACKLIST_APPEAL_STATUSES = ("None", "Pending", "Approved", "Rejected")
INCIDENT_SEVERITIES = ("Low", "Medium", "High", "Critical")
INCIDENT_STATUSES = ("Open", "Investigating", "Resolved", "Closed")
ROOM_INSPECTION_STATUSES = ("Scheduled", "Completed", "Failed", "Cancelled")
ROOM_DAMAGE_LEVELS = ("None", "Minor", "Moderate", "Severe")
FURNITURE_CONDITIONS = ("Excellent", "Good", "Fair", "Poor")


def as_choices(values: tuple[str, ...]) -> tuple[tuple[str, str], ...]:
    return tuple((value, value) for value in values)
