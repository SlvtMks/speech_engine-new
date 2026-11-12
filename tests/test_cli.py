import unittest

from speech_engine import cli


class CLITests(unittest.TestCase):
    def test_build_parser_has_subcommands(self) -> None:
        parser = cli.build_parser()

        # STT command
        args = parser.parse_args(["stt", "input.wav"])
        self.assertEqual(args.command, "stt")
        self.assertTrue(callable(args.func))

        # TTS command
        args = parser.parse_args(
            ["tts", "Привет", "--lang", "ru", "--out", "out.wav"]
        )
        self.assertEqual(args.command, "tts")
        self.assertTrue(callable(args.func))

        # CHAT command
        args = parser.parse_args(["chat", "input.wav", "--out", "reply.wav"])
        self.assertEqual(args.command, "chat")
        self.assertTrue(callable(args.func))


if __name__ == "__main__":
    unittest.main()

