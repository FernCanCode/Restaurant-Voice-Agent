from typing import Dict, List, Any
from restaurant_agent.schemas import CanonicalMenu, MenuItem


def find_dietary_items(menu: CanonicalMenu, dietary_query: str) -> List[MenuItem]:
    q = dietary_query.lower()
    return [
        item
        for item in menu.items
        if item.available and any(q in d.lower() for d in item.dietary_tags)
    ]


def check_allergen_info(item: MenuItem, allergen: str) -> Dict[str, Any]:
    q = allergen.lower()

    if any(q in a.lower() for a in item.allergens):
        return {
            "item_id": item.id,
            "has_allergen": True,
            "evidence": "Explicitly listed in allergens.",
        }

    if any(q in i.lower() for i in item.ingredients):
        return {
            "item_id": item.id,
            "has_allergen": True,
            "evidence": "Found in ingredients list.",
        }

    return {"item_id": item.id, "has_allergen": False, "evidence": "Not listed."}


def summarize_dietary_answer(item: MenuItem, question: str) -> str:
    q = question.lower()
    allergen_name = "peanuts" if "peanut" in q else "the allergen"
    allergen_adj = "peanut" if "peanut" in q else "the allergen"

    if "peanut" in q:
        check = check_allergen_info(item, "peanut")
    elif "dairy" in q:
        allergen_name = "dairy"
        allergen_adj = "dairy"
        check = check_allergen_info(item, "dairy")
    elif "wheat" in q:
        allergen_name = "wheat"
        allergen_adj = "wheat"
        check = check_allergen_info(item, "wheat")
    else:
        check = {"has_allergen": False, "evidence": "Not checked"}

    if check["has_allergen"]:
        return f"Yes, {item.name} contains {allergen_name}."
    else:
        return f"The menu does not list {allergen_name} for {item.name}, but we cannot guarantee it is {allergen_adj}-free."
