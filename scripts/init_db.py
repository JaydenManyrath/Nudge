import os

from models import DB_PATH, init_db


FALSE_VALUES = {"0", "false", "no", "off"}


def seed_demo_data_enabled() -> bool:
    value = os.environ.get("NUDGE_SEED_DEMO_DATA", "true")
    return value.strip().lower() not in FALSE_VALUES


def main() -> None:
    init_db(seed_demo_data=seed_demo_data_enabled())
    print(f"Initialized SQLite database at {DB_PATH}")


if __name__ == "__main__":
    main()
