"""Readers for TMX translation memories and TBX term bases.

TMX (Translation Memory eXchange) files contain translation units
(``<tu>``), each holding one or more language variants (``<tuv>``) with a
``<seg>``.  TBX (TermBase eXchange) files contain ``<termEntry>`` records
with one or more ``<langSet>`` sections, each holding ``<term>`` elements.

The parsers are namespace-tolerant and return plain dictionaries so the
SQLite backends and the UI can share one implementation.
"""
import os
import re
import xml.etree.ElementTree as ET

XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"
_WORD_RE = re.compile(r"\w+", re.UNICODE)


def _local_name(tag):
    """Return an element tag without its ``{namespace}`` prefix."""
    if not isinstance(tag, str):
        return ""
    return tag.rsplit("}", 1)[-1]


def _children(elem, name):
    """Yield direct children whose local name matches ``name``."""
    if elem is None:
        return
    for child in elem:
        if _local_name(child.tag) == name:
            yield child


def _first_child(elem, name):
    return next(_children(elem, name), None)


def _normalize_ws(text):
    return re.sub(r"\s+", " ", text or "").strip()


def _text(elem):
    """Return all text inside an element, including inline tags."""
    if elem is None:
        return ""
    return _normalize_ws("".join(elem.itertext()))


def _lang_matches(requested, actual):
    """Match language codes leniently (``en`` matches ``en-US``)."""
    if not requested or not actual:
        return False
    a = requested.replace("_", "-").lower()
    b = actual.replace("_", "-").lower()
    return a == b or a.split("-")[0] == b.split("-")[0]


def is_single_word(text):
    """True when ``text`` is a single whitespace-free word/token.

    Used to tell a real translation memory from a term list that happens
    to be stored in a TMX container.
    """
    text = (text or "").strip()
    if not text or len(text.split()) != 1:
        return False
    return bool(_WORD_RE.search(text))


def _pick_indexes(tuvs, source_lang=None, target_lang=None):
    """Choose source/target indexes from ``[(lang, text), ...]``."""
    if len(tuvs) < 2:
        return None, None

    src_idx = None
    if source_lang:
        src_idx = next(
            (i for i, (lang, _) in enumerate(tuvs)
             if _lang_matches(source_lang, lang)),
            None,
        )
    if src_idx is None:
        src_idx = 0

    tgt_idx = None
    if target_lang:
        tgt_idx = next(
            (i for i, (lang, _) in enumerate(tuvs)
             if i != src_idx and _lang_matches(target_lang, lang)),
            None,
        )
    if tgt_idx is None:
        tgt_idx = next((i for i in range(len(tuvs)) if i != src_idx), None)
    return src_idx, tgt_idx


