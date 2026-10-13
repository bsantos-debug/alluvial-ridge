# Assessment evidence, 12 October 2026

This directory preserves useful evidence that was untracked when the progress
assessment began. It does not contain new simulation results.

- `legacy-validation-runs.tar.xz`: all 30 files from `validation/runs`, including
  scientific checkpoints. These older outputs have mixed completion status and
  a different executable identity from corrected rebuild 002. The old comparison
  marks fine125 and time250_cfl02 incomplete. They are historical evidence, not
  the source of the corrected first-flood values in the assessment.
- `unique-renderer-checks.tar.xz`: 20 unique files from
  `validation/.threshold-render-check-sg7jvor8`. This includes positive and
  deliberately invalid report-input fixtures, earlier renderer versions, and
  their recorded checks. Twenty-six files identical to existing project files
  were omitted. The old fixtures are not simulation results or new test passes.
- `inventory.json`: original paths, member hashes, archive hashes, and a
  timestamped read-only coverage observation of 31 live production summaries.
  The changing live workspace is not uploaded. Coverage does not establish
  physical validity or completion of manuscript sampling windows.
- `check.py` and `checks.json`: independently recheck 30 first-flood bindings,
  frozen preview input bindings, common-13-flood alpha statistics, all 13 panel
  identities, and both preservation archives. Run from any directory with
  `python3 -B validation/assessment-evidence-20261012/check.py` (path relative
  to project root). This reads existing files and prints JSON; no solver runs.

Original untracked directories remain untouched. Tar ownership and timestamps
are normalized; member contents are unchanged. No credentials, executables,
compiled build products, or downloaded publication files were added to these
archives. Scientific checkpoints are retained as evidence.

The publication includes the existing tracked project and frozen data, earlier
reports, `progress_assessment.tex`, `progress_assessment.pdf`, the isolated
report build script, and this evidence directory. Temporary live workspaces,
duplicate fixtures, local build/cache directories, and downloaded sources stay
local. No claim is made that the entire unfinished live production suite has
been uploaded or that the original 580-flood reproduction is complete.

Assessment compilation:

    bash report/build_progress_assessment.sh

The script confines temporary files and TeX caches to the project and preserves
`report/report.pdf`. Main assessment pages 1–4; appendix pages 5–6. The two
existing figures are included without regenerating the project.

Before publication, a targeted private-key/GitHub-token/AWS-access-key pattern
scan examined 1,100 current files and archive members without matches. This is
not an exhaustive secret or provenance audit. At preflight, all 528 historical
Git blobs were below 50 MiB (largest 20,432,360 bytes). The preserved legacy
archive is 11,931,820 bytes; no new upload file approaches the 100 MiB limit.

A separate scan of all 528 historical Git blobs found no matching credential
patterns and no ELF executables. No original deliverables were overwritten.
