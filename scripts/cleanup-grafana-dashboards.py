#!/usr/bin/env -S uv run
"""
Grafana Dashboard Cleanup Utility
---------------------------------

This script combines multiple functions for Grafana dashboard JSON file management:
1. Removing top-level fields like 'id', 'version', and 'iteration'
2. Generating consistent UIDs - ensures dashboards have stable, deterministic UIDs
3. Removing datasource configurations:
   - All Prometheus datasource references 
   - All datasource template variables (from templating.list)
   - Allows using Grafana's default datasource
4. Recursively removing fields like '$$hashKey', '__requires', 'pluginVersion', and '__inputs'
5. Setting default refresh interval to 30s
6. Setting default time range from "now-15m" to "now"
7. Setting default timezone to UTC
8. Setting dashboard tags to a specified list
9. Disabling points on all time series panels by setting showPoints to "never"
10. Standardizing template variable current values:
    - For variables with includeAll=true: set current to {"text": "All", "value": "$__all"}
    - For other variables: set current to an empty object {}

The UID generation is based on a project identifier, the file path, and dashboard
characteristics, ensuring:
- Consistent UIDs when generated multiple times for the same file
- UIDs tied to the project and file location rather than content
- Prevents conflicts when users have similar dashboards in their own Grafana
- Content changes won't affect the UID

Usage:
    python cleanup-grafana-dashboards.py [options] file1.json [file2.json ...]

Options:
    --project-id ID                Custom project identifier for UID generation (default: "lhotari/pulsar-grafana-dashboards")
    --remove-prometheus-datasources Remove all Prometheus datasource references and all datasource template variables
    --set-tags TAGS                Set dashboard tags to a comma-separated list of tags (e.g. "production,grafana,pulsar")
    --disable-points               Disable points on all time series panels by setting showPoints to "never"

Output:
    - Modified JSON files with removed fields and/or updated UIDs
    - Status report of processed files
"""

import json
import sys
import os
import hashlib
import argparse

def generate_uid(file_path, dashboard_data, project_id):
    """
    Generate a deterministic UID based on project identifier, relative path, and title.
    The UID will be 9 characters long using a mix of lowercase letters and numbers,
    similar to Grafana's standard UID format.
    
    Args:
        file_path (str): Path to the dashboard file
        dashboard_data (dict): Dashboard JSON data
        project_id (str): Project identifier
    
    Returns:
        str: A generated UID (9 characters)
    """
    # Use a normalized path for better consistency across systems
    normalized_path = os.path.normpath(file_path)
    
    # Create a hash from project ID and file path
    hash_input = f"{project_id}:{normalized_path}"
    
    # Generate a hash
    hash_obj = hashlib.sha256(hash_input.encode('utf-8'))
    hash_bytes = hash_obj.digest()
    
    # Convert to a Grafana-like UID (9 characters, alphanumeric with underscore)
    alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_"
    uid = ""
    
    # Use 6 bytes from the hash (48 bits) to generate 9 characters
    # Each character represents ~5.33 bits of information
    for i in range(9):
        # Find the byte and bit position
        byte_pos = (i * 5) // 8
        bit_offset = (i * 5) % 8
        
        # Extract 5 bits from the current position
        if bit_offset <= 3:
            # Bits all come from the same byte
            value = (hash_bytes[byte_pos] >> (3 - bit_offset)) & 0x1F
        else:
            # Bits span two bytes
            value = ((hash_bytes[byte_pos] << (bit_offset - 3)) & 0x1F) 
            if byte_pos + 1 < len(hash_bytes):
                value |= (hash_bytes[byte_pos + 1] >> (11 - bit_offset))
        
        # Map to the alphabet (mod to ensure valid index)
        uid += alphabet[value % len(alphabet)]
    
    return uid

def remove_recursive(obj, fields_to_remove):
    """
    Recursively removes specified fields from a JSON structure.
    
    Args:
        obj: The JSON object or array to process
        fields_to_remove: List of field names to remove
    
    Returns:
        dict: Counts of removed fields by type
    """
    # Initialize removal counters
    recursive_removals_count = {field: 0 for field in fields_to_remove}
    
    if isinstance(obj, dict):
        # Remove all target fields if present
        for field in fields_to_remove:
            if field in obj:
                del obj[field]
                recursive_removals_count[field] += 1
        
        # Process all dict values
        for key in list(obj.keys()):
            sub_counts = remove_recursive(obj[key], fields_to_remove)
            for field, count in sub_counts.items():
                recursive_removals_count[field] += count
    
    elif isinstance(obj, list):
        # Process all list items
        for item in obj:
            sub_counts = remove_recursive(item, fields_to_remove)
            for field, count in sub_counts.items():
                recursive_removals_count[field] += count
    
    return recursive_removals_count

