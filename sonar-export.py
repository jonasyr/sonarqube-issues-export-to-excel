try:
    import pandas as pd
    import requests
    import base64
    import os
    import argparse
    import logging
    import configparser
    import json
    import time
    from datetime import datetime, timedelta
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
except ImportError as e:
    print(f"Missing required dependency: {e}")
    print("Run: pip install requests pandas openpyxl")
    exit(1)

# SonarQube parameters
SONARQUBE_URL = os.getenv('SONAR_URL', 'http://localhost:9000/api/issues/search')
PROJECT_KEY = os.getenv('SONAR_PROJECT_KEY', '')
TOKEN = os.getenv('SONAR_TOKEN', '')

# Parse command-line arguments
parser = argparse.ArgumentParser(description='Export SonarQube issues to CSV or Excel format')
parser.add_argument('--format', type=str, choices=['csv', 'xlsx'], default='csv',
                    help='Output format: csv (default, recommended) or xlsx')
parser.add_argument('--output', '-o', type=str,
                    help='Output filename (default: sonarqube_issues.[format])')
parser.add_argument('--start-date', type=str,
                    help='Start date (YYYY-MM-DD), default: 2000-01-01')
parser.add_argument('--end-date', type=str,
                    help='End date (YYYY-MM-DD), default: today')
parser.add_argument('--severities', type=str,
                    help='Filter by severities (comma-separated): BLOCKER,CRITICAL,MAJOR,MINOR,INFO')
parser.add_argument('--types', type=str,
                    help='Filter by types (comma-separated): BUG,VULNERABILITY,CODE_SMELL,SECURITY_HOTSPOT')
parser.add_argument('--statuses', type=str,
                    help='Filter by statuses (comma-separated): OPEN,CONFIRMED,REOPENED,RESOLVED,CLOSED')
parser.add_argument('--config', type=str,
                    help='Path to configuration file')
parser.add_argument('--summary', action='store_true',
                    help='Generate summary report after export')
parser.add_argument('--log-level', type=str, choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                    default='INFO', help='Logging level (default: INFO)')
parser.add_argument('--projects', type=str,
                    help='Comma-separated project keys or @file.txt with one key per line')
parser.add_argument('--incremental', action='store_true',
                    help='Export only new issues since last export (tracks state per project)')
args = parser.parse_args()

# Load configuration from file if provided
config = None
if args.config and os.path.exists(args.config):
    config = configparser.ConfigParser()
    config.read(args.config)

    # Override with config file settings (environment variables and CLI args take precedence)
    if config.has_section('sonarqube'):
        if not os.getenv('SONAR_URL') and config.has_option('sonarqube', 'url'):
            SONARQUBE_URL = config.get('sonarqube', 'url')
        if not os.getenv('SONAR_PROJECT_KEY') and config.has_option('sonarqube', 'project_key'):
            PROJECT_KEY = config.get('sonarqube', 'project_key')

# Only check PROJECT_KEY if not in multi-project mode
if not args.projects:
    if not PROJECT_KEY or not TOKEN:
        print("Error: PROJECT_KEY and TOKEN must be configured")
        exit(1)
elif not TOKEN:
    print("Error: TOKEN must be configured")
    exit(1)

# Setup logging
log_filename = f'sonar_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
logging.basicConfig(
    level=getattr(logging, args.log_level),
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_filename),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

logger.info(f"Starting SonarQube export script")
logger.info(f"Log file: {log_filename}")

def load_project_keys(projects_arg):
    """Load project keys from argument or file"""
    if projects_arg.startswith('@'):
        # Load from file
        file_path = projects_arg[1:]
        logger.info(f"Loading project keys from file: {file_path}")
        if not os.path.exists(file_path):
            logger.error(f"Project file not found: {file_path}")
            print(f"❌ Error: Project file not found: {file_path}")
            exit(1)
        with open(file_path, 'r') as f:
            projects = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
        logger.info(f"Loaded {len(projects)} projects from file")
        return projects
    else:
        # Comma-separated list
        projects = [p.strip() for p in projects_arg.split(',')]
        logger.info(f"Loaded {len(projects)} projects from argument")
        return projects

