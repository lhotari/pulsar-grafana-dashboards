#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "requests",
# ]
# ///
import os
import json
import argparse
import requests


def extract_uid_from_file(file_path):
    """Extract the UID from a dashboard JSON file."""
    try:
        with open(file_path, 'r') as f:
            dashboard_data = json.load(f)
            # Check if this is a dashboard JSON file
            if isinstance(dashboard_data, dict) and 'uid' in dashboard_data:
                return dashboard_data['uid']
            else:
                print(f"Warning: {file_path} doesn't contain a dashboard UID at the top level")
                return None
    except json.JSONDecodeError:
        print(f"Warning: {file_path} is not a valid JSON file")
        return None
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return None


def export_and_replace_dashboards(dashboard_files, grafana_url):
    """
    Export dashboards from Grafana and replace specified files where UID matches.
    """
    if not dashboard_files:
        print("No input files provided")
        return
    
    print(f"Processing {len(dashboard_files)} input files")
    
    # Map UIDs to file paths
    uid_to_file = {}
    for file_path in dashboard_files:
        if not os.path.exists(file_path):
            print(f"Warning: File {file_path} does not exist")
            continue
            
        uid = extract_uid_from_file(file_path)
        if uid:
            uid_to_file[uid] = file_path
    
    if not uid_to_file:
        print("No valid dashboard files with UIDs found")
        return
    
    print(f"Found {len(uid_to_file)} valid dashboard files with UIDs")
    
    # Get all dashboards from Grafana
    try:
        response = requests.get(f"{grafana_url}/api/search?type=dash-db")
        response.raise_for_status()
        all_dashboards = response.json()
    except requests.RequestException as e:
        print(f"Error fetching dashboards from Grafana: {e}")
        return
    
    # Export and replace matching dashboards
    replaced_count = 0
    
    for dashboard in all_dashboards:
        uid = dashboard.get('uid')
        if not uid or uid not in uid_to_file:
            continue
        
        print(f"Exporting dashboard: {dashboard.get('title')} (UID: {uid})")
        
        try:
            # Get the dashboard JSON
            dashboard_response = requests.get(f"{grafana_url}/api/dashboards/uid/{uid}")
            dashboard_response.raise_for_status()
            dashboard_data = dashboard_response.json()
            
            # Extract just the dashboard part (no meta)
            dashboard_content = dashboard_data.get('dashboard', {})
            
            if not dashboard_content:
                print(f"Warning: No dashboard content found for UID {uid}")
                continue
            
            # Replace the file
            file_path = uid_to_file[uid]
            # delete version and id fields
            dashboard_content.pop('version', None)
            dashboard_content.pop('id', None)
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(dashboard_content, f, indent=2, ensure_ascii=False)
            
            replaced_count += 1
            print(f"Successfully replaced {file_path}")
            
        except requests.RequestException as e:
            print(f"Error exporting dashboard {uid}: {e}")
        except Exception as e:
            print(f"Error writing dashboard {uid} to file: {e}")
    
    print(f"Done! Replaced {replaced_count} dashboard files out of {len(uid_to_file)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export and replace Grafana dashboards")
    parser.add_argument("files", nargs='+', help="Dashboard JSON files to update")
    parser.add_argument("--grafana-url", default="http://localhost:3000", help="Grafana URL (default: http://localhost:3000)")
    args = parser.parse_args()
    
    export_and_replace_dashboards(args.files, args.grafana_url)
