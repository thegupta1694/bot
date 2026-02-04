import asyncio
import sys
import streamlit as st
import pandas as pd
import random
import json

# 1. WINDOWS PATCH: Fix for Playwright on Windows laptops
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from logic_engine import generate_section_logic
from runner import run_audit

st.set_page_config(page_title="AI Survey Logic Auditor Pro", layout="wide")

# --- PATH PERMUTATION ENGINE (Optimized for Sequential Flow) ---
def get_all_paths(questions):
    if not questions:
        return []
    
    q_map = {q['id']: q for q in questions if isinstance(q, dict) and 'id' in q}
    q_ids_ordered = [q['id'] for q in questions]
    all_paths = []

    def find_paths(current_id, current_path):
        # Safety cap to prevent memory crash on massive surveys
        if len(all_paths) > 2500:
            return

        if current_id not in q_map:
            if current_path: all_paths.append(current_path)
            return

        question = q_map[current_id]
        options = question.get('options', [])
        
        if not options:
            # Fallback: If no options exist, try to move to the next sequential question
            curr_idx = q_ids_ordered.index(current_id)
            if curr_idx + 1 < len(q_ids_ordered):
                find_paths(q_ids_ordered[curr_idx + 1], current_path)
            else:
                all_paths.append(current_path)
            return

        for opt in options:
            option_text = opt.get('text', 'Unknown Option')
            new_path = current_path + [option_text]
            dest = opt.get('next_destination')

            # Handle Sequential Default: If no destination is set, find next ID in ordered list
            if not dest or dest == "NEXT":
                try:
                    curr_idx = q_ids_ordered.index(current_id)
                    if curr_idx + 1 < len(q_ids_ordered):
                        dest = q_ids_ordered[curr_idx + 1]
                    else:
                        dest = "SUBMIT"
                except ValueError:
                    dest = "SUBMIT"

            if dest in ["TERMINATE", "SUBMIT", "End", "null"]:
                all_paths.append(new_path)
            else:
                # Basic recursion protection
                if dest == current_id:
                    all_paths.append(new_path)
                else:
                    find_paths(dest, new_path)

    # Start recursion from the first question of the first section
    if q_ids_ordered:
        find_paths(q_ids_ordered[0], [])
    return all_paths

# --- UI HEADER & SIDEBAR ---
st.title("📋 AI Survey Logic Auditor Pro")
st.markdown("Analyze logical permutations and run automated audits across multiple survey sections.")

with st.sidebar:
    st.header("1. Credentials & Model")
    api_key = st.text_input("Portkey API Key", type="password")
    
    model_choice = st.selectbox(
        "Select AI Model",
        ["@personal-openai/gpt-5.1", "@personal-openai/gpt-5", "@personal-openai/gpt-4.1"],
        index=2
    )
    
    st.divider()
    st.header("2. Survey Structure")
    num_sections = st.number_input("Number of Sections", min_value=1, max_value=20, value=1)
    
    if st.button("Reset Session", use_container_width=True):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

# --- STEP 1: MULTI-SECTION INGESTION ---
st.subheader("Step 1: Upload Section Specifications")
st.info(f"Upload your {num_sections} .docx files in the sequence they appear in the survey.")

upload_cols = st.columns(min(num_sections, 3))
files = []
for i in range(num_sections):
    with upload_cols[i % 3]:
        uploaded_file = st.file_uploader(f"Section {i+1} (.docx)", type="docx", key=f"uploader_{i}")
        files.append(uploaded_file)

if all(files) and api_key:
    if "logic_map" not in st.session_state:
        if st.button("Analyze & Stitch Logic", type="primary"):
            with st.spinner(f"Compiling logic from {num_sections} files using {model_choice}..."):
                try:
                    master_questions = []
                    for idx, file_obj in enumerate(files):
                        section_num = idx + 1
                        section_data = generate_section_logic(
                            file_obj, 
                            api_key, 
                            model_choice, 
                            section_num, 
                            num_sections
                        )
                        
                        # VALIDATION: Ensure the AI actually returned questions
                        qs = section_data.get("questions", [])
                        if not qs:
                            st.error(f"Section {section_num} returned no questions. Check if the model '{model_choice}' is hallucinating the JSON structure.")
                            return # Stop execution
                        
                        master_questions.extend(qs)
                    
                    st.session_state.logic_map = {"questions": master_questions}
                    st.success("Logic Stitched Successfully!")
                    # Reset dependent states if logic changes
                    if "display_df" in st.session_state: del st.session_state.display_df
                    st.rerun()
                except Exception as e:
                    st.error(f"Analysis Error: {e}")

