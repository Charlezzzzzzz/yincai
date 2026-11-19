"""Display pseudonyms without changing student IDs or source cache hashes."""

def display_alias(value):
    if isinstance(value, str):
        return value.replace("小安", "小川")
    if isinstance(value, list):
        return [display_alias(item) for item in value]
    if isinstance(value, dict):
        return {key: display_alias(item) for key, item in value.items()}
    return value
