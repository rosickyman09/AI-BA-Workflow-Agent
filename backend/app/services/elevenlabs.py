"""
ElevenLabs Scribe v2 Speech-to-Text service.

Submits audio/video files to ElevenLabs /v1/speech-to-text for transcription.
The call is made synchronously inside a FastAPI BackgroundTask so the upload
endpoint returns immediately while processing continues in the background.

Gracefully degrades (returns None) when API key is not configured.
"""
import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

_API_KEY: str = os.environ.get("ELEVENLABS_API_KEY", "")
_SCRIBE_URL = "https://api.elevenlabs.io/v1/speech-to-text"

# MIME types that qualify for STT
_AUDIO_PREFIXES = ("audio/", "video/")


def is_audio(mime_type: str) -> bool:
    """Return True when the MIME type represents an audio or video file."""
    return any(mime_type.startswith(p) for p in _AUDIO_PREFIXES)


async def transcribe(
    file_bytes: bytes,
    filename: str,
    mime_type: str,
) -> Optional[str]:
    """
    Submit *file_bytes* to ElevenLabs Scribe v2 for transcription.

    Returns the plain-text transcript on success, or None when the API key
    is not configured or the request fails.
    """
    if not _API_KEY:
        logger.info(
            "ELEVENLABS_API_KEY not set — skipping STT for '%s'", filename
        )
        return None

    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                _SCRIBE_URL,
                headers={"xi-api-key": _API_KEY},
                files={"file": (filename, file_bytes, mime_type)},
                data={
                    "model_id": "scribe_v2",
                    "tag_audio_events": "true",
                    "diarize": "true",
                },
            )
            response.raise_for_status()
            data = response.json()
            # Scribe v2 returns { "text": "...", "words": [...], ... }
            transcript: str = data.get("text", "")
            logger.info(
                "STT completed for '%s': %d chars", filename, len(transcript)
            )
            return transcript if transcript else None
    except httpx.HTTPStatusError as exc:
        logger.error(
            "ElevenLabs STT HTTP error for '%s': %s %s",
            filename,
            exc.response.status_code,
            exc.response.text,
        )
        return None
    except Exception as exc:
        logger.error("ElevenLabs STT failed for '%s': %s", filename, exc)
        return None
