from __future__ import annotations

from django import forms
from django.contrib.auth.hashers import make_password
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, F, Q
from django.utils import timezone

from .choices import (
    ACTIVE_APPLICATION_STATUSES,
    ACTIVE_TRANSFER_STATUSES,
    COMPLAINT_PRIORITIES,
    GENDER_CHOICES,
    MAINTENANCE_PRIORITIES,
    TRANSFER_PRIORITIES,
    VISITOR_GENDER_CHOICES,
    as_choices,
)
from .models import (
    AcademicProgram,
    AcademicSemester,
    Blacklist,
    Faculty,
    MaintenanceRequest,
    Complaint,
    EmergencyContact,
    LeavePermission,
    LostAndFoundItem,
    Registration,
    Role,
    Room,
    RoomTransfer,
    Student,
    SystemUser,
    Visitor,
    VisitorPermission,
)


class LoginForm(forms.Form):
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput)

    def clean_email(self) -> str:
        return self.cleaned_data["email"].strip().lower()


class StudentRegistrationForm(forms.Form):
    student_id = forms.CharField(max_length=20, label="Student ID")
    first_name = forms.CharField(max_length=100)
    last_name = forms.CharField(max_length=100)
    email = forms.EmailField()
    date_of_birth = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    gender = forms.ChoiceField(choices=GENDER_CHOICES)
    faculty = forms.ModelChoiceField(queryset=Faculty.objects.order_by("name"), required=False)
    program = forms.ModelChoiceField(
        queryset=AcademicProgram.objects.none(),
        required=False,
        empty_label="Select a faculty first",
    )
    national_id_or_passport = forms.CharField(max_length=60, required=False, label="National ID / passport")
    phone_number = forms.CharField(max_length=20, required=False)
    nationality = forms.CharField(max_length=100, required=False)
    street = forms.CharField(max_length=150, required=False)
    city = forms.CharField(max_length=100, required=False)
    zip_code = forms.CharField(max_length=20, required=False, label="ZIP")
    country = forms.CharField(max_length=100, required=False)
    academic_year = forms.IntegerField(required=False, min_value=1, max_value=20)
    password = forms.CharField(widget=forms.PasswordInput)
    confirm_password = forms.CharField(widget=forms.PasswordInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        faculty_id = None
        if self.is_bound:
            faculty_id = self.data.get(self.add_prefix("faculty")) or None
        elif self.initial.get("faculty"):
            faculty = self.initial["faculty"]
            faculty_id = getattr(faculty, "faculty_id", faculty)

        if faculty_id:
            self.fields["program"].queryset = AcademicProgram.objects.filter(
                faculty_id=faculty_id,
                status="Active",
            ).order_by("name")

    def clean_student_id(self) -> str:
        student_id = self.cleaned_data["student_id"].strip()
        if " " in student_id:
            raise ValidationError("Student ID cannot contain spaces.")
        return student_id

    def clean_email(self) -> str:
        return self.cleaned_data["email"].strip().lower()

    def clean(self):
        cleaned = super().clean()
        password = cleaned.get("password")
        confirm_password = cleaned.get("confirm_password")
        email = cleaned.get("email")
        student_id = cleaned.get("student_id")
        program = cleaned.get("program")
        faculty = cleaned.get("faculty")

        if password and confirm_password and password != confirm_password:
            self.add_error("confirm_password", "Passwords do not match.")

        if password:
            try:
                validate_password(password)
            except ValidationError as exc:
                self.add_error("password", exc)

        if program and faculty and program.faculty_id != faculty.faculty_id:
            self.add_error("program", "Selected program does not belong to the selected faculty.")

        if email and SystemUser.objects.filter(email__iexact=email).exists():
            self.add_error("email", "An account already exists for this email.")

        existing_student = None
        if student_id:
            existing_student = Student.objects.filter(student_id=student_id).first()
            if existing_student and SystemUser.objects.filter(student=existing_student).exists():
                self.add_error("student_id", "This student already has a portal account.")

        if existing_student:
            if existing_student.status != "Active":
                self.add_error("student_id", "This student record is not active.")
            checks = {
                "email": existing_student.email.lower() if existing_student.email else None,
                "first_name": existing_student.first_name,
                "last_name": existing_student.last_name,
                "date_of_birth": existing_student.date_of_birth,
                "gender": existing_student.gender,
            }
            for field_name, expected_value in checks.items():
                if field_name in cleaned:
                    form_value = cleaned.get(field_name)
                    # Handle None comparisons properly
                    if form_value != expected_value and not (form_value is None and expected_value is None):
                        self.add_error(
                            field_name,
                            "This does not match the existing student record.",
                        )
        elif email and Student.objects.filter(email__iexact=email).exists():
            self.add_error(
                "email",
                "This email already belongs to another student record. Use that student's ID to claim the account.",
            )

        national_id_or_passport = cleaned.get("national_id_or_passport")
        if (
            national_id_or_passport
            and not existing_student
            and Student.objects.filter(national_id_or_passport=national_id_or_passport).exists()
        ):
            self.add_error(
                "national_id_or_passport",
                "This national ID or passport is already linked to another student record.",
            )

        cleaned["existing_student"] = existing_student
        return cleaned

    @staticmethod
    def _student_role() -> Role | None:
        role = (
            Role.objects.filter(role_name__iexact="Student Resident").first()
            or Role.objects.filter(role_name__iexact="Student").first()
            or Role.objects.filter(role_name__icontains="student").first()
        )
        if role is not None:
            return role
        role, _ = Role.objects.get_or_create(role_name="Student Resident")
        return role

    @transaction.atomic
    def save(self) -> SystemUser:
        student = self.cleaned_data["existing_student"]
        if student is None:
            faculty = self.cleaned_data.get("faculty")
            program = self.cleaned_data.get("program")
            if program and faculty is None:
                faculty = program.faculty
            student = Student.objects.create(
                student_id=self.cleaned_data["student_id"],
                faculty=faculty,
                program=program,
                first_name=self.cleaned_data["first_name"],
                last_name=self.cleaned_data["last_name"],
                email=self.cleaned_data["email"],
                national_id_or_passport=self.cleaned_data.get("national_id_or_passport") or None,
                date_of_birth=self.cleaned_data["date_of_birth"],
                gender=self.cleaned_data["gender"],
                nationality=self.cleaned_data.get("nationality") or None,
                phone_number=self.cleaned_data.get("phone_number") or None,
                street=self.cleaned_data.get("street") or None,
                city=self.cleaned_data.get("city") or None,
                zip_code=self.cleaned_data.get("zip_code") or None,
                country=self.cleaned_data.get("country") or None,
                academic_year=self.cleaned_data.get("academic_year") or None,
                disciplinary_status="Clear",
                status="Active",
            )

        role = self._student_role()
        return SystemUser.objects.create(
            role=role,
            student=student,
            email=student.email,
            password_hash=make_password(self.cleaned_data["password"]),
            first_name=student.first_name,
            last_name=student.last_name,
            status="Active",
        )


class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = Student
        fields = [
            "phone_number",
            "street",
            "city",
            "zip_code",
            "country",
            "nationality",
            "health_condition",
        ]
        widgets = {
            "health_condition": forms.Textarea(attrs={"rows": 4}),
        }


class EmergencyContactForm(forms.ModelForm):
    class Meta:
        model = EmergencyContact
        fields = [
            "first_name",
            "last_name",
            "relationship",
            "phone_number",
            "email",
            "gender",
            "occupation",
            "notes",
        ]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def save_for_student(self, student: Student) -> EmergencyContact:
        contact = self.save(commit=False)
        contact.student = student
        contact.is_active = True
        contact.save()
        return contact


class DormApplicationForm(forms.ModelForm):
    gpa = forms.DecimalField(
        label="GPA",
        max_digits=4,
        decimal_places=2,
        min_value=0,
        max_value=4,
        help_text="Enter your current GPA on the 0.00 to 4.00 scale.",
        widget=forms.NumberInput(attrs={"step": "0.01", "min": "0", "max": "4"}),
    )

    class Meta:
        model = Registration
        fields = [
            "gpa",
            "semester",
            "start_date",
            "end_date",
            "reason",
        ]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "reason": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, student: Student, **kwargs):
        super().__init__(*args, **kwargs)
        self.student = student
        today = timezone.localdate()
        self.fields["semester"].queryset = (
            AcademicSemester.objects.filter(status__in=["Upcoming", "Active"])
            .filter(end_date__gte=today)
            .filter(
                Q(status="Active")
                | (
                    (Q(registration_open_date__isnull=True) | Q(registration_open_date__lte=today))
                    & (Q(registration_close_date__isnull=True) | Q(registration_close_date__gte=today))
                )
            )
            .order_by("-start_date")
        )
        self.fields["semester"].required = False
        self.fields["gpa"].initial = student.gpa

    def clean(self):
        cleaned = super().clean()
        semester = cleaned.get("semester")
        start_date = cleaned.get("start_date")
        end_date = cleaned.get("end_date")
        active_blacklist_exists = Blacklist.objects.filter(
            student=self.student,
            status="Active",
        ).filter(
            Q(end_date__isnull=True) | Q(end_date__gt=timezone.localdate())
        ).exists()
        if active_blacklist_exists:
            raise ValidationError("You cannot submit a dorm application while an active blacklist record is in place.")
        if start_date and end_date and end_date < start_date:
            self.add_error("end_date", "End date must be on or after the start date.")
        if not semester and not (start_date and end_date):
            raise ValidationError("Choose an open semester or provide both start and end dates.")
        if semester and Registration.objects.filter(
            student=self.student,
            semester=semester,
            status__in=ACTIVE_APPLICATION_STATUSES,
        ).exists():
            self.add_error("semester", "You already have an active application for this semester.")
        return cleaned

    def save(self, commit=True):
        application = super().save(commit=False)
        application.student = self.student
        application.application_date = timezone.localdate()
        application.status = "Pending"
        application.priority = 5
        if application.semester_id:
            if application.start_date is None:
                application.start_date = application.semester.start_date
            if application.end_date is None:
                application.end_date = application.semester.end_date
        if commit:
            with transaction.atomic():
                gpa = self.cleaned_data["gpa"]
                if self.student.gpa != gpa:
                    self.student.gpa = gpa
                    self.student.save(update_fields=["gpa"])
                application.save()
        return application


