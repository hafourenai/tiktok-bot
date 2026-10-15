const HEADER_LENGTH = 16;
const FAKE_HEADER = Uint8Array.from([
  0x52, 0x50, 0x47, 0x4d, 0x56, 0x00, 0x00, 0x00, 0x00, 0x03, 0x01, 0x00, 0x00, 0x00, 0x00,
  0x00,
]);
const PNG_HEADER = Uint8Array.from([
  0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0x00, 0x00, 0x00, 0x0d, 0x49, 0x48, 0x44,
  0x52,
]);

export class Decrypter {
  readonly #encryptionKey: Uint8Array;

  constructor(encryptionKey: string | null) {
    this.#encryptionKey = Uint8Array.from(
      encryptionKey?.match(/.{2}/g)?.map((byte) => Number.parseInt(byte, 16)) ?? [],
    );
  }

  static getKeyFromPNG(headerLength: number, fileContent: ArrayBuffer): string | null {
    if (fileContent.byteLength < headerLength * 2) return null;

    const encryptedHeader = new Uint8Array(fileContent, headerLength, headerLength);
    let key = "";
    for (let i = 0; i < headerLength; i++) {
      key += ((PNG_HEADER[i] ?? 0) ^ encryptedHeader[i]).toString(16).padStart(2, "0");
    }
    return key;
  }

  verifyFakeHeader(header: Uint8Array): boolean {
    return FAKE_HEADER.every((byte, index) => header[index] === byte);
  }

  decrypt(buffer: ArrayBuffer): ArrayBuffer {
    const output = buffer.slice(HEADER_LENGTH);
    const bytes = new Uint8Array(output);
    for (let i = 0; i < HEADER_LENGTH; i++) {
      bytes[i] ^= this.#encryptionKey[i] ?? 0;
    }
    return output;
  }
}
