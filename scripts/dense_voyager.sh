#!/usr/bin/env bash
# Jalankan uji dense BGE-M3 di voyager-wsl (RTX 4060 Laptop) lewat ssh.
#
#   ./eksperimen/dense_voyager.sh probe     # cek host, GPU, disk, python (read-only)
#   ./eksperimen/dense_voyager.sh setup     # buat venv + pasang torch/sentence-transformers
#   ./eksperimen/dense_voyager.sh pool      # kolam kandidat M3/M4 di GPU
#   ./eksperimen/dense_voyager.sh latensi   # latensi kueri di CPU (untuk Tabel IV)
#   ./eksperimen/dense_voyager.sh ambil     # tarik hasil ke mesin lokal
#
# Variabel: HOST (default chrisg@voyager-wsl), DIR (default ~/kk-uas)
set -euo pipefail

HOST="${HOST:-chrisg@100.64.0.2}"   # MagicDNS halley tidak selalu me-resolve nama voyager-wsl
DIR="${DIR:-kk-uas}"
LOKAL="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SSH_OPTS=(-o BatchMode=yes -o ConnectTimeout=8)

kumpulkan() {
  ssh "${SSH_OPTS[@]}" "$HOST" "mkdir -p $DIR/data/anotasi $DIR/eksperimen $DIR/hasil"
  rsync -az --delete-excluded \
    -e "ssh ${SSH_OPTS[*]}" \
    "$LOKAL/data/korpus.jsonl" "$LOKAL/data/kueri.jsonl" \
    "$HOST:$DIR/data/"
  rsync -az -e "ssh ${SSH_OPTS[*]}" \
    "$LOKAL/eksperimen/retrieval_eval.py" "$LOKAL/eksperimen/dense_pool.py" \
    "$HOST:$DIR/eksperimen/"
}

case "${1:-probe}" in
  probe)
    ssh "${SSH_OPTS[@]}" "$HOST" bash -s <<'EOF'
set -u
echo "== host =="; hostname; uname -r; . /etc/os-release && echo "$PRETTY_NAME"
echo "== cpu/ram =="; nproc; free -h | head -2
echo "== disk =="; df -hT /home /tmp | tail -2
echo "== python =="; python3 -V; python3 -m pip --version 2>/dev/null | head -1
echo "== gpu =="; ls -l /dev/dxg 2>/dev/null || echo "no /dev/dxg"
command -v nvidia-smi >/dev/null && nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader || echo "nvidia-smi tidak ada di PATH"
ls /usr/lib/wsl/lib/libcuda.so* 2>/dev/null | head -2
echo "== venv =="; ls -d ~/kk-uas/.venv 2>/dev/null || echo "belum ada venv"
echo "== hf cache =="; du -sh ~/.cache/huggingface 2>/dev/null || echo "cache kosong"
EOF
    ;;
  reuse)
    # mesin ini sudah punya venv ber-torch CUDA (ig-worker). Salin agar tidak mengunduh
    # torch 2,5 GB lewat tautan lambat, lalu pasang sentence-transformers di salinannya.
    kumpulkan
    ssh "${SSH_OPTS[@]}" "$HOST" bash -s <<'EOF'
set -eu
[ -d ~/ig-worker/.venv ] || { echo "venv sumber tidak ada" >&2; exit 1; }
rm -rf ~/kk-uas/.venv
cp -a ~/ig-worker/.venv ~/kk-uas/.venv
~/kk-uas/.venv/bin/python -c "import torch;print('torch',torch.__version__,'cuda',torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else '')"
EOF
    ;;
  setup)
    kumpulkan
    ssh "${SSH_OPTS[@]}" "$HOST" bash -s <<'EOF'
set -eu
cd ~/kk-uas
[ -x .venv/bin/python ] || python3 -m venv .venv
. .venv/bin/activate
python -m pip install -q --upgrade pip
if ! python -c "import torch" 2>/dev/null; then
  python -m pip install -q torch --index-url https://download.pytorch.org/whl/cu124 \
    || python -m pip install -q torch
fi
python -m pip install -q sentence-transformers tokenizers numpy
python - <<'PY'
import torch, sentence_transformers, sys
print("python", sys.version.split()[0], "| torch", torch.__version__,
      "| cuda", torch.cuda.is_available(),
      "| device", torch.cuda.get_device_name(0) if torch.cuda.is_available() else None)
PY
EOF
    ;;
  pool)
    kumpulkan
    ssh "${SSH_OPTS[@]}" "$HOST" bash -s <<'EOF'
set -eu
cd ~/kk-uas
. .venv/bin/activate
python eksperimen/dense_pool.py --korpus data/korpus.jsonl --kueri data/kueri.jsonl \
  --device cuda --fp16 --batch 16 \
  --keluaran data/anotasi/kandidat_m3_m4.jsonl --ringkasan hasil/dense_gpu.json
EOF
    ;;
  latensi)
    ssh "${SSH_OPTS[@]}" "$HOST" bash -s <<'EOF'
set -eu
cd ~/kk-uas
. .venv/bin/activate
python eksperimen/dense_pool.py --korpus data/korpus.jsonl --kueri data/kueri.jsonl \
  --device cpu --batch 8 \
  --keluaran hasil/dense_cpu_kandidat.jsonl --ringkasan hasil/dense_cpu.json
EOF
    ;;
  ambil)
    mkdir -p "$LOKAL/hasil"
    rsync -az -e "ssh ${SSH_OPTS[*]}" \
      "$HOST:$DIR/data/anotasi/kandidat_m3_m4.jsonl" "$LOKAL/data/anotasi/"
    rsync -az -e "ssh ${SSH_OPTS[*]}" "$HOST:$DIR/hasil/" "$LOKAL/hasil/"
    ls -l "$LOKAL/data/anotasi/kandidat_m3_m4.jsonl" "$LOKAL/hasil/"
    ;;
  *)
    echo "perintah tidak dikenal: $1" >&2; exit 2;;
esac
