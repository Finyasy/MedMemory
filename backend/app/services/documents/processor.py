"""Document processing pipeline.

Orchestrates the full document processing workflow:
1. Extract text from document
2. Chunk the text
3. Create memory chunks for embedding (Phase 4)
"""

from datetime import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Document, MemoryChunk
from app.services.documents.chunking import TextChunker
from app.services.documents.extraction import (
    ExtractionResult,
    get_extractor,
)
from app.services.documents.upload import DocumentUploadService


class DocumentProcessor:
    """Processes documents through the full extraction and chunking pipeline.
    
    This processor:
    1. Extracts text from documents (PDF, images, etc.)
    2. Chunks the text into semantic units
    3. Prepares chunks for embedding storage
    """
    
    def __init__(
        self,
        db: AsyncSession,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
    ):
        """Initialize the processor.
        
        Args:
            db: Database session
            chunk_size: Target size for text chunks
            chunk_overlap: Overlap between chunks
        """
        self.db = db
        self.upload_service = DocumentUploadService(db)
        self.chunker = TextChunker(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
    
    async def process_document(
        self,
        document_id: int,
        create_memory_chunks: bool = True,
    ) -> Document:
        """Process a document: extract text and create chunks.
        
        Args:
            document_id: ID of the document to process
            create_memory_chunks: Whether to create memory chunks for embedding
            
        Returns:
            Updated Document with extracted text
            
        Raises:
            ValueError: If document not found or processing fails
        """
        # Get document
        document = await self.upload_service.get_document(document_id)
        if not document:
            raise ValueError(f"Document {document_id} not found")
        
        # Update status to processing
        await self.upload_service.update_processing_status(
            document_id=document_id,
            status="processing",
        )
        
        try:
            # Extract text
            result = await self._extract_text(document)
            
            if result.is_empty:
                await self.upload_service.update_processing_status(
                    document_id=document_id,
                    status="completed",
                    extracted_text="[No text extracted]",
                    page_count=result.page_count,
                )
                return await self.upload_service.get_document(document_id)
            
            # Update document with extracted text
            document = await self.upload_service.update_processing_status(
                document_id=document_id,
                status="completed",
                extracted_text=result.text,
                page_count=result.page_count,
            )
            
            # Create memory chunks if requested
            if create_memory_chunks:
                await self._create_memory_chunks(document, result)
            
            return document
        
        except Exception as e:
            await self.upload_service.update_processing_status(
                document_id=document_id,
                status="failed",
                error=str(e),
            )
            raise
    
    async def _extract_text(self, document: Document) -> ExtractionResult:
        """Extract text from a document.
        
        Args:
            document: Document to extract text from
            
        Returns:
            ExtractionResult with text and metadata
        """
        extractor = get_extractor(document.mime_type or "application/octet-stream")
        
        if not extractor:
            raise ValueError(
                f"No extractor available for MIME type: {document.mime_type}"
            )
        
        return await extractor.extract(document.file_path)
    
    async def _create_memory_chunks(
        self,
        document: Document,
        extraction_result: ExtractionResult,
    ) -> list[MemoryChunk]:
        """Create memory chunks from extracted text.
        
        Args:
            document: Source document
            extraction_result: Extraction result with text
            
        Returns:
            List of created MemoryChunk objects
        """
        # Check if text has page markers
        if "--- Page" in extraction_result.text:
            chunks = self.chunker.chunk_by_pages(extraction_result.text)
        else:
            chunks = self.chunker.chunk_text(extraction_result.text)
        
        memory_chunks = []
        
        for chunk in chunks:
            memory_chunk = MemoryChunk(
                patient_id=document.patient_id,
                content=chunk.content,
                content_hash=chunk.content_hash,
                source_type="document",
                source_id=document.id,
                source_table="documents",
                document_id=document.id,
                page_number=chunk.page_number,
                chunk_index=chunk.chunk_index,
                context_date=document.document_date,
                chunk_type="document_text",
                is_indexed=False,
            )
            self.db.add(memory_chunk)
            memory_chunks.append(memory_chunk)
        
        await self.db.flush()
        return memory_chunks
    
    async def reprocess_document(self, document_id: int) -> Document:
        """Reprocess a document (e.g., after fixing issues).
        
        Args:
            document_id: ID of the document to reprocess
            
        Returns:
            Updated Document
        """
        # Delete existing memory chunks for this document
        from sqlalchemy import delete
        
        await self.db.execute(
            delete(MemoryChunk).where(MemoryChunk.document_id == document_id)
        )
        
        # Reset processing status
        document = await self.upload_service.get_document(document_id)
        if document:
            document.is_processed = False
            document.processing_status = "pending"
            document.extracted_text = None
            document.processing_error = None
            await self.db.flush()
        
        # Process again
        return await self.process_document(document_id)
    
    async def process_all_pending(self) -> dict:
        """Process all pending documents.
        
        Returns:
            Dictionary with processing statistics
        """
        from sqlalchemy import select
        
        # Get all pending documents
        result = await self.db.execute(
            select(Document).where(Document.processing_status == "pending")
        )
        documents = result.scalars().all()
        
        stats = {
            "total": len(documents),
            "processed": 0,
            "failed": 0,
            "errors": [],
        }
        
        for doc in documents:
            try:
                await self.process_document(doc.id)
                stats["processed"] += 1
            except Exception as e:
                stats["failed"] += 1
                stats["errors"].append(f"Document {doc.id}: {str(e)}")
        
        return stats
