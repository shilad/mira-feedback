"""Accuracy testing for PII detection."""

import yaml
from pathlib import Path
from typing import Dict, List, Any
from collections import defaultdict

from shilads_helpers.libs.local_anonymizer import LocalAnonymizer
from shilads_helpers.libs.config_loader import load_all_configs, get_config


class AccuracyMetrics:
    """Calculate and report accuracy metrics for PII detection."""
    
    def calculate_precision_recall_f1(self, expected: List[str], detected: List[str]) -> Dict[str, float]:
        """Calculate precision, recall, and F1 score for a set of items."""
        expected_set = set(expected)
        detected_set = set(detected)
        
        true_positives = len(expected_set & detected_set)
        false_positives = len(detected_set - expected_set)
        false_negatives = len(expected_set - detected_set)
        
        # Calculate metrics
        precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0.0
        recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0.0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        
        return {
            'precision': precision,
            'recall': recall,
            'f1': f1,
            'true_positives': true_positives,
            'false_positives': false_positives,
            'false_negatives': false_negatives
        }
    
    def generate_report(self, results: List[Dict[str, Any]]) -> str:
        """Generate a comprehensive accuracy report from test results."""
        lines = []
        
        # Header
        lines.append("=" * 70)
        lines.append("PII DETECTION ACCURACY REPORT")
        lines.append("=" * 70)
        lines.append("")
        
        # Overall statistics
        total = len(results)
        passed = sum(1 for r in results if r.get('passed', False))
        failed = total - passed
        
        lines.append("OVERALL STATISTICS")
        lines.append("-" * 40)
        lines.append(f"Total Test Cases: {total}")
        lines.append(f"Passed: {passed}")
        lines.append(f"Failed: {failed}")
        if total > 0:
            lines.append(f"Success Rate: {passed/total:.1%}")
        lines.append("")
        
        # Group by category
        by_category = defaultdict(list)
        for result in results:
            category = result.get('category', 'uncategorized')
            by_category[category].append(result)
        
        # Category statistics
        lines.append("BY CATEGORY")
        lines.append("-" * 40)
        
        category_metrics = {}
        
        for category in sorted(by_category.keys()):
            cat_results = by_category[category]
            cat_total = len(cat_results)
            cat_passed = sum(1 for r in cat_results if r.get('passed', False))
            cat_failed = cat_total - cat_passed
            
            lines.append(f"\n{category.upper()}:")
            lines.append(f"  Tests: {cat_total}")
            lines.append(f"  Passed: {cat_passed}")
            lines.append(f"  Failed: {cat_failed}")
            lines.append(f"  Success Rate: {cat_passed/cat_total:.1%}" if cat_total > 0 else "  Success Rate: N/A")
            
            # Calculate precision/recall for this category
            all_expected = []
            all_detected = []
            
            for result in cat_results:
                expected = result.get('expected', {}).get(category, [])
                detected = result.get('detected', {}).get(category, [])
                all_expected.extend(expected)
                all_detected.extend(detected)
            
            if all_expected or all_detected:
                metrics = self.calculate_precision_recall_f1(all_expected, all_detected)
                lines.append(f"  Precision: {metrics['precision']:.1%}")
                lines.append(f"  Recall: {metrics['recall']:.1%}")
                lines.append(f"  F1 Score: {metrics['f1']:.1%}")
                category_metrics[category] = metrics
        
        # Failed test details
        failed_tests = [r for r in results if not r.get('passed', False)]
        if failed_tests:
            lines.append("")
            lines.append("=" * 70)
            lines.append("FAILED TESTS")
            lines.append("-" * 40)
            
            # Group failures by category
            failures_by_category = defaultdict(list)
            for failure in failed_tests:
                failures_by_category[failure.get('category', 'uncategorized')].append(failure)
            
            for category in sorted(failures_by_category.keys()):
                lines.append(f"\n{category.upper()}:")
                for failure in failures_by_category[category][:5]:  # Show first 5 failures per category
                    lines.append(f"  • {failure['id']}: {', '.join(failure.get('errors', ['Unknown error']))}")
                
                if len(failures_by_category[category]) > 5:
                    lines.append(f"  ... and {len(failures_by_category[category]) - 5} more")
        
        # Summary
        lines.append("")
        lines.append("=" * 70)
        lines.append("SUMMARY")
        lines.append("-" * 40)
        
        if total > 0:
            lines.append(f"Overall Success Rate: {passed/total:.1%}")
            
            # Calculate weighted average F1
            if category_metrics:
                total_items = sum(
                    m['true_positives'] + m['false_negatives'] 
                    for m in category_metrics.values()
                )
                if total_items > 0:
                    weighted_f1 = sum(
                        m['f1'] * (m['true_positives'] + m['false_negatives']) 
                        for m in category_metrics.values()
                    ) / total_items
                    lines.append(f"Weighted Average F1 Score: {weighted_f1:.1%}")
        else:
            lines.append("No test results to summarize")
        
        lines.append("=" * 70)
        
        return "\n".join(lines)


