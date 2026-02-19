"""Pydantic schemas for API request/response validation."""

from app.schemas.context import (
    ContextRequest,
    ContextResponse,
    QueryAnalysisResponse,
    QuickSearchRequest,
    QuickSearchResponse,
    SimpleContextRequest,
    SimpleContextResponse,
)
from app.schemas.dashboard import (
    AlertsEvaluateResponse,
    DashboardHighlightsResponse,
    DataConnectionResponse,
    DataConnectionUpsert,
    MetricAlertResponse,
    MetricDetailResponse,
    WatchMetricCreate,
    WatchMetricResponse,
    WatchMetricUpdate,
)
from app.schemas.document import (
    BatchProcessResponse,
    DocumentDetail,
    DocumentProcessRequest,
    DocumentProcessResponse,
    DocumentResponse,
    DocumentUpload,
    OcrRefinementResponse,
)
from app.schemas.ingestion import (
    BatchIngestionRequest,
    EncounterIngest,
    EncounterResponse,
    IngestionResultResponse,
    LabPanelIngest,
    LabResultIngest,
    LabResultResponse,
    MedicationIngest,
    MedicationResponse,
    VitalsIngest,
)
from app.schemas.insights import (
    InsightsLabItem,
    InsightsMedicationItem,
    PatientInsightsResponse,
)
from app.schemas.memory import (
    ContextRequest as MemoryContextRequest,
)
from app.schemas.memory import (
    ContextResponse as MemoryContextResponse,
)
from app.schemas.memory import (
    IndexingStatsResponse,
    IndexPatientRequest,
    IndexTextRequest,
    MemoryChunkResponse,
    MemoryStatsResponse,
    SearchRequest,
    SearchResponse,
    SearchResultItem,
    SimilarChunksRequest,
    SimilarChunksResponse,
)
from app.schemas.patient import (
    PatientBase,
    PatientCreate,
    PatientResponse,
    PatientSummary,
    PatientUpdate,
)
from app.schemas.records import (
    RecordBase,
    RecordCreate,
    RecordResponse,
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
    # Insights
    "InsightsLabItem",
    "InsightsMedicationItem",
    "PatientInsightsResponse",
    # Dashboard
    "DataConnectionUpsert",
    "DataConnectionResponse",
    "DashboardHighlightsResponse",
    "MetricDetailResponse",
    "WatchMetricCreate",
    "WatchMetricUpdate",
    "WatchMetricResponse",
    "MetricAlertResponse",
    "AlertsEvaluateResponse",
]
