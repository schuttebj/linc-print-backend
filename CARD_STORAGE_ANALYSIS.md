# Madagascar License Card Storage Analysis

## File Size Calculations

### Card Specifications
- **Dimensions**: 1012 × 638 pixels (85.6mm × 54mm)
- **Resolution**: 300 DPI (professional print quality)
- **Color Depth**: 24-bit RGB (full color)

### Individual File Size Estimates

#### PNG Images (Front & Back)
- **Uncompressed Size**: 1012 × 638 × 3 bytes = 1,935,048 bytes (≈1.9 MB)
- **PNG Compression**: ~70% compression for mixed graphics/text content
- **Estimated Size per PNG**: ~500 KB

#### PDF Files
- **Front PDF**: PNG image + PDF overhead ≈ 550 KB
- **Back PDF**: PNG image + PDF overhead ≈ 550 KB  
- **Combined PDF**: Both images + PDF overhead ≈ 1.1 MB

### Complete Card File Set (per print job)
```
Front PNG:     500 KB
Back PNG:      500 KB
Front PDF:     550 KB
Back PDF:      550 KB
Combined PDF:  1,100 KB
─────────────────────
TOTAL:         3,200 KB (3.2 MB)
```

## Annual Storage Requirements

### Scenario: 150,000 Transactions/Year

#### Option A: Keep All Files Permanently
```
3.2 MB × 150,000 = 480,000 MB = 480 GB per year
```

**Multi-year projection:**
- Year 1: 480 GB
- Year 3: 1.44 TB  
- Year 5: 2.4 TB
- Year 10: 4.8 TB

#### Option B: Hybrid Approach (Recommended)
**Keep files only until collection, then delete**

**Assumptions:**
- Average time from print to collection: 30 days
- Collection rate: 95% (5% never collected)
- Peak storage = files for 30-day period

**Calculation:**
```
Daily transactions: 150,000 ÷ 365 = ~411 per day
30-day storage: 411 × 30 × 3.2 MB = 39.4 GB
+ 5% uncollected (permanent): 24 GB per year
─────────────────────────────────────────────
Peak Storage Need: ~40 GB (steady state)
Annual Growth: ~24 GB (uncollected files)
```

#### Option C: Temporary Storage Only
**Delete files after 90 days regardless of collection**

```
90-day storage: 411 × 90 × 3.2 MB = 118 GB (steady state)
No permanent growth (all files deleted after 90 days)
```

## Storage Comparison

| Approach | Year 1 | Year 3 | Year 5 | Steady State |
|----------|--------|--------|--------|--------------|
| **Keep All** | 480 GB | 1.44 TB | 2.4 TB | Grows forever |
| **Hybrid (30-day)** | 64 GB | 112 GB | 160 GB | ~40 GB + uncollected |
| **Temporary (90-day)** | 118 GB | 118 GB | 118 GB | 118 GB (constant) |

## Recommendations

### Option B: Hybrid Approach (Recommended)
**Pros:**
- ✅ Manageable storage growth (~24 GB/year)
- ✅ Files available during collection period
- ✅ Good performance for active cards
- ✅ Automatic cleanup reduces maintenance

**Implementation:**
1. Store files during print → collection workflow
2. Delete files when card status = "COLLECTED"
3. Keep database record but remove file references
4. Handle uncollected cards after 90 days

### Storage Optimization Strategies

#### 1. Compression Improvements
- **JPEG for images**: Reduce to ~200-300 KB per image (-40%)
- **PDF compression**: Optimize PDF generation (-20%)
- **Potential savings**: 40-50% size reduction = ~1.8 MB per card

#### 2. Progressive Deletion
```
Print Job States → File Actions:
├── QUEUED → COMPLETED: Keep all files
├── COLLECTED: Delete files, keep metadata
├── 90+ days uncollected: Delete files + clean DB
└── 365+ days: Archive job record only
```

#### 3. Efficient File Organization
```
/var/madagascar-license-data/cards/
├── active/           # Current print jobs (< 30 days)
│   └── YYYY/MM/DD/job_id/
├── ready/           # Ready for collection (30-90 days)  
│   └── YYYY/MM/DD/job_id/
└── archive/         # Long-term storage (uncollected)
    └── YYYY/job_id/
```

## Implementation Plan

### Phase 1: Hybrid Storage Setup
1. **File Storage Service**: Create card file manager similar to biometric files
2. **Lifecycle Management**: Implement file cleanup on status changes
3. **Database Updates**: Add file cleanup tracking

### Phase 2: Optimization
1. **Compression**: Implement JPEG for images, optimized PDFs
2. **Monitoring**: Add storage usage tracking
3. **Cleanup Automation**: Scheduled cleanup jobs

### Phase 3: Advanced Features  
1. **Archival**: Long-term compressed storage for uncollected
2. **Analytics**: Storage usage reporting
3. **Backup**: Selective backup strategies

## Cost Analysis (Cloud Storage)

### Current Render.com Persistent Disk
- **Current**: 10 GB disk
- **Hybrid approach need**: 50-100 GB disk
- **Cost impact**: Minimal for additional storage

### Storage Efficiency
- **Database**: Keeps essential metadata only
- **Files**: Stored only when needed
- **Cleanup**: Automatic and rule-based
- **Performance**: Fast for active cards, efficient for archives

## Conclusion

The **Hybrid Approach** provides the optimal balance of:
- Performance for active print jobs
- Reasonable storage requirements  
- Automatic cleanup to prevent bloat
- Flexibility for different collection patterns

**Recommended Storage**: Start with 100 GB disk, monitor growth patterns. 