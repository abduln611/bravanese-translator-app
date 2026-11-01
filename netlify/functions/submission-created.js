// Netlify Function: runs automatically after every *verified* Netlify Forms
// submission (Netlify invokes any function named `submission-created` and
// filters out spam first). For our two lexicon forms it writes the entry as a
// small JSON file on a new branch and opens a pull request on GitHub.
//
// Nothing reaches lexicon.json until you merge the PR. After merge, the
// GitHub Action in .github/workflows/merge-submissions.yml folds the file
// into lexicon.json / parallel_sentences.jsonl and Netlify redeploys.
//
// Required Netlify environment variables:
//   GITHUB_TOKEN  fine-grained token, this repo only, with
//                 Contents: Read & write + Pull requests: Read & write
// Optional:
//   GITHUB_REPO   default "abduln611/bravanese-translator-app"
//   GITHUB_BASE   default "main"

const REPO = process.env.GITHUB_REPO || 'abduln611/bravanese-translator-app';
const BASE = process.env.GITHUB_BASE || 'main';

// Only these fields are ever written to the (public) repo. Netlify also sends
// ip, user_agent, referrer, etc. -- those are deliberately dropped.
const FORMS = {
  'word-entries': {
    kind: 'word',
    fields: ['bravanese_form', 'english_form', 'is_infinitive_verb', 'size_class',
             'noun_class', 'plural_form', 'past_tense', 'submitted_by'],
    required: ['bravanese_form', 'english_form'],
    title: (d) => `Add word: ${d.bravanese_form} — "${d.english_form}"`,
  },
  'example-entries': {
    kind: 'example',
    fields: ['bravanese_sentence', 'english_translation', 'past_tense',
             'headword_hint', 'submitted_by'],
    required: ['bravanese_sentence', 'english_translation'],
    title: (d) => `Add example: ${d.bravanese_sentence.slice(0, 50)}`,
  },
};

const MAX_LEN = 1000;

function clean(v) {
  if (v === undefined || v === null) return '';
  return String(v).replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F]/g, '').trim().slice(0, MAX_LEN);
}

function slugify(s) {
  return s.normalize('NFKD').replace(/[̀-ͯ]/g, '')
    .toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 40) || 'entry';
}

async function gh(path, opts = {}) {
  const res = await fetch(`https://api.github.com/repos/${REPO}${path}`, {
    ...opts,
    headers: {
      Authorization: `Bearer ${process.env.GITHUB_TOKEN}`,
      Accept: 'application/vnd.github+json',
      'X-GitHub-Api-Version': '2022-11-28',
      'User-Agent': 'bravanese-lexicon-bot',
      ...(opts.body ? { 'Content-Type': 'application/json' } : {}),
    },
  });
  const text = await res.text();
  if (!res.ok) throw new Error(`GitHub ${opts.method || 'GET'} ${path} -> ${res.status}: ${text.slice(0, 300)}`);
  return text ? JSON.parse(text) : {};
}

exports.handler = async function (event) {
  let payload;
  try {
    payload = JSON.parse(event.body || '{}').payload || {};
  } catch (e) {
    return { statusCode: 400, body: 'Invalid event body' };
  }

  const form = FORMS[payload.form_name];
  if (!form) return { statusCode: 200, body: `Ignored form "${payload.form_name}"` };

  if (!process.env.GITHUB_TOKEN) {
    console.error('GITHUB_TOKEN is not set; submission kept in Netlify Forms only.');
    return { statusCode: 500, body: 'GITHUB_TOKEN not configured' };
  }

  const raw = payload.data || {};
  const data = {};
  for (const f of form.fields) data[f] = clean(raw[f]);
  if (form.kind === 'word') data.is_infinitive_verb = data.is_infinitive_verb === 'true';

  for (const f of form.required) {
    if (!data[f]) return { statusCode: 200, body: `Skipped: missing ${f}` };
  }

  const submissionId = clean(payload.id) || String(Date.now());
  const createdAt = clean(payload.created_at) || new Date().toISOString();
  const record = { kind: form.kind, submission_id: submissionId, created_at: createdAt, ...data };

  const label = form.kind === 'word' ? data.bravanese_form : data.bravanese_sentence;
  const stamp = createdAt.replace(/[^0-9]/g, '').slice(0, 14);
  const fileName = `${stamp}-${slugify(label)}-${submissionId.slice(-6)}.json`;
  const filePath = `submissions/${form.kind}s/${fileName}`;
  const branch = `submission/${form.kind}-${stamp}-${submissionId.slice(-6)}`;

  try {
    const baseRef = await gh(`/git/ref/heads/${encodeURIComponent(BASE)}`);
    await gh('/git/refs', {
      method: 'POST',
      body: JSON.stringify({ ref: `refs/heads/${branch}`, sha: baseRef.object.sha }),
    });

    await gh(`/contents/${filePath}`, {
      method: 'PUT',
      body: JSON.stringify({
        message: `${form.title(data)}`.slice(0, 120),
        content: Buffer.from(JSON.stringify(record, null, 2) + '\n', 'utf8').toString('base64'),
        branch,
      }),
    });

    const rows = Object.entries(data)
      .filter(([, v]) => v !== '' && v !== false)
      .map(([k, v]) => `| \`${k}\` | ${String(v).replace(/\|/g, '\\|').replace(/\n/g, ' ')} |`)
      .join('\n');

    const pr = await gh('/pulls', {
      method: 'POST',
      body: JSON.stringify({
        title: form.title(data).slice(0, 120),
        head: branch,
        base: BASE,
        body:
          `New ${form.kind} submitted through the contribute form.\n\n` +
          `| Field | Value |\n|---|---|\n${rows}\n\n` +
          `**Merge** to add it to the lexicon (the merge-submissions Action folds it in and Netlify redeploys). ` +
          `You can edit \`${filePath}\` in this PR first to fix anything. **Close** the PR to reject it.\n\n` +
          `Netlify submission id: \`${submissionId}\``,
      }),
    });

    console.log(`Opened PR #${pr.number} for ${filePath}`);
    return { statusCode: 200, body: `Opened PR #${pr.number}` };
  } catch (err) {
    // The submission is still safe in the Netlify Forms dashboard.
    console.error(err.message);
    return { statusCode: 500, body: err.message };
  }
};