def parse_tmx(file_path, source_lang=None, target_lang=None):
    """Parse a TMX file into translation units.

    Returns ``(units, meta)`` where each unit is a dict with ``source``,
    ``target``, ``source_lang`` and ``target_lang``.  ``meta`` contains
    the header languages and the number of units.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"TMX file not found: {file_path}")

    root = ET.parse(file_path).getroot()
    header = _first_child(root, "header")
    srclang = (header.get("srclang") if header is not None else "") or ""

    body = _first_child(root, "body")
    if body is None:
        return [], {
            "source_lang": source_lang if source_lang is not None else srclang,
            "target_lang": target_lang or "",
            "count": 0,
        }

    seen_langs = set()
    units = []
    for tu in _children(body, "tu"):
        tuvs = []
        for tuv in _children(tu, "tuv"):
            lang = tuv.get(XML_LANG) or tuv.get("lang") or ""
            seg = _first_child(tuv, "seg")
            text = _text(seg)
            if text:
                tuvs.append((lang, text))
                seen_langs.add(lang)

        src_idx, tgt_idx = _pick_indexes(
            tuvs,
            source_lang=source_lang if source_lang is not None else (srclang or None),
            target_lang=target_lang,
        )
        if src_idx is None or tgt_idx is None:
            continue

        src_lang, src_text = tuvs[src_idx]
        tgt_lang, tgt_text = tuvs[tgt_idx]
        if not src_text or not tgt_text:
            continue
        if src_lang and tgt_lang and src_lang == tgt_lang:
            continue

        units.append({
            "source": src_text,
            "target": tgt_text,
            "source_lang": src_lang,
            "target_lang": tgt_lang,
        })

    if target_lang:
        detected_target = target_lang
    else:
        candidates = seen_langs - {srclang} if srclang else set(seen_langs)
        if len(candidates) == 1:
            detected_target = next(iter(candidates))
        else:
            detected_target = ", ".join(sorted(candidates))

    return units, {
        "source_lang": source_lang if source_lang is not None else srclang,
        "target_lang": detected_target,
        "count": len(units),
    }


def peek_tmx(file_path):
    """Return summary information about a TMX file for import dialogs."""
    units, meta = parse_tmx(file_path)
    single_word = sum(
        1 for unit in units
        if is_single_word(unit["source"]) and is_single_word(unit["target"])
    )
    return {
        "source_lang": meta["source_lang"],
        "target_lang": meta["target_lang"],
        "count": len(units),
        "single_word_count": single_word,
        "multi_word_count": len(units) - single_word,
        "is_term_like": bool(units) and single_word == len(units),
        "samples": units[:5],
    }


def _term_description(elem):
    """Pick the most useful description from a ``<tig>`` or entry."""
    fallback = ""
    for node in elem.iter():
        if _local_name(node.tag) != "descrip":
            continue
        text = _text(node)
        if not text:
            continue
        dtype = (node.get("type") or "").lower()
        if dtype in ("definition", "context", "explanation"):
            return text
        if not fallback:
            fallback = text
    return fallback


def parse_tbx(file_path, source_lang=None, target_lang=None):
    """Parse a TBX term base into glossary-style term pairs.

    Returns ``(terms, meta)`` where each term is a dict with ``source``,
    ``target``, ``description``, ``source_lang`` and ``target_lang``.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"TBX file not found: {file_path}")

    root = ET.parse(file_path).getroot()
    header = _first_child(root, "header")
    if header is None:
        header = _first_child(root, "tbxHeader")
    header_lang = ""
    if header is not None:
        header_lang = (header.get("srclang") or header.get(XML_LANG)
                       or header.get("lang") or "")
    if not header_lang:
        header_lang = root.get(XML_LANG) or root.get("lang") or ""

    terms = []
    target_langs = set()

    for entry in root.iter():
        if _local_name(entry.tag) != "termEntry":
            continue

        entry_desc = _term_description(entry)
        langs = []
        for lang_set in _children(entry, "langSet"):
            lang = lang_set.get(XML_LANG) or lang_set.get("lang") or ""
            term_text = ""
            desc = ""
            for tig in _children(lang_set, "tig"):
                term_el = next(
                    (node for node in tig.iter()
                     if _local_name(node.tag) == "term" and _text(node)),
                    None,
                )
                if term_el is None:
                    continue
                term_text = _text(term_el)
                desc = _term_description(tig) or entry_desc
                break
            if term_text:
                langs.append({"lang": lang, "term": term_text,
                              "description": desc})

        if len(langs) < 2:
            continue

        src_idx, tgt_idx = _pick_indexes(
            [(item["lang"], item["term"]) for item in langs],
            source_lang=source_lang if source_lang is not None else (header_lang or None),
            target_lang=target_lang,
        )
        if src_idx is None or tgt_idx is None:
            continue

        src = langs[src_idx]
        tgt = langs[tgt_idx]
        if src["lang"] and tgt["lang"] and src["lang"] == tgt["lang"]:
            continue
        terms.append({
            "source": src["term"],
            "target": tgt["term"],
            "description": src["description"] or tgt["description"],
            "source_lang": src["lang"],
            "target_lang": tgt["lang"],
        })
        target_langs.add(tgt["lang"])

    if target_lang:
        detected_target = target_lang
    elif len(target_langs) == 1:
        detected_target = next(iter(target_langs))
    else:
        detected_target = ", ".join(sorted(target_langs))
    if source_lang is not None:
        detected_source = source_lang
    else:
        detected_source = header_lang or (terms[0]["source_lang"] if terms else "")

    return terms, {
        "source_lang": detected_source,
        "target_lang": detected_target,
        "count": len(terms),
    }


def peek_tbx(file_path):
    """Return summary information about a TBX file for import dialogs."""
    terms, meta = parse_tbx(file_path)
    return {
        "source_lang": meta["source_lang"],
        "target_lang": meta["target_lang"],
        "count": len(terms),
        "samples": terms[:5],
    }
