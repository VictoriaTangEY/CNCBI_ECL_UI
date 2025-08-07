#!/usr/bin/env python3
"""
LDAP Connection Test Script
For diagnosing LDAP connection issues
"""

import sys
import os
import socket
import time

# Add current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from ldap3 import Server, Connection, ALL, NTLM, SIMPLE
    print("✓ ldap3 library imported successfully")
except ImportError as e:
    print(f"✗ Cannot import ldap3 library: {e}")
    print("Please run: pip install ldap3")
    sys.exit(1)

# LDAP Configuration
LDAP_SERVER = 'ldap://10.30.244.12:389'
LDAP_BIND_DN = 'CN=svreclappmgr, OU=Service Accounts,OU=Tier1,OU=Admin,OU=HKG,DC=hkg,DC=ho,DC=cncb2'
LDAP_BIND_PASSWORD = 'Cncbi@567890'
LDAP_SEARCH_BASE = 'OU=User Accounts,OU=HKG,DC=hkg,DC=ho,DC=cncb2'

def test_network_connectivity():
    """Test network connectivity"""
    print("\n=== Network Connectivity Test ===")
    
    # Parse server address
    server_host = LDAP_SERVER.replace('ldap://', '').split(':')[0]
    server_port = int(LDAP_SERVER.split(':')[-1])
    
    print(f"Server address: {server_host}")
    print(f"Port: {server_port}")
    
    try:
        # Test TCP connection
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        result = sock.connect_ex((server_host, server_port))
        sock.close()
        
        if result == 0:
            print("✓ Network connectivity is normal")
            return True
        else:
            print(f"✗ Network connection failed (error code: {result})")
            return False
            
    except Exception as e:
        print(f"✗ Network connectivity test exception: {e}")
        return False

def analyze_ldap_error(error_code, error_message):
    """Analyze LDAP error codes and provide helpful information"""
    print(f"\n=== Error Analysis ===")
    print(f"Error Code: {error_code}")
    print(f"Error Message: {error_message}")
    
    error_analysis = {
        "49": {
            "name": "invalidCredentials",
            "description": "Invalid credentials (username/password)",
            "solutions": [
                "Check if the service account password is correct",
                "Verify the service account is not locked or expired",
                "Ensure the service account has proper permissions",
                "Try different authentication methods"
            ]
        },
        "52e": {
            "name": "Logon failure: unknown user name or bad password",
            "description": "Windows-specific error for invalid credentials",
            "solutions": [
                "Verify the username format (try domain\\username)",
                "Check if the account exists in Active Directory",
                "Ensure the password is correct and not expired",
                "Try using UPN format (username@domain.com)"
            ]
        },
        "51": {
            "name": "serverDown",
            "description": "Cannot contact LDAP server",
            "solutions": [
                "Check network connectivity",
                "Verify server address and port",
                "Check firewall settings",
                "Ensure LDAP service is running"
            ]
        },
        "81": {
            "name": "can'tConnect",
            "description": "Cannot connect to LDAP server",
            "solutions": [
                "Check if server is reachable",
                "Verify port 389 is open",
                "Try SSL/TLS connection (port 636)",
                "Check DNS resolution"
            ]
        }
    }
    
    if error_code in error_analysis:
        analysis = error_analysis[error_code]
        print(f"Error Type: {analysis['name']}")
        print(f"Description: {analysis['description']}")
        print("Possible Solutions:")
        for i, solution in enumerate(analysis['solutions'], 1):
            print(f"  {i}. {solution}")
    else:
        print("Unknown error code. Please check LDAP server logs for more details.")

