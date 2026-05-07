import sys
from restaurant_agent.config import get_settings
from restaurant_agent.menu_ingestion import build_menu_from_fixture


def main() -> None:
    settings = get_settings()

    raw_path = settings.menu_raw_fixture_path
    data_path = settings.menu_data_path

    print(f"Ingesting menu from {raw_path}...")
    try:
        menu = build_menu_from_fixture(raw_path, data_path)
        print(f"Success! Built canonical menu with {len(menu.items)} items.")
        print(f"Saved to {data_path}")
    except Exception as e:
        print(f"Error building menu: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
