"""Load the business's documents, split them into passages and search them.

Search is BM25 (the classic ranking function behind most search engines), written
in plain Python so the bot runs anywhere with no vector database or embedding API.
For a few hundred pages of FAQs and policies it is fast and accurate; swap in
embeddings later if a client's knowledge base grows into the thousands of pages.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

SUPPORTED = {".md", ".txt"}

_STOPWORDS = set(
    """a an and are as at be but by can do does for from has have how i if in is it its
    me my of on or our so that the their them there they this to was we what when where
    which who will with you your hi hello hey please thanks thank ok okay just also would
    could should can't don't long much many need get got like want know tell any about
    still after before i'm i've im ive yes no""".split()
)


_SUFFIXES = ("ment", "ing", "ies", "ed", "es", "ly", "s", "y")


def stem(word: str) -> str:
    """Tiny suffix-stripping stemmer: delivery/delivered -> deliver, shipping -> ship,
    opening -> open, payments -> pay. Good enough for FAQ-style search."""
    if len(word) <= 4 or word.isdigit():
        return word
    for suf in _SUFFIXES:
        if word.endswith(suf) and len(word) - len(suf) >= 3:
            if suf == "s" and word.endswith("ss"):
                continue
            word = word[: -len(suf)] + ("y" if suf == "ies" else "")
            if len(word) > 3 and word[-1] == word[-2] and word[-1] not in "aeiouls":
                word = word[:-1]  # shipp -> ship
            break
    return word


def tokenize(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9$]+", text.lower())
    return [stem(w) for w in words if w not in _STOPWORDS]


@dataclass
class Passage:
    doc: str          # file name, shown to the user as the source
    heading: str      # nearest markdown heading
    text: str

    @property
    def source(self) -> str:
        return f"{self.doc} › {self.heading}" if self.heading else self.doc


def split_document(name: str, text: str, max_chars: int = 900) -> list[Passage]:
    """Split on markdown headings, then on paragraphs if a section is long."""
    passages: list[Passage] = []
    heading = ""
    buf: list[str] = []

    def flush() -> None:
        body = "\n".join(buf).strip()
        if not body:
            return
        chunk: list[str] = []
        size = 0
        for para in re.split(r"\n\s*\n", body):
            if size + len(para) > max_chars and chunk:
                passages.append(Passage(name, heading, "\n\n".join(chunk)))
                chunk, size = [], 0
            chunk.append(para.strip())
            size += len(para)
        if chunk:
            passages.append(Passage(name, heading, "\n\n".join(chunk)))

    for line in text.splitlines():
        m = re.match(r"^#{1,4}\s+(.*)", line)
        if m:
            flush()
            buf = []
            heading = m.group(1).strip()
        else:
            buf.append(line)
    flush()
    return passages


class KnowledgeBase:
    def __init__(self, passages: list[Passage], k1: float = 1.5, b: float = 0.75):
        self.passages = passages
        self.k1, self.b = k1, b
        self._docs = [tokenize(p.heading + " " + p.text) for p in passages]
        self._tf = [Counter(d) for d in self._docs]
        self._len = [len(d) for d in self._docs]
        self._avg = sum(self._len) / max(len(self._len), 1)
        df: Counter[str] = Counter()
        for d in self._docs:
            df.update(set(d))
        n = len(self._docs)
        self._idf = {t: math.log(1 + (n - c + 0.5) / (c + 0.5)) for t, c in df.items()}

    @classmethod
    def from_dir(cls, folder: Path) -> "KnowledgeBase":
        passages: list[Passage] = []
        for path in sorted(folder.rglob("*")):
            if path.suffix.lower() in SUPPORTED and path.is_file():
                passages.extend(split_document(path.name, path.read_text(encoding="utf-8")))
        if not passages:
            raise ValueError(f"No .md or .txt documents found in {folder}")
        return cls(passages)

    def unknown_terms(self, query: str) -> list[str]:
        """Words in the question that appear nowhere in the documents (numbers ignored)."""
        mapped = {stem(k) for k in self.SYNONYMS if " " not in k}
        return [
            t for t in tokenize(query)
            if t.isalpha() and len(t) >= 3 and t not in self._idf and t not in mapped
        ]

    # Customers and documents often use different words for the same thing.
    SYNONYMS = {
        "how much": ["price"], "cost": ["price"], "expensive": ["price"], "cheap": ["price"],
        "refund": ["return"], "send back": ["return"], "open": ["hour"], "close": ["hour"],
        "guarantee": ["warranty"], "broken": ["warranty"], "faulty": ["warranty"],
        "where are you": ["address", "showroom"], "located": ["address", "showroom"],
        "where is my": ["track"], "arrive": ["track", "deliver"], "pay": ["payment"], "postage": ["deliver"],
    }

    def expand(self, query: str) -> list[str]:
        q = query.lower()
        terms = tokenize(query)
        for phrase, extra in self.SYNONYMS.items():
            if re.search(rf"\b{phrase}", q):
                terms += [stem(e) for e in extra]
        return terms

    def search(self, query: str, k: int = 4) -> list[tuple[Passage, float]]:
        terms = self.expand(query)
        scores = []
        for i, tf in enumerate(self._tf):
            s = 0.0
            for t in terms:
                if t not in tf:
                    continue
                f = tf[t]
                denom = f + self.k1 * (1 - self.b + self.b * self._len[i] / self._avg)
                s += self._idf.get(t, 0.0) * f * (self.k1 + 1) / denom
            if s > 0:
                scores.append((s, i))
        scores.sort(reverse=True)
        return [(self.passages[i], s) for s, i in scores[:k]]
