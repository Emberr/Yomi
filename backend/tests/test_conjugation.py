# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tests for the rule-based conjugation engine (M3.7).

Coverage targets
----------------
- All ichidan forms
- All godan te-form ending groups (く/ぐ/す/む/ぬ/ぶ/つ/う/る)
- Godan special overrides: 行く, ある, 問う
- Irregular verbs: する, 勉強する compound, 来る
- I-adjective: regular (高い) and irregular stem (いい, 良い)
- Na-adjective: 静か, きれい
- Copula: だ (all forms), です (limited forms)
- Error cases: empty lemma, unknown form, unknown word_type, unsupported combos
- Ambiguous godan-る verbs with explicit word_type

No database or network access is used anywhere in this module.
"""

from __future__ import annotations

import pytest

from yomi.services.conjugation_engine import (
    ConjugationError,
    UnknownFormError,
    UnknownWordTypeError,
    conjugate,
)


# ===========================================================================
# Ichidan verbs
# ===========================================================================


class TestIchidan:
    def test_te_form(self):
        assert conjugate("食べる", "te-form") == "食べて"

    def test_negative_plain(self):
        assert conjugate("見る", "negative-plain") == "見ない"

    def test_masu_form(self):
        assert conjugate("食べる", "masu-form") == "食べます"

    def test_past_plain(self):
        assert conjugate("食べる", "past-plain") == "食べた"

    def test_dictionary(self):
        assert conjugate("食べる", "dictionary") == "食べる"

    def test_potential(self):
        assert conjugate("食べる", "potential") == "食べられる"

    def test_volitional(self):
        assert conjugate("食べる", "volitional") == "食べよう"

    def test_imperative(self):
        assert conjugate("食べる", "imperative") == "食べろ"

    def test_conditional_ba(self):
        assert conjugate("食べる", "conditional-ba") == "食べれば"

    def test_passive(self):
        assert conjugate("食べる", "passive") == "食べられる"

    def test_causative(self):
        assert conjugate("食べる", "causative") == "食べさせる"

    def test_miru_negative(self):
        assert conjugate("見る", "negative-plain") == "見ない"

    def test_explicit_word_type(self):
        assert conjugate("食べる", "te-form", word_type="ichidan") == "食べて"


# ===========================================================================
# Godan verbs — te-form ending groups
# ===========================================================================


class TestGodanTeForms:
    """One test per godan ending group for te-form (and spot-check ta-form)."""

    def test_ku_te(self):
        assert conjugate("書く", "te-form") == "書いて"

    def test_ku_past(self):
        assert conjugate("書く", "past-plain") == "書いた"

    def test_gu_te(self):
        assert conjugate("泳ぐ", "te-form") == "泳いで"

    def test_gu_past(self):
        assert conjugate("泳ぐ", "past-plain") == "泳いだ"

    def test_mu_te(self):
        assert conjugate("読む", "te-form") == "読んで"

    def test_nu_te(self):
        assert conjugate("死ぬ", "te-form") == "死んで"

    def test_bu_te(self):
        assert conjugate("遊ぶ", "te-form") == "遊んで"

    def test_tsu_te(self):
        assert conjugate("待つ", "te-form") == "待って"

    def test_u_te(self):
        assert conjugate("買う", "te-form") == "買って"

    def test_ru_godan_te(self):
        # Ambiguous -る verb; must supply word_type
        assert conjugate("走る", "te-form", word_type="godan") == "走って"

    def test_iku_te_special(self):
        # 行く is a godan-く verb but te-form is 行って, not 行いて
        assert conjugate("行く", "te-form") == "行って"

    def test_iku_past_special(self):
        assert conjugate("行く", "past-plain") == "行った"


# ===========================================================================
# Godan verbs — non-te forms
# ===========================================================================


class TestGodanForms:
    def test_masu(self):
        assert conjugate("書く", "masu-form") == "書きます"

    def test_negative(self):
        assert conjugate("書く", "negative-plain") == "書かない"

    def test_dictionary(self):
        assert conjugate("書く", "dictionary") == "書く"

    def test_potential(self):
        assert conjugate("書く", "potential") == "書ける"

    def test_volitional(self):
        assert conjugate("書く", "volitional") == "書こう"

    def test_imperative(self):
        assert conjugate("書く", "imperative") == "書け"

    def test_conditional_ba(self):
        assert conjugate("書く", "conditional-ba") == "書けば"

    def test_passive(self):
        assert conjugate("書く", "passive") == "書かれる"

    def test_causative(self):
        assert conjugate("書く", "causative") == "書かせる"

    def test_u_negative(self):
        # う a-row is わ (not あ)
        assert conjugate("買う", "negative-plain") == "買わない"

    def test_u_masu(self):
        assert conjugate("買う", "masu-form") == "買います"

    def test_u_potential(self):
        assert conjugate("買う", "potential") == "買える"

    def test_ru_godan_negative(self):
        assert conjugate("走る", "negative-plain", word_type="godan") == "走らない"

    def test_ru_godan_masu(self):
        assert conjugate("走る", "masu-form", word_type="godan") == "走ります"


# ===========================================================================
# Godan specials: ある and 問う
# ===========================================================================


class TestGodanSpecials:
    def test_aru_negative_irregular(self):
        # ある negative is ない, not あらない
        assert conjugate("ある", "negative-plain") == "ない"

    def test_aru_masu(self):
        assert conjugate("ある", "masu-form") == "あります"

    def test_aru_te(self):
        assert conjugate("ある", "te-form") == "あって"

    def test_aru_past(self):
        assert conjugate("ある", "past-plain") == "あった"

    def test_tou_te_special(self):
        # 問う: te-form documented as 問うて (archaic/formal preference)
        assert conjugate("問う", "te-form") == "問うて"

    def test_tou_past_special(self):
        assert conjugate("問う", "past-plain") == "問うた"

    def test_tou_masu(self):
        assert conjugate("問う", "masu-form") == "問います"


# ===========================================================================
# Irregular verbs: する and 〜する compounds
# ===========================================================================


class TestSuru:
    def test_negative(self):
        assert conjugate("する", "negative-plain") == "しない"

    def test_masu(self):
        assert conjugate("する", "masu-form") == "します"

    def test_te(self):
        assert conjugate("する", "te-form") == "して"

    def test_past(self):
        assert conjugate("する", "past-plain") == "した"

    def test_potential(self):
        assert conjugate("する", "potential") == "できる"

    def test_compound_masu(self):
        assert conjugate("勉強する", "masu-form") == "勉強します"

    def test_compound_potential(self):
        assert conjugate("勉強する", "potential") == "勉強できる"

    def test_compound_negative(self):
        assert conjugate("勉強する", "negative-plain") == "勉強しない"

    def test_compound_te(self):
        assert conjugate("勉強する", "te-form") == "勉強して"


# ===========================================================================
# Irregular verbs: 来る
# ===========================================================================


class TestKuru:
    def test_masu(self):
        assert conjugate("来る", "masu-form") == "来ます"

    def test_negative(self):
        assert conjugate("来る", "negative-plain") == "来ない"

    def test_te(self):
        assert conjugate("来る", "te-form") == "来て"

    def test_past(self):
        assert conjugate("来る", "past-plain") == "来た"

    def test_potential(self):
        assert conjugate("来る", "potential") == "来られる"

    def test_volitional(self):
        assert conjugate("来る", "volitional") == "来よう"

    def test_imperative(self):
        assert conjugate("来る", "imperative") == "来い"

    def test_conditional_ba(self):
        assert conjugate("来る", "conditional-ba") == "来れば"


# ===========================================================================
# I-adjectives
# ===========================================================================


class TestIAdjective:
    def test_negative(self):
        assert conjugate("高い", "negative-plain") == "高くない"

    def test_past(self):
        assert conjugate("高い", "past-plain") == "高かった"

    def test_te(self):
        assert conjugate("高い", "te-form") == "高くて"

    def test_conditional_ba(self):
        assert conjugate("高い", "conditional-ba") == "高ければ"

    def test_dictionary(self):
        assert conjugate("高い", "dictionary") == "高い"

    def test_ii_negative_special_stem(self):
        # いい uses よ- stem for all conjugated forms
        assert conjugate("いい", "negative-plain") == "よくない"

    def test_ii_past(self):
        assert conjugate("いい", "past-plain") == "よかった"

    def test_ii_te(self):
        assert conjugate("いい", "te-form") == "よくて"

    def test_yoi_kanji_negative(self):
        # 良い: strip い → 良, then 良くない
        assert conjugate("良い", "negative-plain") == "良くない"

    def test_yoi_kanji_past(self):
        assert conjugate("良い", "past-plain") == "良かった"

    def test_i_adj_unsupported_potential(self):
        with pytest.raises(UnknownFormError):
            conjugate("高い", "potential")

    def test_i_adj_unsupported_volitional(self):
        with pytest.raises(UnknownFormError):
            conjugate("高い", "volitional")

    def test_i_adj_unsupported_passive(self):
        with pytest.raises(UnknownFormError):
            conjugate("高い", "passive")


# ===========================================================================
# Na-adjectives
# ===========================================================================


class TestNaAdjective:
    def test_negative(self):
        assert conjugate("静か", "negative-plain", word_type="na-adjective") == "静かではない"

    def test_past(self):
        assert conjugate("静か", "past-plain", word_type="na-adjective") == "静かだった"

    def test_te(self):
        assert conjugate("静か", "te-form", word_type="na-adjective") == "静かで"

    def test_dictionary(self):
        assert conjugate("静か", "dictionary", word_type="na-adjective") == "静かだ"

    def test_conditional_ba(self):
        assert conjugate("静か", "conditional-ba", word_type="na-adjective") == "静かであれば"

    def test_kirei_negative(self):
        assert conjugate("きれい", "negative-plain", word_type="na-adjective") == "きれいではない"

    def test_na_adj_unsupported_potential(self):
        with pytest.raises(UnknownFormError):
            conjugate("静か", "potential", word_type="na-adjective")

    def test_na_adj_unsupported_imperative(self):
        with pytest.raises(UnknownFormError):
            conjugate("静か", "imperative", word_type="na-adjective")


# ===========================================================================
# Copula: だ
# ===========================================================================


class TestCopulaDa:
    def test_negative(self):
        assert conjugate("だ", "negative-plain", word_type="copula") == "ではない"

    def test_past(self):
        assert conjugate("だ", "past-plain", word_type="copula") == "だった"

    def test_te(self):
        assert conjugate("だ", "te-form", word_type="copula") == "で"

    def test_dictionary(self):
        assert conjugate("だ", "dictionary", word_type="copula") == "だ"

    def test_conditional_ba(self):
        # Copula conditional uses なら
        assert conjugate("だ", "conditional-ba", word_type="copula") == "なら"

    def test_copula_unsupported_potential(self):
        with pytest.raises(UnknownFormError):
            conjugate("だ", "potential", word_type="copula")

    def test_copula_unsupported_causative(self):
        with pytest.raises(UnknownFormError):
            conjugate("だ", "causative", word_type="copula")


# ===========================================================================
# Copula: です (limited)
# ===========================================================================


class TestCopulaDes:
    def test_dictionary(self):
        assert conjugate("です", "dictionary", word_type="copula") == "です"

    def test_negative(self):
        assert conjugate("です", "negative-plain", word_type="copula") == "ではありません"

    def test_past(self):
        assert conjugate("です", "past-plain", word_type="copula") == "でした"

    def test_te(self):
        assert conjugate("です", "te-form", word_type="copula") == "で"


# ===========================================================================
# Error handling
# ===========================================================================


class TestErrors:
    def test_empty_lemma_raises(self):
        with pytest.raises(ConjugationError):
            conjugate("", "te-form")

    def test_unknown_form_raises(self):
        with pytest.raises(UnknownFormError):
            conjugate("食べる", "gerund")

    def test_unknown_word_type_raises(self):
        with pytest.raises(UnknownWordTypeError):
            conjugate("食べる", "te-form", word_type="verb")

    def test_unknown_form_is_subclass_of_conjugation_error(self):
        with pytest.raises(ConjugationError):
            conjugate("食べる", "xyz")

    def test_unknown_word_type_is_subclass_of_conjugation_error(self):
        with pytest.raises(ConjugationError):
            conjugate("食べる", "te-form", word_type="mystery")

    def test_godan_explicit_override_ambiguous_ru(self):
        # 帰る looks ichidan but is godan — must supply word_type
        result = conjugate("帰る", "te-form", word_type="godan")
        assert result == "帰って"

    def test_auto_detect_ambiguous_ru_defaults_ichidan(self):
        # Without word_type, 走る is treated as ichidan (conservative)
        result = conjugate("走る", "te-form")
        assert result == "走て"  # ichidan stem 走 + て

    def test_masu_form_not_supported_for_copula(self):
        with pytest.raises(UnknownFormError):
            conjugate("だ", "masu-form", word_type="copula")
