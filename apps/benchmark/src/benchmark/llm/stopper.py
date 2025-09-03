import re
import torch
from transformers import StoppingCriteria
from typing import List
import regex as re
import torch
from transformers import LogitsProcessor

class FastSentenceStopper(StoppingCriteria):
    """
    Stop after `max_sentences` *complete* sentences using a rolling text buffer.
    - Decodes only the *newly generated* part (no full re-decode).
    - Ignores common abbreviations and '...' ellipses.
    - Cheap regex; no external NLP libs.
    """
    _boundary = re.compile(
        r"""(?<!\b(?:z|bzw|usw|etc|ca|ggf|Nr|Abs|Art|S|u|a|i|v|Dr|Prof)\.)      # no abbrev before dot
            (?<!\.)                                                              # not part of "..."
            (?<=[.!?])                                                           # real terminal
            (?:["»”'\)\]]+)?                                                     # optional closing quotes/brackets
            \s                                                                   # followed by whitespace
        """,
        re.X
    )

    def __init__(self, tokenizer, prompt_len_tokens: int, max_sentences: int = 2,
            tail_chars: int = 800):
        self.tok = tokenizer
        self.max_sentences = max_sentences
        self.prompt_len_tokens = prompt_len_tokens
        self.prev_len_tokens = prompt_len_tokens
        self.buf = ""                # rolling decoded text of generated part
        self.scan_pos = 0            # last regex scan index within buf
        self.tail_chars = tail_chars # cap buffer to recent chars (perf)

        self.count = 0

    def _append_new_text(self, input_ids: torch.LongTensor):
        cur_len = input_ids.shape[1]
        if cur_len <= self.prev_len_tokens:
            return
        # Decode only new tokens since last step
        new_ids = input_ids[0, self.prev_len_tokens:cur_len]
        new_txt = self.tok.decode(new_ids, skip_special_tokens=True)
        self.prev_len_tokens = cur_len

        # Append and trim buffer (keep recent tail only)
        self.buf += new_txt
        if len(self.buf) > self.tail_chars:
            # Adjust scan_pos when trimming left side
            trim = len(self.buf) - self.tail_chars
            self.buf = self.buf[trim:]
            self.scan_pos = max(0, self.scan_pos - trim)

    def __call__(self, input_ids, scores, **kwargs) -> bool:
        self._append_new_text(input_ids)

        # Count new sentence boundaries since last scan position
        for m in self._boundary.finditer(self.buf, self.scan_pos):
            # Guard: ignore ellipses "... "
            if m.start() >= 2 and self.buf[m.start()-2:m.start()+1] == "...":
                self.scan_pos = m.end()
                continue
            self.count += 1
            self.scan_pos = m.end()
            if self.count >= self.max_sentences:
                return True
        return False



class StopOnFullName(StoppingCriteria):
    
    _name_re = re.compile(
        r"""(?x)
        \b
        \p{Lu}\p{L}+(?:[-']\p{Lu}\p{L}+)*     # First name
        \s+
        \p{Lu}\p{L}+(?:[-']\p{Lu}\p{L}+)*     # Last name
        \b
        """
    )
    
    def __init__(self, tokenizer, prompt_len_tokens):
        self.tok = tokenizer
        self.prev = prompt_len_tokens
        self.buf = ""
    def __call__(self, input_ids, scores, **kwargs):
        new_ids = input_ids[0, self.prev: input_ids.shape[1]]
        if new_ids.numel() == 0: return False
        self.buf += self.tok.decode(new_ids, skip_special_tokens=True)
        self.prev = input_ids.shape[1]
        # Optional: trim buffer tail to keep it cheap
        self.buf = self.buf[-120:]
        return bool(self._name_re.search(self.buf))
    


# --- lightweight per-sample limiter ---
class PerSampleLimiter(LogitsProcessor):
    """
    Enforces per-sample stopping rules within a single batched generate() call
    by forcing EOS for samples that met their condition.
    - Decodes only the *newly generated* token tail (cheap).
    - Maintains small rolling buffers per sample.
    """
    # simple sentence boundary; short abbrev guard
    _sent_boundary = re.compile(
        r"""(?x)
        (?<!\b(?:z|bzw|usw|etc|ca|ggf|Nr|Abs|Art|S|u|a|i|v|Dr|Prof)\.)
        (?<!\.) (?<=[.!?]) (?:["»”'\)\]]+)? \s
        """
    )
    # "Vorname Nachname" matcher (Umlauts, hyphens, apostrophes)
    _fullname = re.compile(
        r"""(?x)\b
            \p{Lu}\p{L}+(?:[-']\p{Lu}\p{L}+)*    # First
            \s+
            \p{Lu}\p{L}+(?:[-']\p{Lu}\p{L}+)*    # Last
            \b
        """
    )

    def __init__(self, tokenizer, eos_id: int, kinds: List[str], max_sents: List[int], tail_chars: int = 600):
        self.tok = tokenizer
        self.eos_id = eos_id
        self.kinds = kinds
        self.max_sents = max_sents
        self.tail_chars = tail_chars

        self._prev_len = None   # tensor[int] per batch
        self._buf = None        # list[str] per sample
        self._sent_counts = None
        self._inited = False

    def _init(self, input_ids: torch.LongTensor):
        bsz, seqlen = input_ids.size(0), input_ids.size(1)
        self._prev_len = torch.full((bsz,), seqlen, dtype=torch.long, device=input_ids.device)
        self._buf = ["" for _ in range(bsz)]
        self._sent_counts = [0 for _ in range(bsz)]
        self._inited = True

    def _update_bufs(self, input_ids: torch.LongTensor):
        bsz, cur_len = input_ids.size(0), input_ids.size(1)
        for i in range(bsz):
            start = int(self._prev_len[i].item())
            if cur_len > start:
                new_ids = input_ids[i, start:cur_len]
                if new_ids.numel() > 0:
                    # decode only the tail; avoid clean_up to keep spacing predictable
                    text = self.tok.decode(new_ids, skip_special_tokens=True, clean_up_tokenization_spaces=False)
                    self._buf[i] += text
                    # trim rolling buffer
                    if len(self._buf[i]) > self.tail_chars:
                        self._buf[i] = self._buf[i][-self.tail_chars:]
                self._prev_len[i] = cur_len

                # update sentence count only for types that need it
                if self.kinds[i] in ("APPEARANCE", "BIOGRAPHY"):
                    for _ in self._sent_boundary.finditer(self._buf[i]):
                        self._sent_counts[i] += 1

    def _should_stop(self, i: int) -> bool:
        kind = self.kinds[i]
        if kind == "NAME":
            # stop once a full name appears
            return bool(self._fullname.search(self._buf[i]))
        elif kind in ("APPEARANCE", "BIOGRAPHY"):
            # stop after N sentences (per-sample max_sents)
            return self._sent_counts[i] >= max(1, int(self.max_sents[i]))
        else:
            return False

    def __call__(self, input_ids: torch.LongTensor, scores: torch.FloatTensor) -> torch.FloatTensor:
        if not self._inited:
            self._init(input_ids)

        # update rolling text buffers for all samples
        self._update_bufs(input_ids)

        # force EOS per sample that met its condition
        bsz = input_ids.size(0)
        for i in range(bsz):
            if self._should_stop(i):
                scores[i, :] = -float("inf")
                scores[i, self.eos_id] = 0.0
        return scores
