from django.urls import path

from . import views

app_name = "students"

urlpatterns = [
    path("", views.landing, name="landing"),
    path("register/", views.register, name="register"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("my-room/", views.my_room, name="my_room"),
    path("roommates/", views.roommates, name="roommates"),
    path("requests/", views.requests_hub, name="requests"),
    path("requests/maintenance/new/", views.maintenance_create, name="maintenance_create"),
    path("requests/maintenance/<int:request_id>/cancel/", views.maintenance_request_cancel, name="maintenance_cancel"),
    path("requests/complaints/new/", views.complaint_create, name="complaint_create"),
    path("requests/complaints/<int:complaint_id>/cancel/", views.complaint_cancel, name="complaint_cancel"),
    path("announcements/", views.announcements, name="announcements"),
    path("announcements/<int:announcement_id>/read/", views.mark_announcement_read, name="mark_announcement_read"),
    path("notifications/<int:notification_id>/read/", views.mark_notification_read, name="mark_notification_read"),
    path("profile/", views.profile, name="profile"),
    path("profile/emergency-contacts/new/", views.emergency_contact_create, name="emergency_contact_create"),
    path(
        "profile/emergency-contacts/<int:contact_id>/deactivate/",
        views.emergency_contact_deactivate,
        name="emergency_contact_deactivate",
    ),
    path("payments/", views.payments, name="payments"),
    path("records/", views.records, name="records"),
    path("applications/", views.applications, name="applications"),
    path("applications/new/", views.application_create, name="application_create"),
    path("applications/<int:application_id>/cancel/", views.application_cancel, name="application_cancel"),
    path("permissions/", views.permissions, name="permissions"),
    path("permissions/leave/new/", views.leave_permission_create, name="leave_permission_create"),
    path("permissions/leave/<int:permission_id>/cancel/", views.leave_permission_cancel, name="leave_permission_cancel"),
    path(
        "permissions/visitors/new/",
        views.visitor_permission_create,
        name="visitor_permission_create",
    ),
    path("permissions/visitors/<int:permission_id>/cancel/", views.visitor_permission_cancel, name="visitor_permission_cancel"),
    path("services/", views.services, name="services"),
    path("services/lost-found/new/", views.lost_found_create, name="lost_found_create"),
    path("services/lost-found/<int:item_id>/cancel/", views.lost_found_cancel, name="lost_found_cancel"),
    path("room-transfer/new/", views.room_transfer_create, name="room_transfer_create"),
    path("room-transfer/<int:transfer_id>/cancel/", views.room_transfer_cancel, name="room_transfer_cancel"),
    path("api/me/", views.api_me, name="api_me"),
    path("api/my-room/", views.api_my_room, name="api_my_room"),
    path("api/requests/", views.api_requests, name="api_requests"),
    path("api/announcements/", views.api_announcements, name="api_announcements"),
]
