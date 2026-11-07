---
name: pages-preflight
description: Diagnose a blank GitHub Pages site, missing JS or CSS after deployment, or a wrong Pages base path. Check a built static artifact before publishing or use its findings to guide a scoped fix.
---

# Pages Preflight

Find the actual publish directory and base path before checking. For a Pages workflow, read the artifact upload step and the build command. If the workflow passes `actions/configure-pages`'s `base_path` output, use that value when known. A project site at `OWNER.github.io/REPO/` normally uses `/REPO/`. A user site or a site served from the root of its own custom domain uses `/`. Use the actual published URL if it differs. If the destination cannot be determined, ask for it.

Use the existing build output. If no artifact exists, inspect the build command and run it only when building the project is within the user's request. Run the bundled `scripts/check.py` with Python 3.10 or newer. Resolve the script path relative to this skill folder and the artifact path relative to the project. Quote both paths.

```sh
python "/absolute/path/to/skill/scripts/check.py" --directory "dist" --base-path /REPO/ --format json
```

Exit 0 means the entry HTML and supported local references passed. Exit 1 means there are findings. Exit 2 means the checker could not run. Report the exact URL and cause. For `outside-base`, inspect the build configuration or workflow override. For `asset-case`, compare the reported spelling with the actual file and Git index. For `missing-entry` or `missing-asset`, confirm the build and upload paths. Rebuild and run the same check after any requested fix.

The checker covers `index.html` and its direct local scripts, stylesheets, and module preloads. If it passes and the site is still blank, use the browser console and Network panel to investigate runtime errors or failed requests. Only change source, workflow, or deployment settings within the user's requested scope.
