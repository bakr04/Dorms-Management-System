from django.db import models

from .choices import (
    ACADEMIC_PROGRAM_STATUSES,
    ACADEMIC_SEMESTER_STATUSES,
    ANNOUNCEMENT_PRIORITIES,
    ANNOUNCEMENT_STATUSES,
    ACCESS_METHODS,
    ACCESS_STATUSES,
    ACCESS_TYPES,
    APPLICATION_STATUSES,
    BLACKLIST_APPEAL_STATUSES,
    BLACKLIST_SEVERITIES,
    BLACKLIST_STATUSES,
    BUILDING_STATUSES,
    COMPLAINT_PRIORITIES,
    COMPLAINT_STATUSES,
    DISCIPLINARY_STATUSES,
    FURNITURE_CONDITIONS,
    GENDER_CHOICES,
    INCIDENT_SEVERITIES,
    INCIDENT_STATUSES,
    INVOICE_PAYMENT_STATUSES,
    LAUNDRY_TYPES,
    LEAVE_PERMISSION_STATUSES,
    LOST_FOUND_STATUSES,
    MAINTENANCE_PRIORITIES,
    MAINTENANCE_STATUSES,
    MEAL_ATTENDANCE_STATUSES,
    MEAL_SUBSCRIPTION_STATUSES,
    MEAL_TYPES,
    NOTIFICATION_CHANNELS,
    NOTIFICATION_STATUSES,
    PENALTY_STATUSES,
    PAYMENT_TRANSACTION_STATUSES,
    ROOM_DAMAGE_LEVELS,
    ROOM_ASSIGNMENT_STATUSES,
    ROOM_INSPECTION_STATUSES,
    ROOM_STATUSES,
    STUDENT_STATUSES,
    SYSTEM_USER_STATUSES,
    TRANSFER_PRIORITIES,
    TRANSFER_STATUSES,
    VISITOR_GENDER_CHOICES,
    VISITOR_PERMISSION_STATUSES,
    as_choices,
)

class Faculty(models.Model):
    faculty_id = models.AutoField(db_column="FacultyID", primary_key=True)
    name = models.CharField(db_column="Name", max_length=150)
    code = models.CharField(db_column="Code", max_length=20)
    phone_number = models.CharField(
        db_column="PhoneNumber",
        max_length=25,
        blank=True,
        null=True,
    )

    class Meta:
        managed = False
        db_table = "Faculty"

    def __str__(self) -> str:
        return self.name


class AcademicProgram(models.Model):
    program_id = models.AutoField(db_column="ProgramID", primary_key=True)
    faculty = models.ForeignKey(
        Faculty,
        db_column="FacultyID",
        on_delete=models.CASCADE,
        related_name="programs",
    )
    name = models.CharField(db_column="Name", max_length=150)
    code = models.CharField(db_column="Code", max_length=20)
    study_language = models.CharField(
        db_column="StudyLanguage",
        max_length=50,
        blank=True,
        null=True,
    )
    status = models.CharField(
        db_column="Status",
        max_length=20,
        choices=as_choices(ACADEMIC_PROGRAM_STATUSES),
    )

    class Meta:
        managed = False
        db_table = "AcademicProgram"

    def __str__(self) -> str:
        return self.name


class AcademicSemester(models.Model):
    semester_id = models.AutoField(db_column="SemesterID", primary_key=True)
    name = models.CharField(db_column="Name", max_length=100)
    academic_year = models.CharField(db_column="AcademicYear", max_length=20)
    type = models.CharField(db_column="Type", max_length=20)
    start_date = models.DateField(db_column="StartDate")
    end_date = models.DateField(db_column="EndDate")
    status = models.CharField(
        db_column="Status",
        max_length=20,
        choices=as_choices(ACADEMIC_SEMESTER_STATUSES),
    )
    registration_open_date = models.DateField(
        db_column="RegistrationOpenDate",
        blank=True,
        null=True,
    )
    registration_close_date = models.DateField(
        db_column="RegistrationCloseDate",
        blank=True,
        null=True,
    )

    class Meta:
        managed = False
        db_table = "AcademicSemester"

    def __str__(self) -> str:
        return f"{self.name} ({self.academic_year})"


class RoomType(models.Model):
    room_type_id = models.AutoField(db_column="RoomTypeID", primary_key=True)
    name = models.CharField(db_column="Name", max_length=80)
    capacity = models.PositiveSmallIntegerField(db_column="Capacity")
    base_price = models.DecimalField(db_column="BasePrice", max_digits=10, decimal_places=2)
    has_private_bathroom = models.BooleanField(db_column="HasPrivateBathroom")
    has_ac = models.BooleanField(db_column="HasAC")
    has_kitchenette = models.BooleanField(db_column="HasKitchenette")
    internet_speed = models.CharField(
        db_column="InternetSpeed",
        max_length=20,
        blank=True,
        null=True,
    )
    furniture_level = models.CharField(db_column="FurnitureLevel", max_length=20)
    security_deposit = models.DecimalField(
        db_column="SecurityDeposit",
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
    )

    class Meta:
        managed = False
        db_table = "RoomType"

    def __str__(self) -> str:
        return self.name


class Role(models.Model):
    role_id = models.AutoField(db_column="RoleID", primary_key=True)
    role_name = models.CharField(db_column="RoleName", max_length=60)

    class Meta:
        managed = False
        db_table = "Role"

    def __str__(self) -> str:
        return self.role_name