def get_last_export_info(project_key):
    """Get information about the last successful export for a project"""
    state_file = f'.last_export_{project_key.replace(":", "_").replace("/", "_")}.json'

    if os.path.exists(state_file):
        try:
            with open(state_file, 'r') as f:
                state = json.load(f)
            logger.info(f"Found previous export state for {project_key}: {state.get('last_export_date')}")
            return state
        except Exception as e:
            logger.warning(f"Could not read state file for {project_key}: {e}")
            return None
    logger.info(f"No previous export found for {project_key}")
    return None

def save_export_info(project_key, end_date, issue_count):
    """Save information about this export for a project"""
    state_file = f'.last_export_{project_key.replace(":", "_").replace("/", "_")}.json'

    state = {
        'project_key': project_key,
        'last_export_date': end_date.strftime('%Y-%m-%d'),  # Store as YYYY-MM-DD only
        'last_export_timestamp': datetime.now().isoformat(),
        'issue_count': issue_count
    }

    try:
        with open(state_file, 'w') as f:
            json.dump(state, f, indent=2)
        logger.info(f"Saved export state for {project_key}")
    except Exception as e:
        logger.error(f"Could not save state file for {project_key}: {e}")

def create_session_with_retries():
    """Create a requests session with automatic retry logic"""
    session = requests.Session()

    retry_strategy = Retry(
        total=3,
        backoff_factor=1,  # Wait 1, 2, 4 seconds between retries
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"]
    )

    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    logger.debug("Created session with retry strategy")
    return session

def flatten_issue(issue):
    """
    Extract and flatten useful fields from SonarQube issue JSON.
    Returns a flat dictionary suitable for CSV/Excel export.
    """
    # Parse textRange if present
    text_range = issue.get('textRange', {})

    # Parse impacts if present
    impacts = issue.get('impacts', [])
    impacts_str = '; '.join([f"{imp.get('softwareQuality', '')}:{imp.get('severity', '')}"
                             for imp in impacts]) if impacts else ''

    return {
        'key': issue.get('key', ''),
        'rule': issue.get('rule', ''),
        'severity': issue.get('severity', ''),
        'component': issue.get('component', ''),
        'componentLongName': issue.get('componentLongName', ''),
        'project': issue.get('project', ''),
        'subProject': issue.get('subProject', ''),
        'line': issue.get('line', ''),
        'hash': issue.get('hash', ''),
        'startLine': text_range.get('startLine', '') if isinstance(text_range, dict) else '',
        'endLine': text_range.get('endLine', '') if isinstance(text_range, dict) else '',
        'startOffset': text_range.get('startOffset', '') if isinstance(text_range, dict) else '',
        'endOffset': text_range.get('endOffset', '') if isinstance(text_range, dict) else '',
        'message': issue.get('message', ''),
        'author': issue.get('author', ''),
        'assignee': issue.get('assignee', ''),
        'status': issue.get('status', ''),
        'resolution': issue.get('resolution', ''),
        'type': issue.get('type', ''),
        'tags': ','.join(issue.get('tags', [])),
        'creationDate': issue.get('creationDate', ''),
        'updateDate': issue.get('updateDate', ''),
        'closeDate': issue.get('closeDate', ''),
        'effort': issue.get('effort', ''),
        'debt': issue.get('debt', ''),
        'transitions': ','.join(issue.get('transitions', [])),
        'actions': ','.join(issue.get('actions', [])),
        'comments': len(issue.get('comments', [])),
        'flows': len(issue.get('flows', [])),
        'organization': issue.get('organization', ''),
        'cleanCodeAttribute': issue.get('cleanCodeAttribute', ''),
        'cleanCodeAttributeCategory': issue.get('cleanCodeAttributeCategory', ''),
        'impacts': impacts_str,
        'issueStatus': issue.get('issueStatus', ''),
        'projectName': issue.get('projectName', ''),
    }

def write_chunk_to_csv(filename, chunk_data, mode='w'):
    """
    Write a chunk of issue data to a CSV file in a memory-efficient way.

    Parameters:
        filename (str): The path to the output CSV file.
        chunk_data (list): List of issue dictionaries to write.
        mode (str): File write mode, 'w' for write (creates new file), 'a' for append.
    """
    # Flatten the issues before writing
    flattened_data = [flatten_issue(issue) for issue in chunk_data]
    df = pd.DataFrame(flattened_data)
    df.to_csv(filename, index=False, mode=mode, header=(mode == 'w'))
    logger.debug(f"Wrote {len(chunk_data)} issues to {filename} in mode '{mode}'")

