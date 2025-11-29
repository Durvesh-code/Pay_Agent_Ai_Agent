import re

def mask_sensitive_data(text: str) -> str:
    """
    Masks sensitive data such as credit card numbers and potential account numbers.
    """
    # Mask Credit Card Numbers (13-19 digits)
    # This regex looks for sequences of digits that resemble CC numbers
    # It attempts to match groups of 4 digits separated by spaces or dashes
    cc_pattern = r'\b(?:\d[ -]*?){13,19}\b'
    
    def mask_cc(match):
        original = match.group()
        # Keep last 4 digits, mask the rest
        digits = re.sub(r'\D', '', original)
        if len(digits) < 13: # Avoid masking short numbers that might be dates or amounts
             return original
        masked = '*' * (len(digits) - 4) + digits[-4:]
        return masked

    text = re.sub(cc_pattern, mask_cc, text)

    # Mask IBANs (Generic basic check)
    iban_pattern = r'\b[A-Z]{2}\d{2}[A-Z0-9]{1,30}\b'
    text = re.sub(iban_pattern, lambda m: m.group()[:4] + '*' * (len(m.group()) - 8) + m.group()[-4:], text)

    return text
