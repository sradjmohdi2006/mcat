"""Tests for the manual segmentation backend."""
import unittest

from cat_tool.manual_segmentation import (
    ManualSegmentationError,
    ManualSegmenter,
    ManualUnit,
)


def positions(segmenter, text):
    """Return cursor positions around a token occurrence."""
    start = segmenter.text.index(text)
    return start, start + len(text)


class TestTokenBoundaries(unittest.TestCase):
    def test_tokens_keep_punctuation_separate(self):
        seg = ManualSegmenter(["Hello, world."])
        self.assertEqual(
            [(t["text"], t["start"], t["end"]) for t in seg.tokens],
            [
                ("Hello", 0, 5),
                (",", 5, 6),
                (" ", 6, 7),
                ("world", 7, 12),
                (".", 12, 13),
            ],
        )

    def test_unit_end_stops_exactly_at_word(self):
        seg = ManualSegmenter(["Hello, world."])
        seg.set_start(0)
        unit = seg.set_end(4)
        self.assertEqual(seg.unit_source(unit), "Hello")
        self.assertEqual((unit.block_start, unit.block_end), (0, 5))

    def test_punctuation_can_be_unit_end(self):
        seg = ManualSegmenter(["Hello, world."])
        seg.set_start(0)
        unit = seg.set_end(5)
        self.assertEqual(seg.unit_source(unit), "Hello,")

    def test_punctuation_can_be_unit_start(self):
        seg = ManualSegmenter(["Hello, world."])
        seg.set_start(5)
        unit = seg.set_end(12)
        self.assertEqual(seg.unit_source(unit), ", world.")

    def test_cursor_just_after_word_resolves_to_that_word(self):
        seg = ManualSegmenter(["one two"])
        token = seg.token_at(2)
        self.assertIsNotNone(token)
        self.assertEqual(token["text"], "one")

    def test_cursor_inside_wide_whitespace_has_no_token(self):
        seg = ManualSegmenter(["one   two"])
        self.assertIsNone(seg.token_at(4))

    def test_cursor_at_document_end_resolves_to_last_token(self):
        seg = ManualSegmenter(["last"])
        token = seg.token_at(4)
        self.assertIsNotNone(token)
        self.assertEqual(token["text"], "last")

    def test_start_requires_token(self):
        seg = ManualSegmenter(["one   two"])
        with self.assertRaises(ManualSegmentationError):
            seg.set_start(4)

    def test_end_requires_start(self):
        seg = ManualSegmenter(["one two"])
        with self.assertRaises(ManualSegmentationError):
            seg.set_end(3)

    def test_unit_cannot_cross_blocks(self):
        seg = ManualSegmenter(["Hello world", "Bye now"])
        seg.set_start(0)
        second_block = seg.text.index("Bye")
        with self.assertRaises(ManualSegmentationError):
            seg.set_end(second_block + 3)

    def test_end_before_start_is_rejected(self):
        seg = ManualSegmenter(["one two"])
        seg.set_start(4)
        with self.assertRaises(ManualSegmentationError):
            seg.set_end(2)

    def test_overlapping_range_is_rejected(self):
        seg = ManualSegmenter(["one two three"])
        seg.set_start(0)
        seg.set_end(2)
        seg.split()
        seg.set_start(0)
        with self.assertRaises(ManualSegmentationError):
            seg.set_end(6)


