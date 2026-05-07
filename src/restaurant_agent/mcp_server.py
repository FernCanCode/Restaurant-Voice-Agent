from typing import Any, Dict, List, Optional

from restaurant_agent.config import get_settings
from restaurant_agent.dietary import summarize_dietary_answer
from restaurant_agent.menu_loader import get_item_by_id, load_menu
from restaurant_agent.menu_retriever import search_menu
from restaurant_agent.order_store import (
    add_item,
    add_special_instruction,
    cancel_order,
    confirm_order,
    get_order,
    remove_line_item,
    update_line_item_quantity,
)
from restaurant_agent.pricing import compute_order_totals, format_money
from restaurant_agent.schemas import DialogueMode, ToolStatus
from restaurant_agent.session_store import set_dialogue_mode


def list_tools() -> List[Dict[str, Any]]:
    return [
        {
            "name": "search_menu",
            "description": "Search the menu for items by name or category.",
            "required_arguments": ["query", "top_k"],
        },
        {
            "name": "get_menu_item",
            "description": "Get detailed info for a specific menu item by its ID.",
            "required_arguments": ["item_id"],
        },
        {
            "name": "check_dietary_info",
            "description": "Check if an item contains an allergen or is safe for a dietary restriction.",
            "required_arguments": ["item_id", "question", "allergen"],
        },
        {
            "name": "add_order_item",
            "description": "Add a menu item to the user's order.",
            "required_arguments": ["session_id", "item_id", "quantity"],
        },
        {
            "name": "remove_order_item",
            "description": "Remove a specific line item from the order by its line_item_id.",
            "required_arguments": ["session_id", "line_item_id"],
        },
        {
            "name": "update_order_item",
            "description": "Update the quantity or add special instructions to a specific line item.",
            "required_arguments": ["session_id", "line_item_id"],
        },
        {
            "name": "get_order_summary",
            "description": "Get a human-readable summary of the current order.",
            "required_arguments": ["session_id"],
        },
        {
            "name": "compute_total",
            "description": "Get the deterministic subtotal, tax, fees, and total of the order.",
            "required_arguments": ["session_id"],
        },
        {
            "name": "confirm_order",
            "description": "Confirm the order.",
            "required_arguments": ["session_id"],
        },
        {
            "name": "cancel_order",
            "description": "Cancel the order.",
            "required_arguments": ["session_id"],
        },
    ]


def _format_error(tool_name: str, msg: str, req_id: Optional[str]) -> Dict[str, Any]:
    return {
        "tool_name": tool_name,
        "status": ToolStatus.error.value,
        "result": None,
        "error": msg,
        "request_id": req_id,
    }


