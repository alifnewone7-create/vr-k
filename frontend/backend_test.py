#!/usr/bin/env python3
"""
ROUND 3 Backend Testing Script
Tests the Telegram admin panel backend APIs after Neon migration and tgultra rename
"""

import requests
import subprocess
import os
import tarfile
import tempfile
import shutil
from pathlib import Path

BASE_URL = "http://localhost:3000"
AUTH_COOKIE = "tg_admin_session=31abc58299136684e59a8e44d474700eb64414723a6f62c7364ed44f25b3ffca"

def print_section(title):
    print(f"\n{'='*80}")
    print(f"{title}")
    print('='*80)

def test_tgultra_service():
    """Test 1: GET /api/setup/tgultra.service"""
    print_section("TEST 1: GET /api/setup/tgultra.service")
    
    try:
        response = requests.get(f"{BASE_URL}/api/setup/tgultra.service", timeout=10)
        print(f"Status Code: {response.status_code}")
        print(f"Content-Type: {response.headers.get('Content-Type')}")
        
        if response.status_code == 200:
            body = response.text
            print(f"Body length: {len(body)} bytes")
            
            # Check required strings
            required_strings = [
                "WorkingDirectory=/root/tgultra",
                "ExecStart=/root/tgultra/.venv/bin/python -m agent.supervisor",
                "SyslogIdentifier=tgultra"
            ]
            
            all_found = True
            for req_str in required_strings:
                if req_str in body:
                    print(f"✅ Found: {req_str}")
                else:
                    print(f"❌ MISSING: {req_str}")
                    all_found = False
            
            # Check that "tgpro" is NOT present
            if "tgpro" in body:
                print(f"❌ CRITICAL: Found 'tgpro' in body (should be renamed to tgultra)")
                print(f"Occurrences: {body.count('tgpro')}")
                return False
            else:
                print(f"✅ 'tgpro' NOT found in body (correctly renamed)")
            
            return all_found
        else:
            print(f"❌ Expected 200, got {response.status_code}")
            print(f"Body: {response.text[:500]}")
            return False
            
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False

