"""Optional Playwright probes for a game's playback mix and DOM controls."""
import base64
import wave
from contextlib import contextmanager


@contextmanager
def record_mix(page, path):
    """Write a short WAV of the observed final Web Audio bus, after a real unlock."""
    tap = page.evaluate_handle("""() => {
      const output = window.__GAME_TEST__?.audioOutput?.();
      if (!output || output.context.state !== 'running') {
        throw new Error('Unlock audio through a real gesture, then expose the final mix via audioOutput()');
      }
      // A read-only PCM tap for short Chromium diagnostics, including silent
      // intervals. It needs no worklet module or change to the game's CSP.
      const tap = output.context.createScriptProcessor(1024, output.channelCount, 1);
      const blocks = [];
      tap.onaudioprocess = event => {
        const input = event.inputBuffer;
        blocks.push(Array.from({length: input.numberOfChannels}, (_, c) => input.getChannelData(c).slice()));
        event.outputBuffer.getChannelData(0).fill(0);
      };
      output.connect(tap);
      tap.connect(output.context.destination);
      return {output, tap, blocks};
    }""")
    try:
        yield
        data = tap.evaluate("""({output, tap, blocks}) => {
          if (!blocks.length) throw new Error('No playback samples observed in this capture window');
          const channels = blocks[0].length;
          const bytes = new Uint8Array(blocks.length * tap.bufferSize * channels * 2);
          const pcm = new DataView(bytes.buffer);
          let offset = 0;
          for (const block of blocks) {
            for (let i = 0; i < block[0].length; i++) {
              for (const channel of block) {
                const sample = Math.max(-1, Math.min(1, channel[i]));
                pcm.setInt16(offset, Math.round(sample * 32767), true);
                offset += 2;
              }
            }
          }
          let binary = '';
          for (let i = 0; i < bytes.length; i += 8192) {
            binary += String.fromCharCode(...bytes.subarray(i, i + 8192));
          }
          return {rate: output.context.sampleRate, channels, pcm: btoa(binary)};
        }""")
        with wave.open(str(path), 'wb') as wav:
            wav.setparams((data['channels'], 2, data['rate'], 0, 'NONE', 'not compressed'))
            wav.writeframes(base64.b64decode(data['pcm']))
    finally:
        try:
            tap.evaluate("""({output, tap}) => {
              tap.onaudioprocess = null;
              output.disconnect(tap);
              tap.disconnect();
            }""")
        finally:
            tap.dispose()


def hit_target(locator):
    """Read a control at its current position without scrolling it into view."""
    return locator.evaluate("""el => {
      const r = el.getBoundingClientRect(), x = r.left + r.width / 2, y = r.top + r.height / 2;
      const hit = document.elementFromPoint(x, y);
      return {
        rect: {x: r.x, y: r.y, width: r.width, height: r.height},
        insideViewport: r.width > 0 && r.height > 0 && r.left >= 0 && r.top >= 0
          && r.right <= innerWidth && r.bottom <= innerHeight,
        receivesCenter: !!hit && el.contains(hit), hit: hit?.id || hit?.tagName || null
      };
    }""")
