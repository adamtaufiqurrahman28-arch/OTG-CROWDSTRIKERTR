## Struktur project

```text
cs_bulk_upgrade_app/
├─ main.py
├─ requirements.txt
├─ .env.example
├─ README.md
├─ app/
│  ├─ config/
│  │  └─ settings.py
│  ├─ clients/
│  │  └─ falcon.py
│  ├─ models/
│  │  └─ host.py
│  ├─ services/
│  │  ├─ host_group_service.py
│  │  ├─ inventory_service.py
│  │  ├─ putfile_service.py
│  │  ├─ rtr_service.py
│  │  ├─ monitor_service.py
│  │  └─ orchestrator.py
│  └─ utils/
│     └─ common.py
└─ exports/
```

# CrowdStrike Bulk Upgrade RTR App

Aplikasi Python modular untuk melakukan bulk upgrade CrowdStrike Falcon Sensor melalui Real Time Response (RTR) menggunakan file installer yang **sudah tersedia** di tab **RTR Put Files**.

Aplikasi ini **tidak** meng-upload installer baru dari lokal dan **tidak** mengunduh put-file ke mesin lokal. Saat command `put-and-run` dikirim, endpoint target akan mengambil file installer langsung dari cloud RTR lalu menjalankannya di host masing-masing.

## Fungsi utama

- Mengambil seluruh AID dari sebuah Host Group.
- Mengambil inventory host berdasarkan AID.
- Memfilter host Windows yang versinya masih di bawah target build.
- Me-resolve put-file yang sudah ada di RTR berdasarkan nama file atau put-file ID.
- Membuat batch RTR session.
- Menjalankan `put-and-run` ke seluruh host kandidat.
- Opsional memonitor perubahan versi sensor sampai target tercapai.
- Mengekspor hasil ke CSV dan JSON agar mudah diaudit.

## Cara kerja singkat

1. Ambil AID dari Host Group.
2. Ambil detail host (`hostname`, `platform`, `agent_version`, dll).
3. Normalisasi versi ke format 3-part build, misalnya `7.34.20610.0` menjadi `7.34.20610`.
4. Pilih hanya host Windows dengan build lebih rendah dari target.
5. Cari put-file existing di RTR.
6. Inisialisasi batch RTR session.
7. Jalankan command `put-and-run`.
8. Simpan response RTR ke file JSON.
9. Jika mode monitor aktif, lakukan polling inventory sampai host mencapai target build atau jumlah polling habis.



## Penjelasan file dan folder

### `main.py`
Entry point aplikasi. File ini hanya:

- membaca argumen CLI,
- membentuk konfigurasi aplikasi,
- membuat client FalconPy,
- memanggil orchestrator utama.

Dengan pola ini, `main.py` tetap tipis dan mudah dirawat.

### `requirements.txt`
Daftar dependency Python:

- `falconpy`
- `python-dotenv`

### `app/config/settings.py`
Berisi:

- parser argumen CLI,
- validasi input,
- pembacaan environment variable,
- pembentukan `AppConfig`.

### `app/clients/falcon.py`
Tempat inisialisasi seluruh client FalconPy yang dipakai aplikasi, misalnya:

- `HostGroup`
- `Hosts`
- `RealTimeResponse`
- `RealTimeResponseAdmin`

### `app/models/host.py`
Model data (dataclass) untuk inventory host dan kandidat upgrade agar struktur data konsisten.

### `app/services/host_group_service.py`
Logika untuk mengambil member Host Group dan menghasilkan daftar AID.

### `app/services/inventory_service.py`
Logika untuk:

- mengambil inventory host via `post_device_details_v2`,
- membandingkan versi sensor,
- membangun summary kandidat upgrade.

### `app/services/putfile_service.py`
Logika untuk mencari put-file yang **sudah ada** di RTR:

- by `put_file_id`, atau
- by `put_name`

Service ini hanya membaca metadata file, bukan mengunduh isi file ke lokal.

### `app/services/rtr_service.py`
Logika untuk:

- membuat batch RTR session,
- menjalankan `put-and-run`.

Di versi ini, `command_string` sudah disusun dengan benar: hanya nama file + argumen installer, karena `base_command` sudah `put-and-run`.

### `app/services/monitor_service.py`
Logika polling inventory setelah command dikirim untuk mengecek apakah host sudah mencapai target build.

### `app/services/orchestrator.py`
Alur utama aplikasi dari awal sampai akhir. Semua langkah dijalankan berurutan di sini.

### `app/utils/common.py`
Kumpulan helper umum:

- normalisasi versi,
- helper chunk list,
- validasi response API,
- writer CSV/JSON,
- quoting nama file jika perlu.

### `exports/`
Folder output otomatis yang berisi hasil proses, seperti:

- daftar AID,
- inventory host,
- kandidat upgrade,
- response RTR JSON,
- AID yang masih belum upgrade setelah monitoring.

## Persiapan

### 1. Install dependency

```bash
pip install -r requirements.txt
```

### 2. Siapkan credential API

Bisa lewat environment variable langsung, atau lewat file `.env`.

Buat file `.env` dengan isi seperti ini:

```env
FALCON_CLIENT_ID=your_client_id_here
FALCON_CLIENT_SECRET=your_client_secret_here
```

