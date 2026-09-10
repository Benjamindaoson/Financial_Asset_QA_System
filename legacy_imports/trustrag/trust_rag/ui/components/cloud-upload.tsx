"use client";

import React, { useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Loading } from '@/components/ui/loading';
import { useDocuments } from '@/hooks/useDocuments';
import { CloudValidationResult, CloudProvider } from '@/types';
import {
  Cloud,
  Link as LinkIcon,
  CheckCircle,
  XCircle,
  AlertCircle,
  Upload,
  FileText,
  Download,
  Trash2,
  ExternalLink
} from 'lucide-react';

interface CloudUploadProps {
  className?: string;
}

const SUPPORTED_PROVIDERS: CloudProvider[] = [
  {
    name: 'google_drive',
    display_name: 'Google Drive',
    supported: true,
    requires_auth: false,
    examples: [
      'https://drive.google.com/file/d/1abc.../view',
      'https://docs.google.com/document/d/1abc...'
    ]
  },
  {
    name: 'baidu_yun',
    display_name: '百度网盘',
    supported: true,
    requires_auth: true,
    examples: [
      'https://pan.baidu.com/s/1abc...'
    ]
  },
  {
    name: 'quark',
    display_name: '夸克网盘',
    supported: true,
    requires_auth: true,
    examples: [
      'https://pan.quark.cn/s/1abc...'
    ]
  },
  {
    name: 'onedrive',
    display_name: 'OneDrive',
    supported: true,
    requires_auth: true,
    examples: [
      'https://onedrive.live.com/?id=1abc...'
    ]
  },
  {
    name: 'dropbox',
    display_name: 'Dropbox',
    supported: true,
    requires_auth: false,
    examples: [
      'https://www.dropbox.com/s/1abc.../file.pdf'
    ]
  }
];

