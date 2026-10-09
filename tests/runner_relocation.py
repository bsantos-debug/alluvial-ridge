#!/usr/bin/env python3
"""Check live-child discovery and containment after a same-filesystem move."""
import contextlib
import importlib.util
import pathlib
import subprocess
import sys
import tempfile
from unittest import mock

sys.dont_write_bytecode = True
root = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('run_suite', str(root / 'scripts/run_suite.py'))
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


@contextlib.contextmanager
def child(cwd, flag, output):
    command = [sys.executable, '-B', '-c',
               'import sys; print("ready", flush=True); sys.stdin.buffer.read(1)', flag, str(output)]
    process = subprocess.Popen(command, cwd=str(cwd), stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        assert process.stdout.readline() == b'ready\n'
        yield process
    finally:
        process.communicate(input=b'\n', timeout=10)
        assert process.returncode == 0


def rejected(path):
    try:
        runner.inside(path)
    except ValueError:
        return
    raise AssertionError('accepted path outside the project: ' + str(path))


(root / 'tmp').mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(prefix='runner-relocation-', dir=str(root / 'tmp')) as temporary:
    base = pathlib.Path(temporary)
    old = base / 'old'
    new = base / 'new'
    old.mkdir()
    for name in ('absolute', 'relative', 'different', 'unrelated'):
        (old / name).mkdir()
    outside = base / 'new-sibling'
    outside.mkdir()
    (old / 'escape').symlink_to(outside, target_is_directory=True)
    runner.ROOT = old  # Simulate a runner loaded before the move.

    with contextlib.ExitStack() as children:
        absolute = children.enter_context(child(old, '--out', old / 'absolute'))
        relative = children.enter_context(child(old, '--out', 'relative'))
        different = children.enter_context(child(old, '--out', old / 'different'))
        children.enter_context(child(old, '--unrelated', old / 'unrelated'))
        assert runner.live_case(old / 'absolute') == absolute.pid
        old.rename(new)
        old.symlink_to(new, target_is_directory=True)

        assert runner.inside('absolute') == new / 'absolute'
        assert runner.inside(old / 'absolute') == new / 'absolute'
        assert runner.inside(new / 'absolute') == new / 'absolute'
        rejected(outside)
        rejected('escape/result')
        assert runner.live_case(new / 'absolute') == absolute.pid
        assert runner.live_case(old / 'absolute') == absolute.pid
        assert runner.live_case(new / 'relative') == relative.pid
        assert runner.live_case(new / 'different') == different.pid
        assert runner.live_case(new / 'unrelated') is None
        assert runner.live_case(new / 'absent') is None

        # A changed identity between the two /proc reads must not count as live.
        real_identity = runner.process_identity
        reads = []

        def changing_identity(pid):
            if pid == absolute.pid:
                reads.append(pid)
                return 'changed' if len(reads) > 1 else real_identity(pid)
            return real_identity(pid)

        with mock.patch.object(runner, 'process_identity', side_effect=changing_identity):
            assert runner.live_case(new / 'absolute') is None
        assert len(reads) == 2

        runner.ROOT = pathlib.Path('/data/data8/project')
        rejected('output')
        runner.ROOT = old

    assert runner.live_case(new / 'absolute') is None
    assert runner.live_case(new / 'relative') is None

print('runner relocation: old alias, relative output, process identity, containment pass')
