# Update Cloudflare Tunnel untuk Instagram Callback

Panduan update konfigurasi Cloudflare Tunnel agar callback service Facebook/Instagram dapat diakses.

---

## Persiapan

Anda sudah punya Cloudflare Tunnel yang berjalan untuk Ollama di port 8000.

Sekarang kita akan tambah route baru untuk callback service di port 8001.

---

## Opsi A: Menggunakan Path di Domain yang Sama (Recommended)

Callback service akan diakses di: `https://aldidev.tech/auth/instagram/callback`

### Langkah A.1 — Edit config.yml

1. Di Termux, buka file config Cloudflare Tunnel:
   ```bash
   nano ~/.cloudflared/config.yml
   ```

2. Cari bagian `ingress:` yang terlihat seperti:
   ```yaml
   ingress:
     - hostname: aldidev.tech
       service: http://localhost:8000
     - service: http_status:404
   ```

3. **Ubah menjadi:**
   ```yaml
   ingress:
     - hostname: aldidev.tech
       path: /ollama/*
       service: http://localhost:8000
     
     - hostname: aldidev.tech
       path: /auth/instagram/*
       service: http://localhost:8001
     
     - service: http_status:404
   ```

   **Penjelasan:**
   - Baris 1-3: Request ke `/ollama/*` → Ollama di port 8000
   - Baris 5-7: Request ke `/auth/instagram/*` → Callback service di port 8001
   - Baris 9: Route default (404) untuk path lain

4. Simpan: `Ctrl+O` → `Enter` → `Ctrl+X`

### Langkah A.2 — Restart Cloudflare Tunnel

```bash
# Hentikan tunnel yang sedang berjalan
# (Ctrl+C jika running di foreground, atau kill process jika background)

# Jalankan ulang
cloudflared tunnel run
```

Harusnya output menunjukkan routes baru sudah aktif.

### Langkah A.3 — Verifikasi

Test di browser atau terminal:
```bash
curl -I https://aldidev.tech/auth/instagram/callback
```

Harusnya return HTTP 404 atau 405 (expected, karena callback belum ada). Jika HTTP 502/503, ada masalah dengan tunnel.

---

## Opsi B: Menggunakan Subdomain Terpisah

Jika lebih suka callback di subdomain: `https://instagram-auth.aldidev.tech/callback`

### Langkah B.1 — Setup DNS di Cloudflare

1. Buka dashboard Cloudflare → Domain `aldidev.tech`
2. Ke **DNS Records**
3. Tambah record CNAME:
   ```
   Name: instagram-auth
   Target: aldidev.tech
   ```
4. Save

### Langkah B.2 — Update config.yml

```yaml
ingress:
  - hostname: aldidev.tech
    service: http://localhost:8000
  
  - hostname: instagram-auth.aldidev.tech
    service: http://localhost:8001
  
  - service: http_status:404
```

### Langkah B.3 — Restart & Verifikasi

```bash
cloudflared tunnel run

# Test
curl -I https://instagram-auth.aldidev.tech/callback
```

---

## Pilihan Mana?

| Opsi | Kelebihan | Kekurangan |
|------|-----------|-----------|
| **Path** (`/auth/instagram/*`) | Satu domain, simple setup | Perlu path routing |
| **Subdomain** (`instagram-auth.aldidev.tech`) | Clean, terpisah jelas | Perlu DNS record tambahan |

**Rekomendasi: Gunakan Opsi A (Path)** — lebih sederhana, sudah included di config.

---

## Testing Tunnel

Setelah update, verifikasi:

1. **Ollama tetap berjalan:**
   ```bash
   curl https://aldidev.tech/ollama/api/tags
   ```

2. **Callback route terdeteksi:**
   ```bash
   curl -I https://aldidev.tech/auth/instagram/callback
   ```
   (akan return error karena service belum running, tapi route harus "found")

3. **Check tunnel logs:**
   ```bash
   cloudflared tunnel run
   ```
   Lihat output untuk route mana yang active.

---

## Troubleshooting

### "502 Bad Gateway"
- Pastikan callback service tidak sedang berjalan atau di port yang salah
- Check konfigurasi path/hostname

### "Connection refused"
- Callback service belum dijalankan di port 8001
- Lihat file CALLBACK_SERVICE.md untuk menjalankan service

### "Path routing tidak bekerja"
- Pastikan path diakhiri `*` (wildcard)
- Harus sebelum route default `http_status:404`

---

## Next Steps

1. Setelah tunnel update dan verified, jalankan callback service
2. Lihat file **CALLBACK_SERVICE.md** untuk setup FastAPI

---

**Tunnel sudah siap menerima callback Instagram OAuth!**
