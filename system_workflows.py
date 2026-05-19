from __future__ import annotations

from datetime import date
from typing import Any

from housing_workflows import reconcile_housing_data


def get_system_integrity_snapshot(db: Any) -> dict[str, int]:
    checks = {
        "resolved_maintenance_missing_timestamp": """
            SELECT COUNT(*)
            FROM MaintenanceRequest
            WHERE Status IN ('Resolved', 'Closed')
              AND ResolvedAt IS NULL
        """,
        "closed_complaints_missing_timestamp": """
            SELECT COUNT(*)
            FROM Complaint
            WHERE Status IN ('Resolved', 'Closed')
              AND ClosedAt IS NULL
        """,
        "resolved_incidents_missing_timestamp": """
            SELECT COUNT(*)
            FROM IncidentReport
            WHERE Status IN ('Resolved', 'Closed')
              AND ResolvedAt IS NULL
        """,
        "decisions_missing_dates": """
            SELECT
                (
                    SELECT COUNT(*)
                    FROM Registration
                    WHERE Status IN ('Approved', 'Rejected', 'Cancelled')
                      AND ApprovalDate IS NULL
                )
                +
                (
                    SELECT COUNT(*)
                    FROM RoomTransfer
                    WHERE Status IN ('Approved', 'Rejected', 'Completed', 'Cancelled')
                      AND ApprovalDate IS NULL
                )
                +
                (
                    SELECT COUNT(*)
                    FROM LeavePermission
                    WHERE Status IN ('Approved', 'Rejected', 'Cancelled')
                      AND ApprovalDate IS NULL
                )
                +
                (
                    SELECT COUNT(*)
                    FROM VisitorPermission
                    WHERE Status IN ('Approved', 'Rejected', 'Expired')
                      AND ApprovalDate IS NULL
                )
        """,
        "invoice_status_mismatch": """
            SELECT COUNT(*)
            FROM Invoice invoice
            LEFT JOIN (
                SELECT InvoiceID, COALESCE(SUM(PaymentAmount), 0) AS PaidAmount
                FROM PaymentTransaction
                WHERE PaymentStatus = 'Completed'
                GROUP BY InvoiceID
            ) payments ON payments.InvoiceID = invoice.InvoiceID
            WHERE invoice.PaymentStatus <> CASE
                WHEN invoice.PaymentStatus = 'Cancelled' THEN 'Cancelled'
                WHEN COALESCE(payments.PaidAmount, 0) >=
                     (invoice.TotalAmount + invoice.TaxAmount + invoice.LateFee - invoice.DiscountAmount)
                THEN 'Paid'
                WHEN invoice.DueDate < CURDATE() THEN 'Overdue'
                WHEN COALESCE(payments.PaidAmount, 0) > 0 THEN 'Partial'
                ELSE 'Unpaid'
            END
        """,
        "completed_transfers_without_new_assignment": """
            SELECT COUNT(*)
            FROM RoomTransfer transfer
            LEFT JOIN RoomAssignment assignment
              ON assignment.StudentID = transfer.StudentID
             AND assignment.RoomID = transfer.ToRoomID
             AND assignment.Status = 'Active'
            WHERE transfer.Status = 'Completed'
              AND assignment.AssignmentID IS NULL
        """,
        "approved_transfers_due_without_move": """
            SELECT COUNT(*)
            FROM RoomTransfer transfer
            LEFT JOIN RoomAssignment assignment
              ON assignment.StudentID = transfer.StudentID
             AND assignment.RoomID = transfer.ToRoomID
             AND assignment.Status = 'Active'
            WHERE transfer.Status = 'Approved'
              AND COALESCE(transfer.EffectiveMoveDate, CURDATE()) <= CURDATE()
              AND assignment.AssignmentID IS NULL
        """,
        "payment_student_mismatch": """
            SELECT COUNT(*)
            FROM PaymentTransaction payment
            JOIN Invoice invoice ON invoice.InvoiceID = payment.InvoiceID
            WHERE payment.StudentID <> invoice.StudentID
        """,
        "student_account_profile_mismatch": """
            SELECT COUNT(*)
            FROM SystemUser user_account
            JOIN Student student ON student.StudentID = user_account.StudentID
            WHERE user_account.Email <> student.Email
               OR COALESCE(user_account.FirstName, '') <> COALESCE(student.FirstName, '')
               OR COALESCE(user_account.LastName, '') <> COALESCE(student.LastName, '')
        """,
        "active_students_without_portal_account": """
            SELECT COUNT(*)
            FROM Student student
            LEFT JOIN SystemUser user_account
              ON user_account.StudentID = student.StudentID
             AND user_account.Status = 'Active'
            LEFT JOIN Role role
              ON role.RoleID = user_account.RoleID
             AND LOWER(role.RoleName) LIKE '%student%'
            WHERE student.Status = 'Active'
              AND role.RoleID IS NULL
        """,
        "stale_visitor_permissions": """
            SELECT COUNT(*)
            FROM VisitorPermission
            WHERE Status = 'Approved'
              AND EndDate < CURDATE()
        """,
        "stale_meal_subscriptions": """
            SELECT COUNT(*)
            FROM MealSubscription
            WHERE Status = 'Active'
              AND EndDate < CURDATE()
        """,
        "pending_penalties_past_due": """
            SELECT COUNT(*)
            FROM Penalty
            WHERE Status = 'Pending'
              AND DueDate IS NOT NULL
              AND DueDate < CURDATE()
        """,
        "room_inspection_rollup_mismatch": """
            SELECT COUNT(*)
            FROM Room room
            JOIN (
                SELECT latest.RoomID, latest.InspectionDate, latest.FurnitureCondition
                FROM RoomInspection latest
                JOIN (
                    SELECT RoomID, MAX(InspectionDate) AS InspectionDate
                    FROM RoomInspection
                    WHERE Status = 'Completed'
                    GROUP BY RoomID
                ) newest
                  ON newest.RoomID = latest.RoomID
                 AND newest.InspectionDate = latest.InspectionDate
                WHERE latest.Status = 'Completed'
            ) inspection ON inspection.RoomID = room.RoomID
            WHERE room.LastInspectionDate <> inspection.InspectionDate
               OR room.LastInspectionDate IS NULL
               OR COALESCE(room.FurnitureCondition, '') <> COALESCE(inspection.FurnitureCondition, '')
        """,
        "building_maintenance_rollup_mismatch": """
            SELECT COUNT(*)
            FROM Building building
            JOIN (
                SELECT room.BuildingID, MAX(DATE(request.ResolvedAt)) AS LastMaintenanceDate
                FROM MaintenanceRequest request
                JOIN Room room ON room.RoomID = request.RoomID
                WHERE request.Status IN ('Resolved', 'Closed')
                  AND request.ResolvedAt IS NOT NULL
                GROUP BY room.BuildingID
            ) maintenance ON maintenance.BuildingID = building.BuildingID
            WHERE building.LastMaintenanceDate <> maintenance.LastMaintenanceDate
               OR building.LastMaintenanceDate IS NULL
        """,
        "assignment_checkout_before_checkin": """
            SELECT COUNT(*)
            FROM RoomAssignment
            WHERE ActualCheckOutDate IS NOT NULL
              AND ActualCheckOutDate < CheckInDate
        """,
        "transfer_move_before_source_checkin": """
            SELECT COUNT(*)
            FROM RoomTransfer transfer
            JOIN RoomAssignment source_assignment
              ON source_assignment.StudentID = transfer.StudentID
             AND source_assignment.RoomID = transfer.FromRoomID
             AND source_assignment.Status = 'Completed'
            WHERE transfer.Status = 'Completed'
              AND transfer.EffectiveMoveDate IS NOT NULL
              AND transfer.EffectiveMoveDate < source_assignment.CheckInDate
        """,
    }
    return {name: int(db.scalar(sql) or 0) for name, sql in checks.items()}


