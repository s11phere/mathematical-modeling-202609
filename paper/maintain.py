#!/usr/bin/env python3
"""核验、更新清单和导出独立评审包；不运行算法或覆盖实验结果。"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parent.parent
ATTACHMENTS = ROOT / 'attachments'
PACKAGE = ATTACHMENTS / 'reviewer-attachments.zip'
HISTORY = '15bea8b'


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def files(folder: Path):
    """Exclude local environments, caches and generated archives from delivery."""
    for path in sorted(folder.rglob('*'), key=lambda p: p.relative_to(folder).as_posix()):
        relative = path.relative_to(folder)
        if any(part.startswith('.') or part == '__pycache__' for part in relative.parts):
            continue
        if path.suffix in ('.pyc', '.pyo', '.zip') or path.name.endswith('.zip.partial'):
            continue
        if path.is_symlink():
            raise ValueError(f'交付文件不能依赖外部符号链接：{path}')
        if path.is_file():
            yield path


def load_manifest(folder: Path):
    return json.loads((folder / 'SOURCE_MANIFEST.json').read_text(encoding='utf-8'))


def refresh():
    # Validate all required files before writing any manifest. Missing historical
    # evidence is not silently forgotten by generating a new list.
    prepared = []
    for number in range(1, 5):
        folder = ATTACHMENTS / f'Q{number}'
        data = load_manifest(folder)
        for relative in data['files']:
            if not (folder / relative).is_file():
                raise ValueError(f'清单中的文件缺失，先恢复或明确修订清单：Q{number}/{relative}')
        entries = {}
        for path in files(folder):
            relative = path.relative_to(folder).as_posix()
            if relative == 'SOURCE_MANIFEST.json':
                continue
            record = dict(data['files'].get(relative, {}))
            current = sha(path)
            if not record:
                record = {'source': 'current editable review package',
                          'adaptation': 'New maintained file; see Git history for changes.'}
            previous = record.get('sha256')
            if previous and previous != current:
                record.setdefault('package_revision_before_maintenance', previous)
                if record.get('adaptation') == 'none; byte-for-byte copy':
                    record['adaptation'] = ('Maintained presentation or reproduction file; '
                                            'source_sha256 retains the historical source hash.')
                record['maintenance_note'] = ('Updated in the editable package; original source/hash '
                                              'fields retain historical provenance. See Git history.')
            record.update(sha256=current, bytes=path.stat().st_size)
            entries[relative] = record
        data['files'] = entries
        data['historical_source_paths'] = {
            'git_revision': HISTORY,
            'note': 'Original B_locator paths are provenance at this revision, not runtime dependencies.'}
        prepared.append((folder / 'SOURCE_MANIFEST.json', data))
    for path, data in prepared:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    rows = [f'{sha(path)}  {path.relative_to(ATTACHMENTS).as_posix()}'
            for path in files(ATTACHMENTS) if path.name != 'SHA256SUMS.txt']
    (ATTACHMENTS / 'SHA256SUMS.txt').write_text('\n'.join(rows) + '\n', encoding='utf-8', newline='\n')
    print('已更新当前交付文件的清单；历史实验、来源哈希和统计结果未改写。')


def check():
    total = 0
    for number in range(1, 5):
        folder = ATTACHMENTS / f'Q{number}'
        expected = load_manifest(folder)['files']
        actual = {p.relative_to(folder).as_posix(): p for p in files(folder)
                  if p.name != 'SOURCE_MANIFEST.json'}
        if set(actual) != set(expected):
            raise ValueError(f'Q{number} 文件列表有变化：缺失 {set(expected)-set(actual)}；'
                             f'新增 {set(actual)-set(expected)}。确认后运行 refresh。')
        for relative, path in actual.items():
            if sha(path) != expected[relative]['sha256']:
                raise ValueError(f'Q{number}/{relative} 已修改。核验修改后运行 refresh；实验核验需另行执行。')
        total += len(actual)
    expected_root = {}
    for line in (ATTACHMENTS / 'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
        digest, relative = line.split('  ', 1)
        if relative in expected_root:
            raise ValueError(f'重复清单项：{relative}')
        expected_root[relative] = digest
    actual_root = {p.relative_to(ATTACHMENTS).as_posix(): sha(p)
                   for p in files(ATTACHMENTS) if p.name != 'SHA256SUMS.txt'}
    if actual_root != expected_root:
        raise ValueError('根目录 SHA256SUMS.txt 与当前文件不一致；确认修改后运行 refresh。')
    # Paper retains one preferred version of each image; package retains both.
    for figure in (ROOT / 'paper/figures').iterdir():
        if figure.suffix not in ('.png', '.pdf'):
            continue
        matches = list(ATTACHMENTS.glob(f'Q*/figures/{figure.name}'))
        if len(matches) != 1 or sha(figure) != sha(matches[0]):
            raise ValueError(f'论文图片与评审包未同步：{figure.name}')
    print(f'四题 {total} 份清单文件、全部交付哈希及论文插图一致；未核验算法性能。')


def pack():
    check()
    # Write atomically; the previous archive remains usable if packing fails.
    with tempfile.TemporaryDirectory(prefix='b-review-pack-') as temporary:
        candidate = Path(temporary) / PACKAGE.name
        with zipfile.ZipFile(candidate, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for path in files(ATTACHMENTS):
                archive.write(path, 'reviewer-attachments/' + path.relative_to(ATTACHMENTS).as_posix())
        with zipfile.ZipFile(candidate) as archive:
            if archive.testzip() is not None:
                raise ValueError('压缩包完整性检查失败')
        # Temporary folder and project may be on different filesystems.
        import shutil
        staging = PACKAGE.with_suffix('.zip.partial')
        try:
            shutil.copyfile(candidate, staging)
            staging.replace(PACKAGE)
        finally:
            staging.unlink(missing_ok=True)
    print(f'已生成 {PACKAGE}（{PACKAGE.stat().st_size / 1_000_000:.2f} MB）；不含本地环境或旧压缩包。')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['check', 'refresh', 'pack'])
    args = parser.parse_args()
    try:
        {'check': check, 'refresh': refresh, 'pack': pack}[args.action]()
    except (ValueError, OSError, KeyError) as error:
        parser.exit(1, f'{error}\n')


if __name__ == '__main__':
    main()
