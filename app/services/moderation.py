from better_profanity import profanity
from app.config import settings

# Initialize profanity filter
profanity.load_censor_words()


def moderate_content(text: str) -> tuple[bool, str]:
    """
    Moderate confession content for safety
    
    Args:
        text: The confession text to moderate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check length
    if len(text) > settings.max_confession_length:
        return False, f"Confession exceeds maximum length of {settings.max_confession_length} characters"
    
    if len(text.strip()) < 1:
        return False, "Confession cannot be empty"
    
    # Check for profanity
    if profanity.contains_profanity(text):
        return False, "Confession contains inappropriate language"
    
    # Check for spam (repeated characters)
    if _is_spam(text):
        return False, "Confession appears to be spam"
    
    return True, ""


def _is_spam(text: str) -> bool:
    """
    Detect potential spam patterns
    
    Args:
        text: Text to check
        
    Returns:
        True if text appears to be spam
    """
    # Check for excessive repeated characters
    max_repeated = 0
    current_char = None
    current_count = 0
    
    for char in text:
        if char == current_char:
            current_count += 1
            max_repeated = max(max_repeated, current_count)
        else:
            current_char = char
            current_count = 1
    
    # If more than 10 repeated characters, likely spam
    if max_repeated > 10:
        return True
    
    # Check for excessive capitalization
    if len(text) > 20:
        caps_ratio = sum(1 for c in text if c.isupper()) / len(text)
        if caps_ratio > 0.7:
            return True
    
    return False
