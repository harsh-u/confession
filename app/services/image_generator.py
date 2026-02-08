from PIL import Image, ImageDraw, ImageFont
import os
import random
import textwrap
from datetime import datetime
from app.config import settings


class ImageGenerator:
    """Service for generating aesthetic confession images"""
    
    def __init__(self):
        self.width = settings.image_width
        self.height = settings.image_height
        self.backgrounds_dir = "backgrounds"
        self.output_dir = "generated_images"
        
        # Ensure output directory exists
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Create backgrounds if they don't exist
        self._ensure_backgrounds()
    
    def _ensure_backgrounds(self):
        """Create aesthetic gradient backgrounds if they don't exist"""
        os.makedirs(self.backgrounds_dir, exist_ok=True)
        
        # Define gradient color schemes (start, end)
        gradients = [
            ((255, 182, 193), (255, 218, 224)),  # Pink to light pink
            ((179, 158, 181), (229, 204, 255)),  # Purple to lavender
            ((173, 216, 230), (224, 247, 250)),  # Light blue to sky blue
            ((255, 218, 185), (255, 239, 213)),  # Peach to cream
            ((221, 160, 221), (238, 213, 238)),  # Plum to thistle
            ((152, 251, 152), (224, 255, 224)),  # Pale green to mint
        ]
        
        for i, (start_color, end_color) in enumerate(gradients):
            bg_path = os.path.join(self.backgrounds_dir, f"gradient_{i}.png")
            if not os.path.exists(bg_path):
                self._create_gradient(start_color, end_color, bg_path)
    
    def _create_gradient(self, start_color: tuple, end_color: tuple, output_path: str):
        """Create a vertical gradient image"""
        image = Image.new('RGB', (self.width, self.height))
        draw = ImageDraw.Draw(image)
        
        for y in range(self.height):
            # Calculate color interpolation
            ratio = y / self.height
            r = int(start_color[0] + (end_color[0] - start_color[0]) * ratio)
            g = int(start_color[1] + (end_color[1] - start_color[1]) * ratio)
            b = int(start_color[2] + (end_color[2] - start_color[2]) * ratio)
            
            draw.line([(0, y), (self.width, y)], fill=(r, g, b))
        
        image.save(output_path)
    
    def _get_random_background(self) -> Image.Image:
        """Get a random background image"""
        backgrounds = [f for f in os.listdir(self.backgrounds_dir) if f.endswith('.png')]
        if not backgrounds:
            # Fallback to solid color
            return Image.new('RGB', (self.width, self.height), color=(240, 240, 245))
        
        bg_path = os.path.join(self.backgrounds_dir, random.choice(backgrounds))
        return Image.open(bg_path)
    
    def _get_font(self, size: int) -> ImageFont.FreeTypeFont:
        """Get font for text rendering"""
        # Try to use elegant fonts, fallback to default
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
            "/System/Library/Fonts/Supplemental/Georgia.ttf",
        ]
        
        for font_path in font_paths:
            if os.path.exists(font_path):
                try:
                    return ImageFont.truetype(font_path, size)
                except:
                    pass
        
        # Fallback to default font
        return ImageFont.load_default()
    
    def _calculate_font_size(self, text: str) -> int:
        """Calculate appropriate font size based on text length"""
        text_length = len(text)
        
        if text_length < 50:
            return 60
        elif text_length < 100:
            return 50
        elif text_length < 200:
            return 40
        elif text_length < 300:
            return 35
        else:
            return 30
    
    def _wrap_text(self, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
        """Wrap text to fit within max width"""
        # Estimate characters per line
        avg_char_width = font.getbbox('A')[2]
        chars_per_line = max(20, int(max_width / avg_char_width))
        
        # Wrap text
        lines = []
        for paragraph in text.split('\n'):
            wrapped = textwrap.wrap(paragraph, width=chars_per_line)
            lines.extend(wrapped if wrapped else [''])
        
        return lines
    
    def generate_image(self, text: str) -> str:
        """
        Generate confession image with text overlay
        
        Args:
            text: Confession text to render
            
        Returns:
            Path to generated image
        """
        # Get background
        image = self._get_random_background()
        draw = ImageDraw.Draw(image)
        
        # Calculate font size
        font_size = self._calculate_font_size(text)
        font = self._get_font(font_size)
        
        # Card dimensions (centered with padding)
        card_padding = 100
        card_width = self.width - (2 * card_padding)
        card_height = self.height - (2 * card_padding)
        
        # Wrap text
        lines = self._wrap_text(text, font, card_width - 80)
        
        # Calculate total text height
        line_height = font_size + 15
        total_text_height = len(lines) * line_height
        
        # Draw semi-transparent card background
        card_x1 = card_padding
        card_y1 = card_padding
        card_x2 = self.width - card_padding
        card_y2 = self.height - card_padding
        
        # Create overlay for card
        overlay = Image.new('RGBA', image.size, (255, 255, 255, 0))
        overlay_draw = ImageDraw.Draw(overlay)
        overlay_draw.rounded_rectangle(
            [card_x1, card_y1, card_x2, card_y2],
            radius=30,
            fill=(255, 255, 255, 200)
        )
        image = Image.alpha_composite(image.convert('RGBA'), overlay).convert('RGB')
        draw = ImageDraw.Draw(image)
        
        # Calculate starting Y position to center text vertically
        start_y = (self.height - total_text_height) // 2
        
        # Draw text lines
        current_y = start_y
        for line in lines:
            # Get text bounding box for centering
            bbox = draw.textbbox((0, 0), line, font=font)
            text_width = bbox[2] - bbox[0]
            
            # Center horizontally
            x = (self.width - text_width) // 2
            
            # Draw text with shadow for better readability
            shadow_offset = 2
            draw.text((x + shadow_offset, current_y + shadow_offset), line, 
                     font=font, fill=(200, 200, 200))
            draw.text((x, current_y), line, font=font, fill=(50, 50, 50))
            
            current_y += line_height
        
        # Generate unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"confession_{timestamp}.png"
        filepath = os.path.join(self.output_dir, filename)
        
        # Save image
        image.save(filepath, quality=95)
        
        return filepath


# Singleton instance
image_generator = ImageGenerator()
