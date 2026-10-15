import Formats from "src/Formats.ts";
import type { FileData, FileFormat, FormatHandler } from "../FormatHandler.ts";
import type { HandlerName } from "./index.ts";
import { changeExt } from "src/common/index.ts";

function createRenameHandler(name: HandlerName, formats: FileFormat[]) {
  return class implements FormatHandler {
    public readonly name = name;
    public supportedFormats = formats;
    public ready = false;

    async init() {
      this.ready = true;
    }

    async doConvert(
      inputFiles: FileData[],
      inputFormat: FileFormat,
      outputFormat: FileFormat,
    ): Promise<FileData[]> {
      return inputFiles.map((file) => ({
        ...file,
        name: changeExt(file.name, outputFormat.extension),
      }));
    }
  };
}

/// handler for renaming various aliased zip files
export const renameZipHandler = createRenameHandler("renameZip", [
  Formats.ZIP.builder("zip").to(),
  Formats.DOCX.builder("docx").from(),
  Formats.XLSX.builder("xlsx").from(),
  Formats.PPTX.builder("pptx").from(),
  Formats.ODT.builder("odt").lossless().from(),
  Formats.ODP.builder("odp").lossless().from(),
  Formats.ODS.builder("ods").lossless().from(),
  Formats.XPI.builder("xpi").lossless().from(),
  Formats.LOVE.builder("love").from(),
  Formats.OSZ.builder("osz").from(),
  Formats.OSK.builder("osk").from(),
  Formats.APWORLD.builder("apworld").from(),
  Formats.JAR.builder("jar").lossless().from(),
  Formats.APK.builder("apk").lossless().from(),
  Formats.SB3.builder("sb3").from(),
  Formats.IPA.builder("ipa").from(),
  Formats.APP.builder("app").from(),
  Formats.CBZ.builder("cbz").lossless().from(),
]);
/// handler for renaming text-based formats
export const renameTxtHandler = createRenameHandler("renameTxt", [
  Formats.TEXT.builder("text").to(),
  Formats.JSON.builder("json").from(),
  Formats.XML.builder("xml").from(),
  Formats.YML.builder("yaml").from(),
]);
/// handler for renaming json-based formats
export const renameJsonHandler = createRenameHandler("renameJson", [
  Formats.JSON.builder("json").to(),
  Formats.HAR.builder("har").from(),
  Formats.PISKEL.builder("piskel").lossless().from(),
]);
/// handler for renaming tar-based formats
export const renameTarHandler = createRenameHandler("renameTar", [
  Formats.TAR.builder("tar").to(),
  Formats.CBT.builder("cbt").lossless().from(),
]);
/// handler for renaming rar-based formats
export const renameRarHandler = createRenameHandler("renameRar", [
  Formats.RAR.builder("rar").to(),
  Formats.CBR.builder("cbr").lossless().from(),
]);
/// handler for renaming 7z-based formats
export const rename7zHandler = createRenameHandler("rename7z", [
  Formats.SZ.builder("7z").to(),
  Formats.CB7.builder("cb7").lossless().from(),
]);
