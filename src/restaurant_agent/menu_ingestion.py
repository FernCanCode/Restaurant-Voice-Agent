from html.parser import HTMLParser
from pathlib import Path
from typing import Union, Optional, List

from restaurant_agent.schemas import (
    CanonicalMenu,
    RestaurantMetadata,
    MenuItem,
    PricedModification,
)


class MenuHTMLParser(HTMLParser):
    def __init__(self, raw_html: str) -> None:
        super().__init__()
        self.raw_html = raw_html
        self.restaurant_meta: Optional[RestaurantMetadata] = None
        self.current_category: Optional[str] = None
        self.current_item: Optional[MenuItem] = None
        self.items: List[MenuItem] = []
        self.in_description = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {k: (v if v is not None else "") for k, v in attrs}

        if tag == "div":
            classes = attrs_dict.get("class", "").split()

            if attrs_dict.get("id") == "restaurant-metadata":
                self.restaurant_meta = RestaurantMetadata(
                    name=attrs_dict.get("data-name", ""),
                    currency=attrs_dict.get("data-currency", "USD"),
                    tax_rate=float(attrs_dict.get("data-tax-rate", "0.0")),
                    service_fee_rate=float(
                        attrs_dict.get("data-service-fee-rate", "0.0")
                    ),
                )

            elif "category" in classes:
                self.current_category = attrs_dict.get("data-category")

            elif "menu-item" in classes:
                if self.current_item is not None:
                    self.items.append(self.current_item)

                if not self.current_category:
                    raise ValueError("Menu item found outside of a category")

                aliases_raw = attrs_dict.get("data-aliases", "")
                aliases = [a.strip() for a in aliases_raw.split(",") if a.strip()]

                ingredients_raw = attrs_dict.get("data-ingredients", "")
                ingredients = [
                    i.strip() for i in ingredients_raw.split(",") if i.strip()
                ]

                dietary_raw = attrs_dict.get("data-dietary", "")
                dietary_tags = [d.strip() for d in dietary_raw.split(",") if d.strip()]

                allergens_raw = attrs_dict.get("data-allergens", "")
                allergens = [a.strip() for a in allergens_raw.split(",") if a.strip()]

                price_raw = attrs_dict.get("data-price")
                if not price_raw:
                    raise ValueError("Menu item missing price")

                id_raw = attrs_dict.get("data-id")
                if not id_raw:
                    raise ValueError("Menu item missing id")

                self.current_item = MenuItem(
                    id=id_raw,
                    name=attrs_dict.get("data-name", ""),
                    aliases=aliases,
                    category=self.current_category,
                    description="",
                    base_price=float(price_raw),
                    available=attrs_dict.get("data-available", "true").lower()
                    == "true",
                    ingredients=ingredients,
                    dietary_tags=dietary_tags,
                    allergens=allergens,
                    modifications=[],
                    source_text=self.raw_html,
                    source_type="html",
                )

            elif "modification" in classes:
                if self.current_item is not None:
                    mod_name = attrs_dict.get("data-mod-name")
                    mod_price = attrs_dict.get("data-mod-price")
                    if mod_name and mod_price is not None:
                        self.current_item.modifications.append(
                            PricedModification(
                                name=mod_name, price_delta=float(mod_price)
                            )
                        )

        elif tag == "p" and attrs_dict.get("class") == "description":
            if self.current_item is not None:
                self.in_description = True

    def handle_data(self, data: str) -> None:
        if self.in_description and self.current_item is not None:
            self.current_item.description += data

    def handle_endtag(self, tag: str) -> None:
        if tag == "p" and self.in_description:
            self.in_description = False

    def close(self) -> None:
        super().close()
        if self.current_item is not None:
            self.items.append(self.current_item)
            self.current_item = None


def ingest_menu_html(html: str) -> CanonicalMenu:
    if not html.strip():
        raise ValueError("Empty HTML")
    parser = MenuHTMLParser(raw_html=html)
    parser.feed(html)
    parser.close()

    if not parser.restaurant_meta:
        raise ValueError("Missing restaurant metadata")

    return CanonicalMenu(restaurant=parser.restaurant_meta, items=parser.items)


def ingest_menu_file(path: Union[str, Path]) -> CanonicalMenu:
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    if file_path.suffix not in [".html", ".htm"]:
        raise ValueError(f"Unsupported file extension: {file_path.suffix}")

    content = file_path.read_text(encoding="utf-8")
    return ingest_menu_html(content)


def write_canonical_menu(menu: CanonicalMenu, output_path: Union[str, Path]) -> Path:
    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(menu.model_dump_json(indent=2), encoding="utf-8")
    return out_file


def build_menu_from_fixture(
    raw_path: Union[str, Path], output_path: Union[str, Path]
) -> CanonicalMenu:
    menu = ingest_menu_file(raw_path)
    write_canonical_menu(menu, output_path)
    return menu
