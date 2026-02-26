"""
Hotel Bot Brain - Single LLM Agent
Clean, simple, one brain to rule them all.
"""

import json
import logging
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models import (
    Conversation,
    Guest,
    Hotel,
    Message,
    MessageDirection,
    MessageSender,
    Room,
    Stay,
    Task,
    TaskStatus,
    TaskType,
)
from app.services.llm_client import LLMClient, _sanitize_text
from app.services.staff_notifier import notify_new_task

logger = logging.getLogger("hotelbot.brain")

# Multilingual fallback messages when OpenAI fails
FALLBACK_ERROR_MESSAGES = {
    "en": "I apologize, I'm having trouble processing your request. Please try again or contact reception.",
}


def _get_fallback_message(staff_lang: str) -> str:
    """Get fallback error message in appropriate language."""
    return FALLBACK_ERROR_MESSAGES.get(staff_lang, FALLBACK_ERROR_MESSAGES["en"])


def _translate_summary_to_staff_lang(llm: "LLMClient", summary: str, staff_lang: str) -> str:
    """Quick translation of task summary to staff language."""
    return summary


def _build_tools(staff_lang: str, hotel_settings: dict = None) -> list:
    """Build tools with language-specific descriptions and dynamic category filtering."""
    settings = hotel_settings or {}

    lang_name = "ENGLISH"
    lang_example = "Examples: '2 towels room 5', 'coffee room 3'"

    # Build dynamic categories based on hotel settings
    # MAINTENANCE, LOST_AND_FOUND, OTHER are ALWAYS available (safety)
    categories = ["MAINTENANCE", "LOST_AND_FOUND", "OTHER"]

    # Add HOUSEKEEPING if enabled (default: False)
    if settings.get("allow_housekeeping", False):
        categories.append("HOUSEKEEPING")

    # Add FOOD_BEVERAGE if enabled (default: False)
    if settings.get("allow_food_beverage", False):
        categories.append("FOOD_BEVERAGE")

    # Sort for consistency
    categories.sort()
    # DEBUG: Log built categories
    logging.getLogger("hotelbot.brain").info(
        f"DEBUG TOOLS: categories={categories}, allow_hk={settings.get('allow_housekeeping')}"
    )

    tools = [
        {
            "type": "function",
            "function": {
                "name": "create_task",
                "description": "Create a new task for hotel staff. Use for housekeeping, food orders, maintenance requests, lost items, emergencies.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "category": {
                            "type": "string",
                            "enum": categories,
                            "description": "Task category",
                        },
                        "summary": {
                            "type": "string",
                            "description": f"⚠️ MANDATORY LANGUAGE: Write summary in {lang_name} ONLY. Do NOT use English unless staff language is English. {lang_example}. Keep SHORT and FACTUAL.",
                        },
                        "priority": {
                            "type": "string",
                            "enum": ["NORMAL", "URGENT", "CRITICAL"],
                            "description": "Task priority. CRITICAL for life-threatening emergencies (fire, violence, medical). URGENT for security issues, flooding, broken locks. NORMAL for regular requests.",
                        },
                        "room": {
                            "type": "string",
                            "description": "Room number mentioned by guest (e.g., '101', '202'). Extract from message if guest mentions a specific room.",
                        },
                    },
                    "required": ["category", "summary"],
                },
            },
        }
    ]

    # Only add add_to_task tool if FOOD_BEVERAGE is enabled AND menu exists
    menu_exists = bool(settings.get("hotel_products_text", "").strip())
    if settings.get("allow_food_beverage", False) and menu_exists:
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": "add_to_task",
                    "description": "ONLY for FOOD_BEVERAGE: Add more items to an existing open food/drink order. NEVER use for HOUSEKEEPING, MAINTENANCE, or OTHER categories.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "task_id": {
                                "type": "integer",
                                "description": "ID of existing task",
                            },
                            "note": {
                                "type": "string",
                                "description": f"⚠️ MANDATORY: Write note in {lang_name} ONLY. {lang_example}",
                            },
                        },
                        "required": ["task_id", "note"],
                    },
                },
            }
        )

    return tools


