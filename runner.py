from playwright.sync_api import sync_playwright
import time

def run_audit(survey_url, persona_steps):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True) 
        context = browser.new_context(viewport={'width': 1280, 'height': 800})
        page = context.new_page()
        
        steps_completed = 0
        last_clicked = "None"
        final_error = None
        clicked_elements_registry = [] # Keep track of specific element IDs we've used

        try:
            page.goto(survey_url, wait_until="networkidle", timeout=60000)
            
            for answer in persona_steps:
                # 1. Check for end screen
                body_text = page.inner_text("body").lower()
                if any(x in body_text for x in ["thank you", "recorded", "unfortunately", "disqualified"]):
                    break 

                # 2. Advanced Selection Logic
                # We look for labels or buttons that match the text
                # We filter to ensure we don't click the same exact radio button twice
                found_click = False
                
                # Try specific selectors that Qualtrics/Google Forms use for options
                selectors = [
                    f"label:has-text('{answer}')",
                    f"span:has-text('{answer}')",
                    f"button:has-text('{answer}')",
                    f"div[role='radio']:has-text('{answer}')",
                    f"div[role='checkbox']:has-text('{answer}')"
                ]

                for selector in selectors:
                    candidates = page.locator(selector)
                    count = candidates.count()
                    
                    for i in range(count):
                        candidate = candidates.nth(i)
                        
                        # Get a unique internal ID for this element to avoid re-clicking
                        element_id = str(candidate.evaluate("node => node.innerText + node.getBoundingClientRect().top"))
                        
                        if candidate.is_visible() and element_id not in clicked_elements_registry:
                            candidate.scroll_into_view_if_needed()
                            candidate.click(force=True)
                            
                            clicked_elements_registry.append(element_id)
                            last_clicked = answer
                            steps_completed += 1
                            found_click = True
                            time.sleep(0.5) # Wait for Qualtrics JS to register click
                            break
                    if found_click: break

                if not found_click:
                    # If we can't find the answer, maybe it's on the next page
                    # Attempt to click Next to see if it reveals the question
                    next_btn = page.locator('#NextButton, #next-button, [aria-label="Next"]').first
                    if next_btn.is_visible():
                        next_btn.click()
                        page.wait_for_load_state("networkidle")
                        time.sleep(1)
                        continue # Re-try current answer on the new page
                    else:
                        break # Truly stuck

                # 3. Intelligent "Next" Navigation
                # We only click Next if the current page seems "finished" 
                # or if we need to trigger validation to see if more questions exist.
                next_btn = page.locator('#NextButton, #next-button, [aria-label="Next"]').first
                if next_btn.is_visible():
                    # Get page "signature" before clicking
                    pre_click_text = page.inner_text("body")
                    
                    next_btn.click()
                    page.wait_for_load_state("networkidle")
                    time.sleep(1.2) # Essential for Qualtrics transitions
                    
                    # Check if the page actually changed
                    post_click_text = page.inner_text("body")
                    
                    # If the page didn't change (e.g., validation error because 
                    # there's another question on the same page), we don't count it as a failure.
                    # The loop will continue and try to find the next 'answer' on the same page.
                    pass 

        except Exception as e:
            final_error = str(e)
        finally:
            browser.close()
            
        return {
            "steps_completed": steps_completed,
            "last_clicked": last_clicked,
            "total_steps_in_path": len(persona_steps),
            "error": final_error
        }