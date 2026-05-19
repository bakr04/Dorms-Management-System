# Schema compliance map

## Supported student-facing features

| Website area | Existing schema tables used | Notes |
| --- | --- | --- |
| Registration / login | `Student`, `Role`, `SystemUser` | Uses `SystemUser.PasswordHash`; only student-linked users may log in |
| Dashboard | `Student`, `RoomAssignment`, `Room`, `Building`, `MaintenanceRequest`, `Complaint`, `Invoice`, `Announcement`, `StudentAnnouncement`, `Notification`, `Registration` | Personalized counts and summaries only |
| My Room | `RoomAssignment`, `Room`, `Building`, `RoomType`, `BedSlot`, `RoomTransfer` | Active assignment + read-only available rooms |
| Roommates | `RoomAssignment`, `Student`, `AcademicProgram` | Roommates are inferred from other active assignments in the same room |
| Requests | `MaintenanceRequest`, `MaintenanceLog`, `Complaint` | Students only see and submit their own rows, plus admin-added work-log updates for their requests |
| Announcements / notifications | `Announcement`, `StudentAnnouncement`, `Notification` | Announcement read state uses the existing junction table |
| Profile | `Student`, `Faculty`, `AcademicProgram`, `EmergencyContact`, `RoomAssignment` | Editing is limited to student-safe contact/address/health fields |
| Payments | `Invoice`, `PaymentTransaction` | Read-only billing history with billed total, paid total, and balance due |
| My Records | `Penalty`, `Blacklist`, `IncidentReport` | Student-visible disciplinary / conduct records tied to their own `StudentID` |
| Applications | `Registration`, `AcademicSemester`, `Student` | Student dorm applications supported by the normalized schema; the application form captures current GPA into `Student.GPA` while profile contact data remains on `Student` |
| Room transfer | `RoomTransfer`, `RoomAssignment`, `Room` | Students may request a move from their current room to an available room |
| Permissions | `LeavePermission`, `Visitor`, `VisitorPermission` | Students may submit leave and visitor requests and view only their own records |
| Services | `DormService`, `MealSubscription`, `MealAttendance`, `LaundryUsage`, `Laundry`, `AccessLog`, `LostAndFoundItem` | Active dorm services, personal activity, and student-submitted found-item reports |
| Room inspections | `RoomInspection`, `RoomAssignment`, `Room` | Recent inspections for the student's current room |

## Features requested in the brief but not supported by the current schema

### Direct messages / chat

No current table stores student-to-student conversations or messages, so the portal does not implement them.

**Optional schema addition, not implemented:**

```sql
CREATE TABLE Conversation (
    ConversationID INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    CreatedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE ConversationParticipant (
    ConversationID INT UNSIGNED NOT NULL,
    StudentID VARCHAR(20) NOT NULL,
    JoinedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ConversationID, StudentID),
    FOREIGN KEY (ConversationID) REFERENCES Conversation(ConversationID),
    FOREIGN KEY (StudentID) REFERENCES Student(StudentID)
);

CREATE TABLE Message (
    MessageID INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    ConversationID INT UNSIGNED NOT NULL,
    SenderStudentID VARCHAR(20) NOT NULL,
    MessageBody TEXT NOT NULL,
    SentAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ReadAt TIMESTAMP NULL,
    FOREIGN KEY (ConversationID) REFERENCES Conversation(ConversationID),
    FOREIGN KEY (SenderStudentID) REFERENCES Student(StudentID)
);
```

### Dorm community discussions

No current thread/post/community table exists, so the portal does not implement discussion boards.

**Optional schema addition, not implemented:**

```sql
CREATE TABLE CommunityThread (
    ThreadID INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    BuildingID INT UNSIGNED NULL,
    CreatedByStudentID VARCHAR(20) NOT NULL,
    Title VARCHAR(200) NOT NULL,
    CreatedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (BuildingID) REFERENCES Building(BuildingID),
    FOREIGN KEY (CreatedByStudentID) REFERENCES Student(StudentID)
);

CREATE TABLE CommunityPost (
    PostID INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    ThreadID INT UNSIGNED NOT NULL,
    StudentID VARCHAR(20) NOT NULL,
    Body TEXT NOT NULL,
    CreatedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (ThreadID) REFERENCES CommunityThread(ThreadID),
    FOREIGN KEY (StudentID) REFERENCES Student(StudentID)
);
```

## Privacy and authorization rules implemented

- No password hash is ever rendered.
- Account creation stores the login email in `SystemUser.Email` and a one-way Django password hash in `SystemUser.PasswordHash`.
- Students can only access their own:
  - maintenance requests
  - complaints
  - notifications
  - invoices
  - payment transactions
  - applications
  - transfer requests
  - leave permissions
  - visitor permissions
  - laundry usage
  - meal attendance
  - access logs
  - lost-and-found reports
  - penalties
  - blacklist records
  - incident reports
- Roommate visibility is limited to names and academic program only.
- Protected identity or operational fields such as `RoleID`, `RoomAssignment`, payment status, `StudentID`, `DisciplinaryStatus`, and staff-only attributes are not student-editable.
- Announcement read state is tracked through the real composite key on `StudentAnnouncement (StudentID, AnnouncementID)`, so one student can correctly read many announcements.
