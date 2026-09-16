import pandas as pd
import json
import xml.etree.ElementTree as ET
import re
import csv
from typing import Dict, List, Tuple, Optional, Any, Union
from datetime import datetime
import os
from pathlib import Path
import chardet
from io import StringIO
import yaml

class DataNormalizer:
    """
    Comprehensive data normalization system for diverse IPDR formats from various telecom providers.
    Normalizes all formats to the synthetic.csv standard structure.
    """
    
    # Standard schema based on synthetic.csv
    STANDARD_SCHEMA = {
        'Protocol': str,
        'Source IP': str,
        'Source Port': int,
        'Destination IP': str,
        'Destination Port': int,
        'Start Time': str,
        'End Time': str,
        'Duration': int,
        'NAT IP': str,
        'NAT Port': int,
        'Device': str,
        'UserID': str,
        'SubscriberID': str,
        'CustName': str,
        'Address': str,
        'Email': str,
        'Phone': str,
        'Alt-Phone': str,
        'CustID': str,
        'IP Type': str,
        'Latitude': float,
        'Longitude': float,
        # B-Party extensions (optional, passthrough if present)
        'B-Phone': str,
        'B-SubscriberID': str,
        'B-CustName': str,
    }
    
    def __init__(self):
        self.supported_formats = ['csv', 'txt', 'json', 'xml', 'tsv', 'log', 'yaml']
        self.normalization_stats = {
            'total_files_processed': 0,
            'successful_normalizations': 0,
            'failed_normalizations': 0,
            'format_counts': {},
            'provider_counts': {},
            'total_records_processed': 0
        }
        
        # Telecom provider-specific field mappings
        self.provider_mappings = self._initialize_provider_mappings()
        
        # Common field aliases for different providers
        self.field_aliases = self._initialize_field_aliases()
    
    def normalize_file(self, file_path: str, provider: str = 'auto', custom_mapping: Dict = None, chunksize: Optional[int] = None) -> pd.DataFrame:
        """
        Main normalization function that handles any supported file format
        """
        try:
            # Detect file format
            file_format = self._detect_file_format(file_path)
            
            # Detect encoding
            encoding = self._detect_encoding(file_path)

            # For CSV with chunksize, stream-parse to handle large files
            if file_format == 'csv' and chunksize and chunksize > 0:
                combined_chunks = []
                first_chunk = True
                detected_provider = provider
                for chunk in pd.read_csv(file_path, delimiter=',', encoding=encoding, low_memory=False, chunksize=chunksize):
                    # Determine provider on first chunk if auto
                    prov = detected_provider
                    if detected_provider == 'auto' and first_chunk:
                        prov = self._auto_detect_provider(chunk, file_path)
                    elif detected_provider == 'auto':
                        prov = prov  # keep previously detected

                    # Apply mapping and normalization on each chunk
                    mapped = self._apply_provider_mapping(chunk, prov, custom_mapping)
                    normalized = self._normalize_to_standard_schema(mapped)
                    cleaned = self._validate_and_clean_data(normalized)
                    combined_chunks.append(cleaned)
                    if first_chunk:
                        detected_provider = prov
                        first_chunk = False
                if combined_chunks:
                    result_df = pd.concat(combined_chunks, ignore_index=True)
                else:
                    result_df = pd.DataFrame(columns=list(self.STANDARD_SCHEMA.keys()))

                # Update statistics
                self._update_stats(file_format, detected_provider, len(result_df))
                return result_df

            # Default path: parse whole file
            raw_data = self._parse_file(file_path, file_format, encoding)

            # Auto-detect provider if not specified
            if provider == 'auto':
                provider = self._auto_detect_provider(raw_data, file_path)

            # Apply provider-specific mapping
            mapped_data = self._apply_provider_mapping(raw_data, provider, custom_mapping)

            # Normalize to standard schema
            normalized_data = self._normalize_to_standard_schema(mapped_data)

            # Validate and clean data
            cleaned_data = self._validate_and_clean_data(normalized_data)

            # Update statistics
            self._update_stats(file_format, provider, len(cleaned_data))

            return cleaned_data
            
        except Exception as e:
            self.normalization_stats['failed_normalizations'] += 1
            raise Exception(f"Failed to normalize file {file_path}: {str(e)}")
    
    def normalize_multiple_files(self, file_paths: List[str], provider: str = 'auto') -> pd.DataFrame:
        """
        Normalize and combine multiple files from potentially different providers
        """
        all_normalized_data = []
        
        for file_path in file_paths:
            try:
                normalized_df = self.normalize_file(file_path, provider)
                all_normalized_data.append(normalized_df)
            except Exception as e:
                print(f"Warning: Could not normalize {file_path}: {str(e)}")
                continue
        
        if all_normalized_data:
            combined_df = pd.concat(all_normalized_data, ignore_index=True)
            return combined_df
        else:
            return pd.DataFrame(columns=list(self.STANDARD_SCHEMA.keys()))
    
    def _detect_file_format(self, file_path: str) -> str:
        """Detect file format based on extension and content analysis"""
        file_ext = Path(file_path).suffix.lower().lstrip('.')
        
        if file_ext in self.supported_formats:
            return file_ext
        
        # Content-based detection for files without clear extensions
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                first_lines = [f.readline().strip() for _ in range(5)]
                content_sample = '\n'.join(first_lines)
            
            if content_sample.startswith('{') or content_sample.startswith('['):
                return 'json'
            elif content_sample.startswith('<'):
                return 'xml'
            elif ',' in content_sample and content_sample.count(',') > content_sample.count('\t'):
                return 'csv'
            elif '\t' in content_sample:
                return 'tsv'
            else:
                return 'txt'
                
        except Exception:
            return 'txt'  # Default fallback
    
    def _detect_encoding(self, file_path: str) -> str:
        """Detect file encoding"""
        try:
            with open(file_path, 'rb') as f:
                raw_data = f.read()
                encoding_result = chardet.detect(raw_data)
                return encoding_result['encoding'] or 'utf-8'
        except Exception:
            return 'utf-8'
    
    def _parse_file(self, file_path: str, file_format: str, encoding: str) -> pd.DataFrame:
        """Parse file based on detected format"""
        
        if file_format == 'csv':
            return self._parse_csv(file_path, encoding)
        elif file_format == 'tsv':
            return self._parse_tsv(file_path, encoding)
        elif file_format == 'json':
            return self._parse_json(file_path, encoding)
        elif file_format == 'xml':
            return self._parse_xml(file_path, encoding)
        elif file_format == 'yaml':
            return self._parse_yaml(file_path, encoding)
        elif file_format in ['txt', 'log']:
            return self._parse_text_log(file_path, encoding)
        else:
            raise ValueError(f"Unsupported file format: {file_format}")
    
    def _parse_csv(self, file_path: str, encoding: str) -> pd.DataFrame:
        """Parse CSV files with various delimiters and structures"""
        # Try different delimiters
        delimiters = [',', ';', '|', '\t']
        
        for delimiter in delimiters:
            try:
                df = pd.read_csv(file_path, delimiter=delimiter, encoding=encoding, low_memory=False)
                if len(df.columns) > 1:  # Valid CSV should have multiple columns
                    return df
            except Exception:
                continue
        
        # Fallback: try to auto-detect delimiter
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                sample = f.read(1024)
                sniffer = csv.Sniffer()
                delimiter = sniffer.sniff(sample).delimiter
                df = pd.read_csv(file_path, delimiter=delimiter, encoding=encoding, low_memory=False)
                return df
        except Exception:
            # Last resort: read as single column and try to split
            df = pd.read_csv(file_path, encoding=encoding, header=None, low_memory=False)
            return df
    
    def _parse_tsv(self, file_path: str, encoding: str) -> pd.DataFrame:
        """Parse Tab-separated values files"""
        return pd.read_csv(file_path, delimiter='\t', encoding=encoding, low_memory=False)
    
    def _parse_json(self, file_path: str, encoding: str) -> pd.DataFrame:
        """Parse JSON files (both array of objects and line-delimited JSON)"""
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                data = json.load(f)
            
            if isinstance(data, list):
                return pd.DataFrame(data)
            elif isinstance(data, dict):
                if 'records' in data:
                    return pd.DataFrame(data['records'])
                elif 'data' in data:
                    return pd.DataFrame(data['data'])
                else:
                    return pd.DataFrame([data])
        except json.JSONDecodeError:
            # Try line-delimited JSON (NDJSON)
            records = []
            with open(file_path, 'r', encoding=encoding) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            records.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
            return pd.DataFrame(records)
    
    def _parse_xml(self, file_path: str, encoding: str) -> pd.DataFrame:
        """Parse XML files"""
        tree = ET.parse(file_path)
        root = tree.getroot()
        
        records = []
        
        # Try to find record elements (common patterns)
        record_tags = ['record', 'entry', 'item', 'row', 'session', 'call', 'connection']
        
        for record_tag in record_tags:
            elements = root.findall(f".//{record_tag}")
            if elements:
                for element in elements:
                    record = {}
                    for child in element:
                        record[child.tag] = child.text or ''
                    if record:
                        records.append(record)
                break
        
        # If no standard record structure found, try to flatten the XML
        if not records and len(root) > 0:
            for child in root:
                record = {}
                if child.text and child.text.strip():
                    record[child.tag] = child.text.strip()
                for subchild in child:
                    record[f"{child.tag}_{subchild.tag}"] = subchild.text or ''
                if record:
                    records.append(record)
        
        return pd.DataFrame(records)
    
    def _parse_yaml(self, file_path: str, encoding: str) -> pd.DataFrame:
        """Parse YAML files"""
        with open(file_path, 'r', encoding=encoding) as f:
            data = yaml.safe_load(f)
        
        if isinstance(data, list):
            return pd.DataFrame(data)
        elif isinstance(data, dict):
            if 'records' in data:
                return pd.DataFrame(data['records'])
            elif 'data' in data:
                return pd.DataFrame(data['data'])
            else:
                return pd.DataFrame([data])
        else:
            return pd.DataFrame()
    
    def _parse_text_log(self, file_path: str, encoding: str) -> pd.DataFrame:
        """Parse text/log files using regex patterns"""
        records = []
        
        # Common log patterns
        patterns = [
            # Standard IPDR-like pattern
            r'(?P<timestamp>\d{4}-\d{2}-\d{2}[\s\-T]\d{2}:\d{2}:\d{2}).*?(?P<source_ip>\d+\.\d+\.\d+\.\d+):(?P<source_port>\d+).*?(?P<dest_ip>\d+\.\d+\.\d+\.\d+):(?P<dest_port>\d+).*?(?P<protocol>\w+)',
            
            # Pipe-separated pattern
            r'(?P<timestamp>[^|]+)\|(?P<source_ip>[^|]+)\|(?P<source_port>[^|]+)\|(?P<dest_ip>[^|]+)\|(?P<dest_port>[^|]+)\|(?P<protocol>[^|]+)',
            
            # Space-separated pattern
            r'(?P<timestamp>\S+\s+\S+)\s+(?P<source_ip>\d+\.\d+\.\d+\.\d+)\s+(?P<source_port>\d+)\s+(?P<dest_ip>\d+\.\d+\.\d+\.\d+)\s+(?P<dest_port>\d+)\s+(?P<protocol>\w+)',
            
            # Key-value pattern
            r'src=(?P<source_ip>[^\s]+)\s+.*?dst=(?P<dest_ip>[^\s]+)\s+.*?sport=(?P<source_port>\d+)\s+.*?dport=(?P<dest_port>\d+)\s+.*?proto=(?P<protocol>\w+)',
        ]
        
        with open(file_path, 'r', encoding=encoding) as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                for pattern in patterns:
                    match = re.search(pattern, line, re.IGNORECASE)
                    if match:
                        record = match.groupdict()
                        record['line_number'] = line_num
                        records.append(record)
                        break
        
        return pd.DataFrame(records)
    
    def _auto_detect_provider(self, data: pd.DataFrame, file_path: str) -> str:
        """Auto-detect telecom provider based on data patterns and filename"""
        if data.empty:
            return 'generic'
        
        filename = Path(file_path).name.lower()
        
        # Check filename patterns
        provider_patterns = {
            'airtel': ['airtel', 'bharti'],
            'jio': ['jio', 'reliance'],
            'vodafone': ['vodafone', 'idea', 'vi'],
            'bsnl': ['bsnl', 'bharat'],
            'cisco': ['cisco', 'asr', 'nexus'],
            'huawei': ['huawei', 'ne40', 'ne80'],
            'ericsson': ['ericsson', 'sgsn', 'ggsn'],
            'nokia': ['nokia', 'siemens']
        }
        
        for provider, patterns in provider_patterns.items():
            if any(pattern in filename for pattern in patterns):
                return provider
        
        # Check column patterns
        columns = [col.lower() for col in data.columns]
        
        if 'msisdn' in columns or 'imsi' in columns:
            return 'telecom_standard'
        elif 'calling_number' in columns or 'called_number' in columns:
            return 'legacy_telecom'
        elif 'src_ip' in columns and 'dst_ip' in columns:
            return 'network_equipment'
        else:
            return 'generic'
    
    def _apply_provider_mapping(self, data: pd.DataFrame, provider: str, custom_mapping: Dict = None) -> pd.DataFrame:
        """Apply provider-specific field mappings"""
        if data.empty:
            return data
        
        # Use custom mapping if provided
        if custom_mapping:
            mapping = custom_mapping
        else:
            mapping = self.provider_mappings.get(provider, {})
        
        # Apply field mappings
        mapped_data = data.copy()
        
        # Rename columns based on mapping
        for standard_field, provider_fields in mapping.items():
            if isinstance(provider_fields, str):
                provider_fields = [provider_fields]
            
            for provider_field in provider_fields:
                if provider_field in mapped_data.columns:
                    mapped_data = mapped_data.rename(columns={provider_field: standard_field})
                    break
        
        # Apply field aliases
        for alias, standard_field in self.field_aliases.items():
            if alias in mapped_data.columns and standard_field not in mapped_data.columns:
                mapped_data = mapped_data.rename(columns={alias: standard_field})
        
        return mapped_data
    
    def _normalize_to_standard_schema(self, data: pd.DataFrame) -> pd.DataFrame:
        """Normalize data to standard schema"""
        if data.empty:
            return pd.DataFrame(columns=list(self.STANDARD_SCHEMA.keys()))
        
        normalized_data = pd.DataFrame()
        
        for standard_field, field_type in self.STANDARD_SCHEMA.items():
            if standard_field in data.columns:
                normalized_data[standard_field] = data[standard_field]
            else:
                # Generate default values based on field type
                default_value = self._get_default_value(standard_field, field_type)
                normalized_data[standard_field] = [default_value] * len(data)
        
        return normalized_data
    
    def _validate_and_clean_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """Validate and clean the normalized data"""
        if data.empty:
            return data
        
        cleaned_data = data.copy()
        
        # Clean and validate specific fields
        cleaned_data = self._clean_ip_addresses(cleaned_data)
        cleaned_data = self._clean_ports(cleaned_data)
        cleaned_data = self._clean_timestamps(cleaned_data)
        cleaned_data = self._clean_phone_numbers(cleaned_data)
        cleaned_data = self._clean_geographic_data(cleaned_data)
        
        # Remove completely empty rows
        cleaned_data = cleaned_data.dropna(how='all')
        
        # Apply data type conversions
        cleaned_data = self._apply_data_types(cleaned_data)
        
        return cleaned_data
    
    def _clean_ip_addresses(self, data: pd.DataFrame) -> pd.DataFrame:
        """Clean and validate IP addresses"""
        ip_fields = ['Source IP', 'Destination IP', 'NAT IP']
        
        for field in ip_fields:
            if field in data.columns:
                # Remove invalid IP addresses
                data[field] = data[field].apply(self._validate_ip_address)
        
        return data
    
    def _clean_ports(self, data: pd.DataFrame) -> pd.DataFrame:
        """Clean and validate port numbers"""
        port_fields = ['Source Port', 'Destination Port', 'NAT Port']
        
        for field in port_fields:
            if field in data.columns:
                # Convert to numeric and validate range
                data[field] = pd.to_numeric(data[field], errors='coerce')
                data[field] = data[field].apply(lambda x: int(x) if pd.notna(x) and 0 <= x <= 65535 else 0)
        
        return data
    
    def _clean_timestamps(self, data: pd.DataFrame) -> pd.DataFrame:
        """Clean and standardize timestamp formats"""
        time_fields = ['Start Time', 'End Time']
        
        for field in time_fields:
            if field in data.columns:
                data[field] = data[field].apply(self._standardize_timestamp)
        
        return data
    
    def _clean_phone_numbers(self, data: pd.DataFrame) -> pd.DataFrame:
        """Clean and standardize phone numbers"""
        phone_fields = ['Phone', 'Alt-Phone', 'B-Phone']

        for field in phone_fields:
            if field in data.columns:
                if field == 'B-Phone':
                    data[field] = data[field].apply(self._standardize_phone_number_optional)
                else:
                    data[field] = data[field].apply(self._standardize_phone_number)

        return data
    
    def _clean_geographic_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """Clean and validate geographic coordinates"""
        if 'Latitude' in data.columns:
            data['Latitude'] = pd.to_numeric(data['Latitude'], errors='coerce')
            data['Latitude'] = data['Latitude'].apply(lambda x: x if pd.notna(x) and -90 <= x <= 90 else 0.0)
        
        if 'Longitude' in data.columns:
            data['Longitude'] = pd.to_numeric(data['Longitude'], errors='coerce')
            data['Longitude'] = data['Longitude'].apply(lambda x: x if pd.notna(x) and -180 <= x <= 180 else 0.0)
        
        return data
    
    def _apply_data_types(self, data: pd.DataFrame) -> pd.DataFrame:
        """Apply correct data types to all columns"""
        for field, field_type in self.STANDARD_SCHEMA.items():
            if field in data.columns:
                try:
                    if field_type == int:
                        data[field] = pd.to_numeric(data[field], errors='coerce').fillna(0).astype(int)
                    elif field_type == float:
                        data[field] = pd.to_numeric(data[field], errors='coerce').fillna(0.0)
                    elif field_type == str:
                        data[field] = data[field].astype(str).fillna('')
                except Exception:
                    # If conversion fails, use default values
                    default_value = self._get_default_value(field, field_type)
                    data[field] = [default_value] * len(data)
        
        return data
    
    def _validate_ip_address(self, ip_str: str) -> str:
        """Validate IP address format"""
        if pd.isna(ip_str):
            return '0.0.0.0'
        
        ip_str = str(ip_str).strip()
        # Simple IP validation
        pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
        if re.match(pattern, ip_str):
            parts = ip_str.split('.')
            if all(0 <= int(part) <= 255 for part in parts):
                return ip_str
        
        return '0.0.0.0'
    
    def _standardize_timestamp(self, timestamp_str: str) -> str:
        """Standardize timestamp to YYYY-MM-DD-HH:MM:SS format"""
        if pd.isna(timestamp_str):
            return '2025-01-01-00:00:00'
        
        timestamp_str = str(timestamp_str).strip()
        
        # Common timestamp patterns
        patterns = [
            '%Y-%m-%d-%H:%M:%S',
            '%Y-%m-%d %H:%M:%S',
            '%Y/%m/%d %H:%M:%S',
            '%d/%m/%Y %H:%M:%S',
            '%Y-%m-%dT%H:%M:%S',
            '%Y%m%d%H%M%S'
        ]
        
        for pattern in patterns:
            try:
                dt = datetime.strptime(timestamp_str, pattern)
                return dt.strftime('%Y-%m-%d-%H:%M:%S')
            except ValueError:
                continue
        
        return '2025-01-01-00:00:00'
    
    def _standardize_phone_number(self, phone_str: str) -> str:
        """Standardize phone number format"""
        if pd.isna(phone_str):
            return '+910000000000'
        
        phone_str = str(phone_str).strip()
        # Remove all non-digit characters except +
        phone_str = re.sub(r'[^\d+]', '', phone_str)
        
        # Ensure it starts with + and has reasonable length
        if not phone_str.startswith('+'):
            if phone_str.startswith('91') and len(phone_str) == 12:
                phone_str = '+' + phone_str
            elif len(phone_str) == 10:
                phone_str = '+91' + phone_str
            else:
                return '+910000000000'
        
        if 10 <= len(phone_str) - 1 <= 15:  # Subtract 1 for the + sign
            return phone_str

        return '+910000000000'

    def _standardize_phone_number_optional(self, phone_str: str) -> str:
        """Standardize phone number but allow blanks for missing/invalid values (used for B-Phone)."""
        if pd.isna(phone_str):
            return ''
        s = str(phone_str).strip()
        if not s or s.lower() in ('na', 'n/a', 'none', 'null', '0'):
            return ''
        # Remove all non-digits except +
        s = re.sub(r'[^\d+]', '', s)
        # Build to +E.164 if possible, else blank
        if not s.startswith('+'):
            if s.startswith('91') and len(s) == 12:
                s = '+' + s
            elif len(s) == 10:
                s = '+91' + s
            elif len(s) == 11 and s.startswith('0'):
                s = '+91' + s[1:]
            else:
                return ''
        # Validate length (10-15 digits excluding '+')
        if 10 <= len(s) - 1 <= 15:
            return s
        return ''
    
    def _get_default_value(self, field_name: str, field_type: type) -> Union[str, int, float]:
        """Get appropriate default value for missing fields"""
        defaults = {
            'Protocol': 'TCP',
            'Source IP': '0.0.0.0',
            'Destination IP': '0.0.0.0',
            'NAT IP': '0.0.0.0',
            'Start Time': '2025-01-01-00:00:00',
            'End Time': '2025-01-01-00:00:00',
            'Device': 'UNKNOWN',
            'UserID': 'unknown',
            'SubscriberID': 'SUB000000',
            'CustName': 'Unknown User',
            'Address': 'Unknown Location',
            'Email': 'unknown@example.com',
            'Phone': '+910000000000',
            'Alt-Phone': '+910000000000',
            'CustID': 'CUST000000',
            'IP Type': 'dynamic'
        }
        
        if field_name in defaults:
            return defaults[field_name]
        elif field_type == int:
            return 0
        elif field_type == float:
            return 0.0
        else:
            return ''
    
    def _initialize_provider_mappings(self) -> Dict[str, Dict[str, List[str]]]:
        """Initialize provider-specific field mappings"""
        return {
            'airtel': {
                'Source IP': ['src_ip', 'source_address', 'calling_ip'],
                'Destination IP': ['dst_ip', 'dest_address', 'called_ip'],
                'Source Port': ['src_port', 'calling_port'],
                'Destination Port': ['dst_port', 'called_port'],
                'Phone': ['msisdn', 'mobile_number', 'calling_number'],
                'SubscriberID': ['subscriber_id', 'imsi'],
                'Start Time': ['start_timestamp', 'call_start_time'],
                'End Time': ['end_timestamp', 'call_end_time'],
                # B-Party fields
                'B-Phone': ['b_number', 'called_number', 'called_msisdn', 'callee', 'b_party', 'b_msisdn'],
                'B-SubscriberID': ['called_subscriber_id', 'b_imsi'],
                'B-CustName': ['called_name', 'callee_name']
            },
            'jio': {
                'Source IP': ['source_ip_address', 'calling_ip_addr'],
                'Destination IP': ['destination_ip_address', 'called_ip_addr'],
                'Phone': ['subscriber_number', 'msisdn_number'],
                'SubscriberID': ['sub_id', 'subscriber_identity'],
                'Start Time': ['session_start', 'begin_time'],
                'End Time': ['session_end', 'finish_time'],
                'B-Phone': ['b_number', 'called_number', 'called_msisdn', 'callee', 'b_party', 'b_msisdn'],
                'B-SubscriberID': ['called_subscriber_id', 'b_imsi'],
                'B-CustName': ['called_name', 'callee_name']
            },
            'vodafone': {
                'Source IP': ['orig_ip', 'a_party_ip'],
                'Destination IP': ['term_ip', 'b_party_ip'],
                'Phone': ['a_number', 'calling_party_number'],
                'Start Time': ['call_reference_time', 'cdr_start_time'],
                'End Time': ['call_release_time', 'cdr_end_time'],
                'B-Phone': ['b_number', 'b_party_number', 'called_number', 'called_msisdn'],
                'B-SubscriberID': ['called_subscriber_id', 'b_imsi'],
                'B-CustName': ['called_name', 'callee_name']
            },
            'generic': {
                'Source IP': ['src_ip', 'source_ip', 'source_address', 'orig_ip'],
                'Destination IP': ['dst_ip', 'dest_ip', 'destination_ip', 'term_ip'],
                'Source Port': ['src_port', 'source_port', 'sport'],
                'Destination Port': ['dst_port', 'dest_port', 'destination_port', 'dport'],
                'Start Time': ['start_time', 'begin_time', 'timestamp', 'time'],
                'End Time': ['end_time', 'finish_time', 'end_timestamp'],
                'B-Phone': ['b_number', 'called_number', 'called_msisdn', 'callee', 'b_party', 'b_msisdn'],
                'B-SubscriberID': ['called_subscriber_id', 'b_imsi'],
                'B-CustName': ['called_name', 'callee_name']
            }
        }
    
    def _initialize_field_aliases(self) -> Dict[str, str]:
        """Initialize common field aliases"""
        return {
            'src_ip': 'Source IP',
            'dst_ip': 'Destination IP',
            'src_port': 'Source Port',
            'dst_port': 'Destination Port',
            'sport': 'Source Port',
            'dport': 'Destination Port',
            'proto': 'Protocol',
            'protocol_type': 'Protocol',
            'start_timestamp': 'Start Time',
            'end_timestamp': 'End Time',
            'begin_time': 'Start Time',
            'finish_time': 'End Time',
            'msisdn': 'Phone',
            'mobile_number': 'Phone',
            'subscriber_number': 'Phone',
            'calling_number': 'Phone',
            'imsi': 'SubscriberID',
            'subscriber_id': 'SubscriberID',
            'customer_name': 'CustName',
            'user_name': 'CustName',
            'lat': 'Latitude',
            'lon': 'Longitude',
            'lng': 'Longitude'
        }
    
    def _update_stats(self, file_format: str, provider: str, record_count: int):
        """Update normalization statistics"""
        self.normalization_stats['total_files_processed'] += 1
        self.normalization_stats['successful_normalizations'] += 1
        self.normalization_stats['total_records_processed'] += record_count
        
        # Update format counts
        if file_format in self.normalization_stats['format_counts']:
            self.normalization_stats['format_counts'][file_format] += 1
        else:
            self.normalization_stats['format_counts'][file_format] = 1
        
        # Update provider counts
        if provider in self.normalization_stats['provider_counts']:
            self.normalization_stats['provider_counts'][provider] += 1
        else:
            self.normalization_stats['provider_counts'][provider] = 1
    
    def get_normalization_stats(self) -> Dict:
        """Get normalization statistics"""
        return self.normalization_stats.copy()
    
    def get_supported_formats(self) -> List[str]:
        """Get list of supported file formats"""
        return self.supported_formats.copy()
    
    def get_standard_schema(self) -> Dict:
        """Get the standard schema definition"""
        return self.STANDARD_SCHEMA.copy()
    
    def create_custom_mapping(self, sample_data: pd.DataFrame) -> Dict[str, str]:
        """Create custom field mapping based on sample data analysis"""
        if sample_data.empty:
            return {}
        
        custom_mapping = {}
        sample_columns = [col.lower() for col in sample_data.columns]
        
        # Analyze column patterns and suggest mappings
        for standard_field in self.STANDARD_SCHEMA.keys():
            standard_lower = standard_field.lower().replace(' ', '_')
            
            # Look for exact matches
            for col in sample_data.columns:
                if col.lower().replace(' ', '_') == standard_lower:
                    custom_mapping[standard_field] = col
                    break
            
            # Look for partial matches
            if standard_field not in custom_mapping:
                for col in sample_data.columns:
                    col_lower = col.lower()
                    if any(keyword in col_lower for keyword in [
                        standard_lower.split('_')[0],
                        standard_field.split()[0].lower()
                    ]):
                        custom_mapping[standard_field] = col
                        break
        
        return custom_mapping
