/* Shared by current turns, restored history and teacher messages. */
(() => {
  'use strict';
  const md = window.markdownit({html: false, linkify: false, breaks: true, maxNesting: 32});
  // Only a teacher's explicit click may leave the workbench. In particular,
  // model-authored Markdown images must never trigger remote image requests.
  md.validateLink = url => /^https?:\/\//i.test(url);
  md.renderer.rules.image = (tokens, i, options, env, renderer) => {
    const alt = renderer.renderInlineAsText(tokens[i].children || [], options, env);
    return md.utils.escapeHtml(alt || '图片');
  };
  md.renderer.rules.link_open = (tokens, i, options, env, renderer) => {
    tokens[i].attrSet('target', '_blank');
    tokens[i].attrSet('rel', 'noopener noreferrer');
    return renderer.renderToken(tokens, i, options);
  };
  // Long tables and code scroll inside the bubble; the conversation keeps its width.
  md.renderer.rules.table_open = () => '<div class="cc-table-wrap" tabindex="0" aria-label="表格"><table>\n';
  md.renderer.rules.table_close = () => '</table></div>\n';
  // Capture TeX before Markdown's backslash escape rule consumes its delimiters.
  // Code spans and fenced blocks already bypass these inline rules.
  const delimiters = [['\\[', '\\]', true], ['\\(', '\\)', false], ['$$', '$$', true], ['$', '$', false]];
  md.inline.ruler.before('escape', 'classroom_math', (state, silent) => {
    const {src, pos, posMax} = state;
    const pair = delimiters.find(([open]) => src.startsWith(open, pos));
    if (!pair) return false;
    const [open, close, display] = pair;
    const start = pos + open.length;
    if (open === '$' && /\s/.test(src[start] || ' ')) return false;
    let end = src.indexOf(close, start);
    while (end > start && src[end - 1] === '\\') end = src.indexOf(close, end + close.length);
    if (end <= start || end + close.length > posMax || end - start > 2048) return false;
    if (open === '$' && (/\s/.test(src[end - 1]) || /\d/.test(src[end + 1] || ''))) return false;
    if (!silent) {
      const token = state.push('classroom_math', '', 0);
      token.content = src.slice(start, end);
      token.meta = {display, literal: src.slice(pos, end + close.length)};
    }
    state.pos = end + close.length;
    return true;
  });
  md.renderer.rules.classroom_math = (tokens, i) => {
    const {content, meta} = tokens[i];
    try {
      return window.katex.renderToString(content, {
        output: 'mathml', displayMode: meta.display, trust: false,
        strict: 'error', maxSize: 12, maxExpand: 300, throwOnError: true
      });
    } catch {
      return md.utils.escapeHtml(meta.literal);
    }
  };
  window.YincaiMarkdown = Object.freeze({render: value => md.render(String(value ?? ''))});
})();
