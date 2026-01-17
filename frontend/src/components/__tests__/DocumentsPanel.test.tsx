import { render, screen } from '@testing-library/react';
import { expect, it, vi } from 'vitest';
import DocumentsPanel from '../DocumentsPanel';

it('renders loading skeletons when loading', () => {
  render(
    <DocumentsPanel
      documents={[]}
      isLoading={true}
      processingIds={[]}
      selectedFile={null}
      status=""
      onFileChange={vi.fn()}
      onUpload={vi.fn()}
      onProcess={vi.fn()}
    />
  );

  const skeletons = document.querySelectorAll('.skeleton-row');
  expect(skeletons.length).toBeGreaterThan(0);
});

it('renders document rows', () => {
  render(
    <DocumentsPanel
      documents={[
        {
          id: 1,
          patient_id: 1,
          document_type: 'lab_report',
          original_filename: 'lab.pdf',
          processing_status: 'completed',
          is_processed: true,
        },
      ]}
      isLoading={false}
      processingIds={[]}
      selectedFile={null}
      status=""
      onFileChange={vi.fn()}
      onUpload={vi.fn()}
      onProcess={vi.fn()}
    />
  );

  expect(screen.getByText('lab.pdf')).toBeInTheDocument();
});
