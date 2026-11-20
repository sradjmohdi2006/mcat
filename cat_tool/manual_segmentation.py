"""Manual segmentation backend and view.

The backend is deliberately Qt-free so the boundary rules can be tested
without a display.  The view wraps it in a read-only document panel.
"""
import re
from dataclasses import dataclass, field

from cat_tool.formats.tag_utils import apply_tags, extract_all_tags


class ManualSegmentationError(ValueError):
    """Raised when a manual segmentation operation is not allowed."""


TOKEN_RE = re.compile(r"\w+(?:['\u2019\-]\w+)*|\s+|.", re.UNICODE)


@dataclass
class ManualUnit:
    """One translation unit, expressed in document and block offsets."""

    start: int
    end: int
    block_index: int
    block_start: int
    block_end: int
    target: str = ""
    fuzzy: bool = False
    source: str = ""

    def copy(self):
        return ManualUnit(
            self.start, self.end, self.block_index, self.block_start,
            self.block_end, self.target, self.fuzzy, self.source)


@dataclass
class ManualBlock:
    text: str
    source_location: dict = field(default_factory=dict)
    all_tags: list = field(default_factory=list)
    global_start: int = 0

    @property
    def global_end(self):
        return self.global_start + len(self.text)


def _normalise_blocks(blocks):
    normalised = []
    for block in blocks:
        if isinstance(block, str):
            normalised.append(ManualBlock(block))
        else:
            normalised.append(ManualBlock(
                text=block.get("text", block.get("source", "")),
                source_location=dict(block.get("source_location") or {}),
                all_tags=list(block.get("all_tags") or []),
            ))
    return normalised