# --- STEP 2: REVIEW & DEFINE TEST CASES ---
if "logic_map" in st.session_state:
    st.divider()
    
    # --- NEW: LOGIC JSON DROPDOWN ---
    with st.expander("🔍 View Understood Logic Map (JSON)"):
        st.markdown("Verify that the AI has correctly extracted the questions and branching logic.")
        st.json(st.session_state.logic_map)
    
    st.subheader("Step 2: Define Test Cases")
    
    if "display_df" not in st.session_state:
        raw_questions = st.session_state.logic_map.get("questions", [])
        all_possible_paths = get_all_paths(raw_questions)
        
        st.session_state.test_paths_lookup = {i: path for i, path in enumerate(all_possible_paths)}
        st.session_state.display_df = pd.DataFrame({
            "Run?": [True] * len(all_possible_paths),
            "Path Sequence": [" → ".join(p) for p in all_possible_paths],
            "path_id": list(range(len(all_possible_paths)))
        })

    # Controls: Sample Size | Random | All | Clear
    total_paths = len(st.session_state.display_df)
    c1, c2, c3, c4, c5 = st.columns([1.5, 1, 1, 1, 3])
    
    with c1: 
        sample_size = st.number_input("Sample Size", 1, max(1, total_paths), min(10, total_paths))
    with c2:
        if st.button("🎲 Random", use_container_width=True):
            st.session_state.display_df["Run?"] = False
            idx = random.sample(range(total_paths), int(min(sample_size, total_paths)))
            st.session_state.display_df.loc[idx, "Run?"] = True
            st.rerun()
    with c3:
        if st.button("✅ All", use_container_width=True):
            st.session_state.display_df["Run?"] = True
            st.rerun()
    with c4:
        if st.button("🗑️ Clear", use_container_width=True):
            st.session_state.display_df["Run?"] = False
            st.rerun()

    # Path Selection Table
    edited_df = st.data_editor(
        st.session_state.display_df,
        column_config={
            "Run?": st.column_config.CheckboxColumn("Audit?", width="small"),
            "Path Sequence": st.column_config.TextColumn("Path Sequence", width="large"),
            "path_id": None
        },
        disabled=["Path Sequence"], 
        hide_index=True, 
        use_container_width=True,
        key="main_data_editor"
    )
    st.session_state.display_df = edited_df

    # --- STEP 3: AUDIT EXECUTION ---
    st.divider()
    st.subheader("Step 3: Live Audit Execution")
    survey_url = st.text_input("Enter Target Survey URL (Qualtrics, Google Forms, etc.)")
    
    selected_rows = edited_df[edited_df["Run?"] == True]
    
    if st.button(f"🚀 Launch Audit on {len(selected_rows)} Selected Cases", type="primary"):
        if not survey_url:
            st.warning("Please provide a survey URL.")
        elif len(selected_rows) == 0:
            st.error("Please select at least one path to audit.")
        else:
            progress = st.progress(0)
            status = st.empty()
            res_table = st.empty()
            results_data = []

            for idx, (row_idx, row) in enumerate(selected_rows.iterrows()):
                status.write(f"⏳ Testing Case {idx+1} of {len(selected_rows)}...")
                path_to_test = st.session_state.test_paths_lookup[row["path_id"]]
                
                # Execute Playwright Audit
                audit_result = run_audit(survey_url, path_to_test)
                
                # Extract results
                done = audit_result["steps_completed"]
                total = audit_result["total_steps_in_path"]
                last_ans = audit_result["last_clicked"]
                
                # Logic-Aware Validation
                is_term = False
                for q in st.session_state.logic_map['questions']:
                    for opt in q.get('options', []):
                        if opt.get('text') == last_ans:
                            if opt.get('next_destination') in ['TERMINATE', 'SUBMIT']:
                                is_term = True

                # Determine Status Icons
                if audit_result["error"]:
                    icon, msg = "❌", f"System Error: {audit_result['error'][:50]}"
                elif done == total:
                    icon, msg = "✅", "Success: Path Fully Reached"
                elif is_term:
                    icon, msg = "🎯", f"Correct Term: Ended at '{last_ans}'"
                else:
                    icon, msg = "⚠️", f"Logic Break: Stopped at '{last_ans}'"

                # Update live table
                results_data.append({
                    "Case": idx + 1,
                    "Result": icon,
                    "Path Sequence": row["Path Sequence"],
                    "Status Detail": msg
                })
                res_table.table(results_data)
                progress.progress((idx + 1) / len(selected_rows))

            status.success(f"Audit Complete. {len(selected_rows)} cases processed.")
else:
    if not api_key:

        st.warning("Please enter your API Key in the sidebar to begin.")
