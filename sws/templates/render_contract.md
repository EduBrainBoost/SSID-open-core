# SWS Render Output Contract

## Purpose

Defines the mandatory specifications for all rendered output from the SWS rebuild pipeline.
Every render execution must produce output conforming to these constraints.

## Resolution Tiers

| Tier | Width | Height | Use Case |
|------|-------|--------|----------|
| SD | 854 | 480 | Preview, low-bandwidth |
| HD | 1280 | 720 | Standard distribution |
| FHD | 1920 | 1080 | Primary distribution |
| 4K | 3840 | 2160 | Premium distribution |

## Codec Requirements

| Parameter | Minimum | Recommended | Maximum |
|-----------|---------|-------------|---------|
| Video Codec | h264 baseline | h264 high | h265 main |
| Video Bitrate (kbps) | 500 | 2500 | 20000 |
| Audio Codec | aac-lc | aac-lc | opus |
| Audio Bitrate (kbps) | 64 | 128 | 320 |
| Audio Sample Rate (Hz) | 22050 | 44100 | 48000 |
| Frame Rate (fps) | 24 | 30 | 60 |

## Container Formats

| Format | Extension | Primary Use |
|--------|-----------|-------------|
| MP4 | .mp4 | YouTube, general distribution |
| WebM | .webm | Web embedding |
| MOV | .mov | Apple ecosystem, editing |

## Render Invariants

1. **Deterministic**: Same inputs must produce byte-identical outputs.
2. **Lossless audio path**: Audio is never re-encoded more than once from source.
3. **Frame-accurate timing**: All cuts, transitions, and overlays are frame-aligned.
4. **Color space preservation**: Source color space is maintained through the pipeline.
5. **Aspect ratio lock**: Output aspect ratio matches the render plan specification exactly.

## Quality Gates

- Output file must be playable by ffprobe without errors.
- Duration must match render plan timeline within 0.1 seconds.
- Audio/video sync drift must not exceed 40ms.
- No black frames outside of intentional transitions.
- File size must be within 20% of estimated (bitrate * duration).

## Artifact Outputs

Each render execution produces:

1. **render_output_manifest.json** — file refs, codec details, ffmpeg version
2. **rebuild_timeline.json** — the timeline that was rendered (input record)
3. Rendered media files per target resolution tier

## Platform-Specific Overrides

Platform policies (from `platform_policy.json`) may override default render
parameters. The render engine must check platform constraints before execution
and reject configurations that violate platform limits.

## Evidence Requirements

- SHA-256 hash of every output file
- ffprobe metadata snapshot of every output file
- Render duration and resource usage logged
- All overrides from platform policy documented in the manifest
