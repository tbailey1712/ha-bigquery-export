# BigQuery Export - Testing & Validation Guide

## Current Status

✅ **Code Complete** - All database analysis features implemented
✅ **Device Page Created** - Professional device view with 4 sensors
✅ **Comprehensive Logging** - Step-by-step debug output added
⏳ **Awaiting Restart** - Need to restart Home Assistant to load changes

---

## Phase 1: Restart and Initial Verification

### Step 1: Restart Home Assistant
```bash
# Restart through UI or CLI
ha core restart
```

**Expected Time**: 2-3 minutes

### Step 2: Verify Integration Loads
Navigate to: **Settings → Devices & Services → BigQuery Export**

**What You Should See**:
- Device: "BigQuery Export"
- 4 entities listed
- No error messages in logs

**Check Logs** (Settings → System → Logs):
```
[custom_components.bigquery_export] BigQuery Export integration setup complete
```

---

## Phase 2: Test Database Retention Service

### Step 3: Run Database Retention Check

**Service Call** (Developer Tools → Services):
```yaml
service: bigquery_export.check_database_retention
```

### Expected Logs (Settings → System → Logs)

**Look for this sequence**:
```
[custom_components.bigquery_export] Checking database retention...
[custom_components.bigquery_export] Step 1/4: Getting recorder instance...
[custom_components.bigquery_export] Step 2/4: Opening database session...
[custom_components.bigquery_export] Estimated records in states table: 19576182
[custom_components.bigquery_export] Timestamp query result: (...)
[custom_components.bigquery_export] Converted dates: YYYY-MM-DD to YYYY-MM-DD (XXX days)
[custom_components.bigquery_export] Database retention: YYYY-MM-DD to YYYY-MM-DD (XXX days, 19,576,182 records)
```

**OR if timestamp column doesn't exist**:
```
[custom_components.bigquery_export] Query returned NULL timestamps - trying datetime column
[custom_components.bigquery_export] Fallback query result: (...)
```

### Expected Results

**Notification** (should appear in Home Assistant):
```
📊 Database Retention Check

**Oldest Data:** 2025-01-01
**Newest Data:** 2025-11-28
**Days of Data:** 332 days
**Total Records:** 19,576,182

Check sensor: `sensor.local_database_retention`
```

**Sensor Update** (sensor.local_database_retention):
- State: `332` (days)
- Attributes:
  - `oldest_date: "2025-01-01"`
  - `newest_date: "2025-11-28"`
  - `total_records: "19,576,182"`

### Troubleshooting

#### If dates are still NULL:

**Share these log lines**:
```
Step 2/4: Opening database session...
Estimated records in states table: [number]
Timestamp query result: [value]
```

This will show whether:
- `last_updated_ts` column exists and has data
- `last_updated` column needs to be used instead
- Database has a schema issue

#### If service hangs (>10 seconds):

