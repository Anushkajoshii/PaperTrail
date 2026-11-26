"""Handling untrusted text (web pages, uploads) before it goes anywhere near an LLM.

Defence in depth against prompt injection (see ADR-006):
1. Remove invisible characters that can hide text from humans but not from models.
2. Replace sentences that read like instructions to an AI with a visible placeholder (and count
   them). Chat-template tokens such as <|im_start|> or [INST] are cut out wherever they appear.
3. Wrap the result in data tags that the text itself cannot close.
4. Prompts tell the model that tagged content is data, and tools are never exposed to page text.

No filter is perfect. That is why step 4 exists and why page text can never trigger actions.
"""

from __future__ import annotations

import html
import re

REMOVED_PLACEHOLDER = "[removed: instruction-like text]"

_INVISIBLE = re.compile("[​-‏‪-‮⁠-⁤﻿­]")

_INSTRUCTION_PATTERNS = [
    r"\b(ignore|disregard|forget|override)\b.{0,40}\b(previous|prior|above|earlier|all|any|your)\b"
    r".{0,40}\b(instructions?|prompts?|rules?|guidelines?|directions?)\b",
    r"\byou are (now )?(an?|the|my) (ai|assistant|language model|chatbot|llm)\b",
    r"\b(system|developer) (prompt|message|instructions?)\b",
    r"\bnew instructions?\b",
    r"(^|\s)(assistant|system|user)\s*:",
    r"\b(mark|rate|label|classify|treat|consider)\b.{0,30}\b(this|the)\b.{0,20}"
    r"\b(claim|article|page|source|statement)\b.{0,20}\b(as )?(true|supported|verified|accurate|"
    r"reliable|legitimate)\b",
    r"\b(respond|answer|reply|output)\b.{0,20}\b(only|exactly)\b.{0,10}\bwith\b",
]
# Chat-template control tokens: removed in place, wherever they appear.
_CONTROL_TOKENS = re.compile(r"<\|[^|>]{0,40}\|>|\[/?INST\]|<</?SYS>>", re.IGNORECASE)
_INSTRUCTION = re.compile("|".join(f"(?:{p})" for p in _INSTRUCTION_PATTERNS), re.IGNORECASE)
_SENTENCE = re.compile(r"[^.!?।\n]+[.!?।]?|\n")
_SPACES = re.compile(r"[ \t\f\v]+")
_BLANK_LINES = re.compile(r"\n{3,}")


def sanitize_untrusted_text(text: str) -> tuple[str, int]:
    """Return (clean_text, number_of_instruction_like_sentences_removed)."""
    text = html.unescape(_INVISIBLE.sub("", text))
    text, removed = _CONTROL_TOKENS.subn(f" {REMOVED_PLACEHOLDER} ", text)
    out: list[str] = []
    for piece in _SENTENCE.findall(text):
        if piece != "\n" and _INSTRUCTION.search(piece):
            removed += 1
            if not out or out[-1].strip() != REMOVED_PLACEHOLDER:
                out.append(f" {REMOVED_PLACEHOLDER}")
        else:
            out.append(piece)
    clean = _SPACES.sub(" ", "".join(out))
    clean = "\n".join(line.strip() for line in clean.split("\n"))
    return _BLANK_LINES.sub("\n\n", clean).strip(), removed


def wrap_as_data(tag: str, text: str, **attrs: str) -> str:
    """Wrap text in <tag ...>...</tag> so the content cannot close or fake the tag."""
    escaped = re.sub(rf"<(/?)\s*{re.escape(tag)}\b", r"&lt;\1" + tag, text, flags=re.IGNORECASE)
    attr_str = "".join(f' {k}="{html.escape(v, quote=True)}"' for k, v in attrs.items())
    return f"<{tag}{attr_str}>\n{escaped}\n</{tag}>"
