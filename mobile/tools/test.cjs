const fs = require('node:fs'), path = require('node:path'), cp = require('node:child_process');
const root = path.resolve(__dirname, '..');
const ts = require(require.resolve('typescript', { paths: [root, path.resolve(root, '../web')] }));
function walk(dir) { return fs.readdirSync(dir, { withFileTypes: true }).flatMap(entry => {
  if (['node_modules', '.test-build', '.checks', 'unpackage', '.hbuilderx'].includes(entry.name)) return [];
  const file = path.join(dir, entry.name); return entry.isDirectory() ? walk(file) : [file];
}); }
// Transpile only executable TS, no credentials or generated native artifacts.
for (const file of walk(root).filter(file => file.endsWith('.ts') && !file.endsWith('.d.ts'))) {
  const dest = path.join(root, '.test-build', path.relative(root, file).replace(/\.ts$/, '.js'));
  fs.mkdirSync(path.dirname(dest), { recursive: true });
  fs.writeFileSync(dest, ts.transpileModule(fs.readFileSync(file, 'utf8'), {
    compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS, esModuleInterop: true } }).outputText);
}
const tests = walk(path.join(root, 'tests')).filter(file => file.endsWith('.test.cjs'));
const result = cp.spawnSync(process.execPath, ['--test', ...tests], { cwd: root, stdio: 'inherit' });
process.exit(result.status ?? 1);
