"""Fast, deterministic news summaries with no model dependency."""
from __future__ import annotations

import re
from collections import Counter


ABBREVIATIONS = (
    "Dr.", "Prof.", "Ir.", "H.", "Hj.", "No.", "Rp.", "S.H.", "M.H.",
    "dll.", "dsb.", "dst.", "dkk.", "a.n.", "s.d.",
)
BOILERPLATE_PREFIXES = (
    "baca juga", "simak juga", "lihat juga", "foto:", "ilustrasi:",
    "advertisement", "scroll to continue", "simak video", "klik di sini",
)
STOPWORDS = {
    "yang", "dan", "di", "ke", "dari", "untuk", "pada", "dengan", "ini",
    "itu", "dalam", "atas", "oleh", "sebagai", "adalah", "akan", "telah",
    "atau", "karena", "juga", "para", "sebuah", "the", "a", "an", "of",
    "to", "in", "on", "for", "and", "is", "are", "was", "were", "with",
}


def _protect_abbreviations(text: str) -> str:
    protected = text
    for abbreviation in ABBREVIATIONS:
        protected = protected.replace(abbreviation, abbreviation.replace(".", "<DOT>"))
    protected = re.sub(r"(?<=\d)\.(?=\d)", "<DOT>", protected)
    return protected


def split_sentences(text: str) -> list[str]:
    """Split Indonesian/English prose while preserving common abbreviations."""
    normalized = re.sub(r"\s+", " ", text or "").strip()
    if not normalized:
        return []
    protected = _protect_abbreviations(normalized)
    parts = re.split(r"(?<=[.!?])\s+(?=[A-ZÀ-ÖØ-Þ0-9\"“‘])", protected)
    return [part.replace("<DOT>", ".").strip() for part in parts if part.strip()]


def _words(text: str) -> list[str]:
    return re.findall(r"[\wÀ-ÖØ-öø-ÿ'-]+", text.lower(), flags=re.UNICODE)


def _is_boilerplate(sentence: str) -> bool:
    lowered = sentence.lower().strip(" -–—")
    return any(lowered.startswith(prefix) for prefix in BOILERPLATE_PREFIXES)


def _clip_words(text: str, max_words: int) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text.strip()
    clipped = " ".join(words[:max_words]).rstrip(" ,;:-")
    return clipped + "."


def _clean_sentence(sentence: str) -> str:
    """Remove wire-service datelines while preserving the source sentence."""
    return re.sub(
        r"^[A-ZÀ-ÖØ-Þ][\wÀ-ÖØ-öø-ÿ .'-]{1,30}\s+\(ANTARA\)\s*[-–—]\s*",
        "",
        sentence,
    ).strip()


def publisher_summary(
    excerpt: str,
    title: str,
    *,
    max_sentences: int = 2,
    max_words: int = 60,
) -> str:
    """Use a publisher-authored RSS description as the preferred fallback."""
    if not excerpt.strip():
        return ""
    # Some feeds expose only a mechanically truncated teaser. It is safer to
    # extract complete source sentences than present an unfinished thought.
    if excerpt.strip().endswith(("...", "…")):
        return ""
    title_terms = {word for word in _words(title) if word not in STOPWORDS and len(word) > 2}
    excerpt_terms = set(_words(excerpt))
    if title_terms and len(title_terms & excerpt_terms) / len(title_terms) < 0.15:
        # The publisher teaser may start mid-context. Prefixing the factual
        # publisher headline keeps the fallback understandable without
        # generating or inferring any new claim.
        headline = title.strip().rstrip(".!?") + "."
        return _clip_words(f"{headline} {excerpt.strip()}", max_words)
    title_key = " ".join(_words(title))
    selected: list[str] = []
    word_count = 0
    for sentence in split_sentences(excerpt):
        if _is_boilerplate(sentence):
            continue
        sentence = _clean_sentence(sentence)
        sentence_words = sentence.split()
        if len(sentence_words) < 6:
            continue
        if " ".join(_words(sentence)) == title_key:
            continue
        remaining = max_words - word_count
        if remaining <= 0:
            break
        if selected and len(sentence_words) > remaining:
            break
        selected.append(_clip_words(sentence, remaining))
        word_count += min(len(sentence_words), remaining)
        if len(selected) >= max_sentences or word_count >= max_words:
            break
    return " ".join(selected).strip()


def extractive_summary(
    text: str,
    title: str,
    *,
    max_sentences: int = 2,
    max_words: int = 60,
) -> str:
    """Select informative source sentences without generating new wording."""
    sentences = [sentence for sentence in split_sentences(text) if not _is_boilerplate(sentence)]
    if not sentences:
        return ""

    title_terms = {word for word in _words(title) if word not in STOPWORDS and len(word) > 2}
    corpus_terms = Counter(
        word
        for sentence in sentences[:12]
        for word in _words(sentence)
        if word not in STOPWORDS and len(word) > 2
    )
    candidates: list[tuple[float, int, str]] = []
    title_key = " ".join(_words(title))

    for index, sentence in enumerate(sentences[:12]):
        sentence = _clean_sentence(sentence)
        words = _words(sentence)
        if not 8 <= len(words) <= 80:
            continue
        if " ".join(words) == title_key:
            continue
        if sentence.count('"') % 2 or sentence.count("“") != sentence.count("”"):
            continue
        unique = set(words)
        title_overlap = len(unique & title_terms) / max(1, len(title_terms))
        keyword_score = sum(corpus_terms[word] for word in unique) / max(1, len(unique))
        position_score = max(0.0, 3.0 - index * 0.25)
        facts_score = min(2.0, len(re.findall(r"\b\d[\d.,%]*\b", sentence)) * 0.5)
        proper_names = len(re.findall(r"(?<![.!?]\s)\b[A-Z][a-zÀ-öø-ÿ]+", sentence))
        score = position_score + title_overlap * 4 + keyword_score * 0.15 + facts_score + min(1.5, proper_names * 0.2)
        candidates.append((score, index, sentence))

    if not candidates:
        return publisher_summary(text, title, max_sentences=max_sentences, max_words=max_words)

    best = sorted(candidates, key=lambda item: item[0], reverse=True)[:max_sentences]
    best.sort(key=lambda item: item[1])
    selected: list[str] = []
    remaining = max_words
    for _, _, sentence in best:
        if remaining <= 0:
            break
        if selected and len(sentence.split()) > remaining:
            break
        clipped = _clip_words(sentence, remaining)
        selected.append(clipped)
        remaining -= len(clipped.split())
    return " ".join(selected).strip()


def deterministic_summary(
    excerpt: str,
    body: str,
    title: str,
    *,
    max_sentences: int = 2,
    max_words: int = 60,
) -> tuple[str, str]:
    """Return the best non-AI summary and its auditable origin."""
    summary = publisher_summary(
        excerpt, title, max_sentences=max_sentences, max_words=max_words
    )
    if summary:
        return summary, "publisher_summary"

    summary = extractive_summary(
        body, title, max_sentences=max_sentences, max_words=max_words
    )
    if summary:
        return summary, "extractive"

    return _clip_words(excerpt.strip(), max_words), "source_excerpt"
