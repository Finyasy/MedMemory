"""Memory indexing service for storing embeddings in PostgreSQL.

Handles the creation, storage, and management of vector embeddings
in the memory_chunks table using pgvector.
"""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Document,
    Encounter,
    LabResult,
    Medication,
    MemoryChunk,
)
from app.services.documents.chunking import TextChunker
from app.services.embeddings.embedding import EmbeddingService


class MemoryIndexingService:
    """Service for indexing text into vector memory.

    Converts medical records and documents into searchable
    vector embeddings stored in PostgreSQL with pgvector.
    """

    def __init__(
        self,
        db: AsyncSession,
        embedding_service: EmbeddingService | None = None,
        chunker: TextChunker | None = None,
    ):
        """Initialize the indexing service.

        Args:
            db: Database session
            embedding_service: Service for generating embeddings
            chunker: Service for chunking text
        """
        self.db = db
        self.embedding_service = embedding_service or EmbeddingService.get_instance()
        self.chunker = chunker or TextChunker()

    async def index_text(
        self,
        patient_id: int,
        content: str,
        source_type: str,
        source_id: int | None = None,
        source_table: str | None = None,
        context_date: datetime | None = None,
        chunk_type: str | None = None,
        importance_score: float | None = None,
        metadata: dict | None = None,
    ) -> list[MemoryChunk]:
        """Index text content into vector memory.

        Args:
            patient_id: ID of the patient
            content: Text content to index
            source_type: Type of source (lab_result, medication, etc.)
            source_id: ID of the source record
            source_table: Table name of source record
            context_date: Date for temporal context
            chunk_type: Type of chunk (summary, detail, note)
            importance_score: Relevance score 0-1
            metadata: Additional metadata as JSON

        Returns:
            List of created MemoryChunk objects
        """
        if not content or not content.strip():
            return []

        # Chunk the text
        chunks = self.chunker.chunk_text(content, source_type=source_type)

        if not chunks:
            return []

        # Generate embeddings for all chunks
        chunk_texts = [c.content for c in chunks]
        embeddings = await self.embedding_service.embed_texts_async(chunk_texts)

        # Create memory chunks
        memory_chunks = []
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            memory_chunk = MemoryChunk(
                patient_id=patient_id,
                content=chunk.content,
                content_hash=chunk.content_hash,
                embedding=embedding,
                embedding_model=self.embedding_service.model_name,
                source_type=source_type,
                source_id=source_id,
                source_table=source_table,
                chunk_index=i,
                context_date=context_date,
                chunk_type=chunk_type,
                importance_score=importance_score,
                metadata_json=str(metadata) if metadata else None,
                is_indexed=True,
                indexed_at=datetime.now(UTC),
            )
            self.db.add(memory_chunk)
            memory_chunks.append(memory_chunk)

        await self.db.flush()
        return memory_chunks

    async def index_lab_result(self, lab_result: LabResult) -> list[MemoryChunk]:
        """Index a lab result into vector memory.

        Creates a natural language representation of the lab result
        and indexes it for semantic search.
        """
        # Build natural language representation
        text_parts = [f"Lab Result: {lab_result.test_name}"]

        if lab_result.value:
            text_parts.append(f"Value: {lab_result.value}")
            if lab_result.unit:
                text_parts[-1] += f" {lab_result.unit}"

        if lab_result.reference_range:
            text_parts.append(f"Reference Range: {lab_result.reference_range}")

        if lab_result.status:
            text_parts.append(f"Status: {lab_result.status}")

        if lab_result.is_abnormal:
            text_parts.append("⚠️ ABNORMAL RESULT")

        if lab_result.notes:
            text_parts.append(f"Notes: {lab_result.notes}")

        if lab_result.category:
            text_parts.append(f"Category: {lab_result.category}")

        content = "\n".join(text_parts)

        return await self.index_text(
            patient_id=lab_result.patient_id,
            content=content,
            source_type="lab_result",
            source_id=lab_result.id,
            source_table="lab_results",
            context_date=lab_result.collected_at or lab_result.resulted_at,
            chunk_type="medical_data",
            importance_score=0.8 if lab_result.is_abnormal else 0.5,
        )

    async def index_medication(self, medication: Medication) -> list[MemoryChunk]:
        """Index a medication into vector memory."""
        text_parts = [f"Medication: {medication.name}"]

        if medication.generic_name and medication.generic_name != medication.name:
            text_parts.append(f"Generic Name: {medication.generic_name}")

        if medication.dosage:
            text_parts.append(f"Dosage: {medication.dosage}")

        if medication.frequency:
            text_parts.append(f"Frequency: {medication.frequency}")

        if medication.route:
            text_parts.append(f"Route: {medication.route}")

        if medication.indication:
            text_parts.append(f"Indication: {medication.indication}")

        if medication.drug_class:
            text_parts.append(f"Drug Class: {medication.drug_class}")

        status = "Active" if medication.is_active else "Discontinued"
        text_parts.append(f"Status: {status}")

        if medication.instructions:
            text_parts.append(f"Instructions: {medication.instructions}")

        if medication.prescriber:
            text_parts.append(f"Prescriber: {medication.prescriber}")

        content = "\n".join(text_parts)

        return await self.index_text(
            patient_id=medication.patient_id,
            content=content,
            source_type="medication",
            source_id=medication.id,
            source_table="medications",
            context_date=medication.prescribed_at,
            chunk_type="medical_data",
            importance_score=0.7 if medication.is_active else 0.4,
        )

    async def index_encounter(self, encounter: Encounter) -> list[MemoryChunk]:
        """Index a medical encounter into vector memory."""
        text_parts = [
            f"Medical Visit: {encounter.encounter_type.replace('_', ' ').title()}",
            f"Date: {encounter.encounter_date.strftime('%Y-%m-%d')}",
        ]

        if encounter.provider_name:
            text_parts.append(f"Provider: {encounter.provider_name}")
            if encounter.provider_specialty:
                text_parts[-1] += f" ({encounter.provider_specialty})"

        if encounter.facility:
            text_parts.append(f"Facility: {encounter.facility}")

        if encounter.chief_complaint:
            text_parts.append(f"Chief Complaint: {encounter.chief_complaint}")

        if encounter.subjective:
            text_parts.append(f"Subjective: {encounter.subjective}")

        if encounter.objective:
            text_parts.append(f"Objective: {encounter.objective}")

        # Vitals
        vitals = []
        if encounter.vital_blood_pressure:
            vitals.append(f"BP: {encounter.vital_blood_pressure}")
        if encounter.vital_heart_rate:
            vitals.append(f"HR: {encounter.vital_heart_rate}")
        if encounter.vital_temperature:
            vitals.append(f"Temp: {encounter.vital_temperature}°F")
        if vitals:
            text_parts.append(f"Vitals: {', '.join(vitals)}")

        if encounter.assessment:
            text_parts.append(f"Assessment: {encounter.assessment}")

        if encounter.diagnoses:
            text_parts.append(f"Diagnoses: {encounter.diagnoses}")

        if encounter.plan:
            text_parts.append(f"Plan: {encounter.plan}")

        if encounter.clinical_notes:
            text_parts.append(f"Clinical Notes: {encounter.clinical_notes}")

        content = "\n".join(text_parts)

        return await self.index_text(
            patient_id=encounter.patient_id,
            content=content,
            source_type="encounter",
            source_id=encounter.id,
            source_table="encounters",
            context_date=encounter.encounter_date,
            chunk_type="clinical_note",
            importance_score=0.8,
        )

    async def index_document_chunks(
        self,
        document: Document,
    ) -> list[MemoryChunk]:
        """Index existing document chunks (add embeddings).

        This indexes chunks that were created during document processing
        but don't have embeddings yet.
        """
        # Get unindexed chunks for this document
        result = await self.db.execute(
            select(MemoryChunk).where(
                MemoryChunk.document_id == document.id,
                MemoryChunk.is_indexed.is_(False),
            )
        )
        chunks = list(result.scalars().all())

        if not chunks:
            return []

        # Generate embeddings
        chunk_texts = [c.content for c in chunks]
        embeddings = await self.embedding_service.embed_texts_async(chunk_texts)

        # Update chunks with embeddings
        for chunk, embedding in zip(chunks, embeddings):
            chunk.embedding = embedding
            chunk.embedding_model = self.embedding_service.model_name
            chunk.is_indexed = True
            chunk.indexed_at = datetime.now(UTC)

        await self.db.flush()
        return chunks

    async def index_all_for_patient(self, patient_id: int) -> dict:
        """Index all records for a patient.

        Returns:
            Statistics about indexing operation
        """
        stats = {
            "lab_results": 0,
            "medications": 0,
            "encounters": 0,
            "documents": 0,
            "total_chunks": 0,
        }

        # Index lab results
        result = await self.db.execute(
            select(LabResult).where(LabResult.patient_id == patient_id)
        )
        for lab in result.scalars().all():
            chunks = await self.index_lab_result(lab)
            stats["lab_results"] += 1
            stats["total_chunks"] += len(chunks)

        # Index medications
        result = await self.db.execute(
            select(Medication).where(Medication.patient_id == patient_id)
        )
        for med in result.scalars().all():
            chunks = await self.index_medication(med)
            stats["medications"] += 1
            stats["total_chunks"] += len(chunks)

        # Index encounters
        result = await self.db.execute(
            select(Encounter).where(Encounter.patient_id == patient_id)
        )
        for encounter in result.scalars().all():
            chunks = await self.index_encounter(encounter)
            stats["encounters"] += 1
            stats["total_chunks"] += len(chunks)

        # Index document chunks
        result = await self.db.execute(
            select(Document).where(
                Document.patient_id == patient_id,
                Document.is_processed,
            )
        )
        for doc in result.scalars().all():
            chunks = await self.index_document_chunks(doc)
            stats["documents"] += 1
            stats["total_chunks"] += len(chunks)

        return stats

    async def reindex_chunk(self, chunk_id: int) -> MemoryChunk:
        """Re-generate embedding for a specific chunk."""
        result = await self.db.execute(
            select(MemoryChunk).where(MemoryChunk.id == chunk_id)
        )
        chunk = result.scalar_one_or_none()

        if not chunk:
            raise ValueError(f"Chunk {chunk_id} not found")

        embedding = await self.embedding_service.embed_text_async(chunk.content)
        chunk.embedding = embedding
        chunk.embedding_model = self.embedding_service.model_name
        chunk.indexed_at = datetime.now(UTC)

        await self.db.flush()
        return chunk

    async def delete_patient_memory(self, patient_id: int) -> int:
        """Delete all memory chunks for a patient.

        Returns:
            Number of chunks deleted
        """
        from sqlalchemy import delete

        result = await self.db.execute(
            delete(MemoryChunk).where(MemoryChunk.patient_id == patient_id)
        )
        return result.rowcount
