from datetime import date
from decimal import Decimal
from datetime import date as DateType, datetime as DateTimeType, time as TimeType, timedelta as TimedeltaType
import json

def calculate_bmr(weight_kg, height_cm, age_years, gender_male):
    """
    Calculates Basal Metabolic Rate (BMR) using the Mifflin-St Jeor Equation.
    Assumes weight in kg and height in cm.
    """
    if gender_male:
        # BMR = (10 * weight in kg) + (6.25 * height in cm) - (5 * age) + 5
        return (10 * weight_kg) + (6.25 * height_cm) - (5 * age_years) + 5
    else:  # female
        # BMR = (10 * weight in kg) + (6.25 * height in cm) - (5 * age) - 161
        return (10 * weight_kg) + (6.25 * height_cm) - (5 * age_years) - 161

def calculate_age(dob):
    """Calculates age in years from a date of birth."""
    if not dob:
        return 0  # Return 0 or handle as appropriate if DOB is missing
    today = date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

def get_daily_calorie_budget(bmr, activity_level, current_weight, target_weight):
    """
    Calculates the recommended daily calorie budget based on BMR, activity, and goals.
    """
    activity_factors = {
        'sedentary': 1.2,
        'light': 1.375,
        'moderate': 1.55,
        'active': 1.725,
        'very_active': 1.9,
        # Adding the extra levels from your onboarding_questions.html
        'lightly_active': 1.375, 
        'moderately_active': 1.55,
        'super_active': 1.9
    }
    
    # Use .get() with a default value of 1.2 (sedentary)
    activity_multiplier = activity_factors.get(activity_level.lower() if activity_level else 'sedentary', 1.2)
    
    # Maintenance calories
    maintenance_calories = bmr * activity_multiplier

    daily_calorie_budget = maintenance_calories

    # Adjust budget based on weight goal
    if target_weight is not None and current_weight is not None:
        if current_weight < target_weight:
            daily_calorie_budget += 500  # Weight gain
        elif current_weight > target_weight:
            daily_calorie_budget -= 500  # Weight loss

    # Enforce a minimum calorie intake
    if daily_calorie_budget < 1200:
        daily_calorie_budget = 1200
        
    return round(daily_calorie_budget)


class CustomJSONEncoder(json.JSONEncoder):
    """
    Custom JSON encoder to handle complex types like Decimal, Date, Time, etc.
    """
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, DateType):
            return obj.strftime('%Y-%m-%d')
        if isinstance(obj, DateTimeType):
            return obj.isoformat()
        if isinstance(obj, TimeType):
            return obj.strftime('%H:%M:%S')
        if isinstance(obj, TimedeltaType):
            return str(obj) # or obj.total_seconds()
        
        # Let the base class default method raise the TypeError
        return json.JSONEncoder.default(self, obj)