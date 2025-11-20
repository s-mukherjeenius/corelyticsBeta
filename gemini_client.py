import os
import re
import logging
import time
import google.generativeai as genai
from google.api_core import exceptions as google_api_core_exceptions

# --- Configuration ---
GEMINI_API_KEY = os.getenv('GOOGLE_API_KEY')
if not GEMINI_API_KEY:
    logging.critical("GOOGLE_API_KEY environment variable not set. AI features will fail.")

# Define an ordered list of models for fallbacks
PREFERRED_MODELS = [
    'gemini-2.5-flash',       # NEWEST & FASTEST (Confirmed available in your logs)
    'gemini-flash-latest',    # STABLE ALIAS (Confirmed available)
    'gemini-2.0-flash-exp',   # Backup (Currently hitting limits, so we move it to last)
]

# Global model variable, will be initialized dynamically
current_gemini_model = None

# --- Constants ---

# Personality prompt for the LOGIC chatbot
LOGIC_PERSONALITY_PROMPT = """
LOGIC's Persona: The Witty Wellness Wingman
Hey there, I'm LOGIC, your slightly-sarcastic-but-mostly-supportive AI sidekick here to help you conquer your health goals with the Corelytics app!

My Vibe: Think of me as that super-fit friend who might tease you a little for eyeing that third cookie, but will genuinely cheer you on when you hit your steps goal. I'm here to make understanding your health data less like deciphering ancient hieroglyphs and more like... well, still a bit of a challenge, but with more laughs!

What I'm Good At (and what I'm not):

Understanding Corelytics: Need to log that kale smoothie (or that regrettable late-night pizza)? Want to see if your calorie count is more "marathon runner" or "couch potato"? I can walk you through all the app's awesome features.
Nutrition Nuances: "Is bread evil?" "How much protein is enough?" I can dish out general info on healthy eating, help you brainstorm tasty recipes, and even demystify calorie counting. I'll help you figure out what to put in your body without making you feel like you're entering a monastic order.
Fitness Fun (or lack thereof): Let's talk about getting those muscles moving! I can guide you on general fitness principles, like why moving your body is a good idea (even if it feels like a bad one at 6 AM).
Your Personal Cheerleader (with a smirk): My goal is to motivate you to make healthier choices. I'll give you encouraging nudges and maybe a gentle, "Did you really just try to skip leg day again?"
Crucial Boundary Alert! (No, seriously, this is important): I'm an AI, not a human with a medical degree. So, if you're dealing with injuries, medical conditions, specific diet plans for diseases (like diabetes), or eating disorders, you absolutely, positively MUST talk to a doctor or registered dietitian. I'll politely (but firmly) tell you to seek professional help because your health is no joke. I'm here to help you track your progress, not diagnose your problems.
My Promise: I'll keep it concise, clear, and hopefully, entertaining. No blabbing, just the good stuff (with a sprinkle of sass).
"""

# Few-shot examples for calorie estimation
_CALORIE_PROMPT_TEMPLATE = (
    f"Food: {{meal_description}}\n"
    f"Meal Type: {{meal_type}}\n"
    f"Portion Size: {{portion_size}}\n"
    f"You are an expert nutritionist. Based on common nutritional data, provide ONLY the approximate numerical calorie value for this meal. "
    f"Make a reasonable estimation but make sure that it is closest to the actual calorie in a decimal format of x.x even if the description is slightly vague, assuming a common preparation method (e.g., for 'chicken', assume 'grilled chicken breast'). "
    f"Do not include units (like 'kcal' or 'calories'), explanations, or any other text. "
    f"Only respond with '0' for items that genuinely have zero calories, such as plain water."
)

_FEW_SHOT_PROMPT_TEXT = (
    "You are an expert nutritionist. Based on common nutritional data, provide ONLY the approximate numerical calorie value for this meal. "
    "Make a reasonable estimation even if the description is slightly vague, assuming a common preparation method (e.g., for 'chicken', assume 'grilled chicken breast'). "
    "Do not include units (like 'kcal' or 'calories'), explanations, or any other text. "
    "Only respond with '0' for items that genuinely have zero calories, such as plain water."
)

_FEW_SHOT_EXAMPLES = [
    {"role": "user", "parts": [{"text": f"Food: 1 medium apple\nMeal Type: Snack\nPortion Size: 1 medium\n{_FEW_SHOT_PROMPT_TEXT}"}]},
    {"role": "model", "parts": [{"text": "95"}]},
    {"role": "user", "parts": [{"text": f"Food: Spaghetti Bolognese\nMeal Type: Dinner\nPortion Size: 300g\n{_FEW_SHOT_PROMPT_TEXT}"}]},
    {"role": "model", "parts": [{"text": "450"}]},
    {"role": "user", "parts": [{"text": f"Food: water\nMeal Type: Drink\nPortion Size: 1 glass\n{_FEW_SHOT_PROMPT_TEXT}"}]},
    {"role": "model", "parts": [{"text": "0"}]}
]