class HotelBrain:
    """Single LLM brain for the hotel bot."""

    def __init__(
        self,
        db: Session,
        hotel: Hotel,
        conversation: Conversation,
        room: Optional[Room] = None,
        guest: Optional[Guest] = None,
        stay: Optional[Stay] = None,
    ):
        self.db = db
        self.hotel = hotel
        self.conversation = conversation
        self.room = room
        self.guest = guest
        self.stay = stay
        self.llm = LLMClient()

    def _get_room_number(self) -> str:
        """Get room number from room, stay, or conversation."""
        if self.room:
            return self.room.room_number
        if self.stay and self.stay.room:
            return self.stay.room.room_number
        return "Unknown"

    def _get_guest_name(self) -> str:
        """Get guest name or Anonymous."""
        if self.guest and self.guest.pii and self.guest.pii.full_name:
            return self.guest.pii.full_name.split()[0]  # First name
        return "Guest"

    def _get_active_tasks(self) -> str:
        """Get active tasks for this room/stay."""
        # If no room/stay context, return None (can't show unrelated tasks)
        if not self.stay and not self.room:
            return "None"

        tasks_q = self.db.query(Task).filter(
            Task.hotel_id == self.hotel.id,
            Task.status.in_([TaskStatus.OPEN, TaskStatus.IN_PROGRESS]),
        )

        # Filter by stay (PRO) or room (BASIC)
        if self.stay:
            tasks_q = tasks_q.filter(Task.stay_id == self.stay.id)
        elif self.room:
            # For BASIC tier, check tasks by room in staff_summary
            room_num = self.room.room_number
            tasks_q = tasks_q.filter(Task.staff_summary.ilike(f"%{room_num}%"))

        tasks = tasks_q.order_by(Task.created_at.desc()).limit(5).all()

        if not tasks:
            return "None"

        lines = []
        for t in tasks:
            lines.append(f"#{t.id} - {t.type.value} - {t.staff_summary or 'No summary'}")
        return "\n".join(lines)

    def _get_history(self) -> List[dict]:
        """Get recent conversation history."""
        messages = (
            self.db.query(Message)
            .filter(Message.conversation_id == self.conversation.id)
            .order_by(Message.created_at.desc())
            .limit(10)
            .all()
        )

        history = []
        for m in reversed(messages):
            role = "assistant" if m.direction == MessageDirection.OUTGOING else "user"
            content = _sanitize_text(m.text) if role == "user" else m.text
            history.append({"role": role, "content": content})
        return history

    def _build_system_prompt(self) -> str:
        """Build the system prompt - simple and clear."""
        settings = self.hotel.settings or {}
        # DEBUG: Log housekeeping settings
        logger.info(
            f"DEBUG SETTINGS: allow_housekeeping={settings.get('allow_housekeeping')}, "
            f"hk_towels={settings.get('hk_towels_toiletries')}, "
            f"hk_laundry={settings.get('hk_laundry')}, "
            f"hk_room_cleaning={settings.get('hk_room_cleaning')}"
        )
        bot_name = settings.get("bot_name", "Assistant")
        staff_lang = self.hotel.staff_language or "en"

        # Get bot personality/tone
        tone = "professional"
        if self.hotel.ai_profile and self.hotel.ai_profile.tone:
            tone = self.hotel.ai_profile.tone

        # Personality instructions based on tone
        if tone == "friendly":
            personality = """- Be warm, friendly and cheerful! 😊
- Give helpful, complete answers (4-6 sentences) - don't be too brief!
- Use emojis naturally to be engaging! 👍🎉😊
- Be enthusiastic, positive and conversational
- Ask follow-up questions to ensure guest satisfaction
- If something doesn't work, offer alternatives and ask if you should contact staff
- Make the guest feel welcome and cared for"""
        else:
            personality = """- Be professional, formal and thorough
- Give complete, detailed answers (4-6 sentences) - be comprehensive!
- NO emojis - maintain professional tone
- Be courteous, respectful and attentive to details
- Ask follow-up questions to ensure guest satisfaction
- If something doesn't work as expected, offer alternatives and propose to escalate to staff
- Provide context and additional helpful information when relevant"""

        # Hotel facts
        wifi_ssid = settings.get("wifi_ssid", "N/A")
        wifi_pass = settings.get("wifi_password", "N/A")
        breakfast = settings.get("breakfast_hours", "7:00 - 10:00")
        checkin_time = settings.get("checkin_time", "14:00")
        checkout = settings.get("checkout_time", "11:00")
        parking_info = settings.get("parking_info", "")
        # Only show menu if Food & Beverage is enabled
        if settings.get("allow_food_beverage", False):
            menu_text = settings.get("hotel_products_text", "").strip()
            if menu_text:
                menu = menu_text
            else:
                menu = "No menu available. If guest asks, say you don't have the menu and suggest contacting reception."
        else:
            menu = "Food & Beverage service is DISABLED. Do NOT show any menu items. If guest asks, politely refuse and suggest contacting reception."
        # CRITICAL: UI field is "custom_knowledge_text" not "hotel_policies_text"
        knowledge = settings.get("custom_knowledge_text", "")
        _welcome = settings.get("welcome_text", "")  # Reserved for future use

        # Build disabled services section
        disabled_services = []
        if not settings.get("allow_housekeeping", False):
            disabled_services.append(
                "HOUSEKEEPING (cleaning, towels, toiletries, laundry) - politely explain this service is not available"
            )
        if not settings.get("allow_food_beverage", False):
            disabled_services.append(
                "FOOD & BEVERAGE (room service, food orders, drinks) - politely explain this service is not available"
            )

        disabled_services_text = ""
        if disabled_services:
            disabled_services_text = "\n\n=== DISABLED SERVICES - DO NOT CREATE TASKS FOR ===\n"
            disabled_services_text += "\n".join(f"- {s}" for s in disabled_services)
            disabled_services_text += (
                "\n\n⚠️ CRITICAL: Do NOT hallucinate! If a service is disabled, you MUST refuse."
            )
            disabled_services_text += (
                "\n- NEVER say 'I have ordered X' or 'I've arranged X' if you cannot create a task"
            )
            disabled_services_text += "\n- Be HONEST: apologize IN THE GUEST'S LANGUAGE and clearly say the service is not available"
            disabled_services_text += "\n- Example: 'I apologize, but we do not offer food/drinks ordering via chat. Please contact reception.'"
            disabled_services_text += "\n- Suggest they contact reception directly if urgent"
            disabled_services_text += "\n- NEVER respond in staff language for guest messages"

        # Build housekeeping services section (explicit ENABLED/DISABLED for each sub-service)
        hk_services_text = ""
        if settings.get("allow_housekeeping", False):
            hk_services = []
            # Room cleaning
            if settings.get("hk_room_cleaning", False):
                hk_services.append("✓ Room cleaning - ENABLED")
            else:
                hk_services.append("✗ Room cleaning - DISABLED")
            # Towels & toiletries
            if settings.get("hk_towels_toiletries", False):
                hk_services.append("✓ Towels & toiletries (soap, shampoo, toilet paper) - ENABLED")
            else:
                hk_services.append("✗ Towels & toiletries (soap, shampoo, toilet paper) - DISABLED")
            # Bed linen
            if settings.get("hk_bed_linen", False):
                hk_services.append("✓ Bed linen (sheets and duvet covers ONLY) - ENABLED")
            else:
                hk_services.append("✗ Bed linen (sheets and duvet covers ONLY) - DISABLED")
            # Laundry
            if settings.get("hk_laundry", False):
                hk_services.append("✓ Laundry service - ENABLED")
            else:
                hk_services.append("✗ Laundry service - DISABLED")
            # Extra amenities
            if settings.get("hk_extra_amenities", False):
                hk_services.append(
                    "✓ Extra amenities (pillows, blankets, iron, slippers - NOT bed sheets) - ENABLED"
                )
            else:
                hk_services.append(
                    "✗ Extra amenities (pillows, blankets, iron, slippers - NOT bed sheets) - DISABLED"
                )

            # DEBUG: Log what services were built
            logger.info(f"DEBUG HK_SERVICES: {hk_services}")

            hk_services_text = "\n\n=== HOUSEKEEPING SERVICES ===\n"
            hk_services_text += "\n".join(hk_services)
            hk_services_text += "\n\nNOTE: 'Bed linen' = sheets/duvet covers. 'Extra amenities' = pillows/blankets/iron/slippers. These are SEPARATE categories."
            hk_services_text += "\n\nIMPORTANT: Create tasks ONLY for ENABLED (✓) services. For DISABLED (✗) services, politely refuse IN THE GUEST'S LANGUAGE and suggest contacting reception."

        room_number = self._get_room_number()
        guest_name = self._get_guest_name()
        active_tasks = self._get_active_tasks()

        # Check-in/out dates for PRO tier
        checkin = checkout_date = "N/A"
        if self.stay:
            if self.stay.checkin_date:
                checkin = self.stay.checkin_date.strftime("%Y-%m-%d")
            if self.stay.checkout_date:
                checkout_date = self.stay.checkout_date.strftime("%Y-%m-%d")

        # Build dynamic "what you can do" list based on enabled services
        can_do_tasks = []
        if settings.get("allow_housekeeping", False):
            can_do_tasks.append("housekeeping")
        if settings.get("allow_food_beverage", False):
            can_do_tasks.append("food/drink orders")
        can_do_tasks.append("maintenance")  # Always available
        can_do_list = ", ".join(can_do_tasks)

        return f"""You are {bot_name}, the virtual concierge for {self.hotel.name}.

YOUR ROLE:
- Answer questions about the hotel
- Create tasks for staff when guests need services

YOUR PERSONALITY:
{personality}

TASK CREATION RULES:
- ALWAYS use create_task for new requests - each request = separate task
- NEVER combine tasks from different messages
- EXCEPTION: FOOD_BEVERAGE only - if guest has open food/drink order and adds more items (e.g., "și o apă"), use add_to_task
- CRITICAL or URGENT priority tasks: NEVER use add_to_task, always create_task
- HOUSEKEEPING, MAINTENANCE, OTHER: ALWAYS create_task (never add_to_task)
- Task summaries must be in {staff_lang.upper()}
- CRITICAL: For EMERGENCIES, use the EXACT words the guest used! Do NOT interpret "blood" as "fire" or change the description. Quote literally!

TASK CATEGORY RULES:
- HOUSEKEEPING: Cleaning, towels, toiletries, bed sheets, toilet paper, room cleaning, laundry service, extra amenities (pillows, blankets, iron)
- FOOD_BEVERAGE: Food orders, drinks, menu items, room service food
- MAINTENANCE: Broken items, AC problems, lights/bulbs, plumbing, GAS SMELL (urgent!), leaks, TV/remote, electrical issues, flooding
- LOST_AND_FOUND: Guest lost items (keys, phone, wallet, charger, jewelry), found items reports
- OTHER: Blood/injury, medical emergencies, aggressive guests, security concerns, taxi, wake-up calls, violence reports
{disabled_services_text}{hk_services_text}
TASK PRIORITY RULES (IMPORTANT):
- CRITICAL: Life-threatening emergencies - fire, violence, assault, blood/injury, medical emergency, serious injury, someone unconscious, heart attack. USE IMMEDIATELY!
- URGENT: Security issues, flooding, broken door lock, stolen items, gas smell, suspicious person, elevator stuck, aggressive guest
- NORMAL: Regular requests - housekeeping, towels, food orders, maintenance, information requests

WHAT YOU CAN DO:
- Answer: WiFi, breakfast hours, checkout time, policies
- Create tasks: {can_do_list}
- Show menu when asked
- For services you cannot do directly (taxi, wake-up call, stay extension, bill questions): CREATE A TASK for Front Desk staff!

WHAT YOU CANNOT DO DIRECTLY (but CAN create task for staff):
- Order taxi → Create task: "Guest needs taxi at [time] to [destination]"
- Wake-up call → Create task: "Guest wants wake-up call at [time]"
- Extend stay → Create task: "Guest wants to extend stay, discuss rates"
- Bill questions → Create task: "Guest has billing questions"

WHAT YOU TRULY CANNOT DO:
- Process payments directly
- Give discounts or negotiate prices
- Answer about other hotels
- Access external systems
- Create tasks for OTHER rooms! If guest asks to order for room 10 but they are in room 7, REFUSE politely. Say: "I can only take orders for your room. Please ask your neighbor to contact us directly."

=== STRICT BOUNDARIES (ZERO HALLUCINATION) ===
You are NOT a general AI assistant. You are EXCLUSIVELY the assistant for {self.hotel.name}.

ABSOLUTELY FORBIDDEN - DO NOT:
1. Answer questions about politics, history, celebrities, world news, sports, science, math, or ANY topic unrelated to this hotel
2. Recommend restaurants, attractions, or services that are NOT explicitly listed in your context
3. Invent facts, prices, hours, or policies that are not in your context
4. Use your general training knowledge for hotel-specific information
5. Guess or assume information - if you don't have it, say so

WHEN INFORMATION IS MISSING:
- Say clearly: "I don't have that information in my database."
- Then ask: "Would you like me to connect you with our staff who can help?"

EXAMPLE RESPONSES FOR OFF-TOPIC:
- "Who is the US president?" → "I can only assist with matters related to your stay at {self.hotel.name}. How can I help with your accommodation?"
- "What Italian restaurant is nearby?" → "I don't have information about nearby restaurants. Would you like me to ask our reception team for recommendations?"
- "What's the weather tomorrow?" → "I don't have access to weather information. Is there anything about your stay I can help with?"

=== HOTEL INFO ===
Hotel: {self.hotel.name}
WiFi: {wifi_ssid} / Password: {wifi_pass}
Breakfast: {breakfast}
Check-in time: {checkin_time}
Checkout time: {checkout}
Parking: {parking_info if parking_info else "Ask reception"}

=== KNOWLEDGE BASE (Policies, Rules, Info) ===
{knowledge if knowledge else "Standard hotel policies apply. For specific questions, ask reception."}

=== MENU ===
{menu}

=== CURRENT CONTEXT ===
Room: {room_number}
Guest: {guest_name}
Check-in: {checkin}
Check-out: {checkout_date}

=== ACTIVE TASKS ===
{active_tasks}

=== BUTTON RESPONSES ===
When guest clicks a button (sends exact text), respond accordingly:

HOTEL POLICIES BUTTON ("Hotel policies"):
→ If KNOWLEDGE BASE section above has content (not just "Standard hotel policies apply"):
  - Display the policies in the guest's language, formatted nicely
  - Summarize key points if policies are long
→ If KNOWLEDGE BASE is empty or just default text:
  - Say: "I don't have the hotel policies in my database. Please contact reception for details."

WHAT CAN I ASK BUTTON ("What can I ask?"):
→ Generate a DYNAMIC list based on what's actually enabled for this hotel:
  - ALWAYS mention: WiFi info, breakfast hours, checkout time, maintenance issues
  - If parking_info exists: mention parking information
  - If allow_housekeeping=True: mention housekeeping services (towels, cleaning, etc.)
  - If allow_food_beverage=True AND menu exists: mention room service/food ordering
  - If custom_knowledge_text exists: mention "hotel policies and rules"
→ DO NOT mention services that are DISABLED!
→ Keep it friendly and concise (3-5 bullet points)

HOUSEKEEPING BUTTON ("Housekeeping"):
→ Ask for confirmation: "Would you like housekeeping service for room {room_number}?"
→ Only create task AFTER guest confirms (yes, da, ใช่, etc.)

ROOM SERVICE BUTTON ("Room Service"):
→ Ask what they'd like to order, show menu if available

MENU BUTTON ("Menu"):
→ Display the menu items TRANSLATED to the guest's language. Show item names and prices. Keep the structure but translate everything to match the guest's language.

=== CRITICAL: RESPONSE LANGUAGE ===
You MUST respond in the EXACT SAME LANGUAGE as the guest's message.
- If guest writes in English → respond in English
- If guest writes in Thai → respond in Thai
- If guest writes in Romanian → respond in Romanian
- If guest writes in any other language → respond in that language
The task summaries for staff are always in {staff_lang.upper()}, but your response to the guest MUST match their language.
"""

    def _execute_tool(self, tool_name: str, args: dict) -> Optional[Task]:
        """Execute a tool call from the LLM."""
        if tool_name == "create_task":
            return self._create_task(args)
        elif tool_name == "add_to_task":
            return self._add_to_task(args)
        return None

    def _create_task(self, args: dict) -> Optional[Task]:
        """Create a new task."""
        from datetime import timedelta

        category = args.get("category", "OTHER")
        summary = args.get("summary", "Guest request")
        priority = args.get("priority", "NORMAL")
        room_from_args = args.get("room")  # Room extracted by LLM from message

        settings = self.hotel.settings or {}
        summary_lower = summary.lower()

        # HARD BLOCK: Food & Beverage
        # If F&B is disabled, block ALL food/drink task creation regardless of category
        if not settings.get("allow_food_beverage", False):
            fb_keywords = [
                # Water (EN, RO, TH, ZH)
                "water",
                "apă",
                "น้ำ",
                "水",
                # Coffee/Tea
                "coffee",
                "cafea",
                "กาแฟ",
                "咖啡",
                "tea",
                "ceai",
                "ชา",
                "茶",
                # Food
                "food",
                "mâncare",
                "อาหาร",
                "食物",
                "餐",
                # Drinks (EN singular/plural, RO singular/plural)
                "drink",
                "drinks",
                "băutură",
                "băuturi",
                "เครื่องดื่ม",
                "饮料",
                # Order/Menu (EN, RO singular/plural)
                "order",
                "orders",
                "comandă",
                "comenzi",
                "สั่ง",
                "订单",
                "点",
                "menu",
                "meniu",
                "เมนู",
                "菜单",
                # Room service
                "room service",
                "serviciu cameră",
                "บริการห้อง",
            ]
            if any(kw in summary_lower for kw in fb_keywords):
                logger.info(f"HARD BLOCK: Food & Beverage disabled, blocking task: {summary}")
                return None
            # Also block if category is explicitly FOOD_BEVERAGE
            if category == "FOOD_BEVERAGE":
                logger.info(
                    f"HARD BLOCK: Food & Beverage category disabled, blocking task: {summary}"
                )
                return None

        # HARD BLOCK: Check housekeeping sub-services
        # This is a hard validation - if sub-service is disabled, block task creation
        # LLM prompt instructions are ~70-80% reliable, this makes it 100%
        if category == "HOUSEKEEPING":
            # Towels & Toiletries (EN, RO, TH)
            if not settings.get("hk_towels_toiletries", False):
                towel_keywords = [
                    # Towel (EN singular/plural, RO singular/plural, TH)
                    "towel",
                    "towels",
                    "prosop",
                    "prosoape",
                    "ผ้าเช็ด",
                    "ผ้าขนหนู",  # towel
                    # Soap (EN singular/plural, RO singular/plural, TH)
                    "soap",
                    "soaps",
                    "săpun",
                    "săpunuri",
                    "สบู่",  # soap
                    # Shampoo (EN, RO singular/plural, TH)
                    "shampoo",
                    "șampon",
                    "șampoane",
                    "แชมพู",  # shampoo
                    # Toilet paper (EN, RO, TH)
                    "toilet paper",
                    "hârtie igienică",
                    "กระดาษชำระ",  # toilet paper
                    # Toiletries/Amenities (EN, RO, TH)
                    "toiletries",
                    "toaletă",
                    "อุปกรณ์อาบน้ำ",  # toiletries
                    "amenities",
                    "amenități",  # amenities (general)
                ]
                if any(kw in summary_lower for kw in towel_keywords):
                    logger.info(f"HARD BLOCK: Towels/toiletries disabled, blocking task: {summary}")
                    return None

            # Room Cleaning (EN, RO, TH)
            if not settings.get("hk_room_cleaning", False):
                cleaning_keywords = [
                    "clean",
                    "curăț",
                    "ทำความสะอาด",
                    "สะอาด",  # clean
                    "cleaning",
                    "curățenie",
                    "การทำความสะอาด",  # cleaning
                    "vacuum",
                    "aspirator",
                    "ดูดฝุ่น",  # vacuum
                    "mop",
                    "mop",
                    "ถูพื้น",  # mop
                    "dust",
                    "praf",
                    "ฝุ่น",  # dust
                    "tidy",
                    "aranjat",
                    "เก็บ",  # tidy
                ]
                if any(kw in summary_lower for kw in cleaning_keywords):
                    logger.info(f"HARD BLOCK: Room cleaning disabled, blocking task: {summary}")
                    return None

            # Bed Linen (EN, RO, TH) - Only sheets/duvet, NOT pillows/blankets (those are Extra Amenities)
            if not settings.get("hk_bed_linen", False):
                linen_keywords = [
                    # Linen (EN, RO, TH)
                    "linen",
                    "linens",
                    "lenjerie",
                    "ผ้าปู",  # linen
                    # Sheet (EN singular/plural, RO singular/plural, TH)
                    "sheet",
                    "sheets",
                    "cearșaf",
                    "cearșafuri",
                    "cearceaf",
                    "cearceafuri",
                    "ผ้าปูที่นอน",  # sheet
                    # Duvet (EN singular/plural, RO singular/plural, TH)
                    "duvet",
                    "duvets",
                    "plapumă",
                    "plapume",
                    "ผ้านวม",  # duvet
                ]
                if any(kw in summary_lower for kw in linen_keywords):
                    logger.info(f"HARD BLOCK: Bed linen disabled, blocking task: {summary}")
                    return None

            # Laundry (EN, RO, TH)
            if not settings.get("hk_laundry", False):
                laundry_keywords = [
                    "laundry",
                    "spălătorie",
                    "rufe",
                    "ซักผ้า",
                    "ซักรีด",  # laundry
                    "wash",
                    "spălat",
                    "ซัก",  # wash
                    "iron",
                    "călcat",
                    "รีด",  # iron
                    "dry clean",
                    "curățătorie",
                    "ซักแห้ง",  # dry clean
                    "press",
                    "călcare",
                    "รีดผ้า",  # press
                ]
                if any(kw in summary_lower for kw in laundry_keywords):
                    logger.info(f"HARD BLOCK: Laundry disabled, blocking task: {summary}")
                    return None

            # Extra Amenities (EN, RO, TH, ZH) - Pillows, blankets, iron, slippers per UI
            if not settings.get("hk_extra_amenities", False):
                extra_keywords = [
                    # Pillow (EN singular/plural, RO singular/plural, TH, ZH)
                    "pillow",
                    "pillows",
                    "pernă",
                    "perne",
                    "หมอน",
                    "枕头",
                    # Blanket (EN singular/plural, RO singular/plural, TH, ZH)
                    "blanket",
                    "blankets",
                    "pătură",
                    "pături",
                    "ผ้าห่ม",
                    "毯子",
                    # Iron (EN, RO, TH, ZH)
                    "iron",
                    "fier de călcat",
                    "เตารีด",
                    "熨斗",
                    # Slippers (EN singular/plural, RO - papuci is already plural, TH, ZH)
                    "slipper",
                    "slippers",
                    "papuc",
                    "papuci",
                    "รองเท้าแตะ",
                    "拖鞋",
                    # Generic extra
                    "extra",
                    "suplimentar",
                    "suplimentare",
                    "เพิ่มเติม",
                    "additional",
                    "adițional",
                    "adiționale",
                    "เพิ่ม",
                ]
                if any(kw in summary_lower for kw in extra_keywords):
                    logger.info(f"HARD BLOCK: Extra amenities disabled, blocking task: {summary}")
                    return None

        # Validate priority
        valid_priorities = ["NORMAL", "URGENT", "CRITICAL"]
        if priority not in valid_priorities:
            priority = "NORMAL"

        # Map category to TaskType
        type_map = {
            "HOUSEKEEPING": TaskType.HOUSEKEEPING,
            "FOOD_BEVERAGE": TaskType.FOOD_BEVERAGE,
            "MAINTENANCE": TaskType.MAINTENANCE,
            "LOST_AND_FOUND": TaskType.LOST_AND_FOUND,
            "OTHER": TaskType.OTHER,
        }
        task_type = type_map.get(category, TaskType.OTHER)

        # FALLBACK: Translate if summary language doesn't match staff language
        # Detects CJK (Chinese/Japanese/Korean), Thai, Arabic, Cyrillic scripts
        staff_lang = self.hotel.staff_language or "en"
        needs_translation = False

        if staff_lang == "th":
            # For Thai staff: check if summary contains ANY Thai characters
            thai_chars = sum(1 for c in summary if 0x0E00 <= ord(c) <= 0x0E7F)
            if thai_chars == 0:
                # No Thai characters = wrong language (Chinese, English, etc.)
                needs_translation = True
        elif staff_lang == "ro":
            # For Romanian staff: check for non-Latin scripts OR English text
            # First check non-Latin scripts
            for c in summary:
                code = ord(c)
                if 0x4E00 <= code <= 0x9FFF or 0x3400 <= code <= 0x4DBF:  # CJK
                    needs_translation = True
                    break
                if 0x0E00 <= code <= 0x0E7F:  # Thai
                    needs_translation = True
                    break
                if 0x0600 <= code <= 0x06FF:  # Arabic
                    needs_translation = True
                    break
                if 0x0400 <= code <= 0x04FF:  # Cyrillic
                    needs_translation = True
                    break
            # Then check for common English words (GPT sometimes writes in English)
            if not needs_translation:
                english_indicators = [
                    "guest",
                    "wants",
                    "request",
                    "check-out",
                    "check-in",
                    "late",
                    "early",
                    "room service",
                    "towel",
                    "clean",
                    "maintenance",
                    "broken",
                    "lost",
                    "found",
                    "emergency",
                ]
                summary_lower = summary.lower()
                for word in english_indicators:
                    if word in summary_lower:
                        needs_translation = True
                        logger.warning(f"English word '{word}' detected in Romanian staff summary")
                        break
        else:  # staff_lang == "en" - English staff
            # Check for non-Latin scripts that need translation to English
            for c in summary:
                code = ord(c)
                # CJK (Chinese/Japanese/Korean): 0x4E00-0x9FFF, 0x3400-0x4DBF
                if 0x4E00 <= code <= 0x9FFF or 0x3400 <= code <= 0x4DBF:
                    needs_translation = True
                    break
                # Thai: 0x0E00-0x0E7F
                if 0x0E00 <= code <= 0x0E7F:
                    needs_translation = True
                    break
                # Arabic: 0x0600-0x06FF
                if 0x0600 <= code <= 0x06FF:
                    needs_translation = True
                    break
                # Cyrillic (Russian, etc.): 0x0400-0x04FF
                if 0x0400 <= code <= 0x04FF:
                    needs_translation = True
                    break

        if needs_translation:
            logger.warning(
                f"Summary in wrong script for staff_lang={staff_lang}, translating: {summary}"
            )
            summary = _translate_summary_to_staff_lang(self.llm, summary, staff_lang)

        # SECURITY: Always use guest's room - cross-room requests are NOT allowed
        guest_room = self._get_room_number()
        if room_from_args and room_from_args != guest_room:
            logger.warning(
                f"Cross-room request blocked: guest room {guest_room}, requested {room_from_args}"
            )
        room_num = guest_room  # Always use guest's actual room

        # Include room number in summary if not present
        if room_num and room_num.lower() not in summary.lower():
            # Use localized room prefix based on staff language (staff_lang already defined above)
            room_labels = {"ro": "Camera", "th": "ห้อง", "en": "Room"}
            room_label = room_labels.get(staff_lang, "Room")
            summary = f"{room_label} {room_num}: {summary}"

        # DEDUPLICATION: Check if similar task exists in last 60 seconds
        recent_cutoff = datetime.now(timezone.utc) - timedelta(seconds=60)
        existing_task = (
            self.db.query(Task)
            .filter(
                Task.hotel_id == self.hotel.id,
                Task.type == task_type,
                Task.created_at >= recent_cutoff,
                Task.staff_summary == summary,
            )
            .first()
        )
        if existing_task:
            logger.info(f"Duplicate task detected, returning existing #{existing_task.id}")
            return existing_task

        task = Task(
            hotel_id=self.hotel.id,
            stay_id=self.stay.id if self.stay else None,
            type=task_type,
            status=TaskStatus.OPEN,
            staff_summary=summary,
            payload_json={"room": room_num, "created_by": "brain"},
            priority=priority,
        )
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)

        # Notify staff
        try:
            notify_new_task(task, self.hotel)
        except Exception as e:
            logger.warning(f"Failed to notify staff: {e}")

        logger.info(
            f"Created task #{task.id}: {task_type.value} - {summary} [Priority: {priority}]"
        )
        return task

    def _add_to_task(self, args: dict) -> Optional[Task]:
        """Add note to existing task. ONLY allowed for FOOD_BEVERAGE tasks."""
        task_id = args.get("task_id")
        note = args.get("note", "")

        task = self.db.query(Task).filter(Task.id == task_id).first()
        if not task:
            logger.warning(f"Task #{task_id} not found")
            return None

        # ENFORCE: add_to_task is ONLY for FOOD_BEVERAGE
        if task.type != TaskType.FOOD_BEVERAGE:
            logger.warning(
                f"Task #{task_id} is {task.type.value}, not FOOD_BEVERAGE. Creating FOOD_BEVERAGE task instead."
            )
            return self._create_task({"category": "FOOD_BEVERAGE", "summary": note})

        # Only add to OPEN or IN_PROGRESS tasks
        if task.status not in [TaskStatus.OPEN, TaskStatus.IN_PROGRESS]:
            logger.warning(
                f"Task #{task_id} is {task.status.value}, creating new FOOD_BEVERAGE task instead"
            )
            # Create a new FOOD_BEVERAGE task instead
            return self._create_task({"category": "FOOD_BEVERAGE", "summary": note})

        # TRANSLATE note to staff language (same logic as create_task)
        staff_lang = self.hotel.staff_language or "en"
        needs_translation = False

        if staff_lang == "th":
            # For Thai staff: check if note contains ANY Thai characters
            thai_chars = sum(1 for c in note if 0x0E00 <= ord(c) <= 0x0E7F)
            if thai_chars == 0:
                needs_translation = True
        elif staff_lang == "ro":
            # For Romanian staff: check for non-Latin scripts OR English text
            for c in note:
                code = ord(c)
                if 0x4E00 <= code <= 0x9FFF or 0x3400 <= code <= 0x4DBF:  # CJK
                    needs_translation = True
                    break
                if 0x0E00 <= code <= 0x0E7F:  # Thai
                    needs_translation = True
                    break
                if 0x0600 <= code <= 0x06FF:  # Arabic
                    needs_translation = True
                    break
                if 0x0400 <= code <= 0x04FF:  # Cyrillic
                    needs_translation = True
                    break
            # Check for common English words
            if not needs_translation:
                english_indicators = [
                    "guest",
                    "wants",
                    "request",
                    "check-out",
                    "check-in",
                    "late",
                    "early",
                    "room service",
                    "towel",
                    "clean",
                    "maintenance",
                    "broken",
                    "lost",
                    "found",
                    "emergency",
                ]
                note_lower = note.lower()
                for word in english_indicators:
                    if word in note_lower:
                        needs_translation = True
                        logger.warning(f"English word '{word}' detected in Romanian staff note")
                        break
        else:  # staff_lang == "en"
            for c in note:
                code = ord(c)
                if 0x4E00 <= code <= 0x9FFF or 0x3400 <= code <= 0x4DBF:  # CJK
                    needs_translation = True
                    break
                if 0x0E00 <= code <= 0x0E7F:  # Thai
                    needs_translation = True
                    break
                if 0x0600 <= code <= 0x06FF:  # Arabic
                    needs_translation = True
                    break
                if 0x0400 <= code <= 0x04FF:  # Cyrillic
                    needs_translation = True
                    break

        if needs_translation:
            logger.warning(f"Note in wrong script for staff_lang={staff_lang}, translating: {note}")
            note = _translate_summary_to_staff_lang(self.llm, note, staff_lang)

        # Append to staff_summary
        if task.staff_summary:
            task.staff_summary = f"{task.staff_summary}. + {note}"
        else:
            task.staff_summary = note

        self.db.add(task)
        self.db.commit()

        logger.info(f"Added to task #{task.id}: {note}")
        return task

    def process_message(self, user_message: str) -> Tuple[str, Optional[Task]]:
        """
        Process a guest message and return (response_text, task_if_created).
        This is the main entry point.
        """
        # === BUTTON DETECTION: Hotel Policies ===
        msg_lower = user_message.lower().strip()
        if msg_lower in ["hotel policies", "politici hotel", "นโยบายโรงแรม"]:
            knowledge = (self.hotel.settings or {}).get("custom_knowledge_text", "")
            if knowledge and "standard hotel policies" not in knowledge.lower():
                return knowledge, None
            else:
                lang = self.hotel.staff_language or "en"
                if lang == "ro":
                    fallback = "Nu am politicile hotelului. Contactați recepția."
                elif lang == "th":
                    fallback = "ไม่มีนโยบายโรงแรมในระบบ กรุณาติดต่อแผนกต้อนรับ"
                else:
                    fallback = "I don't have hotel policies. Please contact reception."
                return fallback, None
        # === BUTTON DETECTION: Menu ===
        if msg_lower in ["menu", "meniu", "เมนู"]:
            settings = self.hotel.settings or {}
            menu_text = settings.get("hotel_products_text", "").strip()
            if menu_text:
                return menu_text, None
            # No menu in DB - let LLM handle (will say "contact reception")

        # === BUTTON DETECTION: Housekeeping ===
        # Not hardcoded - LLM handles confirmation flow + task creation
        # === END BUTTON DETECTION ===

        system_prompt = self._build_system_prompt()
        history = self._get_history()

        # Add current message to history with language context
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history)
        # Add language reminder right before user message - LLM will detect the language
        messages.append(
            {
                "role": "system",
                "content": "CRITICAL: Detect the language of the next message and respond in EXACTLY that same language. This applies to ALL languages worldwide.",
            }
        )
        messages.append({"role": "user", "content": _sanitize_text(user_message)})

        try:
            # Build tools with hotel's staff language and settings
            staff_lang = self.hotel.staff_language or "en"
            hotel_settings = self.hotel.settings or {}
            tools = _build_tools(staff_lang, hotel_settings)

            # Call LLM with tools
            response = self.llm.client.chat.completions.create(
                model=self.llm.model,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                temperature=0.4,
                max_tokens=4000,
                timeout=self.llm.timeout,
            )

            choice = response.choices[0]
            task_created = None

            # Check for tool calls
            if choice.message.tool_calls:
                # First, append the assistant message with tool_calls
                messages.append(
                    {
                        "role": "assistant",
                        "content": choice.message.content,
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments,
                                },
                            }
                            for tc in choice.message.tool_calls
                        ],
                    }
                )

                # Execute each tool and add response for each
                for tool_call in choice.message.tool_calls:
                    func_name = tool_call.function.name
                    func_args = json.loads(tool_call.function.arguments or "{}")
                    logger.info(f"Tool call: {func_name} -> {func_args}")
                    task = self._execute_tool(func_name, func_args)
                    if task:
                        task_created = task

                    # Add tool response for THIS tool_call
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": f"Task #{task.id} created" if task else "Done",
                        }
                    )

                # Get final response after all tool executions
                final_response = self.llm.client.chat.completions.create(
                    model=self.llm.model,
                    messages=messages,
                    temperature=0.4,
                    max_tokens=4000,
                    timeout=self.llm.timeout,
                )
                response_text = final_response.choices[0].message.content or ""
            else:
                response_text = choice.message.content or ""

            return response_text.strip(), task_created

        except Exception as e:
            logger.error(f"Brain error: {e}")
            # Use multilingual fallback based on hotel's staff language
            staff_lang = self.hotel.staff_language or "en"
            return _get_fallback_message(staff_lang), None


