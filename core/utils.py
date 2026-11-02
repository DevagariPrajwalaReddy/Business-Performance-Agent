def clean_output(text):
    markers = ["Final Answer:", "Final Response:"]
    for marker in markers:
        if marker in text:
            return text.split(marker)[-1].strip()
    return text.strip()