# Akses API integrasi

Hanya Super Admin dapat membuat dan mencabut kunci melalui **Pengaturan Admin → Akses API Integrasi**.

1. Isi nama sistem penerima dan masa berlaku 1–90 hari.
2. Tekan **Buat API Key**. Simpan kunci yang ditampilkan satu kali di environment server penerima.
3. Panggil endpoint melalui HTTPS dari backend penerima:

```bash
curl --fail 'https://pengkar-pkkm.onrender.com/api/integration/data' \
  -H "Authorization: Bearer ${PKKM_API_KEY}"
```

Respons JSON berisi `activities`, `students`, `surveys`, `masterStudents`, `dashboardStats`, `cases`, `caseSummary`, dan `exportedAt` (UTC).

Kunci ini membaca seluruh program dan rincian kasus PPKPT, termasuk data pribadi. Berikan hanya kepada penerima yang berwenang. Simpan hasil unduhan dengan perlindungan setara database asal. Jangan tempatkan kunci di frontend, URL, log, atau GitHub. Akses ini tidak mencakup akun pengguna, password/hash, sesi, audit, maupun kunci lain.

Kunci hanya berlaku pada GET `/api/integration/data`; tidak berlaku sebagai token login pada endpoint umum dan tidak mengizinkan perubahan/penghapusan data. Token login biasa tidak berlaku pada endpoint integrasi. Tidak perlu membuka CORS untuk koneksi backend ke backend.

**Cabut Akses** menghentikan permintaan berikutnya; data yang sudah diunduh tidak dapat ditarik kembali. Kunci juga tidak berlaku setelah kedaluwarsa atau pemiliknya tidak aktif/tidak lagi Super Admin. Pergantian password akun bukan pencabutan kunci integrasi; cabut kuncinya secara eksplisit jika perlu.

Untuk rotasi, buat kunci baru, ganti environment server penerima, uji, lalu cabut kunci lama. Jika kunci hilang sebelum disimpan, cabut dan buat ulang. Database hanya menyimpan hash kunci.