# --- Initialization ---

def initialize_gemini_model():
    """
    Initializes the Gemini model, trying preferred models in order.
    Sets the global `current_gemini_model`.
    """
    global current_gemini_model
    if not GEMINI_API_KEY:
        logging.warning("Skipping Gemini model initialization: API key not set.")
        return False

    genai.configure(api_key=GEMINI_API_KEY)
    logging.info("--- Discovering available Gemini models for generateContent ---")
    
    try:
        available_models = [
            m for m in genai.list_models()
            if "generateContent" in m.supported_generation_methods
        ]
        available_models_names = [m.name for m in available_models]

        for preferred_name in PREFERRED_MODELS:
            found_model_name = next((
                name for name in available_models_names
                if preferred_name in name or f"{preferred_name}-latest" in name
            ), None)

            if found_model_name:
                current_gemini_model = genai.GenerativeModel(found_model_name)
                logging.info(f"Successfully configured Gemini model: {found_model_name}")
                return True
        
        if available_models:
            current_gemini_model = genai.GenerativeModel(available_models[0].name)
            logging.info(f"No preferred model found. Falling back to: {available_models[0].name}")
            return True

        logging.error("No Gemini models supporting 'generateContent' found.")
        return False

    except Exception as e:
        logging.error(f"ERROR: Failed to configure Gemini model: {e}")
        return False

# --- Core Generation Logic (Refactored) ---

def _generate_with_retry(contents, generation_config):
    """
    Internal function to handle Gemini API calls with model fallback and retries.
    Returns the raw response object or None on total failure.
    """
    global current_gemini_model
    
    if not current_gemini_model:
        logging.error("Gemini model is not initialized. Cannot generate content.")
        return None

    # Find the index of the currently configured model
    initial_model_name = current_gemini_model.model_name.split('/')[-1]
    start_model_index = 0
    for i, preferred_model in enumerate(PREFERRED_MODELS):
        if preferred_model in initial_model_name:
            start_model_index = i
            break
            
    max_model_switches = len(PREFERRED_MODELS)
    total_retries = 0

    # Loop through preferred models, trying each one a couple of times if needed
    for model_switch_attempt in range(max_model_switches):
        model_to_use_name = PREFERRED_MODELS[(start_model_index + model_switch_attempt) % len(PREFERRED_MODELS)]
        
        # Re-initialize the model object if we're switching
        if current_gemini_model is None or model_to_use_name not in current_gemini_model.model_name:
            try:
                current_gemini_model = genai.GenerativeModel(model_to_use_name)
                logging.info(f"Switched Gemini model to: {model_to_use_name}")
            except Exception as e:
                logging.error(f"Failed to switch to model {model_to_use_name}: {e}. Trying next model.")
                continue

        # Try the API call with the selected model (up to 3 times)
        for inner_retry_attempt in range(3):
            total_retries += 1
            try:
                logging.info(f"Attempting API call with model: {current_gemini_model.model_name} (Total Attempt {total_retries})")
                
                response = current_gemini_model.generate_content(
                    contents,
                    generation_config=generation_config
                )
                
                # Success!
                return response

            except (genai.types.BlockedPromptException, genai.types.StopCandidateException) as e:
                logging.warning(f"Gemini API blocked or stopped generation: {e}")
                return None # Don't retry if prompt is blocked
            except genai.types.BrokenResponseError as e:
                logging.error(f"Broken response from model {current_gemini_model.model_name}: {e}. Switching models.")
                break # Break inner loop to switch models
            except google_api_core_exceptions.ResourceExhausted as e:
                logging.warning(f"Quota exceeded for model {current_gemini_model.model_name}. Switching models. Error: {e}")
                break # Break inner loop to switch models
            except Exception as e:
                error_message = str(e).lower()
                if "not found" in error_message or "bad request" in error_message or "connection error" in error_message:
                    logging.error(f"Model error or connection issue for {current_gemini_model.model_name}: {e}. Switching models.")
                    break # Break inner loop to switch models
                else:
                    logging.error(f"An unexpected error occurred during Gemini API call: {e}")
                    return None # Don't retry for unknown errors

            # Wait before inner retry
            if inner_retry_attempt < 2:
                time.sleep(2 ** inner_retry_attempt)

    logging.error(f"Failed to generate content after multiple retries across all preferred models.")
    return None

