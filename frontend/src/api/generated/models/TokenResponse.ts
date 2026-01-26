/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * Schema for authentication token response.
 */
export type TokenResponse = {
    /**
     * JWT access token
     */
    access_token: string;
    /**
     * JWT refresh token
     */
    refresh_token: string;
    /**
     * Token type
     */
    token_type?: string;
    /**
     * Access token expiry in seconds
     */
    expires_in: number;
    /**
     * User ID
     */
    user_id: number;
    /**
     * User email
     */
    email: string;
};

