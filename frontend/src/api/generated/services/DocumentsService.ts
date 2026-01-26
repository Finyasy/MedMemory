/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { BatchProcessResponse } from '../models/BatchProcessResponse';
import type { Body_upload_document_api_v1_documents_upload_post } from '../models/Body_upload_document_api_v1_documents_upload_post';
import type { DocumentDetail } from '../models/DocumentDetail';
import type { DocumentProcessRequest } from '../models/DocumentProcessRequest';
import type { DocumentProcessResponse } from '../models/DocumentProcessResponse';
import type { DocumentResponse } from '../models/DocumentResponse';
import type { OcrRefinementResponse } from '../models/OcrRefinementResponse';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class DocumentsService {
    /**
     * Upload Document
     * Upload a new document for a patient.
     *
     * Supported file types: PDF, PNG, JPEG, TIFF, DOCX, TXT
     * Maximum file size: 50MB
     * @param formData
     * @returns DocumentResponse Successful Response
     * @throws ApiError
     */
    public static uploadDocumentApiV1DocumentsUploadPost(
        formData: Body_upload_document_api_v1_documents_upload_post,
    ): CancelablePromise<DocumentResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/documents/upload',
            formData: formData,
            mediaType: 'multipart/form-data',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Process Document
     * Process a document: extract text and create memory chunks.
     *
     * This extracts text from the document using appropriate methods:
     * - PDFs: Direct text extraction + OCR for image pages
     * - Images: OCR
     * - DOCX: Text extraction
     *
     * Memory chunks are created for semantic search in later phases.
     * @param documentId
     * @param requestBody
     * @returns DocumentProcessResponse Successful Response
     * @throws ApiError
     */
    public static processDocumentApiV1DocumentsDocumentIdProcessPost(
        documentId: number,
        requestBody?: DocumentProcessRequest,
    ): CancelablePromise<DocumentProcessResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/documents/{document_id}/process',
            path: {
                'document_id': documentId,
            },
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Process Pending Documents
     * Process all pending documents.
     *
     * Useful for batch processing after uploading multiple documents.
     * @returns BatchProcessResponse Successful Response
     * @throws ApiError
     */
    public static processPendingDocumentsApiV1DocumentsProcessPendingPost(): CancelablePromise<BatchProcessResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/documents/process/pending',
        });
    }
    /**
     * Reprocess Document
     * Reprocess a document (delete existing chunks and extract again).
     * @param documentId
     * @returns DocumentProcessResponse Successful Response
     * @throws ApiError
     */
    public static reprocessDocumentApiV1DocumentsDocumentIdReprocessPost(
        documentId: number,
    ): CancelablePromise<DocumentProcessResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/documents/{document_id}/reprocess',
            path: {
                'document_id': documentId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * List Documents
     * List documents with optional filtering.
     * @param patientId
     * @param documentType
     * @param processedOnly
     * @param skip
     * @param limit
     * @returns DocumentResponse Successful Response
     * @throws ApiError
     */
    public static listDocumentsApiV1DocumentsGet(
        patientId?: (number | null),
        documentType?: (string | null),
        processedOnly: boolean = false,
        skip?: number,
        limit: number = 100,
    ): CancelablePromise<Array<DocumentResponse>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/documents/',
            query: {
                'patient_id': patientId,
                'document_type': documentType,
                'processed_only': processedOnly,
                'skip': skip,
                'limit': limit,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Get Document
     * Get document details including extracted text.
     * @param documentId
     * @returns DocumentDetail Successful Response
     * @throws ApiError
     */
    public static getDocumentApiV1DocumentsDocumentIdGet(
        documentId: number,
    ): CancelablePromise<DocumentDetail> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/documents/{document_id}',
            path: {
                'document_id': documentId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Delete Document
     * Delete a document and its associated file and memory chunks.
     * @param documentId
     * @returns void
     * @throws ApiError
     */
    public static deleteDocumentApiV1DocumentsDocumentIdDelete(
        documentId: number,
    ): CancelablePromise<void> {
        return __request(OpenAPI, {
            method: 'DELETE',
            url: '/api/v1/documents/{document_id}',
            path: {
                'document_id': documentId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Download Document
     * Download the original document file.
     * @param documentId
     * @returns any Successful Response
     * @throws ApiError
     */
    public static downloadDocumentApiV1DocumentsDocumentIdDownloadGet(
        documentId: number,
    ): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/documents/{document_id}/download',
            path: {
                'document_id': documentId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Get Document Text
     * Get just the extracted text from a document.
     * @param documentId
     * @returns any Successful Response
     * @throws ApiError
     */
    public static getDocumentTextApiV1DocumentsDocumentIdTextGet(
        documentId: number,
    ): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/documents/{document_id}/text',
            path: {
                'document_id': documentId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Get Document Ocr
     * Get OCR refinement output for a document.
     * @param documentId
     * @returns OcrRefinementResponse Successful Response
     * @throws ApiError
     */
    public static getDocumentOcrApiV1DocumentsDocumentIdOcrGet(
        documentId: number,
    ): CancelablePromise<OcrRefinementResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/documents/{document_id}/ocr',
            path: {
                'document_id': documentId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Get Patient Documents
     * Get all documents for a specific patient.
     * @param patientId
     * @param documentType
     * @param processedOnly
     * @returns DocumentResponse Successful Response
     * @throws ApiError
     */
    public static getPatientDocumentsApiV1DocumentsPatientPatientIdGet(
        patientId: number,
        documentType?: (string | null),
        processedOnly: boolean = false,
    ): CancelablePromise<Array<DocumentResponse>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/documents/patient/{patient_id}',
            path: {
                'patient_id': patientId,
            },
            query: {
                'document_type': documentType,
                'processed_only': processedOnly,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
}
