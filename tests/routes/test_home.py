"""Integration tests for home routes."""


class TestHomePage:
    """Tests for / route."""

    def test_unauthenticated_access(self, client):
        """Home page is accessible without authentication."""
        response = client.get("/")

        assert response.is_success
        assert response.body is not None
        assert "Crossyword" in response.body or "CROSSY" in response.body

    def test_authenticated_access(self, auth_client):
        """Home page shows user info when authenticated."""
        response = auth_client.get("/")

        assert response.is_success
        assert response.body is not None

    def test_shows_logo(self, client):
        """Home page displays the crossword logo."""
        response = client.get("/")

        assert response.is_success
        # Logo contains grid characters
        assert "+" in response.body
        assert "|" in response.body


class TestHelpPage:
    """Tests for /help route."""

    def test_help_accessible(self, client):
        """Help page is accessible without authentication."""
        response = client.get("/help")

        assert response.is_success
        assert response.body is not None

    def test_help_contains_instructions(self, client):
        """Help page contains game instructions."""
        response = client.get("/help")

        assert response.is_success
        # Help page should mention how to play
        body_lower = response.body.lower()
        assert "puzzle" in body_lower or "clue" in body_lower or "play" in body_lower
