"""
SM-2 Spaced Repetition Algorithm Implementation
Based on SuperMemo 2 algorithm by Piotr Wozniak (1987)
Used by popular learning apps like Anki
"""

from datetime import datetime, timedelta
import math


def get_initial_state():
    """
    Returns initial state for a new flashcard.
    
    Returns:
        dict: Initial flashcard state with default SM-2 values
    """
    return {
        'easiness_factor': 2.5,
        'repetition_count': 0,
        'interval_days': 1,
        'next_review_date': datetime.now().date()
    }


def calculate_next_review(quality, easiness_factor, repetition_count, interval_days):
    """
    Calculate next review parameters based on SM-2 algorithm.
    
    Args:
        quality (int): User's quality rating (0-5 scale)
            5 = Perfect response
            4 = Correct after hesitation
            3 = Correct with difficulty
            2 = Incorrect but familiar
            1 = Incorrect, hard to recall
            0 = Complete blackout
        easiness_factor (float): Current easiness factor (minimum 1.3)
        repetition_count (int): Number of consecutive successful reviews
        interval_days (int): Current interval in days
    
    Returns:
        dict: Updated state with new EF, repetition count, interval, and next review date
    """
    
    # Validate quality rating
    quality = max(0, min(5, quality))
    
    # Calculate new easiness factor
    # Formula: EF' = EF + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
    new_ef = easiness_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    
    # Easiness factor should never fall below 1.3
    new_ef = max(1.3, new_ef)
    
    # Determine new interval based on quality
    if quality < 3:
        # Failed recall - reset progress
        new_repetition_count = 0
        new_interval = 1
    else:
        # Successful recall
        new_repetition_count = repetition_count + 1
        
        if new_repetition_count == 1:
            # First successful review
            new_interval = 1
        elif new_repetition_count == 2:
            # Second successful review
            new_interval = 6
        else:
            # Subsequent reviews: multiply previous interval by EF
            new_interval = math.ceil(interval_days * new_ef)
    
    # Calculate next review date
    next_review_date = datetime.now().date() + timedelta(days=new_interval)
    
    return {
        'easiness_factor': round(new_ef, 2),
        'repetition_count': new_repetition_count,
        'interval_days': new_interval,
        'next_review_date': next_review_date
    }


def quality_to_label(quality):
    """
    Convert numeric quality rating to human-readable label.
    
    Args:
        quality (int): Quality rating (0-5)
    
    Returns:
        str: Label for the quality rating
    """
    labels = {
        0: "Again (Blackout)",
        1: "Again (Hard)",
        2: "Hard",
        3: "Good",
        4: "Good",
        5: "Easy"
    }
    return labels.get(quality, "Unknown")


def simplified_quality_map(button):
    """
    Map simplified 4-button interface to SM-2 quality scale.
    
    Args:
        button (str): Button name ("again", "hard", "good", "easy")
    
    Returns:
        int: Quality rating (0-5)
    """
    mapping = {
        "again": 0,   # Complete failure
        "hard": 2,    # Difficult but correct
        "good": 3,    # Correct response
        "easy": 5     # Perfect response
    }
    return mapping.get(button.lower(), 3)
