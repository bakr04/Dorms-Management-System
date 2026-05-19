from __future__ import annotations

from datetime import date
from typing import Any


def get_housing_integrity_snapshot(db: Any) -> dict[str, int]:
    """Return integrity counters that can be corrected or reviewed by housing staff."""
    checks = {
        "approved_without_assignment": """
            SELECT COUNT(*)
            FROM Registration reg
            LEFT JOIN RoomAssignment ra ON ra.ApplicationID = reg.ApplicationID
            WHERE reg.Status = 'Approved'
              AND ra.AssignmentID IS NULL
        """,
        "missing_occupancy_logs": """
            SELECT COUNT(*)
            FROM RoomAssignment ra
            LEFT JOIN OccupancyLog ol ON ol.AssignmentID = ra.AssignmentID
            WHERE ra.Status = 'Active'
              AND ol.LogID IS NULL
        """,
        "occupancy_mismatch": """
            SELECT COUNT(*)
            FROM Room r
            LEFT JOIN (
                SELECT RoomID, COUNT(*) AS ActiveCount
                FROM RoomAssignment
                WHERE Status = 'Active'
                GROUP BY RoomID
            ) active_assignments ON active_assignments.RoomID = r.RoomID
            WHERE COALESCE(r.CurrentOccupancy, 0) <> COALESCE(active_assignments.ActiveCount, 0)
        """,
        "room_status_mismatch": """
            SELECT COUNT(*)
            FROM Room r
            LEFT JOIN (
                SELECT RoomID, COUNT(*) AS ActiveCount
                FROM RoomAssignment
                WHERE Status = 'Active'
                GROUP BY RoomID
            ) active_assignments ON active_assignments.RoomID = r.RoomID
            WHERE r.Status IN ('Available', 'Occupied')
              AND r.Status <> CASE
                    WHEN COALESCE(active_assignments.ActiveCount, 0) >= r.Capacity
                         AND r.Capacity > 0
                    THEN 'Occupied'
                    ELSE 'Available'
                END
        """,
        "bed_occupancy_mismatch": """
            SELECT COUNT(*)
            FROM BedSlot bed
            LEFT JOIN (
                SELECT BedSlotID, COUNT(*) AS ActiveCount
                FROM RoomAssignment
                WHERE Status = 'Active'
                  AND BedSlotID IS NOT NULL
                GROUP BY BedSlotID
            ) active_assignments ON active_assignments.BedSlotID = bed.BedSlotID
            WHERE bed.IsOccupied <> CASE
                    WHEN COALESCE(active_assignments.ActiveCount, 0) > 0 THEN 1
                    ELSE 0
                END
        """,
        "active_assignments_missing_bed_slots": """
            SELECT COUNT(*)
            FROM RoomAssignment assignment
            WHERE assignment.Status = 'Active'
              AND assignment.BedSlotID IS NULL
              AND EXISTS (
                    SELECT 1
                    FROM BedSlot bed
                    WHERE bed.RoomID = assignment.RoomID
                )
        """,
        "orphan_bed_slots": """
            SELECT COUNT(*)
            FROM BedSlot bed
            LEFT JOIN Room room ON room.RoomID = bed.RoomID
            WHERE room.RoomID IS NULL
        """,
        "assignment_bed_room_mismatch": """
            SELECT COUNT(*)
            FROM RoomAssignment assignment
            JOIN BedSlot bed ON bed.BedSlotID = assignment.BedSlotID
            WHERE assignment.BedSlotID IS NOT NULL
              AND assignment.RoomID <> bed.RoomID
        """,
        "assignment_application_student_mismatch": """
            SELECT COUNT(*)
            FROM RoomAssignment assignment
            JOIN Registration registration ON registration.ApplicationID = assignment.ApplicationID
            WHERE assignment.ApplicationID IS NOT NULL
              AND assignment.StudentID <> registration.StudentID
        """,
        "active_assignment_in_unavailable_room": """
            SELECT COUNT(*)
            FROM RoomAssignment assignment
            JOIN Room room ON room.RoomID = assignment.RoomID
            JOIN Building building ON building.BuildingID = room.BuildingID
            WHERE assignment.Status = 'Active'
              AND (
                    room.Status NOT IN ('Available', 'Occupied')
                    OR building.Status <> 'Active'
                )
        """,
        "active_room_over_capacity": """
            SELECT COUNT(*)
            FROM Room room
            JOIN (
                SELECT RoomID, COUNT(*) AS ActiveCount
                FROM RoomAssignment
                WHERE Status = 'Active'
                GROUP BY RoomID
            ) active_assignments ON active_assignments.RoomID = room.RoomID
            WHERE active_assignments.ActiveCount > room.Capacity
        """,
    }
    return {name: int(db.scalar(sql) or 0) for name, sql in checks.items()}


