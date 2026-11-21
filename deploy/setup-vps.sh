#!/usr/bin/env bash
# One-time VPS preparation (Ubuntu, run as root ON the VPS): Docker, swap, firewall.
#   scp deploy/setup-vps.sh root@<vps>:/root/ && ssh root@<vps> bash /root/setup-vps.sh
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

if ! command -v docker >/dev/null; then
  # get.docker.com may lag behind a brand-new Ubuntu release; Ubuntu's own packages are the fallback.
  curl -fsSL https://get.docker.com | sh || { apt-get update && apt-get install -y docker.io docker-compose-v2; }
fi
docker --version && docker compose version

# 2 GB RAM and no swap: the image build (npm) and rasterio reads need headroom.
if [ ! -f /swapfile ]; then
  fallocate -l 2G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  echo "/swapfile none swap sw 0 0" >> /etc/fstab
fi

# Only SSH and the web ports are open.
if command -v ufw >/dev/null; then
  ufw allow OpenSSH
  ufw allow 80/tcp
  ufw allow 443/tcp
  ufw allow 443/udp
  ufw --force enable
fi
free -m