def remove_top_level_fields(dashboard, fields_to_remove):
    """
    Removes specific fields at the top level of the dashboard.
    
    Args:
        dashboard: The dashboard JSON object
        fields_to_remove: List of field names to remove
    
    Returns:
        dict: Map of field names to boolean indicating if they were removed
    """
    # Initialize removal status
    removals = {field: False for field in fields_to_remove}
    
    # Remove each field if it exists
    for field in fields_to_remove:
        if field in dashboard:
            del dashboard[field]
            removals[field] = True
    
    return removals

def standardize_template_variables(dashboard):
    """
    Standardizes template variable current values:
    - For variables with includeAll=true: set current to {"text": "All", "value": "$__all"}
    - For other variables: set current to an empty object {}
    
    Args:
        dashboard: The dashboard JSON object
    
    Returns:
        tuple: (templates_updated, variables_standardized)
    """
    templates_updated = False
    variables_standardized = 0
    
    # Check if templating exists and contains a list of template variables
    if 'templating' in dashboard and isinstance(dashboard['templating'], dict) and 'list' in dashboard['templating']:
        template_list = dashboard['templating']['list']
        
        # Process each template variable
        for variable in template_list:
            if isinstance(variable, dict):
                # Determine if the variable has includeAll=true
                include_all = variable.get('includeAll', False)
                
                # Set current value based on includeAll setting
                if include_all:
                    if variable.get('current') != {"text": "All", "value": "$__all"}:
                        variable['current'] = {"text": "All", "value": "$__all"}
                        templates_updated = True
                        variables_standardized += 1
                else:
                    if variable.get('current') != {}:
                        variable['current'] = {}
                        templates_updated = True
                        variables_standardized += 1
    
    return templates_updated, variables_standardized

def set_default_values(dashboard, tags_list=None):
    """
    Sets default values for refresh interval, time range, timezone, and tags if provided.
    
    Args:
        dashboard: The dashboard JSON object
        tags_list: Optional list of tags to set
    
    Returns:
        tuple: (refresh_updated, time_updated, timezone_updated, tags_updated)
    """
    refresh_updated = False
    time_updated = False
    timezone_updated = False
    tags_updated = False
    
    # Set default refresh interval
    if 'refresh' not in dashboard or dashboard['refresh'] != '30s':
        dashboard['refresh'] = '30s'
        refresh_updated = True
    
    # Set default time range
    if 'time' not in dashboard or dashboard['time'].get('from') != 'now-15m' or dashboard['time'].get('to') != 'now':
        dashboard['time'] = {
            'from': 'now-15m',
            'to': 'now'
        }
        time_updated = True
    
    # Set default timezone to UTC
    if 'timezone' not in dashboard or dashboard['timezone'] != 'utc':
        dashboard['timezone'] = 'utc'
        timezone_updated = True
    
    # Set tags if provided
    if tags_list is not None:
        current_tags = dashboard.get('tags', [])
        if set(current_tags) != set(tags_list):
            dashboard['tags'] = tags_list
            tags_updated = True
    
    return refresh_updated, time_updated, timezone_updated, tags_updated

def remove_prometheus_datasources_recursive(obj):
    """
    Recursively removes Prometheus datasource fields and template variables.
    
    Args:
        obj: The JSON object or array to process
    
    Returns:
        bool: True if any changes were made
    """
    modified = False
    
    if isinstance(obj, dict):
        # If this is a datasource object with type 'prometheus', mark for removal
        if 'datasource' in obj and isinstance(obj['datasource'], dict) and (obj['datasource'].get('type') == 'prometheus' or obj['datasource'].get('uid') == '${DataSource}'):
            del obj['datasource']
            modified = True

        # If this is a field called 'datasource' and it's a string with value 'Prometheus' (ignore case), set it to null
        if 'datasource' in obj and isinstance(obj['datasource'], str) and obj['datasource'].lower() == 'prometheus':
            obj['datasource'] = None
            modified = True
       
        # Check for templating.list array and remove datasource template variables
        if 'templating' in obj and isinstance(obj['templating'], dict) and 'list' in obj['templating'] and isinstance(obj['templating']['list'], list):
            templating_list = obj['templating']['list']
            # Filter out any items with type == 'datasource'
            original_length = len(templating_list)
            obj['templating']['list'] = [item for item in templating_list if not (isinstance(item, dict) and item.get('type') == 'datasource')]
            # Check if any items were removed
            if len(obj['templating']['list']) < original_length:
                modified = True
        
        # Continue traversing all dictionary values
        for key in list(obj.keys()):
            if remove_prometheus_datasources_recursive(obj[key]):
                modified = True
    
    elif isinstance(obj, list):
        # Traverse all list items
        for item in obj:
            if remove_prometheus_datasources_recursive(item):
                modified = True
    
    return modified

