# PDF Form Generation

This directory contains scripts and HTML templates for generating rental application PDFs.

## Quick Start

### Install Dependencies
```bash
cd frontend
npm install
```

### Generate PDFs
```bash
npm run generate-pdfs
```

This will convert all HTML forms in `/public` to PDF format.

## How It Works

1. **HTML Templates**: Forms are created as HTML files in `/frontend/public/`
2. **Puppeteer Script**: The `generate-pdfs.js` script uses Puppeteer (headless Chrome) to render HTML and save as PDF
3. **Output**: PDFs are saved to `/frontend/public/` and can be downloaded by landlords

## Current Forms

- ✅ Nebraska Residential Rental Application (pre-existing PDF)
- ✅ Missouri Residential Rental Application (generated from HTML)

## Adding New Forms

1. Create a new HTML file in `/frontend/public/` (e.g., `Kansas-Rental-Application.html`)
2. Add the form to the `forms` array in `scripts/generate-pdfs.js`:
   ```javascript
   {
     html: 'Kansas-Rental-Application.html',
     pdf: 'Kansas-Rental-Application.pdf'
   }
   ```
3. Run `npm run generate-pdfs`
4. Update the rental application page to include the new download option

## PDF Settings

The script generates PDFs with:
- **Format**: US Letter (8.5" x 11")
- **Margins**: 0.5" on all sides
- **Background**: Enabled (preserves styling)
- **Quality**: High-resolution, print-ready

## Troubleshooting

**Puppeteer installation issues?**
```bash
# macOS/Linux
npm install puppeteer --ignore-scripts=false

# Or use puppeteer-core with system Chrome
npm install puppeteer-core
```

**PDF not generating?**
- Check console for error messages
- Verify HTML file exists in `/public`
- Ensure HTML is valid (no unclosed tags)

**PDF looks wrong?**
- Adjust margins in `generate-pdfs.js`
- Check CSS `@media print` rules in HTML
- Verify page breaks with `.page-break` class

## Manual PDF Generation (Alternative)

If you prefer not to use Puppeteer:

1. Open the HTML file in Chrome
2. Press `Cmd+P` (Mac) or `Ctrl+P` (Windows)
3. Select "Save as PDF"
4. Set margins to "Minimum"
5. Enable "Background graphics"
6. Save to `/frontend/public/`

