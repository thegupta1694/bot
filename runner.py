from playwright.sync_api import sync_playwright
import time

def run_audit(survey_url, persona_steps):
    """
    Automated Survey Auditor Runner
    Simulates a respondent based on a specific logical path.
    """
    with sync_playwright() as p:
        # Launch with specific flags to prevent memory crashes on hosted environments like Render
        browser = p.chromium.launch(
            headless=True, 
            args=["--disable-dev-shm-usage", "--no-sandbox"]
        ) 
        context = browser.new_context(viewport={'width': 1280, 'height': 800})
        page = context.new_page()
        
        steps_completed = 0
        last_clicked = "None"
        final_error = None
        clicked_elements_registry = [] 

        try:
            # Navigate to survey
            page.goto(survey_url, wait_until="networkidle", timeout=60000)
            
            for answer in persona_steps:
                # 1. Check for end screen (Terminate or Submit)
                body_text = page.inner_text("body").lower()
                if any(x in body_text for x in ["thank you", "recorded", "unfortunately", "disqualified", "completed"]):
                    break 

                # 2. Advanced Selection Logic
                # We use Playwright's 'text=' selector which is the most robust way 
                # to find labels regardless of the underlying HTML (div, span, p, etc.)
                found_click = False
                
                selectors = [
                    f"text='{answer}'",               # Exact text match
                    f"label:has-text('{answer}')",    # Standard label
                    f"button:has-text('{answer}')",   # Button-style option
                    f"span:has-text('{answer}')",     # Span inside a div
                    f"[aria-label*='{answer}']"       # Accessibility label
                ]

                for selector in selectors:
                    candidates = page.locator(selector)
                    count = candidates.count()
                    
                    for i in range(count):
                        candidate = candidates.nth(i)
                        
                        # Generate a unique ID based on text and position to avoid re-clicking
                        element_id = str(candidate.evaluate("node => node.innerText + node.getBoundingClientRect().top"))
                        
                        if candidate.is_visible() and element_id not in clicked_elements_registry:
                            candidate.scroll_into_view_if_needed()
                            candidate.click(force=True)
                            
                            clicked_elements_registry.append(element_id)
                            last_clicked = answer
                            steps_completed += 1
                            found_click = True
                            # Small pause for Qualtrics JS to register the radio selection
                            time.sleep(0.8) 
                            break
                    if found_click: break

                # 3. Intelligent Navigation
                # We look for various "Next" button patterns found in Qualtrics and other platforms
                next_selectors = [
                    '#NextButton', 
                    '#next-button', 
                    '[aria-label="Next"]', 
                    'button:has-text("Next page")', 
                    'button:has-text("Next")',
                    '.NextButton',
                    'input[value="Next"]'
                ]
                
                # Combine selectors into one query
                next_btn = page.locator(", ".join(next_selectors)).first
                
                if next_btn.is_visible():
                    next_btn.click()
                    # Wait for the next page to load
                    try:
                        page.wait_for_load_state("networkidle", timeout=5000)
                    except:
                        pass # Continue if networkidle takes too long
                    time.sleep(1.5) # Essential for Qualtrics UI transitions
                
                elif not found_click:
                    # If we didn't find the answer AND there's no Next button, we are truly stuck
                    break

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
