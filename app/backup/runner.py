from __future__ import annotations

import argparse
from pathlib import Path

from dotenv import load_dotenv

from app.backup.archive import BackupArchive
from app.backup.factory import create_backup_service


DEFAULT_ENV_FILE = "/opt/jarvis/.env"
DEFAULT_BACKUP_DIRECTORY = "/opt/jarvis/backups"


def run_backup(
    *,
    env_file: str = DEFAULT_ENV_FILE,
    backup_directory: str | Path = DEFAULT_BACKUP_DIRECTORY,
) -> dict[str, object]:
    load_dotenv(env_file)

    backup_service = create_backup_service()
    backup = backup_service.create_backup()

    archive = BackupArchive(
        backup_directory,
        backup_service=backup_service,
        daily_retention=7,
        weekly_retention=4,
    )

    path = archive.write(backup)
    retention = archive.apply_retention()

    return {
        "ok": True,
        "path": str(path),
        "format_version": backup.manifest.format_version,
        "created_at": backup.manifest.created_at.isoformat(),
        "postgres": backup.manifest.postgres,
        "redis": backup.manifest.redis,
        "retention": retention,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a JARVIS backup")
    parser.add_argument(
        "--env-file",
        default=DEFAULT_ENV_FILE,
        help="Environment file to load",
    )
    parser.add_argument(
        "--backup-directory",
        default=DEFAULT_BACKUP_DIRECTORY,
        help="Directory where backups are archived",
    )
    args = parser.parse_args()

    try:
        result = run_backup(
            env_file=args.env_file,
            backup_directory=args.backup_directory,
        )
    except Exception as exc:
        print(f"Backup failed: {exc}")
        return 1

    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
