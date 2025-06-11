import re

def extract_score(response: str) -> int:
    match = re.match(r"(\d)\.", str(response).strip())
    return int(match.group(1)) if match else None