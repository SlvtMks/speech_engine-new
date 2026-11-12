from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from speech_engine.storage import CallStore


class CallStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TemporaryDirectory()
        self.store = CallStore(Path(self.tmp.name) / "calls.db")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_create_lead_and_call_history(self) -> None:
        lead = self.store.create_lead(phone="+79990000000", name="Test")
        call = self.store.create_call(
            lead_id=lead["id"],
            direction="outbound",
            scenario="cold_sales_intro",
            current_step="greeting",
            status="started",
            external_call_id="mock-1",
        )
        self.store.add_message(call["id"], role="agent", text="Здравствуйте", step="greeting")
        self.store.add_message(call["id"], role="customer", text="Да", step="greeting")

        loaded_call = self.store.get_call(call["id"])

        self.assertEqual(loaded_call["lead_id"], lead["id"])
        self.assertEqual(len(loaded_call["messages"]), 2)
        self.assertEqual(loaded_call["messages"][0]["role"], "agent")


if __name__ == "__main__":
    unittest.main()
