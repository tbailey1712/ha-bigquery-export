# BigQuery Export - Branding Setup Guide

## Logo Files Created

### 1. Main Logo (`logo.svg`)
- **Location:** `/Users/tbailey/Dev/ha-bigquery-export/logo.svg`
- **Design:**
  - Blue gradient background (Google Cloud colors)
  - Database cylinder (representing HA data)
  - Export arrow (data flow)
  - BigQuery hexagon with "BQ" text
  - Clean, professional appearance

## Required Image Files for Home Assistant

Home Assistant integrations need specific image files in specific locations:

### Directory Structure
```
custom_components/bigquery_export/
├── icon.png (256x256px)
├── icon@2x.png (512x512px)
├── logo.png (256x256px)
└── logo@2x.png (512x512px)
```

### File Specifications

1. **`icon.png`** - Small icon for integration badge
   - Size: 256x256 pixels
   - Format: PNG with transparency
   - Usage: Integration list, services dropdown

2. **`icon@2x.png`** - Retina/HiDPI icon
   - Size: 512x512 pixels
   - Format: PNG with transparency
   - Usage: High-resolution displays

3. **`logo.png`** - Integration card logo
   - Size: 256x256 pixels
   - Format: PNG (can have background)
   - Usage: Integration configuration page header

4. **`logo@2x.png`** - Retina/HiDPI logo
   - Size: 512x512 pixels
   - Format: PNG (can have background)
   - Usage: High-resolution displays

## How to Generate PNG Files from SVG

### Option 1: Online Converter (Easiest)
1. Go to https://svgtopng.com/ or https://cloudconvert.com/svg-to-png
2. Upload `logo.svg`
3. Generate 4 versions:
   - 256x256 → Save as `icon.png` and `logo.png`
   - 512x512 → Save as `icon@2x.png` and `logo@2x.png`
4. Copy files to `custom_components/bigquery_export/`

### Option 2: Using ImageMagick (If installed)
```bash
cd /Users/tbailey/Dev/ha-bigquery-export

# Generate icon files
magick logo.svg -resize 256x256 custom_components/bigquery_export/icon.png
magick logo.svg -resize 512x512 custom_components/bigquery_export/icon@2x.png

# Generate logo files (same as icon for this integration)
cp custom_components/bigquery_export/icon.png custom_components/bigquery_export/logo.png
cp custom_components/bigquery_export/icon@2x.png custom_components/bigquery_export/logo@2x.png
```

### Option 3: Using Inkscape (If installed)
```bash
# 256x256
inkscape logo.svg --export-type=png --export-width=256 --export-filename=custom_components/bigquery_export/icon.png

# 512x512
inkscape logo.svg --export-type=png --export-width=512 --export-filename=custom_components/bigquery_export/icon@2x.png
```

### Option 4: Using macOS Preview
1. Open `logo.svg` in Preview
2. File → Export
3. Set dimensions to 256x256, save as `icon.png`
4. Repeat for 512x512, save as `icon@2x.png`
5. Copy both files and rename copies to `logo.png` and `logo@2x.png`

## Brand Colors

Use these colors for consistency with the BigQuery Export brand:

- **Primary Blue:** `#4285F4` (Google Blue)
- **Dark Blue:** `#185ABC` (Accent)
- **Warning Orange:** `#FBBC04` (Google Yellow)
- **Error Red:** `#EA4335` (Google Red)
- **Success Green:** `#34A853` (Google Green)
- **White:** `#FFFFFF`
- **Light Gray:** `#E8EAED`

## HACS Additional Branding

For HACS (Home Assistant Community Store), you may also want:

### Repository Images
1. **`hacs_banner.png`** (Optional, 1280x640)
   - Featured image for HACS store
   - Place in repository root

2. **GitHub Social Preview** (1280x640)
   - Settings → Social Preview Image
   - Shows in GitHub repo cards

## Verification

After adding image files, verify they appear correctly:

1. **Restart Home Assistant**
2. **Check Integration Page:**
   - Settings → Devices & Services
   - Look for BigQuery Export logo
3. **Check Developer Tools:**
   - Developer Tools → Services
   - Filter "bigquery_export"
   - Logo should appear next to service names

## Troubleshooting

### Images not showing
- Clear browser cache (Ctrl+Shift+R or Cmd+Shift+R)
- Check file permissions: `chmod 644 *.png`
- Verify file sizes: `ls -lh custom_components/bigquery_export/*.png`
- Check HA logs for image loading errors

### Image quality issues
- Ensure PNG files are not compressed too heavily
- Use 24-bit PNG with alpha channel
- Avoid JPEG artifacts (must be PNG)

## Future Enhancements

Consider creating:
- Animated logo for loading states
- Dark mode variant
- Themed icons for different sensor types
- Dashboard card backgrounds
- Documentation graphics

---

**Next Steps:**
1. ✅ SVG logo created
2. ⏳ Generate PNG files (use Option 1 above)
3. ⏳ Copy PNGs to integration directory
4. ⏳ Restart Home Assistant
5. ⏳ Verify appearance

**Status:** SVG logo complete, awaiting PNG conversion
