"""Mock FHIR client for DEV_MODE — returns realistic sample data."""


class MockFHIRClient:
    """Drop-in replacement for EpicFHIRClient that returns sample data."""

    async def close(self) -> None:
        pass

    async def list_appointments(
        self, patient_id: str, date_from: str, date_to: str | None = None, status: str = "booked"
    ) -> list[dict]:
        return [
            {
                "resourceType": "Appointment",
                "id": "mock-appt-001",
                "status": "booked",
                "start": "2026-03-28T10:00:00-03:00",
                "end": "2026-03-28T10:30:00-03:00",
                "participant": [
                    {"actor": {"reference": f"Patient/{patient_id}", "display": "Jason Argonaut"}, "status": "accepted"},
                    {"actor": {"reference": "Practitioner/mock-dr-001", "display": "Dra. María García"}, "status": "accepted"},
                ],
            },
            {
                "resourceType": "Appointment",
                "id": "mock-appt-002",
                "status": "booked",
                "start": "2026-04-05T14:30:00-03:00",
                "end": "2026-04-05T15:00:00-03:00",
                "participant": [
                    {"actor": {"reference": f"Patient/{patient_id}", "display": "Jason Argonaut"}, "status": "accepted"},
                    {"actor": {"reference": "Practitioner/mock-dr-002", "display": "Dr. Carlos López"}, "status": "accepted"},
                ],
            },
        ]

    async def search_practitioner(self, name: str) -> list[dict]:
        practitioners = [
            {"resourceType": "Practitioner", "id": "mock-dr-001", "name": [{"given": ["María"], "family": "García", "prefix": ["Dra."]}]},
            {"resourceType": "Practitioner", "id": "mock-dr-002", "name": [{"given": ["Carlos"], "family": "López", "prefix": ["Dr."]}]},
            {"resourceType": "Practitioner", "id": "mock-dr-003", "name": [{"given": ["Ana"], "family": "Martínez", "prefix": ["Dra."]}]},
        ]
        return [p for p in practitioners if name.lower() in str(p["name"]).lower()] or practitioners[:1]

    async def search_schedules(self, practitioner_id: str) -> list[dict]:
        return [{"resourceType": "Schedule", "id": f"mock-sched-{practitioner_id}", "actor": [{"reference": f"Practitioner/{practitioner_id}"}]}]

    async def search_slots(
        self, schedule_id: str, start_from: str, start_to: str | None = None, status: str = "free"
    ) -> list[dict]:
        return [
            {"resourceType": "Slot", "id": "mock-slot-001", "schedule": {"reference": f"Schedule/{schedule_id}"}, "status": "free", "start": "2026-04-01T09:00:00-03:00", "end": "2026-04-01T09:30:00-03:00"},
            {"resourceType": "Slot", "id": "mock-slot-002", "schedule": {"reference": f"Schedule/{schedule_id}"}, "status": "free", "start": "2026-04-01T10:00:00-03:00", "end": "2026-04-01T10:30:00-03:00"},
            {"resourceType": "Slot", "id": "mock-slot-003", "schedule": {"reference": f"Schedule/{schedule_id}"}, "status": "free", "start": "2026-04-02T11:00:00-03:00", "end": "2026-04-02T11:30:00-03:00"},
        ]

    async def book_appointment(self, slot_id: str, patient_id: str, practitioner_id: str) -> dict:
        return {
            "resourceType": "Appointment",
            "id": "mock-appt-new",
            "status": "booked",
            "slot": [{"reference": f"Slot/{slot_id}"}],
            "participant": [
                {"actor": {"reference": f"Patient/{patient_id}"}, "status": "accepted"},
                {"actor": {"reference": f"Practitioner/{practitioner_id}"}, "status": "accepted"},
            ],
        }

    async def read_appointment(self, appointment_id: str) -> dict:
        return {
            "resourceType": "Appointment",
            "id": appointment_id,
            "status": "booked",
            "start": "2026-03-28T10:00:00-03:00",
            "end": "2026-03-28T10:30:00-03:00",
            "participant": [
                {"actor": {"reference": "Patient/mock", "display": "Jason Argonaut"}, "status": "accepted"},
                {"actor": {"reference": "Practitioner/mock-dr-001", "display": "Dra. María García"}, "status": "accepted"},
            ],
        }

    async def cancel_appointment(self, appointment_id: str) -> dict:
        appt = await self.read_appointment(appointment_id)
        appt["status"] = "cancelled"
        return appt
