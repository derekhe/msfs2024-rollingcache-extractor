# MSFS2024 RollingCache Analysis Project - Final Simplified Version

## Project Overview
Successfully reverse-engineered the MSFS2024 RollingCache (.CCC) file format and developed simplified image extraction tools, extracting 4,196 high-quality 256x256 pixel JPEG satellite images from the cache.

## Final Toolchain

### Core Tools
- **`jpeg_extractor.py`** - Simplified JPEG Satellite Image Extractor
  - Focused on core extraction functionality, no quality classification
  - Single directory output with clear file naming
  - Successfully extracted 4,196 satellite images

- **`satellite_image_analyzer.py`** - Comprehensive Satellite Image Detector
  - Supports multiple format detection (JPEG, BC compression, RAW)
  - Provides detailed statistical analysis

- **`rolling_cache_analyzer.py`** - RollingCache File Structure Analyzer
  - Analyzes basic structure and statistics of cache files

- **`verify_samples.py`** - Sample Validation Tool
  - Validates quality of extracted image samples

### Technical Documentation (Updated to Final Version)
- **`RollingCache_技术文档.md`** - Complete Technical Documentation
- **`快速入门指南.md`** - Quick Start Guide  
- **`技术规格说明.md`** - Detailed Technical Specifications

### Test Data
- **`ROLLINGCACHE-*.CCC`** - Test cache files
- **`extracted_jpegs/`** - Extracted JPEG images directory

## Final Project Results

✅ **Completely Parsed MSFS2024 RollingCache Format**
- 16GB sparse storage with 1MB blocks at 4MB intervals
- Magic number: 0x00000012
- 48-byte header with dual checksum system

✅ **Successfully Extracted 4,196 Satellite Images**
- All 256x256 pixel JPEG format
- File size range: 834 bytes - 66KB
- Average file size: 50KB
- Total size ~200MB

✅ **Developed Simplified Toolchain**
- Removed quality classification functionality, focused on core extraction
- Single directory output with clear file naming
- Processing time only 12 seconds

✅ **Created Complete Technical Documentation**
- File format specifications
- Extraction algorithm descriptions
- Simplified tool usage guides

## Usage

### Quick Extract All Images
```bash
python jpeg_extractor.py ROLLINGCACHE-some-content.CCC
```

### Analysis Only (No Extraction)
```bash
python jpeg_extractor.py --analyze-only ROLLINGCACHE-some-content.CCC
```

### Specify Output Directory
```bash
python jpeg_extractor.py --output-dir my_images ROLLINGCACHE-some-content.CCC
```

## Output Results

Simplified single directory output structure:
```
extracted_jpegs/
├── satellite_0001_256x256_0x1a2b3c4d.jpg
├── satellite_0002_256x256_0x2b3c4d5e.jpg
├── satellite_0003_256x256_0x3c4d5e6f.jpg
└── ... (4,196 images total)
```

## Technical Features
- **Memory Mapping**: Efficient processing of 16GB large files
- **Smart JPEG Detection**: FF D8 FF signature recognition + SOF parsing
- **Simplified Design**: Focused on core functionality, no complex classification
- **Fault Tolerance**: Smart boundary detection and error recovery

## Project Cleanup History
To ensure the final version's simplicity, the following experimental content has been removed:
- ❌ Rust-related files (Cargo.toml, src/, target/, etc.)
- ❌ Experimental Python scripts (20+ files)
- ❌ Quality classification functionality and related code
- ❌ Intermediate results and temporary sample directories
- ✅ Kept final correct simplified tools

## File Format Analysis

### RollingCache Structure
- **File Extension**: `.CCC`
- **File Size**: ~16GB (17,179,869,184 bytes)
- **Storage Type**: Sparse file with pre-allocated space
- **Data Organization**: 1MB data blocks at 4MB intervals

### Header Structure (48 bytes)
```c
struct RollingCacheHeader {
    uint32_t magic;          // 0x00: Magic number (0x12)
    uint32_t header_size;    // 0x04: Header size (48)
    uint32_t version;        // 0x08: File version
    uint32_t block_size;     // 0x0C: Block size (1MB)
    uint32_t block_count;    // 0x10: Total blocks
    uint32_t used_blocks;    // 0x14: Used blocks
    uint32_t checksum1;      // 0x18: Primary checksum
    uint32_t checksum2;      // 0x1C: Secondary checksum
    uint64_t reserved;       // 0x20: Reserved field
    uint64_t timestamp;      // 0x28: Creation timestamp
};
```

## Performance Metrics

### Processing Performance
```
File Size: 16 GB (sparse storage)
Effective Data: ~4 GB (25% utilization)
Data Blocks: 4,096 blocks (1MB each)
Processing Time: 11.56 seconds

Image Statistics:
├── JPEG Images: 4,196 images
├── Image Size: 256x256 pixels
├── File Size Range: 834B - 66,782B
├── Average Size: 50,681 bytes
└── Total Extracted: ~200 MB
```

## Requirements

### System Requirements
- Python 3.8+
- At least 4GB available RAM
- 1GB+ free disk space for output

### Dependencies
```bash
pip install pillow
```

## Legal Notice

The file format analysis and extraction methods described in this project are for educational and research purposes only. The extracted image content is copyrighted by Microsoft Corporation. Please comply with relevant software license agreements and legal regulations.

---
**Project Status**: Complete - Simplified tools running normally, documentation updated

**Last Updated**: August 12, 2025
