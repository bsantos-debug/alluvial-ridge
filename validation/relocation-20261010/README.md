# Live project relocation

At 2026-10-10 00:25:50.471036 UTC, the original project directory moved from
`/data/data0/dominik-scratch/Shared/brnisant/alluvial-ridge` to
`/data/data0/brooke/alluvial-ridge`. The source path became a symlink to the
destination. All physical project files, including live outputs and caches,
are in the destination directory. Nothing was copied to a home directory.

The account's `fastwriters` group membership became available during the
session. `sg fastwriters` allowed creation of `/data/data0/brooke`, owned by
`brnisant:others` with mode 0755. Both paths are on device 2049. A self-targeting
symlink was created at the destination, then `renameat2(RENAME_EXCHANGE)`
atomically exchanged it with the source directory. The old path therefore
continued resolving throughout the move. Both parent directories were fsynced.

`move.json` records the exchange and its checks: the original directory inode
4430121513, seven directory/file inode anchors, five additional immutable
hashes, and all 43 source hashes in the frozen rebuild 002 manifest remained
unchanged. `runtime.json` preserves the independent observations before and
after the exchange. All 37 known processes retained their PID, start ticks,
arguments and working-directory inodes. All 34 model executable hashes
matched. All 175 writable file descriptors retained their descriptor number,
device, inode and relative target. The production driver retained its write
lock on suite-lock inode 67114101. All 34 model CPU counters advanced, and no
published numerical progress regressed. No process was signaled or restarted.

These checks establish filesystem and process continuity. They do not certify
completed numerical calculations or agreement with manuscript panels. Frozen
source, commands, manifests and original execution outcomes are preserved.

Keep the old path alias until all writers, including the older fine-grid
validation process, have ended and the first separate terminal relocation
audit and packaging have finished. Frozen rebuild 002's cached project root
can produce its documented final containment error after this move. Preserve
that outcome and use the explicit `--reconcile-relocation` procedure in
[docs/rebuild.md](../../docs/rebuild.md#relocating-a-project-with-running-calculations)
when the complete rebuild is terminal. Do not restart live or completed models
to hide the administrative discrepancy.
