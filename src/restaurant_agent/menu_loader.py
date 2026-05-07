import json
from pathlib import Path
from typing import Union, List, Optional, Dict

from restaurant_agent.schemas import CanonicalMenu, MenuItem


def load_menu(path: Union[str, Path]) -> CanonicalMenu:
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Menu file not found: {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return CanonicalMenu(**data)


def get_item_by_id(menu: CanonicalMenu, item_id: str) -> Optional[MenuItem]:
    for item in menu.items:
        if item.id == item_id:
            return item
    return None


def find_items_by_category(menu: CanonicalMenu, category: str) -> List[MenuItem]:
    return [item for item in menu.items if item.category.lower() == category.lower()]


def list_available_items(menu: CanonicalMenu) -> List[MenuItem]:
    return [item for item in menu.items if item.available]


def menu_to_lookup(menu: CanonicalMenu) -> Dict[str, MenuItem]:
    return {item.id: item for item in menu.items}
