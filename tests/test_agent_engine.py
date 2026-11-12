import unittest

from speech_engine.agent import AgentEngine


class AgentEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.agent = AgentEngine()

    def test_start_returns_greeting(self) -> None:
        reply = self.agent.start()

        self.assertEqual(reply.next_step, "greeting")
        self.assertEqual(reply.intent, "start")
        self.assertFalse(reply.finish)
        self.assertIn("удобно", reply.text.casefold())

    def test_positive_reply_moves_to_qualification(self) -> None:
        reply = self.agent.respond("Да, говорите", current_step="greeting")

        self.assertEqual(reply.intent, "positive")
        self.assertEqual(reply.next_step, "qualification")
        self.assertEqual(reply.status, "interested")

    def test_negative_reply_finishes_call(self) -> None:
        reply = self.agent.respond("Нет, мне не интересно", current_step="greeting")

        self.assertEqual(reply.intent, "negative")
        self.assertEqual(reply.next_step, "finish_negative")
        self.assertTrue(reply.finish)

    def test_human_request_sets_handoff(self) -> None:
        reply = self.agent.respond("Соедините с оператором", current_step="qualification")

        self.assertEqual(reply.intent, "human")
        self.assertEqual(reply.next_step, "handoff")
        self.assertTrue(reply.handoff)


if __name__ == "__main__":
    unittest.main()
