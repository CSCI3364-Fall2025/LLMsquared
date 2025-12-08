#!/usr/bin/env python3
"""
Security Testing Script for Django Peer Assessment System
Tests for SQL Injection and DoS vulnerabilities

SIMPLIFIED VERSION - Matches original structure from prompt
"""

import requests
import time
import concurrent.futures
import uuid
from datetime import datetime

class SecurityTester:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.session = requests.Session()
        self.results = []
        
    def log_result(self, test_type, test_name, success, details=""):
        """Log test results"""
        result = {
            'timestamp': datetime.now().isoformat(),
            'test_type': test_type,
            'test_name': test_name,
            'success': success,
            'details': details
        }
        self.results.append(result)
        status = "PASS" if success else "FAIL"
        print(f"{status} {test_type}: {test_name} - {details}")
    
    def test_sql_injection_url_parameters(self):
        """Test SQL injection on URL parameters"""
        print("\nTesting SQL Injection on URL Parameters...")
        
        payloads = [
            "' OR '1'='1",
            "' OR 1=1--",
            "'; DROP TABLE courses; --",
            "' UNION SELECT * FROM users--",
        ]
        
        # Test ALL your UUID-based endpoints
        fake_uuid = str(uuid.uuid4())
        endpoints = [
            # Teacher endpoints
            f"/teacher_dashboard/{fake_uuid}/",
            f"/teacher_courses/{fake_uuid}/",
            f"/new_course/{fake_uuid}/",
            f"/teams_dashboard/{fake_uuid}/",
            f"/assessment_dashboard/{fake_uuid}/",
            f"/create_assessment/{fake_uuid}/{fake_uuid}/",
            f"/view_assessment/{fake_uuid}/{fake_uuid}/",
            f"/delete_course/{fake_uuid}/{fake_uuid}/",
            f"/teacher_view_results/{fake_uuid}/{fake_uuid}/{fake_uuid}/",
            
            # Student endpoints
            f"/student_dashboard/{fake_uuid}/",
            f"/student_courses/{fake_uuid}/",
            f"/student_course_detail/{fake_uuid}/{fake_uuid}/",
            f"/student_take_assessment/{fake_uuid}/{fake_uuid}/{fake_uuid}/",
            f"/student_view_results/{fake_uuid}/{fake_uuid}/{fake_uuid}/",
            
            # Team endpoints
            f"/new_team/{fake_uuid}/{fake_uuid}/",
            f"/edit_team/{fake_uuid}/{fake_uuid}/{fake_uuid}/",
            f"/delete_team/{fake_uuid}/{fake_uuid}/{fake_uuid}/",
        ]
        
        for endpoint in endpoints:
            for payload in payloads:
                try:
                    # Replace UUID in endpoint with SQL injection payload
                    url = self.base_url + endpoint.replace(fake_uuid, payload)
                    response = self.session.get(url, timeout=5)
                    
                    # Check for SQL errors
                    error_indicators = [
                        "mysql", "sqlite", "postgresql", "database error",
                        "sql syntax", "query failed"
                    ]
                    
                    if any(indicator in response.text.lower() for indicator in error_indicators):
                        self.log_result("SQL Injection", f"URL param in {endpoint}", False,
                                     f"SQL ERROR EXPOSED")
                    else:
                        self.log_result("SQL Injection", f"URL param in {endpoint}", True)
                        break  # One pass is enough per endpoint
                        
                except Exception as e:
                    if "404" not in str(e):
                        self.log_result("SQL Injection", f"URL test: {endpoint}", False, str(e))

    def test_sql_injection_forms(self):
        """Test SQL injection on form submissions"""
        print("\nTesting SQL Injection on Forms...")
        
        # Test Course Form
        course_data = {
            'course_number': "'; DROP TABLE courses; --",
            'course_name': "' OR '1'='1",
            'course_semester': "Spring",
            'course_year': "2025"
        }
        
        fake_uuid = str(uuid.uuid4())
        
        try:
            url = f"{self.base_url}/new_course/{fake_uuid}/"
            response = self.session.post(url, data=course_data, timeout=5)
            
            error_indicators = ["mysql", "sqlite", "postgresql", "sql syntax"]
            
            if any(indicator in response.text.lower() for indicator in error_indicators):
                self.log_result("SQL Injection", "Course form", False, "SQL error detected")
            else:
                self.log_result("SQL Injection", "Course form", True)
                
        except Exception as e:
            if "404" not in str(e):
                self.log_result("SQL Injection", "Course form test", False, str(e))

    def test_authentication_bypass(self):
        """Test for authentication bypass vulnerabilities"""
        print("\nTesting Authentication Bypass...")
        
        fake_uuid = str(uuid.uuid4())
        
        # ALL protected endpoints that should require authentication
        protected_endpoints = [
            # Teacher endpoints
            f"/teacher_dashboard/{fake_uuid}/",
            f"/teacher_courses/{fake_uuid}/",
            f"/new_course/{fake_uuid}/",
            f"/teams_dashboard/{fake_uuid}/",
            f"/assessment_dashboard/{fake_uuid}/",
            f"/create_assessment/{fake_uuid}/{fake_uuid}/",
            f"/view_assessment/{fake_uuid}/{fake_uuid}/",
            f"/delete_course/{fake_uuid}/{fake_uuid}/",
            f"/delete_assessment/{fake_uuid}/{fake_uuid}/",
            f"/teacher_view_results/{fake_uuid}/{fake_uuid}/{fake_uuid}/",
            f"/teacher/{fake_uuid}/course/{fake_uuid}/assessment/{fake_uuid}/team/{fake_uuid}/student/{fake_uuid}/",
            
            # Student endpoints
            f"/student_dashboard/{fake_uuid}/",
            f"/student_courses/{fake_uuid}/",
            f"/student_course_detail/{fake_uuid}/{fake_uuid}/",
            f"/student_take_assessment/{fake_uuid}/{fake_uuid}/{fake_uuid}/",
            f"/student_view_results/{fake_uuid}/{fake_uuid}/{fake_uuid}/",
            f"/student_take_assessment_form/{fake_uuid}/{fake_uuid}/{fake_uuid}/{fake_uuid}/",
            
            # Team management
            f"/new_team/{fake_uuid}/{fake_uuid}/",
            f"/edit_team/{fake_uuid}/{fake_uuid}/{fake_uuid}/",
            f"/delete_team/{fake_uuid}/{fake_uuid}/{fake_uuid}/",
            f"/remove_from_team/{fake_uuid}/{fake_uuid}/{fake_uuid}/{fake_uuid}/",
            f"/add_to_team/{fake_uuid}/{fake_uuid}/{fake_uuid}/{fake_uuid}/",
            
            # Other protected features
            f"/invite-student/",
            f"/teacher_chat/",
        ]
        
        for endpoint in protected_endpoints:
            try:
                url = self.base_url + endpoint
                response = self.session.get(url, timeout=5, allow_redirects=False)
                
                # Should redirect to login or return 401/403
                if response.status_code == 200:
                    self.log_result("Auth Bypass", f"Endpoint {endpoint}", False,
                                 "Accessible without authentication")
                elif response.status_code in [302, 401, 403]:
                    self.log_result("Auth Bypass", f"Endpoint {endpoint}", True,
                                 f"Protected (Status: {response.status_code})")
                    
            except Exception as e:
                if "404" not in str(e):
                    self.log_result("Auth Bypass", f"Test error: {endpoint}", False, str(e))

    def test_dos_sustained_load(self, endpoint="/", concurrency=20, duration_seconds=8):
        """Test DoS with sustained load"""
        print(f"\nTesting DoS: {concurrency} concurrent requests for {duration_seconds}s...")
        
        url = self.base_url + endpoint
        stop_time = time.time() + duration_seconds
        
        total_sent = 0
        total_success = 0
        total_errors = 0
        
        def single_request():
            nonlocal total_sent, total_success, total_errors
            try:
                r = self.session.get(url, timeout=8)
                total_sent += 1
                if 200 <= r.status_code < 400:
                    total_success += 1
                else:
                    total_errors += 1
            except:
                total_sent += 1
                total_errors += 1
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
            while time.time() < stop_time:
                for _ in range(concurrency):
                    executor.submit(single_request)
                time.sleep(0.1)
        
        success_rate = (total_success / total_sent * 100) if total_sent else 0
        
        details = f"sent={total_sent}, success={total_success}, errors={total_errors}, rate={success_rate:.1f}%"
        
        overwhelmed = success_rate < 50
        self.log_result("DoS", f"Sustained load ({concurrency}x{duration_seconds}s)", 
                       not overwhelmed, details)

    def generate_report(self):
        """Generate security testing report"""
        print("\n" + "="*60)
        print("SECURITY TESTING REPORT")
        print("="*60)
        
        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results if r['success'])
        failed_tests = total_tests - passed_tests
        
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {failed_tests}")
        print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        
        print("\nTest Results by Category:")
        categories = {}
        for result in self.results:
            category = result['test_type']
            if category not in categories:
                categories[category] = {'passed': 0, 'failed': 0}
            
            if result['success']:
                categories[category]['passed'] += 1
            else:
                categories[category]['failed'] += 1
        
        for category, stats in categories.items():
            total = stats['passed'] + stats['failed']
            success_rate = (stats['passed'] / total) * 100 if total > 0 else 0
            print(f"  {category}: {stats['passed']}/{total} ({success_rate:.1f}%)")
        
        return failed_tests == 0
        
    def run_all_tests(self):
        """Run all security tests"""
        print("Starting Security Testing Suite")
        print("="*50)
        
        self.test_sql_injection_url_parameters()
        self.test_sql_injection_forms()
        self.test_authentication_bypass()
        self.test_dos_sustained_load()
        
        return self.generate_report()


if __name__ == "__main__":
    import sys
    
    BASE_URL = "http://127.0.0.1:8000"
    
    tester = SecurityTester(BASE_URL)
    success = tester.run_all_tests()
    
    sys.exit(0 if success else 1)