def test_tgpro_service_404():
    """Test 2: GET /api/setup/tgpro.service should be 404"""
    print_section("TEST 2: GET /api/setup/tgpro.service (should be 404)")
    
    try:
        response = requests.get(f"{BASE_URL}/api/setup/tgpro.service", timeout=10)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 404:
            print(f"✅ Correctly returns 404 (old name removed)")
            return True
        else:
            print(f"❌ Expected 404, got {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False

def test_ls_python_tarball():
    """Test 3: GET /api/setup/LS_Python.tar.gz"""
    print_section("TEST 3: GET /api/setup/LS_Python.tar.gz")
    
    try:
        response = requests.get(f"{BASE_URL}/api/setup/LS_Python.tar.gz", timeout=30)
        print(f"Status Code: {response.status_code}")
        print(f"Content-Type: {response.headers.get('Content-Type')}")
        print(f"Content-Length: {len(response.content)} bytes")
        
        if response.status_code != 200:
            print(f"❌ Expected 200, got {response.status_code}")
            return False
        
        if "application/gzip" not in response.headers.get('Content-Type', ''):
            print(f"❌ Expected Content-Type: application/gzip")
            return False
        
        # Save tarball to temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.tar.gz') as tmp:
            tmp.write(response.content)
            tarball_path = tmp.name
        
        print(f"\n--- 3a. Listing tarball contents ---")
        try:
            result = subprocess.run(['tar', 'tzf', tarball_path], 
                                  capture_output=True, text=True, timeout=10)
            entries = result.stdout.strip().split('\n')
            print(f"Total entries: {len(entries)}")
            print("\nAll entries:")
            for entry in entries:
                print(f"  {entry}")
            
            # Check if .env is in the archive (CRITICAL SECURITY)
            env_in_archive = any('.env' in entry and not ('.env.example' in entry or '.env.vps.example' in entry) 
                               for entry in entries)
            
            if env_in_archive:
                print(f"\n❌ CRITICAL SECURITY ISSUE: .env file found in archive!")
                matching = [e for e in entries if '.env' in e and not ('.env.example' in e or '.env.vps.example' in e)]
                print(f"Matching entries: {matching}")
            else:
                print(f"\n✅ .env NOT in archive (security check passed)")
            
            # Check if tgultra.service is in archive
            service_in_archive = any('tgultra.service' in entry for entry in entries)
            if service_in_archive:
                print(f"✅ tgultra.service IS in archive")
            else:
                print(f"❌ tgultra.service NOT in archive")
            
        except Exception as e:
            print(f"❌ Failed to list tarball: {e}")
            os.unlink(tarball_path)
            return False
        
        # Extract and check for secrets
        print(f"\n--- 3b. CRITICAL SECURITY CHECK: Grep for secrets ---")
        extract_dir = tempfile.mkdtemp()
        try:
            with tarfile.open(tarball_path, 'r:gz') as tar:
                tar.extractall(extract_dir)
            
            print(f"Extracted to: {extract_dir}")
            
            # Grep for sensitive strings
            sensitive_strings = [
                "neondb_owner",
                "npg_",
                "TGLION_API_KEY=gcjn",
                "IMH@TG12",
                "sslmode=require"
            ]
            
            leaked = False
            for sens_str in sensitive_strings:
                result = subprocess.run(
                    ['grep', '-r', sens_str, extract_dir],
                    capture_output=True, text=True, timeout=10
                )
                if result.returncode == 0:
                    # Found matches - check if they're in real .env files
                    matches = result.stdout.strip().split('\n')
                    for match in matches:
                        # Ignore .env.example and .env.vps.example
                        if '.env.example' in match or '.env.vps.example' in match:
                            print(f"ℹ️  Found '{sens_str}' in example file (OK): {match[:100]}")
                        else:
                            print(f"❌ CRITICAL LEAK: Found '{sens_str}' in: {match}")
                            leaked = True
                else:
                    print(f"✅ '{sens_str}' NOT found in extracted files")
            
            if leaked:
                print(f"\n❌ CRITICAL: SECRETS LEAKED IN TARBALL")
                return False
            else:
                print(f"\n✅ No secrets leaked (security check passed)")
            
        except Exception as e:
            print(f"❌ Failed to extract/grep tarball: {e}")
            shutil.rmtree(extract_dir, ignore_errors=True)
            os.unlink(tarball_path)
            return False
        
        # Compile Python files
        print(f"\n--- 3c. Compiling Python files ---")
        agent_dir = os.path.join(extract_dir, 'LS_Python', 'agent')
        if os.path.exists(agent_dir):
            result = subprocess.run(
                ['python3', '-m', 'compileall', '-q', agent_dir],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                print(f"✅ All Python files in agent/ compiled successfully")
            else:
                print(f"❌ Python compilation failed:")
                print(result.stderr)
                shutil.rmtree(extract_dir, ignore_errors=True)
                os.unlink(tarball_path)
                return False
        else:
            print(f"❌ agent/ directory not found in extracted tarball")
            shutil.rmtree(extract_dir, ignore_errors=True)
            os.unlink(tarball_path)
            return False
        
        # Cleanup
        shutil.rmtree(extract_dir, ignore_errors=True)
        os.unlink(tarball_path)
        
        print(f"\n✅ LS_Python.tar.gz test PASSED")
        return True
        
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False

def test_text_files_regression():
    """Test 4: Regression on text files"""
    print_section("TEST 4: Text Files Regression")
    
    results = {}
    
    # Test all_tg.sql
    print("\n--- Testing all_tg.sql ---")
    try:
        response = requests.get(f"{BASE_URL}/api/setup/all_tg.sql", timeout=10)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            lines = response.text.split('\n')
            line_count = len(lines)
            create_table_count = response.text.count("CREATE TABLE IF NOT EXISTS")
            
            print(f"Line count: {line_count}")
            print(f"CREATE TABLE IF NOT EXISTS count: {create_table_count}")
            
            if line_count == 505 and create_table_count == 18:
                print(f"✅ all_tg.sql PASSED")
                results['all_tg.sql'] = True
            else:
                print(f"❌ all_tg.sql FAILED (expected 505 lines and 18 CREATE TABLE)")
                results['all_tg.sql'] = False
        else:
            print(f"❌ all_tg.sql returned {response.status_code}")
            results['all_tg.sql'] = False
    except Exception as e:
        print(f"❌ all_tg.sql exception: {e}")
        results['all_tg.sql'] = False
    
    # Test export_accounts_csv.sh
    print("\n--- Testing export_accounts_csv.sh ---")
    try:
        response = requests.get(f"{BASE_URL}/api/setup/export_accounts_csv.sh", timeout=10)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            # Save to temp file and check syntax
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.sh') as tmp:
                tmp.write(response.text)
                tmp_path = tmp.name
            
            result = subprocess.run(['bash', '-n', tmp_path], 
                                  capture_output=True, text=True, timeout=5)
            os.unlink(tmp_path)
            
            if result.returncode == 0:
                print(f"✅ export_accounts_csv.sh PASSED (valid bash syntax)")
                results['export_accounts_csv.sh'] = True
            else:
                print(f"❌ export_accounts_csv.sh has syntax errors:")
                print(result.stderr)
                results['export_accounts_csv.sh'] = False
        else:
            print(f"❌ export_accounts_csv.sh returned {response.status_code}")
            results['export_accounts_csv.sh'] = False
    except Exception as e:
        print(f"❌ export_accounts_csv.sh exception: {e}")
        results['export_accounts_csv.sh'] = False
    
    # Test dev_local_pg.sh
    print("\n--- Testing dev_local_pg.sh ---")
    try:
        response = requests.get(f"{BASE_URL}/api/setup/dev_local_pg.sh", timeout=10)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            print(f"✅ dev_local_pg.sh PASSED")
            results['dev_local_pg.sh'] = True
        else:
            print(f"❌ dev_local_pg.sh returned {response.status_code}")
            results['dev_local_pg.sh'] = False
    except Exception as e:
        print(f"❌ dev_local_pg.sh exception: {e}")
        results['dev_local_pg.sh'] = False
    
    return all(results.values())

def test_path_traversal():
    """Test 5: Path traversal attacks"""
    print_section("TEST 5: Path Traversal Security Tests")
    
    traversal_attempts = [
        "/api/setup/..%2f.env",
        "/api/setup/..%2F..%2F.env",
        "/api/setup/%2e%2e%2f.env",
        "/api/setup/....//.env",
        "/api/setup/..%252f.env",
        "/api/setup/LS_Python%2f.env",
        "/api/setup/..%2f..%2f..%2f..%2fetc%2fpasswd",
    ]
    
    all_blocked = True
    
    for attempt in traversal_attempts:
        try:
            response = requests.get(f"{BASE_URL}{attempt}", timeout=10)
            status = response.status_code
            
            # Check for any data leakage
            leaked = False
            sensitive_indicators = [
                "DATABASE_URL", "MONGO_URL", "neondb", "npg_",
                "ADMIN_USERNAME", "ADMIN_PASSWORD", "ADMIN_SECRET",
                "TGLION_API_KEY", "TGLION_USER_ID",
                "root:x:", "/bin/bash", "daemon:x:",
                "IMH@TG12", "sslmode=require"
            ]
            
            for indicator in sensitive_indicators:
                if indicator in response.text:
                    print(f"❌ {attempt} → {status} - LEAKED: {indicator}")
                    print(f"   Response snippet: {response.text[:200]}")
                    leaked = True
                    all_blocked = False
                    break
            
            if not leaked:
                if status in [404, 400]:
                    print(f"✅ {attempt} → {status} (blocked, no leak)")
                else:
                    print(f"⚠️  {attempt} → {status} (unexpected status)")
                    all_blocked = False
                    
        except Exception as e:
            print(f"❌ {attempt} → Exception: {e}")
            all_blocked = False
    
    return all_blocked

def test_neon_regression():
    """Test 6: NEON database regression"""
    print_section("TEST 6: NEON Database Regression")
    
    cookies = {'tg_admin_session': AUTH_COOKIE.split('=')[1]}
    results = {}
    
    # Test /api/health
    print("\n--- Testing /api/health ---")
    try:
        response = requests.get(f"{BASE_URL}/api/health", cookies=cookies, timeout=10)
        print(f"Status: {response.status_code}")
        print(f"Body: {response.text}")
        
        if response.status_code == 200 and '"db":"ok"' in response.text:
            print(f"✅ /api/health PASSED")
            results['health'] = True
        else:
            print(f"❌ /api/health FAILED")
            results['health'] = False
    except Exception as e:
        print(f"❌ /api/health exception: {e}")
        results['health'] = False
    
    # Test /api/accounts
    print("\n--- Testing /api/accounts ---")
    try:
        response = requests.get(f"{BASE_URL}/api/accounts", cookies=cookies, timeout=10)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            print(f"✅ /api/accounts PASSED")
            results['accounts'] = True
        else:
            print(f"❌ /api/accounts returned {response.status_code}")
            print(f"Body: {response.text[:500]}")
            results['accounts'] = False
    except Exception as e:
        print(f"❌ /api/accounts exception: {e}")
        results['accounts'] = False
    
    # Test /api/agents
    print("\n--- Testing /api/agents ---")
    try:
        response = requests.get(f"{BASE_URL}/api/agents", cookies=cookies, timeout=10)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            print(f"✅ /api/agents PASSED")
            results['agents'] = True
        else:
            print(f"❌ /api/agents returned {response.status_code}")
            print(f"Body: {response.text[:500]}")
            results['agents'] = False
    except Exception as e:
        print(f"❌ /api/agents exception: {e}")
        results['agents'] = False
    
    # Test /api/accounts/export
    print("\n--- Testing /api/accounts/export ---")
    try:
        response = requests.get(f"{BASE_URL}/api/accounts/export", cookies=cookies, timeout=10)
        print(f"Status: {response.status_code}")
        print(f"Content-Type: {response.headers.get('Content-Type')}")
        
        if response.status_code == 200:
            expected_header = "phone_number,label,app_title,short_name,api_id,api_hash,session_string,status,two_factor_required,last_error,mtproto_hash,login_hash"
            first_line = response.text.split('\n')[0].strip()
            
            print(f"First line: {first_line}")
            
            if first_line == expected_header:
                print(f"✅ /api/accounts/export PASSED (correct CSV header)")
                results['export'] = True
            else:
                print(f"❌ /api/accounts/export header mismatch")
                print(f"Expected: {expected_header}")
                print(f"Got:      {first_line}")
                results['export'] = False
        else:
            print(f"❌ /api/accounts/export returned {response.status_code}")
            results['export'] = False
    except Exception as e:
        print(f"❌ /api/accounts/export exception: {e}")
        results['export'] = False
    
    return all(results.values())

def test_supervisor_logs():
    """Test 7: Check supervisor logs for errors"""
    print_section("TEST 7: Supervisor Log Check")
    
    log_path = "/var/log/supervisor/nextjs.out.log"
    
    try:
        # Get the log content after the most recent "Ready in"
        result = subprocess.run(
            ['tail', '-n', '500', log_path],
            capture_output=True, text=True, timeout=5
        )
        
        lines = result.stdout.split('\n')
        
        # Find the last "Ready in" line
        ready_index = -1
        for i in range(len(lines) - 1, -1, -1):
            if "Ready in" in lines[i]:
                ready_index = i
                break
        
        if ready_index == -1:
            print(f"⚠️  Could not find 'Ready in' in recent logs")
            relevant_logs = '\n'.join(lines[-50:])
        else:
            print(f"Found 'Ready in' at line {ready_index}")
            relevant_logs = '\n'.join(lines[ready_index:])
        
        print(f"\nRelevant logs (after 'Ready in'):")
        print(relevant_logs[-1000:])  # Last 1000 chars
        
        # Check for error patterns
        error_patterns = ["ECONNREFUSED", "500", "migration fail", "SSL error", "ENOTFOUND"]
        errors_found = []
        
        for pattern in error_patterns:
            if pattern in relevant_logs:
                errors_found.append(pattern)
        
        if errors_found:
            print(f"\n❌ Found error patterns: {errors_found}")
            return False
        else:
            print(f"\n✅ No error patterns found in logs")
            return True
            
    except Exception as e:
        print(f"❌ Failed to check logs: {e}")
        return False

def main():
    print("="*80)
    print("ROUND 3 BACKEND TESTING - Neon Migration + tgultra Rename")
    print("="*80)
    
    results = {}
    
    # Run all tests
    results['test1_tgultra_service'] = test_tgultra_service()
    results['test2_tgpro_404'] = test_tgpro_service_404()
    results['test3_tarball'] = test_ls_python_tarball()
    results['test4_text_files'] = test_text_files_regression()
    results['test5_path_traversal'] = test_path_traversal()
    results['test6_neon_regression'] = test_neon_regression()
    results['test7_logs'] = test_supervisor_logs()
    
    # Summary
    print_section("FINAL SUMMARY")
    
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    total = len(results)
    passed = sum(results.values())
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if all(results.values()):
        print("\n🎉 ALL TESTS PASSED")
        return 0
    else:
        print("\n❌ SOME TESTS FAILED")
        return 1

if __name__ == "__main__":
    exit(main())
