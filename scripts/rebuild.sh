#!/usr/bin/env bash
# Recompute in a new staged workspace; preserve the working checkout and live runs.
set -euo pipefail
cd "$(dirname "$0")/.."
case "$PWD/" in
  /data/data[0-7]/*) ;;
  *) echo "rebuild must run from a /data/data[n] project" >&2; exit 1 ;;
esac
source scripts/environment.sh
exec python3 - "$@" <<'PY'
import datetime, hashlib, json, os, pathlib, re, shutil, signal, subprocess, sys, time

root = pathlib.Path.cwd().resolve()
stamp = datetime.datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
if len(sys.argv) > 2:
    raise SystemExit('usage: bash scripts/rebuild.sh [new-project-local-artifact-directory]')
artifact = (root / (sys.argv[1] if len(sys.argv) == 2 else 'tmp/rebuild-' + stamp)).resolve()
if root not in artifact.parents or not re.match(r'^/data/data[0-7]/', str(root) + '/'):
    raise SystemExit('rebuild artifacts must remain inside this /data project')
if artifact.exists():
    raise SystemExit('choose a new artifact directory; existing rebuilds are preserved: ' + str(artifact))
artifact.mkdir(parents=True)
workspace = artifact / 'workspace'
workspace.mkdir()
manifest = {'utc_start': stamp, 'state': 'preparing', 'workspace': str(workspace), 'source_sha256': {}, 'stages': []}
active = {}
interrupted = False


def terminate_active():
    for item in list(active.values()):
        # Each stage owns its process group, so existing independent runs are untouched.
        try:
            os.killpg(item['process'].pid, signal.SIGTERM)
        except ProcessLookupError:
            pass


def stop(signum, unused):
    global interrupted
    interrupted = True
    terminate_active()


signal.signal(signal.SIGINT, stop)
signal.signal(signal.SIGTERM, stop)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save():
    temporary = artifact / 'rebuild_manifest.tmp'
    temporary.write_text(json.dumps(manifest, indent=2) + '\n')
    temporary.replace(artifact / 'rebuild_manifest.json')


def start_stage(name, command):
    if interrupted:
        raise RuntimeError('rebuild interrupted before ' + name)
    record = {'name': name, 'command': command, 'state': 'running',
              'utc_start': datetime.datetime.utcnow().isoformat() + 'Z'}
    manifest['stages'].append(record)
    logpath = artifact / (name + '.log')
    started = time.monotonic()
    print('rebuild stage: ' + name, flush=True)
    try:
        with logpath.open('w') as log:
            process = subprocess.Popen(command, cwd=str(workspace), env=env, stdout=log,
                                       stderr=subprocess.STDOUT, start_new_session=True)
    except OSError as error:
        record.update(state='failed', error=str(error), exit_code=None)
        save()
        raise
    active[name] = {'process': process, 'record': record, 'started': started, 'logpath': logpath}
    if interrupted:
        terminate_active()
    record['pid'] = process.pid
    save()


def finish_stage(name):
    item = active[name]
    record, logpath = item['record'], item['logpath']
    record['exit_code'] = item['process'].wait()
    if record['exit_code']:
        # A failed driver can leave its numerical children alive.
        try:
            os.killpg(item['process'].pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    del active[name]
    state = 'complete' if record['exit_code'] == 0 else 'interrupted' if interrupted else 'failed'
    record.update(state=state, wall_seconds=time.monotonic() - item['started'],
                  utc_end=datetime.datetime.utcnow().isoformat() + 'Z',
                  log=str(logpath.relative_to(artifact)), log_sha256=digest(logpath))
    save()
    print('rebuild stage {} exit={}'.format(name, record['exit_code']), flush=True)
    return record['exit_code'] == 0


def stage(name, command):
    start_stage(name, command)
    passed = finish_stage(name)
    if interrupted:
        raise RuntimeError('rebuild interrupted during ' + name)
    return passed


def tex(text):
    replacements = {'\\': r'\textbackslash{}', '_': r'\_', '&': r'\&', '%': r'\%', '#': r'\#',
                    '{': r'\{', '}': r'\}', '$': r'\$', '^': r'\textasciicircum{}', '~': r'\textasciitilde{}'}
    return ''.join(replacements.get(char, char) for char in str(text))


try:
    inputs = []
    for folder in ('src', 'tests', 'config', 'scripts', 'docs'):
        inputs.extend(path for path in (root / folder).rglob('*') if path.is_file() and '__pycache__' not in path.parts)
    inputs.extend(path for path in (root / 'report').iterdir() if path.is_file() and path.suffix in ('.tex', '.bib', '.py', '.sh'))
    # This is maintained implementation prose, despite its directory name.
    implementation = root / 'report/generated/implementation.tex'
    if implementation.exists():
        inputs.append(implementation)
    inputs.extend(root / name for name in ('Makefile', 'README.md', 'AGENTS.md', 'brad-lipovsky-academic-style-guide.md') if (root / name).is_file())
    for source in sorted(inputs):
        if root not in source.resolve().parents:
            raise ValueError('source symlink leaves the project: ' + str(source))
        name = source.relative_to(root)
        target = workspace / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(source), str(target))
        manifest['source_sha256'][str(name)] = digest(target)
    env = dict(os.environ)
    for key, folder in [('TMPDIR', 'tmp'), ('XDG_CACHE_HOME', 'tmp/cache'), ('MPLCONFIGDIR', 'tmp/matplotlib'),
                        ('PYTHONPYCACHEPREFIX', 'tmp/pycache'), ('CCACHE_DIR', 'tmp/cache/ccache')]:
        path = workspace / folder
        path.mkdir(parents=True, exist_ok=True)
        env[key] = str(path)
    jobs = int(os.environ.get('RIDGE_JOBS', '8'))
    validation_jobs = int(os.environ.get('RIDGE_VALIDATION_JOBS', '2'))
    if jobs < 1 or validation_jobs not in (1, 2):
        raise ValueError('RIDGE_JOBS must be positive; RIDGE_VALIDATION_JOBS must be 1 or 2')
    manifest['state'] = 'running'
    save()
    python = sys.executable
    if not stage('prepare', [python, 'scripts/run_suite.py', '--prepare-only', '--jobs', str(jobs), '--data-root', 'data', '--floods', '580']):
        raise RuntimeError('source compilation failed before numerical checks')
    # Check the exact executable later used for all 31 cases.
    (workspace / 'build').mkdir()
    shutil.copy2(str(workspace / 'data/_inputs/ridge'), str(workspace / 'build/ridge'))
    (workspace / 'validation').mkdir()
    checks = stage('checks', ['make', '-j4', '-o', 'build/ridge', 'check'])
    shutil.copy2(str(artifact / 'checks.log'), str(workspace / 'validation/kernel.txt'))
    if digest(workspace / 'build/ridge') != digest(workspace / 'data/_inputs/ridge'):
        raise RuntimeError('checks rebuilt a different executable from the frozen suite binary')
    if checks:
        start_stage('sensitivity', [python, 'scripts/validate_runs.py', '--output', 'validation/runs',
                                   '--executable', 'data/_inputs/ridge', '--jobs', str(validation_jobs),
                                   '--cases', 'baseline250,coarse500,fine125,time250_cfl02,tau005,tau020,concentration_half,concentration_double'])
        start_stage('simulations', [python, 'scripts/run_suite.py', '--resume', '--jobs', str(jobs), '--data-root', 'data', '--floods', '580'])
        while active:
            for name in list(active):
                if active[name]['process'].poll() is not None:
                    finish_stage(name)
            if active:
                time.sleep(1)
        if interrupted:
            raise RuntimeError('rebuild interrupted during numerical calculations')
    else:
        manifest['stages'].append({'name': 'simulations', 'state': 'skipped', 'reason': 'required implementation checks failed'})
        save()
    # Missing/failed simulations remain visible as incomplete panels and comparisons.
    stage('figures', [python, 'scripts/plot.py', '--data-root', 'data', '--output', 'figures', '--strict'])
    stage('comparison', [python, 'scripts/compare.py', '--data-root', 'data', '--figures', 'figures', '--output', 'figures', '--strict'])
    generated = workspace / 'report/generated'
    generated.mkdir(parents=True, exist_ok=True)
    validation = ['The clean rebuild ran the implementation checks with exit code ' + str(next(x['exit_code'] for x in manifest['stages'] if x['name'] == 'checks')) + '.\\par\n',
                  'The complete command output is retained in \\texttt{validation/kernel.txt}; its named tests delimit the verification scope.\\par\n']
    sensitivity = workspace / 'validation/runs/comparison.json'
    if sensitivity.exists():
        results = json.loads(sensitivity.read_text())['cases']
        validation.append('Fresh first-flood sensitivity calculations:\\par\n\\begin{longtable}{ll}Case & Recorded state \\\\ \\hline\n')
        for name, record in sorted(results.items()):
            validation.append(tex(name) + ' & ' + tex(record['state']) + r' \\' + '\n')
            if record['state'] == 'complete':
                budgets = record.get('budgets', {})
                for key, value in budgets.items():
                    if 'over_input' in key:
                        validation.append(tex(key) + ' & ' + tex(value) + r' \\' + '\n')
        validation.append('\\end{longtable}\nSpatial and temporal differences are recorded in \\texttt{validation/runs/comparison.json}; completion does not by itself establish grid independence.\n')
    else:
        validation.append('Full first-flood sensitivity evidence was not generated by this rebuild.\n')
    (generated / 'validation.tex').write_text(''.join(validation))
    lines = ['This report was generated in a fresh staged workspace. Frozen source, compiler command, executable, inputs, case histories, and hashes are recorded in \\texttt{data/suite\\_manifest.json}.\\par\n',
             'Stages before PDF compilation:\\par\n\\begin{tabular}{lll}Stage & State & Exit code \\\\ \\hline\n']
    for record in manifest['stages']:
        lines.append(tex(record['name']) + ' & ' + tex(record['state']) + ' & ' + tex(record.get('exit_code', 'not run')) + r' \\' + '\n')
    lines.append('\\end{tabular}\\par\nThe external \\texttt{rebuild\\_manifest.json} records the subsequent PDF build outcome. Failed stages remain failures even when a report documenting them compiles.\n')
    (generated / 'rebuild.tex').write_text(''.join(lines))
    stage('report', ['bash', 'report/build.sh'])
    pdf = workspace / 'report/report.pdf'
    if not pdf.is_file() or not pdf.read_bytes().startswith(b'%PDF-'):
        raise RuntimeError('the report stage did not produce a PDF')
    manifest['pdf'] = str(pdf.relative_to(artifact))
    manifest['pdf_sha256'] = digest(pdf)
    for name, expected in manifest['source_sha256'].items():
        if digest(workspace / name) != expected:
            raise RuntimeError('a staged source changed during the rebuild: ' + name)
    complete = all(record['state'] == 'complete' for record in manifest['stages'])
    manifest.update(state='complete' if complete else 'incomplete', utc_end=datetime.datetime.utcnow().isoformat() + 'Z')
    save()
    print('rebuild {}: {}'.format(manifest['state'], artifact), flush=True)
    raise SystemExit(0 if complete else 1)
except Exception as error:
    terminate_active()
    for name in list(active):
        finish_stage(name)
    manifest.update(state='interrupted' if interrupted else 'failed', error=str(error),
                    utc_end=datetime.datetime.utcnow().isoformat() + 'Z')
    save()
    print('ERROR: ' + str(error), flush=True)
    raise SystemExit(1)
PY