export function CloudUpload({ className }: CloudUploadProps) {
  const [cloudUrls, setCloudUrls] = useState<string[]>(['']);
  const [currentTab, setCurrentTab] = useState<'single' | 'batch'>('single');
  const [showProviders, setShowProviders] = useState(false);

  const {
    validateCloudLink,
    validateCloudLinksBatch,
    downloadCloudFile,
    downloadCloudFilesBatch,
    validatingLinks,
    downloadingCloud,
    cloudValidationResults,
    getCloudProviders
  } = useDocuments();

  const addUrlField = () => {
    setCloudUrls(prev => [...prev, '']);
  };

  const removeUrlField = (index: number) => {
    setCloudUrls(prev => prev.filter((_, i) => i !== index));
  };

  const updateUrl = (index: number, url: string) => {
    setCloudUrls(prev => prev.map((u, i) => i === index ? url : u));
  };

  const handleSingleValidate = async (url: string) => {
    if (!url.trim()) return;
    await validateCloudLink(url);
  };

  const handleSingleDownload = async (url: string) => {
    if (!url.trim()) return;
    await downloadCloudFile(url);
  };

  const handleBatchValidate = async () => {
    const validUrls = cloudUrls.filter(url => url.trim());
    if (validUrls.length === 0) return;
    await validateCloudLinksBatch(validUrls);
  };

  const handleBatchDownload = async () => {
    const validUrls = cloudUrls.filter(url => url.trim());
    if (validUrls.length === 0) return;
    await downloadCloudFilesBatch(validUrls);
  };

  const getValidationIcon = (result?: CloudValidationResult) => {
    if (!result) return null;

    if (result.is_valid) {
      return <CheckCircle className="w-5 h-5 text-green-500" />;
    } else {
      return <XCircle className="w-5 h-5 text-red-500" />;
    }
  };

  const getValidationStatus = (result?: CloudValidationResult) => {
    if (!result) return null;

    if (result.is_valid) {
      return (
        <div className="flex items-center gap-2 text-green-600">
          <CheckCircle className="w-4 h-4" />
          <span className="text-sm">Valid link</span>
        </div>
      );
    } else {
      return (
        <div className="flex items-center gap-2 text-red-600">
          <XCircle className="w-4 h-4" />
          <span className="text-sm">{result.error_message || 'Invalid link'}</span>
        </div>
      );
    }
  };

  return (
    <div className={className}>
      <Card className="bg-white/5 border-white/10 backdrop-blur-sm">
        <CardHeader>
          <CardTitle className="text-white flex items-center gap-2">
            <Cloud className="w-5 h-5" />
            Cloud Storage Upload
          </CardTitle>
          <p className="text-white/60 text-sm">
            Upload files from cloud storage platforms
          </p>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Tab Selection */}
          <div className="flex gap-2">
            <Button
              variant={currentTab === 'single' ? 'default' : 'outline'}
              size="sm"
              onClick={() => setCurrentTab('single')}
              className="text-white border-white/20"
            >
              Single Upload
            </Button>
            <Button
              variant={currentTab === 'batch' ? 'default' : 'outline'}
              size="sm"
              onClick={() => setCurrentTab('batch')}
              className="text-white border-white/20"
            >
              Batch Upload
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowProviders(!showProviders)}
              className="text-white border-white/20 ml-auto"
            >
              Supported Platforms
            </Button>
          </div>

          {/* Supported Providers Info */}
          <AnimatePresence>
            {showProviders && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                className="bg-white/5 rounded-lg p-4"
              >
                <h4 className="text-white font-semibold mb-3">Supported Cloud Platforms</h4>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {SUPPORTED_PROVIDERS.map((provider) => (
                    <div key={provider.name} className="bg-white/5 rounded p-3">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-white font-medium">{provider.display_name}</span>
                        <div className="flex items-center gap-1">
                          {provider.requires_auth && (
                            <AlertCircle className="w-4 h-4 text-amber-400" title="Requires authentication" />
                          )}
                          {provider.supported ? (
                            <CheckCircle className="w-4 h-4 text-green-400" />
                          ) : (
                            <XCircle className="w-4 h-4 text-gray-400" />
                          )}
                        </div>
                      </div>
                      <div className="text-xs text-white/60 space-y-1">
                        {provider.examples.slice(0, 1).map((example, i) => (
                          <div key={i} className="font-mono bg-black/20 p-1 rounded">
                            {example}
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Single Upload */}
          <AnimatePresence mode="wait">
            {currentTab === 'single' && (
              <motion.div
                key="single"
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 20 }}
                className="space-y-4"
              >
                <div className="flex gap-3">
                  <div className="flex-1">
                    <Input
                      value={cloudUrls[0] || ''}
                      onChange={(e) => updateUrl(0, e.target.value)}
                      placeholder="Paste cloud storage sharing link..."
                      className="bg-white/10 border-white/20 text-white placeholder:text-white/50"
                    />
                  </div>
                  <Button
                    onClick={() => handleSingleValidate(cloudUrls[0])}
                    disabled={validatingLinks || !cloudUrls[0]?.trim()}
                    variant="outline"
                    className="text-white border-white/20"
                  >
                    {validatingLinks ? <Loading size="sm" /> : 'Validate'}
                  </Button>
                  <Button
                    onClick={() => handleSingleDownload(cloudUrls[0])}
                    disabled={downloadingCloud || !cloudUrls[0]?.trim()}
                    className="bg-blue-600 hover:bg-blue-700"
                  >
                    {downloadingCloud ? <Loading size="sm" /> : <Download className="w-4 h-4 mr-2" />}
                    Download
                  </Button>
                </div>

                {/* Validation Result */}
                {cloudUrls[0] && cloudValidationResults[cloudUrls[0]] && (
                  <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="bg-white/5 rounded-lg p-4"
                  >
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex items-center gap-3">
                        {getValidationIcon(cloudValidationResults[cloudUrls[0]])}
                        <div>
                          <p className="text-white font-medium">
                            {cloudValidationResults[cloudUrls[0]].file_info?.filename || 'Unknown file'}
                          </p>
                          <p className="text-white/60 text-sm">
                            {cloudValidationResults[cloudUrls[0]].provider?.replace('_', ' ').toUpperCase()}
                          </p>
                        </div>
                      </div>
                      {cloudValidationResults[cloudUrls[0]].file_info && (
                        <div className="text-right text-xs text-white/60">
                          <p>{(cloudValidationResults[cloudUrls[0]].file_info.size / 1024 / 1024).toFixed(1)} MB</p>
                          <p>{cloudValidationResults[cloudUrls[0]].file_info.mime_type}</p>
                        </div>
                      )}
                    </div>

                    {getValidationStatus(cloudValidationResults[cloudUrls[0]])}

                    {cloudValidationResults[cloudUrls[0]].is_valid && (
                      <div className="mt-3 flex gap-2">
                        <Button size="sm" className="bg-blue-600 hover:bg-blue-700">
                          <Download className="w-4 h-4 mr-2" />
                          Download & Process
                        </Button>
                        <Button size="sm" variant="outline" className="border-white/20 text-white">
                          <ExternalLink className="w-4 h-4 mr-2" />
                          Open Original
                        </Button>
                      </div>
                    )}
                  </motion.div>
                )}
              </motion.div>
            )}

            {/* Batch Upload */}
            {currentTab === 'batch' && (
              <motion.div
                key="batch"
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 20 }}
                className="space-y-4"
              >
                <div className="space-y-3">
                  {cloudUrls.map((url, index) => (
                    <div key={index} className="flex gap-3">
                      <div className="flex-1">
                        <Input
                          value={url}
                          onChange={(e) => updateUrl(index, e.target.value)}
                          placeholder={`Cloud storage link ${index + 1}...`}
                          className="bg-white/10 border-white/20 text-white placeholder:text-white/50"
                        />
                      </div>
                      {cloudUrls.length > 1 && (
                        <Button
                          onClick={() => removeUrlField(index)}
                          variant="outline"
                          size="sm"
                          className="border-white/20 text-white hover:bg-red-500/20"
                        >
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      )}
                      <div className="flex items-center">
                        {cloudValidationResults[url] && getValidationIcon(cloudValidationResults[url])}
                      </div>
                    </div>
                  ))}
                </div>

                <div className="flex gap-3">
                  <Button
                    onClick={addUrlField}
                    variant="outline"
                    size="sm"
                    className="border-white/20 text-white"
                  >
                    <LinkIcon className="w-4 h-4 mr-2" />
                    Add Link
                  </Button>
                  <Button
                    onClick={handleBatchValidate}
                    disabled={validatingLinks || cloudUrls.filter(u => u.trim()).length === 0}
                    variant="outline"
                    className="border-white/20 text-white"
                  >
                    {validatingLinks ? <Loading size="sm" /> : 'Validate All'}
                  </Button>
                  <Button
                    onClick={handleBatchDownload}
                    disabled={downloadingCloud || cloudUrls.filter(u => u.trim()).length === 0}
                    className="bg-blue-600 hover:bg-blue-700"
                  >
                    {downloadingCloud ? <Loading size="sm" /> : <Upload className="w-4 h-4 mr-2" />}
                    Process All
                  </Button>
                </div>

                {/* Batch Results Summary */}
                {Object.keys(cloudValidationResults).length > 0 && (
                  <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="bg-white/5 rounded-lg p-4"
                  >
                    <h4 className="text-white font-semibold mb-3">Batch Validation Summary</h4>
                    <div className="grid grid-cols-3 gap-4 text-center">
                      <div>
                        <p className="text-2xl font-bold text-green-400">
                          {Object.values(cloudValidationResults).filter(r => r.is_valid).length}
                        </p>
                        <p className="text-xs text-white/60">Valid</p>
                      </div>
                      <div>
                        <p className="text-2xl font-bold text-red-400">
                          {Object.values(cloudValidationResults).filter(r => !r.is_valid).length}
                        </p>
                        <p className="text-xs text-white/60">Invalid</p>
                      </div>
                      <div>
                        <p className="text-2xl font-bold text-blue-400">
                          {Object.keys(cloudValidationResults).length}
                        </p>
                        <p className="text-xs text-white/60">Total</p>
                      </div>
                    </div>
                  </motion.div>
                )}
              </motion.div>
            )}
          </AnimatePresence>

          {/* Help Text */}
          <div className="text-xs text-white/40 bg-white/5 rounded-lg p-3">
            <p className="font-medium mb-2">💡 Tips:</p>
            <ul className="space-y-1 list-disc list-inside">
              <li>Make sure sharing links are set to "Anyone with the link can view"</li>
              <li>Supported formats: PDF, DOC, TXT, CSV, XLSX, images, audio, video</li>
              <li>Files up to 50MB are supported for direct upload</li>
              <li>Batch processing supports up to 10 files simultaneously</li>
            </ul>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}







