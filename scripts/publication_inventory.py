#!/usr/bin/env python3
"""Verify a terminal saved-data package for publication; never stage or upload it."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import sys

sys.dont_write_bytecode = True
from finalize_report import child, digest, no_live_writers, terminal

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {'.git', 'workspace/tmp', 'workspace/report/build'}
MIB = 1024 * 1024


def require(condition, message):
    if not condition:
        raise ValueError(message)


def relative(name):
    require(isinstance(name, str) and name and '\0' not in name, 'invalid manifest path')
    p = PurePosixPath(name)
    require(not p.is_absolute() and '..' not in p.parts and str(p) == name and name != '.',
            'noncanonical manifest path: ' + name)
    return name


def add(required, name, expected):
    relative(name)
    require(not any(name == x or name.startswith(x + '/') for x in EXCLUDED),
            'required evidence lies in an excluded directory: ' + name)
    require(isinstance(expected, str) and re.fullmatch('[0-9a-f]{64}', expected), 'invalid SHA256: ' + name)
    require(name not in required or required[name] == expected, 'conflicting hashes: ' + name)
    required[name] = expected


def required_files(package, record, manifest_hash):
    required = {}; renders = []
    require(record['format'] == 1, 'unsupported postprocess manifest format')
    terminal(record, 'package')
    for command in record['commands']:
        terminal(command, 'command ' + command['name'])
        add(required, command['log'], command['log_sha256'])
        if command['name'].startswith('assessment-render-'):
            name = command['name']
            require(re.fullmatch('assessment-render-[0-9]{3,}', name), 'invalid assessment render name')
            outputs = command['outputs_sha256']; prefix = 'renders/' + name + '/'
            require(outputs and all(n.startswith(prefix) for n in outputs), 'render archive path differs')
            for path, expected in outputs.items():
                add(required, path, expected)
            require(outputs[prefix + 'panels.csv'] == command['assessment_ledger_sha256'] and
                    outputs[prefix + 'finalize_report.py'] == command['procedure_sha256'],
                    'assessment ledger/procedure binding differs')
            require(prefix + 'manifest-before.json' in outputs, 'missing preceding render manifest')
            renders.append(dict(command=name, ledger=prefix + 'panels.csv',
                                manifest_before=prefix + 'manifest-before.json',
                                sha256=command['assessment_ledger_sha256']))
        else:
            require('assessment_ledger_sha256' not in command and 'outputs_sha256' not in command,
                    'unexpected assessment metadata')
    require(len({r['command'] for r in renders}) == len(renders), 'duplicate assessment render')
    source = record['source_sha256']; initial = source['docs/panels.csv']
    override = None
    if renders:
        latest = renders[-1]
        override = dict(initial_source_sha256=initial, current_sha256=latest['sha256'],
                        command=latest['command'], retained_ledger=latest['ledger'],
                        retained_preceding_manifest=latest['manifest_before'])
    for field, prefix in (('source_sha256', 'workspace/'), ('input_sha256', 'workspace/'),
                          ('output_sha256', 'workspace/'), ('original_files_sha256', 'original/')):
        require(isinstance(record[field], dict) and record[field], 'missing manifest section: ' + field)
        for name, expected in record[field].items():
            relative(name)
            if field == 'source_sha256' and name == 'docs/panels.csv' and override:
                expected = override['current_sha256']
            add(required, prefix + name, expected)
    add(required, 'postprocess_manifest.json', manifest_hash)
    return required, renders, override


def package_files(package):
    found = set(); excluded = []
    def walk_error(error):
        raise error
    for folder, directories, names in os.walk(str(package), followlinks=False, onerror=walk_error):
        for name in list(directories):
            path = Path(folder) / name; rel = path.relative_to(package).as_posix()
            require(not path.is_symlink(), 'symlink directory: ' + rel)
            if rel in EXCLUDED:
                directories.remove(name); excluded.append(rel)
        for name in names:
            path = Path(folder) / name; rel = path.relative_to(package).as_posix()
            require(not path.is_symlink() and path.is_file(), 'nonregular or symlink file: ' + rel)
            found.add(rel)
    return found, sorted(excluded)


def checkpoint_rules(package, files):
    # This deliberately recognizes only the two documented literal rules. It
    # is not a Git ignore evaluator and does not consult any repository index.
    ignore = 'workspace/.gitignore'
    lines = (child(package, ignore).read_text().splitlines() if ignore in files else [])
    rules = ('/data/**/checkpoint.bin', '/validation/runs/**/checkpoint.bin')
    present = [rule for rule in rules if rule in lines]
    checkpoints = {}
    for name in sorted(files):
        p = PurePosixPath(name)
        if p.name != 'checkpoint.bin' or not name.startswith(('workspace/data/', 'workspace/validation/runs/')):
            continue
        rule = rules[0] if name.startswith('workspace/data/') else rules[1]
        checkpoints[name] = dict(included_in_pathspec=True, literal_rule_present=rule in present,
                                 documented_rule=rule, rule_file=ignore)
    return dict(scope='Required checkpoint coverage and presence of two literal packaged ignore rules only; not full Git ignore evaluation or index verification. The pathspec includes every required file regardless of ignore rules.',
                literal_rules_present=present, required_checkpoints=checkpoints)


def no_package_writers(package):
    no_live_writers(package)
    # Supplement the inherited command-target check with visible writable
    # handles. Disappearing or inaccessible processes cannot be inspected.
    for process in Path('/proc').iterdir():
        if not process.name.isdigit():
            continue
        try:
            descriptors = list((process / 'fd').iterdir())
        except OSError:
            continue
        for descriptor in descriptors:
            try:
                target = os.readlink(str(descriptor))
                if not target.startswith('/'):
                    continue
                target = Path(target).resolve()
                if target != package and package not in target.parents:
                    continue
                info = (process / 'fdinfo' / descriptor.name).read_text()
                flags = next(int(line.split()[1], 8) for line in info.splitlines()
                             if line.startswith('flags:'))
            except (OSError, UnicodeError, ValueError, StopIteration):
                continue
            require(flags & os.O_ACCMODE not in (os.O_WRONLY, os.O_RDWR),
                    'visible writable package handle: PID {} FD {}'.format(process.name, descriptor.name))


def inventory(package):
    manifest_path = child(package, 'postprocess_manifest.json')
    manifest_hash = digest(manifest_path); blob = manifest_path.read_bytes()
    require(hashlib.sha256(blob).hexdigest() == manifest_hash, 'manifest changed during read')
    record = json.loads(blob)
    required, renders, override = required_files(package, record, manifest_hash)
    no_package_writers(package)
    found, excluded = package_files(package)
    require(found == set(required), 'unrecorded/missing files: extra={} missing={}'.format(
        sorted(found-set(required)), sorted(set(required)-found)))
    files = {}; metadata = {}
    for name, expected in sorted(required.items()):
        path = child(package, name); before = path.stat(); actual = digest(path); after = path.stat()
        state = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns)
        require(state(before) == state(after) and actual == expected, 'changed file: ' + name)
        files[name] = dict(size_bytes=after.st_size, sha256=actual)
        metadata[name] = state(after)
    for render in renders:
        previous = json.loads(child(package, render['manifest_before']).read_bytes())
        terminal(previous, 'preceding assessment manifest')
        require(previous['source_sha256']['docs/panels.csv'] == record['source_sha256']['docs/panels.csv'],
                'initial assessment ledger record changed')
        require(files[render['ledger']]['sha256'] == render['sha256'], 'retained assessment ledger differs')
    coverage = checkpoint_rules(package, files)
    no_package_writers(package)
    require(package_files(package)[0] == found, 'package file set changed during inventory')
    for name, expected in metadata.items():
        p = child(package, name); s = p.stat()
        require((s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns) == expected, 'file changed during inventory: ' + name)
    require(digest(manifest_path) == manifest_hash, 'package manifest changed during inventory')
    oversized = [name for name in files if files[name]['size_bytes'] > 100*MIB]
    warnings = [name for name in files if files[name]['size_bytes'] > 50*MIB]
    return dict(format=1, status='verified', observed_utc=datetime.datetime.utcnow().isoformat()+'Z',
                package_state=record['state'], original_rebuild_state=record['original_rebuild_state'],
                postprocess_manifest_sha256=manifest_hash, files=files, file_count=len(files),
                total_bytes=sum(f['size_bytes'] for f in files.values()),
                assessment_ledger_override=override, retained_assessment_renders=renders,
                writer_observation_scope='Two bounded /proc observations of inherited output-target flags and visible writable file handles under the package. Inaccessible or disappearing processes/handles are skipped; this is not an exclusive host-wide write lock.',
                excluded_directories_present=excluded, allowed_excluded_directories=sorted(EXCLUDED),
                checkpoint_ignore_rule_coverage=coverage,
                transport=dict(regular_git_supported=not oversized, over_100_MiB=oversized,
                               warning_over_50_MiB=warnings,
                               regular_git_max_bytes=100*MIB, warning_threshold_bytes=50*MIB,
                               release_asset_strictly_less_than_bytes=2*1024*MIB, release_max_assets=1000,
                               files_at_or_above_release_asset_limit=[n for n in files if files[n]['size_bytes'] >= 2*1024*MIB],
                               scope='Size preflight only. No archive splitting, release upload, Git index, remote contents or repository-total suitability is verified.'),
                scope='Manifest-bound publication inventory, not scientific acceptance or a new numerical/terminal audit. Incomplete terminal packages retain their recorded failures. No finalizer, model, renderer, upload or Git staging is invoked.')


def output_paths(package, output):
    require(str(ROOT).startswith(tuple('/data/data%d/' % n for n in range(8))), 'project must be on /data/data[n]')
    # A packaged copy may check its own package and write beside it, matching
    # the finalizer's portable packaged-workspace convention.
    base = package.parent if ROOT == package / 'workspace' else ROOT
    require(package == ROOT.parent and ROOT == package / 'workspace' or ROOT in package.parents,
            'package must remain inside this project (or contain this packaged workspace)')
    paths = [output, output.with_name(output.name + '.paths0')]
    for path in paths:
        require(base in path.parents and path != package and package not in path.parents,
                'output must be project-local and outside package')
        require(not path.exists() and not path.is_symlink(), 'output already exists: ' + str(path))
        require(path.parent.is_dir(), 'output parent must already exist: ' + str(path.parent))
    require(paths[0] != paths[1], 'output paths coincide')
    return paths


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        require(not args.package.is_symlink(), 'package cannot be a symlink')
        require(not any(p.is_symlink() for p in [args.output] + list(args.output.parents)),
                'output path cannot contain a symlink')
        package = args.package.resolve(); output = args.output.resolve()
        paths = output_paths(package, output)
        result = inventory(package)
        pathspec = b''.join(name.encode('utf-8')+b'\0' for name in sorted(result['files']))
        result['pathspec'] = dict(format='NUL-delimited UTF-8 package-relative literal paths',
                                  sha256=hashlib.sha256(pathspec).hexdigest(), size_bytes=len(pathspec))
        data = (json.dumps(result, indent=2, sort_keys=True, allow_nan=False)+'\n').encode()
        # Both creations are exclusive; a refusal never overwrites old evidence.
        created = []
        try:
            for path, content in ((paths[1], pathspec), (paths[0], data)):
                with path.open('xb') as stream:
                    created.append(path); stream.write(content); stream.flush(); os.fsync(stream.fileno())
        except OSError:
            for path in created:
                path.unlink()
            raise
        code = 0 if result['transport']['regular_git_supported'] else 2
        print(json.dumps(dict(status='verified', package_state=result['package_state'],
                              file_count=result['file_count'], total_bytes=result['total_bytes'],
                              inventory=str(paths[0]), pathspec=str(paths[1]),
                              sha256=hashlib.sha256(data).hexdigest(), exit_code=code,
                              scope=result['scope']), sort_keys=True))
        return code
    except (OSError, ValueError, KeyError, TypeError, IndexError) as error:
        print('REFUSED: ' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