def reconcile_invoice_statuses(db: Any, invoice_id: int | None = None) -> int:
    where_sql = ""
    params: tuple[Any, ...] = ()
    if invoice_id is not None:
        where_sql = "WHERE invoice.InvoiceID = %s"
        params = (invoice_id,)
    with db.transaction() as cursor:
        cursor.execute(
            f"""
            UPDATE Invoice invoice
            LEFT JOIN (
                SELECT InvoiceID, COALESCE(SUM(PaymentAmount), 0) AS PaidAmount
                FROM PaymentTransaction
                WHERE PaymentStatus = 'Completed'
                GROUP BY InvoiceID
            ) payments ON payments.InvoiceID = invoice.InvoiceID
            SET invoice.PaymentStatus = CASE
                WHEN invoice.PaymentStatus = 'Cancelled' THEN 'Cancelled'
                WHEN COALESCE(payments.PaidAmount, 0) >=
                     (invoice.TotalAmount + invoice.TaxAmount + invoice.LateFee - invoice.DiscountAmount)
                THEN 'Paid'
                WHEN invoice.DueDate < CURDATE() THEN 'Overdue'
                WHEN COALESCE(payments.PaidAmount, 0) > 0 THEN 'Partial'
                ELSE 'Unpaid'
            END
            {where_sql}
            """,
            params,
        )
        return cursor.rowcount


