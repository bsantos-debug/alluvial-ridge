#!/usr/bin/env python3
"""Check publication coverage with synthetic files; run no numerical model."""
import sys
sys.dont_write_bytecode = True

import contextlib
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import publication_inventory as publication


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True) + '\n').encode()


def put(package, name, data):
    path = package / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def fixture(package):
    source = {
        '.gitignore': put(package, 'workspace/.gitignore',
            b'/data/**/checkpoint.bin\n/validation/runs/**/checkpoint.bin\n/tmp/\n/report/build/\n'),
        'docs/panels.csv': put(package, 'workspace/docs/panels.csv', b'fixture initial ledger\n'),
        'scripts/example.py': put(package, 'workspace/scripts/example.py', b'# Not a numerical model.\n')}
    inputs = {name: put(package, 'workspace/' + name, b'SYNTHETIC FILE COVERAGE FIXTURE\n') for name in (
        'data/run01/checkpoint.bin', 'validation/runs/baseline250/checkpoint.bin',
        'data/_inputs/ridge', 'data/[brackets]*.bin')}
    output = {name: put(package, 'workspace/' + name, b'SYNTHETIC OUTPUT; NOT A FIGURE OR PDF\n') for name in (
        'report/report.pdf', 'figures/figure1.pdf', 'report/generated/panels.tex')}
    originals = {'rebuild_manifest.json': put(package, 'original/rebuild_manifest.json',
        encoded({'state': 'incomplete', 'scope': 'synthetic metadata; no simulation'}))}
    stamp = '2000-01-01T00:00:00Z'
    command = dict(name='report', state='incomplete', exit_code=2, utc_end=stamp,
        log='logs/report.log', log_sha256=put(package, 'logs/report.log', b'fixture only\n'),
        output_sha256=copy.deepcopy(output))
    record = dict(format=1, state='incomplete', utc_end=stamp,
        original_rebuild_state='incomplete', source_sha256=source, input_sha256=inputs,
        output_sha256=output, original_files_sha256=originals, commands=[command])
    prefix = 'renders/assessment-render-001/'
    archived = {'manifest-before.json': encoded(record),
        'panels.csv': b'fixture revised ledger; no scientific acceptance\n',
        'finalize_report.py': b'# Synthetic procedure identity.\n',
        'report-before.pdf': (package / 'workspace/report/report.pdf').read_bytes(),
        'report.pdf': b'SYNTHETIC REVISED PDF\n'}
    render_hashes = {prefix + name: put(package, prefix + name, data) for name, data in archived.items()}
    put(package, 'workspace/docs/panels.csv', archived['panels.csv'])
    output['report/report.pdf'] = put(package, 'workspace/report/report.pdf', archived['report.pdf'])
    record['commands'].append(dict(name='assessment-render-001', state='complete', exit_code=0,
        utc_end=stamp, log='logs/assessment-render-001.log',
        log_sha256=put(package, 'logs/assessment-render-001.log', b''),
        assessment_ledger_sha256=render_hashes[prefix + 'panels.csv'],
        procedure_sha256=render_hashes[prefix + 'finalize_report.py'], outputs_sha256=render_hashes))
    put(package, 'workspace/tmp/cache', b'excluded cache\n')
    put(package, 'workspace/report/build/cache', b'excluded TeX cache\n')
    put(package, 'postprocess_manifest.json', encoded(record))
    return record


