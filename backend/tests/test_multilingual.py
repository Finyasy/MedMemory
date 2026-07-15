import asyncio
from types import SimpleNamespace

from app.services.llm.multilingual import (
    SUPPORTED_CHAT_LANGUAGES,
    MultilingualChatService,
)


def test_supported_chat_languages_are_english_and_swahili_only():
    assert set(SUPPORTED_CHAT_LANGUAGES) == {"en", "sw"}


def test_normalize_language_falls_back_to_english_for_unsupported_codes():
    assert MultilingualChatService.normalize_language("sw") == "sw"
    assert MultilingualChatService.normalize_language("kik") == "en"
    assert MultilingualChatService.normalize_language("luo") == "en"


def test_resolve_context_falls_back_to_english_for_unsupported_preference():
    service = MultilingualChatService(llm_service=SimpleNamespace())

    context = service.resolve_context(preferred_language="kik")

    assert context.input_language == "en"
    assert context.output_language == "en"
    assert context.translation_applied is False


class _FakeEnglishOnlyLLM:
    async def generate(self, **_kwargs):
        return SimpleNamespace(
            text="From your records: Hemoglobin: 10.1 g/dL (low) (source: lab_result#unknown)"
        )


def test_translate_answer_uses_swahili_fallback_when_model_returns_english():
    service = MultilingualChatService(llm_service=_FakeEnglishOnlyLLM())

    answer = (
        "From your records: Hemoglobin: 10.1 g/dL (low) "
        "(source: lab_result#unknown)"
    )

    translated = asyncio.run(
        service.translate_answer_from_english(answer, target_language="sw")
    )

    assert "Kutoka kwenye rekodi zako:" in translated
    assert "(chini)" in translated
    assert "(chanzo: lab_result#unknown)" in translated


class _FakeMarkdownSwahiliLLM:
    async def generate(self, **_kwargs):
        return SimpleNamespace(
            text=(
                "**HATUA:**\n\n"
                "* Sijapata data ya hatua za Apple Health inayojibu hilo bado.\n"
                "* Jaribu kusawazisha Apple Health tena."
            )
        )


def test_translate_answer_rejects_markdown_shape_for_plain_swahili_answer():
    service = MultilingualChatService(llm_service=_FakeMarkdownSwahiliLLM())

    answer = (
        "I couldn't find Apple Health step data that answers that yet. "
        "If you expected steps or activity here, try syncing Apple Health again "
        "and ask me about your last week of steps or recent activity trend."
    )

    translated = asyncio.run(
        service.translate_answer_from_english(answer, target_language="sw")
    )

    assert "**" not in translated
    assert "* " not in translated
    assert "Apple Health" in translated
    assert "wiki yako iliyopita" in translated


def test_translate_answer_fallback_handles_apple_health_summary_sentence():
    service = MultilingualChatService(llm_service=_FakeEnglishOnlyLLM())

    answer = (
        "Here's a quick Apple Health update: from 2026-03-04 to 2026-03-10, "
        "you logged 10,322 steps across 6 day(s), averaging about 1,720 steps a day. "
        "Your latest recorded day was 2026-03-10 with 0 steps. "
        "Apple Health is connected, with 18 synced day(s) overall."
    )

    translated = asyncio.run(
        service.translate_answer_from_english(answer, target_language="sw")
    )

    assert "Hapa kuna muhtasari mfupi wa Apple Health:" in translated
    assert "ulirekodi hatua 10,322" in translated
    assert "wastani wa karibu hatua 1,720 kwa siku" in translated
    assert "Siku yako ya hivi karibuni iliyorekodiwa ilikuwa 2026-03-10" in translated
    assert "ikiwa na hatua 0." in translated
    assert "siku 18 zilizolandanishwa kwa ujumla" in translated