def reconcile_housing_data(db: Any) -> dict[str, int]:
    """Repair safe derived housing values without inventing missing parent records."""
    with db.transaction() as cursor:
        cursor.execute(
            """
            INSERT INTO OccupancyLog (StudentID, RoomID, AssignmentID, StartDate)
            SELECT ra.StudentID, ra.RoomID, ra.AssignmentID, ra.CheckInDate
            FROM RoomAssignment ra
            LEFT JOIN OccupancyLog ol ON ol.AssignmentID = ra.AssignmentID
            WHERE ra.Status = 'Active'
              AND ol.LogID IS NULL
            """
        )
        inserted_logs = cursor.rowcount

        cursor.execute(
            """
            UPDATE OccupancyLog ol
            JOIN RoomAssignment ra ON ra.AssignmentID = ol.AssignmentID
            SET ol.EndDate = COALESCE(ra.ActualCheckOutDate, ra.CheckOutDate, CURDATE())
            WHERE ra.Status <> 'Active'
              AND ol.EndDate IS NULL
            """
        )
        closed_logs = cursor.rowcount

        cursor.execute(
            """
            UPDATE BedSlot bed
            LEFT JOIN (
                SELECT BedSlotID, COUNT(*) AS ActiveCount
                FROM RoomAssignment
                WHERE Status = 'Active'
                  AND BedSlotID IS NOT NULL
                GROUP BY BedSlotID
            ) active_assignments ON active_assignments.BedSlotID = bed.BedSlotID
            SET bed.IsOccupied = CASE
                WHEN COALESCE(active_assignments.ActiveCount, 0) > 0 THEN 1
                ELSE 0
            END
            WHERE bed.IsOccupied <> CASE
                WHEN COALESCE(active_assignments.ActiveCount, 0) > 0 THEN 1
                ELSE 0
            END
            """
        )
        updated_beds = cursor.rowcount

        cursor.execute(
            """
            SELECT assignment.AssignmentID, assignment.RoomID
            FROM RoomAssignment assignment
            WHERE assignment.Status = 'Active'
              AND assignment.BedSlotID IS NULL
              AND EXISTS (
                    SELECT 1
                    FROM BedSlot bed
                    WHERE bed.RoomID = assignment.RoomID
                )
            ORDER BY assignment.RoomID, assignment.CheckInDate, assignment.AssignmentID
            FOR UPDATE
            """
        )
        missing_bed_assignments = cursor.fetchall()
        assigned_missing_beds = 0
        for assignment in missing_bed_assignments:
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
                (assignment["RoomID"],),
            )
            free_bed = cursor.fetchone()
            if not free_bed:
                continue
            cursor.execute(
                """
                UPDATE RoomAssignment
                SET BedSlotID = %s
                WHERE AssignmentID = %s
                  AND BedSlotID IS NULL
                """,
                (free_bed["BedSlotID"], assignment["AssignmentID"]),
            )
            if cursor.rowcount:
                cursor.execute(
                    """
                    UPDATE BedSlot
                    SET IsOccupied = 1
                    WHERE BedSlotID = %s
                    """,
                    (free_bed["BedSlotID"],),
                )
                assigned_missing_beds += 1

        cursor.execute(
            """
            UPDATE Room room
            LEFT JOIN (
                SELECT RoomID, COUNT(*) AS ActiveCount
                FROM RoomAssignment
                WHERE Status = 'Active'
                GROUP BY RoomID
            ) active_assignments ON active_assignments.RoomID = room.RoomID
            SET room.CurrentOccupancy = COALESCE(active_assignments.ActiveCount, 0)
            WHERE COALESCE(room.CurrentOccupancy, 0) <> COALESCE(active_assignments.ActiveCount, 0)
            """
        )
        updated_room_occupancy = cursor.rowcount

        cursor.execute(
            """
            UPDATE Room room
            LEFT JOIN (
                SELECT RoomID, COUNT(*) AS ActiveCount
                FROM RoomAssignment
                WHERE Status = 'Active'
                GROUP BY RoomID
            ) active_assignments ON active_assignments.RoomID = room.RoomID
            SET room.Status = CASE
                WHEN COALESCE(active_assignments.ActiveCount, 0) >= room.Capacity
                     AND room.Capacity > 0
                THEN 'Occupied'
                ELSE 'Available'
            END
            WHERE room.Status IN ('Available', 'Occupied')
              AND room.Status <> CASE
                    WHEN COALESCE(active_assignments.ActiveCount, 0) >= room.Capacity
                         AND room.Capacity > 0
                    THEN 'Occupied'
                    ELSE 'Available'
                END
            """
        )
        updated_room_status = cursor.rowcount

    return {
        "inserted_logs": inserted_logs,
        "closed_logs": closed_logs,
        "updated_beds": updated_beds,
        "assigned_missing_beds": assigned_missing_beds,
        "updated_room_occupancy": updated_room_occupancy,
        "updated_room_status": updated_room_status,
    }


