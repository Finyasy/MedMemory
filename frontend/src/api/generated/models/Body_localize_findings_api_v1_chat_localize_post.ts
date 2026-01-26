/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type Body_localize_findings_api_v1_chat_localize_post = {
    prompt: string;
    patient_id: number;
    image?: (Blob | null);
    slices?: (Array<Blob> | null);
    patches?: (Array<Blob> | null);
    sample_count?: number;
    tile_size?: number;
    modality?: string;
};

