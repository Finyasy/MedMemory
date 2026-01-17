"""Query analyzer for understanding user intent and extracting entities.

Analyzes natural language queries to determine:
- Query intent (question type)
- Medical entities (conditions, medications, tests, etc.)
- Temporal references (recent, last year, specific dates)
- Required data sources (labs, meds, encounters, documents)
"""

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional


class QueryIntent(str, Enum):
    """Types of query intents."""
    
    # Factual queries
    LIST = "list"  # "What medications is the patient on?"
    VALUE = "value"  # "What was the last A1C?"
    STATUS = "status"  # "Is the patient diabetic?"
    
    # Temporal queries
    HISTORY = "history"  # "History of cardiac conditions"
    TREND = "trend"  # "How has blood pressure changed?"
    RECENT = "recent"  # "Any recent lab results?"
    
    # Comparative queries
    COMPARE = "compare"  # "Compare current vs previous labs"
    CHANGE = "change"  # "What changed since last visit?"
    
    # Summary queries
    SUMMARY = "summary"  # "Summarize the patient's condition"
    OVERVIEW = "overview"  # "Give me an overview"
    
    # Specific queries
    DIAGNOSIS = "diagnosis"  # "What are the diagnoses?"
    TREATMENT = "treatment"  # "What treatments were recommended?"
    
    # Unknown/general
    GENERAL = "general"


class DataSource(str, Enum):
    """Types of data sources to search."""
    
    LAB_RESULT = "lab_result"
    MEDICATION = "medication"
    ENCOUNTER = "encounter"
    DOCUMENT = "document"
    ALL = "all"


@dataclass
class TemporalContext:
    """Temporal information extracted from query."""
    
    is_temporal: bool = False
    time_range: Optional[str] = None  # "recent", "last_year", "all_time"
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    relative_days: Optional[int] = None


@dataclass
class QueryAnalysis:
    """Result of query analysis."""
    
    original_query: str
    normalized_query: str
    intent: QueryIntent
    
    # Extracted entities
    medical_entities: list[str] = field(default_factory=list)
    medication_names: list[str] = field(default_factory=list)
    test_names: list[str] = field(default_factory=list)
    condition_names: list[str] = field(default_factory=list)
    
    # Temporal context
    temporal: TemporalContext = field(default_factory=TemporalContext)
    
    # Retrieval hints
    data_sources: list[DataSource] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    
    # Search parameters
    use_semantic_search: bool = True
    use_keyword_search: bool = False
    boost_recent: bool = False
    
    confidence: float = 0.5


