# BigQuery Export - Database Analysis Services

## Overview

The BigQuery Export integration now includes powerful diagnostic services that help you understand your data, identify gaps, and plan backfills.

## Services

### 1. `bigquery_export.check_database_retention`

**Purpose:** Check how much data is in your local Home Assistant database.

**Parameters:** None

**Returns:**
- `sensor.recorder_oldest_data` - Oldest date in database
- `sensor.recorder_newest_data` - Newest date in database
- `sensor.recorder_days_of_data` - Total days of data retained
- Persistent notification with summary

**Example:**
```yaml
service: bigquery_export.check_database_retention
```

**Use Case:** "How far back does my local database go?"

---

### 2. `bigquery_export.analyze_export_status`

**Purpose:** Compare local database vs BigQuery to see what's been exported and what gaps exist.

**Parameters:** None

**Returns:** Persistent notification with:
- Local database date range and record count
- BigQuery date range and record count
- Coverage percentage
- Gaps before/after BigQuery data
- Whether backfill is possible

**Example:**
```yaml
service: bigquery_export.analyze_export_status
```

**Sample Output:**
```
## Local Database
- Range: 2025-01-01 to 2025-11-28
- Days: 332
- Records: 15,234,567

## BigQuery
- Range: 2025-03-16 to 2025-11-28
- Days: 257
- Records: 12,456,789

## Coverage
- Coverage: 77.4%
- Gap Before: 74 days (Jan 1 - Mar 15)
- Gap After: 0 days
- Can Backfill: ✅ Yes
```

**Use Case:** "What's missing from BigQuery that I still have locally?"

---

### 3. `bigquery_export.find_data_gaps`

**Purpose:** Identify specific date ranges where local database has data but BigQuery doesn't.

**Parameters:**
- `min_gap_hours` (optional, default: 4) - Minimum gap size to report

**Returns:** Persistent notification listing each gap with:
- Type (before/after BigQuery data)
- Date range
- Days of missing data
- Estimated record count

**Example:**
```yaml
service: bigquery_export.find_data_gaps
data:
  min_gap_hours: 24  # Only show gaps >= 1 day
```

**Sample Output:**
```
## Found 1 Data Gap(s)

### Gap 1 (before)
- Range: 2025-01-01 to 2025-03-15
- Days: 74
- Estimated Records: 2,778,901

💡 Use bigquery_export.estimate_backfill to estimate cost/time.
```

**Use Case:** "Show me exactly what date ranges I need to backfill."

---

### 4. `bigquery_export.estimate_backfill`

**Purpose:** Estimate the cost, time, and size of a backfill operation before you run it.

**Parameters:**
- `start_date` (required) - Start date in YYYY-MM-DD format
- `end_date` (required) - End date in YYYY-MM-DD format

**Returns:** Persistent notification with:
- Total records to export
- Unique entities involved
- Estimated processing time
- BigQuery storage size and costs
- Recommended chunk size for export

**Example:**
```yaml
service: bigquery_export.estimate_backfill
data:
  start_date: "2025-01-01"
  end_date: "2025-03-15"
```

**Sample Output:**
```
## Backfill Estimate
Date Range: 2025-01-01 to 2025-03-15

### Data Volume
- Total Records: 2,778,901
- Unique Entities: 347
- Days of Data: 74

### Processing Time
- Estimated Time: 4.6 hours (277.9 min)
- Recommended Chunk Size: 7 days

### BigQuery Costs
- Storage Size: 2.653 GB
- One-Time Storage Cost: $0.0531
- Monthly Query Cost (est): $0.0013

💡 Run backfill using bigquery_export.manual_export with date range.
```

**Use Case:** "How much will it cost and how long will it take to backfill January-March?"

---

## Workflow: Complete Backfill Process

### Step 1: Check Local Database Retention
```yaml
service: bigquery_export.check_database_retention
```

**Result:** "I have data back to Jan 1, 2025"

### Step 2: Analyze Export Status
```yaml
service: bigquery_export.analyze_export_status
```

**Result:** "BigQuery only has data since Mar 16. I'm missing 74 days."

### Step 3: Find Specific Gaps
```yaml
service: bigquery_export.find_data_gaps
```

**Result:** "Gap from Jan 1 - Mar 15 with ~2.8M records"