def disable_points_recursive(obj):
    """
    Recursively disables points on all time series panels by setting showPoints to "never".
    
    Args:
        obj: The JSON object or array to process
    
    Returns:
        int: Count of panels modified
    """
    panels_modified = 0
    
    if isinstance(obj, dict):
        # Check if this is a time series panel
        if obj.get('type') == 'timeseries':
            # Initialize fieldConfig if it doesn't exist
            if 'fieldConfig' not in obj:
                obj['fieldConfig'] = {}
            
            # Initialize defaults if it doesn't exist
            if 'defaults' not in obj['fieldConfig']:
                obj['fieldConfig']['defaults'] = {}
            
            # Initialize custom if it doesn't exist
            if 'custom' not in obj['fieldConfig']['defaults']:
                obj['fieldConfig']['defaults']['custom'] = {}
            
            # Set showPoints to "never"
            if obj['fieldConfig']['defaults']['custom'].get('showPoints') != 'never':
                obj['fieldConfig']['defaults']['custom']['showPoints'] = 'never'
                panels_modified += 1
        
        # Process panels array if it exists
        if 'panels' in obj and isinstance(obj['panels'], list):
            for panel in obj['panels']:
                panels_modified += disable_points_recursive(panel)
        
        # Continue traversing all dictionary values (except 'panels' which we already processed)
        for key in list(obj.keys()):
            if key != 'panels':  # Skip 'panels' as we've already processed it
                panels_modified += disable_points_recursive(obj[key])
    
    elif isinstance(obj, list):
        # Traverse all list items
        for item in obj:
            panels_modified += disable_points_recursive(item)
    
    return panels_modified

