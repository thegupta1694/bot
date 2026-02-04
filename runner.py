from playwright.sync_api import sync_playwright
import time

def run_audit(survey_url, persona_steps):
    with sync_playwright() as p:
        # Launch with flags to ensure stability on Render/Linux
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"]) 
        context = browser.new_context(viewport={'width': 1280, 'height': 800})
        page = context.new_page()
        
        steps_completed = 0
        last_clicked = "None"
        final_error = None
        clicked_elements_registry = [] 

        try:
            # 1. Navigate and wait for the survey to actually load
            page.goto(survey_url, wait_until="networkidle", timeout=60000)
            time.sleep(2) # Give Qualtrics a moment to clear any loading spinners

            for answer in persona_steps:
                # 2. Check for end screen
                body_text = page.inner_text("body").lower()
                if any(x in body_text for x in ["thank you", "recorded", "unfortunately", "disqualified"]):
                    break 

                # 3. Advanced Selection Logic (Fuzzy & Case-Insensitive)
                found_click = False
                
                # We use Playwright's 'has-text' which is case-insensitive and ignores extra whitespace
                selectors = [
                    f"text='{answer}'", 
                    f"label:has-text('{answer}')",
                    f"span:has-text('{answer}')",
                    f"button:has-text('{answer}')",
                    f"div[role='radio']:has-text('{answer}')"
                ]

                for selector in selectors:
                    candidate = page.locator(selector).first
                    if candidate.is_visible():
                        # Scroll and click
                        candidate.scroll_into_view_if_needed()
                        candidate.click(force=True)
                        
                        last_clicked = answer
                        steps_completed += 1
                        found_click = True
                        time.sleep(1.0) # Wait for Qualtrics selection animation
                        break

                # 4. Intelligent "Next" Navigation
                # Added "Next page" and fuzzy "Next" to match your screenshot
                next_selectors = [
                    '#NextButton', 
                    '#next-button', 
                    'button:has-text("Next page")', 
                    'button:has-text("Next")',
                    '[aria-label="Next"]',
                    '.NextButton'
                ]
                
                next_btn = page.locator(", ".join(next_selectors)).first
                if next_btn.is_visible():
                    next_btn.click()
                    # Wait for the next question to appear
                    page.wait_for_load_state("networkidle")
                    time.sleep(2) # Essential for Qualtrics page-flip animations
                
                elif not found_click:
                    # If we can't find the answer AND can't find a Next button, we are stuck
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
