/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * Request to reset password.
 */
export type ResetPasswordRequest = {
    /**
     * Password reset token
     */
    token: string;
    /**
     * New password
     */
    new_password: string;
};

