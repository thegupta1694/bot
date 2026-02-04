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

    next_section_start = f"S{section_index + 1}_Q1" if section_index < total_sections else "SUBMIT"

    prompt = f"""
    You are a Senior Survey Programmer. Convert this HTML survey spec into a JSON Logic Map.
    This is SECTION {section_index} of {total_sections}.

    ### CRITICAL RULES FOR OPTION TEXT:
    1. **CLEAN LABELS ONLY:** The 'text' field for options must contain ONLY the literal text a respondent sees. 
    2. **STRIP META-DATA:** You MUST remove markers like '[TERMINATE]', '[QUALIFY]', or color-coded instructions.
    3. **LOGIC EXTRACTION:** Use the stripped markers ONLY to set the 'next_destination' and 'is_terminate' fields.

    ### ARCHITECTURAL RULES:
    1. **Sequential Default:** If no skip is mentioned, 'next_destination' is the NEXT question.
    2. **ID Format:** Use 'S{section_index}_Qn'.
    3. **Section Linking:** The last question of this doc should point to "{next_section_start}".

    ### OUTPUT JSON STRUCTURE:
    {{
      "questions": [
        {{
          "id": "S{section_index}_Q1",
          "text": "Clean question text",
          "type": "single-select | multi-select | text-input",
          "show_if": "Logic description or null",
          "options": [
            {{ "text": "Clean Option Label", "next_destination": "S_Qn/TERMINATE/{next_section_start}", "is_terminate": bool }}
          ]
        }}
      ]
    }}

    ### SPEC CONTENT:
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