class Building(models.Model):
    building_id = models.AutoField(db_column="BuildingID", primary_key=True)
    building_code = models.CharField(db_column="BuildingCode", max_length=20)
    building_name = models.CharField(db_column="BuildingName", max_length=120)
    building_type = models.CharField(
        db_column="BuildingType",
        max_length=60,
        blank=True,
        null=True,
    )
    number_of_floors = models.PositiveSmallIntegerField(db_column="NumberOfFloors")
    capacity = models.PositiveSmallIntegerField(db_column="Capacity")
    status = models.CharField(
        db_column="Status",
        max_length=30,
        choices=as_choices(BUILDING_STATUSES),
    )
    gender_allowed = models.CharField(db_column="GenderAllowed", max_length=20)

    class Meta:
        managed = False
        db_table = "Building"

    def __str__(self) -> str:
        return self.building_name


class Room(models.Model):
    room_id = models.AutoField(db_column="RoomID", primary_key=True)
    building = models.ForeignKey(
        Building,
        db_column="BuildingID",
        on_delete=models.CASCADE,
        related_name="rooms",
    )
    room_type = models.ForeignKey(
        RoomType,
        db_column="RoomTypeID",
        on_delete=models.CASCADE,
        related_name="rooms",
        blank=True,
        null=True,
    )
    room_number = models.CharField(db_column="RoomNumber", max_length=20)
    floor_number = models.SmallIntegerField(db_column="FloorNumber")
    capacity = models.PositiveSmallIntegerField(db_column="Capacity")
    current_occupancy = models.PositiveSmallIntegerField(
        db_column="CurrentOccupancy",
        blank=True,
        null=True,
    )
    status = models.CharField(
        db_column="Status",
        max_length=30,
        choices=as_choices(ROOM_STATUSES),
    )
    furniture_condition = models.CharField(
        db_column="FurnitureCondition",
        max_length=20,
        choices=as_choices(FURNITURE_CONDITIONS),
    )
    last_inspection_date = models.DateField(
        db_column="LastInspectionDate",
        blank=True,
        null=True,
    )
    class Meta:
        managed = False
        db_table = "Room"

    def __str__(self) -> str:
        return f"{self.building.building_code}-{self.room_number}"

    @property
    def available_beds(self) -> int:
        # Use actual BedSlot records instead of Room.Capacity for accuracy
        total_beds = self.beds.count()
        if total_beds > 0:
            occupied = self.beds.filter(is_occupied=True).count()
            return max(total_beds - occupied, 0)
        occupancy = self.current_occupancy or 0
        return max(self.capacity - occupancy, 0)

    @property
    def monthly_rate(self):
        return self.room_type.base_price if self.room_type else None

    @property
    def security_deposit(self):
        return self.room_type.security_deposit if self.room_type else None

    @property
    def has_private_bathroom(self) -> bool:
        return bool(self.room_type and self.room_type.has_private_bathroom)

    @property
    def has_ac(self) -> bool:
        return bool(self.room_type and self.room_type.has_ac)

    @property
    def has_kitchenette(self) -> bool:
        return bool(self.room_type and self.room_type.has_kitchenette)

    @property
    def furniture_level(self):
        return self.room_type.furniture_level if self.room_type else None


class BedSlot(models.Model):
    bed_slot_id = models.AutoField(db_column="BedSlotID", primary_key=True)
    room = models.ForeignKey(
        Room,
        db_column="RoomID",
        on_delete=models.CASCADE,
        related_name="beds",
    )
    bed_number = models.CharField(db_column="BedNumber", max_length=10)
    bed_position = models.CharField(
        db_column="BedPosition",
        max_length=50,
        blank=True,
        null=True,
    )
    bed_type = models.CharField(db_column="BedType", max_length=20)
    is_occupied = models.BooleanField(db_column="IsOccupied")
    is_reserved = models.BooleanField(db_column="IsReserved")

    class Meta:
        managed = False
        db_table = "BedSlot"

    def __str__(self) -> str:
        return self.bed_number


class Student(models.Model):
    student_id = models.CharField(db_column="StudentID", max_length=20, primary_key=True)
    faculty = models.ForeignKey(
        Faculty,
        db_column="FacultyID",
        on_delete=models.CASCADE,
        related_name="students",
        blank=True,
        null=True,
    )
    program = models.ForeignKey(
        AcademicProgram,
        db_column="ProgramID",
        on_delete=models.CASCADE,
        related_name="students",
        blank=True,
        null=True,
    )
    first_name = models.CharField(db_column="FirstName", max_length=100)
    last_name = models.CharField(db_column="LastName", max_length=100)
    email = models.EmailField(db_column="Email", max_length=150)
    national_id_or_passport = models.CharField(
        db_column="NationalIDOrPassport",
        max_length=60,
        blank=True,
        null=True,
    )
    date_of_birth = models.DateField(db_column="DateOfBirth")
    gender = models.CharField(db_column="Gender", max_length=10, choices=GENDER_CHOICES)
    nationality = models.CharField(
        db_column="Nationality",
        max_length=100,
        blank=True,
        null=True,
    )
    phone_number = models.CharField(
        db_column="PhoneNumber",
        max_length=20,
        blank=True,
        null=True,
    )
    street = models.CharField(db_column="Street", max_length=150, blank=True, null=True)
    city = models.CharField(db_column="City", max_length=100, blank=True, null=True)
    zip_code = models.CharField(db_column="ZIP", max_length=20, blank=True, null=True)
    country = models.CharField(db_column="Country", max_length=100, blank=True, null=True)
    academic_year = models.PositiveSmallIntegerField(
        db_column="AcademicYear",
        blank=True,
        null=True,
    )
    gpa = models.DecimalField(
        db_column="GPA",
        max_digits=4,
        decimal_places=2,
        blank=True,
        null=True,
    )
    disciplinary_status = models.CharField(
        db_column="DisciplinaryStatus",
        max_length=20,
        choices=as_choices(DISCIPLINARY_STATUSES),
    )
    health_condition = models.TextField(db_column="HealthCondition", blank=True, null=True)
    status = models.CharField(
        db_column="Status",
        max_length=20,
        choices=as_choices(STUDENT_STATUSES),
    )

    class Meta:
        managed = False
        db_table = "Student"

    def __str__(self) -> str:
        return f"{self.first_name} {self.last_name}"


