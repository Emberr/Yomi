# SPDX-License-Identifier: AGPL-3.0-or-later
"""Rule-based Japanese conjugation engine.

Design notes
------------
- Fully deterministic; no AI, no network, no DB access.
- ``word_type`` must be supplied for ambiguous cases (e.g., godan-る verbs
  like 走る, 帰る, 切る that superficially look like ichidan).
- Auto-detection is conservative: bare -る verbs default to ichidan; known
  specials (行く, ある, 問う) are detected explicitly.
- Counter/classifier logic is intentionally absent; see future counter_engine.py.

Na-adjective conditional: uses ``であれば`` (formal written style).
Copula conditional: uses ``なら`` (colloquial spoken default).
"""

from __future__ import annotations

__all__ = [
    "ConjugationError",
    "UnknownFormError",
    "UnknownWordTypeError",
    "conjugate",
]


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ConjugationError(ValueError):
    """Base error for all conjugation failures."""


class UnknownFormError(ConjugationError):
    """Requested form is unknown or not supported for this word type."""


class UnknownWordTypeError(ConjugationError):
    """The supplied word_type string is not recognised."""


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_WORD_TYPES: frozenset[str] = frozenset(
    {"ichidan", "godan", "irregular", "i-adjective", "na-adjective", "copula"}
)

VALID_FORMS: frozenset[str] = frozenset({
    "dictionary",
    "masu-form",
    "negative-plain",
    "past-plain",
    "te-form",
    "potential",
    "volitional",
    "imperative",
    "conditional-ba",
    "passive",
    "causative",
})

# Godan final kana → (a-row, i-row, e-row, o-row, te-suffix, ta-suffix)
# Note: う a-row is わ (not あ) because 買う → 買わない, 買われる, etc.
_GODAN_TABLE: dict[str, tuple[str, str, str, str, str, str]] = {
    "う": ("わ", "い", "え", "お", "って", "った"),
    "く": ("か", "き", "け", "こ", "いて", "いた"),
    "ぐ": ("が", "ぎ", "げ", "ご", "いで", "いだ"),
    "す": ("さ", "し", "せ", "そ", "して", "した"),
    "つ": ("た", "ち", "て", "と", "って", "った"),
    "ぬ": ("な", "に", "ね", "の", "んで", "んだ"),
    "ぶ": ("ば", "び", "べ", "ぼ", "んで", "んだ"),
    "む": ("ま", "み", "め", "も", "んで", "んだ"),
    "る": ("ら", "り", "れ", "ろ", "って", "った"),
}

# Full irregular conjugation tables (lemma → form → result)
_IRREGULAR_TABLE: dict[str, dict[str, str]] = {
    "する": {
        "dictionary":    "する",
        "masu-form":     "します",
        "negative-plain":"しない",
        "past-plain":    "した",
        "te-form":       "して",
        "potential":     "できる",
        "volitional":    "しよう",
        "imperative":    "しろ",
        "conditional-ba":"すれば",
        "passive":       "される",
        "causative":     "させる",
    },
    "来る": {
        "dictionary":    "来る",
        "masu-form":     "来ます",
        "negative-plain":"来ない",
        "past-plain":    "来た",
        "te-form":       "来て",
        "potential":     "来られる",
        "volitional":    "来よう",
        "imperative":    "来い",
        "conditional-ba":"来れば",
        "passive":       "来られる",
        "causative":     "来させる",
    },
    # Kana-only variant of 来る
    "くる": {
        "dictionary":    "くる",
        "masu-form":     "きます",
        "negative-plain":"こない",
        "past-plain":    "きた",
        "te-form":       "きて",
        "potential":     "こられる",
        "volitional":    "こよう",
        "imperative":    "こい",
        "conditional-ba":"くれば",
        "passive":       "こられる",
        "causative":     "こさせる",
    },
}

# Godan specials that still use _conjugate_godan but have form overrides
_GODAN_SPECIALS: frozenset[str] = frozenset({"行く", "ある", "問う"})

# Forms that do not apply to adjectives or copula
_ADJ_UNSUPPORTED: frozenset[str] = frozenset(
    {"masu-form", "potential", "volitional", "imperative", "passive", "causative"}
)


# ---------------------------------------------------------------------------
# Internal conjugators
# ---------------------------------------------------------------------------


def _conjugate_ichidan(lemma: str, form: str) -> str:
    if not lemma.endswith("る"):
        raise ConjugationError(
            f"Ichidan verb '{lemma}' must end in る; supply word_type if godan"
        )
    stem = lemma[:-1]
    match form:
        case "dictionary":      return lemma
        case "masu-form":       return stem + "ます"
        case "negative-plain":  return stem + "ない"
        case "past-plain":      return stem + "た"
        case "te-form":         return stem + "て"
        case "potential":       return stem + "られる"
        case "volitional":      return stem + "よう"
        case "imperative":      return stem + "ろ"
        case "conditional-ba":  return stem + "れば"
        case "passive":         return stem + "られる"
        case "causative":       return stem + "させる"
        case _:
            raise UnknownFormError(f"Unknown form '{form}'")


