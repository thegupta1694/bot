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

    ### MANDATORY ID FORMAT:
    - Every question ID MUST start with 'S{section_index}_'. 
    - Example: 'S{section_index}_Q1', 'S{section_index}_Q2'.
    - DO NOT use plain 'Q1'.

    ### SECTION LINKING:
    - If a question is the last one in this document, its 'next_destination' MUST be '{next_section_start}'.
    
    ### CRITICAL RULES FOR OPTION TEXT:
    1. **CLEAN LABELS ONLY:** The 'text' field for options must contain ONLY the literal text a respondent sees. 
    2. **STRIP META-DATA:** Remove markers like '[TERMINATE]' or '[QUALIFY]'.

    ### OUTPUT JSON STRUCTURE:
    {{
      "questions": [
        {{
          "id": "S{section_index}_Q1",
          "text": "Clean question text",
          "type": "single-select | multi-select | text-input",
          "options": [
            {{ "text": "Clean Option Label", "next_destination": "S{section_index}_Qn | {next_section_start} | TERMINATE", "is_terminate": bool }}
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
