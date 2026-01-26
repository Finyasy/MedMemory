/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { ForgotPasswordRequest } from '../models/ForgotPasswordRequest';
import type { RefreshTokenRequest } from '../models/RefreshTokenRequest';
import type { ResetPasswordRequest } from '../models/ResetPasswordRequest';
import type { TokenResponse } from '../models/TokenResponse';
import type { UserLogin } from '../models/UserLogin';
import type { UserResponse } from '../models/UserResponse';
import type { UserSignUp } from '../models/UserSignUp';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class AuthenticationService {
    /**
     * Signup
     * Create a new user account.
     * @param requestBody
     * @returns TokenResponse Successful Response
     * @throws ApiError
     */
    public static signupApiV1AuthSignupPost(
        requestBody: UserSignUp,
    ): CancelablePromise<TokenResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/auth/signup',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Login
     * Authenticate user and return access and refresh tokens.
     * @param requestBody
     * @returns TokenResponse Successful Response
     * @throws ApiError
     */
    public static loginApiV1AuthLoginPost(
        requestBody: UserLogin,
    ): CancelablePromise<TokenResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/auth/login',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Get Current User Info
     * Get current user information.
     * @returns UserResponse Successful Response
     * @throws ApiError
     */
    public static getCurrentUserInfoApiV1AuthMeGet(): CancelablePromise<UserResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/auth/me',
        });
    }
    /**
     * Refresh Access Token
     * Get new access token using refresh token.
     * @param requestBody
     * @returns TokenResponse Successful Response
     * @throws ApiError
     */
    public static refreshAccessTokenApiV1AuthRefreshPost(
        requestBody: RefreshTokenRequest,
    ): CancelablePromise<TokenResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/auth/refresh',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Logout
     * Logout and invalidate tokens.
     * @returns any Successful Response
     * @throws ApiError
     */
    public static logoutApiV1AuthLogoutPost(): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/auth/logout',
        });
    }
    /**
     * Forgot Password
     * Send a password reset email if the user exists.
     * @param requestBody
     * @returns any Successful Response
     * @throws ApiError
     */
    public static forgotPasswordApiV1AuthForgotPasswordPost(
        requestBody: ForgotPasswordRequest,
    ): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/auth/forgot-password',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Reset Password
     * Reset user password using a reset token.
     * @param requestBody
     * @returns any Successful Response
     * @throws ApiError
     */
    public static resetPasswordApiV1AuthResetPasswordPost(
        requestBody: ResetPasswordRequest,
    ): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/auth/reset-password',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
}
