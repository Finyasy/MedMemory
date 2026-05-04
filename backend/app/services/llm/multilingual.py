"""Patient language helpers for English and Swahili chat support."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any

from app.services.llm.model import LLMService

logger = logging.getLogger("medmemory.multilingual")

SUPPORTED_CHAT_LANGUAGES = {
    "en": {"label": "English", "speech_locale": "en-US"},
    "sw": {"label": "Swahili", "speech_locale": "sw-KE"},
}

TRANSLATION_GLOSSARY: dict[str, tuple[str, ...]] = {
    "sw": (
        "steps -> hatua",
        "heart rate -> mapigo ya moyo",
        "sleep -> usingizi",
        "trend -> mwenendo",
        "out of range -> nje ya kiwango kinachotarajiwa",
        "not in records -> haipo kwenye rekodi",
        "source -> chanzo",
    ),
}

SWAHILI_TRANSLATION_MARKERS = {
    "na",
    "ya",
    "kwa",
    "kwenye",
    "katika",
    "hii",
    "hivi",
    "chanzo",
    "rekodi",
    "zako",
    "chini",
    "juu",
    "tarehe",
    "matokeo",
    "maabara",
    "ripoti",
    "thamani",
    "dawa",
    "inasema",
    "hazitaji",
    "moja",
    "kwa",
}

ENGLISH_TRANSLATION_MARKERS = {
    "the",
    "and",
    "from",
    "your",
    "records",
    "source",
    "date",
    "result",
    "results",
    "related",
    "note",
    "says",
    "low",
    "high",
    "positive",
    "negative",
}

FAST_SWAHILI_SUMMARY_MARKERS = (
    "from your records",
    "here's a quick apple health update",
    "i can see apple health is connected",
    "the records do not explicitly state this value",
    "the document does not record this information",
    "the document does not explain this topic",
    "i do not know from the available records",
    "i could not summarize the latest document",
    "i couldn't find matching information in your records yet",
    "i found records for you, but they are not indexed for search yet",
    "i found a few possible matches, but none were close enough to answer confidently",
    "i couldn't find a clear match for that in your indexed records",
    "not in documents.",
)

SWAHILI_PHRASE_REPLACEMENTS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(
            r"\bfrom your records,\s+the medication marked as discontinued is:\s*",
            re.IGNORECASE,
        ),
        "Kutoka kwenye rekodi zako, dawa iliyoandikwa kuwa imekatishwa ni: ",
    ),
    (
        re.compile(
            r"\bfrom your records,\s+your active medication is:\s*",
            re.IGNORECASE,
        ),
        "Kutoka kwenye rekodi zako, dawa yako inayotumika ni: ",
    ),
    (
        re.compile(
            r"\bfrom your records,\s+one listed medication is:\s*",
            re.IGNORECASE,
        ),
        "Kutoka kwenye rekodi zako, moja ya dawa zilizoandikwa ni: ",
    ),
    (
        re.compile(
            r"\bfrom your records,\s+discontinued medications include:\s*",
            re.IGNORECASE,
        ),
        "Kutoka kwenye rekodi zako, dawa zilizoandikwa kuwa zimekatishwa ni:\n",
    ),
    (
        re.compile(
            r"\bfrom your records,\s+your active medications are:\s*",
            re.IGNORECASE,
        ),
        "Kutoka kwenye rekodi zako, dawa zako zinazotumika ni:\n",
    ),
    (
        re.compile(
            r"\bfrom your records,\s+listed medications include:\s*",
            re.IGNORECASE,
        ),
        "Kutoka kwenye rekodi zako, dawa zilizoandikwa ni:\n",
    ),
    (
        re.compile(
            r"\bfrom your records,\s+there are not enough dated values to determine a trend\.?\s*",
            re.IGNORECASE,
        ),
        "Kutoka kwenye rekodi zako, hakuna thamani za tarehe za kutosha kubaini mwenendo. ",
    ),
    (
        re.compile(
            r"\bfrom your records,\s+please specify which test trend you want to review\.?\s*",
            re.IGNORECASE,
        ),
        "Kutoka kwenye rekodi zako, tafadhali eleza ni mwenendo wa kipimo kipi unataka kukagua. ",
    ),
    (
        re.compile(
            r"\bfrom your records,\s+there are not enough consistent values to determine a trend\.?\s*",
            re.IGNORECASE,
        ),
        "Kutoka kwenye rekodi zako, hakuna thamani thabiti za kutosha kubaini mwenendo. ",
    ),
    (
        re.compile(
            r"\bi couldn't find apple health step data that answers that yet\.?\s*",
            re.IGNORECASE,
        ),
        "Sijapata data ya hatua za Apple Health zinazojibu hilo bado. ",
    ),
    (
        re.compile(
            r"\bif you expected steps or activity here, try syncing apple health again and ask me about your last week of steps or recent activity trend\.?\s*",
            re.IGNORECASE,
        ),
        "Ikiwa ulitarajia kuona hatua au shughuli hapa, jaribu kusawazisha Apple Health tena kisha uniulize kuhusu hatua za wiki yako iliyopita au mwenendo wa shughuli zako za hivi karibuni. ",
    ),
    (
        re.compile(r"\bhere's a quick apple health update:\s*", re.IGNORECASE),
        "Hapa kuna muhtasari mfupi wa Apple Health: ",
    ),
    (
        re.compile(
            r"\bfrom\s+(?P<start>\d{4}-\d{2}-\d{2})\s+to\s+(?P<end>\d{4}-\d{2}-\d{2}),\s+you logged\s+(?P<steps>[0-9,]+)\s+steps\s+across\s+(?P<days>[0-9,]+)\s+day\(s\),\s+averaging about\s+(?P<avg>[0-9,]+)\s+steps a day\.?\s*",
            re.IGNORECASE,
        ),
        "kuanzia tarehe \\g<start> hadi \\g<end>, ulirekodi hatua \\g<steps> katika siku \\g<days>, ukiwa na wastani wa karibu hatua \\g<avg> kwa siku. ",
    ),
    (
        re.compile(r"\byour latest recorded day was\s*", re.IGNORECASE),
        "Siku yako ya hivi karibuni iliyorekodiwa ilikuwa ",
    ),
    (
        re.compile(
            r"\bwith\s+(?P<count>[0-9,]+)\s+steps\.?\s*",
            re.IGNORECASE,
        ),
        "ikiwa na hatua \\g<count>. ",
    ),
    (
        re.compile(
            r"\bapple health is connected, with\s*(?P<count>[0-9,]+)\s*synced day\(s\) overall\.?\s*",
            re.IGNORECASE,
        ),
        "Apple Health imeunganishwa, ikiwa na siku \\g<count> zilizolandanishwa kwa ujumla. ",
    ),
    (
        re.compile(
            r"\bi can see apple health is connected, but i do not have daily step totals for the period you asked about yet\.?\s*",
            re.IGNORECASE,
        ),
        "Naona Apple Health imeunganishwa, lakini bado sina jumla za hatua za kila siku kwa kipindi ulichoomba. ",
    ),
    (
        re.compile(
            r"\bthe last sync i can see was\s*",
            re.IGNORECASE,
        ),
        "Usawazishaji wa mwisho ninaoweza kuona ulikuwa ",
    ),
    (
        re.compile(
            r"\byour daily steps stayed about the same between\s+",
            re.IGNORECASE,
        ),
        "Hatua zako za kila siku zilibaki karibu sawa kati ya tarehe ",
    ),
    (
        re.compile(
            r"\bacross that span,\s+your daily steps\s+",
            re.IGNORECASE,
        ),
        "Katika kipindi hicho, hatua zako za kila siku ",
    ),
    (
        re.compile(
            r"\bthe document does not record this information\.?\s*",
            re.IGNORECASE,
        ),
        "Rekodi hazina taarifa hii. ",
    ),
    (
        re.compile(
            r"\bthe document does not explain this topic\.?\s*",
            re.IGNORECASE,
        ),
        "Hati haielezi mada hii. ",
    ),
    (
        re.compile(
            r"\bi can provide a general explanation if you'd like, but it won't be from your medical records\.?\s*",
            re.IGNORECASE,
        ),
        "Ninaweza kutoa maelezo ya jumla ukitaka, lakini hayatatokana na rekodi zako za matibabu. ",
    ),
    (
        re.compile(
            r"\bi do not know from the available records\.?\s*",
            re.IGNORECASE,
        ),
        "Sijui kutoka kwenye rekodi zilizopo. ",
    ),
    (
        re.compile(
            r"\bi could not summarize the latest document because no completed document text is available yet\.?\s*",
            re.IGNORECASE,
        ),
        "Sikuweza kufupisha hati ya hivi karibuni kwa sababu maandishi ya hati yaliyokamilika hayajapatikana bado. ",
    ),
    (
        re.compile(
            r"\bplease upload a document or wait for processing to finish\.?\s*",
            re.IGNORECASE,
        ),
        "Tafadhali pakia hati au subiri uchakataji ukamilike. ",
    ),
    (
        re.compile(
            r"\bi couldn't find matching information in your records yet\.?\s*",
            re.IGNORECASE,
        ),
        "Sijapata taarifa inayolingana kwenye rekodi zako bado. ",
    ),
    (
        re.compile(
            r"\bthere are no processed document chunks or matching structured records for this question right now\.?\s*",
            re.IGNORECASE,
        ),
        "Kwa sasa hakuna vipande vya hati vilivyochakatwa au rekodi za muundo zinazolingana na swali hili. ",
    ),
    (
        re.compile(
            r"\bi found records for you, but they are not indexed for search yet\.?\s*",
            re.IGNORECASE,
        ),
        "Nimepata rekodi zako, lakini bado hazijawekewa faharasa kwa utafutaji. ",
    ),
    (
        re.compile(
            r"\bthere are\s+(?P<count>[0-9,]+)\s+document chunks available, and indexing likely failed or has not finished yet\.?\s*",
            re.IGNORECASE,
        ),
        "Kuna vipande \\g<count> vya hati vinavyopatikana, na uwekaji faharasa huenda ulishindwa au bado haujakamilika. ",
    ),
    (
        re.compile(
            r"\breprocessing the documents should fix that\.?\s*",
            re.IGNORECASE,
        ),
        "Kuchakata hati tena kunapaswa kurekebisha hilo. ",
    ),
    (
        re.compile(
            r"\bi found a few possible matches, but none were close enough to answer confidently\s*\(top similarity\s+(?P<score>[0-9.]+)\)\.?\s*",
            re.IGNORECASE,
        ),
        "Nimepata uwezekano kadhaa wa kulingana, lakini hakuna uliokuwa karibu vya kutosha kujibu kwa uhakika (ufanano wa juu \\g<score>). ",
    ),
    (
        re.compile(
            r"\btry rephrasing with simpler words or ask for a summary of the related record\.?\s*",
            re.IGNORECASE,
        ),
        "Jaribu kuuliza tena kwa maneno rahisi au uniombe muhtasari wa rekodi inayohusiana. ",
    ),
    (
        re.compile(
            r"\bi couldn't find a clear match for that in your indexed records\s*\(about\s+(?P<count>[0-9,]+)\s+searchable chunks right now\)\.?\s*",
            re.IGNORECASE,
        ),
        "Sikuweza kupata ulinganifu wa wazi wa hilo kwenye rekodi zako zilizowekewa faharasa (takriban vipande \\g<count> vinavyoweza kutafutwa kwa sasa). ",
    ),
    (
        re.compile(
            r"\btry asking with different wording or ask me to summarize the related record\.?\s*",
            re.IGNORECASE,
        ),
        "Jaribu kuuliza kwa maneno tofauti au uniombe nifupishe rekodi inayohusiana. ",
    ),
    (
        re.compile(
            r"\bthe document does not record your pulse rate\.?\s*",
            re.IGNORECASE,
        ),
        "Hati hairekodi mapigo yako ya moyo. ",
    ),
    (
        re.compile(
            r"\bnot in documents\.\s*",
            re.IGNORECASE,
        ),
        "Haipo kwenye nyaraka. ",
    ),
    (
        re.compile(
            r"\bfrom your records,\s*",
            re.IGNORECASE,
        ),
        "Kutoka kwenye rekodi zako, ",
    ),
    (re.compile(r"\bfrom your records:\s*", re.IGNORECASE), "Kutoka kwenye rekodi zako: "),
    (
        re.compile(r"\bthe records do not explicitly state this value\.?\s*", re.IGNORECASE),
        "Rekodi hazitaji thamani hii moja kwa moja. ",
    ),
    (
        re.compile(r"\ba related note says:\s*", re.IGNORECASE),
        "Maelezo yanayohusiana yanasema: ",
    ),
    (
        re.compile(r"\brelated note says:\s*", re.IGNORECASE),
        "Maelezo yanayohusiana yanasema: ",
    ),
    (re.compile(r"\bdate:\s*", re.IGNORECASE), "Tarehe: "),
    (re.compile(r"\bscreening outcome:\s*", re.IGNORECASE), "Matokeo ya uchunguzi: "),
    (re.compile(r"\burinalysis:\s*", re.IGNORECASE), "Uchunguzi wa mkojo: "),
    (re.compile(r"\bnon-reactive\b", re.IGNORECASE), "Si reaktifu"),
    (re.compile(r"\bpositive\b", re.IGNORECASE), "Chanya"),
    (re.compile(r"\bnegative\b", re.IGNORECASE), "Hasi"),
    (re.compile(r"\bnot documented\b", re.IGNORECASE), "haijaandikwa"),
    (re.compile(r"\bsource:\s*", re.IGNORECASE), "chanzo: "),
)

SWAHILI_INLINE_REPLACEMENTS = {
    "(low)": "(chini)",
    "(high)": "(juu)",
    "(normal)": "(kawaida)",
}

SWAHILI_WORD_REPLACEMENTS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bactive\b", re.IGNORECASE), "inayotumika"),
    (re.compile(r"\bdiscontinued\b", re.IGNORECASE), "imekatishwa"),
    (re.compile(r"\binactive\b", re.IGNORECASE), "haitumiki"),
    (re.compile(r"\bstopped\b", re.IGNORECASE), "imesimamishwa"),
    (re.compile(r"\bincreased by\b", re.IGNORECASE), "iliongezeka kwa"),
    (re.compile(r"\bdecreased by\b", re.IGNORECASE), "ilipungua kwa"),
    (re.compile(r"\bstayed about the same\b", re.IGNORECASE), "ilibaki karibu sawa"),
    (re.compile(r"\bstayed the same\b", re.IGNORECASE), "ilibaki sawa"),
)

TRANSLATION_PROMPT_LEAK_MARKERS = (
    "<unused",
    "thoughtthe user wants me to translate",
    "the user wants me to translate",
    "text to translate is:",
    "let's break down the text",
    "translate this grounded patient medical answer",
    "translate this patient question for medical record retrieval",
    "translated text:",
)


@dataclass(frozen=True)
class MultilingualContext:
    input_language: str
    output_language: str
    detected_language: str
    translation_applied: bool
    speech_locale: str | None


class MultilingualChatService:
    """Translate patient chat questions/answers around the English RAG core."""

    def __init__(self, llm_service: LLMService | None = None):
        self.llm_service = llm_service or LLMService.get_instance()

    @staticmethod
    def normalize_language(value: str | None, fallback: str = "en") -> str:
        if not value:
            return fallback
        normalized = value.strip().lower().replace("_", "-")
        aliases = {
            "english": "en",
            "eng": "en",
            "en-us": "en",
            "en-gb": "en",
            "swahili": "sw",
            "swa": "sw",
            "sw-ke": "sw",
            "kiswahili": "sw",
        }
        normalized = aliases.get(normalized, normalized)
        return normalized if normalized in SUPPORTED_CHAT_LANGUAGES else fallback

    def resolve_context(
        self,
        *,
        input_language: str | None = None,
        output_language: str | None = None,
        preferred_language: str | None = None,
        clinician_mode: bool = False,
    ) -> MultilingualContext:
        if clinician_mode:
            return MultilingualContext(
                input_language="en",
                output_language="en",
                detected_language="en",
                translation_applied=False,
                speech_locale=SUPPORTED_CHAT_LANGUAGES["en"]["speech_locale"],
            )

        preferred = self.normalize_language(preferred_language, fallback="en")
        resolved_input = self.normalize_language(
            input_language or preferred_language,
            fallback=preferred,
        )
        resolved_output = self.normalize_language(
            output_language or preferred_language or resolved_input,
            fallback=resolved_input,
        )
        return MultilingualContext(
            input_language=resolved_input,
            output_language=resolved_output,
            detected_language=resolved_input,
            translation_applied=resolved_input != "en" or resolved_output != "en",
            speech_locale=SUPPORTED_CHAT_LANGUAGES[resolved_output]["speech_locale"],
        )

    async def translate_question_to_english(
        self,
        question: str,
        *,
        source_language: str,
    ) -> str:
        if source_language == "en":
            return question
        return await self._translate_text(
            text=question,
            source_language=source_language,
            target_language="en",
            content_type="patient question for medical record retrieval",
        )

    async def translate_answer_from_english(
        self,
        answer: str,
        *,
        target_language: str,
    ) -> str:
        if target_language == "en":
            return answer
        return await self._translate_text(
            text=answer,
            source_language="en",
            target_language=target_language,
            content_type="grounded patient medical answer",
        )

    async def translate_structured_payload(
        self,
        payload: dict[str, Any] | None,
        *,
        target_language: str,
    ) -> dict[str, Any] | None:
        if payload is None or target_language == "en":
            return payload

        serialized = json.dumps(payload, ensure_ascii=False)
        glossary_block = self._glossary_block(target_language)
        prompt = (
            "Translate ONLY the JSON string values below from English into "
            f"{self.language_label(target_language)}.\n"
            "Keep every JSON key exactly the same.\n"
            "Keep every number, date, unit, medication name, test name, null, boolean, and array structure unchanged.\n"
            "Return VALID JSON only with no markdown.\n"
            f"{glossary_block}"
            "JSON:\n"
            f"{serialized}\n\n"
            "Translated JSON:"
        )
        response = await self.llm_service.generate(
            prompt=prompt,
            system_prompt=(
                "You are a medical localization assistant. Return valid JSON only."
            ),
            max_new_tokens=min(1400, max(300, len(serialized) + 200)),
            temperature=0.0,
            do_sample=False,
        )
        translated = self._extract_json_object(response.text)
        if translated is None:
            logger.warning(
                "Structured translation failed for language=%s; using English payload",
                target_language,
            )
            return payload
        return translated

    @staticmethod
    def language_label(language_code: str) -> str:
        return SUPPORTED_CHAT_LANGUAGES.get(language_code, SUPPORTED_CHAT_LANGUAGES["en"])[
            "label"
        ]

    @staticmethod
    def split_for_streaming(text: str, max_chars: int = 180) -> list[str]:
        stripped = text.strip()
        if not stripped:
            return []
        segments = [
            segment.strip()
            for segment in re.split(r"(?<=[\.\!\?\n])\s+", stripped)
            if segment.strip()
        ]
        chunks: list[str] = []
        current = ""
        for segment in segments:
            candidate = f"{current} {segment}".strip() if current else segment
            if len(candidate) <= max_chars:
                current = candidate
                continue
            if current:
                chunks.append(current)
            if len(segment) <= max_chars:
                current = segment
                continue
            for index in range(0, len(segment), max_chars):
                part = segment[index : index + max_chars].strip()
                if part:
                    chunks.append(part)
            current = ""
        if current:
            chunks.append(current)
        return chunks

    async def _translate_text(
        self,
        *,
        text: str,
        source_language: str,
        target_language: str,
        content_type: str,
    ) -> str:
        if source_language == target_language or not text.strip():
            return text

        deterministic_translation = self._fallback_translate_text(
            text=text,
            source_language=source_language,
            target_language=target_language,
        )
        if self._should_use_fast_translation(
            text=text,
            content_type=content_type,
            source_language=source_language,
            target_language=target_language,
            deterministic_translation=deterministic_translation,
        ):
            return deterministic_translation or text

        glossary_block = self._glossary_block(target_language)
        prompt = (
            f"Translate this {content_type} from {self.language_label(source_language)} "
            f"to {self.language_label(target_language)}.\n"
            "Preserve every number, date, unit, medication name, lab name, source label, and refusal statement exactly.\n"
            "Preserve the original format and tone.\n"
            "Do not add headings, bullets, markdown, or extra line breaks if they were not in the source text.\n"
            "If a medical term is safer in English, keep it in English.\n"
            f"You must return the final answer primarily in {self.language_label(target_language)}.\n"
            "Return the translation only with no extra commentary.\n"
            f"{glossary_block}"
            "TEXT:\n"
            f"{text}\n\n"
            "TRANSLATION:"
        )
        try:
            response = await self.llm_service.generate(
                prompt=prompt,
                system_prompt=(
                    "You are a precise medical translator. Preserve clinical facts exactly."
                ),
                max_new_tokens=min(900, max(180, len(text) + 180)),
                temperature=0.0,
                do_sample=False,
            )
            translated = self._sanitize_translation_output(response.text)
            if self._should_prefer_deterministic_swahili_fallback(
                source_text=text,
                candidate_text=translated,
                target_language=target_language,
            ):
                fallback_translation = self._fallback_translate_text(
                    text=text,
                    source_language=source_language,
                    target_language=target_language,
                )
                if fallback_translation:
                    logger.warning(
                        "Using deterministic translation fallback due to formatting drift source=%s target=%s",
                        source_language,
                        target_language,
                    )
                    return fallback_translation
            if self._is_translation_acceptable(
                source_text=text,
                translated_text=translated,
                source_language=source_language,
                target_language=target_language,
            ):
                return translated

            retry_translation = await self._retry_translation(
                text=text,
                source_language=source_language,
                target_language=target_language,
                content_type=content_type,
                glossary_block=glossary_block,
            )
            if self._is_translation_acceptable(
                source_text=text,
                translated_text=retry_translation,
                source_language=source_language,
                target_language=target_language,
            ):
                return retry_translation

            fallback_translation = self._fallback_translate_text(
                text=text,
                source_language=source_language,
                target_language=target_language,
            )
            if fallback_translation:
                logger.warning(
                    "Using deterministic translation fallback source=%s target=%s",
                    source_language,
                    target_language,
                )
                return fallback_translation
            return translated or text
        except Exception:
            logger.exception(
                "Text translation failed source=%s target=%s", source_language, target_language
            )
            fallback_translation = self._fallback_translate_text(
                text=text,
                source_language=source_language,
                target_language=target_language,
            )
            return fallback_translation or text

    async def _retry_translation(
        self,
        *,
        text: str,
        source_language: str,
        target_language: str,
        content_type: str,
        glossary_block: str,
    ) -> str:
        prompt = (
            f"Translate this {content_type} from {self.language_label(source_language)} "
            f"to {self.language_label(target_language)}.\n"
            f"Do not leave the sentence in {self.language_label(source_language)}.\n"
            "Translate all connective language, qualifiers, and explanatory phrases.\n"
            "Preserve only medical entities, numbers, dates, units, medication names, lab names, and source IDs verbatim.\n"
            "Do not add markdown headings, bullet points, or extra structure that is not present in the source.\n"
            "Return only the translated text.\n"
            f"{glossary_block}"
            "TEXT:\n"
            f"{text}\n\n"
            "TRANSLATED TEXT:"
        )
        response = await self.llm_service.generate(
            prompt=prompt,
            system_prompt=(
                "You are a strict medical translator. Output must be in the target language."
            ),
            max_new_tokens=min(900, max(180, len(text) + 180)),
            temperature=0.0,
            do_sample=False,
        )
        return self._sanitize_translation_output(response.text)

    @staticmethod
    def _sanitize_translation_output(text: str) -> str:
        candidate = text.strip()
        if not candidate:
            return ""
        candidate = re.sub(r"^<unused\d+>\s*", "", candidate, flags=re.IGNORECASE).strip()
        candidate = re.sub(r"^thought\s*", "", candidate, flags=re.IGNORECASE).strip()
        for prefix in ("translation:", "translated text:", "translated answer:"):
            if candidate.lower().startswith(prefix):
                candidate = candidate[len(prefix) :].strip()
                break
        if "```" in candidate:
            parts = candidate.split("```")
            candidate = next(
                (part.strip() for part in parts if part.strip() and not part.strip().lower().startswith("json")),
                candidate,
            )
        return candidate.strip().strip('"').strip()

    @staticmethod
    def _should_prefer_deterministic_swahili_fallback(
        *,
        source_text: str,
        candidate_text: str,
        target_language: str,
    ) -> bool:
        if target_language != "sw":
            return False
        source = source_text.strip()
        candidate = candidate_text.strip()
        if not source or not candidate:
            return False
        if MultilingualChatService._looks_like_translation_prompt_leakage(
            candidate_text=candidate,
            source_text=source,
        ):
            return True
        if any(marker in source for marker in ("**", "\n*", "\n•")):
            return False
        if not any(marker in candidate for marker in ("**", "\n-", "\n*", "\n•")):
            return False
        return True

    def _is_translation_acceptable(
        self,
        *,
        source_text: str,
        translated_text: str,
        source_language: str,
        target_language: str,
    ) -> bool:
        if source_language == target_language:
            return True
        candidate = translated_text.strip()
        if not candidate:
            return False
        if self._looks_like_translation_prompt_leakage(
            candidate_text=candidate,
            source_text=source_text,
        ):
            return False
        if target_language != "sw":
            return candidate != source_text.strip()
        return not self._looks_untranslated_for_swahili(
            source_text=source_text,
            candidate_text=candidate,
        )

    @staticmethod
    def _looks_like_translation_prompt_leakage(
        *,
        candidate_text: str,
        source_text: str,
    ) -> bool:
        candidate_norm = MultilingualChatService._normalize_language_text(candidate_text)
        source_norm = MultilingualChatService._normalize_language_text(source_text)
        if not candidate_norm:
            return False
        if any(marker in candidate_norm for marker in TRANSLATION_PROMPT_LEAK_MARKERS):
            return True
        if source_norm and source_norm in candidate_norm and len(candidate_norm) > len(source_norm) * 2:
            return True
        return False

    def _looks_untranslated_for_swahili(
        self,
        *,
        source_text: str,
        candidate_text: str,
    ) -> bool:
        source_norm = self._normalize_language_text(source_text)
        candidate_norm = self._normalize_language_text(candidate_text)
        if not candidate_norm:
            return True
        if candidate_norm == source_norm:
            return True

        similarity = SequenceMatcher(None, source_norm, candidate_norm).ratio()
        tokens = set(candidate_norm.split())
        swahili_hits = len(tokens & SWAHILI_TRANSLATION_MARKERS)
        english_hits = len(tokens & ENGLISH_TRANSLATION_MARKERS)
        has_swahili_signal = swahili_hits > 0 or any(
            marker in candidate_norm
            for marker in ("kutoka kwenye", "chanzo:", "rekodi zako", "chini", "juu")
        )

        if has_swahili_signal:
            return False
        if similarity >= 0.88:
            return True
        return english_hits >= 2 and swahili_hits == 0

    @staticmethod
    def _normalize_language_text(text: str) -> str:
        return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9#:/\.\-\(\)\s]", " ", text.lower())).strip()

    @staticmethod
    def _looks_like_deterministic_swahili_summary_candidate(text: str) -> bool:
        normalized = MultilingualChatService._normalize_language_text(text)
        if not normalized:
            return False
        return any(marker in normalized for marker in FAST_SWAHILI_SUMMARY_MARKERS)

    @staticmethod
    def _should_use_fast_translation(
        *,
        text: str,
        content_type: str,
        source_language: str,
        target_language: str,
        deterministic_translation: str | None,
    ) -> bool:
        if source_language != "en" or target_language != "sw":
            return False
        if not deterministic_translation:
            return False
        normalized_content_type = content_type.lower()
        if "grounded patient medical answer" not in normalized_content_type:
            return False
        if any(marker in text for marker in ("**", "\n*", "\n•")):
            return False
        if len(text.strip()) <= 220:
            return True
        return MultilingualChatService._looks_like_deterministic_swahili_summary_candidate(
            text
        )

    def _fallback_translate_text(
        self,
        *,
        text: str,
        source_language: str,
        target_language: str,
    ) -> str | None:
        if source_language == "en" and target_language == "sw":
            return self._fallback_translate_english_to_swahili(text)
        return None

    def _fallback_translate_english_to_swahili(self, text: str) -> str | None:
        translated = self._apply_swahili_sentence_patterns(text)
        replacements_applied = int(translated != text)
        for pattern, replacement in SWAHILI_PHRASE_REPLACEMENTS:
            translated, count = pattern.subn(replacement, translated)
            replacements_applied += count
        for pattern, replacement in SWAHILI_WORD_REPLACEMENTS:
            translated, count = pattern.subn(replacement, translated)
            replacements_applied += count
        for english, swahili in SWAHILI_INLINE_REPLACEMENTS.items():
            if english in translated:
                translated = translated.replace(english, swahili)
                replacements_applied += 1
        translated = re.sub(r"\(\s*source:\s*", "(chanzo: ", translated, flags=re.IGNORECASE)
        translated = re.sub(r"\(\s*from your records:\s*", "(kutoka kwenye rekodi zako: ", translated, flags=re.IGNORECASE)
        translated = re.sub(r"\s{2,}", " ", translated).strip()
        if replacements_applied == 0 or translated == text:
            return None
        return translated

    def _apply_swahili_sentence_patterns(self, text: str) -> str:
        translated = re.sub(
            (
                r"From your records,\s+(?P<name>.+?)\s+changed from\s+"
                r"(?P<first>.+?)\s+on\s+(?P<first_date>\d{4}-\d{2}-\d{2})\s+to\s+"
                r"(?P<last>.+?)\s+on\s+(?P<last_date>\d{4}-\d{2}-\d{2})\s+\((?P<trend>.+?)\)\.?"
            ),
            self._translate_numeric_or_ratio_trend_match,
            text,
            flags=re.IGNORECASE,
        )
        translated = re.sub(
            (
                r"From your records,\s+(?P<name>.+?)\s+"
                r"(?P<trend>changed from\s+.+?|stayed the same)\s+between\s+"
                r"(?P<first_date>\d{4}-\d{2}-\d{2})\s+and\s+(?P<last_date>\d{4}-\d{2}-\d{2})\.?"
            ),
            self._translate_categorical_trend_match,
            translated,
            flags=re.IGNORECASE,
        )
        translated = re.sub(
            (
                r"Across that span,\s+your daily steps\s+"
                r"(?P<direction>increased|decreased)\s+by\s+"
                r"(?P<delta>[0-9,]+)\s+compared with\s+(?P<start>\d{4}-\d{2}-\d{2})\.?"
            ),
            self._translate_step_delta_match,
            translated,
            flags=re.IGNORECASE,
        )
        return translated

    def _translate_numeric_or_ratio_trend_match(self, match: re.Match[str]) -> str:
        trend_phrase = self._translate_trend_phrase(match.group("trend"))
        return (
            "Kutoka kwenye rekodi zako, "
            f"{match.group('name')} ilibadilika kutoka {match.group('first')} "
            f"tarehe {match.group('first_date')} hadi {match.group('last')} "
            f"tarehe {match.group('last_date')} ({trend_phrase})."
        )

    def _translate_categorical_trend_match(self, match: re.Match[str]) -> str:
        trend_phrase = self._translate_categorical_trend_phrase(match.group("trend"))
        return (
            "Kutoka kwenye rekodi zako, "
            f"{match.group('name')} {trend_phrase} kati ya tarehe "
            f"{match.group('first_date')} na {match.group('last_date')}."
        )

    @staticmethod
    def _translate_step_delta_match(match: re.Match[str]) -> str:
        direction = (
            "ziliongezeka kwa"
            if match.group("direction").lower() == "increased"
            else "zilipungua kwa"
        )
        return (
            "Katika kipindi hicho, hatua zako za kila siku "
            f"{direction} {match.group('delta')} ikilinganishwa na "
            f"{match.group('start')}."
        )

    def _translate_trend_phrase(self, phrase: str) -> str:
        translated = phrase.strip()
        for pattern, replacement in SWAHILI_WORD_REPLACEMENTS:
            translated = pattern.sub(replacement, translated)
        return translated

    def _translate_categorical_trend_phrase(self, phrase: str) -> str:
        normalized = phrase.strip()
        if re.fullmatch(r"stayed the same", normalized, flags=re.IGNORECASE):
            return "ilibaki sawa"
        changed_match = re.fullmatch(
            r"changed from\s+(?P<first>.+?)\s+to\s+(?P<last>.+)",
            normalized,
            flags=re.IGNORECASE,
        )
        if changed_match:
            return (
                f"ilibadilika kutoka {changed_match.group('first')} "
                f"hadi {changed_match.group('last')}"
            )
        return self._translate_trend_phrase(normalized)

    @staticmethod
    def _extract_json_object(text: str) -> dict[str, Any] | None:
        candidate = text.strip()
        if not candidate:
            return None
        if "```json" in candidate:
            candidate = candidate.split("```json", 1)[1].split("```", 1)[0].strip()
        elif "```" in candidate:
            candidate = candidate.split("```", 1)[1].split("```", 1)[0].strip()
        if not candidate.startswith("{"):
            start = candidate.find("{")
            end = candidate.rfind("}")
            if start == -1 or end <= start:
                return None
            candidate = candidate[start : end + 1]
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None

    @staticmethod
    def _glossary_block(language_code: str) -> str:
        glossary = TRANSLATION_GLOSSARY.get(language_code)
        if not glossary:
            return ""
        joined = "\n".join(f"- {entry}" for entry in glossary)
        return f"Preferred terminology:\n{joined}\n"
