import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


CHECKER = (Path(__file__).resolve().parents[1]
           / 'plugins/pages-preflight/skills/pages-preflight/scripts/check.py')


class PreflightTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.site = Path(self.temp.name) / 'site'
        self.site.mkdir()

    def put(self, path, content=''):
        file = self.site / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(content, encoding='utf-8')

    def check(self, base='/demo/', output='json'):
        return subprocess.run(
            [sys.executable, str(CHECKER), '--directory', str(self.site),
             '--base-path', base, '--format', output],
            capture_output=True, text=True, encoding='utf-8', check=False,
        )

    def assert_codes(self, expected, *, base='/demo/'):
        result = self.check(base)
        self.assertEqual(result.returncode, int(bool(expected)), result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual([item['code'] for item in report['findings']], expected)
        return report

    def test_project_paths_support_relative_urls_queries_and_percent_encoding(self):
        self.put('index.html', '''<script src="/demo/assets/app.js?v=1#top"></script>
            <link rel="stylesheet" href="assets/site%20style.css">
            <link rel="modulepreload" href="assets/shared.js">
            <link rel="icon" href="/untracked.svg">
            <script src="https://cdn.example.org/script.js"></script>
            <script src="//cdn.example.org/other.js"></script>''')
        for path in ('assets/app.js', 'assets/site style.css', 'assets/shared.js'):
            self.put(path)
        self.assertEqual(self.assert_codes([])['checked'], 3)

    def test_root_site_and_base_element(self):
        self.put('index.html', '''<script src="app.js"></script>
            <base href="/scripts/"><base href="/ignored/">
            <link rel="stylesheet" href="/site.css">''')
        self.put('scripts/app.js')
        self.put('site.css')
        self.assert_codes([], base='/')

    def test_missing_entrypoint_distinguishes_case(self):
        self.put('Index.html')
        report = self.assert_codes(['missing-entry'])
        self.assertIn('Index.html', report['findings'][0]['message'])

    def test_reports_base_mismatch_missing_asset_and_wrong_case(self):
        self.put('index.html', '''<script src="/assets/main.js"></script>
            <link rel="stylesheet" href="/demo/absent.css">
            <script src="/demo/Assets/Main.js"></script>''')
        self.put('assets/main.js')
        report = self.assert_codes(['outside-base', 'missing-asset', 'asset-case'])
        self.assertEqual(report['findings'][0]['reference'], '/assets/main.js')
        self.assertIn('assets/main.js', report['findings'][2]['message'])

    def test_file_resolution_rejects_encoded_traversal_and_directories(self):
        self.put('index.html', '''<script src="/demo/%2e%2e/secret.js"></script>
            <script src="/demo/assets/"></script>''')
        self.put('assets/app.js')
        (self.site.parent / 'secret.js').write_text('outside', encoding='utf-8')
        self.assert_codes(['outside-base', 'missing-asset'])

    def test_symlink_outside_artifact_is_rejected(self):
        self.put('index.html', '<script src="linked.js"></script>')
        outside = self.site.parent / 'outside.js'
        outside.write_text('outside', encoding='utf-8')
        try:
            (self.site / 'linked.js').symlink_to(outside)
        except OSError as error:
            self.skipTest(f'symlink creation unavailable: {error}')
        self.assert_codes(['unsafe-file'])

    def test_invalid_base_returns_usage_error(self):
        self.put('index.html')
        result = self.check('https://example.com/demo/')
        self.assertEqual(result.returncode, 2)
        self.assertIn('--base-path', result.stderr)

    def test_github_output_keeps_untrusted_reference_in_one_annotation(self):
        self.put('index.html', '<script src="/outside&#10;::warning::x%0A.js"></script>')
        result = self.check(output='github')
        self.assertEqual(result.returncode, 1, result.stderr)
        lines = result.stdout.splitlines()
        self.assertEqual(len(lines), 1)
        self.assertTrue(lines[0].startswith('::error title=Pages Preflight::'))
        self.assertIn('%250A', lines[0])


if __name__ == '__main__':
    unittest.main()