def convert_csv_to_excel(csv_file, xlsx_file):
    """
    Convert CSV file to Excel format.
    Done at the end to avoid memory issues with chunked writing.

    Parameters:
        csv_file (str): Path to source CSV file.
        xlsx_file (str): Path to target Excel file.
    """
    logger.info(f"🔄 Converting CSV to Excel format...")
    try:
        # Read CSV in chunks to handle large files
        chunk_size = 100000
        chunks = []
        for chunk in pd.read_csv(csv_file, chunksize=chunk_size):
            chunks.append(chunk)
            logger.debug(f"Read chunk of {len(chunk)} rows")

        df = pd.concat(chunks, ignore_index=True)
        df.to_excel(xlsx_file, index=False, engine='openpyxl')
        logger.info(f"✅ Excel file created: {xlsx_file}")
        print(f"✅ Excel file created: {xlsx_file}")

        # Optionally remove CSV file
        if os.path.exists(csv_file) and csv_file != xlsx_file:
            response = input(f"Delete intermediate CSV file '{csv_file}'? (y/N): ")
            if response.lower() == 'y':
                os.remove(csv_file)
                logger.info(f"Removed intermediate CSV file: {csv_file}")
                print(f"🗑️  Removed {csv_file}")
    except Exception as e:
        logger.error(f"Could not convert to Excel: {e}", exc_info=True)
        print(f"⚠️  Warning: Could not convert to Excel: {e}")
        print(f"💡 CSV file is still available at: {csv_file}")

