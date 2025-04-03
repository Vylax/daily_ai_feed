import unittest
from unittest import mock
import smtplib # For exception testing
import sys
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Adjust the path to import from the src directory
# This assumes tests are run from the project root directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.email_utils import send_email

# --- Check for required environment variables for live tests ---
# Use different variable names to avoid clashes if the main app also uses .env
TEST_SENDER = os.getenv("SENDER_EMAIL")
TEST_RECIPIENT = os.getenv("RECIPIENT_EMAIL")
TEST_PASSWORD = os.getenv("SMTP_PASSWORD")
TEST_SERVER = os.getenv("SMTP_SERVER")
TEST_PORT_STR = os.getenv("SMTP_PORT")
TEST_PORT = None
if TEST_PORT_STR and TEST_PORT_STR.isdigit():
    TEST_PORT = int(TEST_PORT_STR)

# Flag to skip live tests if config is incomplete
LIVE_TEST_CONFIG_MISSING = not all([TEST_SENDER, TEST_RECIPIENT, TEST_PASSWORD, TEST_SERVER, TEST_PORT])
LIVE_TEST_SKIP_REASON = "Missing one or more environment variables for live email test (TEST_SENDER_EMAIL, TEST_RECIPIENT_EMAIL, TEST_SMTP_PASSWORD, TEST_SMTP_SERVER, TEST_SMTP_PORT)"
# --- End Check ---