class EmergencyContact(models.Model):
    contact_id = models.AutoField(db_column="ContactID", primary_key=True)
    student = models.ForeignKey(
        Student,
        db_column="StudentID",
        on_delete=models.CASCADE,
        related_name="emergency_contacts",
    )
    first_name = models.CharField(db_column="FirstName", max_length=100)
    last_name = models.CharField(db_column="LastName", max_length=100)
    relationship = models.CharField(
        db_column="Relationship",
        max_length=60,
        blank=True,
        null=True,
    )
    phone_number = models.CharField(db_column="PhoneNumber", max_length=20)
    email = models.EmailField(db_column="Email", max_length=150, blank=True, null=True)
    gender = models.CharField(
        db_column="Gender",
        max_length=10,
        choices=VISITOR_GENDER_CHOICES,
        blank=True,
        null=True,
    )
    occupation = models.CharField(
        db_column="Occupation",
        max_length=100,
        blank=True,
        null=True,
    )
    notes = models.TextField(db_column="Notes", blank=True, null=True)
    is_active = models.BooleanField(db_column="IsActive")

    class Meta:
        managed = False
        db_table = "EmergencyContact"


class SystemUser(models.Model):
    user_id = models.AutoField(db_column="UserID", primary_key=True)
    role = models.ForeignKey(
        Role,
        db_column="RoleID",
        on_delete=models.CASCADE,
        related_name="system_users",
    )
    student = models.ForeignKey(
        Student,
        db_column="StudentID",
        on_delete=models.CASCADE,
        related_name="system_users",
        blank=True,
        null=True,
    )
    email = models.EmailField(db_column="Email", max_length=150)
    password_hash = models.CharField(db_column="PasswordHash", max_length=255)
    first_name = models.CharField(
        db_column="FirstName",
        max_length=100,
        blank=True,
        null=True,
    )
    last_name = models.CharField(
        db_column="LastName",
        max_length=100,
        blank=True,
        null=True,
    )
    status = models.CharField(
        db_column="Status",
        max_length=20,
        choices=as_choices(SYSTEM_USER_STATUSES),
    )

    class Meta:
        managed = False
        db_table = "SystemUser"


class Registration(models.Model):
    application_id = models.AutoField(db_column="ApplicationID", primary_key=True)
    student = models.ForeignKey(
        Student,
        db_column="StudentID",
        on_delete=models.CASCADE,
        related_name="registrations",
    )
    semester = models.ForeignKey(
        AcademicSemester,
        db_column="SemesterID",
        on_delete=models.CASCADE,
        related_name="registrations",
        blank=True,
        null=True,
    )
    priority = models.PositiveSmallIntegerField(db_column="Priority", default=5)
    status = models.CharField(
        db_column="Status",
        max_length=20,
        default="Pending",
        choices=as_choices(APPLICATION_STATUSES),
    )
    application_date = models.DateField(db_column="ApplicationDate")
    submitted_at = models.DateTimeField(db_column="SubmittedAt", auto_now_add=True)
    approval_date = models.DateField(db_column="ApprovalDate", blank=True, null=True)
    start_date = models.DateField(db_column="StartDate", blank=True, null=True)
    end_date = models.DateField(db_column="EndDate", blank=True, null=True)
    reason = models.TextField(db_column="Reason", blank=True, null=True)
    notes = models.TextField(db_column="Notes", blank=True, null=True)

    class Meta:
        managed = False
        db_table = "Registration"


