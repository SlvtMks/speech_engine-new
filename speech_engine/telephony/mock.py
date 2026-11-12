from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class TelephonyCall:
    external_call_id: str
    status: str


class MockTelephonyProvider:
    """Placeholder adapter until a concrete SIP/ATS provider is selected."""

    def start_outbound_call(self, phone: str) -> TelephonyCall:
        return TelephonyCall(
            external_call_id=f"mock-{uuid.uuid4().hex}",
            status="mock_started",
        )

    def accept_inbound_call(self, external_call_id: str | None = None) -> TelephonyCall:
        return TelephonyCall(
            external_call_id=external_call_id or f"mock-in-{uuid.uuid4().hex}",
            status="mock_answered",
        )
