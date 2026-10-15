import type { FileData, FileFormat, FormatHandler } from "../FormatHandler.ts";
import * as Pe from "pe-library";
import JSZip from "jszip";

import { Buffer } from "buffer";
import Formats from "src/Formats.ts";
import { changeExt } from "src/common/index.ts";
if (typeof window !== "undefined") {
  (window as any).Buffer = Buffer;
}

class peToZipHandler implements FormatHandler {
  public readonly name = "peToZip";
  public supportedFormats = [
    Formats.EXE.builder("exe").from(),
    Formats.DLL.builder("dll").from(),
    Formats.ZIP.builder("zip").lossless().to(),
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
    if (outputFormat.format !== "zip") {
      throw new TypeError(
        `Unsupported output format of ${outputFormat.format}. Only ZIP is supported.`,
      );
    }

    const outputFiles: FileData[] = [];

    for (const inputFile of inputFiles) {
      try {
        //initialize JSzip + buffer
        const zip = new JSZip();
        const buffer = Buffer.from(inputFile.bytes as Uint8Array);

        // Get metadata from PE headers
        //@ts-ignore
        const peFile = Pe.NtExecutable.from(buffer);
        const ntHeader = peFile.newHeader;

        const subsystemValue = ntHeader.optionalHeader.subsystem;
        const subsystemMap: Record<number, string> = {
          1: "Native",
          2: "Windows GUI",
          3: "Windows Console",
          7: "POSIX",
          9: "Windows CE",
          10: "EFI Application",
        };

        const metadata = {
          originalFileName: inputFile.name,
          architecture: peFile.is32bit() ? "x86 (32-bit)" : "x64 (64-bit)",
          compileTimestamp: new Date(ntHeader.fileHeader.timeDateStamp * 1000).toISOString(),
          subsystem: subsystemMap[subsystemValue] || `Unknown (${subsystemValue})`,
          imageBase: peFile.getImageBase(),
          sectionAlignment: peFile.getSectionAlignment(),
          imports: [] as any[],
          exports: [] as any[],
        };

        zip.file("metadata.json", JSON.stringify(metadata, null, 2));

        // Extract binary
        const allSections = peFile.getAllSections();

        for (const section of allSections) {
          const rawName = section.info.name.toString().replace(/\0/g, "");
          const safeName = rawName.replace(/[^a-zA-Z0-9]/g, "");
          const fileName = `section_${safeName || "unnamed"}.bin`;

          if (section.data) {
            zip.file(fileName, section.data);
          }
        }

        // generate final ZIP
        const outputBytes = await zip.generateAsync({
          type: "uint8array",
          compression: "DEFLATE",
          compressionOptions: { level: 9 },
        });

        const newName = changeExt(inputFile.name, "zip", "_pe_data");

        outputFiles.push({
          bytes: outputBytes,
          name: newName,
        });
      } catch (e: any) {
        // error handling
        console.error(`[petozip] Error converting ${inputFile.name}:`, e);
        throw new Error(`Failed to process PE file ${inputFile.name}: ${e.message}`, { cause: e });
      }
    }

    return outputFiles;
  }
}

export default peToZipHandler;
