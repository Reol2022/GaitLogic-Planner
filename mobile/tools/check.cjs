// Static TypeScript and SFC syntax only; never label this a native compilation.
const fs = require('node:fs'), path = require('node:path');
const root = path.resolve(__dirname, '..');
const resolve = name => require.resolve(name, { paths: [root, path.resolve(root, '../web')] });
const ts = require(resolve('typescript'));
const { parse, compileScript, compileTemplate } = require(resolve('@vue/compiler-sfc'));
function walk(dir) { return fs.readdirSync(dir, { withFileTypes: true }).flatMap(entry => {
  if (['node_modules', '.checks', '.test-build', 'unpackage', '.hbuilderx'].includes(entry.name)) return [];
  const file = path.join(dir, entry.name); return entry.isDirectory() ? walk(file) : [file];
}); }
// Component tests have a separate Vitest/jsdom transform boundary.
const files = walk(root).filter(file => !file.startsWith(path.join(root, 'tests', 'component') + path.sep)), virtual = new Map();
for (const file of files.filter(f => f.endsWith('.uvue') || f.endsWith('.uts'))) {
  if (file.endsWith('.uts')) { virtual.set(file + '.ts', fs.readFileSync(file, 'utf8')); continue; }
  const source = fs.readFileSync(file, 'utf8'), result = parse(source, { filename: file });
  if (result.errors.length) throw new Error(`${file}: invalid SFC syntax`);
  if (result.descriptor.template) {
    const template = compileTemplate({ source: result.descriptor.template.content, filename: file, id: 'mobile-static-check' });
    if (template.errors.length) throw new Error(`${file}: invalid template syntax: ${template.errors.join(',')}`);
  }
  if (result.descriptor.script || result.descriptor.scriptSetup) {
    virtual.set(file + '.ts', compileScript(result.descriptor, { id: 'mobile-static-check' }).content);
  }
}
const options = { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS, moduleResolution: ts.ModuleResolutionKind.Node10,
  strict: true, skipLibCheck: true, noEmit: true, baseUrl: root,
  paths: { vue: [resolve('vue/dist/vue.d.ts')] } };
const host = ts.createCompilerHost(options), exists = host.fileExists, read = host.readFile;
host.fileExists = file => virtual.has(path.normalize(file)) || exists(file);
host.readFile = file => virtual.get(path.normalize(file)) ?? read(file);
host.getSourceFile = (file, languageVersion) => { const text = host.readFile(file); return text === undefined ? undefined : ts.createSourceFile(file, text, languageVersion); };
const program = ts.createProgram([...files.filter(f => f.endsWith('.ts')), ...virtual.keys()], options, host);
const diagnostics = ts.getPreEmitDiagnostics(program);
if (diagnostics.length) { console.error(ts.formatDiagnosticsWithColorAndContext(diagnostics, {
  getCanonicalFileName: file => file, getCurrentDirectory: () => root, getNewLine: () => '\n' })); process.exit(1); }
const manifest = JSON.parse(fs.readFileSync(path.join(root, 'manifest.json'), 'utf8'));
if (!manifest['uni-app-x']?.vapor) throw new Error('Vapor project marker required');
const pages = JSON.parse(fs.readFileSync(path.join(root, 'pages.json'), 'utf8'));
for (const page of pages.pages) if (!fs.existsSync(path.join(root, page.path + '.uvue'))) throw new Error('Missing page: ' + page.path);
console.log(JSON.stringify({ status: 'PASS', typecheck: 'TypeScript + SFC syntax, NOT native compile', typescript: ts.version,
  pages: pages.pages.length, vapor: true, compilerTarget: 'HBuilderX 5.34.2026102909' }));
