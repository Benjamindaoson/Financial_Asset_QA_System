"use client";

import { useState, useCallback, useEffect } from 'react';
import { DocumentMetadata, IngestResult, ApiResponse, CloudValidationResult, CloudDownloadResult, CloudBatchResult } from '@/types';
import { useNotifications } from './useNotifications';
import { formatBytes } from '@/lib/utils';

const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50MB
const SUPPORTED_TYPES = [
  'application/pdf',
  'text/html',
  'text/plain',
  'text/csv',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  'application/vnd.ms-excel'
];

export function useDocuments() {
  const [documents, setDocuments] = useState<DocumentMetadata[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Cloud storage state
  const [validatingLinks, setValidatingLinks] = useState(false);
  const [downloadingCloud, setDownloadingCloud] = useState(false);
  const [cloudValidationResults, setCloudValidationResults] = useState<Record<string, CloudValidationResult>>({});

  const { addNotification } = useNotifications();

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

  const fetchDocuments = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${apiUrl}/api/documents`);
      if (!response.ok) {
        throw new Error(`Failed to fetch documents: ${response.status}`);
      }

      const data: ApiResponse<DocumentMetadata[]> = await response.json();
      if (data.success && data.data) {
        setDocuments(data.data);
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to fetch documents';
      setError(errorMessage);
      addNotification({
        type: 'error',
        title: 'Failed to Load Documents',
        message: errorMessage
      });
    } finally {
      setLoading(false);
    }
  }, [apiUrl, addNotification]);

  const uploadDocument = useCallback(async (file: File): Promise<IngestResult | null> => {
    // Validate file
    if (file.size > MAX_FILE_SIZE) {
      const errorMessage = `File size ${formatBytes(file.size)} exceeds maximum ${formatBytes(MAX_FILE_SIZE)}`;
      addNotification({
        type: 'error',
        title: 'File Too Large',
        message: errorMessage
      });
      return null;
    }

    if (!SUPPORTED_TYPES.includes(file.type)) {
      const errorMessage = `Unsupported file type: ${file.type}`;
      addNotification({
        type: 'error',
        title: 'Unsupported File Type',
        message: errorMessage
      });
      return null;
    }

    setUploading(true);
    setError(null);

    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('profile', 'generic');

      addNotification({
        type: 'info',
        title: 'Upload Started',
        message: `Uploading ${file.name}...`
      });

      const response = await fetch(`${apiUrl}/api/ingest`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail?.detail || errorData.detail || `Upload failed: ${response.status}`);
      }

      const data: IngestResult = await response.json();

      if (data.status === 'OK') {
        addNotification({
          type: 'success',
          title: 'Upload Successful',
          message: `${file.name} processed successfully with ${data.chunks_count} chunks`,
          duration: 5000
        });

        // Refresh document list
        await fetchDocuments();
      } else {
        addNotification({
          type: 'warning',
          title: 'Upload Completed with Issues',
          message: data.message,
          duration: 5000
        });
      }

      return data;

    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Upload failed';
      setError(errorMessage);
      addNotification({
        type: 'error',
        title: 'Upload Failed',
        message: errorMessage,
        duration: 7000
      });
      return null;
    } finally {
      setUploading(false);
    }
  }, [apiUrl, addNotification, fetchDocuments]);

  const deleteDocument = useCallback(async (docId: string): Promise<boolean> => {
    try {
      const response = await fetch(`${apiUrl}/api/documents/${docId}`, {
        method: 'DELETE',
      });

      if (!response.ok) {
        throw new Error(`Failed to delete document: ${response.status}`);
      }

      addNotification({
        type: 'success',
        title: 'Document Deleted',
        message: 'Document has been removed successfully'
      });

      // Refresh document list
      await fetchDocuments();
      return true;

    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to delete document';
      addNotification({
        type: 'error',
        title: 'Delete Failed',
        message: errorMessage
      });
      return false;
    }
  }, [apiUrl, addNotification, fetchDocuments]);

  const getDocumentDetails = useCallback(async (docId: string): Promise<DocumentMetadata | null> => {
    try {
      const response = await fetch(`${apiUrl}/api/documents/${docId}`);
      if (!response.ok) {
        throw new Error(`Failed to fetch document details: ${response.status}`);
      }

      const data: ApiResponse<DocumentMetadata> = await response.json();
      return data.success ? data.data || null : null;

    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to fetch document details';
      addNotification({
        type: 'error',
        title: 'Fetch Failed',
        message: errorMessage
      });
      return null;
    }
  }, [apiUrl, addNotification]);

  // Load documents on mount
  useEffect(() => {
    fetchDocuments();
  }, [fetchDocuments]);

  const validateCloudLink = async (url: string): Promise<CloudValidationResult | null> => {
    try {
      const response = await fetch(`${apiUrl}/api/cloud/validate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url, validate_only: true }),
      });

      if (!response.ok) {
        throw new Error(`Validation failed: ${response.status}`);
      }

      const result: CloudValidationResult = await response.json();

      // Cache validation result
      setCloudValidationResults(prev => ({ ...prev, [url]: result }));

      return result;
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Validation failed';
      addNotification({
        type: 'error',
        title: 'Link Validation Failed',
        message: errorMessage
      });
      return null;
    }
  };

  const validateCloudLinksBatch = async (urls: string[]): Promise<Record<string, CloudValidationResult> | null> => {
    try {
      setValidatingLinks(true);

      const response = await fetch(`${apiUrl}/api/cloud/batch/validate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ urls, validate_only: true }),
      });

      if (!response.ok) {
        throw new Error(`Batch validation failed: ${response.status}`);
      }

      const data = await response.json();
      const results: Record<string, CloudValidationResult> = {};

      data.results.forEach((result: any) => {
        results[result.url] = result;
      });

      // Cache all results
      setCloudValidationResults(prev => ({ ...prev, ...results }));

      addNotification({
        type: 'success',
        title: 'Batch Validation Complete',
        message: `${data.summary.valid_links} valid, ${data.summary.invalid_links} invalid links`
      });

      return results;
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Batch validation failed';
      addNotification({
        type: 'error',
        title: 'Batch Validation Failed',
        message: errorMessage
      });
      return null;
    } finally {
      setValidatingLinks(false);
    }
  };

  const downloadCloudFile = async (url: string): Promise<CloudDownloadResult | null> => {
    try {
      setDownloadingCloud(true);

      addNotification({
        type: 'info',
        title: 'Starting Download',
        message: 'Downloading file from cloud storage...'
      });

      const response = await fetch(`${apiUrl}/api/cloud/download`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Download failed: ${response.status}`);
      }

      const result: CloudDownloadResult = await response.json();

      if (result.success && result.ingest_result) {
        addNotification({
          type: 'success',
          title: 'Cloud File Processed',
          message: `${result.ingest_result.chunks_count} chunks created from cloud file`,
          duration: 5000
        });

        // Refresh document list
        await fetchDocuments();
      } else if (!result.success) {
        addNotification({
          type: 'error',
          title: 'Cloud Download Failed',
          message: result.error_message || 'Unknown error'
        });
      }

      return result;
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Download failed';
      addNotification({
        type: 'error',
        title: 'Cloud Download Failed',
        message: errorMessage
      });
      return null;
    } finally {
      setDownloadingCloud(false);
    }
  };

  const downloadCloudFilesBatch = async (urls: string[]): Promise<CloudBatchResult | null> => {
    try {
      setDownloadingCloud(true);

      addNotification({
        type: 'info',
        title: 'Batch Download Started',
        message: `Processing ${urls.length} cloud links...`
      });

      const response = await fetch(`${apiUrl}/api/cloud/batch/download`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ urls }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Batch download failed: ${response.status}`);
      }

      const result: CloudBatchResult = await response.json();

      const successCount = result.summary.successful_ingests;
      const failCount = result.summary.failed_ingests + result.summary.invalid_links;

      if (successCount > 0) {
        addNotification({
          type: 'success',
          title: 'Batch Processing Complete',
          message: `${successCount} files processed successfully${failCount > 0 ? `, ${failCount} failed` : ''}`,
          duration: 7000
        });

        // Refresh document list
        await fetchDocuments();
      }

      if (failCount > 0) {
        addNotification({
          type: 'warning',
          title: 'Some Downloads Failed',
          message: `${failCount} operations failed. Check results for details.`,
          duration: 5000
        });
      }

      return result;
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Batch download failed';
      addNotification({
        type: 'error',
        title: 'Batch Download Failed',
        message: errorMessage
      });
      return null;
    } finally {
      setDownloadingCloud(false);
    }
  };

  const getCloudProviders = async () => {
    try {
      const response = await fetch(`${apiUrl}/api/cloud/providers`);
      if (response.ok) {
        return await response.json();
      }
    } catch (err) {
      console.error('Failed to fetch cloud providers:', err);
    }
    return null;
  };

  return {
    // State
    documents,
    loading,
    uploading,
    error,
    validatingLinks,
    downloadingCloud,
    cloudValidationResults,

    // Actions
    fetchDocuments,
    uploadDocument,
    deleteDocument,
    getDocumentDetails,

    // Cloud Storage Actions
    validateCloudLink,
    validateCloudLinksBatch,
    downloadCloudFile,
    downloadCloudFilesBatch,
    getCloudProviders,

    // Computed
    hasDocuments: documents.length > 0,
    totalSize: documents.reduce((sum, doc) => sum + doc.size, 0),
    processingCount: documents.filter(doc => doc.status === 'processing').length,
    failedCount: documents.filter(doc => doc.status === 'failed').length,

    // Validation helpers
    isValidFile: (file: File) => {
      return file.size <= MAX_FILE_SIZE && SUPPORTED_TYPES.includes(file.type);
    },

    // Cloud validation helpers
    isValidCloudUrl: (url: string) => {
      // Basic URL validation for cloud links
      return url.startsWith('http') && (
        url.includes('drive.google.com') ||
        url.includes('pan.baidu.com') ||
        url.includes('pan.quark.cn') ||
        url.includes('onedrive.live.com') ||
        url.includes('1drv.ms') ||
        url.includes('dropbox.com')
      );
    },

    supportedTypes: SUPPORTED_TYPES,
    maxFileSize: MAX_FILE_SIZE,
    maxFileSizeFormatted: formatBytes(MAX_FILE_SIZE)
  };
}