def process_with_brain(db: Session, message: Message) -> Optional[Message]:
    """
    Main entry point - process incoming message with the hotel brain.
    Returns the bot's response message (already saved to DB).
    """
    conversation = message.conversation
    if not conversation:
        logger.error(f"No conversation for message {message.id}")
        return None

    hotel = conversation.hotel
    if not hotel:
        logger.error(f"No hotel for conversation {conversation.id}")
        return None

    # CRITICAL: Refresh hotel to get latest settings from DB
    # This prevents stale cached data when settings were updated in another session
    db.refresh(hotel)

    # Determine context: PRO tier (stay) vs BASIC tier (room)
    room = None
    guest = None
    stay = None

    if conversation.stay_id and conversation.stay:
        # PRO tier - has stay
        stay = conversation.stay
        room = stay.room
        guest = stay.guest
    elif conversation.room_id and conversation.room:
        # BASIC tier - has room only
        room = conversation.room
        guest = conversation.guest  # May be anonymous
    else:
        # Fallback - try to get room from stay
        if conversation.stay:
            stay = conversation.stay
            room = stay.room
            guest = stay.guest

    # Create brain and process
    brain = HotelBrain(
        db=db, hotel=hotel, conversation=conversation, room=room, guest=guest, stay=stay
    )

    response_text, task = brain.process_message(message.text)

    # Save bot response
    bot_message = Message(
        conversation_id=conversation.id,
        sender_type=MessageSender.BOT,
        direction=MessageDirection.OUTGOING,
        text=response_text,
    )
    db.add(bot_message)
    try:
        db.commit()
        db.refresh(bot_message)
    except Exception as e:
        logger.error(f"DB commit failed for conv {conversation.id}: {e}")
        db.rollback()
        return None

    logger.info(f"Brain response for conv {conversation.id}: {response_text[:100]}...")
    return bot_message