class MaintenanceRequestForm(forms.ModelForm):
    class Meta:
        model = MaintenanceRequest
        fields = ["title", "category", "priority", "description"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 5}),
        }

    def __init__(self, *args, student: Student, room: Room | None, **kwargs):
        super().__init__(*args, **kwargs)
        self.student = student
        self.room = room
        self.fields["description"].required = True
        self.fields["priority"].widget = forms.Select(choices=as_choices(MAINTENANCE_PRIORITIES))

    def save(self, commit=True):
        request = super().save(commit=False)
        request.reported_by_student = self.student
        request.room = self.room
        request.status = "Open"
        if commit:
            request.save()
        return request


class ComplaintForm(forms.ModelForm):
    class Meta:
        model = Complaint
        fields = ["subject", "category", "priority", "description"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 5}),
        }

    def __init__(self, *args, student: Student, **kwargs):
        super().__init__(*args, **kwargs)
        self.student = student
        self.fields["description"].required = True
        self.fields["priority"].widget = forms.Select(choices=as_choices(COMPLAINT_PRIORITIES))

    def save(self, commit=True):
        complaint = super().save(commit=False)
        complaint.student = self.student
        complaint.status = "Open"
        if commit:
            complaint.save()
        return complaint


class RoomTransferForm(forms.ModelForm):
    class Meta:
        model = RoomTransfer
        fields = ["to_room", "reason", "priority_level"]
        widgets = {
            "reason": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, student: Student, from_room: Room, **kwargs):
        super().__init__(*args, **kwargs)
        self.student = student
        self.from_room = from_room
        eligible_buildings = Q(building__gender_allowed="Mixed") | Q(
            building__gender_allowed=student.gender
        )
        self.fields["to_room"].queryset = (
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
            .filter(Q(current_occupancy__isnull=True) | Q(current_occupancy__lt=F("capacity")))
            .filter(building__status="Active")
            .filter(eligible_buildings)
            .filter(Q(total_bed_slots=0) | Q(free_bed_slots__gt=0))
            .exclude(room_id=from_room.room_id)
            .order_by("building__building_name", "room_number")
        )
        self.fields["priority_level"].widget = forms.Select(choices=as_choices(TRANSFER_PRIORITIES))

    def clean(self):
        cleaned = super().clean()
        to_room = cleaned.get("to_room")
        if to_room:
            to_room.refresh_from_db(fields=["status", "current_occupancy", "capacity"])
            if to_room.status not in {"Available", "Occupied"} or to_room.available_beds < 1:
                self.add_error("to_room", "This room is no longer available.")
            elif to_room.beds.exists() and not to_room.beds.filter(
                is_occupied=False,
                is_reserved=False,
            ).exists():
                self.add_error("to_room", "This room no longer has a free bed slot.")
        if to_room and RoomTransfer.objects.filter(
            student=self.student,
            from_room=self.from_room,
            to_room=to_room,
            status__in=ACTIVE_TRANSFER_STATUSES,
        ).exists():
            self.add_error("to_room", "You already have an active transfer request for this room.")
        return cleaned

    def save(self, commit=True):
        transfer = super().save(commit=False)
        transfer.student = self.student
        transfer.from_room = self.from_room
        transfer.request_date = timezone.localdate()
        transfer.status = "Pending"
        if commit:
            transfer.save()
        return transfer


