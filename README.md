
# SonarQube Issues Export

This Python script fetches issues from a SonarQube project and exports them to CSV or Excel format. It uses the SonarQube REST API and handles pagination, date ranges, and chunked writing to efficiently retrieve and export large numbers of issues.

**Compatible with both local SonarQube instances (localhost:9000) and SonarCloud.**

## Prerequisites

- Python 3.x
- `requests`, `pandas`, `openpyxl` library
- Access to a SonarQube instance with an appropriate token

## Installation

1. Clone the repository:

```bash
git clone https://github.com/talha2k/sonarqube-issues-export-to-excel.git
cd sonarqube-issues-export-to-excel
```

2. Install the required Python libraries:

```bash
pip install requests pandas openpyxl
```

## Configuration

Configure the script using environment variables. The script works with both local SonarQube instances and SonarCloud.

### For Local SonarQube Instance (default)

```bash
export SONAR_URL='http://localhost:9000/api/issues/search'   # Local SonarQube instance
export SONAR_PROJECT_KEY='your-project-key'                  # Your project key
export SONAR_TOKEN='your-authentication-token'               # Your authentication token
```

### For SonarCloud

```bash
export SONAR_URL='https://sonarcloud.io/api/issues/search'   # SonarCloud instance
export SONAR_PROJECT_KEY='your-project-key'                  # Your project key
export SONAR_TOKEN='your-authentication-token'               # Your authentication token
```

Alternatively, you can edit these values directly in the script.

## Usage

### Basic Usage

```bash
# Export to CSV (default, recommended)
python sonar-export.py

# Export to Excel
python sonar-export.py --format xlsx
```

### Export Options

The script supports various command-line arguments for customization:

```bash
python sonar-export.py [OPTIONS]

Options:
  --format {csv,xlsx}        Output format (default: csv)
  --output, -o FILENAME      Custom output filename
  --start-date YYYY-MM-DD    Start date for issue retrieval (default: 2000-01-01)
  --end-date YYYY-MM-DD      End date for issue retrieval (default: today)
  --severities SEVERITIES    Filter by severities (comma-separated)
  --types TYPES              Filter by issue types (comma-separated)
  --statuses STATUSES        Filter by statuses (comma-separated)
```

## Advanced Usage Examples

### Export ALL historical issues (default behavior)
```bash
python sonar-export.py
# This exports all issues from 2000-01-01 to today
```

### Export only recent issues
```bash
# Only issues from 2025
python sonar-export.py --start-date 2025-01-01

# Last 30 days (Linux/Mac)
python sonar-export.py --start-date $(date -d '30 days ago' +%Y-%m-%d)

# Custom date range
python sonar-export.py --start-date 2024-01-01 --end-date 2024-12-31
```

### Filter by severity and type
```bash
# Only critical bugs
python sonar-export.py --severities BLOCKER,CRITICAL --types BUG

# Only open code smells
python sonar-export.py --types CODE_SMELL --statuses OPEN,CONFIRMED

# High severity issues only
python sonar-export.py --severities BLOCKER,CRITICAL,MAJOR
```

### Custom output filename
```bash
python sonar-export.py --output my_project_issues_2025.csv

# Excel format with custom name
python sonar-export.py --format xlsx --output critical_bugs
```

### Complete workflow for large projects
```bash
# Step 1: Export to CSV (memory efficient, recommended for large projects)
export SONAR_URL='https://sonarcloud.io/api/issues/search'
export SONAR_PROJECT_KEY='my-large-project'
export SONAR_TOKEN='your-token'

python sonar-export.py --format csv --output all_issues

# Step 2: If you need Excel, specify xlsx format
# The script will create CSV first, then convert
python sonar-export.py --format xlsx --output all_issues
```

## Features