def _conjugate_godan(lemma: str, form: str) -> str:
    last = lemma[-1]
    if last not in _GODAN_TABLE:
        raise ConjugationError(
            f"Godan verb '{lemma}' ends in '{last}' which is not a godan kana"
        )
    stem = lemma[:-1]
    a, i, e, o, te_suf, ta_suf = _GODAN_TABLE[last]

    # --- per-lemma overrides ---

    # 行く: te-form=行って, past=行った (not 行いて/行いた)
    if lemma == "行く":
        if form == "te-form":   return "行って"
        if form == "past-plain": return "行った"

    # 問う: te-form=問うて (irregular/archaic; documented special case)
    # The regular godan-う te-form would be 問って, but 問うて is conventional.
    if lemma == "問う":
        if form == "te-form":    return "問うて"
        if form == "past-plain": return "問うた"

    # ある: negative-plain=ない (not あらない)
    if lemma == "ある" and form == "negative-plain":
        return "ない"

    # --- normal godan dispatch ---
    match form:
        case "dictionary":      return lemma
        case "masu-form":       return stem + i + "ます"
        case "negative-plain":  return stem + a + "ない"
        case "past-plain":      return stem + ta_suf
        case "te-form":         return stem + te_suf
        case "potential":       return stem + e + "る"
        case "volitional":      return stem + o + "う"
        case "imperative":      return stem + e
        case "conditional-ba":  return stem + e + "ば"
        case "passive":         return stem + a + "れる"
        case "causative":       return stem + a + "せる"
        case _:
            raise UnknownFormError(f"Unknown form '{form}'")


def _conjugate_suru_compound(lemma: str, form: str) -> str:
    """〜する compound: strip する, apply する table, substitute prefix."""
    prefix = lemma[:-2]
    suru = _IRREGULAR_TABLE["する"]
    if form == "potential":
        return prefix + "できる"
    if form not in suru:
        raise UnknownFormError(f"Unknown form '{form}' for suru compound")
    base_result = suru[form]
    # Replace leading する-specific characters with prefix + conjugated tail.
    # The する table entries all start with し/す/さ which belongs to する itself.
    # Strip the leading する contribution and prepend prefix.
    return prefix + base_result


def _conjugate_irregular(lemma: str, form: str) -> str:
    if lemma.endswith("する") and len(lemma) > 2:
        return _conjugate_suru_compound(lemma, form)
    if lemma not in _IRREGULAR_TABLE:
        raise ConjugationError(f"No irregular entry for '{lemma}'")
    table = _IRREGULAR_TABLE[lemma]
    if form not in table:
        raise UnknownFormError(
            f"Form '{form}' not supported for irregular verb '{lemma}'"
        )
    return table[form]


def _conjugate_i_adjective(lemma: str, form: str) -> str:
    if form in _ADJ_UNSUPPORTED:
        raise UnknownFormError(
            f"Form '{form}' is not applicable to i-adjectives"
        )
    # いい uses よ- stem for all conjugated forms (not い-)
    if lemma == "いい":
        stem = "よ"
    elif lemma.endswith("い"):
        stem = lemma[:-1]
    else:
        raise ConjugationError(f"I-adjective '{lemma}' must end in い")

    match form:
        case "dictionary":      return lemma
        case "negative-plain":  return stem + "くない"
        case "past-plain":      return stem + "かった"
        case "te-form":         return stem + "くて"
        case "conditional-ba":  return stem + "ければ"
        case _:
            raise UnknownFormError(f"Unknown form '{form}' for i-adjective")


def _conjugate_na_adjective(lemma: str, form: str) -> str:
    """Lemma is the bare stem (no だ appended), e.g., 静か, きれい."""
    if form in _ADJ_UNSUPPORTED:
        raise UnknownFormError(
            f"Form '{form}' is not applicable to na-adjectives"
        )
    # conditional-ba uses であれば (formal written style)
    match form:
        case "dictionary":      return lemma + "だ"
        case "negative-plain":  return lemma + "ではない"
        case "past-plain":      return lemma + "だった"
        case "te-form":         return lemma + "で"
        case "conditional-ba":  return lemma + "であれば"
        case _:
            raise UnknownFormError(f"Unknown form '{form}' for na-adjective")


