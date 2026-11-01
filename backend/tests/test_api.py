import time
import pytest
from fastapi.testclient import TestClient
from cutforge.api import create_app


def wait_job(client, job):
    for _ in range(200):
        result = client.get(f"/api/jobs/{job['id']}").json()
        if result["status"] in {"completed", "failed"}:
            return result
        time.sleep(.05)
    raise AssertionError("job timed out")


def test_persistent_workflow_and_undo(tmp_path, wav):
    root = tmp_path / "workspace with & symbols"
    app = create_app(root)
    with TestClient(app) as client:
        response = client.post("/api/import", files={"file": ("../Voice.wav", wav.read_bytes())})
        assert response.status_code == 202
        job = wait_job(client, response.json())
        assert job["status"] == "completed", job
        identifier = job["project_id"]
        url = f"/api/projects/{identifier}"
        p = client.get(url).json()
        job = client.post(url + "/analysis", json={"revision": p["revision"], "settings": p["settings"]}).json()
        assert wait_job(client, job)["status"] == "completed"
        p = client.get(url).json()
        assert len(p["cuts"]) == 3

        def act(action, cut=None):
            nonlocal p
            result = client.post(url + "/review", json={"revision": p["revision"], "action": action, "cut_id": cut})
            assert result.status_code == 200, result.text
            p = result.json()

        act("accept", p["cuts"][1]["id"])
        removed = p["summary"]["removed_seconds"]
        assert removed > 0
        act("undo")
        assert p["summary"]["removed_seconds"] == 0
        act("redo")
        assert p["summary"]["removed_seconds"] == removed
        old = p["cuts"][1]["id"]
        settings = {**p["settings"], "padding": .25}
        job = client.post(url + "/analysis", json={"revision": p["revision"], "settings": settings}).json()
        assert wait_job(client, job)["status"] == "completed"
        p = client.get(url).json()
        assert next(c for c in p["cuts"] if c["id"] == old)["decision"] == "accepted"
        assert p["summary"]["removed_seconds"] == removed
        assert client.post(url + "/review", json={"revision": 0, "action": "restore"}).status_code == 409
        assert client.get(url + f"/export?revision={p['revision']}").status_code == 200
        ranged = client.get(url + "/media", headers={"Range": "bytes=0-99"})
        assert ranged.status_code == 206 and len(ranged.content) == 100
        assert client.get(url + "/project.json").status_code == 200
        # Adjust a retained old decision, then prove the exact changed boundary
        # survives disk persistence and is undoable via the HTTP contract.
        accepted = next(c for c in p["cuts"] if c["id"] == old)
        response = client.post(url + "/review", json={"revision": p["revision"], "action": "adjust", "cut_id": old,
                                                      "start": accepted["start"] + 1, "end": accepted["end"]})
        assert response.status_code == 200
        p = response.json()
        assert next(c for c in p["cuts"] if c["id"] == old)["start"] == accepted["start"] + 1
        invalid = client.post(url + "/review", json={"revision": p["revision"], "action": "adjust", "cut_id": old, "start": 2.5, "end": 20})
        assert invalid.status_code == 422
        act("undo")
        assert p["summary"]["removed_seconds"] == removed
    with TestClient(create_app(root)) as client:
        assert client.get(url).json()["summary"]["removed_seconds"] == removed
        assert client.get(url + "/media").status_code == 200


def test_security_and_invalid_upload(tmp_path):
    with TestClient(create_app(tmp_path / "workspace")) as client:
        assert client.get("/api/projects/not-an-id").status_code == 400
        assert client.get("/api/projects", headers={"Origin": "https://evil.example"}).status_code == 403
        assert client.get("/api/projects", headers={"Host": "evil.example"}).status_code == 400
        assert client.post("/api/import", files={"file": ("bad.exe", b"test")}).status_code == 400
        response = client.post("/api/import", files={"file": ("bad.wav", b"broken")})
        assert wait_job(client, response.json())["status"] == "failed"
        assert list((tmp_path / "workspace").glob("*/source.wav")), "Failed imports remain on disk"


def test_missing_media_and_project_id_mismatch(tmp_path, wav):
    import json
    from pathlib import Path
    root = tmp_path / "workspace"
    with TestClient(create_app(root)) as client:
        job = wait_job(client, client.post("/api/import", files={"file": ("voice.wav", wav.read_bytes())}).json())
        identifier = job["project_id"]
        url = f"/api/projects/{identifier}"
        p = client.get(url).json()
        Path(p["media_path"]).rename(root / identifier / "moved.wav")
        response = client.get(url + f"/export?revision={p['revision']}")
        assert response.status_code == 400 and "missing" in response.json()["detail"]
        stored = root / identifier / "project.json"
        data = json.loads(stored.read_text())
        data["id"] = "0" * 32
        stored.write_text(json.dumps(data))
        assert client.get(url).status_code == 400


@pytest.mark.parametrize("extension,audio", [("wav", True), ("mp3", True), ("mp4", True), ("mov", True), ("mp4", False)])
def test_supported_media_end_to_end(tmp_path, wav, encode, extension, audio):
    from pathlib import Path
    from lxml import etree as ET
    source = wav
    if extension == "mp3":
        source = tmp_path / "voice.mp3"
        encode("-i", wav, "-c:a", "libmp3lame", source)
    elif extension in {"mp4", "mov"}:
        source = tmp_path / f"recording.{extension}"
        args = ["-f", "lavfi", "-i", "testsrc2=size=160x90:rate=25:duration=5"]
        if audio:
            args += ["-i", wav, "-c:a", "aac"]
        encode(*args, "-c:v", "libx264", source)
    with TestClient(create_app(tmp_path / "workspace")) as client:
        job = wait_job(client, client.post("/api/import", files={"file": (source.name, source.read_bytes())}).json())
        assert job["status"] == "completed", job
        url = f"/api/projects/{job['project_id']}"
        p = client.get(url).json()
        assert Path(p["media_path"]).read_bytes() == source.read_bytes()
        assert p["metadata"]["has_audio"] == audio
        job = client.post(url + "/analysis", json={"revision": p["revision"], "settings": p["settings"]}).json()
        assert wait_job(client, job)["status"] == "completed"
        p = client.get(url).json()
        assert len(p["cuts"]) == (3 if audio else 0)
        if audio:
            p = client.post(url + "/review", json={"revision": p["revision"], "action": "accept_all"}).json()
            p = client.post(url + "/review", json={"revision": p["revision"], "action": "reject", "cut_id": p["cuts"][0]["id"]}).json()
        response = client.get(url + f"/export?revision={p['revision']}")
        assert response.status_code == 200, response.text
        root = ET.fromstring(response.content)
        assert root.find(".//asset-clip").get("start") == "0/1s", "Rejected leading silence must survive export"
        assert root.find("resources/asset").get("src") == Path(p["media_path"]).as_uri()