def list_assignable_rooms(db: Any, student_id: str) -> list[dict[str, Any]]:
    return db.query(
        """
        SELECT
            room.RoomID,
            room.RoomNumber,
            room.FloorNumber,
            room.Capacity,
            COALESCE(room.CurrentOccupancy, 0) AS CurrentOccupancy,
            room_type.BasePrice AS MonthlyRent,
            room_type.SecurityDeposit AS DepositAmount,
            building.BuildingName,
            building.BuildingCode,
            room_type.Name AS RoomTypeName
        FROM Student student
        CROSS JOIN Room room
        JOIN Building building ON building.BuildingID = room.BuildingID
        LEFT JOIN RoomType room_type ON room_type.RoomTypeID = room.RoomTypeID
        WHERE student.StudentID = %s
          AND room.Status IN ('Available', 'Occupied')
          AND COALESCE(room.CurrentOccupancy, 0) < room.Capacity
          AND building.Status = 'Active'
          AND building.GenderAllowed IN ('Mixed', student.Gender)
          AND (
                NOT EXISTS (
                    SELECT 1
                    FROM BedSlot bed
                    WHERE bed.RoomID = room.RoomID
                )
                OR EXISTS (
                    SELECT 1
                    FROM BedSlot bed
                    WHERE bed.RoomID = room.RoomID
                      AND bed.IsOccupied = 0
                      AND bed.IsReserved = 0
                )
          )
        ORDER BY building.BuildingName, room.RoomNumber
        """,
        (student_id,),
    )


def list_available_beds(db: Any, room_id: int) -> list[dict[str, Any]]:
    return db.query(
        """
        SELECT BedSlotID, BedNumber, BedPosition, BedType
        FROM BedSlot
        WHERE RoomID = %s
          AND IsOccupied = 0
          AND IsReserved = 0
        ORDER BY BedNumber, BedSlotID
        """,
        (room_id,),
    )