class ManualSegmenter:
    """Tracks word/punctuation boundaries and builds translation units.

    A document is made of blocks (paragraphs, lines, table cells) joined by
    newlines.  Units are confined to one block so they can be rendered back
    into the original format without ambiguity.
    """

    def __init__(self, blocks):
        self.blocks = _normalise_blocks(blocks)
        offset = 0
        for block in self.blocks:
            block.global_start = offset
            offset += len(block.text) + 1
        self.text = "\n".join(block.text for block in self.blocks)
        self.tokens = self._tokenize()
        self.units = []
        self.marked = []
        self.active_start = None
        self._undo_stack = []

    # ------------------------------------------------------------------
    # Token helpers
    # ------------------------------------------------------------------
    def _tokenize(self):
        tokens = []
        for block_index, block in enumerate(self.blocks):
            for match in TOKEN_RE.finditer(block.text):
                value = match.group(0)
                start = block.global_start + match.start()
                end = block.global_start + match.end()
                tokens.append({
                    "text": value,
                    "start": start,
                    "end": end,
                    "block_index": block_index,
                    "block_start": match.start(),
                    "block_end": match.end(),
                    "is_space": value.isspace(),
                })
        return tokens

    def token_at(self, position):
        """Return the non-whitespace token at or immediately before *position*.

        Cursor positions are insertion points, so a cursor just after a word
        still resolves to that word.  Positions inside whitespace return None.
        """
        if not self.tokens:
            return None
        position = max(0, min(int(position), len(self.text)))

        for index, token in enumerate(self.tokens):
            if token["start"] <= position < token["end"]:
                if not token["is_space"]:
                    return token
                # Just after the previous word / just before the next word.
                if position == token["start"] and index > 0:
                    previous = self.tokens[index - 1]
                    if not previous["is_space"] and previous["end"] == position:
                        return previous
                if position == token["end"] and index + 1 < len(self.tokens):
                    following = self.tokens[index + 1]
                    if not following["is_space"] and following["start"] == position:
                        return following
                return None

        if position == len(self.text) and self.tokens:
            last = self.tokens[-1]
            if not last["is_space"] and last["end"] == position:
                return last
        return None

    def block_for_token(self, token):
        return self.blocks[token["block_index"]]

    # ------------------------------------------------------------------
    # Undo
    # ------------------------------------------------------------------
    def _snapshot(self):
        self._undo_stack.append((
            self.active_start,
            [unit.copy() for unit in self.marked],
            [unit.copy() for unit in self.units],
        ))

    @property
    def can_undo(self):
        return bool(self._undo_stack)

    def undo(self):
        if not self._undo_stack:
            raise ManualSegmentationError("Nothing to undo.")
        self.active_start, self.marked, self.units = self._undo_stack.pop()
        return True

    # ------------------------------------------------------------------
    # Boundary marking
    # ------------------------------------------------------------------
    def _require_token(self, position):
        token = self.token_at(position)
        if token is None:
            raise ManualSegmentationError(
                "Place the cursor on a word or punctuation mark.")
        return token

    def _check_overlap(self, start, end):
        for unit in list(self.units) + list(self.marked):
            if start < unit.end and end > unit.start:
                raise ManualSegmentationError(
                    "That range overlaps an existing unit.")

    def set_start(self, position):
        token = self._require_token(position)
        self._snapshot()
        self.active_start = token
        return token

    def clear_pending(self):
        if self.active_start is None and not self.marked:
            return False
        self._snapshot()
        self.active_start = None
        self.marked.clear()
        return True

    def set_end(self, position):
        token = self._require_token(position)
        if self.active_start is None:
            raise ManualSegmentationError("Set a unit start first.")

        start_token = self.active_start
        if token["block_index"] != start_token["block_index"]:
            raise ManualSegmentationError(
                "A unit cannot cross a paragraph or block boundary.")

        start = start_token["start"]
        end = token["end"]
        if end <= start:
            raise ManualSegmentationError(
                "The unit end must come after the unit start.")
        self._check_overlap(start, end)

        block = self.blocks[start_token["block_index"]]
        unit = ManualUnit(
            start=start,
            end=end,
            block_index=start_token["block_index"],
            block_start=start - block.global_start,
            block_end=end - block.global_start,
        )
        self._snapshot()
        self.marked.append(unit)
        self.marked.sort(key=lambda item: item.start)
        self.active_start = None
        return unit

    # ------------------------------------------------------------------
    # Splitting
    # ------------------------------------------------------------------
    def _units_in_range(self, start, end):
        """Split a global range into trimmed block-local units."""
        units = []
        for block_index, block in enumerate(self.blocks):
            block_start = max(start, block.global_start)
            block_end = min(end, block.global_end)
            if block_end <= block_start:
                continue
            local_start = block_start - block.global_start
            local_end = block_end - block.global_start
            raw = block.text[local_start:local_end]
            if not raw.strip():
                continue
            left_trim = len(raw) - len(raw.lstrip())
            right_trim = len(raw) - len(raw.rstrip())
            local_start += left_trim
            local_end -= right_trim
            units.append(ManualUnit(
                start=block.global_start + local_start,
                end=block.global_start + local_end,
                block_index=block_index,
                block_start=local_start,
                block_end=local_end,
            ))
        return units

    def _is_covered(self, start, end):
        for unit in self.units:
            if start >= unit.start and end <= unit.end:
                return True
        for unit in self.marked:
            if start >= unit.start and end <= unit.end:
                return True
        return False

    def _gap_ranges(self):
        boundaries = {0, len(self.text)}
        for unit in self.units:
            boundaries.add(unit.start)
            boundaries.add(unit.end)
        ordered = sorted(boundaries)
        gaps = []
        for start, end in zip(ordered, ordered[1:]):
            if end <= start:
                continue
            if self._is_covered(start, end):
                continue
            if self.text[start:end].strip():
                gaps.append((start, end))
        return gaps

    def split(self):
        """Commit the oldest marked unit."""
        if not self.marked:
            raise ManualSegmentationError("Mark a unit start and end first.")
        self._snapshot()
        unit = self.marked.pop(0)
        self.units.append(unit)
        self.units.sort(key=lambda item: (item.block_index, item.block_start))
        return unit

    def split_all(self):
        """Commit marked units and turn every remaining gap into units.

        Gaps are split at block boundaries, so every created unit belongs to
        one paragraph/line/cell.
        """
        if self.active_start is not None:
            raise ManualSegmentationError(
                "Finish or clear the current unit before Split All.")
        if not self.marked:
            raise ManualSegmentationError("Mark at least one unit first.")

        self._snapshot()
        marked = [unit.copy() for unit in self.marked]
        marked.sort(key=lambda item: item.start)
        boundaries = {0, len(self.text)}
        for unit in self.units + marked:
            boundaries.add(unit.start)
            boundaries.add(unit.end)
        ordered = sorted(boundaries)

        new_units = []
        for start, end in zip(ordered, ordered[1:]):
            if end <= start or self._is_covered(start, end):
                continue
            if self.text[start:end].strip():
                new_units.extend(self._units_in_range(start, end))

        self.units.extend(marked)
        self.units.extend(new_units)
        self.units.sort(key=lambda item: (item.block_index, item.block_start))
        self.marked.clear()
        self.active_start = None
        return len(marked) + len(new_units)

    def fill_gaps(self):
        """Create units for every part of the document not yet committed."""
        gaps = self._gap_ranges()
        if not gaps:
            return 0
        self._snapshot()
        new_units = []
        for start, end in gaps:
            new_units.extend(self._units_in_range(start, end))
        self.units.extend(new_units)
        self.units.sort(key=lambda item: (item.block_index, item.block_start))
        return len(new_units)

    def gaps(self):
        """Return text ranges that are not part of a committed unit."""
        return [
            (start, end, self.text[start:end])
            for start, end in self._gap_ranges()
        ]

    def has_unsegmented_text(self):
        return any(text.strip() for _, _, text in self.gaps())

    # ------------------------------------------------------------------
    # Output
    # ------------------------------------------------------------------
    def unit_source(self, unit):
        block = self.blocks[unit.block_index]
        return block.text[unit.block_start:unit.block_end]

    def to_segments(self):
        """Build application segment dictionaries for committed units."""
        ordered = sorted(
            self.units, key=lambda item: (item.block_index, item.block_start))
        segments = []
        for index, unit in enumerate(ordered):
            source = self.unit_source(unit)
            all_tags = extract_all_tags(source)
            source_clean = apply_tags(source, all_tags)
            block = self.blocks[unit.block_index]
            location = dict(block.source_location or {})
            location["manual"] = {
                "start": unit.start,
                "end": unit.end,
                "block": unit.block_index,
                "block_start": unit.block_start,
                "block_end": unit.block_end,
            }
            segments.append({
                "index": index,
                "source": source,
                "target": unit.target,
                "source_clean": source_clean,
                "target_clean": apply_tags(unit.target, all_tags),
                "all_tags": all_tags,
                "notes": f"Manual unit {index + 1}",
                "fuzzy": unit.fuzzy,
                "translated": bool(unit.target.strip()),
                "locations": f"block:{unit.block_index}",
                "source_location": location,
                "manual_start": unit.start,
                "manual_end": unit.end,
                "manual_block": unit.block_index,
                "manual_block_start": unit.block_start,
                "manual_block_end": unit.block_end,
                "store": None,
                "unit": None,
            })
        return segments

    def to_state(self):
        """Serialisable representation stored in the project file."""
        return [
            {
                "start": unit.start,
                "end": unit.end,
                "block_index": unit.block_index,
                "block_start": unit.block_start,
                "block_end": unit.block_end,
                "target": unit.target,
                "fuzzy": unit.fuzzy,
                "source": self.unit_source(unit),
            }
            for unit in sorted(
                self.units, key=lambda item: (item.block_index, item.block_start))
        ]

    def load_units(self, units):
        """Restore units from project state or from segment dictionaries."""
        restored = []
        for item in units or []:
            try:
                start = int(item.get("start", item.get("manual_start")))
                end = int(item.get("end", item.get("manual_end")))
                block_index = int(item.get(
                    "block_index", item.get("manual_block", -1)))
                block_start = item.get(
                    "block_start", item.get("manual_block_start"))
                block_end = item.get("block_end", item.get("manual_block_end"))
            except (TypeError, ValueError):
                continue
            if block_index < 0 or block_index >= len(self.blocks):
                continue
            block = self.blocks[block_index]
            if block_start is None:
                block_start = start - block.global_start
            if block_end is None:
                block_end = end - block.global_start
            block_start = int(block_start)
            block_end = int(block_end)
            if not (0 <= block_start < block_end <= len(block.text)):
                continue
            restored.append(ManualUnit(
                start=start,
                end=end,
                block_index=block_index,
                block_start=block_start,
                block_end=block_end,
                target=item.get("target", "") or "",
                fuzzy=bool(item.get("fuzzy", False)),
            ))
        self.units = sorted(
            restored, key=lambda item: (item.block_index, item.block_start))
        self.marked.clear()
        self.active_start = None
        self._undo_stack.clear()
        return len(self.units)

    def build_render_segments(self):
        """Return one segment per original block for the format renderers.

        Multiple manual units in one block are joined back together, keeping
        any untranslated gaps in their original form.
        """
        by_block = {}
        for unit in self.units:
            by_block.setdefault(unit.block_index, []).append(unit)

        render_segments = []
        for index, block in enumerate(self.blocks):
            units = sorted(by_block.get(index, []),
                           key=lambda item: item.block_start)
            target = ""
            if units:
                parts = []
                position = 0
                for unit in units:
                    if unit.block_start < position:
                        continue
                    if unit.block_start > position:
                        parts.append(block.text[position:unit.block_start])
                    parts.append(
                        unit.target
                        if unit.target.strip()
                        else block.text[unit.block_start:unit.block_end])
                    position = unit.block_end
                parts.append(block.text[position:])
                combined = "".join(parts)
                if combined != block.text:
                    target = combined
            all_tags = extract_all_tags(target or block.text)
            render_segments.append({
                "index": index,
                "source": block.text,
                "target": target,
                "source_clean": apply_tags(block.text, all_tags),
                "target_clean": apply_tags(target, all_tags),
                "all_tags": all_tags,
                "notes": "",
                "fuzzy": False,
                "translated": bool(target.strip()),
                "locations": "",
                "source_location": dict(block.source_location or {}),
                "store": None,
                "unit": None,
            })
        return render_segments
