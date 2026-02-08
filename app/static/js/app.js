// DOM Elements
const form = document.getElementById('confessionForm');
const textarea = document.getElementById('confessionText');
const charCount = document.getElementById('charCount');
const submitBtn = document.getElementById('submitBtn');
const btnText = submitBtn.querySelector('.btn-text');
const btnLoader = submitBtn.querySelector('.btn-loader');
const errorMessage = document.getElementById('errorMessage');
const successMessage = document.getElementById('successMessage');

// Character counter
textarea.addEventListener('input', () => {
    const count = textarea.value.length;
    charCount.textContent = count;

    // Change color when approaching limit
    const maxLength = parseInt(textarea.getAttribute('maxlength'));
    if (count > maxLength * 0.9) {
        charCount.style.color = '#EF4444';
    } else if (count > maxLength * 0.7) {
        charCount.style.color = '#F59E0B';
    } else {
        charCount.style.color = '#8B5CF6';
    }
});

// Form submission
form.addEventListener('submit', async (e) => {
    e.preventDefault();

    // Clear previous messages
    hideMessages();

    // Validate
    const text = textarea.value.trim();
    if (!text) {
        showError('Please enter your confession');
        return;
    }

    // Show loading state
    setLoading(true);

    try {
        const response = await fetch('/api/submit', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ text }),
        });

        const data = await response.json();

        if (response.ok) {
            // Success
            showSuccess(data.message || 'Confession posted successfully!');

            // Clear form
            textarea.value = '';
            charCount.textContent = '0';

            // Redirect to success page after delay
            setTimeout(() => {
                window.location.href = '/success';
            }, 1500);
        } else {
            // Error from server
            showError(data.detail || 'Failed to post confession. Please try again.');
        }
    } catch (error) {
        console.error('Error:', error);
        showError('Network error. Please check your connection and try again.');
    } finally {
        setLoading(false);
    }
});

// Helper functions
function setLoading(loading) {
    if (loading) {
        submitBtn.disabled = true;
        btnText.style.display = 'none';
        btnLoader.style.display = 'inline-block';
    } else {
        submitBtn.disabled = false;
        btnText.style.display = 'inline';
        btnLoader.style.display = 'none';
    }
}

function showError(message) {
    errorMessage.textContent = message;
    errorMessage.style.display = 'block';

    // Auto-hide after 5 seconds
    setTimeout(() => {
        errorMessage.style.display = 'none';
    }, 5000);
}

function showSuccess(message) {
    successMessage.textContent = message;
    successMessage.style.display = 'block';
}

function hideMessages() {
    errorMessage.style.display = 'none';
    successMessage.style.display = 'none';
}

// Auto-resize textarea
textarea.addEventListener('input', function () {
    this.style.height = 'auto';
    this.style.height = Math.max(200, this.scrollHeight) + 'px';
});