class RoomAssignment(models.Model):
    assignment_id = models.AutoField(db_column="AssignmentID", primary_key=True)
    student = models.ForeignKey(
        Student,
        db_column="StudentID",
        on_delete=models.CASCADE,
        related_name="room_assignments",
    )
    room = models.ForeignKey(
        Room,
        db_column="RoomID",
        on_delete=models.CASCADE,
        related_name="assignments",
    )
    bed_slot = models.ForeignKey(
        BedSlot,
        db_column="BedSlotID",
        on_delete=models.CASCADE,
        related_name="assignments",
        blank=True,
        null=True,
    )
    application = models.ForeignKey(
        Registration,
        db_column="ApplicationID",
        on_delete=models.CASCADE,
        related_name="room_assignments",
        blank=True,
        null=True,
    )
    check_in_date = models.DateField(db_column="CheckInDate")
    check_out_date = models.DateField(db_column="CheckOutDate", blank=True, null=True)
    actual_check_out_date = models.DateField(
        db_column="ActualCheckOutDate",
        blank=True,
        null=True,
    )
    status = models.CharField(
        db_column="Status",
        max_length=20,
        choices=as_choices(ROOM_ASSIGNMENT_STATUSES),
    )
    monthly_rent = models.DecimalField(
        db_column="MonthlyRent",
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
    )
    deposit_amount = models.DecimalField(
        db_column="DepositAmount",
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
    )
    contract_duration = models.CharField(
        db_column="ContractDuration",
        max_length=50,
        blank=True,
        null=True,
    )

    class Meta:
        managed = False
        db_table = "RoomAssignment"


class RoomTransfer(models.Model):
    transfer_id = models.AutoField(db_column="TransferID", primary_key=True)
    student = models.ForeignKey(
        Student,
        db_column="StudentID",
        on_delete=models.CASCADE,
        related_name="room_transfers",
    )
    from_room = models.ForeignKey(
        Room,
        db_column="FromRoomID",
        on_delete=models.CASCADE,
        related_name="outgoing_transfers",
    )
    to_room = models.ForeignKey(
        Room,
        db_column="ToRoomID",
        on_delete=models.CASCADE,
        related_name="incoming_transfers",
    )
    reason = models.TextField(db_column="Reason", blank=True, null=True)
    request_date = models.DateField(db_column="RequestDate")
    approval_date = models.DateField(db_column="ApprovalDate", blank=True, null=True)
    effective_move_date = models.DateField(db_column="EffectiveMoveDate", blank=True, null=True)
    status = models.CharField(
        db_column="Status",
        max_length=20,
        default="Pending",
        choices=as_choices(TRANSFER_STATUSES),
    )
    priority_level = models.CharField(
        db_column="PriorityLevel",
        max_length=20,
        default="Normal",
        choices=as_choices(TRANSFER_PRIORITIES),
    )
    notes = models.TextField(db_column="Notes", blank=True, null=True)

    class Meta:
        managed = False
        db_table = "RoomTransfer"


class MaintenanceRequest(models.Model):
    request_id = models.AutoField(db_column="RequestID", primary_key=True)
    room = models.ForeignKey(
        Room,
        db_column="RoomID",
        on_delete=models.CASCADE,
        related_name="maintenance_requests",
        blank=True,
        null=True,
    )
    reported_by_student = models.ForeignKey(
        Student,
        db_column="ReportedByStudentID",
        on_delete=models.CASCADE,
        related_name="maintenance_requests",
        blank=True,
        null=True,
    )
    title = models.CharField(db_column="Title", max_length=200)
    category = models.CharField(db_column="Category", max_length=100, blank=True, null=True)
    priority = models.CharField(
        db_column="Priority",
        max_length=20,
        default="Medium",
        choices=as_choices(MAINTENANCE_PRIORITIES),
    )
    status = models.CharField(
        db_column="Status",
        max_length=20,
        default="Open",
        choices=as_choices(MAINTENANCE_STATUSES),
    )
    description = models.TextField(db_column="Description", blank=True, null=True)
    resolution_note = models.TextField(db_column="ResolutionNote", blank=True, null=True)
    reported_at = models.DateTimeField(db_column="ReportedAt", auto_now_add=True)
    updated_at = models.DateTimeField(db_column="UpdatedAt", auto_now=True)
    estimated_completion_at = models.DateTimeField(
        db_column="EstimatedCompletionAt",
        blank=True,
        null=True,
    )
    resolved_at = models.DateTimeField(db_column="ResolvedAt", blank=True, null=True)
    notes = models.TextField(db_column="Notes", blank=True, null=True)

    class Meta:
        managed = False
        db_table = "MaintenanceRequest"


class MaintenanceLog(models.Model):
    log_id = models.AutoField(db_column="LogID", primary_key=True)
    request = models.ForeignKey(
        MaintenanceRequest,
        db_column="RequestID",
        on_delete=models.CASCADE,
        related_name="maintenance_logs",
    )
    action_taken = models.TextField(db_column="ActionTaken")
    parts_used = models.TextField(db_column="PartsUsed", blank=True, null=True)
    labor_hours = models.DecimalField(
        db_column="LaborHours",
        max_digits=6,
        decimal_places=2,
        blank=True,
        null=True,
    )
    cost = models.DecimalField(
        db_column="Cost",
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
    )
    logged_at = models.DateTimeField(db_column="LoggedAt", auto_now_add=True)

    class Meta:
        managed = False
        db_table = "MaintenanceLog"