class LeavePermissionForm(forms.ModelForm):
    class Meta:
        model = LeavePermission
        fields = ["start_date", "end_date", "reason"]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "reason": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, student: Student, **kwargs):
        super().__init__(*args, **kwargs)
        self.student = student
        self.fields["reason"].required = True

    def clean(self):
        cleaned = super().clean()
        start_date = cleaned.get("start_date")
        end_date = cleaned.get("end_date")
        if start_date and end_date and end_date < start_date:
            self.add_error("end_date", "End date must be on or after the start date.")
        return cleaned

    def save(self, commit=True):
        permission = super().save(commit=False)
        permission.student = self.student
        permission.request_date = timezone.localdate()
        permission.status = "Pending"
        if commit:
            permission.save()
        return permission


class VisitorPermissionRequestForm(forms.Form):
    visitor_first_name = forms.CharField(max_length=100, label="Visitor first name")
    visitor_last_name = forms.CharField(max_length=100, label="Visitor last name")
    visitor_national_id = forms.CharField(max_length=60, required=False, label="Visitor national ID")
    visitor_gender = forms.ChoiceField(
        choices=(("", "---------"),) + VISITOR_GENDER_CHOICES,
        required=False,
        label="Visitor gender",
    )
    visitor_email = forms.EmailField(required=False, label="Visitor email")
    visitor_phone_number = forms.CharField(max_length=20, required=False, label="Visitor phone")
    visitor_occupation = forms.CharField(max_length=100, required=False, label="Visitor occupation")
    start_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    end_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    reason = forms.CharField(widget=forms.Textarea(attrs={"rows": 4}))

    def __init__(self, *args, student: Student, **kwargs):
        super().__init__(*args, **kwargs)
        self.student = student

    def clean(self):
        cleaned = super().clean()
        start_date = cleaned.get("start_date")
        end_date = cleaned.get("end_date")
        if start_date and end_date and end_date < start_date:
            self.add_error("end_date", "End date must be on or after the start date.")
        return cleaned

    @transaction.atomic
    def save(self) -> VisitorPermission:
        national_id = self.cleaned_data.get("visitor_national_id") or None
        visitor = Visitor.objects.filter(national_id=national_id).first() if national_id else None
        if visitor is None:
            visitor = Visitor.objects.create(
                first_name=self.cleaned_data["visitor_first_name"],
                last_name=self.cleaned_data["visitor_last_name"],
                national_id=national_id,
                gender=self.cleaned_data.get("visitor_gender") or None,
                email=self.cleaned_data.get("visitor_email") or None,
                phone_number=self.cleaned_data.get("visitor_phone_number") or None,
                occupation=self.cleaned_data.get("visitor_occupation") or None,
                is_active=True,
            )
        return VisitorPermission.objects.create(
            visitor=visitor,
            student=self.student,
            request_date=timezone.localdate(),
            start_date=self.cleaned_data["start_date"],
            end_date=self.cleaned_data["end_date"],
            reason=self.cleaned_data["reason"],
            status="Pending",
        )


class LostAndFoundReportForm(forms.ModelForm):
    class Meta:
        model = LostAndFoundItem
        fields = ["item_name", "description", "found_date", "location_found"]
        widgets = {
            "found_date": forms.DateInput(attrs={"type": "date"}),
            "description": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, student: Student, **kwargs):
        super().__init__(*args, **kwargs)
        self.student = student
        self.fields["description"].required = True

    def save(self, commit=True):
        item = super().save(commit=False)
        item.report_date = timezone.localdate()
        item.status = "Found"
        item.reported_by = self.student
        if commit:
            item.save()
        return item