def _extract_text_from_response(response):
    """Helper to safely extract text from a Gemini response object."""
    if not response:
        return ""
    try:
        if hasattr(response, 'text'):
            return response.text.strip()
        elif response.parts:
            for part in response.parts:
                if hasattr(part, 'text'):
                    return part.text.strip()
        return ""
    except Exception as e:
        logging.error(f"Error extracting text from Gemini response: {e}")
        return ""

# --- Public Functions ---

def estimate_calories_with_gemini(meal_description, meal_type, portion_size):
    """
    Estimates calorie value using the Gemini API.
    Returns a float (e.g., 95.0) or 0.0 on failure.
    """
    current_prompt = _CALORIE_PROMPT_TEMPLATE.format(
        meal_description=meal_description,
        meal_type=meal_type,
        portion_size=portion_size
    )
    
    contents = _FEW_SHOT_EXAMPLES + [{"role": "user", "parts": [{"text": current_prompt}]}]
    config = {"temperature": 0.2}

    response = _generate_with_retry(contents, config)
    estimated_calories_raw = _extract_text_from_response(response)

    if not estimated_calories_raw:
        logging.warning(f"Model returned empty calorie estimate for '{meal_description}'.")
        return 0.0

    numbers = re.findall(r'\d+\.?\d*', estimated_calories_raw)
    if numbers:
        estimated_calories = float(numbers[0])
        if estimated_calories < 0:
            logging.warning(f"Negative calories ({estimated_calories}) adjusted to 0 for '{meal_description}'.")
            return 0.0
        logging.info(f"Successfully estimated calories: {estimated_calories}")
        return estimated_calories
    else:
        logging.warning(f"Model returned non-numeric calorie estimate for '{meal_description}'. Raw: '{estimated_calories_raw}'.")
        return 0.0

def generate_meal_plan_with_gemini(user_profile_data):
    """
    Generates a meal plan using the Gemini API.
    Returns a string (the meal plan) or an error message string.
    """
    full_name = user_profile_data.get('full_name', 'User')
    age = user_profile_data.get('age_years')
    current_weight = user_profile_data.get('current_weight')
    height = user_profile_data.get('height')
    gender = user_profile_data.get('gender')
    activity_level = user_profile_data.get('activity_level')
    target_weight = user_profile_data.get('target_weight')
    daily_calorie_budget = user_profile_data.get('daily_calorie_budget')
    
    goal = "maintain general health and fitness"
    if target_weight is not None and current_weight is not None:
        if current_weight < target_weight:
            goal = "gain weight"
        elif current_weight > target_weight:
            goal = "lose weight"
        else:
            goal = "maintain weight"

    prompt = (
        f"You are an expert nutritionist and meal planner. Generate a balanced and varied 7-day meal plan for {full_name} "
        f"who is a {age}-year-old {gender} with a current weight of {current_weight} kg and height of {height} cm. "
        f"Their activity level is {activity_level}. Their goal is to {goal} with a daily calorie budget of approximately {daily_calorie_budget} calories. "
        f"Include Breakfast, Lunch, Dinner, and 1-2 snacks per day. "
        f"For each meal, provide a short description and an estimated calorie count. "
        f"Also, provide the total estimated calories for each day. "
        f"Structure the response clearly, using days (e.g., 'Day 1'), and then list meals (Breakfast, Lunch, etc.) with descriptions and calorie estimates. "
        f"At the end of each day's meals, state 'Daily Total: X calories'."
        f"Ensure variety over the 7 days. Do not include any introductory or concluding remarks, only the meal plan content itself. "
        f"Format the output using Markdown (e.g., use '### Day 1' for day headings and bullet points for meals)."
    )
    
    contents = [prompt]
    config = {"temperature": 0.7}

    response = _generate_with_retry(contents, config)
    meal_plan_text = _extract_text_from_response(response)

    if not meal_plan_text:
        logging.error(f"Failed to generate meal plan for {full_name} after all retries.")
        return "Failed to generate a meal plan. The AI service may be busy. Please try again later."
    
    logging.info(f"Meal plan generated successfully for {full_name}.")
    return meal_plan_text

def generate_chat_response(chat_history):
    """
    Generates a chat response using the Gemini API.
    Assumes chat_history includes the personality prompt.
    Returns a string (the response) or None on failure.
    """
    contents = chat_history
    config = {"temperature": 0.7} # Use default config or make specific

    response = _generate_with_retry(contents, config)
    bot_response = _extract_text_from_response(response)

    if not bot_response:
        logging.warning("Gemini returned an empty chat response.")
        return None
    
    return bot_response