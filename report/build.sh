#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p report/build/tmp report/build/cache report/build/texmf-home report/build/texmf-var report/build/texmf-config
export TMPDIR="$PWD/report/build/tmp"
export XDG_CACHE_HOME="$PWD/report/build/cache"
export TEXMFHOME="$PWD/report/build/texmf-home"
export TEXMFVAR="$PWD/report/build/texmf-var"
export TEXMFCONFIG="$PWD/report/build/texmf-config"
export TEXMFCACHE="$PWD/report/build/cache"
python3 report/make_first_flood.py
python3 -B report/make_recycling.py
python3 report/make_inputs.py
pdflatex -interaction=nonstopmode -halt-on-error -output-directory=report/build -jobname=report report/main.tex > report/build/compile-1.txt
pdflatex -interaction=nonstopmode -halt-on-error -output-directory=report/build -jobname=report report/main.tex > report/build/compile-2.txt
cp report/build/report.pdf report/report.pdf