class TestSplitAndGaps(unittest.TestCase):
    def test_split_commits_the_marked_unit(self):
        seg = ManualSegmenter(["one two three"])
        seg.set_start(0)
        seg.set_end(2)
        self.assertEqual(len(seg.marked), 1)
        unit = seg.split()
        self.assertEqual(seg.unit_source(unit), "one")
        self.assertEqual(seg.marked, [])
        self.assertEqual(len(seg.units), 1)

    def test_split_without_mark_is_rejected(self):
        seg = ManualSegmenter(["one two"])
        with self.assertRaises(ManualSegmentationError):
            seg.split()

    def test_split_all_creates_units_from_gaps(self):
        seg = ManualSegmenter(["One two three four."])
        seg.set_start(0)
        seg.set_end(2)
        seg.split()
        seg.set_start(4)
        seg.set_end(8)
        created = seg.split_all()
        self.assertEqual(created, 2)
        self.assertEqual(
            [seg.unit_source(unit) for unit in seg.units],
            ["One", "two three", "four."],
        )
        self.assertFalse(seg.has_unsegmented_text())

    def test_split_all_trims_whitespace_from_gap_units(self):
        seg = ManualSegmenter(["  alpha beta  "])
        seg.set_start(2)
        seg.set_end(6)
        seg.split_all()
        self.assertEqual(
            [seg.unit_source(unit) for unit in seg.units],
            ["alpha", "beta"],
        )
        self.assertEqual(seg.units[0].block_start, 2)
        self.assertEqual(seg.units[1].block_end, len("  alpha beta"))

    def test_split_all_splits_gaps_at_block_boundaries(self):
        seg = ManualSegmenter(["one two", "three four"])
        seg.set_start(0)
        seg.set_end(2)
        seg.split_all()
        self.assertEqual(
            [seg.unit_source(unit) for unit in seg.units],
            ["one", "two", "three four"],
        )
        self.assertEqual(
            [unit.block_index for unit in seg.units], [0, 0, 1])

    def test_split_all_rejects_active_start(self):
        seg = ManualSegmenter(["one two"])
        seg.set_start(0)
        seg.set_end(2)
        seg.set_start(4)
        with self.assertRaises(ManualSegmentationError):
            seg.split_all()

    def test_split_all_requires_a_marked_unit(self):
        seg = ManualSegmenter(["one two"])
        with self.assertRaises(ManualSegmentationError):
            seg.split_all()

    def test_fill_gaps_creates_missing_units(self):
        seg = ManualSegmenter(["one two three"])
        seg.set_start(0)
        seg.set_end(2)
        seg.split()
        created = seg.fill_gaps()
        self.assertEqual(created, 1)
        self.assertEqual(
            [seg.unit_source(unit) for unit in seg.units],
            ["one", "two three"],
        )

    def test_gaps_reports_unsegmented_text(self):
        seg = ManualSegmenter(["one two three"])
        seg.set_start(0)
        seg.set_end(2)
        seg.split()
        gaps = seg.gaps()
        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0][2], " two three")
        self.assertTrue(seg.has_unsegmented_text())

    def test_clear_pending_removes_marks(self):
        seg = ManualSegmenter(["one two"])
        seg.set_start(0)
        seg.set_end(2)
        seg.set_start(4)
        self.assertTrue(seg.clear_pending())
        self.assertIsNone(seg.active_start)
        self.assertEqual(seg.marked, [])

    def test_clear_pending_with_nothing_pending_is_noop(self):
        seg = ManualSegmenter(["one two"])
        self.assertFalse(seg.clear_pending())


class TestUndo(unittest.TestCase):
    def test_undo_restores_committed_units(self):
        seg = ManualSegmenter(["one two"])
        seg.set_start(0)
        seg.set_end(2)
        seg.split()
        self.assertEqual(len(seg.units), 1)
        self.assertTrue(seg.undo())
        self.assertEqual(seg.units, [])

    def test_undo_restores_split_all(self):
        seg = ManualSegmenter(["one two three"])
        seg.set_start(0)
        seg.set_end(2)
        seg.split_all()
        self.assertEqual(len(seg.units), 2)
        seg.undo()
        self.assertEqual(seg.units, [])
        self.assertEqual(len(seg.marked), 1)

    def test_undo_with_empty_stack_is_rejected(self):
        seg = ManualSegmenter(["one"])
        with self.assertRaises(ManualSegmentationError):
            seg.undo()

    def test_can_undo_tracks_actions(self):
        seg = ManualSegmenter(["one two"])
        self.assertFalse(seg.can_undo)
        seg.set_start(0)
        self.assertTrue(seg.can_undo)


