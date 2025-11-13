try:
    import pandas as pd
    import requests
    import base64
    import os
    import argparse
    from datetime import datetime, timedelta
except ImportError as e:
    print(f"Missing required dependency: {e}")
    print("Run: pip install requests pandas openpyxl")
    exit(1)

# SonarQube parameters
SONARQUBE_URL = os.getenv('SONAR_URL', 'http://localhost:9000/api/issues/search')
PROJECT_KEY = os.getenv('SONAR_PROJECT_KEY', '')
TOKEN = os.getenv('SONAR_TOKEN', '')

if not PROJECT_KEY or not TOKEN:
    print("Error: PROJECT_KEY and TOKEN must be configured")
    exit(1)

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
args = parser.parse_args()

# Function to write data in chunks to CSV (memory efficient)
def write_chunk_to_csv(filename, chunk_data, mode='w'):
    """
    Write a chunk of issue data to a CSV file in a memory-efficient way.

    Parameters:
        filename (str): The path to the output CSV file.
        chunk_data (list): List of issue dictionaries to write.
        mode (str): File write mode, 'w' for write (creates new file), 'a' for append.
    """
    df = pd.DataFrame(chunk_data)
    df.to_csv(filename, index=False, mode=mode, header=(mode == 'w'))

def convert_csv_to_excel(csv_file, xlsx_file):
    """
    Convert CSV file to Excel format.
    Done at the end to avoid memory issues with chunked writing.

    Parameters:
        csv_file (str): Path to source CSV file.
        xlsx_file (str): Path to target Excel file.
    """
    print(f"🔄 Converting CSV to Excel format...")
    try:
        # Read CSV in chunks to handle large files
        chunk_size = 100000
        chunks = []
        for chunk in pd.read_csv(csv_file, chunksize=chunk_size):
            chunks.append(chunk)

        df = pd.concat(chunks, ignore_index=True)
        df.to_excel(xlsx_file, index=False, engine='openpyxl')
        print(f"✅ Excel file created: {xlsx_file}")

        # Optionally remove CSV file
        if os.path.exists(csv_file) and csv_file != xlsx_file:
            response = input(f"Delete intermediate CSV file '{csv_file}'? (y/N): ")
            if response.lower() == 'y':
                os.remove(csv_file)
                print(f"🗑️  Removed {csv_file}")
    except Exception as e:
        print(f"⚠️  Warning: Could not convert to Excel: {e}")
        print(f"💡 CSV file is still available at: {csv_file}")

# Fetch issues from SonarQube
auth = base64.b64encode(f'{TOKEN}:'.encode()).decode()
headers = {'Authorization': f'Basic {auth}'}
page_size = 500

# Date range configuration
start_date_str = args.start_date if args.start_date else '2000-01-01'
end_date_str = args.end_date if args.end_date else datetime.now().strftime('%Y-%m-%d')

try:
    start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
    end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
except ValueError as e:
    print(f"❌ Invalid date format: {e}")
    print("💡 Use format: YYYY-MM-DD (e.g., 2000-01-01)")
    exit(1)

if start_date >= end_date:
    print("❌ Error: Start date must be before end date")
    exit(1)

delta = timedelta(days=30)
current_start_date = start_date
all_issues = []

# Output file configuration
if args.output:
    csv_file = args.output if args.output.endswith('.csv') else f"{args.output}.csv"
else:
    csv_file = 'sonarqube_issues.csv'

# If user wants xlsx, we'll still write to CSV first, then convert
if args.format == 'xlsx':
    xlsx_file = csv_file.replace('.csv', '.xlsx')
    print(f"📝 Note: Writing to CSV first for memory efficiency, will convert to Excel at the end")

chunk_size = 5000
write_mode = 'w'
total_issues_count = 0

print(f"🚀 Starting export...")
print(f"📅 Date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
print(f"🎯 Project: {PROJECT_KEY}")
if args.severities:
    print(f"🔍 Severities: {args.severities}")
if args.types:
    print(f"🔍 Types: {args.types}")
if args.statuses:
    print(f"🔍 Statuses: {args.statuses}")
print()

while current_start_date < end_date:
    current_end_date = current_start_date + delta
    if current_end_date > end_date:
        current_end_date = end_date

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
            response = requests.get(SONARQUBE_URL, headers=headers, params=params, timeout=30)

            if response.status_code == 200:
                try:
                    data = response.json()
                    issues = data.get('issues', [])

                    if issues:
                        all_issues.extend(issues)
                        total_issues_count += len(issues)
                        print(f"   📄 Page {params['p']}: {len(issues)} issues ({total_issues_count} total so far)")

                    # Write to file in chunks to save memory
                    if len(all_issues) >= chunk_size:
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
                    print(f'❌ Failed to parse JSON response: {e}')
                    print(f'Response content: {response.text}')
                    break
            else:
                if response.status_code == 401:
                    print('❌ Authentication failed. Check your TOKEN.')
                elif response.status_code == 404:
                    print('❌ Project not found. Check your PROJECT_KEY and SONARQUBE_URL.')
                elif response.status_code == 403:
                    print('❌ Access denied. Check project permissions.')
                else:
                    print(f'❌ API request failed with status {response.status_code}')
                print(f'Response: {response.text}')
                break

        except requests.exceptions.Timeout:
            print('❌ Connection timed out. Check your network or try again later.')
            break
        except requests.exceptions.ConnectionError:
            print('❌ Connection error. Check your network and SONARQUBE_URL.')
            break
        except Exception as e:
            print(f'❌ Unexpected error: {e}')
            break

    current_start_date = current_end_date

# Write any remaining issues
if all_issues:
    print(f"💾 Writing final chunk of {len(all_issues)} issues to CSV...")
    write_chunk_to_csv(csv_file, all_issues, write_mode)

if total_issues_count > 0:
    print(f'\n✅ CSV Export completed: {total_issues_count} issues exported to {csv_file}')
    print(f'📊 Date range: {start_date.strftime("%Y-%m-%d")} to {end_date.strftime("%Y-%m-%d")}')

    # Convert to Excel if requested
    if args.format == 'xlsx':
        convert_csv_to_excel(csv_file, xlsx_file)
        print(f'\n✅ Final output: {xlsx_file}')
    else:
        print(f'\n✅ Final output: {csv_file}')
else:
    print('❌ No issues found.')
