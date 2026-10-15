import type { FileData, FileFormat, FormatHandler } from "../FormatHandler.ts";
import Formats from "src/Formats.ts";
import { Buffer } from "buffer";

import elfUrl from "built/shtoelf/stub.elf?url";
import { changeExt } from "src/common/index.ts";

function replaceUint32LE(file: Buffer, from: number, to: number) {
  const fromBytes = Buffer.alloc(4);
  fromBytes.writeUint32LE(from, 0);

  const toBytes = Buffer.alloc(4);
  toBytes.writeUint32LE(to, 0);

  const index = file.indexOf(fromBytes);
  toBytes.copy(file, index);
}

class shToElfHandler implements FormatHandler {
  public readonly name = "shToElf";
  public supportedFormats = [
    Formats.SH.builder("sh").lossless().from(),
    Formats.ELF.builder("elf").to(),
  ];
  public ready = false;

  #binary?: Buffer;

  async init() {
    this.ready = true;
    this.#binary = Buffer.from(await (await fetch(elfUrl)).bytes());
  }

  async doConvert(
    inputFiles: FileData[],
    inputFormat: FileFormat,
    outputFormat: FileFormat,
  ): Promise<FileData[]> {
    const outputFiles: FileData[] = [];

    for (const inputFile of inputFiles) {
      const binary = Buffer.from(new Uint8Array(this.#binary!));
      replaceUint32LE(binary, 1273991571, inputFile.bytes.length);

      let file = Buffer.concat([binary, inputFile.bytes]);

      outputFiles.push({
        name: changeExt(inputFile.name, "elf"),
        bytes: file,
      });
    }

    return outputFiles;
  }
}

export default shToElfHandler;
