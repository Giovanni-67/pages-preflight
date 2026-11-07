"""Check the entry HTML of a static artifact against its GitHub Pages URL path."""

import argparse
from html.parser import HTMLParser
import json
from pathlib import Path
import posixpath
import sys
from urllib.parse import unquote, urljoin, urlsplit


ORIGIN = 'https://pages-preflight.invalid'


class EntryHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.base = None
        self.references = []
        self.template_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag == 'template':
            self.template_depth += 1
        if self.template_depth:
            return

        attrs = dict(reversed(attrs))  # Browsers keep the first duplicate attribute.
        if tag == 'base' and self.base is None and 'href' in attrs:
            self.base = attrs['href'] or ''
        if tag == 'script' and attrs.get('src'):
            self.references.append(attrs['src'])
        if tag == 'link' and attrs.get('href'):
            relation = (attrs.get('rel') or '').lower().split()
            if {'stylesheet', 'modulepreload'}.intersection(relation):
                self.references.append(attrs['href'])

    def handle_endtag(self, tag):
        if tag == 'template' and self.template_depth:
            self.template_depth -= 1


def base_path(value):
    if (not value.startswith('/') or '//' in value
            or any(char in value for char in '?#\\%:')
            or any(ord(char) < 32 for char in value)
            or {'.', '..'}.intersection(value.split('/'))):
        raise argparse.ArgumentTypeError('use a URL path such as / or /my-repo/')
    return value.rstrip('/') + '/'


def find_file(root, relative):
    """Return exact, case, missing, or unsafe, plus the spelling found on disk."""
    current = root
    parts = relative.split('/')
    if any(not part or part in {'.', '..'} or ':' in part for part in parts):
        return 'missing', relative

    for part in parts:
        if not current.is_dir():
            return 'missing', relative
        entries = {entry.name: entry for entry in current.iterdir()}
        match = entries.get(part)
        if match is None:
            matches = [entry for name, entry in entries.items()
                       if name.casefold() == part.casefold()]
            if len(matches) != 1:
                return 'missing', relative
            match = matches[0]
        if not match.resolve().is_relative_to(root):
            return 'unsafe', relative
        current = match

    actual = current.relative_to(root).as_posix()
    if not current.is_file():
        return 'missing', relative
    return ('exact' if actual == relative else 'case'), actual


def finding(code, message, reference=None):
    return {'code': code, 'message': message, 'reference': reference}


def asset_path(reference, document_url, base):
    source = reference.strip().replace('\\', '/')
    url = urlsplit(source)
    if url.scheme or url.netloc or source.startswith('//'):
        return None
    resolved = urlsplit(urljoin(document_url, source))
    if f'{resolved.scheme}://{resolved.netloc}' != ORIGIN:
        return None

    decoded = unquote(resolved.path, errors='strict').replace('\\', '/')
    if any(ord(char) < 32 for char in decoded):
        raise ValueError('control character in asset path')
    normalized = posixpath.normpath('/' + decoded.lstrip('/'))
    if decoded.endswith('/') and normalized != '/':
        normalized += '/'
    if not normalized.startswith(base):
        return finding('outside-base', f'{reference!r} resolves outside {base!r}. '
                       'Set the build base to the published path and rebuild.', reference)
    return normalized[len(base):]


def check(root, base):
    entry_status, entry = find_file(root, 'index.html')
    if entry_status != 'exact':
        message = 'The artifact needs index.html at its root.'
        if entry_status == 'case':
            message += f' Rename {entry!r} to index.html.'
        if entry_status == 'unsafe':
            message += ' The existing entry points outside the artifact.'
        return 0, [finding('missing-entry', message)]

    parser = EntryHTML()
    parser.feed((root / entry).read_text(encoding='utf-8-sig'))
    parser.close()
    document_url = ORIGIN + base
    if parser.base is not None:
        try:
            document_url = urljoin(document_url, parser.base.replace('\\', '/'))
        except ValueError:
            return 0, [finding('invalid-url', f'Invalid HTML base URL {parser.base!r}.')]

    count = 0
    findings = []
    for reference in dict.fromkeys(parser.references):
        try:
            path = asset_path(reference, document_url, base)
        except ValueError:
            path = finding('invalid-url', f'Invalid asset URL {reference!r}.', reference)
        if path is None:
            continue
        count += 1
        if isinstance(path, dict):
            findings.append(path)
            continue

        status, actual = find_file(root, path)
        if status == 'missing':
            findings.append(finding('missing-asset', f'{reference!r} is missing from the artifact.', reference))
        elif status == 'case':
            findings.append(finding('asset-case', f'{reference!r} has the wrong letter case. '
                                    f'The artifact contains {actual!r}.', reference))
        elif status == 'unsafe':
            findings.append(finding('unsafe-file', f'{reference!r} points outside the artifact.', reference))
    return count, findings


def report(count, findings, base, output):
    if output == 'json':
        print(json.dumps({'base_path': base, 'checked': count, 'findings': findings}))
        return
    if not findings:
        print(f'Pages Preflight passed. Checked index.html and {count} local asset URL(s) for {base!r}.')
    for item in findings:
        message = item['message']
        if output == 'github':
            message = message.replace('%', '%25').replace('\r', '%0D').replace('\n', '%0A')
            print(f'::error title=Pages Preflight::{message}')
        else:
            print(f"{item['code']}: {message}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', required=True, type=Path, help='built site directory')
    parser.add_argument('--base-path', required=True, type=base_path, help='published URL path')
    parser.add_argument('--format', choices=('text', 'json', 'github'), default='text')
    args = parser.parse_args()
    try:
        root = args.directory.resolve(strict=True)
        if not root.is_dir():
            parser.error('--directory must point to a built site directory')
        count, findings = check(root, args.base_path)
    except (OSError, RuntimeError, UnicodeError) as error:
        parser.error(str(error))
    report(count, findings, args.base_path, args.format)
    return int(bool(findings))


if __name__ == '__main__':
    sys.exit(main())
