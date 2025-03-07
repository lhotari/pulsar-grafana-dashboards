#!/usr/bin/env -S uv run
import json
import re
import sys
from pathlib import Path
from typing import Set, Dict, Any

def extract_metric_names_from_promql(promql: str) -> Set[str]:
    """
    Extract metric names from a PromQL query string.
    
    Args:
        promql: A PromQL query string
        
    Returns:
        A set of unique metric names found in the query
    """
    # This regex pattern matches metric names in PromQL
    # A metric name must follow Prometheus naming conventions:
    # It must match the regex [a-zA-Z_:][a-zA-Z0-9_:]*
    pattern = r'(?<![a-zA-Z0-9_:])([a-zA-Z_:][a-zA-Z0-9_:]*)(?={|\[|\(|\s|$)'
    
    # Find all matches in the query
    metric_names = re.findall(pattern, promql)
    
    # Comprehensive list of PromQL keywords, operators, and functions
    promql_keywords = {
        # Operators
        'and', 'or', 'unless', 'by', 'without', 'on', 'ignoring', 'group_left', 
        'group_right', 'offset', 'bool',
        
        # Aggregation operators
        'sum', 'min', 'max', 'avg', 'group', 'stddev', 'stdvar', 'count', 'count_values', 
        'bottomk', 'topk', 'quantile',
        
        # Functions for counter/gauge
        'rate', 'increase', 'irate', 'delta', 'idelta', 'predict_linear', 'deriv',
        'resets', 'changes',
        
        # Functions for histogram
        'histogram_quantile', 'histogram_sum', 'histogram_count', 'histogram_fraction',
        
        # Range vector functions
        'avg_over_time', 'min_over_time', 'max_over_time', 'sum_over_time',
        'count_over_time', 'quantile_over_time', 'stddev_over_time', 'stdvar_over_time',
        'last_over_time', 'present_over_time',
        
        # PromQL 2.x functions
        'label_join', 'label_replace', 'absent', 'scalar', 'vector', 'time',
        
        # Mathematical functions
        'abs', 'ceil', 'floor', 'exp', 'sqrt', 'ln', 'log2', 'log10', 'round',
        'clamp', 'clamp_min', 'clamp_max',
        
        # Trigonometric functions
        'sin', 'cos', 'tan', 'asin', 'acos', 'atan', 'deg', 'rad', 'pi',
        
        # Date & time functions
        'day_of_week', 'day_of_month', 'day_of_year', 'days_in_month', 'month',
        'year', 'hour', 'minute', 'timestamp',
        
        # Label manipulation
        'label_replace', 'label_join',
        
        # String functions
        'sort', 'sort_desc',
        
        # Other utility functions
        'sgn', 'absent', 'absent_over_time', 'present_over_time', 'vector',
        
        # Common time units often used in expressions
        's', 'm', 'h', 'd', 'w', 'y'
    }
    
    # Return filtered unique metric names
    return {name for name in metric_names if name not in promql_keywords}

def extract_metrics_from_dashboard(dashboard_json: Dict[Any, Any]) -> Set[str]:
    """
    Extract all metric names from a Grafana dashboard JSON.
    
    Args:
        dashboard_json: Parsed Grafana dashboard JSON
        
    Returns:
        A set of unique metric names
    """
    metrics = set()
    
    # Process all panels recursively
    def process_panels(panels):
        for panel in panels:
            # If panel has sub-panels (like in rows), process them
            if 'panels' in panel:
                process_panels(panel['panels'])
            
            # Extract metrics from targets
            if 'targets' in panel:
                for target in panel['targets']:
                    if 'expr' in target:
                        promql = target['expr']
                        metrics.update(extract_metric_names_from_promql(promql))
    
    # Start processing panels
    if 'panels' in dashboard_json:
        process_panels(dashboard_json['panels'])
    
    return metrics

def process_dashboard_file(file_path: Path) -> Set[str]:
    """
    Process a Grafana dashboard JSON file and extract metric names.
    
    Args:
        file_path: Path to the dashboard JSON file
        
    Returns:
        A set of unique metric names
    """
    try:
        with open(file_path, 'r') as f:
            dashboard = json.load(f)
        return extract_metrics_from_dashboard(dashboard)
    except json.JSONDecodeError:
        print(f"Error: {file_path} is not a valid JSON file", file=sys.stderr)
        return set()
    except Exception as e:
        print(f"Error processing {file_path}: {str(e)}", file=sys.stderr)
        return set()

def main():
    # Check if file paths were provided
    if len(sys.argv) < 2:
        print("Usage: python extract_metrics.py <dashboard_file1.json> [dashboard_file2.json ...]", file=sys.stderr)
        sys.exit(1)
    
    # Process all input files
    all_metrics = set()
    for file_path in sys.argv[1:]:
        path = Path(file_path)
        if not path.exists():
            print(f"Warning: File {file_path} does not exist", file=sys.stderr)
            continue
        
        metrics = process_dashboard_file(path)
        all_metrics.update(metrics)
        print(f"Found {len(metrics)} unique metrics in {file_path}", file=sys.stderr)
    
    # Sort the metrics and print to stdout
    for metric in sorted(all_metrics):
        print(metric)

if __name__ == "__main__":
    main()