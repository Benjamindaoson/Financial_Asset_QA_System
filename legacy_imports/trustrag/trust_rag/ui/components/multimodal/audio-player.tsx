"use client";

import React, { useState, useRef, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Slider } from '@/components/ui/slider';
import { AudioAnalysis } from '@/types';
import { formatDuration } from '@/lib/utils';

interface AudioPlayerProps {
  audioData: AudioAnalysis;
  className?: string;
  autoPlay?: boolean;
  showTranscript?: boolean;
  showWaveform?: boolean;
}

export function AudioPlayer({
  audioData,
  className,
  autoPlay = false,
  showTranscript = true,
  showWaveform = true
}: AudioPlayerProps) {
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(audioData.duration || 0);
  const [volume, setVolume] = useState(1);
  const [showTranscript, setShowTranscriptState] = useState(showTranscript);

  const audioRef = useRef<HTMLAudioElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;

    const updateTime = () => setCurrentTime(audio.currentTime);
    const updateDuration = () => setDuration(audio.duration || audioData.duration || 0);
    const handleEnded = () => setIsPlaying(false);

    audio.addEventListener('timeupdate', updateTime);
    audio.addEventListener('loadedmetadata', updateDuration);
    audio.addEventListener('ended', handleEnded);

    if (autoPlay) {
      audio.play().catch(console.error);
    }

    return () => {
      audio.removeEventListener('timeupdate', updateTime);
      audio.removeEventListener('loadedmetadata', updateDuration);
      audio.removeEventListener('ended', handleEnded);
    };
  }, [autoPlay, audioData.duration]);

  useEffect(() => {
    if (showWaveform && canvasRef.current) {
      drawWaveform();
    }
  }, [audioData, showWaveform]);

  const drawWaveform = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const width = canvas.width;
    const height = canvas.height;

    // Clear canvas
    ctx.clearRect(0, 0, width, height);

    // Draw waveform (simplified - in real implementation, you'd use actual audio data)
    ctx.strokeStyle = '#3b82f6';
    ctx.lineWidth = 2;
    ctx.beginPath();

    const segments = 100;
    const amplitude = height / 4;

    for (let i = 0; i <= segments; i++) {
      const x = (i / segments) * width;
      const y = height / 2 + Math.sin((i / segments) * Math.PI * 4) * amplitude * Math.random();

      if (i === 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
    }

    ctx.stroke();

    // Draw progress line
    const progressX = (currentTime / duration) * width;
    ctx.strokeStyle = '#ef4444';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(progressX, 0);
    ctx.lineTo(progressX, height);
    ctx.stroke();
  };

  const togglePlay = async () => {
    const audio = audioRef.current;
    if (!audio) return;

    try {
      if (isPlaying) {
        audio.pause();
        setIsPlaying(false);
      } else {
        await audio.play();
        setIsPlaying(true);
      }
    } catch (error) {
      console.error('Audio playback error:', error);
    }
  };

  const handleSeek = (value: number[]) => {
    const audio = audioRef.current;
    if (audio) {
      audio.currentTime = value[0];
      setCurrentTime(value[0]);
    }
  };

  const handleVolumeChange = (value: number[]) => {
    const audio = audioRef.current;
    if (audio) {
      audio.volume = value[0];
      setVolume(value[0]);
    }
  };

  const skipTime = (seconds: number) => {
    const audio = audioRef.current;
    if (audio) {
      audio.currentTime = Math.max(0, Math.min(duration, audio.currentTime + seconds));
    }
  };

  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle className="text-lg flex items-center justify-between">
          <span>Audio Analysis</span>
          <div className="text-sm text-muted-foreground">
            Duration: {formatDuration(duration * 1000)}
          </div>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Audio Controls */}
        <div className="flex items-center gap-4">
          <Button
            variant="outline"
            size="sm"
            onClick={() => skipTime(-10)}
            disabled={!duration}
          >
            ⏪ 10s
          </Button>

          <Button
            onClick={togglePlay}
            disabled={!duration}
            className="w-12 h-12 rounded-full"
          >
            {isPlaying ? '⏸️' : '▶️'}
          </Button>

          <Button
            variant="outline"
            size="sm"
            onClick={() => skipTime(10)}
            disabled={!duration}
          >
            10s ⏩
          </Button>

          <div className="flex items-center gap-2 ml-4">
            <span className="text-sm">🔊</span>
            <Slider
              value={[volume]}
              onValueChange={handleVolumeChange}
              max={1}
              step={0.1}
              className="w-20"
            />
          </div>
        </div>

        {/* Progress Bar */}
        <div className="space-y-2">
          <Slider
            value={[currentTime]}
            onValueChange={handleSeek}
            max={duration || 100}
            step={0.1}
            className="w-full"
          />
          <div className="flex justify-between text-xs text-muted-foreground">
            <span>{formatDuration(currentTime * 1000)}</span>
            <span>{formatDuration(duration * 1000)}</span>
          </div>
        </div>

        {/* Waveform Visualization */}
        {showWaveform && (
          <div className="border rounded-lg p-4 bg-muted/20">
            <canvas
              ref={canvasRef}
              width={600}
              height={80}
              className="w-full h-20 border border-muted rounded"
            />
          </div>
        )}

        {/* Audio Analysis Info */}
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <span className="font-medium">Language:</span>
            <span className="ml-2 text-muted-foreground">{audioData.language || 'Unknown'}</span>
          </div>
          <div>
            <span className="font-medium">Confidence:</span>
            <span className="ml-2 text-muted-foreground">
              {(audioData.confidence * 100).toFixed(1)}%
            </span>
          </div>
        </div>

        {/* Transcript Toggle */}
        <div className="flex items-center justify-between">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowTranscriptState(!showTranscript)}
          >
            {showTranscript ? 'Hide' : 'Show'} Transcript
          </Button>
        </div>

        {/* Transcript */}
        {showTranscript && audioData.transcription && (
          <div className="border rounded-lg p-4 max-h-40 overflow-y-auto">
            <h4 className="font-medium mb-2">Transcript</h4>
            <p className="text-sm text-muted-foreground leading-relaxed">
              {audioData.transcription}
            </p>

            {audioData.segments && audioData.segments.length > 0 && (
              <div className="mt-4 space-y-2">
                <h5 className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                  Segments
                </h5>
                {audioData.segments.slice(0, 5).map((segment, index) => (
                  <div key={index} className="flex items-start gap-3 text-xs">
                    <span className="text-muted-foreground w-12">
                      {formatDuration(segment.start * 1000)}
                    </span>
                    <span className="flex-1">{segment.text}</span>
                    <span className="text-muted-foreground">
                      {(segment.confidence * 100).toFixed(0)}%
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Hidden Audio Element */}
        <audio
          ref={audioRef}
          src="" // Would be set from props or context
          preload="metadata"
          onError={(e) => console.error('Audio loading error:', e)}
        />
      </CardContent>
    </Card>
  );
}