### Step 4: Estimate Backfill Cost
```yaml
service: bigquery_export.estimate_backfill
data:
  start_date: "2025-01-01"
  end_date: "2025-03-15"
```

**Result:** "Will take 4.6 hours, cost $0.05 storage, recommended 7-day chunks"

### Step 5: Run Backfill
```yaml
# Option A: Manual single export (for small gaps)
service: bigquery_export.manual_export
data:
  start_time: "2025-01-01T00:00:00"
  end_time: "2025-03-15T23:59:59"
  use_bulk_upload: true

# Option B: Chunked export (recommended for large gaps)
service: bigquery_export.manual_export
data:
  start_time: "2025-01-01T00:00:00"
  end_time: "2025-01-07T23:59:59"
  use_bulk_upload: true

# Repeat for each 7-day chunk...
```

---

## Use Cases

### Use Case 1: "Just installed integration, want to backfill everything"
1. `check_database_retention` - See what's available locally
2. `analyze_export_status` - See that 0% is exported
3. `estimate_backfill` - Estimate full backfill cost
4. Run `manual_export` in weekly chunks

### Use Case 2: "Integration was offline for 2 weeks, need to catch up"
1. `find_data_gaps` - Identify the 2-week gap
2. `estimate_backfill` - Estimate cost/time for gap
3. Run `manual_export` for the gap period

### Use Case 3: "Want to know my data coverage before purge"
1. `analyze_export_status` - See coverage %
2. Decision: If coverage < 100%, run backfill before purge

### Use Case 4: "Planning to reduce retention, want to archive first"
1. `check_database_retention` - See current retention (e.g., 120 days)
2. `analyze_export_status` - See BigQuery only has 90 days
3. `estimate_backfill` - Estimate archiving last 30 days
4. Run backfill, then reduce `purge_keep_days`

---

## Technical Details

### Database Access
- Uses Home Assistant's recorder instance
- Queries local MariaDB/PostgreSQL/SQLite via SQLAlchemy
- Queries BigQuery via google-cloud-bigquery client
- All queries run in executor to avoid blocking

### Performance
- Queries are optimized with MIN/MAX/COUNT aggregations
- Date-based filtering uses indexes
- Large result sets are paginated
- Estimates assume ~1KB per record (conservative)

### Cost Calculations
- **Storage:** $0.02/GB/month (BigQuery active storage)
- **Queries:** $5/TB scanned (assumes 10% scan rate)
- **Streaming Inserts:** Free with bulk upload mode
- Estimates are conservative; actual costs typically lower

### Limitations
- Gap detection only finds before/after gaps (not middle gaps)
- Record counts are estimates based on states table only
- Processing time estimates assume 10K records/minute
- Cost estimates don't include network egress (usually negligible)

---

## Troubleshooting

### "Recorder instance not available"
- Ensure Home Assistant recorder is enabled
- Check `configuration.yaml` has `recorder:` section
- Restart Home Assistant

### "BigQuery client not initialized"
- Ensure BigQuery Export integration is configured
- Check service account key is valid
- Restart integration from Integrations page

### "Query returned no results"
- Local database might be empty
- BigQuery table might not exist
- Check entity filtering settings

### Estimate seems wrong
- Record size varies by entity type
- Estimates assume 1KB/record average
- Use actual export to get precise metrics

---

## Best Practices

1. **Always estimate before backfilling** - Prevents surprises
2. **Use chunked exports for >100K records** - Better error handling
3. **Run during off-peak hours** - Reduces HA load
4. **Monitor the first chunk** - Validates estimates
5. **Check data after backfill** - Use `analyze_export_status` to verify

---

## Future Enhancements

Potential additions:
- Middle gap detection (HA downtime periods)
- Entity-level gap analysis
- Automatic backfill scheduling
- Progress tracking for multi-chunk backfills
- Data quality validation post-backfill
- Export compression options
- Incremental deduplication

---

## Related Documentation

- Main README: `/Users/tbailey/Dev/ha-bigquery-export/README.md`
- Reporting Guide: `REPORTING_DEPLOYMENT_GUIDE.md`
- Label Strategy: `LABEL_BASED_REPORTING_STRATEGY.md`

---

**Created:** 2025-11-28
**Version:** 1.0.0