class _FakePromptLeakSwahiliLLM:
    async def generate(self, **_kwargs):
        return SimpleNamespace(
            text=(
                "<unused94>thoughtThe user wants me to translate a medical patient "
                'answer from English to Swahili. The text to translate is: '
                '"From your records: Hemoglobin: 10.1 g/dL (low) '
                '(source: lab_result#unknown)" Let\'s break down the text.'
            )
        )


def test_translate_answer_rejects_prompt_leak_and_uses_swahili_fallback():
    service = MultilingualChatService(llm_service=_FakePromptLeakSwahiliLLM())

    answer = (
        "From your records: Hemoglobin: 10.1 g/dL (low) "
        "(source: lab_result#unknown)"
    )

    translated = asyncio.run(
        service.translate_answer_from_english(answer, target_language="sw")
    )

    assert translated == (
        "Kutoka kwenye rekodi zako: Hemoglobin: 10.1 g/dL (chini) "
        "(chanzo: lab_result#unknown)"
    )


class _FailingLLM:
    async def generate(self, **_kwargs):
        raise AssertionError("LLM should not be called for fast deterministic Swahili answers")


def test_translate_answer_uses_fast_deterministic_path_for_short_grounded_answers():
    service = MultilingualChatService(llm_service=_FailingLLM())

    answer = "Hemoglobin: 10.1 g/dL (low) (source: lab_result#unknown)"

    translated = asyncio.run(
        service.translate_answer_from_english(answer, target_language="sw")
    )

    assert translated == "Hemoglobin: 10.1 g/dL (chini) (chanzo: lab_result#unknown)"


def test_translate_answer_uses_fast_deterministic_path_for_multiline_medication_summary():
    service = MultilingualChatService(llm_service=_FailingLLM())

    answer = (
        "From your records, your active medications are:\n"
        "- Metformin — active (source: medication#1)\n"
        "- Aspirin — active (source: medication#2)"
    )

    translated = asyncio.run(
        service.translate_answer_from_english(answer, target_language="sw")
    )

    assert translated == (
        "Kutoka kwenye rekodi zako, dawa zako zinazotumika ni:\n"
        "- Metformin — inayotumika (chanzo: medication#1)\n"
        "- Aspirin — inayotumika (chanzo: medication#2)"
    )


def test_translate_answer_uses_fast_deterministic_path_for_trend_summary():
    service = MultilingualChatService(llm_service=_FailingLLM())

    answer = (
        "From your records, HbA1c changed from 6.8 % on 2026-01-01 to 7.2 % "
        "on 2026-03-01 (increased by 0.4 %)."
    )

    translated = asyncio.run(
        service.translate_answer_from_english(answer, target_language="sw")
    )

    assert translated == (
        "Kutoka kwenye rekodi zako, HbA1c ilibadilika kutoka 6.8 % tarehe "
        "2026-01-01 hadi 7.2 % tarehe 2026-03-01 (iliongezeka kwa 0.4 %)."
    )


def test_translate_answer_uses_fast_deterministic_path_for_long_apple_health_summary():
    service = MultilingualChatService(llm_service=_FailingLLM())

    answer = (
        "Here's a quick Apple Health update: from 2026-03-01 to 2026-03-07, "
        "you logged 42,000 steps across 7 day(s), averaging about 6,000 steps a day. "
        "Your latest recorded day was 2026-03-07 with 7,200 steps. "
        "Across that span, your daily steps increased by 1,200 compared with 2026-03-01. "
        "Apple Health is connected, with 18 synced day(s) overall."
    )

    translated = asyncio.run(
        service.translate_answer_from_english(answer, target_language="sw")
    )

    assert "Hapa kuna muhtasari mfupi wa Apple Health:" in translated
    assert "ulirekodi hatua 42,000 katika siku 7" in translated
    assert "Siku yako ya hivi karibuni iliyorekodiwa ilikuwa 2026-03-07 ikiwa na hatua 7,200." in translated
    assert "Katika kipindi hicho, hatua zako za kila siku ziliongezeka kwa 1,200 ikilinganishwa na 2026-03-01." in translated
    assert "Apple Health imeunganishwa, ikiwa na siku 18 zilizolandanishwa kwa ujumla." in translated