class AccuracyTester:
    """Run accuracy tests from YAML files."""
    
    def __init__(self, test_dir: Path = None, backend: str = "local"):
        """Initialize the accuracy tester.
        
        Args:
            test_dir: Directory containing test YAML files
            backend: Anonymizer backend to use ('local' or 'anonllm')
        """
        if test_dir is None:
            # Default to test_cases in same directory
            test_dir = Path(__file__).parent / "test_cases"
        
        self.test_dir = Path(test_dir)
        self.backend = backend
        self.metrics = AccuracyMetrics()
        
        # Load config and create anonymizer from it
        config = load_all_configs()
        anon_config = get_config('anonymizer', config)
        self.anonymizer = LocalAnonymizer.create_from_config(anon_config)
    
    def load_test_cases(self) -> List[Dict]:
        """Load all test cases from YAML files."""
        all_test_cases = []
        
        if not self.test_dir.exists():
            print(f"Warning: Test directory {self.test_dir} does not exist")
            return all_test_cases
        
        # Load all .yaml files, sorted for consistent ordering
        yaml_files = sorted(self.test_dir.glob("*.yaml"))
        
        for yaml_file in yaml_files:
            with open(yaml_file) as f:
                data = yaml.safe_load(f)

                if not data or 'test_cases' not in data:
                    continue

                # Add source file info to each test case
                for case in data['test_cases']:
                    case['source_file'] = yaml_file.name
                    all_test_cases.append(case)

        return all_test_cases
    
    def extract_detected_pii(self, mappings: Dict) -> Dict[str, List[str]]:
        """Extract detected PII from anonymizer mappings."""
        detected = defaultdict(list)
        
        # Map anonymizer categories to test categories
        category_map = {
            # Regex patterns used by anonymizer
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b': 'emails',
            r'\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b': 'phones',
            r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b': 'credit_cards',
            # Named categories
            'SSN': 'ssn',
            'PERSON': 'names',
            'ORGANIZATION': 'organizations',
            'IP_ADDRESS': 'ipv4'
        }
        
        for key, items in mappings.items():
            if isinstance(items, dict):
                category = category_map.get(key, key.lower())
                for original, replacement in items.items():
                    detected[category].append(original)
        
        return dict(detected)
    
    def validate_detection(self, expected: Dict, detected: Dict, test_case: Dict) -> List[str]:
        """Validate detected PII against expected."""
        errors = []
        tags = test_case.get('tags', [])
        
        # For false positive tests, nothing should be detected
        if 'false_positive' in tags:
            if detected:
                detected_str = ', '.join(f"{k}: {v}" for k, v in detected.items())
                errors.append(f"False positive - detected: {detected_str}")
            return errors
        
        # Check each expected category
        for category, expected_items in expected.items():
            detected_items = detected.get(category, [])
            
            # Check for missing detections
            for item in expected_items:
                if item not in detected_items:
                    errors.append(f"Not detected ({category}): '{item}'")
            
            # Check for extra detections (optional)
            for item in detected_items:
                if category in expected and item not in expected_items:
                    errors.append(f"Unexpected ({category}): '{item}'")
        
        return errors
    
    def run_test(self, test_case: Dict) -> Dict[str, Any]:
        """Run a single test case."""
        # Skip tests with skip tag
        if 'skip' in test_case.get('tags', []):
            return {
                'id': test_case['id'],
                'category': test_case.get('category', 'uncategorized'),
                'source_file': test_case.get('source_file', 'unknown'),
                'passed': False,
                'errors': ['Test marked as skip'],
                'expected': test_case.get('expected', {}),
                'detected': {},
                'skipped': True
            }

        # Reset anonymizer for each test to ensure independent results
        self.anonymizer.reset()

        # Use the shared anonymizer instance
        anon_text, mappings = self.anonymizer.anonymize_data(test_case['input'])
        detected = self.extract_detected_pii(mappings)
        expected = test_case.get('expected', {})

        errors = self.validate_detection(expected, detected, test_case)

        return {
            'id': test_case['id'],
            'category': test_case.get('category', 'uncategorized'),
            'source_file': test_case.get('source_file', 'unknown'),
            'passed': len(errors) == 0,
            'errors': errors,
            'expected': expected,
            'detected': detected
        }
    
    def run_all_tests(self) -> List[Dict[str, Any]]:
        """Run all test cases and return results."""
        test_cases = self.load_test_cases()
        
        if not test_cases:
            print("No test cases found")
            return []
        
        print(f"Running {len(test_cases)} test cases...")
        results = []
        
        for test_case in test_cases:
            result = self.run_test(test_case)
            results.append(result)
            
            # Show progress
            status = "✓" if result['passed'] else "✗" if not result.get('skipped') else "○"
            print(f"  {status} {result['id']}")
        
        return results
    
    def run(self, verbose: bool = False) -> None:
        """Run accuracy tests and display report.
        
        Args:
            verbose: If True, show detailed failure information
        """
        results = self.run_all_tests()
        
        if not results:
            return
        
        # Generate and display report
        report = self.metrics.generate_report(results)
        print(f"\n{report}")
        
        if verbose:
            # Show detailed failure information
            failed = [r for r in results if not r['passed'] and not r.get('skipped')]
            if failed:
                print("\n" + "=" * 70)
                print("DETAILED FAILURE INFORMATION")
                print("=" * 70)
                
                for failure in failed:
                    print(f"\nTest: {failure['id']}")
                    print(f"Category: {failure['category']}")
                    print(f"Source: {failure['source_file']}")
                    print(f"Expected: {failure['expected']}")
                    print(f"Detected: {failure['detected']}")
                    print(f"Errors: {', '.join(failure['errors'])}")
