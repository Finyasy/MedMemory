/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { Body_ask_with_image_api_v1_chat_vision_post } from '../models/Body_ask_with_image_api_v1_chat_vision_post';
import type { Body_ask_with_volume_api_v1_chat_volume_post } from '../models/Body_ask_with_volume_api_v1_chat_volume_post';
import type { Body_ask_with_wsi_api_v1_chat_wsi_post } from '../models/Body_ask_with_wsi_api_v1_chat_wsi_post';
import type { Body_compare_cxr_api_v1_chat_cxr_compare_post } from '../models/Body_compare_cxr_api_v1_chat_cxr_compare_post';
import type { Body_localize_findings_api_v1_chat_localize_post } from '../models/Body_localize_findings_api_v1_chat_localize_post';
import type { ChatRequest } from '../models/ChatRequest';
import type { ChatResponse } from '../models/ChatResponse';
import type { ConversationCreate } from '../models/ConversationCreate';
import type { ConversationDetail } from '../models/ConversationDetail';
import type { ConversationResponse } from '../models/ConversationResponse';
import type { CxrCompareResponse } from '../models/CxrCompareResponse';
import type { LLMInfoResponse } from '../models/LLMInfoResponse';
import type { LocalizationResponse } from '../models/LocalizationResponse';
import type { VisionChatResponse } from '../models/VisionChatResponse';
import type { VolumeChatResponse } from '../models/VolumeChatResponse';
import type { WsiChatResponse } from '../models/WsiChatResponse';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class ChatService {
    /**
     * Get Llm Info
     * Get information about the loaded LLM model.
     * @returns LLMInfoResponse Successful Response
     * @throws ApiError
     */
    public static getLlmInfoApiV1ChatLlmInfoGet(): CancelablePromise<LLMInfoResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/chat/llm/info',
        });
    }
    /**
     * Ask Question
     * Ask a question about a patient using RAG.
     *
     * This endpoint:
     * 1. Retrieves relevant context from patient records
     * 2. Generates an answer using MedGemma-4B-IT
     * 3. Stores the conversation for history
     *
     * Example questions:
     * - "What medications is the patient currently taking?"
     * - "Show me any abnormal lab results from the past year"
     * - "What is the patient's diagnosis history?"
     * @param requestBody
     * @returns ChatResponse Successful Response
     * @throws ApiError
     */
    public static askQuestionApiV1ChatAskPost(
        requestBody: ChatRequest,
    ): CancelablePromise<ChatResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/chat/ask',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Stream Ask
     * Stream answer generation token by token.
     *
     * Useful for real-time chat interfaces where you want to show
     * the answer as it's being generated.
     * @param question
     * @param patientId
     * @param conversationId
     * @returns any Successful Response
     * @throws ApiError
     */
    public static streamAskApiV1ChatStreamPost(
        question: string,
        patientId: number,
        conversationId?: (string | null),
    ): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/chat/stream',
            query: {
                'question': question,
                'patient_id': patientId,
                'conversation_id': conversationId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Ask With Image
     * Analyze a medical image using the vision-language model.
     * @param formData
     * @returns VisionChatResponse Successful Response
     * @throws ApiError
     */
    public static askWithImageApiV1ChatVisionPost(
        formData: Body_ask_with_image_api_v1_chat_vision_post,
    ): CancelablePromise<VisionChatResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/chat/vision',
            formData: formData,
            mediaType: 'multipart/form-data',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Ask With Volume
     * Analyze a CT/MRI volume provided as a stack of 2D slices.
     * @param formData
     * @returns VolumeChatResponse Successful Response
     * @throws ApiError
     */
    public static askWithVolumeApiV1ChatVolumePost(
        formData: Body_ask_with_volume_api_v1_chat_volume_post,
    ): CancelablePromise<VolumeChatResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/chat/volume',
            formData: formData,
            mediaType: 'multipart/form-data',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Ask With Wsi
     * Analyze WSI patches provided as multiple images or a zip.
     * @param formData
     * @returns WsiChatResponse Successful Response
     * @throws ApiError
     */
    public static askWithWsiApiV1ChatWsiPost(
        formData: Body_ask_with_wsi_api_v1_chat_wsi_post,
    ): CancelablePromise<WsiChatResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/chat/wsi',
            formData: formData,
            mediaType: 'multipart/form-data',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Compare Cxr
     * Compare a current and prior chest X-ray.
     * @param formData
     * @returns CxrCompareResponse Successful Response
     * @throws ApiError
     */
    public static compareCxrApiV1ChatCxrComparePost(
        formData: Body_compare_cxr_api_v1_chat_cxr_compare_post,
    ): CancelablePromise<CxrCompareResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/chat/cxr/compare',
            formData: formData,
            mediaType: 'multipart/form-data',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Localize Findings
     * Localize findings with bounding boxes for multiple modalities.
     * @param formData
     * @returns LocalizationResponse Successful Response
     * @throws ApiError
     */
    public static localizeFindingsApiV1ChatLocalizePost(
        formData: Body_localize_findings_api_v1_chat_localize_post,
    ): CancelablePromise<LocalizationResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/chat/localize',
            formData: formData,
            mediaType: 'multipart/form-data',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Create Conversation
     * Create a new conversation.
     * @param requestBody
     * @returns ConversationResponse Successful Response
     * @throws ApiError
     */
    public static createConversationApiV1ChatConversationsPost(
        requestBody: ConversationCreate,
    ): CancelablePromise<ConversationResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/chat/conversations',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * List Conversations
     * List conversations for a patient.
     * @param patientId
     * @param limit
     * @returns ConversationResponse Successful Response
     * @throws ApiError
     */
    public static listConversationsApiV1ChatConversationsGet(
        patientId: number,
        limit: number = 20,
    ): CancelablePromise<Array<ConversationResponse>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/chat/conversations',
            query: {
                'patient_id': patientId,
                'limit': limit,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Get Conversation
     * Get a conversation with all messages.
     * @param conversationId
     * @returns ConversationDetail Successful Response
     * @throws ApiError
     */
    public static getConversationApiV1ChatConversationsConversationIdGet(
        conversationId: string,
    ): CancelablePromise<ConversationDetail> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/chat/conversations/{conversation_id}',
            path: {
                'conversation_id': conversationId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Delete Conversation
     * Delete a conversation and all its messages.
     * @param conversationId
     * @returns void
     * @throws ApiError
     */
    public static deleteConversationApiV1ChatConversationsConversationIdDelete(
        conversationId: string,
    ): CancelablePromise<void> {
        return __request(OpenAPI, {
            method: 'DELETE',
            url: '/api/v1/chat/conversations/{conversation_id}',
            path: {
                'conversation_id': conversationId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Update Conversation Title
     * Update conversation title.
     * @param conversationId
     * @param title
     * @returns any Successful Response
     * @throws ApiError
     */
    public static updateConversationTitleApiV1ChatConversationsConversationIdTitlePatch(
        conversationId: string,
        title: string,
    ): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'PATCH',
            url: '/api/v1/chat/conversations/{conversation_id}/title',
            path: {
                'conversation_id': conversationId,
            },
            query: {
                'title': title,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
}
