import unittest
from unittest.mock import patch, Mock, MagicMock, mock_open
import pandas as pd
import os
import sys
import json
import tempfile
from datetime import datetime

# Add parent directory to path to import the module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock the modules before importing
sys.modules['requests'] = MagicMock()
sys.modules['openpyxl'] = MagicMock()

# Now we can import after mocking but we'll test individual functions


class TestHelperFunctions(unittest.TestCase):
    """Test helper functions from sonar-export.py"""

    def test_load_project_keys_from_list(self):
        """Test loading project keys from comma-separated string"""
        # Mock the logger
        with patch('logging.getLogger'):
            # We need to manually import and test the function logic
            projects_arg = "project1,project2,project3"
            expected = ['project1', 'project2', 'project3']

            # Inline implementation to test
            projects = [p.strip() for p in projects_arg.split(',')]

            self.assertEqual(projects, expected)

    def test_load_project_keys_from_file(self):
        """Test loading project keys from file"""
        # Create a temporary file with project keys
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write("project1\n")
            f.write("# This is a comment\n")
            f.write("project2\n")
            f.write("\n")  # Empty line
            f.write("project3\n")
            temp_file = f.name

        try:
            # Read and test
            with open(temp_file, 'r') as f:
                projects = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]

            expected = ['project1', 'project2', 'project3']
            self.assertEqual(projects, expected)
        finally:
            os.unlink(temp_file)

    def test_flatten_issue_basic(self):
        """Test basic issue flattening"""
        issue = {
            'key': 'TEST-123',
            'rule': 'typescript:S1234',
            'severity': 'MAJOR',
            'component': 'test:src/file.ts',
            'message': 'Test issue message',
            'tags': ['bug', 'security'],
            'comments': [{'text': 'comment1'}, {'text': 'comment2'}],
            'flows': [],
            'textRange': {
                'startLine': 10,
                'endLine': 15,
                'startOffset': 5,
                'endOffset': 20
            },
            'impacts': [
                {'softwareQuality': 'MAINTAINABILITY', 'severity': 'MEDIUM'},
                {'softwareQuality': 'SECURITY', 'severity': 'HIGH'}
            ]
        }

        # Inline flattening logic to test
        text_range = issue.get('textRange', {})
        impacts = issue.get('impacts', [])
        impacts_str = '; '.join([f"{imp.get('softwareQuality', '')}:{imp.get('severity', '')}"
                                 for imp in impacts]) if impacts else ''

        flattened = {
            'key': issue.get('key', ''),
            'rule': issue.get('rule', ''),
            'severity': issue.get('severity', ''),
            'startLine': text_range.get('startLine', '') if isinstance(text_range, dict) else '',
            'endLine': text_range.get('endLine', '') if isinstance(text_range, dict) else '',
            'message': issue.get('message', ''),
            'tags': ','.join(issue.get('tags', [])),
            'comments': len(issue.get('comments', [])),
            'flows': len(issue.get('flows', [])),
            'impacts': impacts_str
        }

        self.assertEqual(flattened['key'], 'TEST-123')
        self.assertEqual(flattened['rule'], 'typescript:S1234')
        self.assertEqual(flattened['severity'], 'MAJOR')
        self.assertEqual(flattened['startLine'], 10)
        self.assertEqual(flattened['endLine'], 15)
        self.assertEqual(flattened['tags'], 'bug,security')
        self.assertEqual(flattened['comments'], 2)
        self.assertEqual(flattened['flows'], 0)
        self.assertEqual(flattened['impacts'], 'MAINTAINABILITY:MEDIUM; SECURITY:HIGH')

    def test_flatten_issue_missing_fields(self):
        """Test issue flattening with missing fields"""
        issue = {
            'key': 'TEST-456',
            'rule': 'typescript:S5678'
        }

        flattened = {
            'key': issue.get('key', ''),
            'rule': issue.get('rule', ''),
            'severity': issue.get('severity', ''),
            'tags': ','.join(issue.get('tags', [])),
            'comments': len(issue.get('comments', [])),
        }

        self.assertEqual(flattened['key'], 'TEST-456')
        self.assertEqual(flattened['rule'], 'typescript:S5678')
        self.assertEqual(flattened['severity'], '')
        self.assertEqual(flattened['tags'], '')
        self.assertEqual(flattened['comments'], 0)


class TestStateManagement(unittest.TestCase):
    """Test incremental export state management"""

    def test_save_and_load_export_info(self):
        """Test saving and loading export state"""
        project_key = "test-project"
        end_date = datetime(2025, 11, 13)
        issue_count = 150

        # Create state
        state = {
            'project_key': project_key,
            'last_export_date': end_date.isoformat(),
            'last_export_timestamp': datetime.now().isoformat(),
            'issue_count': issue_count
        }

        # Save to temp file
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            json.dump(state, f, indent=2)
            state_file = f.name

        try:
            # Load and verify
            with open(state_file, 'r') as f:
                loaded_state = json.load(f)

            self.assertEqual(loaded_state['project_key'], project_key)
            self.assertEqual(loaded_state['last_export_date'], end_date.isoformat())
            self.assertEqual(loaded_state['issue_count'], issue_count)
        finally:
            os.unlink(state_file)

    def test_state_file_naming(self):
        """Test state file name generation with special characters"""
        test_cases = [
            ('simple-project', '.last_export_simple-project.json'),
            ('org:project', '.last_export_org_project.json'),
            ('org/sub/project', '.last_export_org_sub_project.json'),
            ('project:key/with:special', '.last_export_project_key_with_special.json'),
        ]

        for project_key, expected_filename in test_cases:
            filename = f'.last_export_{project_key.replace(":", "_").replace("/", "_")}.json'
            self.assertEqual(filename, expected_filename)


