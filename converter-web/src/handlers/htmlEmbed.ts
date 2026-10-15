import Formats from "src/Formats.ts";
import type { FileData, FileFormat, FormatHandler } from "../FormatHandler.ts";
import { changeExt, decode, encode } from "src/common/index.ts";

class htmlEmbedHandler implements FormatHandler {
  public readonly name = "htmlEmbed";
  public supportedFormats = [
    Formats.HTML.builder("html").lossless().to(),
    Formats.PNG.builder("png").from(),
    Formats.JPEG.builder("jpeg").from(),
    Formats.WEBP.builder("webp").from(),
    Formats.GIF.builder("gif").from(),
    Formats.SVG.builder("svg").from(),
    Formats.TEXT.builder("text").from(),
    Formats.MP4.builder("mp4").from(),
    Formats.MP3.builder("mp3").from(),
  ];
  public ready = false;

  async init() {
    this.ready = true;
  }

  static bytesToBase64(bytes: Uint8Array): string {
    const chunks = [];
    for (let i = 0; i < bytes.length; i += 32768) {
      const byteChunk = bytes.subarray(i, i + 32768);
      chunks.push(String.fromCharCode(...byteChunk));
    }
    return btoa(chunks.join(""));
  }

  async doConvert(
    inputFiles: FileData[],
    inputFormat: FileFormat,
    outputFormat: FileFormat,
  ): Promise<FileData[]> {
    if (outputFormat.internal !== "html")
      throw new TypeError(`Unsupported output format: ${outputFormat.internal}`);

    let html = "";

    for (const inputFile of inputFiles) {
      if (inputFormat.internal === "text") {
        const text = decode(inputFile.bytes)
          .replaceAll("&", "&amp;")
          .replaceAll("<", "&lt;")
          .replaceAll(">", "&gt;");
        html += `<pre>${text}</pre>`;
      } else if (inputFormat.internal === "svg") {
        html += `<div><template shadowrootmode="open">${decode(inputFile.bytes)}</template></div><br>`;
      } else {
        const base64 = htmlEmbedHandler.bytesToBase64(inputFile.bytes);

        if (inputFormat.mime.startsWith("image/")) {
          html += `<img src="data:${inputFormat.mime};base64,${base64}"><br>`;
        } else if (inputFormat.mime.startsWith("audio/")) {
          html += `<audio controls>
            <source src="data:${inputFormat.mime};base64,${base64}" type="${inputFormat.mime}"></source>
          </audio><br>`;
        } else {
          html += `<video controls>
            <source src="data:${inputFormat.mime};base64,${base64}" type="${inputFormat.mime}"></source>
          </video><br>`;
        }
      }
    }

    const bytes = encode(html);
    const name = changeExt(inputFiles[0].name, outputFormat.extension);
    return [{ bytes, name }];
  }
}

export default htmlEmbedHandler;