def reconcile_operational_data(db: Any) -> dict[str, int]:
    with db.transaction() as cursor:
        cursor.execute(
            """
            UPDATE MaintenanceRequest
            SET ResolvedAt = COALESCE(ResolvedAt, CURRENT_TIMESTAMP)
            WHERE Status IN ('Resolved', 'Closed')
              AND ResolvedAt IS NULL
            """
        )
        maintenance_timestamps = cursor.rowcount

        cursor.execute(
            """
            UPDATE Complaint
            SET ClosedAt = COALESCE(ClosedAt, CURRENT_TIMESTAMP)
            WHERE Status IN ('Resolved', 'Closed')
              AND ClosedAt IS NULL
            """
        )
        complaint_timestamps = cursor.rowcount

        cursor.execute(
            """
            UPDATE IncidentReport
            SET ResolvedAt = COALESCE(ResolvedAt, CURRENT_TIMESTAMP)
            WHERE Status IN ('Resolved', 'Closed')
              AND ResolvedAt IS NULL
            """
        )
        incident_timestamps = cursor.rowcount

        cursor.execute(
            """
            UPDATE Registration
            SET ApprovalDate = COALESCE(ApprovalDate, CURDATE())
            WHERE Status IN ('Approved', 'Rejected', 'Cancelled')
              AND ApprovalDate IS NULL
            """
        )
        registration_decisions = cursor.rowcount

        cursor.execute(
            """
            UPDATE RoomTransfer
            SET ApprovalDate = COALESCE(ApprovalDate, CURDATE())
            WHERE Status IN ('Approved', 'Rejected', 'Completed', 'Cancelled')
              AND ApprovalDate IS NULL
            """
        )
        transfer_decisions = cursor.rowcount

        cursor.execute(
            """
            UPDATE LeavePermission
            SET ApprovalDate = COALESCE(ApprovalDate, CURDATE())
            WHERE Status IN ('Approved', 'Rejected', 'Cancelled')
              AND ApprovalDate IS NULL
            """
        )
        leave_decisions = cursor.rowcount

        cursor.execute(
            """
            UPDATE VisitorPermission
            SET ApprovalDate = COALESCE(ApprovalDate, CURDATE())
            WHERE Status IN ('Approved', 'Rejected', 'Expired')
              AND ApprovalDate IS NULL
            """
        )
        visitor_decisions = cursor.rowcount

        cursor.execute(
            """
            UPDATE VisitorPermission
            SET Status = 'Expired'
            WHERE Status = 'Approved'
              AND EndDate < CURDATE()
            """
        )
        expired_visitor_permissions = cursor.rowcount

        cursor.execute(
            """
            UPDATE MealSubscription
            SET Status = 'Expired'
            WHERE Status = 'Active'
              AND EndDate < CURDATE()
            """
        )
        expired_meal_subscriptions = cursor.rowcount

        cursor.execute(
            """
            UPDATE Penalty
            SET Status = 'Overdue'
            WHERE Status = 'Pending'
              AND DueDate IS NOT NULL
              AND DueDate < CURDATE()
            """
        )
        overdue_penalties = cursor.rowcount

        cursor.execute(
            """
            UPDATE RoomAssignment
            SET ActualCheckOutDate = CheckInDate
            WHERE ActualCheckOutDate IS NOT NULL
              AND ActualCheckOutDate < CheckInDate
            """
        )
        repaired_assignment_dates = cursor.rowcount

        cursor.execute(
            """
            UPDATE RoomTransfer transfer
            JOIN RoomAssignment source_assignment
              ON source_assignment.StudentID = transfer.StudentID
             AND source_assignment.RoomID = transfer.FromRoomID
             AND source_assignment.Status = 'Completed'
            LEFT JOIN RoomAssignment destination_assignment
              ON destination_assignment.StudentID = transfer.StudentID
             AND destination_assignment.RoomID = transfer.ToRoomID
             AND destination_assignment.Status = 'Active'
            SET transfer.EffectiveMoveDate = source_assignment.CheckInDate,
                destination_assignment.CheckInDate = CASE
                    WHEN destination_assignment.AssignmentID IS NOT NULL
                         AND destination_assignment.CheckInDate < source_assignment.CheckInDate
                    THEN source_assignment.CheckInDate
                    ELSE destination_assignment.CheckInDate
                END
            WHERE transfer.Status = 'Completed'
              AND transfer.EffectiveMoveDate IS NOT NULL
              AND transfer.EffectiveMoveDate < source_assignment.CheckInDate
            """
        )
        repaired_transfer_dates = cursor.rowcount

    invoice_statuses = reconcile_invoice_statuses(db)
    synced_student_accounts = sync_student_portal_accounts(db)
    room_inspection_rollups = sync_room_inspection_rollups(db)
    building_maintenance_rollups = sync_building_maintenance_rollups(db)
    completed_due_transfers = complete_due_approved_transfers(db)
    return {
        "maintenance_timestamps": maintenance_timestamps,
        "complaint_timestamps": complaint_timestamps,
        "incident_timestamps": incident_timestamps,
        "registration_decisions": registration_decisions,
        "transfer_decisions": transfer_decisions,
        "leave_decisions": leave_decisions,
        "visitor_decisions": visitor_decisions,
        "expired_visitor_permissions": expired_visitor_permissions,
        "expired_meal_subscriptions": expired_meal_subscriptions,
        "overdue_penalties": overdue_penalties,
        "repaired_assignment_dates": repaired_assignment_dates,
        "repaired_transfer_dates": repaired_transfer_dates,
        "invoice_statuses": invoice_statuses,
        "synced_student_accounts": synced_student_accounts,
        "room_inspection_rollups": room_inspection_rollups,
        "building_maintenance_rollups": building_maintenance_rollups,
        "completed_due_transfers": completed_due_transfers,
    }


