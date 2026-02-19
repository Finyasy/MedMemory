import { useCallback, useState } from 'react';
import { api, ApiError } from '../api';
import { getChatUploadKind, isCxrFilename } from '../utils/uploadRouting';
import type { ChatMessage } from '../types';

type UseChatUploadsArgs = {
  patientId: number;
  question: string;
  setQuestion: (value: string) => void;
  reloadDocuments: () => Promise<void> | void;
  uploadWithDuplicateCheck: (
    file: File,
    metadata?: { title?: string; category?: string; document_type?: string; description?: string },
  ) => Promise<{ kind: 'uploaded' | 'duplicate-same' | 'duplicate-other'; id: number }>;
  pushToast: (type: 'error' | 'info' | 'success', message: string) => void;
  handleError: (label: string, error: unknown) => void;
  sendVision: (file: File, promptOverride?: string) => Promise<void>;
  sendVolume: (file: File, promptOverride?: string) => Promise<void>;
  sendWsi: (file: File, promptOverride?: string) => Promise<void>;
  pushMessage: (message: ChatMessage) => void;
};

const useChatUploads = ({
  patientId,
  question,
  setQuestion,
  reloadDocuments,
  uploadWithDuplicateCheck,
  pushToast,
  handleError,
  sendVision,
  sendVolume,
  sendWsi,
  pushMessage,
}: UseChatUploadsArgs) => {
  const [chatUploadStatus, setChatUploadStatus] = useState('');
  const [isChatUploading, setIsChatUploading] = useState(false);
  const [localizationPreview, setLocalizationPreview] = useState<{
    imageUrl: string;
    boxes: {
      label: string;
      confidence: number;
      x_min: number;
      y_min: number;
      x_max: number;
      y_max: number;
      x_min_norm: number;
      y_min_norm: number;
      x_max_norm: number;
      y_max_norm: number;
    }[];
  } | null>(null);

  const getLatestCxrNote = (description?: string | null): string | null => {
    if (!description) return null;
    const notes = description
      .split('\n')
      .map((line) => line.trim())
      .filter((line) => line.startsWith('Auto CXR comparison'));
    if (!notes.length) return null;
    return notes[notes.length - 1];
  };

  const handleSingleChatUpload = useCallback(
    async (single: File) => {
      const uploadKind = getChatUploadKind(single);
      if (!patientId) {
        pushToast('info', 'Select a patient before uploading a report.');
        return;
      }
      if (uploadKind === 'dicom') {
        pushToast('info', 'Please upload DICOM series as a .zip file.');
        return;
      }
      if (uploadKind === 'wsi') {
        setIsChatUploading(true);
        setChatUploadStatus('Analyzing WSI patches...');
        try {
          await sendWsi(single, question);
          setChatUploadStatus('WSI analysis complete.');
        } catch {
          setChatUploadStatus('WSI analysis failed.');
        } finally {
          setIsChatUploading(false);
        }
        return;
      }
      if (uploadKind === 'volume') {
        setIsChatUploading(true);
        setChatUploadStatus('Analyzing volume...');
        try {
          await sendVolume(single, question);
          setChatUploadStatus('Volume analysis complete.');
        } catch {
          setChatUploadStatus('Volume analysis failed.');
        } finally {
          setIsChatUploading(false);
        }
        return;
      }
      if (uploadKind === 'image') {
        if (isCxrFilename(single.name)) {
          setIsChatUploading(true);
          setChatUploadStatus('Uploading chest X-ray...');
          try {
            const result = await uploadWithDuplicateCheck(single, { title: single.name });
            if (result.kind === 'duplicate-other') {
              handleError(
                'Duplicate document',
                new Error('This file already exists under a different family member. Duplicate uploads across profiles are blocked.'),
              );
              setChatUploadStatus('Upload failed.');
              return;
            }
            setChatUploadStatus('Generating CXR comparison...');
            await api.processDocument(result.id);
            const updatedDocument = await api.getDocument(result.id);
            const latestCxrNote = getLatestCxrNote(updatedDocument.description);
            if (latestCxrNote?.startsWith('Auto CXR comparison (baseline')) {
              setChatUploadStatus('CXR comparison complete.');
              pushToast(
                'success',
                result.kind === 'duplicate-same'
                  ? 'Chest X-ray processed. Comparison completed.'
                  : 'Chest X-ray uploaded. Comparison completed.',
              );
            } else if (
              latestCxrNote === 'Auto CXR comparison: no prior baseline image found.'
            ) {
              setChatUploadStatus('CXR uploaded. Waiting for a prior baseline image.');
              pushToast(
                'info',
                'Chest X-ray uploaded. Add an older baseline CXR to enable comparison.',
              );
            } else if (
              latestCxrNote?.startsWith('Auto CXR comparison unavailable:')
            ) {
              setChatUploadStatus('CXR uploaded, but automatic comparison was unavailable.');
              pushToast(
                'info',
                'Chest X-ray uploaded, but automatic comparison was unavailable for this file.',
              );
            } else {
              setChatUploadStatus('CXR uploaded. Comparison status unavailable.');
              pushToast(
                'info',
                'Chest X-ray uploaded. Comparison note was not found.',
              );
            }
            await reloadDocuments();
          } catch (error) {
            handleError('Failed to upload chest X-ray', error);
            setChatUploadStatus('Upload failed.');
          } finally {
            setIsChatUploading(false);
          }
          return;
        }
        setIsChatUploading(true);
        setChatUploadStatus('Analyzing image...');
        try {
          await sendVision(single, question);
          setChatUploadStatus('Image analysis complete.');
          pushToast('success', 'Image analyzed with MedGemma.');
        } catch (error) {
          handleError('Failed to analyze image', error);
          setChatUploadStatus('Image analysis failed.');
        } finally {
          setIsChatUploading(false);
        }
        return;
      }

      // Default: treat as report
      setIsChatUploading(true);
      setChatUploadStatus('Uploading report...');
      try {
        const result = await uploadWithDuplicateCheck(single, { title: single.name });
        const targetId = result.id;
        if (result.kind === 'duplicate-other') {
          handleError(
            'Duplicate document',
            new Error('This file already exists under a different family member. Duplicate uploads across profiles are blocked.'),
          );
          setChatUploadStatus('Upload failed.');
          return;
        }
        setChatUploadStatus('Processing for chat...');
        await api.processDocument(targetId);
        setChatUploadStatus('Ready to chat with this report.');
        pushToast('success', result.kind === 'duplicate-same' ? 'Report processed.' : 'Report uploaded and processed.');
        await reloadDocuments();
      } catch (error) {
        handleError('Failed to upload chat file', error);
        setChatUploadStatus('Upload failed.');
      } finally {
        setIsChatUploading(false);
      }
    },
    [handleError, patientId, pushToast, question, reloadDocuments, sendVision, sendVolume, sendWsi, uploadWithDuplicateCheck],
  );

  const handleChatUpload = useCallback(
    async (file: File | File[]) => {
      const files = Array.isArray(file) ? file : [file];
      for (const single of files) {
        await handleSingleChatUpload(single);
      }
    },
    [handleSingleChatUpload],
  );

  const handleLocalizeUpload = useCallback(
    async (file: File) => {
      if (!patientId) {
        pushToast('info', 'Select a patient before localizing.');
        return;
      }
      setIsChatUploading(true);
      setChatUploadStatus('Localizing findings...');
      const imageUrl = URL.createObjectURL(file);
      try {
        const modality = isCxrFilename(file.name) ? 'cxr' : 'imaging';
        const prompt = question.trim() || 'Localize findings in this image.';
        pushMessage({ role: 'user', content: `${prompt}\n[Localization: ${file.name}]` });
        setQuestion('');
        const response = await api.localizeFindings(patientId, prompt, file, modality);
        const boxes = response.boxes ?? [];
        setLocalizationPreview({ imageUrl, boxes });
        const topLabels = boxes
          .slice(0, 3)
          .map((box) => `${box.label} (${Math.round(box.confidence * 100)}%)`)
          .join(', ');
        const summaryText = boxes.length
          ? `Localization found ${boxes.length} region(s): ${topLabels}.`
          : 'Localization found no regions.';
        pushMessage({ role: 'assistant', content: summaryText });
        try {
          await api.uploadDocument(patientId, file, {
            title: file.name,
            document_type: 'imaging',
            category: 'localization',
            description: `Auto localization: ${summaryText}`,
          });
        } catch {
          // Optional persistence; ignore failures.
        }
        setChatUploadStatus('Localization complete.');
        pushToast('success', 'Localization ready.');
      } catch (error) {
        if (error instanceof ApiError && error.status === 404) {
          pushToast('error', 'Localization endpoint unavailable. Restart the backend.');
        } else {
          handleError('Failed to localize image', error);
        }
        setChatUploadStatus('Localization failed.');
        URL.revokeObjectURL(imageUrl);
      } finally {
        setIsChatUploading(false);
      }
    },
    [handleError, patientId, pushMessage, pushToast, question, setQuestion],
  );

  const clearLocalizationPreview = useCallback(() => {
    if (localizationPreview) {
      URL.revokeObjectURL(localizationPreview.imageUrl);
    }
    setLocalizationPreview(null);
  }, [localizationPreview]);

  return {
    chatUploadStatus,
    isChatUploading,
    localizationPreview,
    handleChatUpload,
    handleLocalizeUpload,
    clearLocalizationPreview,
  };
};

export default useChatUploads;
