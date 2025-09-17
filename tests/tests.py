# test_app.py

import unittest
import requests
import json
import time

class TestAPI(unittest.TestCase):
    
    # The base URL for the running Flask application
    BASE_URL = "http://127.0.0.1:7860"

    # We will store credentials and tokens here to use across different tests
    user_credentials = {
        "name": "Test User",
        "email": f"testuser_{int(time.time())}@example.com", # Unique email every run
        "password": "testpassword123",
        "account_type": "volunteer"
    }
    
    # Class-level variables to store tokens
    access_token = None
    refresh_token = None

    def test_1_signup(self):
        """
        Test Case 1: User Signup
        - Tries to create a new user.
        - Checks for a successful 201 status code.
        - Checks if the response contains user data and tokens.
        - Tries to create the SAME user again.
        - Checks for a 400 error indicating the user already exists.
        """
        print("\n--- Running Test: User Signup ---")
        
        # --- Test 1.1: Successful Signup ---
        print("Testing successful signup...")
        signup_url = f"{self.BASE_URL}/signup/"
        response = requests.post(signup_url, json=self.user_credentials)
        
        # Assert the request was successful
        self.assertEqual(response.status_code, 201, f"Expected 201, got {response.status_code}")
        
        # Assert the response has the expected keys
        data = response.json()
        self.assertIn('user', data)
        self.assertIn('access_token', data)
        self.assertIn('refresh_token', data)
        self.assertEqual(data['user']['email'], self.user_credentials['email'])
        print("Success: User created and tokens received.")

        # --- Test 1.2: Signup with existing email ---
        print("Testing signup with an email that already exists...")
        response_fail = requests.post(signup_url, json=self.user_credentials)
        
        self.assertEqual(response_fail.status_code, 400, f"Expected 400, got {response_fail.status_code}")
        self.assertIn('error', response_fail.json())
        self.assertEqual(response_fail.json()['error'], 'User with this email already exists')
        print("Success: Server correctly blocked duplicate user creation.")

    def test_2_login(self):
        """
        Test Case 2: User Login
        - Tries to log in with incorrect credentials.
        - Checks for a 401 Unauthorized error.
        - Tries to log in with correct credentials.
        - Checks for a successful 200 status code.
        - Stores the access and refresh tokens for subsequent tests.
        """
        print("\n--- Running Test: User Login ---")
        login_url = f"{self.BASE_URL}/login/"

        # --- Test 2.1: Login with incorrect password ---
        print("Testing login with incorrect credentials...")
        invalid_creds = {
            "email": self.user_credentials['email'],
            "password": "wrongpassword"
        }
        response_fail = requests.post(login_url, json=invalid_creds)
        
        self.assertEqual(response_fail.status_code, 401, f"Expected 401, got {response_fail.status_code}")
        print("Success: Server correctly blocked login with wrong password.")
        
        # --- Test 2.2: Login with correct credentials ---
        print("Testing login with correct credentials...")
        valid_creds = {
            "email": self.user_credentials['email'],
            "password": self.user_credentials['password']
        }
        response_success = requests.post(login_url, json=valid_creds)
        
        self.assertEqual(response_success.status_code, 200, f"Expected 200, got {response_success.status_code}")
        data = response_success.json()
        self.assertIn('access_token', data)
        self.assertIn('refresh_token', data)
        
        # Store tokens for the next tests
        TestAPI.access_token = data['access_token']
        TestAPI.refresh_token = data['refresh_token']
        self.assertIsNotNone(TestAPI.access_token)
        self.assertIsNotNone(TestAPI.refresh_token)
        print("Success: User logged in and tokens stored.")

    def test_3_protected_endpoint_access(self):
        """
        Test Case 3: Accessing a Protected Route
        - Tries to access /profile/ without a token.
        - Checks for a 401 Unauthorized error.
        - Tries to access /profile/ with a valid access token.
        - Checks for a successful 200 status code.
        """
        print("\n--- Running Test: Protected Endpoint Access ---")
        profile_url = f"{self.BASE_URL}/profile/"
        
        # --- Test 3.1: Access without token ---
        print("Testing access without an authentication token...")
        response_fail = requests.get(profile_url)
        
        self.assertEqual(response_fail.status_code, 401, f"Expected 401, got {response_fail.status_code}")
        print("Success: Server correctly denied access without a token.")

        # --- Test 3.2: Access with valid token ---
        print("Testing access with a valid token...")
        headers = {'Authorization': f'Bearer {TestAPI.access_token}'}
        response_success = requests.get(profile_url, headers=headers)
        
        self.assertEqual(response_success.status_code, 200, f"Expected 200, got {response_success.status_code} - {response_success.text}")
        data = response_success.json()
        self.assertIn('user', data)
        self.assertEqual(data['user']['email'], self.user_credentials['email'])
        print("Success: Server granted access with a valid token.")

# IN test_app.py

    def test_4_token_refresh(self):
        """
        Test Case 4: Refreshing an Access Token
        - Uses the refresh token from login to get a new access token.
        - Checks for a successful 200 status code.
        - Verifies that new tokens are returned.
        """
        print("\n--- Running Test: Token Refresh ---")
        refresh_url = f"{self.BASE_URL}/token/refresh/"
        
        # Add this line to wait for 1 second
        time.sleep(1) 
        
        payload = {'refresh_token': TestAPI.refresh_token}
        response = requests.post(refresh_url, json=payload)
        
        self.assertEqual(response.status_code, 200, f"Expected 200, got {response.status_code}")
        data = response.json()
        self.assertIn('access_token', data)
        self.assertIn('refresh_token', data)
        self.assertNotEqual(TestAPI.access_token, data['access_token'], "New access token should be different.")
        
        # Update tokens for any subsequent tests
        TestAPI.access_token = data['access_token']
        print("Success: Tokens were refreshed successfully.")

    def test_5_logout(self):
        """
        Test Case 5: User Logout
        - Tries to access the logout endpoint with a valid token.
        - Checks for a successful 200 status code.
        """
        print("\n--- Running Test: User Logout ---")
        logout_url = f"{self.BASE_URL}/logout/"
        headers = {'Authorization': f'Bearer {TestAPI.access_token}'}
        
        response = requests.post(logout_url, headers=headers)
        
        self.assertEqual(response.status_code, 200, f"Expected 200, got {response.status_code}")
        data = response.json()
        self.assertEqual(data['message'], 'Successfully logged out')
        print("Success: Logout endpoint responded correctly.")

if __name__ == '__main__':
    # Ensure the server is running before starting the tests
    print("Starting the API test suite...")
    print(f"Make sure the Flask server is running at {TestAPI.BASE_URL}")
    print("="*70)
    unittest.main()