def sync_student_portal_accounts(db: Any, student_id: str | None = None) -> int:
    where_sql = ""
    params: tuple[Any, ...] = ()
    if student_id is not None:
        where_sql = "WHERE student.StudentID = %s"
        params = (student_id,)
    with db.transaction() as cursor:
        cursor.execute(
            f"""
            UPDATE SystemUser user_account
            JOIN Student student ON student.StudentID = user_account.StudentID
            SET user_account.Email = student.Email,
                user_account.FirstName = student.FirstName,
                user_account.LastName = student.LastName
            {where_sql}
            """,
            params,
        )
        return cursor.rowcount


def sync_room_inspection_rollups(db: Any) -> int:
    with db.transaction() as cursor:
        cursor.execute(
            """
            UPDATE Room room
            JOIN (
                SELECT latest.RoomID, latest.InspectionDate, latest.FurnitureCondition
                FROM RoomInspection latest
                JOIN (
                    SELECT RoomID, MAX(InspectionDate) AS InspectionDate
                    FROM RoomInspection
                    WHERE Status = 'Completed'
                    GROUP BY RoomID
                ) newest
                  ON newest.RoomID = latest.RoomID
                 AND newest.InspectionDate = latest.InspectionDate
                WHERE latest.Status = 'Completed'
            ) inspection ON inspection.RoomID = room.RoomID
            SET room.LastInspectionDate = inspection.InspectionDate,
                room.FurnitureCondition = inspection.FurnitureCondition
            WHERE room.LastInspectionDate <> inspection.InspectionDate
               OR room.LastInspectionDate IS NULL
               OR COALESCE(room.FurnitureCondition, '') <> COALESCE(inspection.FurnitureCondition, '')
            """
        )
        return cursor.rowcount


def sync_building_maintenance_rollups(db: Any) -> int:
    with db.transaction() as cursor:
        cursor.execute(
            """
            UPDATE Building building
            JOIN (
                SELECT room.BuildingID, MAX(DATE(request.ResolvedAt)) AS LastMaintenanceDate
                FROM MaintenanceRequest request
                JOIN Room room ON room.RoomID = request.RoomID
                WHERE request.Status IN ('Resolved', 'Closed')
                  AND request.ResolvedAt IS NOT NULL
                GROUP BY room.BuildingID
            ) maintenance ON maintenance.BuildingID = building.BuildingID
            SET building.LastMaintenanceDate = maintenance.LastMaintenanceDate
            WHERE building.LastMaintenanceDate <> maintenance.LastMaintenanceDate
               OR building.LastMaintenanceDate IS NULL
            """
        )
        return cursor.rowcount