class Complaint(models.Model):
    complaint_id = models.AutoField(db_column="ComplaintID", primary_key=True)
    student = models.ForeignKey(
        Student,
        db_column="StudentID",
        on_delete=models.CASCADE,
        related_name="complaints",
    )
    subject = models.CharField(db_column="Subject", max_length=200)
    description = models.TextField(db_column="Description", blank=True, null=True)
    category = models.CharField(db_column="Category", max_length=100, blank=True, null=True)
    priority = models.CharField(
        db_column="Priority",
        max_length=20,
        default="Medium",
        choices=as_choices(COMPLAINT_PRIORITIES),
    )
    status = models.CharField(
        db_column="Status",
        max_length=20,
        default="Open",
        choices=as_choices(COMPLAINT_STATUSES),
    )
    submitted_at = models.DateTimeField(db_column="SubmittedAt", auto_now_add=True)
    updated_at = models.DateTimeField(db_column="UpdatedAt", auto_now=True)
    closed_at = models.DateTimeField(db_column="ClosedAt", blank=True, null=True)
    resolution_notes = models.TextField(db_column="ResolutionNotes", blank=True, null=True)
    satisfaction_rate = models.PositiveSmallIntegerField(
        db_column="SatisfactionRate",
        blank=True,
        null=True,
    )

    class Meta:
        managed = False
        db_table = "Complaint"


class Invoice(models.Model):
    invoice_id = models.AutoField(db_column="InvoiceID", primary_key=True)
    student = models.ForeignKey(
        Student,
        db_column="StudentID",
        on_delete=models.CASCADE,
        related_name="invoices",
    )
    assignment = models.ForeignKey(
        RoomAssignment,
        db_column="AssignmentID",
        on_delete=models.CASCADE,
        related_name="invoices",
        blank=True,
        null=True,
    )
    invoice_type = models.CharField(db_column="InvoiceType", max_length=20)
    total_amount = models.DecimalField(db_column="TotalAmount", max_digits=10, decimal_places=2)
    tax_amount = models.DecimalField(db_column="TaxAmount", max_digits=10, decimal_places=2)
    discount_amount = models.DecimalField(db_column="DiscountAmount", max_digits=10, decimal_places=2)
    late_fee = models.DecimalField(db_column="LateFee", max_digits=10, decimal_places=2)
    due_date = models.DateField(db_column="DueDate")
    payment_status = models.CharField(
        db_column="PaymentStatus",
        max_length=20,
        choices=as_choices(INVOICE_PAYMENT_STATUSES),
    )
    notes = models.TextField(db_column="Notes", blank=True, null=True)
    created_at = models.DateTimeField(db_column="CreatedAt", auto_now_add=True)

    class Meta:
        managed = False
        db_table = "Invoice"

    @property
    def billed_total(self):
        return self.total_amount + self.tax_amount + self.late_fee - self.discount_amount


class PaymentTransaction(models.Model):
    transaction_id = models.AutoField(db_column="TransactionID", primary_key=True)
    invoice = models.ForeignKey(
        Invoice,
        db_column="InvoiceID",
        on_delete=models.CASCADE,
        related_name="transactions",
    )
    student = models.ForeignKey(
        Student,
        db_column="StudentID",
        on_delete=models.CASCADE,
        related_name="payment_transactions",
    )
    payment_amount = models.DecimalField(
        db_column="PaymentAmount",
        max_digits=10,
        decimal_places=2,
    )
    payment_date = models.DateField(db_column="PaymentDate")
    payment_method = models.CharField(db_column="PaymentMethod", max_length=30)
    payment_status = models.CharField(
        db_column="PaymentStatus",
        max_length=20,
        choices=as_choices(PAYMENT_TRANSACTION_STATUSES),
    )
    reference = models.CharField(db_column="Reference", max_length=100, blank=True, null=True)
    payment_description = models.TextField(
        db_column="PaymentDescription",
        blank=True,
        null=True,
    )
    fine_amount = models.DecimalField(
        db_column="FineAmount",
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
    )
    discount_amount = models.DecimalField(
        db_column="DiscountAmount",
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
    )
    receipt_number = models.CharField(
        db_column="ReceiptNumber",
        max_length=60,
        blank=True,
        null=True,
    )

    class Meta:
        managed = False
        db_table = "PaymentTransaction"


class Announcement(models.Model):
    announcement_id = models.AutoField(db_column="AnnouncementID", primary_key=True)
    title = models.CharField(db_column="Title", max_length=200)
    type = models.CharField(db_column="Type", max_length=100, blank=True, null=True)
    message_body = models.TextField(db_column="MessageBody")
    publish_date = models.DateTimeField(db_column="PublishDate")
    expiry_date = models.DateTimeField(db_column="ExpiryDate", blank=True, null=True)
    priority_level = models.CharField(
        db_column="PriorityLevel",
        max_length=20,
        choices=as_choices(ANNOUNCEMENT_PRIORITIES),
    )
    status = models.CharField(
        db_column="Status",
        max_length=20,
        choices=as_choices(ANNOUNCEMENT_STATUSES),
    )

    class Meta:
        managed = False
        db_table = "Announcement"


class StudentAnnouncement(models.Model):
    student = models.ForeignKey(
        Student,
        db_column="StudentID",
        on_delete=models.CASCADE,
        related_name="announcement_receipts",
    )
    announcement = models.ForeignKey(
        Announcement,
        db_column="AnnouncementID",
        on_delete=models.CASCADE,
        related_name="student_receipts",
    )
    is_read = models.BooleanField(db_column="IsRead", default=False)
    read_at = models.DateTimeField(db_column="ReadAt", blank=True, null=True)
    pk = models.CompositePrimaryKey("student", "announcement")

    class Meta:
        managed = False
        db_table = "StudentAnnouncement"