def list_application_queue(db: Any) -> list[dict[str, Any]]:
    return db.query(
        """
        SELECT
            reg.ApplicationID,
            reg.StudentID,
            CONCAT(student.FirstName, ' ', student.LastName) AS StudentName,
            student.Gender,
            student.Email,
            reg.Status,
            reg.ApplicationDate,
            reg.StartDate,
            reg.EndDate,
            semester.Name AS SemesterName,
            semester.AcademicYear,
            student.PhoneNumber,
            student.City,
            student.Country,
            reg.Priority,
            student.GPA
        FROM Registration reg
        JOIN Student student ON student.StudentID = reg.StudentID
        LEFT JOIN AcademicSemester semester ON semester.SemesterID = reg.SemesterID
        LEFT JOIN RoomAssignment assignment ON assignment.ApplicationID = reg.ApplicationID
        WHERE reg.Status IN ('Pending', 'Waitlisted', 'Approved')
          AND assignment.AssignmentID IS NULL
        ORDER BY
            CASE reg.Status
                WHEN 'Pending' THEN 1
                WHEN 'Waitlisted' THEN 2
                ELSE 3
            END,
            reg.Priority,
            reg.ApplicationDate,
            reg.ApplicationID
        """
    )


def list_room_transfer_queue(db: Any) -> list[dict[str, Any]]:
    return db.query(
        """
        SELECT
            transfer.TransferID,
            transfer.StudentID,
            CONCAT(student.FirstName, ' ', student.LastName) AS StudentName,
            transfer.FromRoomID,
            from_room.RoomNumber AS FromRoomNumber,
            from_building.BuildingName AS FromBuildingName,
            transfer.ToRoomID,
            to_room.RoomNumber AS ToRoomNumber,
            to_building.BuildingName AS ToBuildingName,
            transfer.RequestDate,
            transfer.EffectiveMoveDate,
            transfer.Status,
            transfer.PriorityLevel,
            transfer.Reason
        FROM RoomTransfer transfer
        JOIN Student student ON student.StudentID = transfer.StudentID
        JOIN Room from_room ON from_room.RoomID = transfer.FromRoomID
        JOIN Building from_building ON from_building.BuildingID = from_room.BuildingID
        JOIN Room to_room ON to_room.RoomID = transfer.ToRoomID
        JOIN Building to_building ON to_building.BuildingID = to_room.BuildingID
        WHERE transfer.Status IN ('Pending', 'Approved')
        ORDER BY
            CASE transfer.PriorityLevel
                WHEN 'Urgent' THEN 1
                WHEN 'High' THEN 2
                WHEN 'Normal' THEN 3
                ELSE 4
            END,
            transfer.RequestDate,
            transfer.TransferID
        """
    )


