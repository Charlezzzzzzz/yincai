const {test} = require('node:test');
const assert = require('node:assert/strict');
global.window = {markdownit: require('./vendor/markdown-it.umd.min.js'), katex: require('./vendor/katex.min.js')};
require('./markdown.js');
const render = window.YincaiMarkdown.render;

test('the expert review uses real emphasis, numbered reasons and suggested steps', () => {
  const html = render('**审阅意见**\n1. 错因定位准确\n2. 还原步骤\n\n**下一步建议**\n- 学生说明依据');
  assert.match(html, /<strong>审阅意见<\/strong>/);
  assert.match(html, /<ol>\s*<li>错因定位准确<\/li>/);
  assert.match(html, /<ul>\s*<li>学生说明依据<\/li>/);
  assert.doesNotMatch(html, /\*\*/);
});

test('handles tables, literal code, block quotations and Chinese plain text', () => {
  const html = render('> 先圈出每一项。\n\n| 学生 | 建议 |\n|---|---|\n| 小川 | 验算 |\n\n`**教师原话**`');
  assert.match(html, /<blockquote>/);
  assert.match(html, /<table>/);
  assert.match(html, /<code>\*\*教师原话\*\*<\/code>/);
  assert.match(render('两边同乘 6。'), /两边同乘 6。/);
});

test('only teacher-clicked web links navigate and remote markdown images stay text', () => {
  const html = render('[参考](https://example.org) ![图示](https://example.org/class.png) <i>原文</i>');
  assert.match(html, /href="https:\/\/example.org"/);
  assert.match(html, /rel="noopener noreferrer"/);
  assert.doesNotMatch(html, /<img|<i>/);
  assert.match(html, /&lt;i&gt;原文/);
});

test('renders classroom TeX to offline MathML and leaves literal code intact', () => {
  for (const source of [String.raw`\(\frac{x-1}{2}=1\)`, '$x=13$', String.raw`\[2x=26\]`, '$$x=13$$']) {
    assert.match(render(source), /<math\b/);
  }
  assert.doesNotMatch(render('`$x=13$`'), /<math\b/);
  assert.doesNotMatch(render('单价 $50 和 $100'), /<math\b/);
});

test('contact previews use readable text without Markdown markers or duplicate math', () => {
  const preview = window.YincaiMarkdown.preview;
  assert.equal(preview('**课堂追问**\n用蓝笔圈出常数项。'), '课堂追问 用蓝笔圈出常数项。');
  assert.equal(preview('1. **核验**\n2. 代回'), '核验 代回');
  assert.equal(preview('建议 $x=13$ 。'), '建议 x=13 。');
  assert.equal(preview('学生写 `**原话**`'), '学生写 **原话**');
});
