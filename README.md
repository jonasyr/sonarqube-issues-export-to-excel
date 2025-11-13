# SonarQube Issues Export

<div align="center">

![Python Version](https://img.shields.io/badge/python-3.8%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Platform](https://img.shields.io/badge/platform-linux%20%7C%20macos%20%7C%20windows-lightgrey)
![SonarQube](https://img.shields.io/badge/SonarQube-%E2%9C%93-success)
![SonarCloud](https://img.shields.io/badge/SonarCloud-%E2%9C%93-success)

**A powerful, production-ready tool to export SonarQube/SonarCloud issues to CSV or Excel with advanced features like incremental exports, multi-project support, and comprehensive logging.**

[Features](#features) •
[Quick Setup](#quick-setup) •
[Documentation](#detailed-documentation) •
[Examples](#usage-examples) •
[Testing](#testing)

</div>

---

## Table of Contents

- [Quick Setup](#quick-setup)
- [Features](#features)
- [Detailed Documentation](#detailed-documentation)
  - [Installation](#installation)
  - [Configuration](#configuration)
  - [Command-Line Options](#command-line-options)
- [Usage Examples](#usage-examples)
  - [Basic Export](#basic-export)
  - [Date Filtering](#date-filtering)
  - [Issue Filtering](#issue-filtering)
  - [Incremental Exports](#incremental-exports)
  - [Multi-Project Exports](#multi-project-exports)
  - [Configuration Files](#configuration-files)
  - [Summary Reports](#summary-reports)
- [Output Files](#output-files)
- [Performance Recommendations](#performance-recommendations)
- [Filter Reference](#filter-reference)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)
- [License](#license)

---

## Quick Setup

Get started in under 1 minute:

```bash
# 1. Clone and install
git clone https://github.com/talha2k/sonarqube-issues-export-to-excel.git
cd sonarqube-issues-export-to-excel
pip install -r requirements.txt

# 2. Set environment variables
export SONAR_URL='https://sonarcloud.io/api/issues/search'  # or your SonarQube URL
export SONAR_PROJECT_KEY='your-project-key'
export SONAR_TOKEN='your-token'

# 3. Run export
python sonar-export.py
```

That's it! Your issues are now in `sonarqube_issues.csv` ✨

---

## Features

###  Core Export Capabilities
- **Multiple Export Formats**: CSV (default, recommended) or Excel (XLSX)
- **CSV-First Strategy**: Creates CSV first, then optionally converts to Excel for better memory management
- **Flexible Date Filtering**: Customize start and end dates
- **Advanced Filtering**: Filter by severity, type, and status
- **Chunked Writing**: Processes 5000 issues per chunk to minimize memory usage
- **Automatic Pagination**: Handles SonarQube's 10,000 result limit automatically
- **Both Platforms**: Works with SonarQube (localhost:9000) and SonarCloud

###  Data Quality & Analysis
- **Data Flattening**: Automatically flattens nested JSON (textRange, impacts) into 35+ columns
- **Summary Reports**: Generate statistical summaries with `--summary` flag
  - Issues breakdown by severity, type, and status with percentages
  - Top 10 most common rules
  - Date range statistics
- **Clean Column Structure**: All SonarQube fields extracted and formatted for easy analysis

###  Enterprise Features (Phase 3)
- **Multi-Project Support**: Export from multiple projects in one command
  - Comma-separated list: `--projects project1,project2,project3`
  - From file: `--projects @projects.txt`
  - Consolidated summary report (JSON)
- **Incremental Exports**: Only export new issues since last export
  - Automatic state tracking per project
  - Perfect for daily/weekly automated exports
  - Saves time and bandwidth
- **Unit Tests**: Comprehensive test suite with 12+ unit tests

###  Reliability & Debugging
- **Automatic Retry Logic**: Exponential backoff for transient failures (429, 500, 502, 503, 504)
- **Comprehensive Logging**: Timestamped logs to both console and file
- **Configurable Log Levels**: DEBUG, INFO, WARNING, ERROR
- **Detailed Error Messages**: Specific guidance for common issues (401, 403, 404, timeouts)

###  Configuration & Flexibility
- **Environment Variables**: Secure credential management
- **Configuration Files**: Reusable INI-based configurations
- **Priority System**: ENV vars > CLI args > config file > defaults
- **Real-time Progress**: Live progress reporting during export

---

## Detailed Documentation

### Installation

**Prerequisites:**
- Python 3.8 or higher
- Access to a SonarQube instance or SonarCloud with a valid token

**Install Dependencies:**

```bash
pip install -r requirements.txt
```

Or manually:

```bash
pip install requests==2.32.5 pandas==2.3.3 openpyxl==3.1.5
```

### Configuration

#### Environment Variables (Recommended)

```bash
# For SonarCloud
export SONAR_URL='https://sonarcloud.io/api/issues/search'
export SONAR_PROJECT_KEY='your-project-key'
export SONAR_TOKEN='your-authentication-token'

# For Local SonarQube
export SONAR_URL='http://localhost:9000/api/issues/search'
export SONAR_PROJECT_KEY='your-project-key'
export SONAR_TOKEN='your-authentication-token'
```

#### Configuration File (Optional)

Create `config.ini` (see `config.ini.example` for template):

```ini
[sonarqube]
url = https://sonarcloud.io/api/issues/search
project_key = my-project

[export]
format = csv
start_date = 2024-01-01

[filters]
severities = BLOCKER,CRITICAL
types = BUG,VULNERABILITY
```

### Command-Line Options

```
python sonar-export.py [OPTIONS]

Export Options:
  --format {csv,xlsx}             Output format (default: csv)
  --output, -o FILENAME           Custom output filename
  --start-date YYYY-MM-DD         Start date (default: 2000-01-01)
  --end-date YYYY-MM-DD           End date (default: today)

Filtering Options:
  --severities SEVERITIES         Filter by severity (comma-separated)
  --types TYPES                   Filter by issue type (comma-separated)
  --statuses STATUSES             Filter by status (comma-separated)

Advanced Features:
  --projects PROJECTS             Multi-project export (comma-separated or @file.txt)
  --incremental                   Export only new issues since last export
  --summary                       Generate summary report after export
  --config CONFIG_FILE            Path to configuration file
  --log-level {DEBUG,INFO,WARNING,ERROR}  Logging verbosity (default: INFO)
```

---

## Usage Examples

### Basic Export

```bash
# Export all issues to CSV (default, recommended)
python sonar-export.py

# Export to Excel
python sonar-export.py --format xlsx

# Custom filename
python sonar-export.py --output my_issues
```

### Date Filtering

```bash
# Export ALL historical issues (default)
python sonar-export.py
# Exports from 2000-01-01 to today

# Only recent issues
python sonar-export.py --start-date 2025-01-01

# Specific date range
python sonar-export.py --start-date 2024-01-01 --end-date 2024-12-31

# Last 30 days (Linux/Mac)
python sonar-export.py --start-date $(date -d '30 days ago' +%Y-%m-%d)
```

### Issue Filtering

```bash
# Only critical bugs
python sonar-export.py --severities BLOCKER,CRITICAL --types BUG

# Only open code smells
python sonar-export.py --types CODE_SMELL --statuses OPEN,CONFIRMED

# High severity issues
python sonar-export.py --severities BLOCKER,CRITICAL,MAJOR
```

### Incremental Exports

Perfect for automated daily/weekly exports - only fetches new issues since last run:

```bash
# First run: exports all issues and saves state
python sonar-export.py --incremental

# Second run: only exports new issues since first run
python sonar-export.py --incremental

# Combine with other options
python sonar-export.py --incremental --severities BLOCKER,CRITICAL --summary
```

**How it works:**
- First run creates `.last_export_PROJECT.json` with export timestamp
- Subsequent runs only fetch issues created after last export date
- Saves bandwidth and time for large projects
- Each project has its own state file

### Multi-Project Exports

Export from multiple projects in a single command:

```bash
# Comma-separated list
python sonar-export.py --projects project1,project2,project3

# From file (one project per line, # for comments)
cat > projects.txt <<EOF
# Production projects
prod-frontend
prod-backend
# Development projects
dev-app
EOF

python sonar-export.py --projects @projects.txt

# With filters and custom output directory
python sonar-export.py --projects @projects.txt \
  --start-date 2025-01-01 \
  --severities BLOCKER,CRITICAL \
  --output my_exports

# Multi-project + incremental (perfect for automation!)
python sonar-export.py --projects @projects.txt --incremental --summary
```

**Output structure:**
```
my_exports/
  ├── project1_issues.csv
  ├── project2_issues.csv
  ├── project3_issues.csv
  └── export_summary.json
```

### Configuration Files

```bash
# Create config file
cp config.ini.example config.ini
nano config.ini

# Use config file
python sonar-export.py --config config.ini

# CLI args override config values
python sonar-export.py --config config.ini --start-date 2025-01-01 --summary
```

### Summary Reports

```bash
# Generate statistical summary
python sonar-export.py --summary

# Creates:
# - sonarqube_issues.csv (main export)
# - export_summary.txt (statistical breakdown)
```

Example summary output:
```
============================================================
SONARQUBE EXPORT SUMMARY REPORT
============================================================

Generated: 2025-11-13 23:22:09
Project: gitray-dev
Total Issues: 110

------------------------------------------------------------
BY SEVERITY
------------------------------------------------------------
  MINOR             105 ( 95.5%)
  MAJOR               4 (  3.6%)
  INFO                1 (  0.9%)

------------------------------------------------------------
TOP 10 RULES
------------------------------------------------------------
   1. typescript:S7748                                  29
   2. typescript:S7772                                  24
...
```

---

## Output Files

### Always Generated
- **CSV/Excel Export**: `sonarqube_issues.csv` or `sonarqube_issues.xlsx` (or custom name via `--output`)
- **Log File**: `sonar_export_YYYYMMDD_HHMMSS.log` - Detailed execution log with timestamps

### Optional Outputs
- **Summary Report**: `export_summary.txt` - Statistical breakdown (with `--summary`)
- **State Files**: `.last_export_PROJECT.json` - Incremental export tracking (with `--incremental`)
- **Multi-Project Summary**: `export_summary.json` - Consolidated results (with `--projects`)

### Log Levels

Control verbosity with `--log-level`:
- **DEBUG**: Detailed diagnostic information
- **INFO**: Confirmation of expected behavior (default)
- **WARNING**: Unexpected events that don't prevent execution
- **ERROR**: Serious problems preventing some functionality

```bash
python sonar-export.py --log-level DEBUG --summary
```

---

## Performance Recommendations

### For Large Projects (>50,000 issues)
- ✅ **Always use CSV format** for initial export (better memory management)
- ✅ Use **date filtering** to reduce scope: `--start-date 2024-01-01`
- ✅ Apply **severity/type filters** to reduce data volume
- ✅ Consider **incremental exports** for regular updates
- ✅ Use **multi-project** mode to batch multiple projects efficiently

### Memory Considerations
The script uses **chunked writing** (5000 issues per chunk) to minimize memory:
- CSV format: ~1-2 GB RAM for millions of issues
- Excel conversion: 2-4x the CSV file size in RAM

### Large-Scale Export Example

```bash
# Export by year for very large projects
for year in 2020 2021 2022 2023 2024 2025; do
  python sonar-export.py \
    --start-date ${year}-01-01 \
    --end-date ${year}-12-31 \
    --output issues_${year}.csv
done
```

---

## Filter Reference

### Severities
- `BLOCKER` - Blocker issues (must fix immediately)
- `CRITICAL` - Critical issues (high priority)
- `MAJOR` - Major issues (medium priority)
- `MINOR` - Minor issues (low priority)
- `INFO` - Informational issues

### Types
- `BUG` - Bugs (functional errors)
- `VULNERABILITY` - Security vulnerabilities
- `CODE_SMELL` - Code quality/maintainability issues
- `SECURITY_HOTSPOT` - Security review required

### Statuses
- `OPEN` - Open issues (not yet reviewed)
- `CONFIRMED` - Confirmed issues
- `REOPENED` - Reopened after being closed
- `RESOLVED` - Resolved (fixed or accepted)
- `CLOSED` - Closed issues

---

## Testing

The project includes comprehensive unit tests:

```bash
# Run all tests
python -m unittest discover tests/ -v

# Or with pytest (if installed)
pytest tests/ -v

# Run specific test file
python -m unittest tests.test_sonar_export -v
```

**Test Coverage:**
- ✅ Data flattening and transformation
- ✅ CSV chunked writing
- ✅ Multi-project handling
- ✅ State management (incremental exports)
- ✅ Configuration file parsing
- ✅ Date validation
- ✅ Project key sanitization

---

## Troubleshooting

### Common Issues

**Authentication Error (401)**
```bash
# Check your token
echo $SONAR_TOKEN

# Regenerate token in SonarQube/SonarCloud and update
export SONAR_TOKEN='new-token-here'
```

**Project Not Found (404)**
```bash
# Verify project key
# In SonarQube: Project Settings → General Settings → Project Key
export SONAR_PROJECT_KEY='correct-project-key'
```

**No Issues Found**
- Check date range (default: 2000-01-01 to today)
- Remove filters to see all issues
- Verify project has issues in SonarQube UI

**Memory Issues with Large Exports**
- Use CSV format instead of Excel
- Apply date or severity filters
- Export by time periods (monthly/quarterly)

### Debug Mode

Enable detailed logging for troubleshooting:

```bash
python sonar-export.py --log-level DEBUG --output debug_export
```

Check the log file: `sonar_export_YYYYMMDD_HHMMSS.log`

---

## Examples for Specific Use Cases

### Daily Automated Export (Cron/Scheduled Task)

```bash
#!/bin/bash
# daily_export.sh

export SONAR_URL='https://sonarcloud.io/api/issues/search'
export SONAR_TOKEN='your-token'
export SONAR_PROJECT_KEY='your-project'

# Incremental export with summary
python sonar-export.py \
  --incremental \
  --summary \
  --output "daily_export_$(date +%Y%m%d)"
```

### Weekly Multi-Project Report

```bash
#!/bin/bash
# weekly_report.sh

export SONAR_URL='https://sonarcloud.io/api/issues/search'
export SONAR_TOKEN='your-token'

python sonar-export.py \
  --projects @production_projects.txt \
  --incremental \
  --severities BLOCKER,CRITICAL \
  --summary \
  --output "weekly_report_$(date +%Y%m%d)"
```

### One-Time Historical Analysis

```bash
# Export all issues for analysis
python sonar-export.py \
  --start-date 2020-01-01 \
  --summary \
  --output historical_analysis

# Then analyze in Excel/Python/R
```

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

---

<div align="center">

**Made with ❤️ for the SonarQube community**

[Report Bug](https://github.com/talha2k/sonarqube-issues-export-to-excel/issues) •
[Request Feature](https://github.com/talha2k/sonarqube-issues-export-to-excel/issues)

</div>
