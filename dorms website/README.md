# GU Dorms Student Portal

Student-facing Django website for the existing `GUDorms` MySQL database. It sits beside the existing desktop admin GUI and intentionally does **not** create staff dashboards or new database tables.

## What is included

- Student registration, login, logout, and protected pages through the existing `Student`, `Role`, and `SystemUser` tables
- Dashboard, room view, roommate visibility, maintenance requests with admin work-log updates, complaints, announcements, notifications, profile editing, emergency contacts, payments, penalties, student records, dorm applications with GPA capture, room-transfer requests, leave permissions, visitor permissions, service history, room inspections, and lost-and-found reporting
- Read-only JSON endpoints for:
  - `/api/me/`
  - `/api/my-room/`
  - `/api/requests/`
  - `/api/announcements/`
- Signed-cookie sessions so the site does not require extra Django-owned tables inside the supplied schema

## Run locally

1. Make sure MySQL is running and that `GU Dorms.sql` has already been executed.
2. From this folder, install dependencies:

   ```powershell
   pip install -r requirements.txt
   ```

3. The project automatically reuses the parent folder's `db_config.json`. You can also override any setting with environment variables:

   ```powershell
   $env:MYSQL_HOST="localhost"
   $env:MYSQL_PORT="3306"
   $env:MYSQL_USER="root"
   $env:MYSQL_PASSWORD="your-password"
   $env:MYSQL_DATABASE="gudorms"
   ```

4. Start the site:

   ```powershell
   python manage.py runserver
   ```

5. Open `http://127.0.0.1:8000/`.

   If port `8000` is already occupied on your computer, use:

   ```powershell
   python manage.py runserver 8001
   ```

   and open `http://127.0.0.1:8001/` instead.

## Important implementation notes

- Do **not** run `makemigrations` or `migrate` for the portal models. They are unmanaged mappings to the already-existing schema, so the app intentionally keeps only an empty `migrations/__init__.py` package marker.
- Student registration supports both:
  - new students, by inserting into `Student` and `SystemUser`
  - existing students who do not yet have a portal account, only when the submitted identity fields match the existing `Student` row
- A default `Student Resident` role is created automatically the first time it is needed, so a freshly created schema can accept student registrations without manual seed data.
- Registration now captures the student profile fields the normalized schema can safely accept from students themselves, including optional contact/address/identity values already present in `Student`.
- Dorm applications collect the student's current GPA and save it back to `Student.GPA`, so housing staff see one consistent academic value across the system.
- Dorm applications now store only application-specific values in `Registration`; phone and address data stay normalized on `Student`.
- Room availability and transfer requests now reject inactive buildings, full rooms, and rooms with configured bed slots but no free assignable bed.
- The room page shows the student's contracted assignment rent/deposit, not a later-edited room-type price.
- Login email is stored in `SystemUser.Email`.
- Passwords are hashed with Django's password hasher and stored only as hashes in `SystemUser.PasswordHash`; plaintext passwords are never saved.
- Students can only query or mutate rows tied to their own `StudentID`.
- Read markers for announcements use the real composite primary key in `StudentAnnouncement (StudentID, AnnouncementID)`.
- Admin-created student records such as penalties, incidents, blacklist entries, room inspections, maintenance work logs, and important status changes now have matching student-facing surfaces instead of living only in the desktop GUI.
- Visitor permissions follow the current schema exactly and are stored as date ranges, with no unsupported hour fields assumed by the portal.

See [`SCHEMA_MAPPING.md`](./SCHEMA_MAPPING.md) for the exact page-to-table mapping and unsupported features.
