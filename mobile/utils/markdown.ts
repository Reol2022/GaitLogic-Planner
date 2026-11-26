export interface MarkdownBlock { kind: 'heading' | 'paragraph' | 'code' | 'list'; text: string }
/** Plain text blocks only: no HTML, image loading, scripts or unsafe links. */
export function markdownBlocks(text: string): MarkdownBlock[] {
  const blocks: MarkdownBlock[] = []; let code = false;
  for (const line of text.slice(0, 60000).split('\n')) {
    if (line.trim().startsWith('```')) { code = !code; continue; }
    blocks.push({ kind: code ? 'code' : /^#{1,6}\s/.test(line) ? 'heading' : /^\s*[-*]\s/.test(line) ? 'list' : 'paragraph',
      text: code ? line : line.replace(/^#{1,6}\s+/, '').replace(/^\s*[-*]\s+/, '• ').replace(/\*\*(.*?)\*\*/g, '$1') });
  }
  return blocks;
}
