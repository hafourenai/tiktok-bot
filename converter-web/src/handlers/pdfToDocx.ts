import type { FileData, FileFormat, FormatHandler } from "../FormatHandler.ts";
import Formats from "src/Formats.ts";
import { changeExt } from "src/common/index.ts";
import { getDocument } from "pdfjs-dist";
import { Document, Packer, Paragraph, TextRun, HeadingLevel } from "docx";

class pdfToDocxHandler implements FormatHandler {
  public readonly name = "pdfToDocx";
  public supportedFormats = [
    Formats.PDF.builder("pdf").lossless().from(),
    Formats.DOCX.builder("docx").lossless().to(),
  ];
  public ready = false;

  async init() {
    this.ready = true;
  }

  async doConvert(
    inputFiles: FileData[],
    inputFormat: FileFormat,
    outputFormat: FileFormat,
  ): Promise<FileData[]> {
    const outputFiles: FileData[] = [];

    for (const inputFile of inputFiles) {
      try {
        // Load PDF document
        const pdf = await getDocument({ data: inputFile.bytes }).promise;
        
        const paragraphs: Paragraph[] = [];
        let pageNum = 1;

        // Extract text from each page
        for (let i = 1; i <= pdf.numPages; i++) {
          const page = await pdf.getPage(i);
          const textContent = await page.getTextContent();

          if (i > 1) {
            // Add page break before each new page (except first)
            paragraphs.push(new Paragraph({ text: "", pageBreakBefore: true }));
          }

          // Group text items by line (y-coordinate proximity)
          const lines: any[][] = [];
          let currentLine: any[] = [];
          let currentY = -1;

          for (const item of textContent.items) {
            if (typeof item === "object" && "transform" in item) {
              const y = item.transform[5];
              
              // If y coordinate changed significantly, start new line
              if (currentY !== -1 && Math.abs(y - currentY) > 5) {
                if (currentLine.length > 0) {
                  lines.push(currentLine);
                  currentLine = [];
                }
              }
              
              currentY = y;
              currentLine.push(item);
            }
          }
          
          if (currentLine.length > 0) {
            lines.push(currentLine);
          }

          // Convert lines to paragraphs
          for (const line of lines) {
            let lineText = "";
            let fontSize = 12;

            for (const item of line) {
              if ("str" in item && typeof item.str === "string") {
                lineText += item.str;
                // Try to detect font size
                if ("height" in item && typeof item.height === "number") {
                  fontSize = Math.round(item.height);
                }
              }
            }

            lineText = lineText.trim();
            if (lineText.length === 0) continue;

            // Detect heading vs normal text (simple heuristic: short lines at start of page might be headings)
            const isLikelyHeading =
              fontSize > 14 || (lineText.length < 80 && lineText.endsWith(":"));

            if (isLikelyHeading && lineText.length > 0) {
              paragraphs.push(
                new Paragraph({
                  text: lineText,
                  heading: HeadingLevel.HEADING_1,
                  spacing: { after: 200 },
                }),
              );
            } else {
              paragraphs.push(
                new Paragraph({
                  text: lineText,
                  spacing: { line: 240, after: 100 },
                }),
              );
            }
          }

          pageNum++;
        }

        // Create DOCX document
        const doc = new Document({
          sections: [
            {
              children: paragraphs,
            },
          ],
        });

        // Convert to bytes
        const buffer = await Packer.toBuffer(doc);
        const bytes = new Uint8Array(buffer);

        outputFiles.push({
          name: changeExt(inputFile.name, outputFormat.extension),
          bytes,
        });
      } catch (error) {
        console.error(`Failed to convert PDF to DOCX: ${error}`);
        throw new Error(`PDF to DOCX conversion failed: ${error}`);
      }
    }

    return outputFiles;
  }
}

export default pdfToDocxHandler;