def cli(package, output, expected=0):
    result = subprocess.run([sys.executable, '-B', str(ROOT / 'scripts/publication_inventory.py'),
        str(package), '--output', str(output)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert result.returncode == expected, (result.returncode, result.stdout, result.stderr)
    return result


@contextlib.contextmanager
def waiting_writer(package, writable_fd):
    if writable_fd:
        code = ('import sys; f=open(sys.argv[1], "ab"); '
                'print("ready",flush=True); sys.stdin.buffer.read(1)')
        args = [str(package / 'workspace/data/run01/checkpoint.bin')]
    else:
        code = 'import sys; print("ready",flush=True); sys.stdin.buffer.read(1)'
        args = ['--output', str(package)]
    child = subprocess.Popen([sys.executable, '-B', '-c', code] + args,
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        assert child.stdout.readline() == b'ready\n'
        yield
    finally:
        child.communicate(input=b'\n', timeout=10)
        assert child.returncode == 0


checks = []
(ROOT / 'tmp').mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(prefix='publication-inventory-', dir=str(ROOT / 'tmp')) as temporary:
    base = Path(temporary); package = base / 'package'; record = fixture(package)
    inventory_path = base / 'inventory.json'; cli(package, inventory_path)
    inventory = json.loads(inventory_path.read_bytes())
    pathspec = Path(str(inventory_path) + '.paths0')
    assert set(pathspec.read_bytes().decode().rstrip('\0').split('\0')) == set(inventory['files'])
    assert inventory['package_state'] == 'incomplete'
    override = inventory['assessment_ledger_override']
    assert override['initial_source_sha256'] != override['current_sha256']
    checkpoint_names = {'workspace/data/run01/checkpoint.bin',
                        'workspace/validation/runs/baseline250/checkpoint.bin'}
    assert set(inventory['checkpoint_ignore_rule_coverage']['required_checkpoints']) == checkpoint_names
    assert all(v['literal_rule_present'] for v in
        inventory['checkpoint_ignore_rule_coverage']['required_checkpoints'].values())
    checks.append('complete pathspec with checkpoints, executable, render archive and revised ledger')

    def refuses(label, mutate=None, fragment=None):
        target = base / ('bad-' + str(len(checks)))
        shutil.copytree(str(package), str(target))
        if mutate:
            mutate(target)
        try:
            publication.inventory(target)
        except (OSError, ValueError, KeyError) as error:
            if fragment:
                assert fragment in str(error), (label, str(error))
            checks.append(label)
            return
        raise AssertionError('accepted: ' + label)

    def change_manifest(target, operation):
        path = target / 'postprocess_manifest.json'
        value = json.loads(path.read_bytes()); operation(value); path.write_bytes(encoded(value))

    cp = 'workspace/data/run01/checkpoint.bin'
    refuses('missing checkpoint', lambda p: (p / cp).unlink(), 'missing')
    refuses('changed checkpoint', lambda p: (p / cp).write_bytes(b'changed'), 'changed file')
    refuses('unrecorded file', lambda p: put(p, 'unrecorded.txt', b'extra'), 'unrecorded')
    def symlink(p):
        (p / cp).unlink(); (p / cp).symlink_to(p / 'workspace/data/_inputs/ridge')
    refuses('evidence symlink', symlink, 'symlink')
    refuses('path traversal', lambda p: change_manifest(p,
        lambda m: m['input_sha256'].update({'../escape': '0' * 64})), 'manifest path')
    refuses('conflicting hash maps', lambda p: change_manifest(p,
        lambda m: m['input_sha256'].update({'docs/panels.csv': '0' * 64})), 'conflicting hashes')
    refuses('unbound current ledger', lambda p: (p / 'workspace/docs/panels.csv').write_bytes(b'changed'),
        'changed file')
    refuses('unbound retained ledger', lambda p: change_manifest(p,
        lambda m: m['commands'][-1].update(assessment_ledger_sha256='0' * 64)), 'ledger/procedure')
    refuses('nonterminal package', lambda p: change_manifest(p,
        lambda m: m.update(state='postprocessing')), 'not terminal')
    refuses('nonterminal command', lambda p: change_manifest(p,
        lambda m: m['commands'][0].update(state='running')), 'not terminal')
    for writable in (False, True):
        with waiting_writer(package, writable):
            try:
                publication.inventory(package)
            except ValueError as error:
                assert 'writer' in str(error) or 'writable package' in str(error), str(error)
            else:
                raise AssertionError('accepted live writer')
        checks.append('writable evidence descriptor' if writable else 'package-root output writer')

    before = inventory_path.read_bytes(); sidecar_before = pathspec.read_bytes()
    assert b'output already exists' in cli(package, inventory_path, 1).stderr
    assert inventory_path.read_bytes() == before and pathspec.read_bytes() == sidecar_before
    checks.append('existing outputs remain unchanged')
    dangling = base / 'dangling.json'; destination = base / 'never-created.json'
    dangling.symlink_to(destination)
    assert b'symlink' in cli(package, dangling, 1).stderr and not destination.exists()
    checks.append('dangling output symlink')
    assert b'outside package' in cli(package, package / 'new.json', 1).stderr
    checks.append('output inside package')

    # Real Git staging must retain literal special characters and ignored files.
    env = dict(os.environ, GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL='/dev/null', TMPDIR=str(base))
    def git(*args):
        return subprocess.check_output(['git', '-C', str(package)] + list(args), env=env,
                                       stderr=subprocess.PIPE)
    git('init', '--quiet'); git('add', '.')
    ordinary = set(git('ls-files', '-z').decode().rstrip('\0').split('\0'))
    assert checkpoint_names.isdisjoint(ordinary)
    git('read-tree', '--empty')  # Only this synthetic fixture's unpublished index.
    git('--literal-pathspecs', 'add', '--force', '--pathspec-from-file=' + str(pathspec), '--pathspec-file-nul')
    staged = set(git('ls-files', '-z').decode().rstrip('\0').split('\0'))
    assert staged == set(inventory['files'])
    tree = git('write-tree').decode().strip(); archive = base / 'index.tar'
    git('archive', '--format=tar', tree, '--output=' + str(archive))
    exported = base / 'index'; exported.mkdir()
    subprocess.check_call(['tar', '-xf', str(archive), '-C', str(exported)], env=env)
    exported_inventory = publication.inventory(exported)
    assert exported_inventory['files'] == inventory['files']
    assert exported_inventory['postprocess_manifest_sha256'] == inventory['postprocess_manifest_sha256']
    checks.append('forced literal staging and index export preserve every required byte')

    # Sparse synthetic bytes exercise the actual documented regular-Git boundary.
    sized = base / 'sized'; shutil.copytree(str(exported), str(sized))
    large = sized / 'workspace/data/size-fixture.bin'
    for size, expected in ((100 * publication.MIB, 0), (100 * publication.MIB + 1, 2)):
        with large.open('wb') as stream:
            stream.truncate(size)
        change_manifest(sized, lambda m: m['input_sha256'].update(
            {'data/size-fixture.bin': publication.digest(large)}))
        result_path = base / ('size-' + str(size) + '.json')
        cli(sized, result_path, expected)
        result = json.loads(result_path.read_bytes())
        assert result['files']['workspace/data/size-fixture.bin']['size_bytes'] == size
        assert result['transport']['regular_git_supported'] == (expected == 0)
        assert 'workspace/data/size-fixture.bin' in result['transport']['warning_over_50_MiB']
    checks.append('100 MiB accepted and 100 MiB plus one byte requires alternate transport')

print(json.dumps({'checks_passed': checks, 'count': len(checks),
    'scope': 'Synthetic file/provenance and Git staging fixtures only; no simulation, numerical completion, scientific acceptance or remote publication tested.'}, indent=2, sort_keys=True))
