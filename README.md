# 0804 Frame Extraction Pipeline

This package contains the two Windows-side toolsets used by the camera collection workflow.

## Directories

- `collection_pipeline/`: SD-card collection, archive, extraction, and NAS upload pipeline.
- `collection_pipeline/desktop_launcher/`: desktop batch launcher and localized menu text.
- `collection_pipeline/streaming_tools/`: local streaming frame extraction and timed NAS upload scripts added on 2026-08-04.
- `camera_time_sync/`: GPlus camera batch time correction scripts and usage notes.

## Current direct-link network

- PC Ethernet: `10.10.10.1/24`
- NAS Ethernet: `10.10.10.2/24`
- NAS share: `\\10.10.10.2\collector-data`
- Archive root after mapping: `Z:\Processed Videos`

## Streaming extraction benchmark

`collection_pipeline/streaming_tools/抽帧测速.ps1` reads videos from `F:\VIDEO`, decodes locally with ffmpeg, and streams JPEG frames directly into one `frames_low.zip`. It does not create loose JPEG files and does not call an AI model, API, or cloud service.

The terminal prints start time, live elapsed time, ETA, per-video timing, end time, and total elapsed time.

## Timed NAS upload

`collection_pipeline/streaming_tools/上传NAS测速.ps1` uploads the latest completed `frames_low.zip` to the matching owner/date directory on the NAS. It writes a temporary `.uploading` file, flushes and size-checks it, then atomically publishes `frames_low.zip`.

## Runtime files excluded

Git metadata, Python caches, card-check logs, backup snapshots, local Claude permissions, machine-specific roster paths, and temporary benchmark output are intentionally excluded.
