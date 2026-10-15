type ReadyCallback = (error?: ErrorEvent | Error) => void;
type WorkerCallback = (...result: any[]) => void;

export type SimpleTTSOptions = {
  workerPath: string;
  defaultVoice?: string;
  defaultRate?: number;
  defaultPitch?: number;
  defaultVolume?: number;
  enhanceAudio?: boolean;
};

export class SimpleTTS {
  readonly worker: Worker;
  readonly defaultVoice: string;
  readonly defaultRate: number;
  readonly defaultPitch: number;
  readonly defaultVolume: number;
  readonly enhanceAudio: boolean;

  #ready = false;
  #sampleRate = 22050;
  #readyCallbacks: ReadyCallback[] = [];
  #callbacks = new Map<string, WorkerCallback>();

  constructor(options: SimpleTTSOptions) {
    this.defaultVoice = options.defaultVoice ?? "en";
    this.defaultRate = options.defaultRate ?? 175;
    this.defaultPitch = options.defaultPitch ?? 50;
    this.defaultVolume = options.defaultVolume ?? 1;
    this.enhanceAudio = options.enhanceAudio ?? false;
    this.worker = new Worker(options.workerPath);

    this.worker.onmessage = (event: MessageEvent) => {
      if (event.data !== "ready") return;

      this.#ready = true;
      this.worker.onmessage = (message) => this.#handleMessage(message);
      this.#sendMessage("get_samplerate", [], (rate: number) => {
        if (rate) this.#sampleRate = rate;
      });
      this.#executeReadyCallbacks();
    };

    this.worker.onerror = (error) => this.#executeReadyCallbacks(error);
  }

  onReady(callback: ReadyCallback) {
    if (this.#ready) callback();
    else this.#readyCallbacks.push(callback);
  }

  speak(text: string, callback: (audio: Float32Array, sampleRate: number) => void) {
    if (!this.#ready) throw new Error("SimpleTTS is not ready");

    const chunks: Float32Array[] = [];
    this.#sendMessage("set_voice", [this.defaultVoice]);
    this.#sendMessage("set_rate", [this.defaultRate]);
    this.#sendMessage("set_pitch", [this.defaultPitch]);
    this.#sendMessage("synthesize", [text], (samples?: ArrayLike<number>) => {
      if (samples) {
        chunks.push(new Float32Array(samples));
        return;
      }

      let audio = this.#mergeChunks(chunks);
      if (this.enhanceAudio) audio = this.#enhance(audio);
      if (this.defaultVolume !== 1) {
        audio = audio.map((sample) => sample * this.defaultVolume);
      }
      callback(audio, this.#sampleRate);
    });
  }

  #handleMessage(event: MessageEvent) {
    const { callback, result = [], done } = event.data as {
      callback?: string;
      result?: any[];
      done?: boolean;
    };
    if (!callback) return;

    this.#callbacks.get(callback)?.(...result);
    if (done) this.#callbacks.delete(callback);
  }

  #sendMessage(method: string, args: unknown[], callback?: WorkerCallback) {
    const message: { method: string; args: unknown[]; callback?: string } = { method, args };
    if (callback) {
      message.callback = `_${method}_${crypto.randomUUID()}_cb`;
      this.#callbacks.set(message.callback, callback);
    }
    this.worker.postMessage(message);
  }

  #executeReadyCallbacks(error?: ErrorEvent | Error) {
    for (const callback of this.#readyCallbacks.splice(0)) callback(error);
  }

  #mergeChunks(chunks: Float32Array[]) {
    const output = new Float32Array(chunks.reduce((length, chunk) => length + chunk.length, 0));
    let offset = 0;
    for (const chunk of chunks) {
      output.set(chunk, offset);
      offset += chunk.length;
    }
    return output;
  }

  #enhance(input: Float32Array) {
    const boosted = new Float32Array(input.length);
    if (!input.length) return boosted;
    boosted[0] = input[0];
    for (let i = 1; i < input.length; i++) {
      boosted[i] = input[i] + (input[i] - input[i - 1]) * 0.2;
    }

    const output = new Float32Array(input.length);
    let hold = 0;
    for (let i = 0; i < boosted.length; i++) {
      if (Math.abs(boosted[i]) > 0.01) {
        output[i] = boosted[i];
        hold = 220;
      } else if (hold > 0) {
        output[i] = boosted[i];
        hold--;
      }
    }
    return output;
  }
}
