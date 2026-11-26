/** Future transport probe only. NOT wired to a nonexistent Coach SSE endpoint. */
export class Utf8Chunks {
  private bytes: number[] = [];
  push(chunk: ArrayBuffer): string {
    for (const value of new Uint8Array(chunk)) this.bytes.push(value);
    let text = '', consumed = 0;
    while (consumed < this.bytes.length) {
      const lead = this.bytes[consumed];
      const count = lead < 0x80 ? 1 : lead >= 0xc2 && lead <= 0xdf ? 2 : lead >= 0xe0 && lead <= 0xef ? 3 : lead >= 0xf0 && lead <= 0xf4 ? 4 : 0;
      if (!count) throw new Error('INVALID_UTF8');
      if (consumed + count > this.bytes.length) break;
      let point = count === 1 ? lead : lead & (0x7f >> count);
      for (let i = 1; i < count; i++) {
        const next = this.bytes[consumed + i];
        if ((next & 0xc0) !== 0x80) throw new Error('INVALID_UTF8');
        point = (point << 6) | (next & 0x3f);
      }
      if ((count === 2 && point < 0x80) || (count === 3 && point < 0x800) || (count === 4 && point < 0x10000)
          || point > 0x10ffff || (point >= 0xd800 && point <= 0xdfff)) throw new Error('INVALID_UTF8');
      text += String.fromCodePoint(point); consumed += count;
    }
    this.bytes = this.bytes.slice(consumed);
    return text;
  }
  finish() { if (this.bytes.length) throw new Error('TRUNCATED_UTF8'); }
}
export interface StreamEvent { type: string; data: string }
export class SseProbe {
  private decoder = new Utf8Chunks();
  private pending = '';
  private event = 'message';
  private lines: string[] = [];
  private eventSize = 0;
  done = false;
  push(chunk: ArrayBuffer): StreamEvent[] {
    if (this.done) return [];
    this.pending += this.decoder.push(chunk);
    if (this.pending.length > 65536) throw new Error('STREAM_EVENT_TOO_LARGE');
    const events: StreamEvent[] = [];
    for (;;) {
      const match = /\r\n|\r|\n/.exec(this.pending);
      if (!match || (match[0] === '\r' && match.index === this.pending.length - 1)) break;
      const line = this.pending.slice(0, match.index); this.pending = this.pending.slice(match.index + match[0].length);
      if (!line) {
        if (this.lines.length) {
          const data = this.lines.join('\n');
          if (data === '[DONE]') {
            this.done = true; this.pending = ''; this.lines = []; this.eventSize = 0; break;
          }
          events.push({ type: this.event, data });
        }
        this.event = 'message'; this.lines = []; this.eventSize = 0;
      } else if (line.startsWith('event:')) this.event = line.slice(6).trim();
      else if (line.startsWith('data:')) {
        this.eventSize += line.length;
        if (this.eventSize > 65536) throw new Error('STREAM_EVENT_TOO_LARGE');
        this.lines.push(line.slice(5).replace(/^ /, ''));
      }
    }
    return events;
  }
  finish() { this.decoder.finish(); if (this.pending || this.lines.length) throw new Error('TRUNCATED_EVENT'); }
}
