# SWS Golden Test Fixtures

This directory contains golden test fixtures for the SWS (Synthetic Video Stream) analyzer test suite.

## Contents

### Directories

- `expected_outputs/` - Reference JSON outputs from a deterministic synthetic video analysis
- `regenerate_fixtures.sh` - Script to deterministically regenerate all fixtures
- `reference_hashes.json` - SHA256 hashes of all expected outputs for integrity verification

### Expected Outputs (11 artifacts)

All outputs are deterministically generated with a fixed seed (42) to ensure consistency across test runs.

#### 1. source_manifest.json
- Video source metadata
- Resolution: 1920x1080
- Duration: 300 seconds (5 minutes)
- Codec: h264 video, AAC audio at 44.1 kHz
- SHA256 hash for integrity verification

#### 2. media_technical.json
- Technical specifications of the synthetic video
- Frame rate: 30 fps
- Total frames: 9000
- Bitrates and quality metrics

#### 3. shot_timeline.json
- Detected shot boundaries (3 shots)
- Shot IDs, frame ranges, scene types
- Confidence scores per shot

#### 4. transcript_master.json
- Synthesized audio transcript
- 3 segments covering the full 300-second duration
- Per-segment confidence scores

#### 5. caption_layers.json
- Detected caption/subtitle data
- Empty for synthetic video (expected behavior)

#### 6. audio_map.json
- Audio channel mapping (mono to stereo conversion)
- Source and output channel configuration

#### 7. hook_fingerprint.json
- Detected "hooks" (engagement markers)
- Empty for synthetic video (expected behavior)

#### 8. processing_metadata.json
- Analyzer version and processing timestamp
- List of completed analysis stages
- Processing duration (15.3 seconds)

#### 9. quality_assessment.json
- Overall quality score (0.88)
- Component scores:
  - Video clarity: 0.92
  - Audio quality: 0.85
  - Shot detection confidence: 0.91
  - Transcript confidence: 0.89

#### 10. archive_metadata.json
- Archive ID and creation date
- Analyst notes and retention policy

#### 11. validation_report.json
- Final validation status (PASS)
- 11/11 checks passed
- Detailed check results (file existence, codecs, duration, etc.)

## Usage

### Running the Test Suite

```bash
pytest test_fixtures/sws_golden/  # Runs all SWS golden tests
```

### Regenerating Fixtures

If you modify the analyzer logic and need to regenerate the golden fixtures:

```bash
cd test_fixtures/sws_golden
bash regenerate_fixtures.sh
```

**Important:** This script regenerates fixtures with the same deterministic seed (42), ensuring identical output JSON files. It will also verify that the regenerated files match the reference hashes.

### Verifying Fixtures

To verify that all fixtures match the reference hashes:

```bash
python3 << 'EOF'
import json
import hashlib
from pathlib import Path

ref_file = Path("test_fixtures/sws_golden/reference_hashes.json")
expected_dir = Path("test_fixtures/sws_golden/expected_outputs")

with open(ref_file) as f:
    ref_hashes = json.load(f)

for json_file in sorted(expected_dir.glob("*.json")):
    with open(json_file, 'rb') as f:
        actual_hash = hashlib.sha256(f.read()).hexdigest()
        expected_hash = ref_hashes["outputs"][json_file.name]["sha256"]
        status = "OK" if actual_hash == expected_hash else "FAIL"
        print("[%s] %s" % (status, json_file.name))
EOF
```

## Determinism Requirements

All fixtures are generated with fixed parameters:

- **Random Seed:** 42 (for numpy/random operations)
- **Timestamps:** Fixed to 2026-04-17T00:00:00Z
- **Source Hash:** Deterministic SHA256 of "synthetic_short_video_v1.0_seed42"
- **Confidence Scores:** Fixed values (not random)

This ensures that:
1. Same input → Same output (all 11 JSON files have identical content across runs)
2. Hash validation works reliably
3. Test assertions can use exact equality checks

## Synthetic Video Specifications

The analyzer processes a synthetic test video with these specs:

- **Resolution:** 1920x1080 (16:9 aspect ratio)
- **Duration:** 300 seconds (5 minutes)
- **Frame Rate:** 30 fps
- **Video Codec:** h264 with yuv420p pixel format
- **Audio Codec:** AAC at 44.1 kHz, stereo
- **Estimated File Size:** ~25 MB

## Integration with CI/CD

The golden fixtures are used in:

1. **Regression Tests** - Verify that analyzer output hasn't changed unexpectedly
2. **Performance Baselines** - Track processing duration (should be ~15.3 seconds)
3. **Quality Benchmarks** - Ensure quality scores remain within expected ranges
4. **Integration Tests** - Validate end-to-end analyzer pipeline

## Adding New Fixtures

If you need to add new golden fixtures:

1. Generate the synthetic video (or use an existing test video)
2. Run the SWS analyzer on it
3. Save the 11 JSON outputs to `expected_outputs/`
4. Run `regenerate_fixtures.sh` to compute and store reference hashes
5. Commit both the outputs and hashes to version control

## Troubleshooting

### "Hash mismatch" errors

If fixture regeneration fails hash verification:

1. Check that the deterministic seed is set to 42
2. Verify that all timestamps are fixed to 2026-04-17T00:00:00Z
3. Ensure no random functions are called (use seeded RNG only)
4. Regenerate all fixtures: `bash regenerate_fixtures.sh`

### "Missing expected_outputs" errors

If the expected_outputs directory is missing:

```bash
bash regenerate_fixtures.sh  # This will create all files
```

## Reference

- **Created:** 2026-04-17
- **Last Updated:** 2026-04-17
- **SWS Analyzer Version:** v1.0
- **Python Version:** 3.10+
