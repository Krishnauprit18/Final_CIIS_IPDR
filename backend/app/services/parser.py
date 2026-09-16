
import pandas as pd
import re
from ipaddress import ip_address, AddressValueError

def is_private_ip(ip_str: str) -> bool:
    """Checks if a given string is a private IP address."""
    try:
        # The IP address might be read as a float from CSV, convert to string
        return ip_address(str(ip_str)).is_private
    except (ValueError, AddressValueError):
        return False

def parse_log_data(file_path: str, config: dict) -> pd.DataFrame:
    """
    Parses a log file. If it's a CSV, it reads it directly.
    Otherwise, it uses regex patterns defined in a config file.

    Args:
        file_path: The path to the log file.
        config: The parsed YAML configuration.

    Returns:
        A pandas DataFrame containing the extracted and filtered data.
    """
    filters = config.get('filters', [])
    df = pd.DataFrame()

    # --- Data Loading ---
    if file_path.lower().endswith('.csv'):
        try:
            df = pd.read_csv(file_path)
        except Exception as e:
            print(f"Error reading CSV file: {e}")
            return pd.DataFrame() # Return empty dataframe on error
    else:
        patterns = config.get('patterns', [])
        if not patterns:
            return pd.DataFrame()

        extracted_records = []
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                for pattern in patterns:
                    match = re.search(pattern, line)
                    if match:
                        extracted_records.append(match.groupdict())
                        break
        if extracted_records:
            df = pd.DataFrame(extracted_records)

    if df.empty:
        return pd.DataFrame()

    # --- Apply Filters ---
    for f in filters:
        col = f.get("column")
        filter_type = f.get("type")

        if not col or not filter_type or col not in df.columns:
            continue

        if filter_type == "private_ip":
            # Ensure column is string type before applying IP address functions
            df = df[~df[col].astype(str).apply(is_private_ip)]

    return df
