
import os
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types

import tools

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

MODELS = [
    "gemini-3.5-flash",
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash-lite",
    "gemini-3-flash-preview",
]


# ---------- TOOLS ----------
def build_tools(business):

    def lookup_record(record_id: str) -> dict:
        """Look up an order or reservation using its ID."""
        return tools.lookup_record(business, record_id)

    def check_policy(record_id: str) -> dict:
        """Check whether an order is eligible for return."""
        return tools.check_policy(business, record_id)

    def create_request(
        request_type: str,
        record_id: str,
        details: str
    ) -> dict:
        """Register a complaint, return, exchange or reservation request."""
        return tools.create_request(
            business, request_type, record_id, details
        )

    def escalate_to_human(
        summary: str,
        priority: str = "normal"
    ) -> dict:
        """Transfer the customer's issue to human support."""
        return tools.escalate_to_human(
            business, summary, priority
        )

    all_tools = {
        "lookup_record": lookup_record,
        "check_policy": check_policy,
        "create_request": create_request,
        "escalate_to_human": escalate_to_human,
    }

    enabled = tools.load_config(business)["enabled_tools"]

    return [
        all_tools[name]
        for name in enabled
        if name in all_tools
    ]


# ---------- SYSTEM PROMPT ----------
def build_prompt(business):

    cfg = tools.load_config(business)
    faq = tools.load_faq(business)

    return f"""
You are {cfg['assistant_name']}, the customer support assistant
for {cfg['business_name']} ({cfg['industry']}).

Powered by Convorza AI.

Tone: {cfg['tone']}.

Supported languages:
{', '.join(cfg['languages'])}.

LANGUAGE RULE:
Always reply in the same language used by the customer.
Understand English, Hindi written in Roman script, and Hinglish.
If the customer mixes Hindi and English, reply naturally in Hinglish.
Do not unnecessarily translate the customer's language.

Business information:
{faq}

Allowed request types:
{', '.join(cfg['request_types'])}.

Escalation rules:
{'; '.join(cfg['escalation_rules'])}.

IMPORTANT RULES:

1. Never invent order details, prices, policies or dates.
2. Use business information and actual tool results.
3. Ask for an order or reservation ID when needed.
4. Use lookup_record to check orders and reservations.
5. Use check_policy for return eligibility.
6. Use create_request to register customer requests.
7. Use escalate_to_human when human assistance is needed.
8. Never claim an action succeeded unless the tool confirms it.
9. Keep responses short, friendly and conversational.
10. If you cannot resolve an issue, offer human support.
"""


# ---------- RESPONSE EXTRACTION ----------
def get_text(response):

    try:
        if response.text:
            return response.text
    except Exception:
        pass

    if response.candidates:
        for candidate in response.candidates:
            if candidate.content:
                for part in candidate.content.parts:
                    if part.text:
                        return part.text

    return None


# ---------- MAIN CHAT FUNCTION ----------

# ---------- MAIN CHAT FUNCTION ----------
def chat(business, history, user_message):

    contents = []

    # Add previous conversation turns in the correct order.
    for turn in history:
        role = turn.get("role")
        text = turn.get("text", "")

        if role not in ("user", "model") or not text:
            continue

        # Merge consecutive turns with the same role.
        if contents and contents[-1].role == role:
            contents[-1].parts.append(types.Part(text=text))
        else:
            contents.append(
                types.Content(
                    role=role,
                    parts=[types.Part(text=text)]
                )
            )

    # The latest message must be from the user.
    if contents and contents[-1].role == "model":
        contents.pop()

    if contents and contents[-1].role == "user":
        contents[-1].parts.append(types.Part(text=user_message))
    else:
        contents.append(
            types.Content(
                role="user",
                parts=[types.Part(text=user_message)]
            )
        )

    available_tools = build_tools(business)

    tool_map = {
        function.__name__: function
        for function in available_tools
    }

    config = types.GenerateContentConfig(
        system_instruction=build_prompt(business),
        tools=available_tools,
    )

    last_error = None

    for model in MODELS:
        try:
            working_contents = list(contents)

            for tool_round in range(6):

                response = client.models.generate_content(
                    model=model,
                    contents=working_contents,
                    config=config
                )

                candidate = (
                    response.candidates[0]
                    if response.candidates
                    else None
                )

                if not candidate or not candidate.content:
                    return get_text(response) or (
                        "Sorry, I couldn't generate a response."
                    )

                function_calls = [
                    part.function_call
                    for part in candidate.content.parts
                    if part.function_call
                ]

                # If Gemini has finished, return its answer.
                if not function_calls:
                    return get_text(response) or (
                        "Sorry, I couldn't generate a response."
                    )

                # Add Gemini's function-call turn.
                working_contents.append(candidate.content)

                function_responses = []

                for function_call in function_calls:
                    function = tool_map.get(function_call.name)

                    if function is None:
                        result = {
                            "error": "This tool is not available."
                        }
                    else:
                        try:
                            arguments = dict(function_call.args or {})
                            result = function(**arguments)
                        except Exception as error:
                            result = {"error": str(error)}

                    function_responses.append(
                        types.Part.from_function_response(
                            name=function_call.name,
                            response={"result": result}
                        )
                    )

                # Function responses must immediately follow
                # the model's function-call turn.
                working_contents.append(
                    types.Content(
                        role="user",
                        parts=function_responses
                    )
                )

            return (
                "I couldn't complete that request. "
                "Could you please try again?"
            )

        except Exception as error:
            last_error = error
            print(f"Gemini error with {model}: {error}")
            time.sleep(2)

    print(f"All Gemini models failed. Last error: {last_error}")

    return (
        "Sorry, I'm having trouble responding right now. "
        "Please try again in a moment."
    )


# ---------- TERMINAL TEST ----------
if __name__ == "__main__":

    import sys

    business = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "kora_clothing"
    )

    cfg = tools.load_config(business)

    print(
        f"Chatting with {cfg['assistant_name']} "
        f"at {cfg['business_name']}."
    )

    history = []

    while True:

        message = input("\nYou: ")

        if message.strip().lower() == "quit":
            break

        answer = chat(business, history, message)

        print(f"\n{cfg['assistant_name']}: {answer}")

        history.append({
            "role": "user",
            "text": message
        })

        history.append({
            "role": "model",
            "text": answer
        })