def _conjugate_copula(lemma: str, form: str) -> str:
    """Support だ (all forms) and です (limited forms).

    Copula conditional uses なら (colloquial default).
    """
    if lemma not in ("だ", "です"):
        raise ConjugationError(
            f"Unknown copula lemma '{lemma}'; expected 'だ' or 'です'"
        )
    if form in _ADJ_UNSUPPORTED:
        raise UnknownFormError(
            f"Form '{form}' is not applicable to copula"
        )

    if lemma == "です":
        match form:
            case "dictionary":      return "です"
            case "negative-plain":  return "ではありません"
            case "past-plain":      return "でした"
            case "te-form":         return "で"
            case "conditional-ba":  return "でなければ"
            case _:
                raise UnknownFormError(
                    f"Form '{form}' not supported for copula 'です'"
                )

    # だ
    match form:
        case "dictionary":      return "だ"
        case "negative-plain":  return "ではない"
        case "past-plain":      return "だった"
        case "te-form":         return "で"
        case "conditional-ba":  return "なら"
        case _:
            raise UnknownFormError(f"Unknown form '{form}' for copula 'だ'")


# ---------------------------------------------------------------------------
# Auto-detection
# ---------------------------------------------------------------------------


def _detect_word_type(lemma: str) -> str:
    """Conservative POS detection from lemma surface form only.

    Raises ``ConjugationError`` when classification is genuinely ambiguous
    (e.g., a naked -る verb that could be godan).  Callers should supply
    ``word_type`` explicitly in such cases.
    """
    # Known full-irregular verbs
    if lemma in _IRREGULAR_TABLE:
        return "irregular"
    # 〜する compounds (勉強する, 運動する, …)
    if lemma.endswith("する") and len(lemma) > 2:
        return "irregular"
    # Godan specials detected explicitly so they don't fall through to ichidan
    if lemma in _GODAN_SPECIALS:
        return "godan"
    # いい → i-adjective with special よ- stem
    if lemma in ("いい", "良い"):
        return "i-adjective"

    last = lemma[-1] if lemma else ""

    # -い ending → i-adjective (covers 高い, 楽しい, etc.)
    if last == "い":
        return "i-adjective"
    # -る ending → ichidan by default (ambiguous godan-る verbs like 走る
    # require explicit word_type="godan")
    if last == "る":
        return "ichidan"
    # Unambiguous godan endings
    if last in _GODAN_TABLE:
        return "godan"

    raise ConjugationError(
        f"Cannot auto-detect word type for '{lemma}'; "
        "supply word_type explicitly"
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def conjugate(
    lemma: str,
    target_form: str,
    word_type: str | None = None,
) -> str:
    """Return the conjugated form of *lemma*.

    Parameters
    ----------
    lemma:
        Dictionary form of the word (e.g., ``"食べる"``, ``"書く"``,
        ``"高い"``).  For na-adjectives supply the bare stem without だ
        (e.g., ``"静か"``, ``"きれい"``).
    target_form:
        One of: ``dictionary``, ``masu-form``, ``negative-plain``,
        ``past-plain``, ``te-form``, ``potential``, ``volitional``,
        ``imperative``, ``conditional-ba``, ``passive``, ``causative``.
    word_type:
        One of: ``ichidan``, ``godan``, ``irregular``, ``i-adjective``,
        ``na-adjective``, ``copula``, or ``None`` for auto-detection.
        Must be supplied for ambiguous godan -る verbs (走る, 帰る, …).

    Raises
    ------
    ConjugationError
        Empty lemma or other unrecoverable input error.
    UnknownFormError
        ``target_form`` is not recognised, or is unsupported for the given
        word type (e.g., ``potential`` on an i-adjective).
    UnknownWordTypeError
        ``word_type`` string is not in the recognised set.
    """
    if not lemma:
        raise ConjugationError("lemma must not be empty")

    if target_form not in VALID_FORMS:
        raise UnknownFormError(f"Unknown target form '{target_form}'")

    if word_type is not None and word_type not in VALID_WORD_TYPES:
        raise UnknownWordTypeError(f"Unknown word_type '{word_type}'")

    effective_type = word_type if word_type is not None else _detect_word_type(lemma)

    match effective_type:
        case "ichidan":
            return _conjugate_ichidan(lemma, target_form)
        case "godan":
            return _conjugate_godan(lemma, target_form)
        case "irregular":
            return _conjugate_irregular(lemma, target_form)
        case "i-adjective":
            return _conjugate_i_adjective(lemma, target_form)
        case "na-adjective":
            return _conjugate_na_adjective(lemma, target_form)
        case "copula":
            return _conjugate_copula(lemma, target_form)
        case _:
            raise UnknownWordTypeError(f"Unknown word_type '{effective_type}'")