def call_tool(
    tool_name: str, arguments: Dict[str, Any], request_id: Optional[str] = None
) -> Dict[str, Any]:
    known_tools = {t["name"]: t for t in list_tools()}
    if tool_name not in known_tools:
        return _format_error(tool_name, f"Unknown tool: {tool_name}", request_id)

    required = known_tools[tool_name]["required_arguments"]
    for req in required:
        if req not in arguments:
            return _format_error(
                tool_name, f"Missing required argument: {req}", request_id
            )

    settings = get_settings()

    try:
        if tool_name == "search_menu":
            menu = load_menu(settings.menu_data_path)
            query = str(arguments["query"])
            top_k = int(arguments["top_k"])
            results = search_menu(query, menu, settings.menu_index_path, top_k)
            return {
                "tool_name": tool_name,
                "status": ToolStatus.success.value,
                "result": [r.model_dump() for r in results],
                "error": None,
                "request_id": request_id,
            }

        elif tool_name == "get_menu_item":
            menu = load_menu(settings.menu_data_path)
            item_id = str(arguments["item_id"])
            menu_item = get_item_by_id(menu, item_id)
            if not menu_item:
                return _format_error(
                    tool_name, f"Item not found: {item_id}", request_id
                )
            return {
                "tool_name": tool_name,
                "status": ToolStatus.success.value,
                "result": menu_item.model_dump(),
                "error": None,
                "request_id": request_id,
            }

        elif tool_name == "check_dietary_info":
            menu = load_menu(settings.menu_data_path)
            item_id = str(arguments["item_id"])
            menu_item = get_item_by_id(menu, item_id)
            if not menu_item:
                return _format_error(
                    tool_name, f"Item not found: {item_id}", request_id
                )
            question = str(arguments["question"])
            answer = summarize_dietary_answer(menu_item, question)
            return {
                "tool_name": tool_name,
                "status": ToolStatus.success.value,
                "result": {"answer": answer},
                "error": None,
                "request_id": request_id,
            }

        elif tool_name == "add_order_item":
            session_id = str(arguments["session_id"])
            item_id = str(arguments["item_id"])
            quantity = int(arguments["quantity"])
            known_modifications = arguments.get("known_modification_names", [])
            special_instructions = arguments.get("special_instructions", [])

            menu = load_menu(settings.menu_data_path)
            menu_item = get_item_by_id(menu, item_id)
            if not menu_item:
                return _format_error(
                    tool_name, f"Item not found: {item_id}", request_id
                )

            added_order = add_item(
                session_id,
                menu_item,
                quantity,
                known_modifications,
                special_instructions,
            )
            return {
                "tool_name": tool_name,
                "status": ToolStatus.success.value,
                "result": added_order.model_dump(),
                "error": None,
                "request_id": request_id,
            }

        elif tool_name == "remove_order_item":
            session_id = str(arguments["session_id"])
            line_item_id = str(arguments["line_item_id"])
            removed_order = remove_line_item(session_id, line_item_id)
            return {
                "tool_name": tool_name,
                "status": ToolStatus.success.value,
                "result": removed_order.model_dump(),
                "error": None,
                "request_id": request_id,
            }

        elif tool_name == "update_order_item":
            session_id = str(arguments["session_id"])
            line_item_id = str(arguments["line_item_id"])

            current_order = get_order(session_id)
            if not current_order:
                return _format_error(
                    tool_name, f"Order not found for session {session_id}", request_id
                )

            updated_order = current_order
            if "quantity" in arguments:
                quantity = int(arguments["quantity"])
                updated_order = update_line_item_quantity(
                    session_id, line_item_id, quantity
                )

            if "special_instructions_to_add" in arguments:
                for inst in arguments["special_instructions_to_add"]:
                    updated_order = add_special_instruction(
                        session_id, line_item_id, str(inst)
                    )

            return {
                "tool_name": tool_name,
                "status": ToolStatus.success.value,
                "result": updated_order.model_dump(),
                "error": None,
                "request_id": request_id,
            }

        elif tool_name == "get_order_summary":
            session_id = str(arguments["session_id"])
            summary_order = get_order(session_id)
            if not summary_order:
                return _format_error(
                    tool_name, f"Order not found for session {session_id}", request_id
                )

            lines = []
            for line_item in summary_order.items:
                mods = ", ".join([m.name for m in line_item.known_modifications])
                specs = ", ".join(line_item.special_instructions)
                extras = []
                if mods:
                    extras.append(mods)
                if specs:
                    extras.append(specs)
                extra_str = f" ({'; '.join(extras)})" if extras else ""
                lines.append(f"{line_item.quantity}x {line_item.item_name}{extra_str}")

            summary_str = "\n".join(lines) if lines else "Order is empty."
            return {
                "tool_name": tool_name,
                "status": ToolStatus.success.value,
                "result": {"summary": summary_str, "order": summary_order.model_dump()},
                "error": None,
                "request_id": request_id,
            }

        elif tool_name == "compute_total":
            session_id = str(arguments["session_id"])
            base_order = get_order(session_id)
            if not base_order:
                return _format_error(
                    tool_name, f"Order not found for session {session_id}", request_id
                )

            menu = load_menu(settings.menu_data_path)
            tax_rate = menu.restaurant.tax_rate
            service_fee_rate = menu.restaurant.service_fee_rate

            computed_order = compute_order_totals(
                base_order, tax_rate, service_fee_rate
            )
            return {
                "tool_name": tool_name,
                "status": ToolStatus.success.value,
                "result": {
                    "subtotal": computed_order.subtotal,
                    "tax": computed_order.tax,
                    "fees": computed_order.fees,
                    "total": computed_order.total,
                    "currency": computed_order.currency,
                    "formatted_total": format_money(
                        computed_order.total, computed_order.currency
                    ),
                },
                "error": None,
                "request_id": request_id,
            }

        elif tool_name == "confirm_order":
            session_id = str(arguments["session_id"])
            confirmed_order = confirm_order(session_id)
            return {
                "tool_name": tool_name,
                "status": ToolStatus.success.value,
                "result": {
                    "confirmation_id": confirmed_order.confirmation_id,
                    "order": confirmed_order.model_dump(),
                },
                "error": None,
                "request_id": request_id,
            }

        elif tool_name == "cancel_order":
            session_id = str(arguments["session_id"])
            cancelled_order = cancel_order(session_id)
            set_dialogue_mode(session_id, DialogueMode.CANCELLED)
            return {
                "tool_name": tool_name,
                "status": ToolStatus.success.value,
                "result": cancelled_order.model_dump(),
                "error": None,
                "request_id": request_id,
            }

    except Exception as e:
        return _format_error(tool_name, str(e), request_id)

    return _format_error(tool_name, "Unhandled execution path", request_id)
