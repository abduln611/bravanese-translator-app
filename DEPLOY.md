# Bravanese Translator -- standalone deployment (with hidden API key)

This is a real, standalone version of the AI translator: your friend gets a
plain URL, no Claude account needed, and never sees or handles your API key.
The key lives only in Netlify's server-side environment variables.

## How it works

- `index.html` -- the page your friend uses (uploads lexicon.json/parallel_sentences.jsonl, types a sentence).
- `netlify/functions/translate.js` -- a small server-side function. It holds
  the real API key and is the only thing that ever talks to Anthropic. The
  browser only ever talks to this function, never to Anthropic directly.

## Before you deploy: add your data files

The page no longer asks anyone to upload files -- it fetches `lexicon.json`
and `parallel_sentences.jsonl` automatically from the site itself. That
means **you need to copy your actual `lexicon.json` and
`parallel_sentences.jsonl` into this folder** (same level as `index.html`)
*before* pushing to GitHub, so Netlify serves them as static files.

```
netlify_site_v2/
  index.html
  lexicon.json              <- copy your real file here
  parallel_sentences.jsonl  <- copy your real file here
  netlify.toml
  netlify/functions/translate.js
```

Any future edits to your dictionary (new words via `add_entry.py`, etc.)
need to be copied into this folder again and re-pushed/redeployed for your
friend to see them -- this is a snapshot of your data at deploy time, not a
live connection to your local files.

## Deploy steps

1. **Put this whole folder in its own GitHub repo** (a fresh one, separate
   from your main `bravanese-translator` repo, keeps things simple) and push
   it, the same way you did before:
   ```
   git init
   git add -A
   git commit -m "Initial commit"
   git remote add origin https://github.com/YOUR-USERNAME/bravanese-translator-app.git
   git branch -M main
   git push -u origin main
   ```

2. **On Netlify**, choose "Import from Git" / "Add new site" and connect
   this new repo (NOT the drag-and-drop Netlify Drop flow -- that one is for
   plain static files and may not reliably support serverless functions).
   Netlify will detect `netlify.toml` automatically; no build command is
   needed.

3. **Set your API key** in the Netlify dashboard: Site settings ->
   Environment variables -> Add a variable ->
   - Key: `ANTHROPIC_API_KEY`
   - Value: your real key
   This is the only place your real key exists. It is never in the repo,
   never in the HTML, never sent to the browser.

4. Netlify gives you a `https://something.netlify.app` URL. **That's the
   link you send your friend.** The dictionary data is already built into
   the site, so he doesn't need any files from you -- just the link.

## Testing it

I tested the function's request/response handling directly (missing key,
wrong HTTP method, missing prompt, and a real network call to Anthropic
with a fake key that correctly came back as an authentication error) --
all four behaved correctly. I have not been able to test an actual live
Netlify deployment end-to-end from here, since that requires a real
Netlify account and DNS/build step I can't access. After deploying, do one
real test translation yourself before sending the link along, just to
confirm the environment variable is wired up the way you expect.

## If something goes wrong

- **"ANTHROPIC_API_KEY is not set on the server"** -- you deployed before
  adding the environment variable, or added it but haven't redeployed since.
  Trigger a new deploy after adding the variable (Netlify's dashboard has a
  "Trigger deploy" button, or just push an empty commit).
- **A 401/authentication error** -- the key itself is invalid or was
  copy-pasted with extra whitespace. Double-check it in the Netlify
  dashboard.
- **The page loads but "Translate" does nothing** -- open the browser's
  developer console (F12) and check for errors; if it says the function
  wasn't found, the function likely isn't deployed -- confirm
  `netlify/functions/translate.js` actually made it into the repo (check on
  GitHub) and that Netlify's build log mentions detecting a function.

## Community submissions -> GitHub (contribute.html)

`/contribute.html` lets people add words and example sentences. The flow:

1. Someone submits the form -> Netlify Forms stores it and filters spam.
2. `netlify/functions/submission-created.js` runs automatically, writes the
   entry to `submissions/words/` or `submissions/examples/` on a new branch,
   and opens a **pull request** (only the form fields are written -- never the
   submitter's IP or browser info).
3. You review the PR on GitHub. Edit the JSON file in the PR to fix typos if
   needed. **Merge** to accept, **Close** to reject.
4. On merge, `.github/workflows/merge-submissions.yml` runs
   `scripts/merge_submissions.py`, which adds the entry to `lexicon.json` /
   `parallel_sentences.jsonl` (tagged `"source": "user_added"`), deletes the
   submission file, and pushes. Netlify redeploys and the translator has it.

### One-time setup

1. **GitHub token**: github.com -> Settings -> Developer settings ->
   Personal access tokens -> Fine-grained tokens -> Generate new token.
   - Repository access: *Only select repositories* -> `bravanese-translator-app`
   - Permissions: **Contents: Read and write**, **Pull requests: Read and write**
2. **Netlify**: Site configuration -> Environment variables -> add
   `GITHUB_TOKEN` = that token. Trigger a redeploy.
3. **Netlify Forms**: Site configuration -> Forms -> make sure form detection
   is enabled (the two forms `word-entries` and `example-entries` should
   appear after the deploy).
4. **GitHub Actions**: repo Settings -> Actions -> General -> Workflow
   permissions -> select **Read and write permissions** -> Save.

### Troubleshooting

- No PR appeared: Netlify dashboard -> Logs -> Functions ->
  `submission-created`. A 401/403 means the token or its permissions are
  wrong. The submission is still safe under Forms either way.
- Check Netlify's Forms -> "Spam submissions" tab if a real one got flagged.
- To merge by hand: `python scripts/merge_submissions.py`, or run the
  workflow from the Actions tab.
