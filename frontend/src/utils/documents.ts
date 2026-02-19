import { ApiError } from '../api';

export const getExistingDocumentId = (error: unknown) => {
  let message = '';
  if (error instanceof ApiError) {
    message = error.message;
  } else if (error && typeof error === 'object' && 'body' in error) {
    const body = (error as { body?: { detail?: string; error?: { message?: string } }; message?: string }).body;
    message = body?.detail || body?.error?.message || (error as { message?: string }).message || '';
  } else if (error instanceof Error) {
    message = error.message;
  }
  const match = /Document already exists with ID (\d+)/.exec(message);
  return match ? Number(match[1]) : null;
};
