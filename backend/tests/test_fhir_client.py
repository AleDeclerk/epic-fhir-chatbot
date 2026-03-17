"""Tests for FHIR client base class (TDD Red → Green)."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

import httpx

from app.fhir_client import (
    EpicFHIRClient,
    FHIRError,
    FHIRAuthError,
    FHIRNotFoundError,
    FHIRRateLimitError,
)


@pytest.fixture
def fhir_client():
    """Create a FHIR client for testing."""
    return EpicFHIRClient(
        base_url="https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4",
        access_token="test-token-123",
    )


class TestClientInit:
    def test_client_sets_base_url(self, fhir_client):
        assert str(fhir_client.client.base_url).rstrip("/").endswith("FHIR/R4")

    def test_client_sets_auth_header(self, fhir_client):
        assert fhir_client.client.headers["authorization"] == "Bearer test-token-123"

    def test_client_sets_accept_header(self, fhir_client):
        assert fhir_client.client.headers["accept"] == "application/fhir+json"

    def test_client_sets_timeout(self, fhir_client):
        assert fhir_client.client.timeout.connect == 30.0


class TestErrorHandling:
    def test_401_raises_auth_error(self, fhir_client):
        resp = MagicMock(spec=httpx.Response)
        resp.status_code = 401
        resp.json.return_value = {
            "resourceType": "OperationOutcome",
            "issue": [{"diagnostics": "Token expired"}],
        }
        with pytest.raises(FHIRAuthError) as exc_info:
            fhir_client._raise_for_status(resp)
        assert exc_info.value.status_code == 401

    def test_403_raises_auth_error(self, fhir_client):
        resp = MagicMock(spec=httpx.Response)
        resp.status_code = 403
        resp.json.return_value = None
        with pytest.raises(FHIRAuthError):
            fhir_client._raise_for_status(resp)

    def test_404_raises_not_found(self, fhir_client):
        resp = MagicMock(spec=httpx.Response)
        resp.status_code = 404
        resp.json.return_value = None
        with pytest.raises(FHIRNotFoundError):
            fhir_client._raise_for_status(resp)

    def test_429_raises_rate_limit(self, fhir_client):
        resp = MagicMock(spec=httpx.Response)
        resp.status_code = 429
        resp.json.return_value = None
        with pytest.raises(FHIRRateLimitError):
            fhir_client._raise_for_status(resp)

    def test_500_raises_fhir_error(self, fhir_client):
        resp = MagicMock(spec=httpx.Response)
        resp.status_code = 500
        resp.json.return_value = None
        with pytest.raises(FHIRError):
            fhir_client._raise_for_status(resp)

    def test_200_does_not_raise(self, fhir_client):
        resp = MagicMock(spec=httpx.Response)
        resp.status_code = 200
        fhir_client._raise_for_status(resp)  # Should not raise


class TestExtractEntries:
    def test_extracts_resources_from_bundle(self, fhir_client, sample_appointment_bundle):
        entries = fhir_client._extract_entries(sample_appointment_bundle)
        assert len(entries) == 1
        assert entries[0]["resourceType"] == "Appointment"

    def test_empty_bundle_returns_empty_list(self, fhir_client, empty_bundle):
        entries = fhir_client._extract_entries(empty_bundle)
        assert entries == []


class TestGetWithRetry:
    @pytest.mark.asyncio
    async def test_get_retries_on_429(self, fhir_client):
        """Should retry once on 429 then succeed."""
        rate_limit_resp = MagicMock(spec=httpx.Response)
        rate_limit_resp.status_code = 429
        rate_limit_resp.json.return_value = None

        success_resp = MagicMock(spec=httpx.Response)
        success_resp.status_code = 200
        success_resp.json.return_value = {"resourceType": "Bundle", "total": 0}

        fhir_client.client.get = AsyncMock(
            side_effect=[rate_limit_resp, success_resp]
        )

        result = await fhir_client._get("/Patient")
        assert result["resourceType"] == "Bundle"
        assert fhir_client.client.get.call_count == 2

    @pytest.mark.asyncio
    async def test_get_raises_after_retry_exhausted(self, fhir_client):
        """Should raise after max retries on 429."""
        rate_limit_resp = MagicMock(spec=httpx.Response)
        rate_limit_resp.status_code = 429
        rate_limit_resp.json.return_value = None

        fhir_client.client.get = AsyncMock(return_value=rate_limit_resp)

        with pytest.raises(FHIRRateLimitError):
            await fhir_client._get("/Patient")


class TestListAppointments:
    """T014: Tests for list_appointments()."""

    @pytest.mark.asyncio
    async def test_list_appointments_returns_results(self, fhir_client, sample_appointment_bundle):
        """Returns parsed appointments from a FHIR Bundle."""
        success_resp = MagicMock(spec=httpx.Response)
        success_resp.status_code = 200
        success_resp.json.return_value = sample_appointment_bundle
        fhir_client.client.get = AsyncMock(return_value=success_resp)

        results = await fhir_client.list_appointments(
            patient_id="Tbt3KuCY0B5PSrJvCu2j-PlK.aiHsu2xUjUM8bWpetXoB",
            date_from="2026-03-16",
        )
        assert len(results) == 1
        assert results[0]["resourceType"] == "Appointment"
        assert results[0]["id"] == "abc123"

    @pytest.mark.asyncio
    async def test_list_appointments_empty(self, fhir_client, empty_bundle):
        """Returns empty list when no appointments found."""
        success_resp = MagicMock(spec=httpx.Response)
        success_resp.status_code = 200
        success_resp.json.return_value = empty_bundle
        fhir_client.client.get = AsyncMock(return_value=success_resp)

        results = await fhir_client.list_appointments(
            patient_id="patient-123",
            date_from="2026-03-16",
        )
        assert results == []

    @pytest.mark.asyncio
    async def test_list_appointments_fhir_error(self, fhir_client):
        """Raises FHIRError on server error."""
        error_resp = MagicMock(spec=httpx.Response)
        error_resp.status_code = 500
        error_resp.json.return_value = None
        fhir_client.client.get = AsyncMock(return_value=error_resp)

        with pytest.raises(FHIRError):
            await fhir_client.list_appointments(
                patient_id="patient-123",
                date_from="2026-03-16",
            )

    @pytest.mark.asyncio
    async def test_list_appointments_extracts_practitioner_name(self, fhir_client, sample_appointment_bundle):
        """Practitioner name is in the participant array."""
        success_resp = MagicMock(spec=httpx.Response)
        success_resp.status_code = 200
        success_resp.json.return_value = sample_appointment_bundle
        fhir_client.client.get = AsyncMock(return_value=success_resp)

        results = await fhir_client.list_appointments(
            patient_id="Tbt3KuCY0B5PSrJvCu2j-PlK.aiHsu2xUjUM8bWpetXoB",
            date_from="2026-03-16",
        )
        appt = results[0]
        # Practitioner is in participant array
        practitioners = [
            p for p in appt["participant"]
            if "Practitioner" in p["actor"]["reference"]
        ]
        assert len(practitioners) == 1
        assert practitioners[0]["actor"]["display"] == "Family Medicine Physician"


class TestSearchPractitioners:
    """T023: Tests for search_practitioner()."""

    @pytest.mark.asyncio
    async def test_search_practitioner_by_name(self, fhir_client, sample_practitioner_bundle):
        success_resp = MagicMock(spec=httpx.Response)
        success_resp.status_code = 200
        success_resp.json.return_value = sample_practitioner_bundle
        fhir_client.client.get = AsyncMock(return_value=success_resp)

        results = await fhir_client.search_practitioner("Physician")
        assert len(results) == 1
        assert results[0]["id"] == "eM5CWtq15N0WJeuCet5bJlQ3"

    @pytest.mark.asyncio
    async def test_search_practitioner_empty(self, fhir_client, empty_bundle):
        success_resp = MagicMock(spec=httpx.Response)
        success_resp.status_code = 200
        success_resp.json.return_value = empty_bundle
        fhir_client.client.get = AsyncMock(return_value=success_resp)

        results = await fhir_client.search_practitioner("Unknown")
        assert results == []


class TestSearchSlots:
    """T023: Tests for search_slots()."""

    @pytest.mark.asyncio
    async def test_search_free_slots(self, fhir_client, sample_slot_bundle):
        success_resp = MagicMock(spec=httpx.Response)
        success_resp.status_code = 200
        success_resp.json.return_value = sample_slot_bundle
        fhir_client.client.get = AsyncMock(return_value=success_resp)

        results = await fhir_client.search_slots(
            schedule_id="eIDmKq.4HlMO6fwMQ5B2eEw3",
            start_from="2026-03-20",
        )
        assert len(results) == 1
        assert results[0]["status"] == "free"

    @pytest.mark.asyncio
    async def test_search_slots_with_date_range(self, fhir_client, sample_slot_bundle):
        success_resp = MagicMock(spec=httpx.Response)
        success_resp.status_code = 200
        success_resp.json.return_value = sample_slot_bundle
        fhir_client.client.get = AsyncMock(return_value=success_resp)

        results = await fhir_client.search_slots(
            schedule_id="sched-1",
            start_from="2026-03-20",
            start_to="2026-03-25",
        )
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_search_slots_404_fallback(self, fhir_client):
        """Slot.Search may return 404 on Epic sandbox — handle gracefully."""
        error_resp = MagicMock(spec=httpx.Response)
        error_resp.status_code = 404
        error_resp.json.return_value = None
        fhir_client.client.get = AsyncMock(return_value=error_resp)

        with pytest.raises(FHIRNotFoundError):
            await fhir_client.search_slots(
                schedule_id="sched-1",
                start_from="2026-03-20",
            )

    @pytest.mark.asyncio
    async def test_search_slots_empty(self, fhir_client, empty_bundle):
        success_resp = MagicMock(spec=httpx.Response)
        success_resp.status_code = 200
        success_resp.json.return_value = empty_bundle
        fhir_client.client.get = AsyncMock(return_value=success_resp)

        results = await fhir_client.search_slots(
            schedule_id="sched-1",
            start_from="2026-03-20",
        )
        assert results == []


class TestSearchSchedules:
    """T023: Tests for search_schedules()."""

    @pytest.mark.asyncio
    async def test_search_schedules_by_practitioner(self, fhir_client, sample_schedule_bundle):
        success_resp = MagicMock(spec=httpx.Response)
        success_resp.status_code = 200
        success_resp.json.return_value = sample_schedule_bundle
        fhir_client.client.get = AsyncMock(return_value=success_resp)

        results = await fhir_client.search_schedules("eM5CWtq15N0WJeuCet5bJlQ3")
        assert len(results) == 1


class TestPostWithRetry:
    """F10: POST retries once on 429."""

    @pytest.mark.asyncio
    async def test_post_retries_on_429(self, fhir_client):
        """Should retry once on 429 then succeed."""
        rate_limit_resp = MagicMock(spec=httpx.Response)
        rate_limit_resp.status_code = 429
        rate_limit_resp.json.return_value = None

        success_resp = MagicMock(spec=httpx.Response)
        success_resp.status_code = 200
        success_resp.json.return_value = {"resourceType": "Appointment", "id": "a1"}

        fhir_client.client.post = AsyncMock(
            side_effect=[rate_limit_resp, success_resp]
        )

        result = await fhir_client._post("/Appointment/$book", json={})
        assert result["id"] == "a1"
        assert fhir_client.client.post.call_count == 2

    @pytest.mark.asyncio
    async def test_post_raises_after_retry_exhausted(self, fhir_client):
        """Should raise after max retries on 429."""
        rate_limit_resp = MagicMock(spec=httpx.Response)
        rate_limit_resp.status_code = 429
        rate_limit_resp.json.return_value = None

        fhir_client.client.post = AsyncMock(return_value=rate_limit_resp)

        with pytest.raises(FHIRRateLimitError):
            await fhir_client._post("/Appointment/$book", json={})


class TestPutWithRetry:
    """F10: PUT retries once on 429."""

    @pytest.mark.asyncio
    async def test_put_retries_on_429(self, fhir_client):
        """Should retry once on 429 then succeed."""
        rate_limit_resp = MagicMock(spec=httpx.Response)
        rate_limit_resp.status_code = 429
        rate_limit_resp.json.return_value = None

        success_resp = MagicMock(spec=httpx.Response)
        success_resp.status_code = 200
        success_resp.json.return_value = {"resourceType": "Appointment", "status": "cancelled"}

        fhir_client.client.put = AsyncMock(
            side_effect=[rate_limit_resp, success_resp]
        )

        result = await fhir_client._put("/Appointment/a1", json={})
        assert result["status"] == "cancelled"
        assert fhir_client.client.put.call_count == 2


class TestBookAppointment:
    """T029: Tests for book_appointment()."""

    @pytest.mark.asyncio
    async def test_book_appointment_success(self, fhir_client):
        """Successful booking returns Appointment resource."""
        book_bundle = {
            "resourceType": "Bundle",
            "entry": [
                {
                    "resource": {
                        "resourceType": "Appointment",
                        "id": "new-appt-001",
                        "status": "booked",
                        "start": "2026-03-20T09:00:00-05:00",
                    }
                }
            ],
        }
        success_resp = MagicMock(spec=httpx.Response)
        success_resp.status_code = 200
        success_resp.json.return_value = book_bundle
        fhir_client.client.post = AsyncMock(return_value=success_resp)

        result = await fhir_client.book_appointment(
            slot_id="slot-001",
            patient_id="patient-123",
            practitioner_id="prac-001",
        )
        assert result["id"] == "new-appt-001"
        assert result["status"] == "booked"

    @pytest.mark.asyncio
    async def test_book_appointment_slot_taken(self, fhir_client):
        """Booking a taken slot raises FHIR error."""
        error_resp = MagicMock(spec=httpx.Response)
        error_resp.status_code = 422
        error_resp.json.return_value = {
            "resourceType": "OperationOutcome",
            "issue": [{"diagnostics": "Slot is no longer available"}],
        }
        fhir_client.client.post = AsyncMock(return_value=error_resp)

        with pytest.raises(FHIRError):
            await fhir_client.book_appointment(
                slot_id="slot-taken",
                patient_id="patient-123",
                practitioner_id="prac-001",
            )

    @pytest.mark.asyncio
    async def test_book_uses_parameters_wrapper(self, fhir_client):
        """Book sends Appointment inside a Parameters resource wrapper."""
        book_bundle = {
            "resourceType": "Bundle",
            "entry": [{"resource": {"resourceType": "Appointment", "id": "a1", "status": "booked"}}],
        }
        success_resp = MagicMock(spec=httpx.Response)
        success_resp.status_code = 200
        success_resp.json.return_value = book_bundle
        fhir_client.client.post = AsyncMock(return_value=success_resp)

        await fhir_client.book_appointment("slot-1", "patient-1", "prac-1")

        call_args = fhir_client.client.post.call_args
        body = call_args.kwargs["json"]
        assert body["resourceType"] == "Parameters"
        assert body["parameter"][0]["name"] == "appt-resource"
        assert body["parameter"][0]["resource"]["resourceType"] == "Appointment"


class TestCancelAppointment:
    """T035: Tests for cancel_appointment()."""

    @pytest.mark.asyncio
    async def test_cancel_appointment_success(self, fhir_client):
        """Successful cancellation returns updated Appointment."""
        # Mock GET (read current)
        get_resp = MagicMock(spec=httpx.Response)
        get_resp.status_code = 200
        get_resp.json.return_value = {
            "resourceType": "Appointment",
            "id": "appt-001",
            "status": "booked",
            "start": "2026-03-25T14:00:00",
            "participant": [],
        }

        # Mock PUT (update)
        put_resp = MagicMock(spec=httpx.Response)
        put_resp.status_code = 200
        put_resp.json.return_value = {
            "resourceType": "Appointment",
            "id": "appt-001",
            "status": "cancelled",
        }

        fhir_client.client.get = AsyncMock(return_value=get_resp)
        fhir_client.client.put = AsyncMock(return_value=put_resp)

        result = await fhir_client.cancel_appointment("appt-001")
        assert result["status"] == "cancelled"

    @pytest.mark.asyncio
    async def test_cancel_appointment_not_found(self, fhir_client):
        """Cancelling non-existent appointment raises 404."""
        error_resp = MagicMock(spec=httpx.Response)
        error_resp.status_code = 404
        error_resp.json.return_value = None
        fhir_client.client.get = AsyncMock(return_value=error_resp)

        with pytest.raises(FHIRNotFoundError):
            await fhir_client.cancel_appointment("nonexistent")


class TestClose:
    @pytest.mark.asyncio
    async def test_close_calls_aclose(self, fhir_client):
        fhir_client.client.aclose = AsyncMock()
        await fhir_client.close()
        fhir_client.client.aclose.assert_called_once()