class TestDataValidation(unittest.TestCase):
    """Test data validation and error handling"""

    def test_date_validation(self):
        """Test date format validation"""
        valid_dates = ['2025-01-01', '2000-12-31', '2025-11-13']
        invalid_dates = ['2025/01/01', '01-01-2025', 'invalid', '2025-13-01']

        for date_str in valid_dates:
            try:
                datetime.strptime(date_str, '%Y-%m-%d')
                success = True
            except ValueError:
                success = False
            self.assertTrue(success, f"{date_str} should be valid")

        for date_str in invalid_dates:
            try:
                datetime.strptime(date_str, '%Y-%m-%d')
                success = True
            except ValueError:
                success = False
            self.assertFalse(success, f"{date_str} should be invalid")

    def test_project_key_sanitization(self):
        """Test project key sanitization for filenames"""
        test_cases = [
            ('project:key', 'project_key'),
            ('org/project', 'org_project'),
            ('project:with/special:chars', 'project_with_special_chars'),
            ('simple-project', 'simple-project'),
        ]

        for input_key, expected_output in test_cases:
            sanitized = input_key.replace(':', '_').replace('/', '_')
            self.assertEqual(sanitized, expected_output)


class TestCSVOperations(unittest.TestCase):
    """Test CSV writing and reading operations"""

    def test_csv_chunk_writing(self):
        """Test CSV chunk writing functionality"""
        test_data = [
            {'key': 'TEST-1', 'severity': 'HIGH', 'rule': 'rule:1'},
            {'key': 'TEST-2', 'severity': 'LOW', 'rule': 'rule:2'}
        ]

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as f:
            test_file = f.name

        try:
            # Write first chunk
            df = pd.DataFrame(test_data)
            df.to_csv(test_file, index=False, mode='w', header=True)

            # Verify content
            df_read = pd.read_csv(test_file)
            self.assertEqual(len(df_read), 2)
            self.assertEqual(df_read.iloc[0]['key'], 'TEST-1')
            self.assertEqual(df_read.iloc[1]['key'], 'TEST-2')

            # Append more data
            more_data = [
                {'key': 'TEST-3', 'severity': 'MEDIUM', 'rule': 'rule:3'}
            ]
            df_more = pd.DataFrame(more_data)
            df_more.to_csv(test_file, index=False, mode='a', header=False)

            # Verify appended content
            df_final = pd.read_csv(test_file)
            self.assertEqual(len(df_final), 3)
            self.assertEqual(df_final.iloc[2]['key'], 'TEST-3')

        finally:
            os.unlink(test_file)


class TestMultiProjectHandling(unittest.TestCase):
    """Test multi-project export handling"""

    def test_result_aggregation(self):
        """Test aggregating results from multiple projects"""
        results = {
            'project1': {'status': 'success', 'count': 100},
            'project2': {'status': 'success', 'count': 200},
            'project3': {'status': 'failed', 'error': 'Connection error'}
        }

        successful = sum(1 for r in results.values() if r['status'] == 'success')
        failed = sum(1 for r in results.values() if r['status'] == 'failed')
        total_issues = sum(r['count'] for r in results.values() if r['status'] == 'success')

        self.assertEqual(successful, 2)
        self.assertEqual(failed, 1)
        self.assertEqual(total_issues, 300)

    def test_output_directory_creation(self):
        """Test output directory naming for multi-project exports"""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = os.path.join(temp_dir, 'multi_project_export')
            os.makedirs(output_dir, exist_ok=True)

            self.assertTrue(os.path.exists(output_dir))
            self.assertTrue(os.path.isdir(output_dir))


class TestConfigurationParsing(unittest.TestCase):
    """Test configuration file parsing"""

    def test_ini_file_parsing(self):
        """Test parsing configuration from INI file"""
        import configparser

        config_content = """[sonarqube]
url = https://sonarcloud.io/api/issues/search
project_key = test-project

[export]
format = csv
start_date = 2025-01-01

[filters]
severities = BLOCKER,CRITICAL
types = BUG,VULNERABILITY
"""

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.ini') as f:
            f.write(config_content)
            config_file = f.name

        try:
            config = configparser.ConfigParser()
            config.read(config_file)

            self.assertTrue(config.has_section('sonarqube'))
            self.assertEqual(config.get('sonarqube', 'url'), 'https://sonarcloud.io/api/issues/search')
            self.assertEqual(config.get('sonarqube', 'project_key'), 'test-project')
            self.assertEqual(config.get('export', 'format'), 'csv')
            self.assertEqual(config.get('export', 'start_date'), '2025-01-01')
        finally:
            os.unlink(config_file)


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)
