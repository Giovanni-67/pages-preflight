# Pages Preflight

Catch a blank GitHub Pages site before you publish it. Pages Preflight checks the files your build produced against the URL where Pages will serve them. Use it as a GitHub Action, a Codex plugin, or a local command.

```text
outside-base: '/assets/app.js' resolves outside '/demo/'. Set the build base to the published path and rebuild.
```

The checker catches a missing `index.html`, missing scripts and stylesheets, and mismatches in URL prefixes or letter case. It also checks module preloads. It runs offline and uses Python 3.10 or newer with no packages to install.

## GitHub Action

Add this step after your build and before `actions/upload-pages-artifact`. Match `directory` to the upload step and `base-path` to the public URL. Use `/` for a root site. If your workflow uses `actions/configure-pages` with `id: pages`, you can use `${{ steps.pages.outputs.base_path || '/' }}` as the path.

```yaml
- name: Check the Pages build
  uses: Giovanni-67/pages-preflight@v0.1.0
  with:
    directory: dist
    base-path: /my-repo/
```

The Action requires Bash and Python 3.10+ on the runner. A finding fails the step and appears as a GitHub Actions annotation.

## Codex plugin

```sh
codex plugin marketplace add Giovanni-67/pages-preflight --ref v0.1.0
codex plugin add pages-preflight@pages-preflight-tools
```

Open a new Codex chat and ask `$pages-preflight Check my built site for GitHub Pages`. The skill identifies your publish path, runs the checker, and explains the result. To install just the skill, copy `plugins/pages-preflight/skills/pages-preflight/` into `.agents/skills/` in the project where you want to use it.

## Try it locally

From the root of a clone, run the broken example and then the fixed one:

```sh
python plugins/pages-preflight/skills/pages-preflight/scripts/check.py --directory examples/broken --base-path /demo/
python plugins/pages-preflight/skills/pages-preflight/scripts/check.py --directory examples/fixed --base-path /demo/
```

Pass `--format json` for machine-readable findings. The exit codes are `0` for a pass, `1` for findings, and `2` for invalid input or a read error. Run the tests with `python -m unittest discover -s tests -v`.

Version 0.1 checks the artifact's entry page and its direct local scripts, stylesheets, and module preloads. Browser runtime errors, other pages, and requests made inside JavaScript or CSS need a separate check.