def process_dashboard(file_path, project_id, remove_prometheus, disable_points, top_level_fields, recursive_fields, tags_list=None):
    """
    Process a single dashboard file by removing fields and updating UIDs.
    
    Args:
        file_path (str): Path to the dashboard JSON file
        project_id (str): Project identifier for UID generation
        remove_prometheus (bool): Whether to remove Prometheus datasource configurations
        disable_points (bool): Whether to disable points on all time series panels
        top_level_fields (list): Fields to remove at the top level
        recursive_fields (list): Fields to remove recursively
        tags_list (list, optional): List of tags to set on the dashboard
    
    Returns:
        dict: Results of processing the file
    """
    results = {
        'success': False,
        'uid_updated': False,
        'prometheus_removed': False,
        'points_disabled': 0,
        'file_modified': False,
        'refresh_updated': False,
        'time_updated': False,
        'timezone_updated': False,
        'tags_updated': False,
        'templates_updated': False,
        'variables_standardized': 0
    }
    
    # Add fields to track for recursive removal
    for field in recursive_fields:
        results[f"{field}_removed"] = 0
        
    # Add fields to track for top-level removal
    for field in top_level_fields:
        results[f"{field}_removed"] = False
    
    try:
        # Check if file exists
        if not os.path.isfile(file_path):
            print(f"Warning: File '{file_path}' does not exist. Skipping.")
            return results
        
        # Read and parse the JSON file
        with open(file_path, 'r', encoding='utf-8') as file:
            try:
                dashboard = json.load(file)
            except json.JSONDecodeError:
                print(f"Error: '{file_path}' is not a valid JSON file. Skipping.")
                return results
        
        # Get current values before modification
        old_uid = dashboard.get('uid', None)
        
        # Remove top-level fields
        top_level_removals = remove_top_level_fields(dashboard, top_level_fields)
        
        # Update results with top-level removals
        for field, removed in top_level_removals.items():
            results[f"{field}_removed"] = removed
            if removed:
                results['file_modified'] = True
                print(f"- Removed '{field}' from '{file_path}'")
        
        # Generate and update UID
        new_uid = generate_uid(file_path, dashboard, project_id)
        if old_uid != new_uid:
            dashboard['uid'] = new_uid
            results['uid_updated'] = True
            results['file_modified'] = True
            
            if old_uid:
                print(f"- Changed UID from '{old_uid}' to '{new_uid}' in '{file_path}'")
            else:
                print(f"- Assigned new UID '{new_uid}' to '{file_path}'")
        
        # Standardize template variable current values
        templates_updated, variables_standardized = standardize_template_variables(dashboard)
        results['templates_updated'] = templates_updated
        results['variables_standardized'] = variables_standardized
        
        if templates_updated:
            results['file_modified'] = True
            print(f"- Standardized {variables_standardized} template variables in '{file_path}'")
        
        # Set default values for refresh, time, timezone, and tags if provided
        refresh_updated, time_updated, timezone_updated, tags_updated = set_default_values(dashboard, tags_list)
        results['refresh_updated'] = refresh_updated
        results['time_updated'] = time_updated
        results['timezone_updated'] = timezone_updated
        results['tags_updated'] = tags_updated
        
        if refresh_updated:
            results['file_modified'] = True
            print(f"- Set refresh interval to '30s' in '{file_path}'")
        
        if time_updated:
            results['file_modified'] = True
            print(f"- Set time range to 'now-15m' to 'now' in '{file_path}'")
        
        if timezone_updated:
            results['file_modified'] = True
            print(f"- Set timezone to 'utc' in '{file_path}'")
            
        if tags_updated:
            results['file_modified'] = True
            print(f"- Set tags to {tags_list} in '{file_path}'")
        
        # Remove Prometheus datasource configurations if requested
        if remove_prometheus:
            prometheus_modified = remove_prometheus_datasources_recursive(dashboard)
            results['prometheus_removed'] = prometheus_modified
            if prometheus_modified:
                results['file_modified'] = True
                print(f"- Removed datasource configurations from '{file_path}'")
        
        # Disable points on all time series panels if requested
        if disable_points:
            panels_modified = disable_points_recursive(dashboard)
            results['points_disabled'] = panels_modified
            if panels_modified > 0:
                results['file_modified'] = True
                print(f"- Disabled points on {panels_modified} time series panels in '{file_path}'")
        
        # Perform recursive field removal
        recursive_removals_count = remove_recursive(dashboard, recursive_fields)
        
        # Update results with removed counts
        for field, count in recursive_removals_count.items():
            results[f"{field}_removed"] = count
            if count > 0:
                results['file_modified'] = True
                print(f"- Removed {count} '{field}' fields from '{file_path}'")
        
        # Write the modified dashboard back to the file if any changes were made
        if results['file_modified']:
            with open(file_path, 'w', encoding='utf-8') as output_file:
                json.dump(dashboard, output_file, indent=2, ensure_ascii=False)
        
        results['success'] = True
        
    except Exception as e:
        print(f"Error processing '{file_path}': {str(e)}. Skipping.")
    
    return results

def get_default_project_id():
    """
    Return the default project identifier from the original script.
    
    Returns:
        str: Default project identifier
    """
    return "lhotari/pulsar-grafana-dashboards"

