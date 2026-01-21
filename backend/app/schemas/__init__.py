"""Pydantic schemas for API request/response validation."""

from app.schemas.patient import (
    PatientBase,
    PatientCreate,
    PatientUpdate,
    PatientResponse,
    PatientSummary,
)
from app.schemas.records import (
    RecordBase,
    RecordCreate,
    RecordResponse,
)
from app.schemas.ingestion import (
    LabResultIngest,
    LabResultResponse,
    LabPanelIngest,
    MedicationIngest,
    MedicationResponse,
    EncounterIngest,
    EncounterResponse,
    VitalsIngest,
    BatchIngestionRequest,
    IngestionResultResponse,
)
from app.schemas.document import (
    DocumentUpload,
    DocumentResponse,
    DocumentDetail,
    DocumentProcessRequest,
    DocumentProcessResponse,
    BatchProcessResponse,
    OcrRefinementResponse,
)
from app.schemas.memory import (
    SearchRequest,
    SearchResultItem,
    SearchResponse,
    IndexTextRequest,
    IndexPatientRequest,
    IndexingStatsResponse,
    MemoryChunkResponse,
    MemoryStatsResponse,
    ContextRequest as MemoryContextRequest,
    ContextResponse as MemoryContextResponse,
    SimilarChunksRequest,
    SimilarChunksResponse,
)
from app.schemas.context import (
    QueryAnalysisResponse,
    ContextRequest,
    ContextResponse,
    SimpleContextRequest,
    SimpleContextResponse,
    QuickSearchRequest,
    QuickSearchResponse,
)
from app.schemas.insights import (
    InsightsLabItem,
    InsightsMedicationItem,
    PatientInsightsResponse,
)

__all__ = [
    # Patient
    "PatientBase",
    "PatientCreate",
    "PatientUpdate",
    "PatientResponse",
    "PatientSummary",
    # Records (legacy)
    "RecordBase",
    "RecordCreate",
    "RecordResponse",
    # Ingestion - Labs
    "LabResultIngest",
    "LabResultResponse",
    "LabPanelIngest",
    # Ingestion - Medications
    "MedicationIngest",
    "MedicationResponse",
    # Ingestion - Encounters
    "EncounterIngest",
    "EncounterResponse",
    "VitalsIngest",
    # Ingestion - Batch
    "BatchIngestionRequest",
    "IngestionResultResponse",
    # Documents
    "DocumentUpload",
    "DocumentResponse",
    "DocumentDetail",
    "DocumentProcessRequest",
    "DocumentProcessResponse",
    "BatchProcessResponse",
    "OcrRefinementResponse",
    # Memory & Search
    "SearchRequest",
    "SearchResultItem",
    "SearchResponse",
    "IndexTextRequest",
    "IndexPatientRequest",
    "IndexingStatsResponse",
    "MemoryChunkResponse",
    "MemoryStatsResponse",
    "MemoryContextRequest",
    "MemoryContextResponse",
    "SimilarChunksRequest",
    "SimilarChunksResponse",
    # Context Engine
    "QueryAnalysisResponse",
    "ContextRequest",
    "ContextResponse",
    "SimpleContextRequest",
    "SimpleContextResponse",
    "QuickSearchRequest",
    "QuickSearchResponse",
]