- **Multiple Export Formats**: Export to CSV (default, recommended) or Excel (XLSX) format
- **CSV-First Strategy**: For Excel exports, creates CSV first then converts (better memory management)
- **Flexible Date Filtering**: Customize start and end dates for export
- **Issue Filtering**: Filter by severity, type, and status
- **Chunked Writing**: Writes data in chunks (every 5000 issues) to minimize memory usage for large exports
- **Date Range Handling**: Automatically splits requests into date ranges to handle SonarQube's 10,000 result limit
- **Pagination Support**: Handles pagination to fetch all issues within each date range
- **Comprehensive Error Handling**: Includes specific error messages for common issues:
  - Authentication failures (401)
  - Project not found (404)
  - Access denied (403)
  - Connection timeouts
  - Network errors
- **Environment Variable Support**: Configure via environment variables for better security
- **Progress Reporting**: Shows real-time progress during export

## Performance Recommendations

### For Large Projects (>50,000 issues)
- **Always use CSV format** for initial export (better memory management)
- Use **date filtering** to reduce scope: `--start-date 2024-01-01`
- Apply **severity/type filters** to reduce data volume
- Consider **incremental exports** (export by year or quarter)

Example for very large project:
```bash
# Export by year
for year in 2020 2021 2022 2023 2024 2025; do
  python sonar-export.py \
    --start-date ${year}-01-01 \
    --end-date ${year}-12-31 \
    --output issues_${year}.csv
done
```

### Memory Considerations
The script uses **chunked writing** (5000 issues per chunk) to minimize memory usage.
For projects with millions of issues:
- CSV format uses ~1-2 GB RAM
- Excel conversion may require 2-4x the CSV file size in RAM

## Customization

You can customize the date range and other parameters by editing the script:

- `start_date`: Start date for issue retrieval (default: 2000-01-01 to export ALL historical issues)
- `end_date`: End date (default: current date)
- `delta`: Date range chunk size (default: 30 days)
- `chunk_size`: How often data is written to disk (default: 5000 issues)

**Note**: The default configuration exports ALL issues from 2000 onwards. For large projects with many issues, you may want to adjust the start date or use filtering options to reduce the export scope.

### Example: Export only recent issues

To export only issues from this year, modify the script or use command-line arguments:
```bash
python sonar-export.py --start-date 2025-01-01
```

## Example Output

### Using Local SonarQube Instance

```bash
# Set up environment variables for local instance
export SONAR_URL='http://localhost:9000/api/issues/search'
export SONAR_PROJECT_KEY='my-project'
export SONAR_TOKEN='your-token-here'

# Export to CSV (default, recommended)
python sonar-export.py
```

### Using SonarCloud

```bash
# Set up environment variables for SonarCloud
export SONAR_URL='https://sonarcloud.io/api/issues/search'
export SONAR_PROJECT_KEY='my-project'
export SONAR_TOKEN='your-token-here'

# Export with filters
python sonar-export.py --severities BLOCKER,CRITICAL --start-date 2025-01-01
```

Example output:
```
🚀 Starting export...
📅 Date range: 2000-01-01 to 2025-11-13
🎯 Project: my-project

📥 Fetching issues from 2000-01-01 to 2000-01-31...
   📄 Page 1: 500 issues (500 total so far)
   📄 Page 2: 234 issues (734 total so far)
📥 Fetching issues from 2000-01-31 to 2000-03-01...
   📄 Page 1: 500 issues (1234 total so far)
...
💾 Writing chunk of 5000 issues to CSV...
...
✅ CSV Export completed: 7891 issues exported to sonarqube_issues.csv
📊 Date range: 2000-01-01 to 2025-11-13

✅ Final output: sonarqube_issues.csv
```

## Available Filters

### Severities
- `BLOCKER` - Blocker issues
- `CRITICAL` - Critical issues
- `MAJOR` - Major issues
- `MINOR` - Minor issues
- `INFO` - Informational issues

### Types
- `BUG` - Bugs
- `VULNERABILITY` - Security vulnerabilities
- `CODE_SMELL` - Code smells
- `SECURITY_HOTSPOT` - Security hotspots

### Statuses
- `OPEN` - Open issues
- `CONFIRMED` - Confirmed issues
- `REOPENED` - Reopened issues
- `RESOLVED` - Resolved issues
- `CLOSED` - Closed issues

## License

This project is licensed under the MIT License.
