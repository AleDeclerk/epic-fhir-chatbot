"""Epic FHIR STU3 async client adapter for scheduling workflows.

Uses STU3 because Epic's scheduling operations ($find, $book) and
resources (Slot, Schedule) are only available in STU3, not R4.
"""

import asyncio
import logging
import random

import httpx

logger = logging.getLogger(__name__)


class FHIRError(Exception):
    """Base FHIR error with OperationOutcome details."""

    def __init__(self, status_code: int, outcome: dict | None = None):
        self.status_code = status_code
        self.outcome = outcome
        issues = outcome.get("issue", []) if outcome else []
        self.diagnostics = "; ".join(
            i.get("diagnostics", "Unknown error") for i in issues
        )
        super().__init__(f"FHIR {status_code}: {self.diagnostics}")


class FHIRAuthError(FHIRError):
    """401/403 — token expired or insufficient scopes."""
    pass


class FHIRNotFoundError(FHIRError):
    """404 — resource not found."""
    pass


class FHIRRateLimitError(FHIRError):
    """429 — rate limited, retry with backoff."""
    pass


class EpicFHIRClient:
    """Async FHIR client for Epic STU3 sandbox (scheduling workflows)."""

    _MAX_RETRIES = 2

    def __init__(self, base_url: str, access_token: str):
        self.base_url = base_url
        self.client = httpx.AsyncClient(
            base_url=base_url,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/fhir+json",
            },
            timeout=30.0,
        )

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self.client.aclose()

    def _raise_for_status(self, resp: httpx.Response) -> None:
        """Raise typed FHIR errors for non-2xx responses."""
        if resp.status_code < 400:
            return
        try:
            outcome = resp.json()
        except Exception:
            outcome = None

        error_map = {
            401: FHIRAuthError,
            403: FHIRAuthError,
            404: FHIRNotFoundError,
            429: FHIRRateLimitError,
        }
        exc_class = error_map.get(resp.status_code, FHIRError)
        raise exc_class(resp.status_code, outcome)

    async def _get(self, path: str, params: dict | None = None) -> dict:
        """GET with 1 retry on 429."""
        for attempt in range(self._MAX_RETRIES):
            resp = await self.client.get(path, params=params)
            if resp.status_code == 429 and attempt < self._MAX_RETRIES - 1:
                wait = (2 ** attempt) + random.uniform(0, 0.5)
                logger.warning("Rate limited on %s, retrying in %.1fs", path, wait)
                await asyncio.sleep(wait)
                continue
            self._raise_for_status(resp)
            return resp.json()
        # Should not reach here, but just in case
        self._raise_for_status(resp)
        return resp.json()

    async def _post(self, path: str, json: dict) -> dict:
        """POST a FHIR resource with 1 retry on 429."""
        for attempt in range(self._MAX_RETRIES):
            resp = await self.client.post(
                path, json=json,
                headers={"Content-Type": "application/fhir+json"},
            )
            if resp.status_code == 429 and attempt < self._MAX_RETRIES - 1:
                wait = (2 ** attempt) + random.uniform(0, 0.5)
                logger.warning("Rate limited on POST %s, retrying in %.1fs", path, wait)
                await asyncio.sleep(wait)
                continue
            self._raise_for_status(resp)
            return resp.json()
        self._raise_for_status(resp)
        return resp.json()

    async def _put(self, path: str, json: dict) -> dict:
        """PUT a FHIR resource with 1 retry on 429."""
        for attempt in range(self._MAX_RETRIES):
            resp = await self.client.put(
                path, json=json,
                headers={"Content-Type": "application/fhir+json"},
            )
            if resp.status_code == 429 and attempt < self._MAX_RETRIES - 1:
                wait = (2 ** attempt) + random.uniform(0, 0.5)
                logger.warning("Rate limited on PUT %s, retrying in %.1fs", path, wait)
                await asyncio.sleep(wait)
                continue
            self._raise_for_status(resp)
            return resp.json()
        self._raise_for_status(resp)
        return resp.json()

    @staticmethod
    def _extract_entries(bundle: dict) -> list[dict]:
        """Extract resources from a FHIR Bundle."""
        return [e["resource"] for e in bundle.get("entry", [])]

    # --- Practitioner ---

    async def search_practitioner(self, name: str) -> list[dict]:
        """Search practitioners by name."""
        bundle = await self._get("/Practitioner", params={"name": name})
        return self._extract_entries(bundle)

    # --- Schedule ---

    async def search_schedules(self, practitioner_id: str) -> list[dict]:
        """Search schedules by practitioner."""
        bundle = await self._get(
            "/Schedule",
            params={"actor": f"Practitioner/{practitioner_id}"},
        )
        return self._extract_entries(bundle)

    # --- Slot ---

    async def search_slots(
        self,
        schedule_id: str,
        start_from: str,
        start_to: str | None = None,
        status: str = "free",
    ) -> list[dict]:
        """Search slots by schedule, date range, and status."""
        params: dict = {
            "schedule": f"Schedule/{schedule_id}",
            "status": status,
        }
        if start_to:
            params["start"] = [f"ge{start_from}", f"le{start_to}"]
        else:
            params["start"] = f"ge{start_from}"
        bundle = await self._get("/Slot", params=params)
        return self._extract_entries(bundle)

    # --- Appointment ---

    async def list_appointments(
        self,
        patient_id: str,
        date_from: str,
        date_to: str | None = None,
        status: str = "booked",
    ) -> list[dict]:
        """List patient appointments in a date range."""
        params: dict = {"patient": patient_id, "status": status}
        if date_to:
            params["date"] = [f"ge{date_from}", f"le{date_to}"]
        else:
            params["date"] = f"ge{date_from}"
        bundle = await self._get("/Appointment", params=params)
        return self._extract_entries(bundle)

    async def read_appointment(self, appointment_id: str) -> dict:
        """Read a single appointment by ID."""
        return await self._get(f"/Appointment/{appointment_id}")

    async def find_availability(
        self,
        practitioner_id: str,
        start: str,
        end: str,
    ) -> list[dict]:
        """Search available appointments using $find (STU3 Argonaut IG).

        This is Epic's preferred way to discover bookable slots.
        Returns proposed Appointment resources.
        """
        body = {
            "resourceType": "Parameters",
            "parameter": [
                {"name": "start", "valueDateTime": start},
                {"name": "end", "valueDateTime": end},
                {
                    "name": "provider",
                    "valueUri": f"Practitioner/{practitioner_id}",
                },
            ],
        }
        bundle = await self._post("/Appointment/$find", json=body)
        return self._extract_entries(bundle)

    async def book_appointment(
        self,
        slot_id: str,
        patient_id: str,
        practitioner_id: str,
    ) -> dict:
        """Book an appointment using Appointment.$book with Parameters wrapper."""
        body = {
            "resourceType": "Parameters",
            "parameter": [
                {
                    "name": "appt-resource",
                    "resource": {
                        "resourceType": "Appointment",
                        "status": "booked",
                        "slot": [{"reference": f"Slot/{slot_id}"}],
                        "participant": [
                            {
                                "actor": {"reference": f"Patient/{patient_id}"},
                                "status": "accepted",
                            },
                            {
                                "actor": {"reference": f"Practitioner/{practitioner_id}"},
                                "status": "accepted",
                            },
                        ],
                    },
                }
            ],
        }
        result = await self._post("/Appointment/$book", json=body)
        entries = self._extract_entries(result)
        appointments = [e for e in entries if e.get("resourceType") == "Appointment"]
        return appointments[0] if appointments else result

    async def cancel_appointment(self, appointment_id: str) -> dict:
        """Cancel by reading full resource, changing status, and PUT back."""
        appt = await self.read_appointment(appointment_id)
        appt["status"] = "cancelled"
        return await self._put(f"/Appointment/{appointment_id}", json=appt)
