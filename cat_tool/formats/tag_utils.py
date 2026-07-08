import re

TAG_RE = re.compile(r'<[^>]+>')
PH_L = '\u27e6'
PH_R = '\u27e7'


def extract_all_tags(text):
    seen = []
    for m in TAG_RE.finditer(text or ""):
        t = m.group(0)
        if t not in seen:
            seen.append(t)
    return seen


def apply_tags(text, tag_list):
    if not text or not tag_list:
        return text
    tag_to_idx = {t: i for i, t in enumerate(tag_list)}
    def _repl(m):
        idx = tag_to_idx.get(m.group(0))
        return f'{PH_L}{idx}{PH_R}' if idx is not None else m.group(0)
    return TAG_RE.sub(_repl, text)


def restore_tags(text, tag_list):
    if not text or not tag_list:
        return text
    pat = re.escape(PH_L) + r'(\d+)' + re.escape(PH_R)
    def _repl(m):
        idx = int(m.group(1))
        return tag_list[idx] if idx < len(tag_list) else m.group(0)
    return re.sub(pat, _repl, text)
