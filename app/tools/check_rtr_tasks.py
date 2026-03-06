import json
import time
import os
from falconpy import RealTimeResponseAdmin

CLIENT_ID = os.getenv("FALCON_CLIENT_ID")
CLIENT_SECRET = os.getenv("FALCON_CLIENT_SECRET")

JSON_PATH = r"exports\a3102b1b645b4b658f787adea003bd2c_rtr_put_and_run_response.json"
SLEEP = 20
LOOPS = 30  # total ~10 menit (30*20s)

rtra = RealTimeResponseAdmin(client_id=CLIENT_ID, client_secret=CLIENT_SECRET)

with open(JSON_PATH, "r", encoding="utf-8") as f:
    resp = json.load(f)

per_host = resp["body"]["combined"]["resources"]  # dict keyed by AID

task_map = {}
for aid, data in per_host.items():
    tid = data.get("task_id")
    if tid:
        task_map[aid] = tid

print(f"Task ditemukan: {len(task_map)}")

for i in range(1, LOOPS + 1):
    done = 0
    failed = 0
    running = 0

    for aid, tid in task_map.items():
        st = rtra.check_admin_command_status(cloud_request_id=tid, sequence_id=0)
        body = st.get("body") or {}
        res = (body.get("resources") or [{}])[0]

        complete = res.get("complete", False)
        errs = res.get("errors") or []
        if complete and not errs:
            done += 1
        elif errs:
            failed += 1
        else:
            running += 1

    print(f"poll {i}/{LOOPS} | done={done} running={running} failed={failed}")
    time.sleep(SLEEP)