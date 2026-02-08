import random

# Caption templates
CAPTION_TEMPLATES = [
    "Anonymous confession 💭",
    "Someone needed to say this...",
    "Confession time 🤫",
    "Speaking the truth anonymously 💬",
    "An honest confession 🌙",
    "Sometimes you just need to confess ✨",
    "Anonymous thoughts, real feelings 💫",
    "Confession of the day 🌟",
]

# Hashtags
HASHTAGS = [
    "#confession",
    "#anonymous",
    "#beyourself",
    "#confessions",
    "#truth",
    "#honesty",
    "#realfeelings",
    "#confessiontime",
    "#anonymousconfession",
]


def generate_caption() -> str:
    """
    Generate a random Instagram caption with hashtags
    
    Returns:
        Complete caption string with hashtags
    """
    # Select random template
    caption = random.choice(CAPTION_TEMPLATES)
    
    # Add hashtags
    hashtag_string = " ".join(HASHTAGS)
    
    return f"{caption}\n\n{hashtag_string}"