def parse_arguments():
    """
    Parse command line arguments.
    
    Returns:
        Namespace: Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="Grafana Dashboard Cleanup Utility",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # Add arguments
    parser.add_argument(
        'files',
        metavar='file',
        nargs='+',
        help='Dashboard JSON files to process'
    )
    
    parser.add_argument(
        '--project-id',
        type=str,
        default=get_default_project_id(),
        help='Custom project identifier for UID generation'
    )
    
    parser.add_argument(
        '--remove-prometheus-datasources',
        action='store_true',
        help='Remove all datasource configurations for Prometheus datasources'
    )
    
    parser.add_argument(
        '--set-tags',
        type=str,
        help='Set dashboard tags to a comma-separated list of tags (e.g. "production,grafana,pulsar")'
    )
    
    parser.add_argument(
        '--disable-points',
        action='store_true',
        help='Disable points on all time series panels by setting showPoints to "never"'
    )
    
    # Parse arguments
    args = parser.parse_args()
    
    return args

def main():
    # Parse command line arguments
    args = parse_arguments()
    
    file_paths = args.files
    total_files = len(file_paths)
    
    # Define field lists
    recursive_fields = ['$$hashKey', '__requires', 'pluginVersion', '__inputs', 'prometheusLink']
    top_level_fields = ['id', 'version', 'iteration', 'links', 'gnetId', 'liveNow', 'preload', 'timepicker', 'annotations']
    
    # Process tags if provided
    tags_list = None
    if args.set_tags:
        tags_list = [tag.strip() for tag in args.set_tags.split(',') if tag.strip()]
    
    # Print operation mode
    print(f"Processing {total_files} Grafana dashboard files...")
    print(f"Using project identifier: '{args.project_id}'")
    
    # Describe fields being removed
    top_level_fields_str = "', '".join(top_level_fields)
    recursive_fields_str = "', '".join(recursive_fields)
    print(f"Removing top-level fields: '{top_level_fields_str}'")
    print(f"Recursively removing fields: '{recursive_fields_str}'")
    print("Generating consistent UIDs")
    print("Setting default refresh interval to '30s'")
    print("Setting default time range from 'now-15m' to 'now'")
    print("Setting default timezone to 'utc'")
    print("Standardizing template variable current values")
    
    if args.remove_prometheus_datasources:
        print("Removing Prometheus datasource references and all datasource template variables")
        
    if args.disable_points:
        print("Disabling points on all time series panels")
        
    if tags_list:
        print(f"Setting dashboard tags to: {tags_list}")
    print()
    
    # Track statistics
    success_count = 0
    uid_updated_count = 0
    prometheus_removed_count = 0
    panels_with_points_disabled = 0
    refresh_updated_count = 0
    time_updated_count = 0
    timezone_updated_count = 0
    tags_updated_count = 0
    templates_updated_count = 0
    total_variables_standardized = 0
    
    # Track top-level field removals
    top_level_removed_files = {field: 0 for field in top_level_fields}
    
    # Track recursive field removals
    fields_removed_files = {field: 0 for field in recursive_fields}
    total_fields_removed = {field: 0 for field in recursive_fields}
    
    modified_count = 0
    failed_count = 0
    
    # Process each file
    for file_path in file_paths:
        results = process_dashboard(file_path, args.project_id, args.remove_prometheus_datasources, 
                                  args.disable_points, top_level_fields, recursive_fields, tags_list)
        
        if results['success']:
            success_count += 1
            
            # Track top-level field removals
            for field in top_level_fields:
                if results[f"{field}_removed"]:
                    top_level_removed_files[field] += 1
            
            # Track UID updates
            if results['uid_updated']:
                uid_updated_count += 1
                
            # Track Prometheus removals
            if results['prometheus_removed']:
                prometheus_removed_count += 1
                
            # Track points disabled
            if results['points_disabled'] > 0:
                panels_with_points_disabled += results['points_disabled']
                
            # Track default value updates
            if results['refresh_updated']:
                refresh_updated_count += 1
            
            if results['time_updated']:
                time_updated_count += 1
            
            if results['timezone_updated']:
                timezone_updated_count += 1
                
            if results['tags_updated']:
                tags_updated_count += 1
                
            # Track template variable updates
            if results['templates_updated']:
                templates_updated_count += 1
                total_variables_standardized += results['variables_standardized']
                
            # Track recursive field removals
            for field in recursive_fields:
                count = results[f"{field}_removed"]
                if count > 0:
                    fields_removed_files[field] += 1
                    total_fields_removed[field] += count
            
            # Track modified files
            if results['file_modified']:
                modified_count += 1
        else:
            failed_count += 1
    
    # Print summary
    print("\n" + "="*60)
    print(f"Summary:")
    print(f"  Total files processed: {total_files}")
    print(f"  Successfully processed: {success_count}")
    
    # Print top-level field removal statistics
    for field in top_level_fields:
        print(f"  Files with '{field}' removed: {top_level_removed_files[field]}")
    
    print(f"  Files with UIDs updated: {uid_updated_count}")
    print(f"  Files with UIDs unchanged: {success_count - uid_updated_count}")
    
    # Print default value update statistics
    print(f"  Files with refresh interval updated: {refresh_updated_count}")
    print(f"  Files with time range updated: {time_updated_count}")
    print(f"  Files with timezone updated: {timezone_updated_count}")
    
    # Print template variable standardization statistics
    print(f"  Files with template variables standardized: {templates_updated_count}")
    print(f"  Total template variables standardized: {total_variables_standardized}")
    
    if tags_list:
        print(f"  Files with tags updated: {tags_updated_count}")
    
    # Print recursive field removal statistics
    for field in recursive_fields:
        if fields_removed_files[field] > 0:
            print(f"  Files with '{field}' fields removed: {fields_removed_files[field]}")
            print(f"  Total '{field}' fields removed: {total_fields_removed[field]}")
    
    if args.remove_prometheus_datasources:
        print(f"  Files with datasource configurations removed: {prometheus_removed_count}")
        
    if args.disable_points:
        print(f"  Total time series panels with points disabled: {panels_with_points_disabled}")
    
    print(f"  Total files modified: {modified_count}")
    print(f"  Files failed: {failed_count}")
    
    # Return non-zero exit code if any files failed
    if failed_count > 0:
        sys.exit(1)

if __name__ == "__main__":
    main()