class Notification(models.Model):
    notification_id = models.AutoField(db_column="NotificationID", primary_key=True)
    student = models.ForeignKey(
        Student,
        db_column="StudentID",
        on_delete=models.CASCADE,
        related_name="notifications",
        blank=True,
        null=True,
    )
    title = models.CharField(db_column="Title", max_length=200)
    message = models.TextField(db_column="Message")
    channel = models.CharField(
        db_column="Channel",
        max_length=20,
        choices=as_choices(NOTIFICATION_CHANNELS),
    )
    type = models.CharField(db_column="Type", max_length=100, blank=True, null=True)
    is_read = models.BooleanField(db_column="IsRead", default=False)
    publish_date = models.DateTimeField(db_column="PublishDate", auto_now_add=True)
    expiry_date = models.DateTimeField(db_column="ExpiryDate", blank=True, null=True)
    priority_level = models.CharField(
        db_column="PriorityLevel",
        max_length=20,
        choices=as_choices(ANNOUNCEMENT_PRIORITIES),
    )
    status = models.CharField(
        db_column="Status",
        max_length=20,
        choices=as_choices(NOTIFICATION_STATUSES),
    )

    class Meta:
        managed = False
        db_table = "Notification"


class LeavePermission(models.Model):
    permission_id = models.AutoField(db_column="PermissionID", primary_key=True)
    student = models.ForeignKey(
        Student,
        db_column="StudentID",
        on_delete=models.CASCADE,
        related_name="leave_permissions",
    )
    request_date = models.DateField(db_column="RequestDate")
    start_date = models.DateField(db_column="StartDate")
    end_date = models.DateField(db_column="EndDate")
    reason = models.TextField(db_column="Reason", blank=True, null=True)
    status = models.CharField(
        db_column="Status",
        max_length=20,
        choices=as_choices(LEAVE_PERMISSION_STATUSES),
    )
    approval_date = models.DateField(db_column="ApprovalDate", blank=True, null=True)
    notes = models.TextField(db_column="Notes", blank=True, null=True)

    class Meta:
        managed = False
        db_table = "LeavePermission"


class Visitor(models.Model):
    visitor_id = models.AutoField(db_column="VisitorID", primary_key=True)
    first_name = models.CharField(db_column="FirstName", max_length=100)
    last_name = models.CharField(db_column="LastName", max_length=100)
    national_id = models.CharField(db_column="NationalID", max_length=60, blank=True, null=True)
    gender = models.CharField(
        db_column="Gender",
        max_length=10,
        choices=VISITOR_GENDER_CHOICES,
        blank=True,
        null=True,
    )
    email = models.EmailField(db_column="Email", max_length=150, blank=True, null=True)
    phone_number = models.CharField(db_column="PhoneNumber", max_length=20, blank=True, null=True)
    street = models.CharField(db_column="Street", max_length=150, blank=True, null=True)
    city = models.CharField(db_column="City", max_length=100, blank=True, null=True)
    zip_code = models.CharField(db_column="ZIP", max_length=20, blank=True, null=True)
    country = models.CharField(db_column="Country", max_length=100, blank=True, null=True)
    occupation = models.CharField(db_column="Occupation", max_length=100, blank=True, null=True)
    notes = models.TextField(db_column="Notes", blank=True, null=True)
    is_active = models.BooleanField(db_column="IsActive")
    created_at = models.DateTimeField(db_column="CreatedAt", blank=True, null=True)

    class Meta:
        managed = False
        db_table = "Visitor"

    def __str__(self) -> str:
        return f"{self.first_name} {self.last_name}"


class VisitorPermission(models.Model):
    permission_id = models.AutoField(db_column="PermissionID", primary_key=True)
    visitor = models.ForeignKey(
        Visitor,
        db_column="VisitorID",
        on_delete=models.CASCADE,
        related_name="permissions",
    )
    student = models.ForeignKey(
        Student,
        db_column="StudentID",
        on_delete=models.CASCADE,
        related_name="visitor_permissions",
    )
    request_date = models.DateField(db_column="RequestDate")
    start_date = models.DateField(db_column="StartDate")
    end_date = models.DateField(db_column="EndDate")
    reason = models.TextField(db_column="Reason", blank=True, null=True)
    status = models.CharField(
        db_column="Status",
        max_length=20,
        choices=as_choices(VISITOR_PERMISSION_STATUSES),
    )
    approval_date = models.DateField(db_column="ApprovalDate", blank=True, null=True)
    notes = models.TextField(db_column="Notes", blank=True, null=True)

    class Meta:
        managed = False
        db_table = "VisitorPermission"


class DormService(models.Model):
    service_id = models.AutoField(db_column="ServiceID", primary_key=True)
    building = models.ForeignKey(
        Building,
        db_column="BuildingID",
        on_delete=models.CASCADE,
        related_name="services",
        blank=True,
        null=True,
    )
    name = models.CharField(db_column="Name", max_length=150)
    type = models.CharField(db_column="Type", max_length=100, blank=True, null=True)
    description = models.TextField(db_column="Description", blank=True, null=True)
    service_location = models.CharField(
        db_column="ServiceLocation",
        max_length=200,
        blank=True,
        null=True,
    )
    operating_hours = models.CharField(
        db_column="OperatingHours",
        max_length=100,
        blank=True,
        null=True,
    )
    status = models.CharField(db_column="Status", max_length=20)
    capacity = models.PositiveSmallIntegerField(db_column="Capacity", blank=True, null=True)
    contact_number = models.CharField(
        db_column="ContactNumber",
        max_length=25,
        blank=True,
        null=True,
    )

    class Meta:
        managed = False
        db_table = "DormService"


