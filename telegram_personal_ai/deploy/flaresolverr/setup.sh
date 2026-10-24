#!/usr/bin/env bash
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo 'Jalankan dengan sudo bash setup.sh' >&2
  exit 1
fi
source /etc/os-release
if [[ "$ID" != ubuntu || ! "$VERSION_ID" =~ ^(22.04|24.04)$ ]]; then
  echo 'Script ini ditujukan untuk Ubuntu 22.04/24.04 LTS.' >&2
  exit 1
fi
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
test -f "$SCRIPT_DIR/compose.yaml"

if ! command -v docker >/dev/null; then
  for package in docker.io docker-compose docker-compose-v2 podman-docker containerd runc; do
    if dpkg-query -W -f='${Status}' "$package" 2>/dev/null | grep -q 'install ok installed'; then
      echo "Paket $package sudah terpasang; selesaikan konflik instalasi Docker terlebih dahulu." >&2
      exit 1
    fi
  done
  apt-get update
  apt-get install -y ca-certificates curl
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  cat > /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: ${UBUNTU_CODENAME:-$VERSION_CODENAME}
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF
  apt-get update
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi

systemctl enable --now docker
docker compose version
docker info >/dev/null
install -d -m 0755 /opt/flaresolverr
if [[ -f /opt/flaresolverr/compose.yaml ]]; then
  if ! cmp -s "$SCRIPT_DIR/compose.yaml" /opt/flaresolverr/compose.yaml; then
    echo 'Konfigurasi /opt/flaresolverr/compose.yaml berbeda; tinjau manual sebelum memperbarui.' >&2
    exit 1
  fi
else
  install -m 0644 "$SCRIPT_DIR/compose.yaml" /opt/flaresolverr/compose.yaml
fi
docker compose -f /opt/flaresolverr/compose.yaml config --quiet
docker compose -f /opt/flaresolverr/compose.yaml pull
docker compose -f /opt/flaresolverr/compose.yaml up -d
docker compose -f /opt/flaresolverr/compose.yaml ps
echo 'Container dimulai. Periksa log dan lakukan smoke test sesuai panduan VPS.'