Contoh PowerShell:

```powershell
$env:FALCON_CLIENT_ID="xxxxx"
$env:FALCON_CLIENT_SECRET="yyyyy"
```

## Cara menjalankan

### Contoh dengan `put_name`

```bash
python main.py \
  --host-group-id a3102b1b645b4b658f787adea003bd2c \
  --target-build 7.34.20610 \
  --put-name "FalconSensor_Latest.exe" \
  --install-args "/install /quiet /norestart" \
  --queue-offline \
  --monitor \
  --poll-seconds 30 \
  --max-polls 20
```

### Contoh dengan `put_file_id`

```bash
python main.py \
  --host-group-id a3102b1b645b4b658f787adea003bd2c \
  --target-build 7.34.20610 \
  --put-file-id <PUT_FILE_ID> \
  --install-args "/install /quiet /norestart"
```

## Argumen yang tersedia

- `--host-group-id` : ID Host Group yang akan diproses.
- `--target-build` : Build target. Bisa 3-part atau 4-part, misalnya `7.34.20610` atau `7.34.20610.0`.
- `--put-name` : Nama file installer yang sudah ada di RTR Put Files.
- `--put-file-id` : ID put-file RTR. Lebih presisi dibanding nama file.
- `--install-args` : Argumen installer. Default: `/install /quiet /norestart`.
- `--queue-offline` : Jika diaktifkan, command dipersist untuk host yang sedang offline.
- `--monitor` : Jika diaktifkan, aplikasi akan polling inventory setelah command dikirim.
- `--poll-seconds` : Jeda antar polling dalam detik. Default `180`.
- `--max-polls` : Jumlah polling maksimum. Default `10`.
- `--dry-run` : Hanya inventory dan candidate summary. Tidak mengirim command RTR.
- `--export-dir` : Folder output file CSV/JSON. Default `./exports`.

## Output yang dihasilkan

Saat aplikasi berjalan, file-file berikut akan dibuat di folder `exports/`:

- `<host_group_id>_aids.csv`
  - Berisi daftar AID dari Host Group.
- `<host_group_id>_inventory.csv`
  - Berisi inventory host hasil `post_device_details_v2`.
- `<host_group_id>_upgrade_candidates_rtr.csv`
  - Berisi host kandidat yang akan di-upgrade.
- `<host_group_id>_rtr_put_and_run_response.json`
  - Berisi raw response dari command `put-and-run`.
- `<host_group_id>_monitor_remaining.csv`
  - Berisi AID yang belum terdeteksi mencapai target build setelah monitoring selesai.

## Catatan operasional penting

### Aplikasi memakai existing Put Files

Aplikasi ini dirancang untuk file installer yang **sudah ada** di RTR Put Files. Jadi:

- tidak ada proses upload file lokal,
- tidak ada proses download file ke mesin lokal,
- endpoint target yang akan mengambil file dari cloud RTR saat `put-and-run` dijalankan.

### Perbandingan versi memakai 3-part build

Untuk menghindari mismatch seperti `7.34.20610` vs `7.34.20610.0`, aplikasi menormalkan versi ke 3-part build sebelum dibandingkan.

### `--monitor` akan terlihat diam beberapa saat

Jika `--monitor` aktif, aplikasi akan menunggu sesuai nilai `--poll-seconds` sebelum menampilkan hasil polling pertama. Ini normal.

### `--dry-run` disarankan untuk validasi awal

Sebelum menjalankan bulk upgrade sungguhan, gunakan `--dry-run` untuk memastikan:

- host group benar,
- kandidat upgrade benar,
- target build sudah sesuai,
- jumlah host target sesuai ekspektasi.

## Troubleshooting singkat

### Put-file tidak ditemukan

Periksa apakah:

- nama file di `--put-name` benar-benar sama dengan yang ada di tab RTR Put Files,
- atau gunakan `--put-file-id` agar lebih presisi.

### Tidak ada kandidat upgrade

Kemungkinan penyebab:

- semua host sudah berada di target build,
- host bukan Windows,
- `agent_version` tidak terbaca,
- target build lebih rendah dari versi host.

### Monitoring terlihat berhenti

Jika memakai `--monitor`, script akan menunggu selama `poll_seconds` tiap siklus. Kecilkan nilainya, misalnya `--poll-seconds 30`, agar progres lebih cepat terlihat.

### Sebagian host belum upgrade

Cek file response JSON RTR dan file `monitor_remaining.csv`. Penyebab umum:

- host offline,
- host lambat memproses install,
- installer memerlukan reboot,
- installer gagal dijalankan karena environment endpoint.

## Pengembangan lanjutan yang disarankan

Kalau ingin aplikasi ini makin siap operasional, pengembangan berikut bisa ditambahkan:

- logging ke file (`logs/app.log`),
- parser response per host (success, failed, offline),
- mode retry hanya untuk host gagal,
- whitelist hostname tertentu,
- integrasi notifikasi email atau Teams setelah proses selesai.

## Ringkasan

Aplikasi ini cocok untuk skenario bulk upgrade CrowdStrike sensor berbasis RTR yang ingin:

- tetap modular,
- mudah dirawat,
- mudah ditrace hasilnya,
- dan memakai installer yang sudah tersedia di RTR Put Files.

