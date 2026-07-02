#!/usr/bin/env bash


set -euo pipefail


REPO="https://github.com/OSU-NLP-Group/Online-Mind2Web"
DEST="third_party/Online-Mind2Web"


if [ ! -d .git ]; then
    echo "Initializing git repo (needed to hold the submodule)..."
    git init -q
fi

if [ ! -d "$DEST" ]; then
    echo "Adding submodule (sparse checkout of src/ only)..."
    git submodule add --depth 1 "$REPO" "$DEST"
    git -C "$DEST" config core.sparseCheckout true
    git -C "$DEST" sparse-checkout init --cone
    git -C "$DEST" sparse-checkout set src    # skip data/
else
    echo "Submodule already present; updating..."
    git submodule update --init --depth 1 "$DEST"
    git -C "$DEST" sparse-checkout set src || true
fi

echo "Installing upstream evaluator deps..."
pip install -r "$DEST/requirements.txt"
echo "Installing runner deps..."
pip install -r requirements.txt

echo "Done. Provide credentials to .env and run 'python mind2web_eval.py'"