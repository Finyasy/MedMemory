import { useCallback, useEffect, useState } from 'react';
import { ApiError, api } from '../api';
import type { DocumentItem } from '../types';
import type { OcrRefinementResponse } from '../api/generated';

type UseDocumentWorkspaceArgs = {
  patientId: number;
  documents: DocumentItem[];
  reloadDocuments: () => Promise<void> | void;
  uploadWithDuplicateCheck: (
    file: File,
    metadata?: { title?: string; category?: string; document_type?: string; description?: string },
  ) => Promise<{ kind: 'uploaded' | 'duplicate-same' | 'duplicate-other'; id: number }>;
  pushToast: (type: 'error' | 'info' | 'success', message: string) => void;
  handleError: (label: string, error: unknown) => void;
};

const getErrorStatus = (error: unknown): number | null => {
  if (error instanceof ApiError) return error.status;
  if (error && typeof error === 'object' && 'status' in error) {
    const status = (error as { status?: unknown }).status;
    if (typeof status === 'number') return status;
  }
  return null;
};

const useDocumentWorkspace = ({
  patientId,
  documents,
  reloadDocuments,
  uploadWithDuplicateCheck,
  pushToast,
  handleError,
}: UseDocumentWorkspaceArgs) => {
  const [processingIds, setProcessingIds] = useState<number[]>([]);
  const [deletingIds, setDeletingIds] = useState<number[]>([]);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [status, setStatus] = useState('');
  const [preview, setPreview] = useState<{
    id: number;
    title: string;
    text: string;
    description?: string | null;
    pageCount?: number | null;
    ocr?: OcrRefinementResponse | null;
  } | null>(null);
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null);

  // Reset preview on patient change
  useEffect(() => {
    setPreview(null);
    setDownloadUrl(null);
  }, [patientId]);

  const handleUpload = useCallback(async () => {
    if (!selectedFile) return;
    setStatus('Uploading document...');
    try {
      const result = await uploadWithDuplicateCheck(selectedFile, { title: selectedFile.name });
      if (result.kind === 'duplicate-same') {
        setSelectedFile(null);
        setStatus('Already uploaded. Using existing document.');
        pushToast('info', `Document already exists (ID ${result.id}). Using existing file.`);
        await reloadDocuments();
        return;
      }
      if (result.kind === 'duplicate-other') {
        handleError(
          'Duplicate document',
          new Error('This file already exists under a different family member. Duplicate uploads across profiles are blocked.'),
        );
        setStatus('Upload failed.');
        return;
      }
      setSelectedFile(null);
      setStatus('Upload complete.');
      pushToast('success', 'Document uploaded.');
      await reloadDocuments();
    } catch (error) {
      handleError('Failed to upload document', error);
      setStatus('Upload failed.');
    }
  }, [handleError, pushToast, reloadDocuments, selectedFile, uploadWithDuplicateCheck]);

  const handleProcess = useCallback(
    async (documentId: number) => {
      setProcessingIds((prev) => [...prev, documentId]);
      setStatus('Processing document...');
      try {
        await api.processDocument(documentId);
        setStatus('Processing complete.');
        pushToast('success', 'Document processed.');
        await reloadDocuments();
      } catch (error) {
        if (getErrorStatus(error) === 404) {
          pushToast('info', 'That document is no longer available. Refreshing your list.');
          await reloadDocuments();
          setStatus('Document list refreshed.');
          return;
        }
        handleError('Failed to process document', error);
        setStatus('Processing failed.');
      } finally {
        setProcessingIds((prev) => prev.filter((id) => id !== documentId));
      }
    },
    [handleError, pushToast, reloadDocuments],
  );

  const handleDelete = useCallback(
    async (documentId: number, label: string) => {
      if (typeof window === 'undefined') return;
      const confirmDelete = window.confirm(`Delete "${label}"? This cannot be undone.`);
      if (!confirmDelete) return;
      setDeletingIds((prev) => [...prev, documentId]);
      try {
        await api.deleteDocument(documentId);
        if (preview?.id === documentId) {
          setPreview(null);
          setDownloadUrl(null);
        }
        pushToast('success', 'Document deleted.');
        await reloadDocuments();
      } catch (error) {
        if (getErrorStatus(error) === 404) {
          if (preview?.id === documentId) {
            setPreview(null);
            setDownloadUrl(null);
          }
          pushToast('info', 'That document was already removed. Refreshing your list.');
          await reloadDocuments();
          return;
        }
        handleError('Failed to delete document', error);
      } finally {
        setDeletingIds((prev) => prev.filter((id) => id !== documentId));
      }
    },
    [handleError, pushToast, reloadDocuments, preview],
  );

  const handleView = useCallback(
    async (documentId: number) => {
      const doc = documents.find((item) => item.id === documentId);
      if (!doc) return;
      if (!doc.is_processed) {
        pushToast('info', 'Process the document to view extracted text.');
        return;
      }
      try {
        const [textResponse, ocrResponse] = await Promise.all([
          api.getDocumentText(documentId),
          api.getDocumentOcr(documentId).catch(() => null),
        ]);
        setPreview({
          id: documentId,
          title: doc.title || doc.original_filename,
          text: textResponse.extracted_text,
          description: doc.description,
          pageCount: textResponse.page_count,
          ocr: ocrResponse,
        });
        setDownloadUrl(`${window.location.origin}/api/v1/documents/${documentId}/download`);
        pushToast('success', 'Document loaded.');
      } catch (error) {
        if (getErrorStatus(error) === 404) {
          pushToast('info', 'That document is no longer available. Refreshing your list.');
          await reloadDocuments();
          return;
        }
        handleError('Failed to load document text', error);
      }
    },
    [documents, handleError, pushToast, reloadDocuments],
  );

  const handleClosePreview = useCallback(() => {
    setPreview(null);
    setDownloadUrl(null);
  }, []);

  return {
    processingIds,
    deletingIds,
    selectedFile,
    setSelectedFile,
    status,
    preview,
    downloadUrl,
    handleUpload,
    handleProcess,
    handleView,
    handleDelete,
    handleClosePreview,
  };
};

export default useDocumentWorkspace;