def complete_due_approved_transfers(db: Any) -> int:
    due_transfers = db.query(
        """
        SELECT transfer.TransferID
        FROM RoomTransfer transfer
        LEFT JOIN RoomAssignment assignment
          ON assignment.StudentID = transfer.StudentID
         AND assignment.RoomID = transfer.ToRoomID
         AND assignment.Status = 'Active'
        WHERE transfer.Status = 'Approved'
          AND COALESCE(transfer.EffectiveMoveDate, CURDATE()) <= CURDATE()
          AND assignment.AssignmentID IS NULL
        ORDER BY transfer.ApprovalDate, transfer.TransferID
        """
    )
    completed = 0
    for row in due_transfers:
        complete_room_transfer(db, int(row["TransferID"]))
        completed += 1
    return completed


def complete_room_transfer(
    db: Any,
    transfer_id: int,
    *,
    effective_move_date: date | None = None,
    notes: str | None = None,
) -> int:
    """Complete a transfer and actually move the student into the destination room."""
    with db.transaction() as cursor:
        cursor.execute(
            """
            SELECT
                transfer.TransferID,
                transfer.StudentID,
                transfer.FromRoomID,
                transfer.ToRoomID,
                transfer.Status,
                transfer.EffectiveMoveDate,
                student.Gender
            FROM RoomTransfer transfer
            JOIN Student student ON student.StudentID = transfer.StudentID
            WHERE transfer.TransferID = %s
            FOR UPDATE
            """,
            (transfer_id,),
        )
        transfer = cursor.fetchone()
        if not transfer:
            raise ValueError("Transfer request not found.")
        if transfer["Status"] == "Completed":
            raise ValueError("This transfer has already been completed.")
        if transfer["Status"] not in {"Pending", "Approved"}:
            raise ValueError("Only pending or approved transfers can be completed.")

        cursor.execute(
            """
            SELECT *
            FROM RoomAssignment
            WHERE StudentID = %s
              AND RoomID = %s
              AND Status = 'Active'
            ORDER BY CheckInDate DESC, AssignmentID DESC
            LIMIT 1
            FOR UPDATE
            """,
            (transfer["StudentID"], transfer["FromRoomID"]),
        )
        current_assignment = cursor.fetchone()
        if not current_assignment:
            raise ValueError("The student has no active assignment in the transfer's source room.")

        cursor.execute(
            """
            SELECT
                room.RoomID,
                room.Capacity,
                COALESCE(room.CurrentOccupancy, 0) AS CurrentOccupancy,
                room.Status,
                room_type.BasePrice AS MonthlyRent,
                COALESCE(room_type.SecurityDeposit, 0) AS DepositAmount,
                building.Status AS BuildingStatus,
                building.GenderAllowed AS BuildingGenderAllowed
            FROM Room room
            JOIN Building building ON building.BuildingID = room.BuildingID
            LEFT JOIN RoomType room_type ON room_type.RoomTypeID = room.RoomTypeID
            WHERE room.RoomID = %s
            FOR UPDATE
            """,
            (transfer["ToRoomID"],),
        )
        destination = cursor.fetchone()
        if not destination:
            raise ValueError("Destination room not found.")
        if destination["BuildingStatus"] != "Active":
            raise ValueError("Destination building is not active.")
        if destination["Status"] not in {"Available", "Occupied"}:
            raise ValueError("Destination room is not assignable.")
        if destination["CurrentOccupancy"] >= destination["Capacity"]:
            raise ValueError("Destination room is already full.")
        if destination["BuildingGenderAllowed"] not in {"Mixed", transfer["Gender"]}:
            raise ValueError("Destination building is not eligible for this student.")

        cursor.execute(
            """
            SELECT COUNT(*) AS TotalBeds
            FROM BedSlot
            WHERE RoomID = %s
            """,
            (transfer["ToRoomID"],),
        )
        total_beds = int(cursor.fetchone()["TotalBeds"])
        chosen_bed_id = None
        if total_beds:
            cursor.execute(
                """
                SELECT BedSlotID
                FROM BedSlot
                WHERE RoomID = %s
                  AND IsOccupied = 0
                  AND IsReserved = 0
                ORDER BY BedNumber, BedSlotID
                LIMIT 1
                FOR UPDATE
                """,
                (transfer["ToRoomID"],),
            )
            free_bed = cursor.fetchone()
            if not free_bed:
                raise ValueError("Destination room has bed slots, but none are currently free.")
            chosen_bed_id = free_bed["BedSlotID"]
        requested_move_date = effective_move_date or transfer["EffectiveMoveDate"] or date.today()
        move_date = max(requested_move_date, current_assignment["CheckInDate"])

        cursor.execute(
            """
            UPDATE RoomAssignment
            SET Status = 'Completed',
                ActualCheckOutDate = COALESCE(ActualCheckOutDate, %s)
            WHERE AssignmentID = %s
            """,
            (move_date, current_assignment["AssignmentID"]),
        )
        cursor.execute(
            """
            UPDATE OccupancyLog
            SET EndDate = COALESCE(EndDate, %s)
            WHERE AssignmentID = %s
              AND EndDate IS NULL
            """,
            (move_date, current_assignment["AssignmentID"]),
        )

        cursor.execute(
            """
            INSERT INTO RoomAssignment (
                StudentID,
                RoomID,
                BedSlotID,
                CheckInDate,
                Status,
                MonthlyRent,
                DepositAmount,
                ContractDuration,
                Notes
            )
            VALUES (%s, %s, %s, %s, 'Active', %s, %s, %s, %s)
            """,
            (
                transfer["StudentID"],
                transfer["ToRoomID"],
                chosen_bed_id,
                move_date,
                destination["MonthlyRent"],
                destination["DepositAmount"],
                current_assignment.get("ContractDuration"),
                notes or current_assignment.get("Notes"),
            ),
        )
        new_assignment_id = int(cursor.lastrowid)
        cursor.execute(
            """
            INSERT INTO OccupancyLog (StudentID, RoomID, AssignmentID, StartDate)
            VALUES (%s, %s, %s, %s)
            """,
            (transfer["StudentID"], transfer["ToRoomID"], new_assignment_id, move_date),
        )
        if current_assignment.get("BedSlotID"):
            cursor.execute(
                """
                UPDATE BedSlot
                SET IsOccupied = 0
                WHERE BedSlotID = %s
                """,
                (current_assignment["BedSlotID"],),
            )
        if chosen_bed_id:
            cursor.execute(
                """
                UPDATE BedSlot
                SET IsOccupied = 1
                WHERE BedSlotID = %s
                """,
                (chosen_bed_id,),
            )
        cursor.execute(
            """
            UPDATE Room room
            LEFT JOIN (
                SELECT RoomID, COUNT(*) AS ActiveCount
                FROM RoomAssignment
                WHERE Status = 'Active'
                  AND RoomID IN (%s, %s)
                GROUP BY RoomID
            ) active_assignments ON active_assignments.RoomID = room.RoomID
            SET room.CurrentOccupancy = COALESCE(active_assignments.ActiveCount, 0),
                room.Status = CASE
                    WHEN room.Status NOT IN ('Available', 'Occupied') THEN room.Status
                    WHEN COALESCE(active_assignments.ActiveCount, 0) >= room.Capacity
                         AND room.Capacity > 0
                    THEN 'Occupied'
                    ELSE 'Available'
                END
            WHERE room.RoomID IN (%s, %s)
            """,
            (
                transfer["FromRoomID"],
                transfer["ToRoomID"],
                transfer["FromRoomID"],
                transfer["ToRoomID"],
            ),
        )
        cursor.execute(
            """
            UPDATE RoomTransfer
            SET Status = 'Completed',
                ApprovalDate = COALESCE(ApprovalDate, CURDATE()),
                EffectiveMoveDate = %s,
                Notes = COALESCE(%s, Notes)
            WHERE TransferID = %s
            """,
            (move_date, notes, transfer_id),
        )
        cursor.execute(
            """
            INSERT INTO Notification (
                StudentID,
                Title,
                Message,
                Channel,
                Type,
                IsRead,
                PriorityLevel,
                Status
            )
            VALUES (%s, %s, %s, 'In-App', 'Housing', 0, 'High', 'Sent')
            """,
            (
                transfer["StudentID"],
                "Room transfer completed",
                "Your room transfer was completed and your new room assignment is now active.",
            ),
        )

    reconcile_housing_data(db)
    return new_assignment_id
