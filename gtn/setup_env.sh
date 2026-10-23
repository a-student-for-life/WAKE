#!/bin/bash
# GeoTrackNet environment for a fresh cloud session (idempotent). Usage: bash gtn/setup_env.sh
# Creates /tmp/gtn/env (Python 3.7, packages pinned in gtn/requirements-gtn37.txt) and
# /tmp/gtn/GeoTrackNet (authors' code at commit 7797b16a, with gtn/geotracknet_compat.patch).
set -e
REPO=$(cd "$(dirname "$0")/.." && pwd)
mkdir -p /tmp/gtn && cd /tmp/gtn
if [ ! -x /tmp/gtn/env/bin/python ]; then
  curl -sSL -o mm.tar.bz2 https://github.com/mamba-org/micromamba-releases/releases/latest/download/micromamba-linux-64.tar.bz2
  tar xjf mm.tar.bz2 bin/micromamba
  MAMBA_ROOT_PREFIX=/tmp/gtn/mamba ./bin/micromamba create -y -q -p /tmp/gtn/env -c conda-forge python=3.7 pip
  /tmp/gtn/env/bin/pip install -q -r "$REPO/gtn/requirements-gtn37.txt"
fi
if [ ! -d /tmp/gtn/GeoTrackNet ]; then
  git clone -q https://github.com/CIA-Oceanix/GeoTrackNet.git /tmp/gtn/GeoTrackNet
  git -C /tmp/gtn/GeoTrackNet checkout -q 7797b16a2fafcf273ff0249eb51add1f52c16ce3
  git -C /tmp/gtn/GeoTrackNet apply "$REPO/gtn/geotracknet_compat.patch"
fi
pip install -q --break-system-packages pyarrow zstandard numba pandas scipy scikit-learn statsmodels 2>/dev/null || true
/tmp/gtn/env/bin/python -c "import tensorflow as tf, sonnet; print('gtn env ok', tf.__version__)"
