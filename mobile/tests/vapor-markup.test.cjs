const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
function pages(directory) {
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap(entry => {
    const file = path.join(directory, entry.name);
    return entry.isDirectory() ? pages(file) : file.endsWith('.uvue') ? [file] : [];
  });
}
test('Vapor scroll containers use explicit direction, not unsupported legacy attributes', () => {
  const files = [...pages(path.join(root, 'pages')), ...pages(path.join(root, 'components'))];
  let count = 0;
  for (const file of files) {
    for (const tag of fs.readFileSync(file, 'utf8').matchAll(/<scroll-view\b[^>]*>/g)) {
      count++;
      assert.doesNotMatch(tag[0], /\bscroll-[xy]\b/, path.relative(root, file));
      assert.match(tag[0], /direction="(?:vertical|horizontal)"/, path.relative(root, file));
    }
  }
  assert.ok(count >= 10);
});
test('native navigation uses matching local raster icons for all five tabs', () => {
  const config = JSON.parse(fs.readFileSync(path.join(root, 'pages.json'), 'utf8'));
  assert.equal(config.tabBar.list.length, 5);
  for (const item of config.tabBar.list) for (const key of ['iconPath', 'selectedIconPath']) {
    const data = fs.readFileSync(path.join(root, item[key]));
    assert.equal(data.subarray(0, 8).toString('hex'), '89504e470d0a1a0a');
    assert.equal(data.readUInt32BE(16), 72);
    assert.equal(data.readUInt32BE(20), 72);
    assert.ok(data.length < 4096);
  }
});
test('Vapor visual styles avoid descendant class selectors unsupported by the native compiler', () => {
  const files = [...pages(path.join(root, 'pages')), ...pages(path.join(root, 'components'))];
  const styles = [fs.readFileSync(path.join(root, 'styles/tokens.css'), 'utf8')];
  for (const file of files) for (const match of fs.readFileSync(file, 'utf8').matchAll(/<style[^>]*>([\s\S]*?)<\/style>/g)) styles.push(match[1]);
  for (const style of styles) assert.doesNotMatch(style, /\.[\w-]+\s+\.[\w-]+\s*\{/);
});
test('normal login has only account fields and a collapsed connection section', () => {
  const login = fs.readFileSync(path.join(root, 'pages/auth/login.uvue'), 'utf8');
  assert.match(login, /const advanced = ref\(false\)/);
  assert.match(login, /v-if="advanced"/);
  assert.match(login, /username-field/);
  assert.match(login, /password-field/);
});

test('tools have a first-level tab while statistics remain reachable from training and tools', () => {
  const config = JSON.parse(fs.readFileSync(path.join(root, 'pages.json'), 'utf8'));
  assert.deepEqual(config.tabBar.list.map(item => item.text), ['今日', '训练', 'Gilo', '工具', '我的']);
  assert.equal(config.tabBar.list[3].pagePath, 'pages/workspace/index');
  for (const page of ['training/index', 'workspace/index']) {
    assert.match(fs.readFileSync(path.join(root, 'pages/' + page + '.uvue'), 'utf8'), /\/pages\/analytics\/index/);
  }
  const profile = fs.readFileSync(path.join(root, 'pages/profile/index.uvue'), 'utf8');
  assert.doesNotMatch(profile, /platform\.navigate\('\/pages\/workspace\/index'\)/);
});

test('mobile shares the existing Web palette and grouped tool rows', () => {
  const web = fs.readFileSync(path.join(root, '../web/src/styles/global.css'), 'utf8').toLowerCase();
  const mobile = fs.readFileSync(path.join(root, 'styles/tokens.css'), 'utf8').toLowerCase();
  for (const color of ['#1976d2', '#ffffff', '#172033', '#e0e6ec']) {
    assert.ok(web.includes(color), color);
    assert.ok(mobile.includes(color), color);
  }
  assert.doesNotMatch(mobile, /#b84e2b|#f5f4f0|#30382d/);
  assert.match(mobile, /\.theme-dark\s*\{[^}]*--tone-canvas:\s*#111419/);
  assert.match(mobile, /\.theme-light\s*\{[^}]*--tone-canvas:\s*#f3f6f9/);
  const config = JSON.parse(fs.readFileSync(path.join(root, 'pages.json'), 'utf8'));
  for (const item of config.pages) assert.match(fs.readFileSync(path.join(root, item.path + '.uvue'), 'utf8'), /:class="themeClass"/, item.path);
  const tools = fs.readFileSync(path.join(root, 'pages/workspace/index.uvue'), 'utf8');
  assert.match(tools, /class="tool-grid"/);
  assert.match(tools, /\.tool-tile\s*\{[^}]*flex-direction:\s*row/);
  assert.match(tools, /\.tool-grid\s*\{[^}]*flex-direction:\s*column/);
});