class Laundry(models.Model):
    laundry_id = models.AutoField(db_column="LaundryID", primary_key=True)
    service = models.ForeignKey(
        DormService,
        db_column="ServiceID",
        on_delete=models.CASCADE,
        related_name="laundry_units",
        blank=True,
        null=True,
    )
    building = models.ForeignKey(
        Building,
        db_column="BuildingID",
        on_delete=models.CASCADE,
        related_name="laundry_units",
        blank=True,
        null=True,
    )
    capacity = models.PositiveSmallIntegerField(db_column="Capacity", blank=True, null=True)
    machine_count = models.PositiveSmallIntegerField(db_column="MachineCount", blank=True, null=True)
    type = models.CharField(
        db_column="Type",
        max_length=20,
        choices=as_choices(LAUNDRY_TYPES),
    )
    class Meta:
        managed = False
        db_table = "Laundry"


class LaundryUsage(models.Model):
    usage_id = models.AutoField(db_column="UsageID", primary_key=True)
    laundry = models.ForeignKey(
        Laundry,
        db_column="LaundryID",
        on_delete=models.CASCADE,
        related_name="usage_records",
    )
    student = models.ForeignKey(
        Student,
        db_column="StudentID",
        on_delete=models.CASCADE,
        related_name="laundry_usage",
    )
    usage_date = models.DateTimeField(db_column="UsageDate")
    duration = models.PositiveSmallIntegerField(db_column="Duration", blank=True, null=True)

    class Meta:
        managed = False
        db_table = "LaundryUsage"


class MealSubscription(models.Model):
    subscription_id = models.AutoField(db_column="SubscriptionID", primary_key=True)
    student = models.ForeignKey(
        Student,
        db_column="StudentID",
        on_delete=models.CASCADE,
        related_name="meal_subscriptions",
    )
    start_date = models.DateField(db_column="StartDate")
    end_date = models.DateField(db_column="EndDate")
    meals_per_day = models.PositiveSmallIntegerField(db_column="MealsPerDay")
    status = models.CharField(
        db_column="Status",
        max_length=20,
        choices=as_choices(MEAL_SUBSCRIPTION_STATUSES),
    )
    dietary_preference = models.CharField(
        db_column="DietaryPreference",
        max_length=100,
        blank=True,
        null=True,
    )
    delivery_time = models.CharField(db_column="DeliveryTime", max_length=50, blank=True, null=True)
    notes = models.TextField(db_column="Notes", blank=True, null=True)
    payment_ref = models.CharField(db_column="PaymentRef", max_length=100, blank=True, null=True)

    class Meta:
        managed = False
        db_table = "MealSubscription"


class MealAttendance(models.Model):
    attendance_id = models.AutoField(db_column="AttendanceID", primary_key=True)
    subscription = models.ForeignKey(
        MealSubscription,
        db_column="SubscriptionID",
        on_delete=models.CASCADE,
        related_name="attendance_records",
    )
    student = models.ForeignKey(
        Student,
        db_column="StudentID",
        on_delete=models.CASCADE,
        related_name="meal_attendance",
    )
    check_in_date_time = models.DateTimeField(db_column="CheckInDateTime")
    meal_type = models.CharField(db_column="MealType", max_length=20, choices=as_choices(MEAL_TYPES))
    meal_date = models.DateField(db_column="MealDate")
    attendance_status = models.CharField(
        db_column="AttendanceStatus",
        max_length=20,
        choices=as_choices(MEAL_ATTENDANCE_STATUSES),
    )
    verification_method = models.CharField(db_column="VerificationMethod", max_length=20)

    class Meta:
        managed = False
        db_table = "MealAttendance"


class LostAndFoundItem(models.Model):
    item_id = models.AutoField(db_column="ItemID", primary_key=True)
    item_name = models.CharField(db_column="ItemName", max_length=150)
    code = models.CharField(db_column="Code", max_length=60, blank=True, null=True)
    description = models.TextField(db_column="Description", blank=True, null=True)
    found_date = models.DateField(db_column="FoundDate", blank=True, null=True)
    report_date = models.DateField(db_column="ReportDate")
    location_found = models.CharField(
        db_column="LocationFound",
        max_length=200,
        blank=True,
        null=True,
    )
    storage_location = models.CharField(
        db_column="StorageLocation",
        max_length=200,
        blank=True,
        null=True,
    )
    status = models.CharField(
        db_column="Status",
        max_length=20,
        choices=as_choices(LOST_FOUND_STATUSES),
    )
    claimed_date = models.DateField(db_column="ClaimedDate", blank=True, null=True)
    notes = models.TextField(db_column="Notes", blank=True, null=True)
    reported_by = models.ForeignKey(
        Student,
        db_column="ReportedBy",
        on_delete=models.CASCADE,
        related_name="lost_found_reports",
        blank=True,
        null=True,
    )

    class Meta:
        managed = False
        db_table = "LostAndFoundItem"