class TestPersistence(unittest.TestCase):
    def test_to_state_and_load_units_roundtrip(self):
        seg = ManualSegmenter(["one two", "three four"])
        seg.set_start(0)
        seg.set_end(2)
        seg.split()
        seg.set_start(seg.text.index("four"))
        seg.set_end(seg.text.index("four") + 3)
        seg.split()
        state = seg.to_state()
        self.assertEqual([item["source"] for item in state], ["one", "four"])

        restored = ManualSegmenter(["one two", "three four"])
        count = restored.load_units(state)
        self.assertEqual(count, 2)
        self.assertEqual(
            [restored.unit_source(unit) for unit in restored.units],
            ["one", "four"],
        )

    def test_load_units_accepts_segment_dictionaries(self):
        seg = ManualSegmenter(["one two"])
        seg.set_start(0)
        seg.set_end(2)
        seg.split()
        segments = seg.to_segments()

        restored = ManualSegmenter(["one two"])
        restored.load_units(segments)
        self.assertEqual(
            [restored.unit_source(unit) for unit in restored.units], ["one"])

    def test_load_units_preserves_targets(self):
        seg = ManualSegmenter(["one two"])
        seg.set_start(0)
        seg.set_end(2)
        seg.marked[0].target = "uno"
        seg.split()

        restored = ManualSegmenter(["one two"])
        restored.load_units(seg.to_state())
        self.assertEqual(restored.to_segments()[0]["target"], "uno")

    def test_load_units_skips_invalid_entries(self):
        seg = ManualSegmenter(["one two"])
        count = seg.load_units([
            {"start": 0, "end": 2, "block_index": 99},
            {"start": "bad"},
            {"start": 0, "end": 100, "block_index": 0},
            {"start": 0, "end": 2, "block_index": 0},
        ])
        self.assertEqual(count, 1)

    def test_to_segments_records_manual_offsets(self):
        seg = ManualSegmenter(["one two"])
        seg.set_start(0)
        seg.set_end(2)
        seg.split()
        segment = seg.to_segments()[0]
        self.assertEqual(segment["source"], "one")
        self.assertEqual(segment["manual_start"], 0)
        self.assertEqual(segment["manual_end"], 3)
        self.assertEqual(segment["manual_block"], 0)
        self.assertEqual(segment["manual_block_start"], 0)
        self.assertEqual(segment["manual_block_end"], 3)
        self.assertEqual(segment["source_location"]["manual"]["start"], 0)


class TestRendering(unittest.TestCase):
    def test_render_keeps_untranslated_gaps(self):
        seg = ManualSegmenter(["Hello world"])
        seg.set_start(0)
        seg.set_end(4)
        seg.marked[0].target = "Bonjour"
        seg.split()
        render = seg.build_render_segments()
        self.assertEqual(len(render), 1)
        self.assertEqual(render[0]["source"], "Hello world")
        self.assertEqual(render[0]["target"], "Bonjour world")

    def test_render_joins_all_translated_parts(self):
        seg = ManualSegmenter(["Hello world"])
        seg.set_start(0)
        seg.set_end(4)
        seg.marked[0].target = "Bonjour"
        seg.split()
        seg.set_start(6)
        seg.set_end(10)
        seg.marked[0].target = "monde"
        seg.split()
        render = seg.build_render_segments()[0]
        self.assertEqual(render["target"], "Bonjour monde")
        self.assertTrue(render["translated"])

    def test_render_one_segment_per_block(self):
        seg = ManualSegmenter(["one two", "three four"])
        seg.set_start(0)
        seg.set_end(2)
        seg.split()
        seg.fill_gaps()
        render = seg.build_render_segments()
        self.assertEqual(len(render), 2)
        self.assertEqual([item["source"] for item in render],
                         ["one two", "three four"])

    def test_render_untouched_block_has_empty_target(self):
        seg = ManualSegmenter(["one two", "three four"])
        seg.set_start(0)
        seg.set_end(2)
        seg.split()
        render = seg.build_render_segments()
        self.assertEqual(render[1]["target"], "")

    def test_unit_source_uses_block_offsets(self):
        unit = ManualUnit(0, 3, 0, 0, 3)
        seg = ManualSegmenter(["one two"])
        self.assertEqual(seg.unit_source(unit), "one")


if __name__ == "__main__":
    unittest.main()
