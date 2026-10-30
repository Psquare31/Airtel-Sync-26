"""Deploys ocr_service/ as a Hugging Face Docker Space.

Needs in backend/.env (read here, never printed):
  HF_TOKEN=hf_...            a Hugging Face *write* token
  OCR_SERVICE_KEY=...        any long random string; the same value goes into Render
Optional: OCR_SPACE_NAME (default udyam-digital-ocr)

usage (from backend/): python -m scripts.deploy_ocr_space
"""
import shutil
import tempfile
from pathlib import Path

from dotenv import dotenv_values
from huggingface_hub import HfApi

ROOT = Path(__file__).resolve().parents[2]
SERVICE = ROOT / "ocr_service"
OCR_LOCAL = ROOT / "backend" / "app" / "services" / "ocr_local.py"


def main() -> None:
    env = dotenv_values(ROOT / "backend" / ".env")
    token, key = env.get("HF_TOKEN"), env.get("OCR_SERVICE_KEY")
    missing = [n for n, v in (("HF_TOKEN", token), ("OCR_SERVICE_KEY", key)) if not v]
    if missing:
        raise SystemExit(f"add {', '.join(missing)} to backend/.env first")
    if len(key) < 24:
        raise SystemExit("OCR_SERVICE_KEY should be at least 24 random characters")

    api = HfApi(token=token)
    user = api.whoami()["name"]
    repo_id = f"{user}/{env.get('OCR_SPACE_NAME') or 'udyam-digital-ocr'}"
    api.create_repo(repo_id, repo_type="space", space_sdk="docker", exist_ok=True)
    api.add_space_secret(repo_id, "OCR_SERVICE_KEY", key)

    with tempfile.TemporaryDirectory() as tmp:
        stage = Path(tmp)
        for name in ("app.py", "Dockerfile", "requirements.txt", "README.md"):
            shutil.copy(SERVICE / name, stage / name)
        shutil.copy(OCR_LOCAL, stage / "ocr_local.py")  # the same reader the main API uses
        api.upload_folder(repo_id=repo_id, repo_type="space", folder_path=stage,
                          commit_message="deploy ocr service")

    host = repo_id.replace("/", "-").replace("_", "-").lower()
    print(f"Space: https://huggingface.co/spaces/{repo_id}")
    print(f"OCR_SERVICE_URL=https://{host}.hf.space")


if __name__ == "__main__":
    main()
