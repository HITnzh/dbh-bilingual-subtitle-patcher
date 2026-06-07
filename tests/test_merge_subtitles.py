import unittest

from dbh_bisub.merge_subtitles import extract_control_tokens, merge_bilingual_text


class MergeSubtitlesTest(unittest.TestCase):
    def test_merge_two_lines(self) -> None:
        result = merge_bilingual_text("Hello", "你好")

        self.assertEqual(result.text, "Hello{B}你好")
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
            "{*1}It moves.{B}Ta zai dong. {*2}Two men are down.{B}Liang ge ren dao xia le.",
        )
        self.assertEqual(result.warnings, [])

    def test_compacts_existing_visual_breaks_for_bilingual_layout(self) -> None:
        result = merge_bilingual_text("One{B}Two", "一{B}二")

        self.assertEqual(result.text, "One Two{B}一 二")

    def test_collapses_repeated_visual_lines(self) -> None:
        result = merge_bilingual_text(
            "{*1}Liberty!{B}Liberty!{B}Liberty!",
            "{*1}要自由！{B}要自由！{B}要自由！",
        )

        self.assertEqual(result.text, "{*1}Liberty!{B}要自由！")

    def test_removes_chinese_lines_from_english_source(self) -> None:
        result = merge_bilingual_text("Hello\n你好", "你好")

        self.assertEqual(result.text, "Hello{B}你好")

    def test_removes_english_lines_from_chinese_source(self) -> None:
        result = merge_bilingual_text("Hello", "Hello\n你好")

        self.assertEqual(result.text, "Hello{B}你好")

    def test_cleans_mixed_timed_sources_before_merging(self) -> None:
        result = merge_bilingual_text(
            "{*1}Captain Allen? {*2}My name is Connor.\n{*1}艾倫隊長？ {*2}我是康納。",
            "{*1}艾伦队长？{*2}我是康纳。",
        )

        self.assertEqual(result.text, "{*1}Captain Allen?{B}艾伦队长？ {*2}My name is Connor.{B}我是康纳。")

    def test_cleaning_keeps_visual_breaks_for_later_deduplication(self) -> None:
        result = merge_bilingual_text(
            "{*1}Liberty!{*2}Liberty!{B}Liberty!{B}Liberty!\n{*1}要自由！{*2}要自由！{B}要自由！",
            "{*1}要自由！{*2}要自由！",
        )

        self.assertEqual(result.text, "{*1}Liberty!{B}要自由！ {*2}Liberty!{B}要自由！")


if __name__ == "__main__":
    unittest.main()
