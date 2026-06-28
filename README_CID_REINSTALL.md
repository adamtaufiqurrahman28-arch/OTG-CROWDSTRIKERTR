# CID Reinstall via RTR

## Files

Tambahkan file berikut ke project:

```text
gui_cid_reinstall.py
app/services/cid_reinstall_rtr_service.py
app/templates/migrate_falcon_sensor.bat
```

File lama tidak perlu di-replace.

## Run UI

```bash
streamlit run gui_cid_reinstall.py
```

## Upload ke Falcon RTR Put Files

Upload 3 file berikut ke Falcon Console > RTR > Put Files:

```text
WindowsSensor.exe
CsUninstallTool.exe
migrate_falcon_sensor.bat
```

## Flow

App akan menjalankan step ini via RTR:

```text
mkdir C:\ProgramData\CSMigration
cd C:\ProgramData\CSMigration
put WindowsSensor.exe
put CsUninstallTool.exe
put migrate_falcon_sensor.bat
run migrate_falcon_sensor.bat <Destination CID>
```

## Prerequisite

Sebelum run:

1. Disable uninstall protection / maintenance token requirement dari policy.
2. Tunggu policy apply ke target host.
3. Test 1 host dulu.
4. Validasi akhir dari Destination CID.
