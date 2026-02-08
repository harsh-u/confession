import pytest
from app.services.image_generator import ImageGenerator
import os


def test_image_generator_initialization():
    """Test that image generator initializes correctly"""
    generator = ImageGenerator()
    assert generator.width == 1080
    assert generator.height == 1080
    assert os.path.exists(generator.backgrounds_dir)
    assert os.path.exists(generator.output_dir)


def test_gradient_creation():
    """Test that gradient backgrounds are created"""
    generator = ImageGenerator()
    backgrounds = os.listdir(generator.backgrounds_dir)
    assert len(backgrounds) >= 6
    assert all(bg.endswith('.png') for bg in backgrounds)


def test_image_generation_short_text():
    """Test image generation with short text"""
    generator = ImageGenerator()
    text = "This is a short confession."
    image_path = generator.generate_image(text)
    
    assert os.path.exists(image_path)
    assert image_path.endswith('.png')
    
    # Cleanup
    os.remove(image_path)


def test_image_generation_long_text():
    """Test image generation with long text"""
    generator = ImageGenerator()
    text = "This is a much longer confession that should test the text wrapping functionality. " * 5
    image_path = generator.generate_image(text)
    
    assert os.path.exists(image_path)
    
    # Cleanup
    os.remove(image_path)


def test_font_size_calculation():
    """Test font size calculation based on text length"""
    generator = ImageGenerator()
    
    short_text = "Short"
    long_text = "x" * 400
    
    short_size = generator._calculate_font_size(short_text)
    long_size = generator._calculate_font_size(long_text)
    
    assert short_size > long_size
