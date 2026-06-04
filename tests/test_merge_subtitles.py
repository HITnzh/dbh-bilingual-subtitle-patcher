import unittest

from dbh_bisub.merge_subtitles import extract_control_tokens, merge_bilingual_text


class MergeSubtitlesTest(unittest.TestCase):
    def test_merge_two_lines(self) -> None:
        result = merge_bilingual_text("Hello", "你好")

        self.assertEqual(result.text, "Hello\n你好")
        self.assertEqual(result.warnings, [])

    def test_merge_missing_chinese(self) -> None:
        result = merge_bilingual_text("Hello", "")

        self.assertEqual(result.text, "Hello")
        self.assertEqual(result.warnings, ["Missing Chinese text; using English only."])

    def test_extract_control_tokens(self) -> None:
        self.assertEqual(extract_control_tokens("<b>{PLAYER}%s\\n"), ["<b>", "{PLAYER}", "%s", "\\n"])

    def test_warns_when_control_tokens_differ(self) -> None:
        result = merge_bilingual_text("{PLAYER} hello", "你好")

        self.assertIn("Control tokens differ between English and Chinese text.", result.warnings)

    def test_merges_timed_cue_segments_individually(self) -> None:
        result = merge_bilingual_text(
            "{*1}It moves. {*2}Two men are down.",
            "{*1}Ta zai dong. {*2}Liang ge ren dao xia le.",
        )

        self.assertEqual(
            result.text,
            "{*1}It moves.\nTa zai dong. {*2}Two men are down.\nLiang ge ren dao xia le.",
        )
        self.assertEqual(result.warnings, [])


if __name__ == "__main__":
    unittest.main()
