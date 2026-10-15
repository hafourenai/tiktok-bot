# PDF to DOCX Conversion - Implementation Summary

## Problem
Original converter menggunakan screenshot approach (mupdf) untuk PDF→DOCX, sehingga hasil Word tidak bisa diedit.

## Solution
Created custom handler `pdfToDocx` yang:
1. Extract text dari PDF menggunakan `pdfjs-dist`
2. Preserve struktur dokumen (paragraf, heading, page breaks)
3. Generate editable DOCX menggunakan `docx` library
4. Full text-based conversion (bukan screenshot)

## Implementation

### Files Added/Modified

#### New File: `src/handlers/pdfToDocx.ts`
```typescript
class pdfToDocxHandler implements FormatHandler {
  - name: "pdfToDocx"
  - Supports: PDF (input) → DOCX (output)
  - doConvert(): Extract text, preserve structure, generate DOCX
}
```

**Key Features:**
- Extracts text from all pages
- Groups text into lines based on Y-coordinate proximity
- Auto-detects headings (large font, short text)
- Adds page breaks between pages
- Maintains spacing and formatting

#### Modified File: `src/handlers/index.ts`
- Added `pdfToDocx: []` to HANDLERS object
- Handler automatically loaded via dynamic import

#### Modified File: `package.json`
- Added dependency: `"docx": "^8.5.0"`

## Dependencies

### Existing
- `pdfjs-dist: 5.4.296` - PDF text extraction

### New
- `docx: ^8.5.0` - DOCX generation

## How It Works

1. **PDF Loading**
   ```typescript
   const pdf = await getDocument({ data: inputFile.bytes }).promise;
   ```

2. **Text Extraction Per Page**
   ```typescript
   for (let i = 1; i <= pdf.numPages; i++) {
     const page = await pdf.getPage(i);
     const textContent = await page.getTextContent();
   }
   ```

3. **Line Detection** (based on Y-coordinate)
   - Groups text items that are close vertically
   - Handles multi-line paragraphs correctly

4. **Heading Detection** (heuristic)
   - Font size > 14pt → Heading
   - Text ends with ":" → Heading
   - Short lines (< 80 chars) at top → Heading

5. **DOCX Generation**
   ```typescript
   const doc = new Document({
     sections: [{
       children: paragraphs
     }]
   });
   const buffer = await Packer.toBuffer(doc);
   ```

## Output Quality

### Advantages
✅ Text fully editable in Word/LibreOffice
✅ Paragraphs preserved (not screenshot)
✅ Heading detection
✅ Page breaks maintained
✅ Spacing preserved
✅ Small file size

### Limitations
⚠️ Complex layouts may lose positioning
⚠️ Images removed (text only)
⚠️ Tables flattened to text
⚠️ Formatting (bold, italic) not detected
⚠️ Columns merged into single column

## Routing Priority

Handler automatically integrated into conversion graph:
- System finds PDF→DOCX path
- Prefers `pdfToDocx` handler (direct, high quality)
- Falls back to other handlers if needed

Cost calculation:
- Direct conversion: Lower cost (preferred)
- Other routes: Higher cost (avoided)

## Testing

### Local Test
```bash
cd converter-web
bun install  # Install docx dependency
bun run dev
# Upload PDF → Select DOCX → Convert
# Open result in Word → Text should be editable
```

### Expected Result
- Word document with extracted text
- Paragraphs properly formatted
- No screenshot/image fallback
- Editable content

## Deployment

When deploying to Vercel:
1. `bun install` automatically runs
2. `docx` package installed
3. Handler ready immediately

No additional configuration needed.

## Future Improvements

Optional enhancements:
- [ ] Better heading detection (ML-based)
- [ ] Table structure preservation
- [ ] Font styling (bold, italic, color)
- [ ] Image embedding
- [ ] List detection
- [ ] Maintain text direction (RTL support)

## Troubleshooting

### "Cannot find module 'docx'"
- Run `bun install` to ensure dependencies are installed
- Check package.json has `"docx": "^8.5.0"`

### Result is empty
- PDF might be image-based (scanned)
- OCR needed (beyond scope of this implementation)

### Text is jumbled
- Complex PDF layout not fully extracted
- Consider alternative: PDF→Text→DOCX

### Large file sizes
- PDF has many pages
- Normal behavior (text-based is still smaller than images)

---

**Status**: ✅ Ready for deployment
**Modified Files**: 2
**New Files**: 1
**Dependencies Added**: 1
