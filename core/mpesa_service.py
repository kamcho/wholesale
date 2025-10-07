import os
import base64
import json
import logging
import datetime
from datetime import datetime, timedelta
from requests.auth import HTTPBasicAuth
from django.conf import settings
import requests
import pytz

logger = logging.getLogger(__name__)

class MPesaService:
    """
    M-Pesa service with core functionality for STK push payments.
    Uses environment variables for configuration.
    """
    
    def __init__(self):
        """Initialize M-Pesa service with credentials from environment variables."""
        self.consumer_key = getattr(settings, 'MPESA_CONSUMER_KEY', os.getenv('MPESA_CONSUMER_KEY'))
        self.consumer_secret = getattr(settings, 'MPESA_CONSUMER_SECRET', os.getenv('MPESA_CONSUMER_SECRET'))
        self.business_shortcode = getattr(settings, 'MPESA_BUSINESS_SHORTCODE', os.getenv('MPESA_BUSINESS_SHORTCODE'))
        self.passkey = getattr(settings, 'MPESA_PASSKEY', os.getenv('MPESA_PASSKEY'))
        self.callback_url = getattr(settings, 'MPESA_CALLBACK_URL', os.getenv('MPESA_CALLBACK_URL'))
        # Use production URL for live M-Pesa API
        self.base_url = "https://api.safaricom.co.ke"
        
        # Log the initialization (without exposing sensitive data)
        logger.info("Initializing M-Pesa service with the following configuration:")
        logger.info(f"Base URL: {self.base_url}")
        logger.info(f"Business Shortcode: {self.business_shortcode}")
        logger.info(f"Callback URL: {self.callback_url}")
        logger.info(f"Consumer Key: {'*' * 8 + self.consumer_key[-4:] if self.consumer_key else 'Not set'}")
        logger.info(f"Passkey: {'*' * 8 + self.passkey[-4:] if self.passkey else 'Not set'}")
        
        # Debug: Check if credentials are being read correctly
        logger.info(f"Debug - Consumer Key length: {len(self.consumer_key) if self.consumer_key else 0}")
        logger.info(f"Debug - Consumer Secret length: {len(self.consumer_secret) if self.consumer_secret else 0}")
        logger.info(f"Debug - Business Shortcode: {repr(self.business_shortcode)}")
        logger.info(f"Debug - Passkey length: {len(self.passkey) if self.passkey else 0}")
        
        # Validate required credentials
        missing = []
        if not self.consumer_key:
            missing.append("MPESA_CONSUMER_KEY")
        if not self.consumer_secret:
            missing.append("MPESA_CONSUMER_SECRET")
        if not self.business_shortcode:
            missing.append("MPESA_BUSINESS_SHORTCODE")
        if not self.passkey:
            missing.append("MPESA_PASSKEY")
        if not self.callback_url:
            missing.append("MPESA_CALLBACK_URL")
            
        if missing:
            error_msg = f"Missing required M-Pesa credentials: {', '.join(missing)}"
            logger.error(error_msg)
            logger.error("Please set the following environment variables:")
            for cred in missing:
                logger.error(f"  - {cred}")
            logger.error("Or add them to your .env file. See .env.example for reference.")
            # Don't raise an exception, just log the error and continue
            # This allows the app to start but M-Pesa payments will fail gracefully
    
    def _is_html_response(self, response_text):
        """Check if the response is HTML instead of JSON."""
        return response_text.strip().startswith('<')

    def _handle_api_response(self, response):
        """Handle API response and log appropriate messages."""
        try:
            if self._is_html_response(response.text):
                error_msg = "Received HTML response instead of JSON. This usually indicates a server-side issue or maintenance."
                logger.error(f"{error_msg} Response starts with: {response.text[:200]}...")
                return {
                    'error': 'M-Pesa API is currently unavailable. Please try again later.',
                    'error_code': 'API_UNAVAILABLE',
                    'is_html_response': True
                }
                
            return response.json()
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON response: {str(e)}")
            logger.error(f"Response content: {response.text[:500]}")
            return {
                'error': 'Invalid response from payment service',
                'error_code': 'INVALID_RESPONSE',
                'raw_response': response.text
            }

    def generate_access_token(self):
        """Generate access token for M-Pesa API authentication."""
        access_token_url = f'{self.base_url}/oauth/v1/generate?grant_type=client_credentials'
        
        if not self.consumer_key or not self.consumer_secret:
            error_msg = "Cannot generate access token: Missing consumer key or secret"
            logger.error(error_msg)
            return None
            
        try:
            logger.info(f"Requesting access token from: {access_token_url}")
            response = requests.get(
                access_token_url,
                auth=HTTPBasicAuth(self.consumer_key, self.consumer_secret),
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            
            logger.info(f"Access token response status: {response.status_code}")
            
            # Handle HTML responses
            if self._is_html_response(response.text):
                logger.error(f"Received HTML response from M-Pesa API. Status: {response.status_code}")
                logger.error(f"Response: {response.text[:500]}...")
                return None
                
            # Try to parse JSON response
            try:
                response_data = response.json()
            except json.JSONDecodeError:
                logger.error(f"Failed to decode JSON response: {response.text[:500]}...")
                return None
            
            if response.status_code == 200:
                token = response_data.get('access_token')
                print('acces token',token,'\n\n\n\n')
                if token:
                    logger.info("Successfully generated M-Pesa access token")
                    return token
                else:
                    logger.error("No access token in response")
                    logger.error(f"Full response: {response.text}")
            else:
                error_msg = response_data.get('errorMessage') or response_data.get('error') or 'Unknown error'
                logger.error(f"Failed to generate access token. Status: {response.status_code}, Error: {error_msg}")
                
            return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error generating access token: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response content: {e.response.text[:500]}...")
        except Exception as e:
            logger.error(f"Unexpected error generating access token: {str(e)}", exc_info=True)
            
        return None
    
    def generate_password(self, paybill_number=None):
        """
        Generate password for M-Pesa STK push.
        Uses the provided paybill number or falls back to the instance's business shortcode.
        M-Pesa expects the timestamp to be in East Africa Time (UTC+3)
        """
        try:
            # Get current time in UTC+3 (Nairobi timezone)
            from datetime import datetime, timezone, timedelta
            
            # Get current UTC time
            utc_now = datetime.utcnow()
            # Convert to EAT (UTC+3)
            eat_offset = timedelta(hours=3)
            eat_now = utc_now + eat_offset
            
            # Format as string without timezone info (MPesa expects this format)
            timestamp = eat_now.strftime("%Y%m%d%H%M%S")
            
            business_code = paybill_number or self.business_shortcode
            concatenated_string = f"{business_code}{self.passkey}{timestamp}"
            password = base64.b64encode(concatenated_string.encode()).decode('utf-8')
            print(password, timestamp, '\n\n\n\n')  
            # Log for debugging
            logger.info(f"Generated password with timestamp (EAT): {timestamp}")
            logger.debug(f"Password string: {concatenated_string}")
            
            return password, timestamp
            
        except Exception as e:
            logger.error(f"Error generating password: {str(e)}", exc_info=True)
            return None, None
    
    def initiate_stk_push(self, phone_number, amount, account_reference, description="Payment"):
        """
        Initiate STK push payment request.
        
        Args:
            phone_number (str): Customer's phone number (format: 2547XXXXXXXX)
            amount (float): Amount to charge
            account_reference (str): Reference for the transaction
            description (str): Description of the payment
            
        Returns:
            dict: Response from M-Pesa API or error details
        """
        try:
            # Format phone number
            phone = self.process_number(str(phone_number).strip())
            
            # Generate access token and password
            access_token = self.generate_access_token()
            password, timestamp = self.generate_password()
            
            # Log the credentials being used (redact sensitive info in production)
            logger.info(f"Using Business Shortcode: {self.business_shortcode}")
            logger.info(f"Using Passkey: {'*' * (len(self.passkey) - 4) + self.passkey[-4:] if self.passkey else 'None'}")
            logger.info(f"Generated Timestamp: {timestamp}")
            
            if not access_token:
                error_msg = "Failed to generate access token. Please check your M-Pesa credentials."
                logger.error(error_msg)
                return {"error": error_msg, "error_code": "AUTH_ERROR"}
                
            if not password or not timestamp:
                error_msg = "Failed to generate transaction password. Please check your M-Pesa configuration."
                logger.error(error_msg)
                return {"error": error_msg, "error_code": "PASSWORD_GENERATION_ERROR"}
            
            # Prepare request
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            # Ensure amount is an integer (KSH)
            try:
                amount = int(amount)
                if amount <= 0:
                    raise ValueError("Amount must be greater than 0")
            except (ValueError, TypeError) as e:
                error_msg = f"Invalid amount: {amount}. Must be a positive number."
                logger.error(error_msg)
                return {"error": error_msg, "error_code": "INVALID_AMOUNT"}
            from datetime import datetime, timezone, timedelta
            
            # Get current UTC time
            utc_now = datetime.utcnow()
            # Convert to EAT (UTC+3)
            eat_offset = timedelta(hours=3)
            eat_now = utc_now + eat_offset
            
            timestamp = eat_now.strftime("%Y%m%d%H%M%S")
            payload = {
                'BusinessShortCode': self.business_shortcode,
                'Password': password,
                'Timestamp': timestamp,
                'TransactionType': 'CustomerPayBillOnline',
                'Amount': amount,
                'PartyA': phone,
                'PartyB': self.business_shortcode,
                'PhoneNumber': phone,
                'CallBackURL': self.callback_url,
                'AccountReference': account_reference[:12],  # Max 12 chars
                'TransactionDesc': description[:13]  # Max 13 chars
            }
            
            # Log the request (without sensitive data)
            log_payload = payload.copy()
            log_payload['Password'] = '***'
            logger.info(f"Initiating STK push with payload: {log_payload}")
            
            # Make the API request
            url = f"{self.base_url}/mpesa/stkpush/v1/processrequest"
            try:
                response = requests.post(url, json=payload, headers=headers, timeout=30)
                
                # Check for HTML response
                if self._is_html_response(response.text):
                    error_msg = "Received HTML response from M-Pesa API. This usually indicates a server-side issue or maintenance."
                    logger.error(f"{error_msg} Status: {response.status_code}")
                    logger.error(f"Response: {response.text[:500]}...")
                    return {
                        'error': 'M-Pesa API is currently unavailable. Please try again later.',
                        'error_code': 'API_UNAVAILABLE',
                        'is_html_response': True
                    }
                
                try:
                    response_data = response.json()
                except json.JSONDecodeError:
                    error_msg = f"Failed to decode JSON response. Status: {response.status_code}"
                    logger.error(f"{error_msg} Response: {response.text[:500]}...")
                    return {
                        'error': 'Invalid response from payment service',
                        'error_code': 'INVALID_RESPONSE',
                        'raw_response': response.text
                    }
                
                logger.info(f"STK push response: {response.status_code} - {json.dumps(response_data)}")
                
                # Process response
                if response.status_code == 200:
                    if 'ResponseCode' in response_data and response_data['ResponseCode'] == '0':
                        logger.info(f"STK push initiated successfully: {response_data}")
                        return response_data
                    else:
                        error_code = response_data.get('errorCode') or response_data.get('ResponseCode', 'UNKNOWN')
                        error_msg = response_data.get('errorMessage') or response_data.get('ResponseDescription', 'Unknown error')
                        
                        if error_code == '500.001.1001':
                            error_msg = "Invalid M-Pesa API credentials. Please verify your consumer key and secret."
                        
                        logger.error(f"STK push failed with status {response.status_code}: {error_msg} (Code: {error_code})")
                        return {
                            "error": f"Payment request failed: {error_msg}",
                            "error_code": error_code,
                            "raw_response": response_data
                        }
                else:
                    error_msg = f"STK push failed with status {response.status_code}"
                    logger.error(f"{error_msg}. Response: {response.text[:500]}...")
                    return {
                        "error": "Payment service is currently unavailable. Please try again later.",
                        "error_code": f"HTTP_{response.status_code}",
                        "raw_response": response.text
                    }
                    
            except requests.exceptions.RequestException as e:
                error_msg = f"Network error while initiating STK push: {str(e)}"
                logger.error(error_msg)
                if hasattr(e, 'response') and e.response is not None:
                    logger.error(f"Response content: {e.response.text[:500]}...")
                return {
                    "error": "Network error while processing your payment. Please check your internet connection and try again.",
                    "error_code": "NETWORK_ERROR"
                }
                
        except Exception as e:
            error_msg = f"Unexpected error initiating STK push: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                "error": "An unexpected error occurred. Please try again later.",
                "error_code": "INTERNAL_ERROR",
                "debug_info": str(e)
            }
    
    def pull_transactions(self):
        """Pull recent M-Pesa transactions (last 5 hours)."""
        try:
            access_token = self.generate_access_token()
            if not access_token:
                return {"error": "Failed to generate access token"}
                
            url = f"{self.base_url}/pulltransactions/v1/query"
            start_date, end_date = self._get_transaction_dates()
            
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {access_token}'
            }
            
            payload = {
                'ShortCode': self.business_shortcode,
                'StartDate': start_date,
                'EndDate': end_date,
                'OffSetValue': '0'
            }
            
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('ResponseCode') == '1000':
                    return data.get('Response', [])
                return {"error": data.get('ResponseDescription', 'Failed to fetch transactions')}
            else:
                return {"error": f"API request failed: {response.status_code}"}
                
        except Exception as e:
            return {"error": f"Error fetching transactions: {str(e)}"}
    
    def register_callback_url(self, nominated_number=None):
        """Register callback URL for transaction notifications."""
        try:
            access_token = self.generate_access_token()
            if not access_token:
                return {"error": "Failed to generate access token"}
                
            url = f"{self.base_url}/pulltransactions/v1/register"
            
            headers = {
                'Content-Type': 'application/json',
                'Accept-Encoding': 'application/json',
                'Authorization': f'Bearer {access_token}'
            }
            
            payload = {
                "ShortCode": self.business_shortcode,
                "RequestType": "Pull",
                "NominatedNumber": nominated_number or "254742134431",  # Default fallback
                "CallBackURL": self.callback_url
            }
            
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            return response.json()
            
        except Exception as e:
            return {"error": f"Error registering callback URL: {str(e)}"}
    
    @staticmethod
    def process_number(input_str):
        """Format phone number to M-Pesa format (254XXXXXXXXX)."""
        phone = str(input_str).strip()
        if phone.startswith('0'):
            return '254' + phone[1:]
        elif phone.startswith('254'):
            return phone
        return phone  # Return as is if format is not recognized
    
    def _get_transaction_dates(self):
        """Get date range for transaction queries (last 5 hours)."""
        try:
            kenya_timezone = pytz.timezone("Africa/Nairobi")
            now_kenya = datetime.now(pytz.utc).astimezone(kenya_timezone)
            five_hours_ago = now_kenya - timedelta(hours=5)
            
            start = five_hours_ago.strftime("%Y-%m-%d %H:%M:%S")
            end = now_kenya.strftime("%Y-%m-%d %H:%M:%S")
            
            return start, end
            
        except Exception as e:
            logger.error(f"Error generating transaction dates: {str(e)}")
            # Fallback to default values
            return (datetime.now() - timedelta(hours=5)).strftime("%Y-%m-%d %H:%M:%S"), \
                   datetime.now().strftime("%Y-%m-%d %H:%M:%S")