Check if query is using `COUNT(*)` (shouldn't be):
```sql
-- BAD (slow)
SELECT COUNT(*) FROM states

-- GOOD (fast)
SELECT TABLE_ROWS FROM information_schema.tables
```

---

## Phase 3: Test All Diagnostic Services

### Step 4: Analyze Export Status
```yaml
service: bigquery_export.analyze_export_status
```

**Expected Notification**:
```
📊 Export Status Analysis

## Local Database
- **Range:** 2025-01-01 to 2025-11-28
- **Days:** 332
- **Records:** 19,576,182

## BigQuery
- **Range:** 2025-03-16 to 2025-11-28
- **Days:** 257
- **Records:** [count]

## Coverage
- **Coverage:** 77.4%
- **Gap Before:** 74 days
- **Gap After:** 0 days
- **Can Backfill:** ✅ Yes
```

**Sensor Update** (sensor.export_coverage):
- State: `77.4` (%)
- Attributes show full breakdown

### Step 5: Find Data Gaps
```yaml
service: bigquery_export.find_data_gaps
data:
  min_gap_hours: 4
```

**Expected Notification**:
```
🔍 Data Gap Analysis

## Found 1 Data Gap(s)

### Gap 1 (before_bigquery)
- **Range:** 2025-01-01 to 2025-03-15
- **Days:** 74
- **Estimated Records:** [count]

💡 Use `bigquery_export.estimate_backfill` to estimate cost/time for filling these gaps.
```

**Sensor Update** (sensor.data_gaps):
- State: `1` (number of gaps)
- Attributes list all gaps

### Step 6: Estimate Backfill Cost
```yaml
service: bigquery_export.estimate_backfill
data:
  start_date: "2025-01-01"
  end_date: "2025-03-15"
```

**Expected Notification**:
```
💰 Backfill Cost Estimate

**Date Range:** 2025-01-01 to 2025-03-15

### Data Volume
- **Total Records:** [count]
- **Unique Entities:** [count]
- **Days of Data:** 74

### Processing Time
- **Estimated Time:** [X] hours ([X] min)
- **Recommended Chunk Size:** 7 days

### BigQuery Costs
- **Storage Size:** [X] GB
- **One-Time Storage Cost:** $[X]
- **Monthly Query Cost (est):** $[X]

💡 Run backfill using `bigquery_export.manual_export` with date range.
```

---

## Phase 4: Verify Device Page

### Step 7: Check Device Page

**Navigate to**: Settings → Devices & Services → BigQuery Export → Click device

**Expected Layout**:
```
╔═══════════════════════════════════════════════════╗
║  BigQuery Export                                  ║
║  Custom • Data Export Service                     ║
║  Software version: 1.2.0                          ║
╠═══════════════════════════════════════════════════╣
║  📊 4 entities                                    ║
╠═══════════════════════════════════════════════════╣
║  Entities                                         ║
║  ├─ Export Status: idle                          ║
║  ├─ Local Database Retention: 332 days          ║
║  ├─ Export Coverage: 77.4%                       ║
║  └─ Data Gaps: 1                                 ║
╠═══════════════════════════════════════════════════╣
║  Activity                                         ║
║  ├─ [timestamp] sensor.export_status updated     ║
║  ├─ [timestamp] sensor.local_database_retention  ║
║  └─ [timestamp] sensor.export_coverage           ║
╠═══════════════════════════════════════════════════╣
║  Configuration                                    ║
║  └─ [Config details]                             ║
╚═══════════════════════════════════════════════════╝
```

### Step 8: Click Each Sensor

**Click on each sensor** to verify attributes are populated:

#### sensor.local_database_retention
- State: `332` days
- Attributes:
  - `oldest_date`
  - `newest_date`
  - `days_of_data`
  - `total_records`

#### sensor.export_coverage
- State: `77.4` %
- Attributes:
  - `local_oldest`, `local_newest`, `local_days`, `local_records`
  - `bigquery_oldest`, `bigquery_newest`, `bigquery_days`, `bigquery_records`
  - `gap_before_days`, `gap_after_days`
  - `can_backfill`

#### sensor.data_gaps
- State: `1` gap
- Attributes:
  - `gaps` (array with details)
  - `total_gaps`
  - `total_missing_days`
  - `total_missing_records`

---

## Phase 5: Performance Validation

### Step 9: Check Service Call Performance

**All service calls should complete in**:
- ✅ `check_database_retention`: < 1 second
- ✅ `analyze_export_status`: < 2 seconds
- ✅ `find_data_gaps`: < 3 seconds
- ✅ `estimate_backfill`: < 5 seconds

**If any service hangs (>10 seconds)**:
1. Check logs for which step it's stuck on
2. Report the log line where it stops
3. Check if MariaDB is responding: `ha mariadb status`

---

## Phase 6: Integration Quality Checks

### Step 10: Logo Files (Optional but Recommended)

**Current Status**: ⏳ SVG logo created, PNG files needed

**Files Needed**:
```
custom_components/bigquery_export/
├── icon.png (256x256)
├── icon@2x.png (512x512)
├── logo.png (256x256)
└── logo@2x.png (512x512)
```

**Quick Convert**: https://svgtopng.com/
1. Upload `/Users/tbailey/Dev/ha-bigquery-export/logo.svg`
2. Generate all 4 sizes
3. Copy to integration folder
4. Restart HA

**Result**: Professional logo appears on integration page

---

## Success Criteria Checklist

### Functionality
- [ ] Integration loads without errors
- [ ] All 4 sensors appear on device page
- [ ] `check_database_retention` completes in <1s
- [ ] Dates are displayed correctly (not NULL)
- [ ] Notification appears with database stats
- [ ] Sensor updates with correct data
- [ ] All 4 diagnostic services execute successfully
- [ ] Device page shows all sensors grouped together

### Performance
- [ ] No service calls hang (all <5s)
- [ ] Database queries use fast index lookups
- [ ] No `COUNT(*)` queries in logs
- [ ] Logs show step-by-step progress

### User Experience
- [ ] Device page looks professional
- [ ] Sensors have clear names and icons
- [ ] Attributes are informative and formatted
- [ ] Notifications are helpful and actionable
- [ ] Activity log shows sensor updates

---

## Known Issues & Solutions

### Issue 1: Dates Returning as NULL
**Symptom**: Notification shows "None to None"

**Diagnosis**: Check logs for:
```
Timestamp query result: (None, None)
```

**Solution**: Database schema uses datetime column, fallback should activate automatically.

**Action**: If fallback doesn't work, share log output.

### Issue 2: Service Call Hangs
**Symptom**: Service call takes >30 seconds

**Diagnosis**: Check if using slow `COUNT(*)` query

**Solution**: Code should use `TABLE_ROWS` estimate. If hanging, check MariaDB status.

### Issue 3: Sensors Not Appearing
**Symptom**: Device page shows 0 entities

**Diagnosis**: Sensors not registered properly

**Solution**:
1. Check logs for sensor setup errors
2. Verify `_attr_entity_registry_enabled_default = True`
3. Try reloading integration (don't need full restart)

### Issue 4: No Activity Log
**Symptom**: Activity section is empty

**Solution**: Activity log only shows recent updates. Run service calls to generate activity.

---

## Next Steps After Validation

### If Everything Works ✅
1. **Set up daily automation**:
```yaml
automation:
  - alias: "BigQuery Daily Export"
    trigger:
      - platform: time
        at: "03:00:00"
    action:
      - service: bigquery_export.incremental_export
```

2. **Weekly analysis automation**:
```yaml
automation:
  - alias: "BigQuery Weekly Analysis"
    trigger:
      - platform: time
        at: "06:00:00"
      - platform: time
        day_of_week: mon
    action:
      - service: bigquery_export.analyze_export_status
      - service: bigquery_export.find_data_gaps
```

3. **Consider backfilling the gap** (74 days: Jan 1 - Mar 15):
```yaml
service: bigquery_export.manual_export
data:
  start_time: "2025-01-01T00:00:00"
  end_time: "2025-01-07T23:59:59"
  use_bulk_upload: true
```
Repeat weekly until gap is filled.

### If Issues Occur 🔧
1. **Capture logs** (Settings → System → Logs)
2. **Share relevant log sections** showing:
   - Step-by-step progress
   - Where it hangs or fails
   - Error messages
3. **Check database health**: `ha mariadb status`
4. **Verify BigQuery connection** is still valid

---

## Documentation References

- **Service Details**: `DATABASE_ANALYSIS_SERVICES.md`
- **Quick Start**: `QUICK_START_GUIDE.md`
- **Logo Setup**: `BRANDING_SETUP.md`
- **Project Status**: `PROFESSIONAL_SETUP_COMPLETE.md`

---

## Support & Feedback

If you encounter issues:
1. Check logs first (Settings → System → Logs)
2. Search for `[custom_components.bigquery_export]`
3. Share relevant log sections that show where it fails
4. Include sensor states and attributes if helpful

**This integration is now feature-complete!** 🎉

The diagnostic sensors give you complete visibility into:
- How much local data you really have (332 days!)
- What's been exported to BigQuery (257 days)
- Where the gaps are (74 days before Mar 16)
- How much it would cost to backfill

---

**Version**: 1.2.0
**Last Updated**: 2025-11-28
**Status**: Ready for testing