class QueryAnalyzer:
    """Analyzes queries to extract intent and entities.
    
    Uses pattern matching and keyword detection to understand
    what the user is asking and how to best retrieve the answer.
    """
    
    # Intent patterns
    INTENT_PATTERNS = {
        QueryIntent.LIST: [
            r"\bwhat\b.*\b(medications?|meds|drugs?)\b",
            r"\blist\b",
            r"\bwhat are\b",
            r"\bshow\b.*\ball\b",
        ],
        QueryIntent.VALUE: [
            r"\bwhat (was|is|were)\b.*\b(level|value|result|reading)\b",
            r"\bwhat('s| is)\b.*\blast\b",
            r"\bhow (high|low|much)\b",
        ],
        QueryIntent.STATUS: [
            r"\bis (the patient|patient|he|she)\b.*\b(diabetic|hypertensive)\b",
            r"\bdoes (the patient|patient|he|she) have\b",
            r"\bhas (the patient|patient|he|she)\b",
        ],
        QueryIntent.HISTORY: [
            r"\bhistory\b",
            r"\bpast\b.*\b(medical|surgical|history)\b",
            r"\bprevious\b",
        ],
        QueryIntent.TREND: [
            r"\btrend\b",
            r"\bhow has\b.*\bchanged\b",
            r"\bover time\b",
            r"\bprogression\b",
        ],
        QueryIntent.RECENT: [
            r"\brecent\b",
            r"\blatest\b",
            r"\blast (few|couple|several)?\s*(days?|weeks?|months?)\b",
            r"\btoday\b",
            r"\bthis (week|month)\b",
        ],
        QueryIntent.COMPARE: [
            r"\bcompare\b",
            r"\bvs\.?\b",
            r"\bversus\b",
            r"\bdifference between\b",
        ],
        QueryIntent.CHANGE: [
            r"\bwhat (has )?changed\b",
            r"\bnew\b.*\bsince\b",
            r"\bupdates?\b",
        ],
        QueryIntent.SUMMARY: [
            r"\bsummar(y|ize)\b",
            r"\bbrief\b",
            r"\bquick overview\b",
        ],
        QueryIntent.OVERVIEW: [
            r"\boverview\b",
            r"\btell me about\b",
            r"\bwhat do (we|you) know\b",
        ],
        QueryIntent.DIAGNOSIS: [
            r"\bdiagnos(is|es|ed)\b",
            r"\bconditions?\b",
            r"\bproblems?\b",
        ],
        QueryIntent.TREATMENT: [
            r"\btreatment\b",
            r"\btherapy\b",
            r"\bplan\b",
            r"\brecommendations?\b",
        ],
    }
    
    # Data source keywords
    SOURCE_KEYWORDS = {
        DataSource.LAB_RESULT: [
            "lab", "labs", "laboratory", "test", "tests", "result", "results",
            "blood", "urine", "a1c", "hemoglobin", "glucose", "cholesterol",
            "creatinine", "bun", "cbc", "cmp", "bmp", "lipid", "panel",
            "potassium", "sodium", "calcium", "vitamin", "tsh", "t4",
        ],
        DataSource.MEDICATION: [
            "medication", "medications", "med", "meds", "drug", "drugs",
            "prescription", "prescriptions", "rx", "taking", "prescribed",
            "dosage", "dose", "pill", "pills", "tablet", "tablets",
        ],
        DataSource.ENCOUNTER: [
            "visit", "visits", "appointment", "appointments", "encounter",
            "encounters", "consultation", "exam", "examination", "checkup",
            "follow-up", "followup", "hospital", "hospitalization", "admission",
            "emergency", "er", "clinic", "office", "provider", "doctor",
        ],
        DataSource.DOCUMENT: [
            "document", "documents", "report", "reports", "note", "notes",
            "pdf", "image", "scan", "record", "records", "file", "files",
            "discharge", "summary", "letter", "referral",
        ],
    }
    
    # Temporal keywords
    TEMPORAL_PATTERNS = {
        "recent": (r"\brecent(ly)?\b|\blast\s*(few|couple)?\s*(days?|weeks?)\b", 14),
        "last_month": (r"\blast month\b|\bpast month\b", 30),
        "last_3_months": (r"\blast (3|three) months?\b|\bpast (3|three) months?\b", 90),
        "last_6_months": (r"\blast (6|six) months?\b|\bpast (6|six) months?\b", 180),
        "last_year": (r"\blast year\b|\bpast year\b|\bthis year\b", 365),
        "today": (r"\btoday\b", 1),
        "this_week": (r"\bthis week\b", 7),
    }
    
    # Common medical terms for entity extraction
    MEDICAL_TERMS = {
        "conditions": [
            "diabetes", "hypertension", "copd", "asthma", "heart failure",
            "chf", "cad", "coronary artery disease", "stroke", "tia",
            "ckd", "kidney disease", "liver disease", "cancer", "obesity",
            "depression", "anxiety", "arthritis", "osteoporosis",
        ],
        "tests": [
            "a1c", "hba1c", "glucose", "blood sugar", "cholesterol", "ldl",
            "hdl", "triglycerides", "creatinine", "egfr", "bun", "cbc",
            "hemoglobin", "hematocrit", "platelets", "wbc", "potassium",
            "sodium", "calcium", "magnesium", "vitamin d", "b12", "tsh",
            "t4", "psa", "inr", "ptt", "alt", "ast", "bilirubin", "albumin",
            "ekg", "ecg", "echo", "mri", "ct", "x-ray", "xray", "ultrasound",
        ],
    }
    
    def __init__(self):
        """Initialize the query analyzer."""
        # Compile regex patterns
        self._intent_patterns = {
            intent: [re.compile(p, re.IGNORECASE) for p in patterns]
            for intent, patterns in self.INTENT_PATTERNS.items()
        }
        
        self._temporal_patterns = {
            name: (re.compile(pattern, re.IGNORECASE), days)
            for name, (pattern, days) in self.TEMPORAL_PATTERNS.items()
        }
    
    def analyze(self, query: str) -> QueryAnalysis:
        """Analyze a query and extract intent, entities, and context.
        
        Args:
            query: Natural language query
            
        Returns:
            QueryAnalysis with extracted information
        """
        # Normalize query
        normalized = self._normalize_query(query)
        
        # Extract intent
        intent, intent_confidence = self._extract_intent(normalized)
        
        # Extract temporal context
        temporal = self._extract_temporal(normalized)
        
        # Extract data sources
        sources = self._extract_sources(normalized)
        
        # Extract medical entities
        entities = self._extract_entities(normalized)
        
        # Extract keywords for keyword search
        keywords = self._extract_keywords(normalized)
        
        # Determine search strategy
        use_semantic = True
        use_keyword = len(keywords) > 0 or len(entities["tests"]) > 0
        boost_recent = temporal.is_temporal and temporal.relative_days is not None
        
        return QueryAnalysis(
            original_query=query,
            normalized_query=normalized,
            intent=intent,
            medical_entities=entities["all"],
            medication_names=entities["medications"],
            test_names=entities["tests"],
            condition_names=entities["conditions"],
            temporal=temporal,
            data_sources=sources if sources else [DataSource.ALL],
            keywords=keywords,
            use_semantic_search=use_semantic,
            use_keyword_search=use_keyword,
            boost_recent=boost_recent,
            confidence=intent_confidence,
        )
    
    def _normalize_query(self, query: str) -> str:
        """Normalize query text."""
        # Lowercase
        query = query.lower()
        
        # Remove extra whitespace
        query = " ".join(query.split())
        
        # Remove punctuation at end
        query = query.rstrip("?!.")
        
        return query
    
    def _extract_intent(self, query: str) -> tuple[QueryIntent, float]:
        """Extract query intent."""
        for intent, patterns in self._intent_patterns.items():
            for pattern in patterns:
                if pattern.search(query):
                    return intent, 0.8
        
        return QueryIntent.GENERAL, 0.5
    
    def _extract_temporal(self, query: str) -> TemporalContext:
        """Extract temporal context from query."""
        for name, (pattern, days) in self._temporal_patterns.items():
            if pattern.search(query):
                return TemporalContext(
                    is_temporal=True,
                    time_range=name,
                    date_from=datetime.now(timezone.utc) - timedelta(days=days),
                    date_to=datetime.now(timezone.utc),
                    relative_days=days,
                )
        
        return TemporalContext(is_temporal=False)
    
    def _extract_sources(self, query: str) -> list[DataSource]:
        """Determine which data sources to search."""
        sources = []
        
        for source, keywords in self.SOURCE_KEYWORDS.items():
            for keyword in keywords:
                if keyword in query:
                    if source not in sources:
                        sources.append(source)
                    break
        
        return sources
    
    def _extract_entities(self, query: str) -> dict:
        """Extract medical entities from query."""
        entities = {
            "conditions": [],
            "tests": [],
            "medications": [],
            "all": [],
        }
        
        # Extract conditions
        for condition in self.MEDICAL_TERMS["conditions"]:
            if condition in query:
                entities["conditions"].append(condition)
                entities["all"].append(condition)
        
        # Extract tests
        for test in self.MEDICAL_TERMS["tests"]:
            if test in query:
                entities["tests"].append(test)
                entities["all"].append(test)
        
        return entities
    
    def _extract_keywords(self, query: str) -> list[str]:
        """Extract important keywords for keyword search."""
        # Remove common words
        stopwords = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "being", "have", "has", "had", "do", "does", "did", "will",
            "would", "could", "should", "may", "might", "must", "shall",
            "can", "need", "dare", "ought", "used", "to", "of", "in",
            "for", "on", "with", "at", "by", "from", "as", "into",
            "through", "during", "before", "after", "above", "below",
            "between", "under", "again", "further", "then", "once",
            "what", "which", "who", "whom", "this", "that", "these",
            "those", "am", "and", "but", "if", "or", "because", "until",
            "while", "any", "all", "both", "each", "few", "more", "most",
            "other", "some", "such", "no", "nor", "not", "only", "own",
            "same", "so", "than", "too", "very", "just", "also", "now",
            "patient", "patients", "me", "tell", "show", "give", "get",
        }
        
        words = query.split()
        keywords = [w for w in words if w not in stopwords and len(w) > 2]
        
        return keywords
