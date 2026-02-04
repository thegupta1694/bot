import httpx
import mammoth
from openai import OpenAI
import json

def generate_section_logic(file_object, api_key, model_name, section_index, total_sections):
    """
    Converts a single .docx section into a structured logic map using a user-specified model.
    """
    result = mammoth.convert_to_html(file_object)
    html_content = result.value 
    
    custom_http_client = httpx.Client(proxy=None, trust_env=False)
    client = OpenAI(
        api_key=api_key,
        base_url="https://portkey.bain.dev/v1",
        http_client=custom_http_client
    )

    next_section_id = f"S{section_index + 1}_Q1" if section_index < total_sections else "SUBMIT"

    prompt = f"""
    You are a Senior Survey Programmer. Your task is to convert the provided HTML survey specification into a structured JSON Logic Map.
    This is SECTION {section_index} of {total_sections}.

    ### 1. IDENTITY & STITCHING RULES (CRITICAL)
    - **Namespace:** Every Question ID in this file MUST follow the format: `S{section_index}_Qn`.
    - **Starting Point:** The first question of this document MUST be named `S{section_index}_Q1`.
    - **Exit Strategy:** 
        - If a question is the final question of this section, its 'next_destination' must be "{next_section_id}".
        - If an option leads to a disqualification, 'next_destination' must be "TERMINATE" and 'is_terminate' must be true.

    ### 2. MECE LOGIC PRINCIPLES
    - **Mutually Exclusive:** Ensure each option has exactly one 'next_destination'. No overlapping logic.
    - **Collectively Exhaustive:** Every single option provided in the spec must be mapped. If the spec implies "All others go to X", you must explicitly map every remaining option to destination X.
    - **Sequential Fallback:** If the spec does not specify a skip for an option, the 'next_destination' should be the next logical question ID (e.g., S{section_index}_Q1 -> S{section_index}_Q2).

    ### 3. UI-READY CONTENT RULES
    - **Literal Labels Only:** The 'text' field for options must contain ONLY the literal text a respondent sees on the screen.
    - **Strip Meta-Data:** You MUST remove markers like '[TERMINATE]', '[QUALIFY]', '[GOTO QX]', or color-coded instructions from the 'text' field.
    - **Logic Extraction:** Use those stripped markers ONLY to populate the 'next_destination' and 'is_terminate' fields.

    ### 4. OUTPUT JSON STRUCTURE
    {{
      "questions": [
        {{
          "id": "S{section_index}_Q1",
          "text": "Clean question text",
          "type": "single-select | multi-select | text-input",
          "options": [
            {{ 
              "text": "Literal Option Label", 
              "next_destination": "S{section_index}_Qn | {next_section_id} | TERMINATE", 
              "is_terminate": boolean 
            }}
          ]
        }}
      ]
    }}

    ### SURVEY SPECIFICATION CONTENT:
    {html_content}
    """

    response = client.chat.completions.create(
        model=model_name, # DYNAMIC MODEL NAME
        messages=[
            {"role": "system", "content": "You are a precise JSON compiler. Output ONLY valid JSON."},
            {"role": "user", "content": prompt}
        ],
        response_format={ "type": "json_object" }
    )

    try:
        logic_data = json.loads(response.choices[0].message.content)
        logic_data["section_id"] = section_index
        return logic_data
    except json.JSONDecodeError as e:

        raise Exception(f"AI returned invalid JSON: {e}")


