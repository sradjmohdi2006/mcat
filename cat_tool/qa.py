import re
from collections import defaultdict


class QAIssue:
    __slots__ = ("severity", "check_name", "segment_index", "source", "target", "description")

    def __init__(self, severity, check_name, segment_index, source, target, description):
        self.severity = severity
        self.check_name = check_name
        self.segment_index = segment_index
        self.source = source
        self.target = target
        self.description = description


def _extract_numbers(text):
    return set(re.findall(r"\d+(?:\.\d+)?", text))


def _count_tags(text):
    if not text:
        return 0
    from cat_tool.formats.tag_utils import PH_L, PH_R
    return text.count(PH_L)


def check_missing_translations(segments):
    issues = []
    for idx, seg in enumerate(segments):
        target = seg.get("target", "") or ""
        if not target.strip():
            issues.append(QAIssue(
                "error", "Missing translation", idx,
                seg.get("source", ""), "",
                "Segment has no translation."
            ))
    return issues


def check_unedited_fuzzy(segments):
    issues = []
    for idx, seg in enumerate(segments):
        if seg.get("fuzzy", False):
            issues.append(QAIssue(
                "warning", "Unedited fuzzy match", idx,
                seg.get("source", ""), seg.get("target", ""),
                "Segment is still marked as fuzzy/needs review."
            ))
    return issues


def check_inconsistent_translations(segments):
    source_map = defaultdict(set)
    for seg in segments:
        src = seg.get("source", "").strip()
        tgt = seg.get("target", "").strip()
        if src and tgt:
            source_map[src].add(tgt)

    issues = []
    for idx, seg in enumerate(segments):
        src = seg.get("source", "").strip()
        tgt = seg.get("target", "").strip()
        if src and tgt and len(source_map.get(src, set())) > 1:
            issues.append(QAIssue(
                "warning", "Inconsistent translation", idx,
                src, tgt,
                f"Source appears {len(source_map[src])} times with different translations: {', '.join(repr(t) for t in source_map[src])}"
            ))
    return issues


def check_tag_mismatch(segments):
    issues = []
    for idx, seg in enumerate(segments):
        src = seg.get("source", "") or ""
        tgt = seg.get("target", "") or ""
        src_count = _count_tags(src)
        tgt_count = _count_tags(tgt)
        if src_count != tgt_count:
            issues.append(QAIssue(
                "error", "Tag mismatch", idx,
                src, tgt,
                f"Source has {src_count} tag(s), target has {tgt_count} tag(s)."
            ))
    return issues


def check_number_mismatch(segments):
    issues = []
    for idx, seg in enumerate(segments):
        src = seg.get("source", "") or ""
        tgt = seg.get("target", "") or ""
        src_nums = _extract_numbers(src)
        tgt_nums = _extract_numbers(tgt)
        if src_nums and src_nums != tgt_nums:
            missing = src_nums - tgt_nums
            extra = tgt_nums - src_nums
            parts = []
            if missing:
                parts.append(f"missing: {', '.join(sorted(missing))}")
            if extra:
                parts.append(f"extra: {', '.join(sorted(extra))}")
            issues.append(QAIssue(
                "error", "Number mismatch", idx,
                src, tgt,
                "; ".join(parts)
            ))
    return issues


def check_whitespace(segments):
    issues = []
    for idx, seg in enumerate(segments):
        src = seg.get("source", "") or ""
        tgt = seg.get("target", "") or ""
        if not tgt.strip():
            continue
        if src.startswith(" ") and not tgt.startswith(" "):
            issues.append(QAIssue(
                "warning", "Leading whitespace", idx,
                src, tgt,
                "Source starts with whitespace but target does not."
            ))
        elif not src.startswith(" ") and tgt.startswith(" "):
            issues.append(QAIssue(
                "warning", "Leading whitespace", idx,
                src, tgt,
                "Target starts with whitespace but source does not."
            ))
        if src.endswith(" ") and not tgt.endswith(" "):
            issues.append(QAIssue(
                "warning", "Trailing whitespace", idx,
                src, tgt,
                "Source ends with whitespace but target does not."
            ))
        elif not src.endswith(" ") and tgt.endswith(" "):
            issues.append(QAIssue(
                "warning", "Trailing whitespace", idx,
                src, tgt,
                "Target ends with whitespace but source does not."
            ))
    return issues


def check_terminology(segments, glossary):
    issues = []
    for idx, seg in enumerate(segments):
        src = seg.get("source", "") or ""
        tgt = seg.get("target", "") or ""
        if not src.strip() or not tgt.strip():
            continue
        terms = glossary.check_segment(src)
        for term in terms:
            tgt_lower = tgt.lower()
            term_target = term.get("target", "").lower()
            if term_target and term_target not in tgt_lower:
                desc = term.get("description") or ""
                extra = f" ({desc})" if desc else ""
                issues.append(QAIssue(
                    "warning", "Terminology", idx,
                    src, tgt,
                    f"Glossary term '{term['source']}' should be '{term['target']}'{extra}."
                ))
    return issues


def run_all_checks(segments, glossary=None):
    issues = []
    issues.extend(check_missing_translations(segments))
    issues.extend(check_unedited_fuzzy(segments))
    issues.extend(check_inconsistent_translations(segments))
    issues.extend(check_tag_mismatch(segments))
    issues.extend(check_number_mismatch(segments))
    issues.extend(check_whitespace(segments))
    if glossary is not None:
        issues.extend(check_terminology(segments, glossary))
    return issues
