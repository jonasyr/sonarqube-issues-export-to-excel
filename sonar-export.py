import pandas as pd
import requests
import base64
import os
from datetime import datetime, timedelta

# SonarQube parameters
SONARQUBE_URL = os.getenv('SONAR_URL', 'http://localhost:9000/api/issues/search') #Sonar Instance URL
PROJECT_KEY = os.getenv('SONAR_PROJECT_KEY', '') #Your Project Key
TOKEN = os.getenv('SONAR_TOKEN', '') #Your Project Token

# Add basic input validation
if not PROJECT_KEY or not TOKEN:
    print("Error: PROJECT_KEY and TOKEN must be configured")
    exit(1)

# Fetch issues from SonarQube
auth = base64.b64encode(f'{TOKEN}:'.encode()).decode()
headers = {'Authorization': f'Basic {auth}'}
page_size = 500  # Page size, maximum allowed by SonarQube

# Adjust date ranges as necessary to ensure each range returns less than 10,000 issues
start_date = datetime(2000, 1, 1)  # Example start date
end_date = datetime.now()  # Current date and time
delta = timedelta(days=30)  # Adjust the range to ensure < 10,000 results

current_start_date = start_date
all_issues = []

while current_start_date < end_date:
    current_end_date = current_start_date + delta
    if current_end_date > end_date:
        current_end_date = end_date
        
    print(f"Fetching issues from {current_start_date.strftime('%Y-%m-%d')} to {current_end_date.strftime('%Y-%m-%d')}...")

    params = { #Adjust as required
        'componentKeys': PROJECT_KEY,
        'createdAfter': current_start_date.strftime('%Y-%m-%d'),
        'createdBefore': current_end_date.strftime('%Y-%m-%d'),
        'ps': page_size,
        'p': 1
    }

    while True:
        try:
            response = requests.get(SONARQUBE_URL, headers=headers, params=params, timeout=30)
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    issues = data.get('issues', [])
                    all_issues.extend(issues)
                    
                    # Check if there are more pages
                    if len(issues) < page_size:
                        break  # No more pages
                    else:
                        params['p'] += 1  # Next page
                except requests.exceptions.JSONDecodeError as e:
                    print('Failed to parse JSON response:', e)
                    print('Response content:', response.text)
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
                print('Response content:', response.text)
                break
        except requests.exceptions.Timeout:
            print('❌ Connection timed out. Check your network or try again later.')
            break
        except requests.exceptions.ConnectionError:
            print('❌ Connection error. Check your network and SONARQUBE_URL.')
            break
        except Exception as e:
            print(f'❌ Unexpected error occurred: {e}')
            break
            
    current_start_date = current_end_date
    print(f"Found {len(all_issues)} issues so far...")

if all_issues:
    # Convert to DataFrame
    df = pd.DataFrame(all_issues)
    # Save to Excel
    df.to_excel('sonarqube_issues.xlsx', index=False)
    print(f'✅ Export completed: {len(all_issues)} issues exported to sonarqube_issues.xlsx')
    print(f'📊 Date range: {start_date.strftime("%Y-%m-%d")} to {end_date.strftime("%Y-%m-%d")}')
else:
    print('No issues found.')