def test_translate_answer_uses_fast_deterministic_path_for_latest_document_unavailable():
    service = MultilingualChatService(llm_service=_FailingLLM())

    answer = (
        "I could not summarize the latest document because no completed document text "
        "is available yet. Please upload a document or wait for processing to finish."
    )

    translated = asyncio.run(
        service.translate_answer_from_english(answer, target_language="sw")
    )

    assert translated == (
        "Sikuweza kufupisha hati ya hivi karibuni kwa sababu maandishi ya hati "
        "yaliyokamilika hayajapatikana bado. Tafadhali pakia hati au subiri "
        "uchakataji ukamilike."
    )


def test_translate_answer_uses_fast_deterministic_path_for_record_refusal():
    service = MultilingualChatService(llm_service=_FailingLLM())

    answer = "I do not know from the available records."

    translated = asyncio.run(
        service.translate_answer_from_english(answer, target_language="sw")
    )

    assert translated == "Sijui kutoka kwenye rekodi zilizopo."


def test_translate_answer_uses_fast_deterministic_path_for_no_match_summary():
    service = MultilingualChatService(llm_service=_FailingLLM())

    answer = (
        "I couldn't find matching information in your records yet. "
        "There are no processed document chunks or matching structured records "
        "for this question right now."
    )

    translated = asyncio.run(
        service.translate_answer_from_english(answer, target_language="sw")
    )

    assert translated == (
        "Sijapata taarifa inayolingana kwenye rekodi zako bado. Kwa sasa hakuna "
        "vipande vya hati vilivyochakatwa au rekodi za muundo zinazolingana na "
        "swali hili."
    )


def test_translate_answer_uses_fast_deterministic_path_for_indexing_refusal():
    service = MultilingualChatService(llm_service=_FailingLLM())

    answer = (
        "I found records for you, but they are not indexed for search yet. "
        "There are 12 document chunks available, and indexing likely failed or has "
        "not finished yet. Reprocessing the documents should fix that."
    )

    translated = asyncio.run(
        service.translate_answer_from_english(answer, target_language="sw")
    )

    assert translated == (
        "Nimepata rekodi zako, lakini bado hazijawekewa faharasa kwa utafutaji. "
        "Kuna vipande 12 vya hati vinavyopatikana, na uwekaji faharasa huenda "
        "ulishindwa au bado haujakamilika. Kuchakata hati tena kunapaswa "
        "kurekebisha hilo."
    )


def test_translate_answer_uses_fast_deterministic_path_for_low_similarity_refusal():
    service = MultilingualChatService(llm_service=_FailingLLM())

    answer = (
        "I found a few possible matches, but none were close enough to answer "
        "confidently (top similarity 0.42). Try rephrasing with simpler words "
        "or ask for a summary of the related record."
    )

    translated = asyncio.run(
        service.translate_answer_from_english(answer, target_language="sw")
    )

    assert translated == (
        "Nimepata uwezekano kadhaa wa kulingana, lakini hakuna uliokuwa karibu "
        "vya kutosha kujibu kwa uhakika (ufanano wa juu 0.42). Jaribu kuuliza "
        "tena kwa maneno rahisi au uniombe muhtasari wa rekodi inayohusiana."
    )


def test_translate_answer_uses_fast_deterministic_path_for_document_explanation_refusal():
    service = MultilingualChatService(llm_service=_FailingLLM())

    answer = (
        "The document does not explain this topic. I can provide a general "
        "explanation if you'd like, but it won't be from your medical records."
    )

    translated = asyncio.run(
        service.translate_answer_from_english(answer, target_language="sw")
    )

    assert translated == (
        "Hati haielezi mada hii. Ninaweza kutoa maelezo ya jumla ukitaka, lakini "
        "hayatatokana na rekodi zako za matibabu."
    )
