import pytest
from app.services.moderation import moderate_content


def test_valid_confession():
    """Test that valid confessions pass moderation"""
    text = "This is a perfectly normal confession."
    is_valid, error = moderate_content(text)
    assert is_valid is True
    assert error == ""


def test_empty_confession():
    """Test that empty confessions are rejected"""
    text = "   "
    is_valid, error = moderate_content(text)
    assert is_valid is False
    assert "empty" in error.lower()


def test_too_long_confession():
    """Test that overly long confessions are rejected"""
    text = "x" * 600
    is_valid, error = moderate_content(text)
    assert is_valid is False
    assert "maximum length" in error.lower()


def test_spam_detection_repeated_chars():
    """Test spam detection for repeated characters"""
    text = "aaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    is_valid, error = moderate_content(text)
    assert is_valid is False
    assert "spam" in error.lower()


def test_spam_detection_excessive_caps():
    """Test spam detection for excessive capitalization"""
    text = "THIS IS ALL CAPS AND SHOULD BE DETECTED AS SPAM!!!"
    is_valid, error = moderate_content(text)
    assert is_valid is False
    assert "spam" in error.lower()


def test_normal_caps_allowed():
    """Test that normal capitalization is allowed"""
    text = "I really LOVE this app!"
    is_valid, error = moderate_content(text)
    assert is_valid is True
