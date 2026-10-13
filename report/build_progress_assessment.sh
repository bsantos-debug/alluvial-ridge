#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
assessment_build="$PWD/tmp/progress-assessment-build"
mkdir -p "$assessment_build"/{texmf-home,texmf-var,texmf-config,cache}
export TMPDIR="$assessment_build"
export XDG_CACHE_HOME="$assessment_build/cache"
export TEXMFHOME="$assessment_build/texmf-home"
export TEXMFVAR="$assessment_build/texmf-var"
export TEXMFCONFIG="$assessment_build/texmf-config"
export TEXMFCACHE="$assessment_build/cache"
for pass in 1 2; do
  pdflatex -interaction=nonstopmode -halt-on-error -output-directory="$assessment_build" progress_assessment.tex > "$assessment_build/compile-$pass.log"
done
cp "$assessment_build/progress_assessment.pdf" progress_assessment.pdf
