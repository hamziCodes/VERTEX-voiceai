/**
 * UCVE demo AudioWorklets:
 * - pcm16-capture: mic → Int16 frames @ 16 kHz (downsamples if AudioContext ≠ 16 kHz)
 * - pcm16-player: float32 queue → speakers (expects samples already at context rate)
 *
 * IMPORTANT: do not use `instanceof Float32Array` in the player — the worklet realm's
 * Float32Array differs from the main thread's, so instanceof silently dropped all TTS.
 */

class Pcm16CaptureProcessor extends AudioWorkletProcessor {
  constructor(options) {
    super(options);
    const targetRate = (options && options.processorOptions && options.processorOptions.targetSampleRate) || 16000;
    this._ratio = sampleRate / targetRate;
    this._acc = 0;
    this._buffer = [];
  }

  process(inputs) {
    const input = inputs[0];
    if (!input || !input[0]) return true;
    const channel = input[0];
    const GAIN = 2.2;
    const TARGET = 512;

    for (let i = 0; i < channel.length; i++) {
      this._acc += 1;
      if (this._acc < this._ratio) continue;
      this._acc -= this._ratio;
      const s = Math.max(-1, Math.min(1, channel[i] * GAIN));
      this._buffer.push(s < 0 ? s * 0x8000 : s * 0x7fff);
    }

    while (this._buffer.length >= TARGET) {
      const pcm = new Int16Array(TARGET);
      for (let i = 0; i < TARGET; i++) pcm[i] = this._buffer[i];
      this._buffer.splice(0, TARGET);
      this.port.postMessage(pcm.buffer, [pcm.buffer]);
    }

    return true;
  }
}

class Pcm16PlayerProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this._buf = new Float32Array(0);
    this._underruns = 0;
    this.port.onmessage = (e) => {
      const incoming = e.data;
      if (incoming && incoming.flush) {
        this._buf = new Float32Array(0);
        this.port.postMessage({ flushed: true });
        return;
      }
      // Cross-realm safe: accept any array-like numeric buffer, never instanceof.
      let samples = null;
      if (incoming && typeof incoming.length === 'number' && incoming.length > 0) {
        samples = incoming;
      } else if (incoming instanceof ArrayBuffer && incoming.byteLength >= 4) {
        samples = new Float32Array(incoming);
      } else {
        return;
      }
      const merged = new Float32Array(this._buf.length + samples.length);
      merged.set(this._buf, 0);
      merged.set(samples, this._buf.length);
      this._buf = merged;
    };
  }

  process(_inputs, outputs) {
    const out = outputs[0] && outputs[0][0];
    if (!out) return true;
    if (this._buf.length >= out.length) {
      out.set(this._buf.subarray(0, out.length));
      this._buf = this._buf.subarray(out.length);
    } else {
      if (this._buf.length > 0) {
        out.set(this._buf);
        for (let i = this._buf.length; i < out.length; i++) out[i] = 0;
        this._underruns++;
        this.port.postMessage({ underrun: this._underruns });
      } else {
        out.fill(0);
      }
      this._buf = new Float32Array(0);
    }
    return true;
  }
}

registerProcessor('pcm16-capture', Pcm16CaptureProcessor);
registerProcessor('Pcm16CaptureProcessor', Pcm16CaptureProcessor);
registerProcessor('pcm16-player', Pcm16PlayerProcessor);
registerProcessor('Pcm16PlayerProcessor', Pcm16PlayerProcessor);
