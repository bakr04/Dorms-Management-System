# Galala Dorms Administration

This is a green Galala University Tkinter desktop dashboard for the `GUDorms` MySQL database schema. It opens as a dorm-operations dashboard for admins and departments, with advanced table editing available when needed.

## Setup

1. Make sure MySQL is running and that you already executed `GU Dorms.sql`.
2. Install the Python dependency:

   ```powershell
   pip install -r requirements.txt
   ```

3. Run the app:

   ```powershell
   python gudorms_admin_gui.py
   ```

4. The app auto-connects using `db_config.json` or the default `GUDorms` settings.
5. Use `Settings` from the dashboard/sidebar footer to change MySQL credentials.

## What it does

- Reads table columns, primary keys, enum values, and foreign keys from MySQL.
- Auto-connects on startup and keeps database settings out of the main dashboard.
- Shows a focused dorm-admin dashboard with KPIs, priority queues, activity snapshots, and management tools.
- Reuses the schema's reporting views on the dashboard where they fit best, including capacity, active maintenance, overdue invoices, actionable inspections, expiring contracts, and active blacklist snapshots.
- Adds a dedicated `Reporting Views` workspace so every schema view can be opened, searched, refreshed, and exported without writing SQL by hand.
- Adds a dedicated Housing Operations workflow for safe application approval + room assignment.
- Adds a System Integrity workspace for cross-module drift checks shared by the admin GUI and student website.
- Reconciles safe derived housing data from active assignments: room occupancy, room availability/occupied state, bed occupancy, and missing occupancy logs.
- Fills missing active bed assignments when the room has a clearly free bed, keeping bed-level and room-level occupancy aligned.
- Reconciles safe operational data too: resolution timestamps, approval dates, invoice status, and linked student portal account profile fields.
- Flags integrity issues the app should not silently guess at, such as orphaned bed slots or approved applications that still need a chosen room.
- Flags active students who exist in `Student` but do not yet have a usable student portal account in `SystemUser`, which prevents the website from silently appearing empty for imported records.
- Converts due approved room transfers into real move workflows instead of allowing a status-only edit that leaves the student in the old room.
- Adds a visible transfer queue inside Housing Operations with an `Approve + Move` action for the admin.
- Blocks illogical edits such as approving an application without assignment, payment records whose student does not match the invoice, and duplicate active assignments.
- Repairs and validates more derived operational data: visitor-pass expiry, meal-plan expiry, overdue penalties, room-inspection rollups, building-maintenance rollups, and impossible assignment date order.
- Creates in-app student notifications for important admin-side changes such as penalties, incidents, application decisions, permission decisions, finance updates, and request status changes.
- Adds department workspaces for Housing, Finance, People & Staff, Maintenance & Assets, Security & Visitors, Services, Buildings & Rooms, and Admin.
- Provides safer  CRUD screens for the schema tables.
- Keeps advanced schema-aware CRUD inside the Advanced Data Manager.
- Keeps sidebar modules stable even if MySQL returns table names in lowercase.
- Uses dropdowns for enum fields, booleans, and foreign key IDs where possible.
- Locks primary keys while editing existing rows.
- Locks auto-increment and MySQL-managed timestamp/date fields.
- Validates required values and common date/number formats before writing.
- Exports the currently visible table rows to CSV.
- Uses deliberate manual refresh controls instead of background auto-refresh, so the UI never steals focus while an admin is editing.
- Bundles the Galala University logo at `assets/galala_university_logo.png`.

The Settings dialog saves connection settings to `db_config.json`. It only saves the password if the `save password` checkbox is enabled.

## Student website

A separate Django student portal now lives in [`dorms website`](./dorms%20website). It reuses the same MySQL database and focuses on student interaction only: authentication, room details, roommates, requests, maintenance work-log updates, announcements, profile editing, payments, penalties, student records, applications, transfer requests, leave/visitor permissions, service history, room inspections, and lost-and-found reporting.
