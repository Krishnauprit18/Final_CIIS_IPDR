import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional, Any, Union
from datetime import datetime, timedelta
import re
import ipaddress
from dataclasses import dataclass
from enum import Enum

class SearchOperator(Enum):
    """Search operators for filtering"""
    EQUALS = "equals"
    CONTAINS = "contains"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    GREATER_THAN = "gt"
    LESS_THAN = "lt"
    BETWEEN = "between"
    IN_LIST = "in"
    NOT_IN = "not_in"
    REGEX = "regex"

class SortOrder(Enum):
    """Sort order options"""
    ASC = "asc"
    DESC = "desc"

@dataclass
class SearchCriteria:
    """Search criteria structure"""
    field: str
    operator: SearchOperator
    value: Any
    case_sensitive: bool = False

@dataclass
class SearchResult:
    """Search result structure"""
    records: pd.DataFrame
    total_count: int
    filtered_count: int
    search_time_ms: float
    criteria_used: List[SearchCriteria]

class SearchQuerySystem:
    """
    Advanced search and query system for IPDR data analysis.
    Allows investigators to search for specific numbers, IPs, date ranges, and communication types.
    """
    
    def __init__(self, data: pd.DataFrame):
        """
        Initialize the search system with IPDR data
        
        Args:
            data: DataFrame containing IPDR records
        """
        self.data = data.copy()
        self._prepare_data()
        self._create_search_indices()
        
    def _prepare_data(self):
        """Prepare and clean data for efficient searching"""
        # Convert datetime columns
        datetime_columns = ['Start Time', 'End Time']
        for col in datetime_columns:
            if col in self.data.columns:
                self.data[col] = pd.to_datetime(self.data[col], errors='coerce')
        
        # Create additional search-friendly columns
        self.data['Start_DateTime'] = self.data['Start Time']
        self.data['End_DateTime'] = self.data['End Time']
        self.data['Call_Date'] = self.data['Start_DateTime'].dt.date
        self.data['Call_Time'] = self.data['Start_DateTime'].dt.time
        self.data['Hour'] = self.data['Start_DateTime'].dt.hour
        self.data['Day_of_Week'] = self.data['Start_DateTime'].dt.day_name()
        
        # Normalize phone numbers for better searching
        phone_cols = ['Phone', 'Alt-Phone']
        for col in phone_cols:
            if col in self.data.columns:
                # Convert to string first, then normalize
                self.data[f'{col}_normalized'] = self.data[col].astype(str).str.replace(r'[^\d]', '', regex=True)
        
        # Create IP address integer representations for range searches
        ip_cols = ['Source IP', 'Destination IP', 'NAT IP']
        for col in ip_cols:
            if col in self.data.columns:
                self.data[f'{col}_int'] = self.data[col].apply(self._ip_to_int)
                
    def _ip_to_int(self, ip_str: str) -> Optional[int]:
        """Convert IP address string to integer for efficient searching"""
        try:
            return int(ipaddress.IPv4Address(ip_str))
        except:
            return None
            
    def _create_search_indices(self):
        """Create search indices for faster querying"""
        self.search_indices = {
            'phone_numbers': set(),
            'ip_addresses': set(),
            'protocols': set(),
            'devices': set(),
            'subscribers': set(),
            'customers': set()
        }
        
        # Build phone number index
        for col in ['Phone', 'Alt-Phone']:
            if col in self.data.columns:
                self.search_indices['phone_numbers'].update(
                    self.data[col].dropna().unique()
                )
        
        # Build IP address index
        for col in ['Source IP', 'Destination IP', 'NAT IP']:
            if col in self.data.columns:
                self.search_indices['ip_addresses'].update(
                    self.data[col].dropna().unique()
                )
        
        # Build other indices
        if 'Protocol' in self.data.columns:
            self.search_indices['protocols'].update(
                self.data['Protocol'].dropna().unique()
            )
            
        if 'Device' in self.data.columns:
            self.search_indices['devices'].update(
                self.data['Device'].dropna().unique()
            )
            
        if 'SubscriberID' in self.data.columns:
            self.search_indices['subscribers'].update(
                self.data['SubscriberID'].dropna().unique()
            )
            
        if 'CustName' in self.data.columns:
            self.search_indices['customers'].update(
                self.data['CustName'].dropna().unique()
            )
    
    def search_by_phone_number(self, 
                              phone_number: str, 
                              include_alt_phone: bool = True,
                              exact_match: bool = False) -> SearchResult:
        """
        Search for records by phone number
        
        Args:
            phone_number: Phone number to search for
            include_alt_phone: Whether to include alternative phone numbers
            exact_match: Whether to use exact matching or partial matching
        """
        start_time = datetime.now()
        
        # Normalize search term
        normalized_phone = re.sub(r'[^\d]', '', phone_number)
        
        # Build search conditions
        conditions = []
        
        if exact_match:
            if 'Phone_normalized' in self.data.columns:
                conditions.append(self.data['Phone_normalized'] == normalized_phone)
            if include_alt_phone and 'Alt-Phone_normalized' in self.data.columns:
                conditions.append(self.data['Alt-Phone_normalized'] == normalized_phone)
        else:
            if 'Phone_normalized' in self.data.columns:
                conditions.append(self.data['Phone_normalized'].str.contains(normalized_phone, na=False, regex=False))
            if include_alt_phone and 'Alt-Phone_normalized' in self.data.columns:
                conditions.append(self.data['Alt-Phone_normalized'].str.contains(normalized_phone, na=False, regex=False))
        
        # Combine conditions
        if conditions:
            combined_condition = conditions[0]
            for condition in conditions[1:]:
                combined_condition |= condition
            
            filtered_data = self.data[combined_condition]
        else:
            filtered_data = pd.DataFrame()
        
        search_time = (datetime.now() - start_time).total_seconds() * 1000
        
        criteria = [SearchCriteria(
            field="Phone Number",
            operator=SearchOperator.EQUALS if exact_match else SearchOperator.CONTAINS,
            value=phone_number
        )]
        
        return SearchResult(
            records=filtered_data,
            total_count=len(self.data),
            filtered_count=len(filtered_data),
            search_time_ms=search_time,
            criteria_used=criteria
        )
    
    def search_by_ip_address(self, 
                           ip_address: str, 
                           search_source: bool = True,
                           search_destination: bool = True,
                           search_nat: bool = True,
                           exact_match: bool = True) -> SearchResult:
        """
        Search for records by IP address
        
        Args:
            ip_address: IP address to search for
            search_source: Search in source IP field
            search_destination: Search in destination IP field  
            search_nat: Search in NAT IP field
            exact_match: Whether to use exact matching
        """
        start_time = datetime.now()
        
        conditions = []
        
        if exact_match:
            if search_source and 'Source IP' in self.data.columns:
                conditions.append(self.data['Source IP'] == ip_address)
            if search_destination and 'Destination IP' in self.data.columns:
                conditions.append(self.data['Destination IP'] == ip_address)
            if search_nat and 'NAT IP' in self.data.columns:
                conditions.append(self.data['NAT IP'] == ip_address)
        else:
            if search_source and 'Source IP' in self.data.columns:
                conditions.append(self.data['Source IP'].str.contains(ip_address, na=False))
            if search_destination and 'Destination IP' in self.data.columns:
                conditions.append(self.data['Destination IP'].str.contains(ip_address, na=False))
            if search_nat and 'NAT IP' in self.data.columns:
                conditions.append(self.data['NAT IP'].str.contains(ip_address, na=False))
        
        # Combine conditions
        if conditions:
            combined_condition = conditions[0]
            for condition in conditions[1:]:
                combined_condition |= condition
                
            filtered_data = self.data[combined_condition]
        else:
            filtered_data = pd.DataFrame()
        
        search_time = (datetime.now() - start_time).total_seconds() * 1000
        
        criteria = [SearchCriteria(
            field="IP Address",
            operator=SearchOperator.EQUALS if exact_match else SearchOperator.CONTAINS,
            value=ip_address
        )]
        
        return SearchResult(
            records=filtered_data,
            total_count=len(self.data),
            filtered_count=len(filtered_data),
            search_time_ms=search_time,
            criteria_used=criteria
        )
    
    def search_by_date_range(self, 
                           start_date: Union[str, datetime],
                           end_date: Union[str, datetime],
                           date_field: str = 'Start_DateTime') -> SearchResult:
        """
        Search for records within a date range
        
        Args:
            start_date: Start date for the range
            end_date: End date for the range  
            date_field: Which date field to use for filtering
        """
        start_time = datetime.now()
        
        # Convert dates if strings
        if isinstance(start_date, str):
            start_date = pd.to_datetime(start_date)
        if isinstance(end_date, str):
            end_date = pd.to_datetime(end_date)
        
        # Filter by date range
        if date_field in self.data.columns:
            condition = (self.data[date_field] >= start_date) & (self.data[date_field] <= end_date)
            filtered_data = self.data[condition]
        else:
            filtered_data = pd.DataFrame()
        
        search_time = (datetime.now() - start_time).total_seconds() * 1000
        
        criteria = [SearchCriteria(
            field=date_field,
            operator=SearchOperator.BETWEEN,
            value=f"{start_date} to {end_date}"
        )]
        
        return SearchResult(
            records=filtered_data,
            total_count=len(self.data),
            filtered_count=len(filtered_data),
            search_time_ms=search_time,
            criteria_used=criteria
        )
    
    def search_by_communication_type(self, 
                                   protocol: Optional[str] = None,
                                   port_range: Optional[Tuple[int, int]] = None,
                                   duration_range: Optional[Tuple[int, int]] = None) -> SearchResult:
        """
        Search by communication type (protocol, ports, duration)
        
        Args:
            protocol: Protocol type (TCP, UDP, etc.)
            port_range: Tuple of (min_port, max_port)
            duration_range: Tuple of (min_duration, max_duration) in seconds
        """
        start_time = datetime.now()
        
        conditions = []
        criteria = []
        
        # Protocol filter
        if protocol and 'Protocol' in self.data.columns:
            conditions.append(self.data['Protocol'].str.upper() == protocol.upper())
            criteria.append(SearchCriteria(
                field="Protocol",
                operator=SearchOperator.EQUALS,
                value=protocol
            ))
        
        # Port range filter
        if port_range:
            min_port, max_port = port_range
            port_conditions = []
            
            for port_col in ['Source Port', 'Destination Port']:
                if port_col in self.data.columns:
                    port_condition = (
                        (self.data[port_col] >= min_port) & 
                        (self.data[port_col] <= max_port)
                    )
                    port_conditions.append(port_condition)
            
            if port_conditions:
                combined_port_condition = port_conditions[0]
                for condition in port_conditions[1:]:
                    combined_port_condition |= condition
                conditions.append(combined_port_condition)
                
                criteria.append(SearchCriteria(
                    field="Port Range",
                    operator=SearchOperator.BETWEEN,
                    value=f"{min_port}-{max_port}"
                ))
        
        # Duration range filter
        if duration_range and 'Duration' in self.data.columns:
            min_duration, max_duration = duration_range
            duration_condition = (
                (self.data['Duration'] >= min_duration) & 
                (self.data['Duration'] <= max_duration)
            )
            conditions.append(duration_condition)
            criteria.append(SearchCriteria(
                field="Duration",
                operator=SearchOperator.BETWEEN,
                value=f"{min_duration}-{max_duration} seconds"
            ))
        
        # Combine all conditions
        if conditions:
            combined_condition = conditions[0]
            for condition in conditions[1:]:
                combined_condition &= condition
                
            filtered_data = self.data[combined_condition]
        else:
            filtered_data = self.data.copy()
        
        search_time = (datetime.now() - start_time).total_seconds() * 1000
        
        return SearchResult(
            records=filtered_data,
            total_count=len(self.data),
            filtered_count=len(filtered_data),
            search_time_ms=search_time,
            criteria_used=criteria
        )
    
    def advanced_search(self, 
                       criteria_list: List[SearchCriteria],
                       combine_with_and: bool = True,
                       sort_by: Optional[str] = None,
                       sort_order: SortOrder = SortOrder.ASC,
                       limit: Optional[int] = None) -> SearchResult:
        """
        Perform advanced search with multiple criteria
        
        Args:
            criteria_list: List of search criteria
            combine_with_and: Whether to combine criteria with AND (True) or OR (False)
            sort_by: Field to sort by
            sort_order: Sort order (ASC or DESC)
            limit: Maximum number of results to return
        """
        start_time = datetime.now()
        
        if not criteria_list:
            filtered_data = self.data.copy()
        else:
            conditions = []
            
            for criteria in criteria_list:
                condition = self._build_condition(criteria)
                if condition is not None:
                    conditions.append(condition)
            
            if conditions:
                if combine_with_and:
                    combined_condition = conditions[0]
                    for condition in conditions[1:]:
                        combined_condition &= condition
                else:
                    combined_condition = conditions[0]
                    for condition in conditions[1:]:
                        combined_condition |= condition
                
                filtered_data = self.data[combined_condition]
            else:
                filtered_data = self.data.copy()
        
        # Apply sorting
        if sort_by and sort_by in filtered_data.columns:
            ascending = (sort_order == SortOrder.ASC)
            filtered_data = filtered_data.sort_values(by=sort_by, ascending=ascending)
        
        # Apply limit
        if limit and limit > 0:
            filtered_data = filtered_data.head(limit)
        
        search_time = (datetime.now() - start_time).total_seconds() * 1000
        
        return SearchResult(
            records=filtered_data,
            total_count=len(self.data),
            filtered_count=len(filtered_data),
            search_time_ms=search_time,
            criteria_used=criteria_list
        )
    
    def _build_condition(self, criteria: SearchCriteria):
        """Build pandas condition from search criteria"""
        field = criteria.field
        operator = criteria.operator
        value = criteria.value
        
        if field not in self.data.columns:
            return None
        
        series = self.data[field]
        
        if operator == SearchOperator.EQUALS:
            if criteria.case_sensitive:
                return series == value
            else:
                return series.str.upper() == str(value).upper()
                
        elif operator == SearchOperator.CONTAINS:
            if criteria.case_sensitive:
                return series.str.contains(str(value), na=False, regex=False)
            else:
                return series.str.contains(str(value), na=False, case=False, regex=False)
                
        elif operator == SearchOperator.STARTS_WITH:
            if criteria.case_sensitive:
                return series.str.startswith(str(value), na=False)
            else:
                return series.str.upper().str.startswith(str(value).upper(), na=False)
                
        elif operator == SearchOperator.ENDS_WITH:
            if criteria.case_sensitive:
                return series.str.endswith(str(value), na=False)
            else:
                return series.str.upper().str.endswith(str(value).upper(), na=False)
                
        elif operator == SearchOperator.GREATER_THAN:
            return series > value
            
        elif operator == SearchOperator.LESS_THAN:
            return series < value
            
        elif operator == SearchOperator.BETWEEN:
            if isinstance(value, (list, tuple)) and len(value) == 2:
                return (series >= value[0]) & (series <= value[1])
                
        elif operator == SearchOperator.IN_LIST:
            if isinstance(value, (list, tuple, set)):
                return series.isin(value)
                
        elif operator == SearchOperator.NOT_IN:
            if isinstance(value, (list, tuple, set)):
                return ~series.isin(value)
                
        elif operator == SearchOperator.REGEX:
            return series.str.contains(str(value), na=False, regex=True)
        
        return None
    
    def search_by_customer(self, 
                          customer_name: Optional[str] = None,
                          customer_id: Optional[str] = None,
                          subscriber_id: Optional[str] = None,
                          exact_match: bool = False) -> SearchResult:
        """
        Search for records by customer information
        
        Args:
            customer_name: Customer name to search for
            customer_id: Customer ID to search for
            subscriber_id: Subscriber ID to search for
            exact_match: Whether to use exact matching
        """
        start_time = datetime.now()
        
        conditions = []
        criteria = []
        
        if customer_name and 'CustName' in self.data.columns:
            if exact_match:
                conditions.append(self.data['CustName'] == customer_name)
            else:
                conditions.append(self.data['CustName'].str.contains(customer_name, na=False, case=False))
            criteria.append(SearchCriteria(
                field="CustName",
                operator=SearchOperator.EQUALS if exact_match else SearchOperator.CONTAINS,
                value=customer_name
            ))
        
        if customer_id and 'CustID' in self.data.columns:
            conditions.append(self.data['CustID'] == customer_id)
            criteria.append(SearchCriteria(
                field="CustID",
                operator=SearchOperator.EQUALS,
                value=customer_id
            ))
        
        if subscriber_id and 'SubscriberID' in self.data.columns:
            conditions.append(self.data['SubscriberID'] == subscriber_id)
            criteria.append(SearchCriteria(
                field="SubscriberID",
                operator=SearchOperator.EQUALS,
                value=subscriber_id
            ))
        
        # Combine conditions
        if conditions:
            combined_condition = conditions[0]
            for condition in conditions[1:]:
                combined_condition &= condition
                
            filtered_data = self.data[combined_condition]
        else:
            filtered_data = pd.DataFrame()
        
        search_time = (datetime.now() - start_time).total_seconds() * 1000
        
        return SearchResult(
            records=filtered_data,
            total_count=len(self.data),
            filtered_count=len(filtered_data),
            search_time_ms=search_time,
            criteria_used=criteria
        )
    
    def get_search_suggestions(self, query: str, field: str) -> List[str]:
        """
        Get search suggestions for auto-completion
        
        Args:
            query: Partial search query
            field: Field to search in
            
        Returns:
            List of suggested completions
        """
        if field not in self.data.columns:
            return []
        
        # Get unique values from the field
        unique_values = self.data[field].dropna().astype(str).unique()
        
        # Filter suggestions that start with the query
        suggestions = [
            value for value in unique_values 
            if query.lower() in value.lower()
        ][:10]  # Limit to 10 suggestions
        
        return sorted(suggestions)
    
    def get_search_statistics(self) -> Dict[str, Any]:
        """Get statistics about searchable data"""
        stats = {
            'total_records': len(self.data),
            'date_range': {
                'start': self.data['Start_DateTime'].min() if 'Start_DateTime' in self.data.columns else None,
                'end': self.data['Start_DateTime'].max() if 'Start_DateTime' in self.data.columns else None
            },
            'unique_counts': {},
            'available_fields': list(self.data.columns),
            'search_indices_size': {k: len(v) for k, v in self.search_indices.items()}
        }
        
        # Count unique values in key fields
        key_fields = ['Protocol', 'CustName', 'SubscriberID', 'Phone', 'Source IP', 'Destination IP']
        for field in key_fields:
            if field in self.data.columns:
                stats['unique_counts'][field] = self.data[field].nunique()
        
        return stats
    
    def export_search_results(self, search_result: SearchResult, 
                            filename: str = "search_results.csv",
                            include_metadata: bool = True,
                            anonymize: bool = False) -> str:
        """
        Export search results to CSV file
        
        Args:
            search_result: SearchResult object to export
            filename: Name of the output file
            include_metadata: Whether to include search metadata
            
        Returns:
            Path to the exported file
        """
        # Prepare data
        df = search_result.records.copy()
        if anonymize and not df.empty:
            # Mask PII fields if present
            if 'Phone' in df.columns:
                df['Phone'] = df['Phone'].astype(str).str.replace(r'.(?=.{4}$)', 'X', regex=True)
            if 'Alt-Phone' in df.columns:
                df['Alt-Phone'] = df['Alt-Phone'].astype(str).str.replace(r'.(?=.{4}$)', 'X', regex=True)
            if 'B-Phone' in df.columns:
                df['B-Phone'] = df['B-Phone'].astype(str).str.replace(r'.(?=.{4}$)', 'X', regex=True)
            if 'Email' in df.columns:
                df['Email'] = df['Email'].astype(str).str.replace(r'(^.).*(@.*$)', r'\1***\2', regex=True)
        # Export the data
        df.to_csv(filename, index=False)
        
        # Add metadata if requested
        if include_metadata:
            metadata_filename = filename.replace('.csv', '_metadata.txt')
            with open(metadata_filename, 'w') as f:
                f.write("Search Results Metadata\n")
                f.write("=" * 30 + "\n")
                f.write(f"Total records in dataset: {search_result.total_count}\n")
                f.write(f"Filtered records returned: {search_result.filtered_count}\n")
                f.write(f"Search time: {search_result.search_time_ms:.2f} ms\n")
                f.write(f"Search criteria used:\n")
                for criteria in search_result.criteria_used:
                    f.write(f"  - {criteria.field} {criteria.operator.value} '{criteria.value}'\n")
        
        return filename
