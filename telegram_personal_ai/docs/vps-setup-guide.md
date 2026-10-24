# Panduan Setup VPS Contabo + FlareSolverr

**Target:** VPS Contabo, 4 vCPU / 8 GB RAM, Ubuntu 24.04 atau 22.04 LTS  
**Tujuan:** Menjalankan FlareSolverr untuk fetch jadwal BAAK Gunadarma

---

## 1. Order Contabo

1. Buka https://contabo.com/en-us/pricing
2. Pilih paket dengan 4 vCPU / 8 GB RAM. Periksa harga final, durasi kontrak,
   biaya lokasi Singapore, setup, dan pajak di checkout; harga sebelumnya bukan penawaran pasti.
3. Konfigurasi saat order:
   - **Region:** Singapore
   - **OS:** Ubuntu 24.04 LTS (22.04 juga didukung script)
   - **Storage:** 100 GB SSD (default)
4. Bayar via PayPal / Kartu Debit Visa/Mastercard
5. Setelah order, tunggu email berisi:
   - IP Address VPS
   - Username (biasanya `root`)
   - Password awal

---

## 2. Koneksi ke VPS

Dari terminal (atau PowerShell Windows):

```bash
ssh root@<IP_VPS_KAMU>
```

Masukkan password dari email. Saat pertama login biasanya diminta ganti password.

---

## 3. Setup Otomatis (Jalankan Script)

Dari root repository di komputer lokal, upload folder deployment (ganti `IP_VPS`):

```bash
scp -r telegram_personal_ai/deploy/flaresolverr root@IP_VPS:/root/
ssh root@IP_VPS
cd /root/flaresolverr
sed -i 's/\r$//' setup.sh
bash setup.sh
```

Script memasang Docker dari repository resmi bila belum ada, memeriksa Compose,
dan menjalankan konfigurasi di `/opt/flaresolverr/compose.yaml`. Docker yang sudah
ada digunakan kembali; plugin Compose wajib tersedia. Konfigurasi deployment
yang berbeda tidak ditimpa otomatis. Jalankan script pada VPS, bukan Termux/Windows.

---

## 4. Verifikasi FlareSolverr Berjalan

```bash
# Cek container running
docker compose -f /opt/flaresolverr/compose.yaml ps
docker compose -f /opt/flaresolverr/compose.yaml logs --tail=50
curl --fail --max-time 10 http://127.0.0.1:8191/

# Test request ke FlareSolverr
curl --fail --silent --show-error --max-time 75 -X POST http://127.0.0.1:8191/v1 \
  -H "Content-Type: application/json" \
  -d '{"cmd":"request.get","url":"https://baak.gunadarma.ac.id/","maxTimeout":60000}' \
  -o /root/baak-response.json
```

Periksa `status`, `message`, `solution.status`, dan HTML di `solution.response`.
HTTP 200 dari proxy saja belum membuktikan akses BAAK berhasil. HTML harus benar-benar
halaman BAAK, bukan challenge; halaman utama juga belum membuktikan jadwal per kelas
tersedia. File respons dapat berisi cookies; simpan lokal dan jangan commit.

Status saat panduan dibuat: konfigurasi disiapkan; instalasi VPS dan akses BAAK
melalui FlareSolverr belum diuji pada VPS pengguna.

---

## 5. Environment Variables FlareSolverr

| Variable | Default | Keterangan |
|----------|---------|------------|
| `LOG_LEVEL` | `info` | Gunakan `debug` untuk troubleshoot |
| `TZ` | `Asia/Jakarta` | Timezone |
| `PORT` | `8191` | Port listener |
| `BROWSER_WAIT_TIMEOUT` | `1` | Naikkan ke `3-5` jika website lambat |

---

## 6. Port & Firewall

FlareSolverr **hanya** di-bind ke `127.0.0.1:8191` (localhost saja).  
Tidak diekspos ke internet — hanya bisa diakses dari dalam VPS itu sendiri.

Jika Go API juga jalan di VPS yang sama, ia bisa panggil `http://localhost:8191/v1`.

Untuk pengujian dari Termux/komputer lokal, buka tunnel SSH:

```bash
ssh -N -L 8191:127.0.0.1:8191 root@IP_VPS
```

Selama tunnel aktif, akses `http://127.0.0.1:8191` dari terminal lokal lain.
Jika Go API nanti berada di container terpisah, gunakan jaringan Docker bersama
dan nama service; `localhost` di container merujuk ke container itu sendiri.
API di Vercel tidak bisa mengakses localhost VPS secara langsung.

---

## 7. Troubleshooting

**Container tidak mau start:**
```bash
docker compose -f /opt/flaresolverr/compose.yaml logs --tail=100
```

**Cloudflare challenge tidak solved (timeout):**
```bash
# Naikkan maxTimeout pada JSON request ke 120000 dan curl --max-time ke 135.
# Timeout adalah parameter request, bukan properti Compose.
```

**Restart container:**
```bash
docker compose -f /opt/flaresolverr/compose.yaml restart
```

**Update FlareSolverr ke versi terbaru:**
```bash
docker compose -f /opt/flaresolverr/compose.yaml pull
docker compose -f /opt/flaresolverr/compose.yaml up -d
```

Image awal memakai `latest`. Setelah pengujian berhasil, pin `image` pada Compose
ke digest versi yang diuji agar deployment berikutnya reproducible.

Referensi: [Docker Ubuntu](https://docs.docker.com/engine/install/ubuntu/),
[FlareSolverr resmi](https://github.com/FlareSolverr/FlareSolverr).