def test_ldap_connection():
    """Test LDAP connection"""
    print("\n=== LDAP Connection Test ===")
    
    try:
        # Create server object
        print("Creating LDAP server object...")
        server = Server(LDAP_SERVER, get_info=ALL, connect_timeout=10)
        print(f"✓ Server object created successfully: {server}")
        
        # Test different authentication methods with proper formats
        auth_methods = [
            ("SIMPLE with full DN", "SIMPLE", LDAP_BIND_DN),
            ("SIMPLE with short DN", "SIMPLE", "CN=svreclappmgr"),
            ("NTLM with domain\\username", NTLM, "hkg\\svreclappmgr"),
            ("SIMPLE with UPN", "SIMPLE", "svreclappmgr@hkg.ho.cncb2"),
        ]
        
        for auth_name, auth_method, user_dn in auth_methods:
            print(f"\n--- Testing: {auth_name} ---")
            print(f"User DN: {user_dn}")
            
            try:
                conn = Connection(
                    server, 
                    user=user_dn, 
                    password=LDAP_BIND_PASSWORD, 
                    authentication=auth_method,
                    auto_bind=False,
                    check_names=True
                )
                
                print(f"Connection object created successfully, attempting to bind...")
                
                if conn.bind():
                    print(f"✓ {auth_name} authentication successful!")
                    
                    # Test search functionality
                    print("Testing search functionality...")
                    try:
                        conn.search(
                            search_base=LDAP_SEARCH_BASE,
                            search_filter='(objectClass=user)',
                            attributes=['sAMAccountName'],
                            search_scope='SUBTREE',
                            size_limit=1
                        )
                        print("✓ Search test successful")
                        
                        # Test specific user search
                        test_user = "testuser"
                        conn.search(
                            search_base=LDAP_SEARCH_BASE,
                            search_filter=f'(sAMAccountName={test_user})',
                            attributes=['sAMAccountName', 'displayName'],
                            search_scope='SUBTREE'
                        )
                        print(f"✓ User search test completed (found {len(conn.entries)} results)")
                        
                    except Exception as search_error:
                        print(f"✗ Search test failed: {search_error}")
                    
                    conn.unbind()
                    return True
                    
                else:
                    print(f"✗ {auth_name} authentication failed: {conn.result}")
                    # Analyze the error
                    if hasattr(conn, 'result') and conn.result:
                        error_code = str(conn.result.get('result', ''))
                        error_message = conn.result.get('message', '')
                        analyze_ldap_error(error_code, error_message)
                    
            except Exception as e:
                print(f"✗ {auth_name} authentication exception: {e}")
        
        print("\n--- Trying additional connection methods ---")
        
        # Try with different server configurations
        try:
            print("Testing with SSL/TLS...")
            ssl_server = Server(LDAP_SERVER.replace('ldap://', 'ldaps://'), get_info=ALL, connect_timeout=10)
            conn = Connection(
                ssl_server, 
                user=LDAP_BIND_DN, 
                password=LDAP_BIND_PASSWORD, 
                authentication="SIMPLE",
                auto_bind=False
            )
            
            if conn.bind():
                print("✓ SSL/TLS connection successful!")
                conn.unbind()
                return True
            else:
                print(f"✗ SSL/TLS connection failed: {conn.result}")
                
        except Exception as e:
            print(f"✗ SSL/TLS connection exception: {e}")
        
        # Try with different search bases
        print("\n--- Testing different search bases ---")
        search_bases = [
            LDAP_SEARCH_BASE,
            "DC=hkg,DC=ho,DC=cncb2",
            "OU=HKG,DC=hkg,DC=ho,DC=cncb2",
            "OU=Admin,OU=HKG,DC=hkg,DC=ho,DC=cncb2"
        ]
        
        for search_base in search_bases:
            try:
                print(f"Testing search base: {search_base}")
                conn = Connection(
                    server, 
                    user=LDAP_BIND_DN, 
                    password=LDAP_BIND_PASSWORD, 
                    authentication="SIMPLE",
                    auto_bind=True
                )
                
                conn.search(
                    search_base=search_base,
                    search_filter='(objectClass=user)',
                    attributes=['sAMAccountName'],
                    search_scope='SUBTREE',
                    size_limit=1
                )
                
                if conn.entries:
                    print(f"✓ Search base {search_base} works!")
                    conn.unbind()
                    return True
                    
            except Exception as e:
                print(f"✗ Search base {search_base} failed: {e}")
        
        return False
        
    except Exception as e:
        print(f"✗ LDAP connection test exception: {e}")
        return False

def test_user_validation():
    """Test user validation"""
    print("\n=== User Validation Test ===")
    
    test_users = ["testuser", "admin", "user"]
    
    try:
        server = Server(LDAP_SERVER, get_info=ALL, connect_timeout=10)
        conn = Connection(
            server, 
            user=LDAP_BIND_DN, 
            password=LDAP_BIND_PASSWORD, 
            authentication="SIMPLE",  # Use SIMPLE instead of NTLM
            auto_bind=True
        )
        
        for user_id in test_users:
            print(f"Validating user: {user_id}")
            try:
                conn.search(
                    search_base=LDAP_SEARCH_BASE,
                    search_filter=f'(sAMAccountName={user_id})',
                    attributes=['sAMAccountName', 'displayName', 'mail'],
                    search_scope='SUBTREE'
                )
                
                if conn.entries:
                    user_entry = conn.entries[0]
                    print(f"✓ User {user_id} exists")
                    print(f"  Display Name: {user_entry.get('displayName', 'N/A')}")
                    print(f"  Email: {user_entry.get('mail', 'N/A')}")
                else:
                    print(f"✗ User {user_id} does not exist")
                    
            except Exception as e:
                print(f"✗ Error validating user {user_id}: {e}")
        
        conn.unbind()
        
    except Exception as e:
        print(f"✗ User validation test failed: {e}")

def main():
    """Main function"""
    print("LDAP Connection Diagnostic Tool")
    print("=" * 50)
    
    # 1. Test network connectivity
    if not test_network_connectivity():
        print("\n Network connection failed, please check:")
        print("   - Firewall settings")
        print("   - Network routing")
        print("   - Server address is correct")
        return
    
    # 2. Test LDAP connection
    if not test_ldap_connection():
        print("\n LDAP connection failed, please check:")
        print("   - LDAP server configuration")
        print("   - Service account credentials")
        print("   - Authentication method settings")
        return
    
    # 3. Test user validation
    test_user_validation()
    
    print("\n Diagnostic completed!")

if __name__ == "__main__":
    main() 