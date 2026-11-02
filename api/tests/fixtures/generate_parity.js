// Regenerates js_parity.json: runs the *website's own* retrieval code from
// index.html on the sample data, so the Python port can be checked against it.
//
// Run from the repo root whenever you change the retrieval logic in index.html:
//   node api/tests/fixtures/generate_parity.js
const fs = require('fs');
const path = require('path');

const here = __dirname;
const html = fs.readFileSync(path.join(here, '../../../index.html'), 'utf8');

// Pull out the helper functions + Index from the page script (everything
// between the IIFE start and where the page creates its index).
const start = html.indexOf('(function(){') + '(function(){'.length;
const end = html.indexOf('var idx = new Index();');
if (start < 12 || end < 0) throw new Error('Could not find the retrieval code in index.html');
const Index = new Function(html.slice(start, end) + '\nreturn Index;')();

const lexicon = JSON.parse(fs.readFileSync(path.join(here, 'sample/lexicon.json'), 'utf8'));
const rows = fs.readFileSync(path.join(here, 'sample/parallel_sentences.jsonl'), 'utf8')
  .split('\n').filter(l => l.trim()).map(l => JSON.parse(l));
const sentences = JSON.parse(fs.readFileSync(path.join(here, 'sentences.json'), 'utf8'));

const idx = new Index();
idx.build(lexicon, rows);

const cases = [];
for (const direction of ['b2e', 'e2b']) {
  for (const sentence of sentences[direction]) {
    const ctx = idx.buildContext(sentence, direction);
    cases.push({
      direction, sentence,
      lexLines: ctx.lexLines,
      unknown: ctx.unknown,
      examples: ctx.examples.map(e => ({ score: e[0], source: e[1], target: e[2], community: e[3] })),
    });
  }
}
fs.writeFileSync(path.join(here, 'js_parity.json'), JSON.stringify(cases, null, 1));
console.log(`Wrote ${cases.length} cases to js_parity.json`);