class AccessLog(models.Model):
    log_id = models.AutoField(db_column="LogID", primary_key=True)
    student = models.ForeignKey(
        Student,
        db_column="StudentID",
        on_delete=models.CASCADE,
        related_name="access_logs",
        blank=True,
        null=True,
    )
    building = models.ForeignKey(
        Building,
        db_column="BuildingID",
        on_delete=models.CASCADE,
        related_name="access_logs",
        blank=True,
        null=True,
    )
    log_time = models.DateTimeField(db_column="LogTime")
    access_type = models.CharField(db_column="AccessType", max_length=20, choices=as_choices(ACCESS_TYPES))
    status = models.CharField(db_column="Status", max_length=20, choices=as_choices(ACCESS_STATUSES))
    method = models.CharField(db_column="Method", max_length=20, choices=as_choices(ACCESS_METHODS))
    notes = models.TextField(db_column="Notes", blank=True, null=True)

    class Meta:
        managed = False
        db_table = "AccessLog"


class Penalty(models.Model):
    penalty_id = models.AutoField(db_column="PenaltyID", primary_key=True)
    student = models.ForeignKey(
        Student,
        db_column="StudentID",
        on_delete=models.CASCADE,
        related_name="penalties",
    )
    type = models.CharField(db_column="Type", max_length=100)
    description = models.TextField(db_column="Description", blank=True, null=True)
    amount = models.DecimalField(db_column="Amount", max_digits=10, decimal_places=2)
    penalty_date = models.DateField(db_column="PenaltyDate")
    due_date = models.DateField(db_column="DueDate", blank=True, null=True)
    status = models.CharField(
        db_column="Status",
        max_length=20,
        choices=as_choices(PENALTY_STATUSES),
    )
    reason = models.TextField(db_column="Reason", blank=True, null=True)

    class Meta:
        managed = False
        db_table = "Penalty"


class Blacklist(models.Model):
    blacklist_id = models.AutoField(db_column="BlacklistID", primary_key=True)
    student = models.OneToOneField(
        Student,
        db_column="StudentID",
        on_delete=models.CASCADE,
        related_name="blacklist_record",
    )
    reason = models.TextField(db_column="Reason")
    start_date = models.DateField(db_column="StartDate")
    end_date = models.DateField(db_column="EndDate", blank=True, null=True)
    severity_level = models.CharField(
        db_column="SeverityLevel",
        max_length=20,
        choices=as_choices(BLACKLIST_SEVERITIES),
    )
    status = models.CharField(
        db_column="Status",
        max_length=20,
        choices=as_choices(BLACKLIST_STATUSES),
    )
    is_permanent = models.BooleanField(db_column="IsPermanent")
    appeal_status = models.CharField(
        db_column="AppealStatus",
        max_length=20,
        choices=as_choices(BLACKLIST_APPEAL_STATUSES),
    )
    notes = models.TextField(db_column="Notes", blank=True, null=True)

    class Meta:
        managed = False
        db_table = "Blacklist"


class IncidentReport(models.Model):
    report_id = models.AutoField(db_column="ReportID", primary_key=True)
    student = models.ForeignKey(
        Student,
        db_column="StudentID",
        on_delete=models.CASCADE,
        related_name="incident_reports",
        blank=True,
        null=True,
    )
    title = models.CharField(db_column="Title", max_length=200)
    description = models.TextField(db_column="Description", blank=True, null=True)
    incident_date = models.DateField(db_column="IncidentDate")
    severity_level = models.CharField(
        db_column="SeverityLevel",
        max_length=20,
        choices=as_choices(INCIDENT_SEVERITIES),
    )
    status = models.CharField(
        db_column="Status",
        max_length=20,
        choices=as_choices(INCIDENT_STATUSES),
    )
    resolved_at = models.DateTimeField(db_column="ResolvedAt", blank=True, null=True)
    resolution_notes = models.TextField(db_column="ResolutionNotes", blank=True, null=True)

    class Meta:
        managed = False
        db_table = "IncidentReport"


class RoomInspection(models.Model):
    inspection_id = models.AutoField(db_column="InspectionID", primary_key=True)
    room = models.ForeignKey(
        Room,
        db_column="RoomID",
        on_delete=models.CASCADE,
        related_name="inspections",
    )
    inspection_date = models.DateField(db_column="InspectionDate")
    status = models.CharField(
        db_column="Status",
        max_length=20,
        choices=as_choices(ROOM_INSPECTION_STATUSES),
    )
    cleanliness_score = models.PositiveSmallIntegerField(
        db_column="CleanlinessScore",
        blank=True,
        null=True,
    )
    safety_score = models.PositiveSmallIntegerField(
        db_column="SafetyScore",
        blank=True,
        null=True,
    )
    damage_level = models.CharField(
        db_column="DamageLevel",
        max_length=20,
        choices=as_choices(ROOM_DAMAGE_LEVELS),
    )
    furniture_condition = models.CharField(
        db_column="FurnitureCondition",
        max_length=20,
        choices=as_choices(FURNITURE_CONDITIONS),
    )
    violation_found = models.BooleanField(db_column="ViolationFound")
    follow_up_required = models.BooleanField(db_column="FollowUpRequired")
    follow_up_date = models.DateField(db_column="FollowUpDate", blank=True, null=True)
    notes = models.TextField(db_column="Notes", blank=True, null=True)
    recommendation = models.TextField(db_column="Recommendation", blank=True, null=True)
    next_inspection_date = models.DateField(db_column="NextInspectionDate", blank=True, null=True)

    class Meta:
        managed = False
        db_table = "RoomInspection"

