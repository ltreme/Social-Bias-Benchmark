import re

def strip_thinking(text: str) -> str:
    if not text:
        return text
    text = re.sub(r"(?is)<think>.*?</think>", "", text)
    filtered: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        low = line.lower()
        if low.startswith(("analysis", "reason", "thought", "we need")):
            continue
        attr_hits = sum(k in low for k in (
            "age", "gender", "occupation", "education", "migration",
            "origin", "religion", "sexuality",
        ))
        if attr_hits >= 3 and len(low) > 40:
            continue
        filtered.append(line)
    if filtered:
        text = "\n".join(filtered)
    return text.strip().strip("'\"`“”„‚’").strip()

def cleanup_name(text: str, max_words: int = 4) -> str:
    text = strip_thinking(text)
    first = re.split(r"[\n,:;]|\\|/", text, 1)[0]
    first = re.sub(r"[^A-Za-zÀ-ÖØ-öø-ÿÄÖÜäöüß '\-]", "", first)
    first = re.sub(r"\s+", " ", first).strip()
    if len(first.split()) > max_words:
        first = " ".join(first.split()[:max_words])
    return first

def cleanup_text(text: str, max_len: int | None = None) -> str:
    text = strip_thinking(text)
    text = re.sub(r"(?is)antworte nur.*$", "", text).strip()
    if max_len and len(text) > max_len:
        text = text[:max_len].rsplit(" ", 1)[0].rstrip(".,;: ") + "..."
    return text.strip()