def approve_application_with_assignment(
    db: Any,
    application_id: int,
    room_id: int,
    *,
    bed_slot_id: int | None = None,
    check_in_date: date | None = None,
    assigned_by: int | None = None,
    contract_duration: str | None = None,
    notes: str | None = None,
) -> int:
    """Approve a housing application and create the linked records atomically."""
    with db.transaction() as cursor:
        cursor.execute(
            """
            SELECT
                reg.ApplicationID,
                reg.StudentID,
                reg.Status,
                reg.StartDate,
                semester.StartDate AS SemesterStartDate,
                student.Status AS StudentStatus,
                student.Gender
            FROM Registration reg
            JOIN Student student ON student.StudentID = reg.StudentID
            LEFT JOIN AcademicSemester semester ON semester.SemesterID = reg.SemesterID
            WHERE reg.ApplicationID = %s
            FOR UPDATE
            """,
            (application_id,),
        )
        application = cursor.fetchone()
        if not application:
            raise ValueError("Application not found.")
        if application["StudentStatus"] != "Active":
            raise ValueError("Only active students can receive a room assignment.")
        if application["Status"] not in {"Pending", "Waitlisted", "Approved"}:
            raise ValueError("Only pending, waitlisted, or already approved applications can be assigned.")

        cursor.execute(
            """
            SELECT AssignmentID
            FROM RoomAssignment
            WHERE StudentID = %s
              AND Status = 'Active'
            LIMIT 1
            FOR UPDATE
            """,
            (application["StudentID"],),
        )
        if cursor.fetchone():
            raise ValueError("This student already has an active room assignment.")

        cursor.execute(
            """
            SELECT
                room.RoomID,
                room.RoomNumber,
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
            (room_id,),
        )
        room = cursor.fetchone()
        if not room:
            raise ValueError("Room not found.")
        if room["BuildingStatus"] != "Active":
            raise ValueError("Only rooms in active buildings can be assigned.")
        if room["Status"] not in {"Available", "Occupied"}:
            raise ValueError("This room is not assignable right now.")
        if room["CurrentOccupancy"] >= room["Capacity"]:
            raise ValueError("This room is already full.")
        if room["BuildingGenderAllowed"] not in {"Mixed", application["Gender"]}:
            raise ValueError("This building is not eligible for the student's gender.")

        cursor.execute(
            """
            SELECT COUNT(*) AS TotalBeds
            FROM BedSlot
            WHERE RoomID = %s
            """,
            (room_id,),
        )
        total_beds = int(cursor.fetchone()["TotalBeds"])

        chosen_bed_id = bed_slot_id
        if chosen_bed_id is not None:
            cursor.execute(
                """
                SELECT BedSlotID, IsOccupied, IsReserved
                FROM BedSlot
                WHERE BedSlotID = %s
                  AND RoomID = %s
                FOR UPDATE
                """,
                (chosen_bed_id, room_id),
            )
            bed = cursor.fetchone()
            if not bed:
                raise ValueError("Selected bed does not belong to the chosen room.")
            if bed["IsOccupied"] or bed["IsReserved"]:
                raise ValueError("Selected bed is no longer available.")
        elif total_beds:
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
                (room_id,),
            )
            free_bed = cursor.fetchone()
            if not free_bed:
                raise ValueError("This room has bed slots, but none are currently free.")
            chosen_bed_id = free_bed["BedSlotID"]

        chosen_check_in = (
            check_in_date
            or application["StartDate"]
            or application["SemesterStartDate"]
            or date.today()
        )
        cursor.execute(
            """
            UPDATE Registration
            SET Status = 'Approved',
                ApprovalDate = COALESCE(ApprovalDate, CURDATE())
            WHERE ApplicationID = %s
            """,
            (application_id,),
        )
        cursor.execute(
            """
            INSERT INTO RoomAssignment (
                StudentID,
                RoomID,
                BedSlotID,
                AssignedBy,
                ApplicationID,
                CheckInDate,
                Status,
                MonthlyRent,
                DepositAmount,
                ContractDuration,
                Notes
            )
            VALUES (%s, %s, %s, %s, %s, %s, 'Active', %s, %s, %s, %s)
            """,
            (
                application["StudentID"],
                room_id,
                chosen_bed_id,
                assigned_by,
                application_id,
                chosen_check_in,
                room["MonthlyRent"],
                room["DepositAmount"],
                contract_duration or None,
                notes or None,
            ),
        )
        assignment_id = int(cursor.lastrowid)

        cursor.execute(
            """
            INSERT INTO OccupancyLog (StudentID, RoomID, AssignmentID, StartDate)
            VALUES (%s, %s, %s, %s)
            """,
            (application["StudentID"], room_id, assignment_id, chosen_check_in),
        )
        if chosen_bed_id is not None:
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
                  AND RoomID = %s
                GROUP BY RoomID
            ) active_assignments ON active_assignments.RoomID = room.RoomID
            SET room.CurrentOccupancy = COALESCE(active_assignments.ActiveCount, 0),
                room.Status = CASE
                    WHEN COALESCE(active_assignments.ActiveCount, 0) >= room.Capacity
                         AND room.Capacity > 0
                    THEN 'Occupied'
                    ELSE 'Available'
                END
            WHERE room.RoomID = %s
            """,
            (room_id, room_id),
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
                application["StudentID"],
                "Dorm application approved",
                f"Your dorm application was approved and a room assignment is now active.",
            ),
        )
    return assignment_id
