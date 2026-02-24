"""
Customer-Facing Conversation Agent — the front-line agent that talks to customers.
Includes comprehensive guardrails for safe, helpful, and compliant interactions.
"""

from __future__ import annotations

import json
from typing import Any

from agents.base import get_client

GUARDRAILS = """\
MANDATORY GUARDRAILS — You must follow these at all times:

1. NO MEDICAL ADVICE: Never diagnose, recommend dosages, or suggest treatments.
   Say: "I'd recommend speaking with our pharmacist about that."

2. NO PRESCRIPTION DETAILS TO UNVERIFIED USERS: Prescription info is only shared
   after the customer has been authenticated (customer_id verified in context).

3. DRUG INTERACTION ESCALATION: If a drug interaction flag is present in the order
   context, you MUST mention it and recommend a pharmacist consultation before
   completing the order. Do NOT downplay interaction warnings.

4. ALLERGY SAFETY: If the customer has known allergies and is ordering something
   that could be a concern, flag it clearly. Say: "I see you have a [X] allergy
   on file — please confirm with our pharmacist that this product is safe for you."

5. DATA PRIVACY: Never share customer data (address, phone, email, full order history)
   in the conversation. Summarize instead of quoting raw records.

6. PRICE ACCURACY: Only quote prices from the inventory data. Never estimate or
   guess prices.

7. STOCK HONESTY: If an item is out of stock, say so clearly. Provide the ETA if
   available. Never promise availability you can't confirm.

8. SCOPE BOUNDARIES: If asked about topics outside retail/pharmacy/clinic scope
   (legal advice, insurance claims, complex medical questions), redirect:
   "That's outside what I can help with — I'd recommend contacting [appropriate resource]."

9. TONE: Be warm, professional, and concise. Use the customer's name when available.
   Acknowledge loyalty status when relevant ("As a Gold member, ...").

10. ESCALATION: If the customer is frustrated or the situation is complex, offer to
    connect them with a human associate: "Would you like me to connect you with a
    team member who can help further?"
"""

SYSTEM_PROMPT = f"""\
You are the Customer Service Agent for a retail pharmacy chain. You interact directly
with customers via chat. You are friendly, helpful, and safety-conscious.

You receive context from internal systems about:
- The customer's profile and loyalty status
- Their order status and inventory availability
- Pharmacy information (prescriptions, refills, interactions)
- Clinic information (appointments, wellness recommendations)

Use this context to provide personalized, accurate responses. Always follow the
guardrails below — they are non-negotiable.

{GUARDRAILS}
"""


class CustomerAgent:
    """Customer-facing conversational agent with safety guardrails."""

    def __init__(self, model: str = "gpt-4.1"):
        self.model = model
        self.conversations: dict[str, list[dict]] = {}

    def start_conversation(self, customer_id: str, order_context: dict) -> str:
        """Initialize a conversation with order context and greet the customer."""
        system_messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "system",
                "content": (
                    "INTERNAL CONTEXT (do not share raw data with the customer):\n"
                    f"{json.dumps(order_context, indent=2, default=str)}"
                ),
            },
        ]
        self.conversations[customer_id] = system_messages

        # Generate initial greeting based on the order context
        return self.send_message(
            customer_id,
            "[SYSTEM] The customer has just placed an order. Greet them and "
            "provide a summary of their order status based on the context provided. "
            "Include any relevant pharmacy flags, clinic reminders, or personalized suggestions.",
            is_system=True,
        )

    def send_message(
        self,
        customer_id: str,
        message: str,
        is_system: bool = False,
    ) -> str:
        """Send a message and get a response. is_system=True for internal prompts."""
        if customer_id not in self.conversations:
            return "Error: No active conversation. Please start a new conversation first."

        role = "system" if is_system else "user"
        self.conversations[customer_id].append({"role": role, "content": message})

        client = get_client()
        response = client.chat.completions.create(
            model=self.model,
            messages=self.conversations[customer_id],
        )

        assistant_msg = response.choices[0].message.content or ""
        self.conversations[customer_id].append({"role": "assistant", "content": assistant_msg})

        # Guardrail post-processing check
        assistant_msg = self._apply_post_guardrails(assistant_msg)

        return assistant_msg

    def _apply_post_guardrails(self, response: str) -> str:
        """Post-process the response to catch any guardrail violations."""
        # Check for common guardrail violations and add disclaimers if needed
        medical_keywords = [
            "you should take", "i recommend taking", "the correct dose is",
            "you have", "you are diagnosed", "your condition",
        ]
        response_lower = response.lower()
        for keyword in medical_keywords:
            if keyword in response_lower:
                response += (
                    "\n\n*Please note: I'm not a medical professional. For specific "
                    "medical advice, please consult with our pharmacist or your healthcare provider.*"
                )
                break
        return response

    def get_conversation_history(self, customer_id: str) -> list[dict]:
        """Get the conversation history (excluding system messages) for review."""
        if customer_id not in self.conversations:
            return []
        return [
            msg for msg in self.conversations[customer_id]
            if msg["role"] in ("user", "assistant")
        ]
