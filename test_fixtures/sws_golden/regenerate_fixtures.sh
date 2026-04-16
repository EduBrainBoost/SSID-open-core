#!/bin/bash
# regenerate_fixtures.sh
# Deterministically regenerate all SWS golden test fixtures
# Usage: ./regenerate_fixtures.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXPECTED_DIR="${SCRIPT_DIR}/expected_outputs"
REF_HASH_FILE="${SCRIPT_DIR}/reference_hashes.json"

echo "[INFO] Regenerating SWS golden fixtures..."

# Clean expected_outputs directory
if [ -d "$EXPECTED_DIR" ]; then
    rm -rf "$EXPECTED_DIR"
    echo "[OK] Cleared expected_outputs directory"
fi

mkdir -p "$EXPECTED_DIR"

# Generate all expected outputs with deterministic seed
python3 << 'PYTHON_EOF'
import json
import hashlib
from pathlib import Path

base_path = Path(__file__).parent
expected_path = base_path / "expected_outputs"
expected_path.mkdir(parents=True, exist_ok=True)

source_content = b"synthetic_short_video_v1.0_seed42"
source_hash = hashlib.sha256(source_content).hexdigest()

outputs = {
    "source_manifest.json": {
        "source_id": "synthetic_short_video_v1.0",
        "filename": "synthetic_short_video.mp4",
        "duration_seconds": 300,
        "width": 1920,
        "height": 1080,
        "frame_rate": 30,
        "codec_video": "h264",
        "codec_audio": "aac",
        "sample_rate": 44100,
        "channels": 2,
        "file_size_bytes": 25000000,
        "created_timestamp": "2026-04-17T00:00:00Z",
        "source_hash": source_hash
    },
    "media_technical.json": {
        "resolution": {
            "width": 1920,
            "height": 1080,
            "aspect_ratio": "16:9"
        },
        "temporal": {
            "duration_seconds": 300,
            "frame_rate": 30,
            "total_frames": 9000
        },
        "codec": {
            "video_codec": "h264",
            "video_profile": "high",
            "audio_codec": "aac",
            "audio_sample_rate": 44100,
            "audio_channels": 2
        },
        "quality_metrics": {
            "bitrate_video_kbps": 2500,
            "bitrate_audio_kbps": 128,
            "pix_fmt": "yuv420p"
        }
    },
    "shot_timeline.json": {
        "shots": [
            {"shot_id": "shot_001", "start_frame": 0, "end_frame": 3000, "duration_seconds": 100, "scene_type": "opening_static", "confidence": 0.95},
            {"shot_id": "shot_002", "start_frame": 3000, "end_frame": 6000, "duration_seconds": 100, "scene_type": "transition_fade", "confidence": 0.87},
            {"shot_id": "shot_003", "start_frame": 6000, "end_frame": 9000, "duration_seconds": 100, "scene_type": "closing_static", "confidence": 0.92}
        ],
        "total_shots": 3
    },
    "transcript_master.json": {
        "transcript_id": "transcript_v1",
        "language": "en",
        "segments": [
            {"segment_id": 1, "start_time": 0.0, "end_time": 100.0, "text": "[Synthetic test audio segment 1]", "confidence": 0.89},
            {"segment_id": 2, "start_time": 100.0, "end_time": 200.0, "text": "[Synthetic test audio segment 2]", "confidence": 0.91},
            {"segment_id": 3, "start_time": 200.0, "end_time": 300.0, "text": "[Synthetic test audio segment 3]", "confidence": 0.88}
        ],
        "full_text": "[Synthetic test audio segment 1] [Synthetic test audio segment 2] [Synthetic test audio segment 3]"
    },
    "caption_layers.json": {
        "layers": [],
        "note": "No detected captions in synthetic test video"
    },
    "audio_map.json": {
        "source_channels": 1,
        "output_channels": 2,
        "channel_map": {"channel_0": {"type": "mono_to_stereo", "left_source": 0, "right_source": 0}}
    },
    "hook_fingerprint.json": {
        "hooks": [],
        "note": "No detected hooks in synthetic test video"
    },
    "processing_metadata.json": {
        "analyzer_version": "sws_analyzer_v1.0",
        "processing_timestamp": "2026-04-17T00:00:00Z",
        "processing_duration_seconds": 15.3,
        "stages_completed": ["frame_extraction", "shot_detection", "transcript_extraction", "audio_analysis", "caption_detection", "hook_detection"]
    },
    "quality_assessment.json": {
        "overall_score": 0.88,
        "components": {"video_clarity": 0.92, "audio_quality": 0.85, "shot_detection_confidence": 0.91, "transcript_confidence": 0.89},
        "warnings": []
    },
    "archive_metadata.json": {
        "archive_id": "archive_sws_golden_v1",
        "created_date": "2026-04-17",
        "analyst_notes": "Golden fixture for SWS test suite. Deterministically generated synthetic video.",
        "retention_policy": "indefinite"
    },
    "validation_report.json": {
        "validation_timestamp": "2026-04-17T00:00:00Z",
        "checks_passed": 11,
        "checks_total": 11,
        "status": "PASS",
        "details": {"file_exists": True, "file_size_in_range": True, "codec_valid": True, "resolution_valid": True, "duration_valid": True, "metadata_complete": True, "audio_present": True, "transcript_valid": True, "shots_detected": True, "hashes_match": True, "no_corruption": True}
    }
}

for filename, data in outputs.items():
    filepath = expected_path / filename
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)

print("[OK] Generated all 11 expected_outputs")
PYTHON_EOF

# Verify hashes
python3 << 'PYTHON_EOF'
import json
import hashlib
from pathlib import Path

expected_path = Path(__file__).parent / "expected_outputs"
ref_hash_file = Path(__file__).parent / "reference_hashes.json"

if not ref_hash_file.exists():
    print("[WARN] reference_hashes.json not found, regenerating...")
else:
    with open(ref_hash_file) as f:
        ref_hashes = json.load(f)

    all_match = True
    for json_file in sorted(expected_path.glob("*.json")):
        with open(json_file, 'rb') as f:
            content = f.read()
            file_hash = hashlib.sha256(content).hexdigest()
            expected_hash = ref_hashes["outputs"][json_file.name]["sha256"]

            if file_hash == expected_hash:
                print("[OK] %s hash matches" % json_file.name)
            else:
                print("[FAIL] %s hash mismatch (expected %s, got %s)" % (json_file.name, expected_hash, file_hash))
                all_match = False

    if all_match:
        print("\n[OK] All fixtures verified against reference hashes")
        exit(0)
    else:
        print("\n[FAIL] Some fixtures do not match reference hashes")
        exit(1)
PYTHON_EOF

echo "[OK] regenerate_fixtures.sh completed successfully"
