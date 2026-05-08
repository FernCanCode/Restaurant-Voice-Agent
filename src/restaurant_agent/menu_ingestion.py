from html.parser import HTMLParser
from pathlib import Path
import re
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


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return slug or "menu_item"


def _looks_like_html(text: str) -> bool:
    lower = text.lower()
    return any(
        marker in lower
        for marker in (
            "<html",
            "<body",
            "<div",
            "<p",
            "<!doctype",
            "restaurant-metadata",
        )
    )


def ingest_menu_text(text: str) -> CanonicalMenu:
    if not text.strip():
        raise ValueError("Empty text")

    if _looks_like_html(text):
        return ingest_menu_html(text)

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        raise ValueError("Empty text")

    restaurant_name = lines[0].lstrip("#").strip() or "Imported Menu"
    restaurant = RestaurantMetadata(
        name=restaurant_name,
        currency="USD",
        tax_rate=0.0,
        service_fee_rate=0.0,
    )

    items: List[MenuItem] = []
    current_category = "Menu"
    full_source_text = text.strip()

    for line in lines[1:]:
        heading_match = re.match(r"^(?:#+\s*)?([A-Za-z][A-Za-z &/]+):?$", line)
        if heading_match and "$" not in line and " - " not in line:
            current_category = heading_match.group(1).strip()
            continue

        price_match = re.search(r"\$?(\d+(?:\.\d{1,2})?)", line)
        if not price_match:
            continue

        price = float(price_match.group(1))
        before_price = line[: price_match.start()].rstrip(" -")
        after_price = line[price_match.end() :].strip(" -")
        item_name = before_price.strip()
        if not item_name:
            continue

        items.append(
            MenuItem(
                id=_slugify(item_name),
                name=item_name,
                aliases=[],
                category=current_category,
                description=after_price,
                base_price=price,
                available=True,
                ingredients=[],
                dietary_tags=[],
                allergens=[],
                modifications=[],
                source_text=full_source_text,
                source_type="text",
            )
        )

    if not items:
        raise ValueError(
            "Unable to parse menu text. Provide fixture-style HTML or simple menu lines with prices."
        )

    return CanonicalMenu(restaurant=restaurant, items=items)


def ingest_menu_file(path: Union[str, Path]) -> CanonicalMenu:
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    supported_text_extensions = {".html", ".htm", ".txt", ".md"}
    unsupported_structured_extensions = {".csv", ".json"}

    if file_path.suffix in unsupported_structured_extensions:
        raise ValueError(
            f"Unsupported file extension for this phase: {file_path.suffix}"
        )

    if file_path.suffix not in supported_text_extensions:
        raise ValueError(f"Unsupported file extension: {file_path.suffix}")

    content = file_path.read_text(encoding="utf-8")
    return ingest_menu_text(content)


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