def generate_summary_report(csv_file, output_file='export_summary.txt'):
    """Generate a summary report from exported data"""
    try:
        logger.info(f"Generating summary report from {csv_file}")
        df = pd.read_csv(csv_file)

        summary = []
        summary.append("=" * 60)
        summary.append("SONARQUBE EXPORT SUMMARY REPORT")
        summary.append("=" * 60)
        summary.append(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        summary.append(f"Project: {PROJECT_KEY}")
        summary.append(f"Total Issues: {len(df):,}")

        if len(df) > 0:
            summary.append("\n" + "-" * 60)
            summary.append("BY SEVERITY")
            summary.append("-" * 60)
            if 'severity' in df.columns:
                for severity, count in df['severity'].value_counts().items():
                    percentage = (count / len(df)) * 100
                    summary.append(f"  {severity:<15} {count:>8,} ({percentage:>5.1f}%)")

            summary.append("\n" + "-" * 60)
            summary.append("BY TYPE")
            summary.append("-" * 60)
            if 'type' in df.columns:
                for issue_type, count in df['type'].value_counts().items():
                    percentage = (count / len(df)) * 100
                    summary.append(f"  {issue_type:<15} {count:>8,} ({percentage:>5.1f}%)")

            summary.append("\n" + "-" * 60)
            summary.append("BY STATUS")
            summary.append("-" * 60)
            if 'status' in df.columns:
                for status, count in df['status'].value_counts().items():
                    percentage = (count / len(df)) * 100
                    summary.append(f"  {status:<15} {count:>8,} ({percentage:>5.1f}%)")

            # Top rules
            summary.append("\n" + "-" * 60)
            summary.append("TOP 10 RULES")
            summary.append("-" * 60)
            if 'rule' in df.columns:
                for i, (rule, count) in enumerate(df['rule'].value_counts().head(10).items(), 1):
                    summary.append(f"  {i:>2}. {rule[:45]:<45} {count:>6,}")

            # Date range
            if 'creationDate' in df.columns:
                summary.append("\n" + "-" * 60)
                summary.append("DATE RANGE")
                summary.append("-" * 60)
                df['creationDate'] = pd.to_datetime(df['creationDate'])
                summary.append(f"  Earliest: {df['creationDate'].min()}")
                summary.append(f"  Latest:   {df['creationDate'].max()}")

        summary.append("\n" + "=" * 60)

        report_text = '\n'.join(summary)

        # Print to console
        print(f"\n{report_text}")

        # Save to file
        with open(output_file, 'w') as f:
            f.write(report_text)

        logger.info(f"Summary report saved to: {output_file}")
        print(f"\n📄 Summary report saved to: {output_file}")

    except Exception as e:
        logger.error(f"Could not generate summary report: {e}", exc_info=True)
        print(f"⚠️  Could not generate summary report: {e}")

def export_single_project(project_key, base_args, session, sonarqube_url, token, output_file=None):
    """
    Export issues from a single SonarQube project.

    Parameters:
        project_key (str): The SonarQube project key
        base_args: Parsed command-line arguments
        session: Requests session with retry logic
        sonarqube_url (str): SonarQube API URL
        token (str): Authentication token
        output_file (str): Custom output filename (optional)

    Returns:
        dict: Export results with status, count, and file path
    """
    try:
        # Fetch issues from SonarQube
        auth = base64.b64encode(f'{token}:'.encode()).decode()
        headers = {'Authorization': f'Basic {auth}'}
        page_size = 500

        # Date range configuration
        start_date_str = base_args.start_date if base_args.start_date else '2000-01-01'
        end_date_str = base_args.end_date if base_args.end_date else datetime.now().strftime('%Y-%m-%d')

        # Override with config file if not specified via CLI
        if config and config.has_section('export'):
            if not base_args.start_date and config.has_option('export', 'start_date'):
                start_date_str = config.get('export', 'start_date')
            if not base_args.format and config.has_option('export', 'format'):
                base_args.format = config.get('export', 'format')

        # Incremental export: adjust start date if needed
        if base_args.incremental:
            last_info = get_last_export_info(project_key)
            if last_info:
                start_date_str = last_info['last_export_date']
                logger.info(f"📅 Incremental mode: exporting issues since {start_date_str}")
                print(f"📅 Incremental mode: exporting issues since {start_date_str}")
                print(f"   (Last export: {last_info['last_export_timestamp']})")
            else:
                logger.info("ℹ️  No previous export found, performing full export")
                print("ℹ️  No previous export found, performing full export")

        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        except ValueError as e:
            logger.error(f"Invalid date format: {e}")
            return {'status': 'failed', 'error': f'Invalid date format: {e}'}

        if start_date >= end_date:
            logger.error("Start date must be before end date")
            return {'status': 'failed', 'error': 'Start date must be before end date'}

        delta = timedelta(days=30)
        current_start_date = start_date
        all_issues = []

        # Output file configuration
        if output_file:
            csv_file = output_file if output_file.endswith('.csv') else f"{output_file}.csv"
        elif base_args.output:
            csv_file = base_args.output if base_args.output.endswith('.csv') else f"{base_args.output}.csv"
        else:
            safe_project_name = project_key.replace(':', '_').replace('/', '_')
            csv_file = f'{safe_project_name}_issues.csv'

        # If user wants xlsx, we'll still write to CSV first, then convert
        if base_args.format == 'xlsx':
            xlsx_file = csv_file.replace('.csv', '.xlsx')
            logger.info("Writing to CSV first for memory efficiency, will convert to Excel at the end")

        chunk_size = 5000
        write_mode = 'w'
        total_issues_count = 0

        logger.info(f"Starting export for project: {project_key}")
        logger.info(f"Date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
        logger.info(f"Output file: {csv_file}")

        while current_start_date < end_date:
            current_end_date = current_start_date + delta
            if current_end_date > end_date:
                current_end_date = end_date

            logger.info(f"Fetching issues from {current_start_date.strftime('%Y-%m-%d')} to {current_end_date.strftime('%Y-%m-%d')}")
            print(f"   📥 Fetching issues from {current_start_date.strftime('%Y-%m-%d')} to {current_end_date.strftime('%Y-%m-%d')}...")

            params = {
                'componentKeys': project_key,
                'createdAfter': current_start_date.strftime('%Y-%m-%d'),
                'createdBefore': current_end_date.strftime('%Y-%m-%d'),
                'ps': page_size,
                'p': 1
            }

            # Add filters if provided
            if base_args.severities:
                params['severities'] = base_args.severities
            if base_args.types:
                params['types'] = base_args.types
            if base_args.statuses:
                params['statuses'] = base_args.statuses

            while True:
                try:
                    response = session.get(sonarqube_url, headers=headers, params=params, timeout=30)

                    if response.status_code == 200:
                        try:
                            data = response.json()
                            issues = data.get('issues', [])

                            if issues:
                                all_issues.extend(issues)
                                total_issues_count += len(issues)
                                logger.debug(f"Page {params['p']}: {len(issues)} issues")
                                print(f"      📄 Page {params['p']}: {len(issues)} issues ({total_issues_count} total so far)")

                            # Write to file in chunks to save memory
                            if len(all_issues) >= chunk_size:
                                logger.info(f"Writing chunk of {len(all_issues)} issues to CSV")
                                print(f"   💾 Writing chunk of {len(all_issues)} issues to CSV...")
                                write_chunk_to_csv(csv_file, all_issues, write_mode)
                                all_issues = []  # Clear memory
                                write_mode = 'a'  # Switch to append mode after first write

                            # Check if there are more pages
                            if len(issues) < page_size:
                                break
                            else:
                                params['p'] += 1

                        except requests.exceptions.JSONDecodeError as e:
                            logger.error(f"Failed to parse JSON response: {e}")
                            break
                    else:
                        if response.status_code == 401:
                            logger.error("Authentication failed. Check your TOKEN.")
                        elif response.status_code == 404:
                            logger.error("Project not found. Check your PROJECT_KEY and SONARQUBE_URL.")
                        elif response.status_code == 403:
                            logger.error("Access denied. Check project permissions.")
                        else:
                            logger.error(f"API request failed with status {response.status_code}: {response.text}")
                        break

                except requests.exceptions.Timeout:
                    logger.error("Connection timed out")
                    break
                except requests.exceptions.ConnectionError as e:
                    logger.error(f"Connection error: {e}")
                    break
                except Exception as e:
                    logger.error(f"Unexpected error: {e}", exc_info=True)
                    break

            current_start_date = current_end_date

        # Write any remaining issues
        if all_issues:
            logger.info(f"Writing final chunk of {len(all_issues)} issues")
            print(f"   💾 Writing final chunk of {len(all_issues)} issues to CSV...")
            write_chunk_to_csv(csv_file, all_issues, write_mode)

        # Save export state for incremental mode
        if total_issues_count > 0 and base_args.incremental:
            save_export_info(project_key, end_date, total_issues_count)

        return {
            'status': 'success',
            'count': total_issues_count,
            'csv_file': csv_file,
            'xlsx_file': xlsx_file if base_args.format == 'xlsx' else None,
            'start_date': start_date,
            'end_date': end_date
        }
    except Exception as e:
        logger.error(f"Failed to export {project_key}: {e}", exc_info=True)
        return {'status': 'failed', 'error': str(e)}

def export_multiple_projects(project_keys, base_args, session, sonarqube_url, token):
    """Export issues from multiple projects"""
    results = {}
    output_dir = base_args.output if base_args.output else 'multi_project_export'

    # Only create directory if it doesn't exist
    if not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
        logger.info(f"Created output directory: {output_dir}")

    print(f"\n{'='*70}")
    print(f"MULTI-PROJECT EXPORT: {len(project_keys)} projects")
    print(f"{'='*70}\n")

    for i, project_key in enumerate(project_keys, 1):
        print(f"\n{'='*70}")
        print(f"Processing project {i}/{len(project_keys)}: {project_key}")
        print(f"{'='*70}\n")

        # Set output file for this project
        safe_name = project_key.replace(':', '_').replace('/', '_')
        output_file = os.path.join(output_dir, f"{safe_name}_issues.csv")

        try:
            result = export_single_project(project_key, base_args, session, sonarqube_url, token, output_file)
            results[project_key] = result
        except Exception as e:
            logger.error(f"Failed to export {project_key}: {e}")
            results[project_key] = {'status': 'failed', 'error': str(e)}

    # Generate consolidated report
    print(f"\n{'='*70}")
    print("MULTI-PROJECT EXPORT SUMMARY")
    print(f"{'='*70}\n")

    successful = 0
    failed = 0
    total_issues = 0

    for project, result in results.items():
        if result['status'] == 'success':
            successful += 1
            total_issues += result['count']
            print(f"✅ {project}: {result['count']:,} issues → {result['csv_file']}")
        else:
            failed += 1
            print(f"❌ {project}: FAILED - {result.get('error', 'Unknown error')}")

    print(f"\n{'-'*70}")
    print(f"Summary: {successful} successful, {failed} failed, {total_issues:,} total issues")
    print(f"{'-'*70}\n")

    # Save summary JSON
    summary_file = os.path.join(output_dir, 'export_summary.json')
    with open(summary_file, 'w') as f:
        # Convert datetime objects to strings for JSON serialization
        json_results = {}
        for project, result in results.items():
            json_result = result.copy()
            if 'start_date' in json_result:
                json_result['start_date'] = json_result['start_date'].isoformat()
            if 'end_date' in json_result:
                json_result['end_date'] = json_result['end_date'].isoformat()
            json_results[project] = json_result
        json.dump(json_results, f, indent=2)

    logger.info(f"Multi-project export summary saved to: {summary_file}")
    print(f"📄 Summary saved to: {summary_file}")

    return results

# Create session with retry logic
session = create_session_with_retries()

# Check if multi-project mode
if args.projects:
    # Multi-project export
    project_keys = load_project_keys(args.projects)
    export_multiple_projects(project_keys, args, session, SONARQUBE_URL, TOKEN)
    logger.info("Multi-project export completed successfully")
    logger.info("Export script completed successfully")
    exit(0)

# Single project export (original behavior)
if not PROJECT_KEY or not TOKEN:
    print("Error: PROJECT_KEY and TOKEN must be configured")
    exit(1)

# Date range configuration
start_date_str = args.start_date if args.start_date else '2000-01-01'
end_date_str = args.end_date if args.end_date else datetime.now().strftime('%Y-%m-%d')

# Override with config file if not specified via CLI
if config and config.has_section('export'):
    if not args.start_date and config.has_option('export', 'start_date'):
        start_date_str = config.get('export', 'start_date')
    if not args.format and config.has_option('export', 'format'):
        args.format = config.get('export', 'format')

# Incremental export: adjust start date if needed
if args.incremental:
    last_info = get_last_export_info(PROJECT_KEY)
    if last_info:
        start_date_str = last_info['last_export_date']
        logger.info(f"📅 Incremental mode: exporting issues since {start_date_str}")
        print(f"📅 Incremental mode: exporting issues since {start_date_str}")
        print(f"   (Last export: {last_info['last_export_timestamp']})")
    else:
        logger.info("ℹ️  No previous export found, performing full export")
        print("ℹ️  No previous export found, performing full export")

try:
    start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
    end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
except ValueError as e:
    logger.error(f"Invalid date format: {e}")
    print(f"❌ Invalid date format: {e}")
    print("💡 Use format: YYYY-MM-DD (e.g., 2000-01-01)")
    exit(1)

if start_date >= end_date:
    logger.error("Start date must be before end date")
    print("❌ Error: Start date must be before end date")
    exit(1)

delta = timedelta(days=30)
current_start_date = start_date
all_issues = []

# Fetch issues from SonarQube
auth = base64.b64encode(f'{TOKEN}:'.encode()).decode()
headers = {'Authorization': f'Basic {auth}'}
page_size = 500

# Output file configuration
if args.output:
    csv_file = args.output if args.output.endswith('.csv') else f"{args.output}.csv"
else:
    csv_file = 'sonarqube_issues.csv'

# If user wants xlsx, we'll still write to CSV first, then convert
if args.format == 'xlsx':
    xlsx_file = csv_file.replace('.csv', '.xlsx')
    logger.info("Writing to CSV first for memory efficiency, will convert to Excel at the end")
    print(f"📝 Note: Writing to CSV first for memory efficiency, will convert to Excel at the end")

chunk_size = 5000
write_mode = 'w'
total_issues_count = 0

logger.info(f"Starting export for project: {PROJECT_KEY}")
logger.info(f"Date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
logger.info(f"Output format: {args.format}")
logger.info(f"Output file: {csv_file}")

print(f"🚀 Starting export...")
print(f"📅 Date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
print(f"🎯 Project: {PROJECT_KEY}")
if args.severities:
    logger.info(f"Severity filter: {args.severities}")
    print(f"🔍 Severities: {args.severities}")
if args.types:
    logger.info(f"Type filter: {args.types}")
    print(f"🔍 Types: {args.types}")
if args.statuses:
    logger.info(f"Status filter: {args.statuses}")
    print(f"🔍 Statuses: {args.statuses}")
print()

while current_start_date < end_date:
    current_end_date = current_start_date + delta
    if current_end_date > end_date:
        current_end_date = end_date

    logger.info(f"Fetching issues from {current_start_date.strftime('%Y-%m-%d')} to {current_end_date.strftime('%Y-%m-%d')}")
    print(f"📥 Fetching issues from {current_start_date.strftime('%Y-%m-%d')} to {current_end_date.strftime('%Y-%m-%d')}...")

    params = {
        'componentKeys': PROJECT_KEY,
        'createdAfter': current_start_date.strftime('%Y-%m-%d'),
        'createdBefore': current_end_date.strftime('%Y-%m-%d'),
        'ps': page_size,
        'p': 1
    }

    # Add filters if provided
    if args.severities:
        params['severities'] = args.severities
    if args.types:
        params['types'] = args.types
    if args.statuses:
        params['statuses'] = args.statuses

    while True:
        try:
            response = session.get(SONARQUBE_URL, headers=headers, params=params, timeout=30)

            if response.status_code == 200:
                try:
                    data = response.json()
                    issues = data.get('issues', [])

                    if issues:
                        all_issues.extend(issues)
                        total_issues_count += len(issues)
                        logger.debug(f"Page {params['p']}: {len(issues)} issues")
                        print(f"   📄 Page {params['p']}: {len(issues)} issues ({total_issues_count} total so far)")

                    # Write to file in chunks to save memory
                    if len(all_issues) >= chunk_size:
                        logger.info(f"Writing chunk of {len(all_issues)} issues to CSV")
                        print(f"💾 Writing chunk of {len(all_issues)} issues to CSV...")
                        write_chunk_to_csv(csv_file, all_issues, write_mode)
                        all_issues = []  # Clear memory
                        write_mode = 'a'  # Switch to append mode after first write

                    # Check if there are more pages
                    if len(issues) < page_size:
                        break
                    else:
                        params['p'] += 1

                except requests.exceptions.JSONDecodeError as e:
                    logger.error(f"Failed to parse JSON response: {e}")
                    print(f'❌ Failed to parse JSON response: {e}')
                    print(f'Response content: {response.text}')
                    break
            else:
                if response.status_code == 401:
                    logger.error("Authentication failed. Check your TOKEN.")
                    print('❌ Authentication failed. Check your TOKEN.')
                elif response.status_code == 404:
                    logger.error("Project not found. Check your PROJECT_KEY and SONARQUBE_URL.")
                    print('❌ Project not found. Check your PROJECT_KEY and SONARQUBE_URL.')
                elif response.status_code == 403:
                    logger.error("Access denied. Check project permissions.")
                    print('❌ Access denied. Check project permissions.')
                else:
                    logger.error(f"API request failed with status {response.status_code}: {response.text}")
                    print(f'❌ API request failed with status {response.status_code}')
                print(f'Response: {response.text}')
                break

        except requests.exceptions.Timeout:
            logger.error("Connection timed out")
            print('❌ Connection timed out. Check your network or try again later.')
            break
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error: {e}")
            print('❌ Connection error. Check your network and SONARQUBE_URL.')
            break
        except Exception as e:
            logger.error(f"Unexpected error: {e}", exc_info=True)
            print(f'❌ Unexpected error: {e}')
            break

    current_start_date = current_end_date

# Write any remaining issues
if all_issues:
    logger.info(f"Writing final chunk of {len(all_issues)} issues")
    print(f"💾 Writing final chunk of {len(all_issues)} issues to CSV...")
    write_chunk_to_csv(csv_file, all_issues, write_mode)

if total_issues_count > 0:
    logger.info(f"Export completed: {total_issues_count} issues exported to {csv_file}")
    print(f'\n✅ CSV Export completed: {total_issues_count} issues exported to {csv_file}')
    print(f'📊 Date range: {start_date.strftime("%Y-%m-%d")} to {end_date.strftime("%Y-%m-%d")}')

    # Convert to Excel if requested
    if args.format == 'xlsx':
        convert_csv_to_excel(csv_file, xlsx_file)
        logger.info(f"Final output: {xlsx_file}")
        print(f'\n✅ Final output: {xlsx_file}')
    else:
        logger.info(f"Final output: {csv_file}")
        print(f'\n✅ Final output: {csv_file}')

    # Generate summary report if requested
    if args.summary:
        generate_summary_report(csv_file)

    # Save export state for incremental mode
    if args.incremental:
        save_export_info(PROJECT_KEY, end_date, total_issues_count)
else:
    logger.warning("No issues found")
    print('❌ No issues found.')

logger.info("Export script completed successfully")
