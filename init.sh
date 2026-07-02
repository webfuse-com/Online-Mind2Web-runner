#!/usr/bin/env bash


set -euo pipefail


JUDGE_REPO_URL="https://github.com/OSU-NLP-Group/Online-Mind2Web"
JUDGE_SUBMODULE_PATH="third_party/Online-Mind2Web"


if [ ! -d .git ]; then
    echo "Initializing git repo (needed to hold the submodule)..."
    git init -q
fi

if [ ! -d "$JUDGE_SUBMODULE_PATH" ]; then
    echo "Adding submodule (sparse checkout of src/ only)..."
    git submodule add --depth 1 "$JUDGE_REPO_URL" "$JUDGE_SUBMODULE_PATH"
    git -C "$JUDGE_SUBMODULE_PATH" config core.sparseCheckout true
    git -C "$JUDGE_SUBMODULE_PATH" sparse-checkout init --cone
    git -C "$JUDGE_SUBMODULE_PATH" sparse-checkout set src    # skip data/
else
    echo "Submodule already present; updating..."
    git submodule update --init --depth 1 "$JUDGE_SUBMODULE_PATH"
    git -C "$JUDGE_SUBMODULE_PATH" sparse-checkout set src || true
fi

echo "Installing upstream evaluator deps..."
pip install -r "$JUDGE_SUBMODULE_PATHs/requirements.txt"
echo "Installing runner deps..."
pip install -r requirements.txt

echo "Done. Provide credentials to .env and run 'python mind2web_eval.py'"