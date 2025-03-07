#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "pyyaml",
# ]
# ///
"""
Pulsar Grafana Dashboard YAML Generator
---------------------------------------

This script generates YAML configuration for Pulsar Helm chart's values.yaml
for victoria-metrics-k8s-stack config, based on input JSON files.

It takes the input file path's directory part as the name of the provider
and uses a capitalized version as the folder. The URL for each dashboard
points to the lhotari/pulsar-grafana-dashboards GitHub project.

Usage:
    python generate-dashboard-yaml.py dashboard1.json [dashboard2.json ...]

Output:
    YAML configuration printed to stdout that can be copied into values.yaml
"""

import sys
import os
import yaml

# GitHub repository URL where dashboards will be hosted
GITHUB_REPO = "lhotari/pulsar-grafana-dashboards"
GITHUB_BRANCH = "master"  # or change to your branch name
GITHUB_RAW_URL = f"https://raw.githubusercontent.com/{GITHUB_REPO}/{GITHUB_BRANCH}"

def generate_yaml_config(file_paths):
    """
    Generate YAML configuration for Pulsar Helm chart's values.yaml.
    
    Args:
        file_paths (list): List of dashboard JSON file paths
    
    Returns:
        str: YAML configuration
    """
    # Group files by directory
    providers = {}
    for file_path in file_paths:
        # Extract directory and filename
        dir_path, filename = os.path.split(file_path)
        
        # Use directory name as provider name, default to 'dashboards' if at root
        provider_name = os.path.basename(dir_path) if dir_path else 'dashboards'
        
        # Capitalize folder name
        folder_name = provider_name.capitalize()
        
        # Create provider if it doesn't exist
        if provider_name not in providers:
            providers[provider_name] = {
                'name': folder_name,
                'dashboards': {}
            }
        
        # Create dashboard entry
        dashboard_name = os.path.splitext(filename)[0]  # Remove extension
        rel_path = os.path.normpath(file_path)  # Normalize path for URL
        providers[provider_name]['dashboards'][dashboard_name] = {
            'url': f"{GITHUB_RAW_URL}/{rel_path}",
        }
    
    # Build configuration dictionary with victoria-metrics-k8s-stack as the root key
    config = {
        'victoria-metrics-k8s-stack': {
            'grafana': {
                'dashboardProviders': {
                    'dashboardproviders.yaml': {
                        'apiVersion': 1,
                        'providers': []
                    }
                },
                'dashboards': {}
            }
        }
    }
    
    # Add providers to configuration
    for provider_name, provider_data in providers.items():
        # Add provider to dashboardProviders
        config['victoria-metrics-k8s-stack']['grafana']['dashboardProviders']['dashboardproviders.yaml']['providers'].append({
            'name': provider_name,
            'orgId': 1,
            'folder': provider_data['name'],
            'type': 'file',
            'disableDeletion': False,
            'editable': True,
            'allowUiUpdates': True,
            'options': {
                'path': f"/var/lib/grafana/dashboards/{provider_name}"
            }
        })
        
        # Add dashboards to configuration
        config['victoria-metrics-k8s-stack']['grafana']['dashboards'][provider_name] = provider_data['dashboards']
    
    # Convert to YAML
    return yaml.dump(config, default_flow_style=False, sort_keys=False)

def main():
    # Check command line arguments
    if len(sys.argv) < 2:
        print("Error: No files specified.")
        print(f"Usage: {sys.argv[0]} dashboard1.json [dashboard2.json ...]")
        sys.exit(1)
    
    file_paths = sys.argv[1:]
    
    # Generate and print YAML configuration
    yaml_config = generate_yaml_config(file_paths)
    print(yaml_config)

if __name__ == "__main__":
    main()
