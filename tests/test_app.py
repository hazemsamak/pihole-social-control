import unittest
from unittest.mock import MagicMock, patch
import os

# Set dummy environment variables for testing before importing app
os.environ['APP_PASSWORD'] = 'test_password'
os.environ['FLASK_SECRET_KEY'] = 'test_secret'
os.environ['PIHOLE_URL'] = 'http://localhost:80'
os.environ['PIHOLE_PASSWORD'] = 'test_pi_pass'
os.environ['CLIENT_IP'] = '192.168.1.100'

from app import app


class SocialControlTestCase(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()

    def test_login_page_renders(self):
        """Test login page loads successfully."""
        response = self.client.get('/login')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Welcome', response.data)

    def test_unauthenticated_dashboard_redirects(self):
        """Test accessing root redirects to login when unauthenticated."""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response.headers.get('Location', ''))

    def test_unauthenticated_api_status_returns_401(self):
        """Test accessing API without auth returns 401."""
        response = self.client.get('/api/v1/social/status')
        self.assertEqual(response.status_code, 401)
        data = response.get_json()
        self.assertEqual(data.get('error'), 'Unauthorized')

    def test_login_failure(self):
        """Test login fails with incorrect password."""
        response = self.client.post('/login', data={'password': 'wrong_password'}, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Invalid Password', response.data)

    def test_login_success(self):
        """Test successful login redirects to index."""
        response = self.client.post('/login', data={'password': 'test_password'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers.get('Location'), '/')

    def test_authenticated_index(self):
        """Test authenticated user can access index."""
        with self.client.session_transaction() as sess:
            sess['logged_in'] = True
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Social Control', response.data)

    @patch('app.api.send_notification')
    def test_api_status_mocked(self, mock_notify):
        """Test API status endpoint returns mocked Pi-hole status."""
        mock_pihole = MagicMock()
        mock_pihole.get_status.return_value = 'Blocked'
        self.app.config['PIHOLE_CLIENT'] = mock_pihole

        with self.client.session_transaction() as sess:
            sess['logged_in'] = True

        response = self.client.get('/api/v1/social/status')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {'status': 'Blocked'})

    @patch('app.api.send_notification')
    def test_api_toggle_mocked(self, mock_notify):
        """Test API toggle endpoint triggers block action."""
        mock_pihole = MagicMock()
        mock_pihole.set_social_block.return_value = 'Blocked'
        self.app.config['PIHOLE_CLIENT'] = mock_pihole

        with self.client.session_transaction() as sess:
            sess['logged_in'] = True

        response = self.client.post(
            '/api/v1/social/toggle',
            json={'action': 'block'}
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data.get('success'))
        self.assertEqual(data.get('status'), 'Blocked')
        mock_pihole.set_social_block.assert_called_with('192.168.1.100', enabled=True)
        mock_notify.assert_called_with('Blocked')


if __name__ == '__main__':
    unittest.main()
