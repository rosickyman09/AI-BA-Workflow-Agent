import React from 'react'

interface ProgressBarProps {
  progress: number      // 0–100
  stage: string         // current stage label
  title?: string        // header title
  show: boolean         // visibility toggle
  startTime?: number    // epoch ms — used for ETA calculation
}

export function ProgressBar({
  progress,
  stage,
  title = 'Processing...',
  show,
  startTime,
}: ProgressBarProps) {
  if (!show) return null

  const eta =
    startTime !== undefined && progress > 0 && progress < 100
      ? Math.ceil(((Date.now() - startTime) / progress) * (100 - progress) / 1000)
      : null

  return (
    <div
      style={{
        background: '#F0F7FF',
        border: '1px solid #D0E8F7',
        borderRadius: 12,
        padding: '16px 20px',
        margin: '12px 0',
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          marginBottom: 8,
          fontWeight: 600,
          fontSize: 14,
          color: '#1E4A6E',
        }}
      >
        <span>🔄</span>
        <span>{title}</span>
      </div>

      <div
        style={{
          fontSize: 13,
          color: '#666',
          fontStyle: 'italic',
          marginBottom: 10,
          minHeight: 20,
        }}
      >
        {stage}
      </div>

      <div
        style={{
          background: '#E2EFF7',
          borderRadius: 5,
          height: 10,
          overflow: 'hidden',
          marginBottom: 8,
        }}
      >
        <div
          style={{
            height: '100%',
            background: 'linear-gradient(90deg, #2E75B6, #4CAF50)',
            borderRadius: 5,
            width: `${progress}%`,
            transition: 'width 0.5s ease-in-out',
          }}
        />
      </div>

      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          fontSize: 13,
        }}
      >
        <span style={{ fontWeight: 700, color: '#1E4A6E', fontSize: 15 }}>
          {progress}%
        </span>
        {eta !== null && (
          <span style={{ color: '#888', fontSize: 12 }}>~{eta}s remaining</span>
        )}
      </div>
    </div>
  )
}
