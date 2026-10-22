#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

pkg update
pkg install -y python git clang cmake make
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

if [ ! -f .env ]; then
  cp .env.example .env
  chmod 600 .env
fi
mkdir -p data knowledge logs
chmod 700 data
echo "Setup aplikasi selesai. Isi .env, lalu jalankan: python main.py"
echo "llama.cpp/model lokal tidak dipasang otomatis; lihat README.md."