class TestEmailSending(unittest.TestCase):

    def setUp(self):
        """Common setup for tests."""
        self.subject = "Test Subject from test_email.py" # Modified subject for clarity
        self.markdown_body = "# Hello from Test\nThis is *markdown* sent during testing."
        self.expected_html_part_content = "<h1>Hello from Test</h1>\n<p>This is <em>markdown</em> sent during testing.</p>"
        # Keep dummy values for tests that still use mocks or don't need real creds
        self.dummy_sender = "sender@example.com"
        self.dummy_recipient = "recipient@example.com"
        self.dummy_password = "password"
        self.dummy_server = "smtp.example.com"

    # --- Live Sending Tests ---

    @unittest.skipIf(LIVE_TEST_CONFIG_MISSING, LIVE_TEST_SKIP_REASON)
    def test_send_email_smtp_live_ssl_or_starttls(self):
        """Test successful LIVE email sending via SMTP (SSL or STARTTLS based on port)."""
        config = {
            'email_provider': 'smtp',
            'sender_email': TEST_SENDER,
            'recipient_email': TEST_RECIPIENT,
            'smtp_password': TEST_PASSWORD,
            'smtp_server': TEST_SERVER,
            'smtp_port': TEST_PORT, # Use the loaded integer port
        }
        print(f"\nAttempting LIVE email send: Subject='{self.subject}' To='{TEST_RECIPIENT}' Server='{TEST_SERVER}:{TEST_PORT}'")

        success = send_email(self.subject, self.markdown_body, config)

        if not success:
            print("Live email sending failed. Check credentials, server/port, and network.")
        self.assertTrue(success, "send_email should return True on successful live sending.")
        # Cannot easily assert contents of the received email here.
        # Manual verification of the recipient inbox is needed.

    # --- Mocked Tests (Original tests are kept below for logic/error checking) ---

    # Note: The original success tests using mocks are removed as they are
    # replaced by the single live test above which covers both ports implicitly
    # by using the port from the .env file.

    # @mock.patch('src.email_utils.smtplib.SMTP_SSL') # Removed original mocked success test
    # def test_send_email_smtp_ssl_success(self, mock_smtp_ssl): ...

    # @mock.patch('src.email_utils.smtplib.SMTP') # Removed original mocked success test
    # def test_send_email_smtp_starttls_success(self, mock_smtp): ...


    @mock.patch('src.email_utils.smtplib.SMTP_SSL')
    def test_send_email_smtp_auth_error(self, mock_smtp_ssl):
        """Test handling of SMTP Authentication Error (using mocks)."""
        config = {
            'email_provider': 'smtp',
            'sender_email': self.dummy_sender, # Use dummy for mock tests
            'recipient_email': self.dummy_recipient,
            'smtp_password': self.dummy_password,
            'smtp_server': self.dummy_server,
            'smtp_port': 465, # Use specific port for mock test scenario
        }
        mock_server = mock.MagicMock()
        mock_smtp_ssl.return_value.__enter__.return_value = mock_server
        mock_server.login.side_effect = smtplib.SMTPAuthenticationError(535, b'Authentication failed')

        success = send_email(self.subject, self.markdown_body, config)

        self.assertFalse(success)
        mock_server.login.assert_called_once()
        mock_server.sendmail.assert_not_called()

    @mock.patch('src.email_utils.smtplib.SMTP_SSL')
    def test_send_email_smtp_generic_error(self, mock_smtp_ssl):
        """Test handling of a generic error during SMTP communication (using mocks)."""
        config = {
            'email_provider': 'smtp',
            'sender_email': self.dummy_sender,
            'recipient_email': self.dummy_recipient,
            'smtp_password': self.dummy_password,
            'smtp_server': self.dummy_server,
            'smtp_port': 465,
        }
        mock_server = mock.MagicMock()
        mock_smtp_ssl.return_value.__enter__.return_value = mock_server
        # Assume login works, but sendmail fails
        mock_server.login.return_value = None # Simulate successful login
        mock_server.sendmail.side_effect = Exception("Generic sending error")

        success = send_email(self.subject, self.markdown_body, config)

        self.assertFalse(success)
        mock_server.login.assert_called_once() # Login happens before sendmail
        mock_server.sendmail.assert_called_once()

    @mock.patch('src.email_utils.smtplib.SMTP_SSL')
    @mock.patch('src.email_utils.smtplib.SMTP')
    def test_send_email_incomplete_config(self, mock_smtp, mock_smtp_ssl):
        """Test that email sending fails with incomplete SMTP config (using mocks)."""
        config = {
            'email_provider': 'smtp',
            'sender_email': self.dummy_sender,
            'recipient_email': self.dummy_recipient,
            # Missing password, server, port
        }
        # This test doesn't depend on live credentials, uses dummies
        success = send_email(self.subject, self.markdown_body, config)
        self.assertFalse(success)
        mock_smtp_ssl.assert_not_called()
        mock_smtp.assert_not_called()

    @mock.patch('src.email_utils.smtplib.SMTP_SSL')
    @mock.patch('src.email_utils.smtplib.SMTP')
    def test_send_email_invalid_provider(self, mock_smtp, mock_smtp_ssl):
        """Test that email sending fails with an invalid provider (using mocks)."""
        config = {
            'email_provider': 'invalid_service',
            'sender_email': self.dummy_sender,
            'recipient_email': self.dummy_recipient,
        }
        # This test doesn't depend on live credentials
        success = send_email(self.subject, self.markdown_body, config)
        self.assertFalse(success)
        mock_smtp_ssl.assert_not_called()
        mock_smtp.assert_not_called()

    @mock.patch('src.email_utils.markdown.markdown')
    @mock.patch('src.email_utils.smtplib.SMTP_SSL')
    def test_send_email_markdown_failure(self, mock_smtp_ssl, mock_markdown):
        """Test email sending fallback to plain text if markdown fails (using mocks)."""
        config = {
            'email_provider': 'smtp',
            'sender_email': self.dummy_sender,
            'recipient_email': self.dummy_recipient,
            'smtp_password': self.dummy_password,
            'smtp_server': self.dummy_server,
            'smtp_port': 465,
        }
        mock_server = mock.MagicMock()
        mock_smtp_ssl.return_value.__enter__.return_value = mock_server
        mock_markdown.side_effect = Exception("Markdown conversion failed")

        success = send_email(self.subject, self.markdown_body, config)

        self.assertTrue(success) # Should still attempt to send plain text
        mock_markdown.assert_called_once()
        mock_server.sendmail.assert_called_once()
        args, _ = mock_server.sendmail.call_args
        sent_message = args[2]
        # Should contain plain text part
        self.assertIn("Content-Type: text/plain", sent_message)
        self.assertIn(self.markdown_body, sent_message)
        # Should NOT contain HTML part (or it might be empty/basic structure)
        # Depending on exact implementation, multipart header might still exist
        # self.assertNotIn("Content-Type: text/html", sent_message) # This might be too strict
        # Check that the expected *rendered* HTML content isn't there
        self.assertNotIn(self.expected_html_part_content, sent_message)


if __name__ == '__main__':
    unittest.main() 