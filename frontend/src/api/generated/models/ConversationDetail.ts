/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { MessageSchema } from './MessageSchema';
/**
 * Detailed conversation with messages.
 */
export type ConversationDetail = {
    conversation_id: string;
    patient_id: number;
    title: string;
    created_at: string;
    updated_at: string;
    message_count?: number;
    messages?: Array<MessageSchema>;
};

