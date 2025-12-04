# apps/benchmark/src/benchmark/pipeline/adapters/utils/json_tools.py
from __future__ import annotations

import json
import re
from json import JSONDecoder


def strip_code_fences(s: str) -> str:
    """Remove ```json ... ``` or ``` ... ``` fences if present."""
    if not s:
        return ""
    t = s.strip()
    if t.startswith("```") and t.endswith("```"):
        t = t.strip("`")
        nl = t.find("\n")
        if nl != -1:
            t = t[nl + 1 :]
    return t.strip()


def sanitize_llama_chat(text: str) -> str:
    """Trim trailing chat markers often seen in Llama-style outputs."""
    if not text:
        return ""
    candidates = ["[/INST]", "/INST]"]
    pos = max((text.rfind(tok) for tok in candidates), default=-1)
    return text[pos + len("[/INST]") :].lstrip(" \t\n\r]") if pos != -1 else text


def strip_thinking_blocks(text: str) -> str:
    """Remove 'thinking' or 'thoughts' blocks emitted by some models."""
    if not text:
        return ""
    t = text
    t = re.sub(r"```(?:thinking|thoughts)\b.*?```", "", t, flags=re.S | re.I)
    t = re.sub(r"<think>.*?</think>", "", t, flags=re.S | re.I)
    t = re.sub(r"(?is)\A\s*(?:thoughts?|thinking)\s*:\s*.*?\n\s*\n", "", t)
    return t.strip()


def extract_first_json(text: str):
    """Robust JSON extraction trying multiple strategies."""
    t = strip_code_fences(text)

    # 1) direct parse
    try:
        return json.loads(t)
    except Exception:
        pass

    dec = JSONDecoder()

    # 2) raw_decode from start
    try:
        obj, _ = dec.raw_decode(t.lstrip())
        return obj
    except Exception:
        pass

    # 2.5) If a JSON object appears later in the string, try slicing
    # between the first '{' and the last '}' and parse that chunk.
    first = t.find("{")
    last = t.rfind("}")
    if first != -1 and last != -1 and last > first:
        chunk = t[first : last + 1]
        try:
            return json.loads(chunk)
        except Exception:
            # fall back to decoder below
            pass

    # 3) try first '{' or '['
    for ch in ("{", "["):
        i = t.find(ch)
        if i != -1:
            try:
                obj, _ = dec.raw_decode(t[i:])
                return obj
            except Exception:
                pass

    # 4) brace-matching fallback
    start = t.find("{")
    if start != -1:
        depth, in_str, esc = 0, False, False
        for i, ch in enumerate(t[start:], start=start):
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
            else:
                if ch == '"':
                    in_str = True
                elif ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(t[start : i + 1])
                        except Exception:
                            break
    return None
