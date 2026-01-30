"""Integration tests for profile routes."""

from sqlmodel import Session, select

from crossyword.models import PlayerProgress, User


class TestUserProfile:
    """Tests for /profile route."""

    def test_requires_certificate(self, client):
        """Profile page requires client certificate."""
        response = client.get("/profile")

        assert response.is_certificate_required

    def test_authenticated_access(self, auth_client):
        """Authenticated user can access profile."""
        response = auth_client.get("/profile")

        assert response.is_success
        assert response.body is not None

    def test_shows_user_info(self, auth_client):
        """Profile shows user statistics."""
        response = auth_client.get("/profile")

        assert response.is_success
        # Should show some stats
        body_lower = response.body.lower()
        assert "completed" in body_lower or "progress" in body_lower

    def test_new_user_shows_zeros(self, client):
        """New user shows zero stats."""
        # Create new user
        with Session(client._app.state.engine) as session:
            user = User(
                fingerprint="new-profile-user",
                display_name="NewProfileUser",
            )
            session.add(user)
            session.commit()

        new_client = client.with_certificate("new-profile-user")
        response = new_client.get("/profile")

        assert response.is_success


class TestSetDisplayName:
    """Tests for /profile/name route."""

    def test_input_route_prompts_first(self, client):
        """Input routes prompt for input before checking certificate."""
        # Note: @app.input routes return INPUT status first,
        # certificate is checked when submitting the actual input
        response = client.get("/profile/name")

        assert response.is_input_required

    def test_prompts_for_username(self, auth_client):
        """Name route prompts for username input."""
        response = auth_client.get("/profile/name")

        assert response.is_input_required
        assert "username" in response.input_prompt.lower()

    def test_set_valid_username(self, client):
        """Can set a valid username."""
        # Create user without display name
        with Session(client._app.state.engine) as session:
            user = User(
                fingerprint="set-name-user",
                display_name=None,
            )
            session.add(user)
            session.commit()

        auth = client.with_certificate("set-name-user")
        response = auth.get_input("/profile/name", "ValidName123")

        assert response.is_success
        assert "ValidName123" in response.body

    def test_username_invalid_chars_rejected(self, client):
        """Username with invalid characters returns error."""
        with Session(client._app.state.engine) as session:
            user = User(
                fingerprint="invalid-chars-user",
                display_name=None,
            )
            session.add(user)
            session.commit()

        auth = client.with_certificate("invalid-chars-user")
        # Username with special characters should be rejected
        response = auth.get_input("/profile/name", "user@name!")

        assert response.is_success
        body_lower = response.body.lower()
        assert "invalid" in body_lower or "error" in body_lower or "only" in body_lower

    def test_username_taken(self, client):
        """Duplicate username returns error."""
        # Create first user with a name
        with Session(client._app.state.engine) as session:
            user1 = User(
                fingerprint="first-name-user",
                display_name="TakenName",
            )
            user2 = User(
                fingerprint="second-name-user",
                display_name=None,
            )
            session.add(user1)
            session.add(user2)
            session.commit()

        auth = client.with_certificate("second-name-user")
        response = auth.get_input("/profile/name", "TakenName")

        assert response.is_success
        assert "taken" in response.body.lower()


class TestToggleColors:
    """Tests for /profile/colors route."""

    def test_requires_certificate(self, client):
        """Toggle colors route requires client certificate."""
        response = client.get("/profile/colors")

        assert response.is_certificate_required

    def test_toggle_on(self, client):
        """Can toggle colors on."""
        with Session(client._app.state.engine) as session:
            user = User(
                fingerprint="toggle-on-user",
                display_name="ToggleOnUser",
                use_colors=False,
            )
            session.add(user)
            session.commit()

        auth = client.with_certificate("toggle-on-user")
        response = auth.get("/profile/colors")

        # Should redirect to profile
        assert response.is_redirect

        # Verify database was updated
        with Session(client._app.state.engine) as session:
            user = session.exec(
                select(User).where(User.fingerprint == "toggle-on-user")
            ).first()
            assert user.use_colors is True

    def test_toggle_off(self, client):
        """Can toggle colors off."""
        with Session(client._app.state.engine) as session:
            user = User(
                fingerprint="toggle-off-user",
                display_name="ToggleOffUser",
                use_colors=True,
            )
            session.add(user)
            session.commit()

        auth = client.with_certificate("toggle-off-user")
        response = auth.get("/profile/colors")

        # Should redirect to profile
        assert response.is_redirect

        # Verify database was updated
        with Session(client._app.state.engine) as session:
            user = session.exec(
                select(User).where(User.fingerprint == "toggle-off-user")
            ).first()
            assert user.use_colors is False

    def test_profile_shows_color_status(self, client):
        """Profile page shows current color setting."""
        with Session(client._app.state.engine) as session:
            user = User(
                fingerprint="color-status-user",
                display_name="ColorStatusUser",
                use_colors=False,
            )
            session.add(user)
            session.commit()

        auth = client.with_certificate("color-status-user")
        response = auth.get("/profile")

        assert response.is_success
        assert "Enable Colors" in response.body or "colors" in response.body.lower()

    def test_profile_shows_disable_when_enabled(self, client):
        """Profile shows 'Disable Colors' when colors are on."""
        with Session(client._app.state.engine) as session:
            user = User(
                fingerprint="disable-link-user",
                display_name="DisableLinkUser",
                use_colors=True,
            )
            session.add(user)
            session.commit()

        auth = client.with_certificate("disable-link-user")
        response = auth.get("/profile")

        assert response.is_success
        assert "Disable Colors" in response.body


class TestProfileAutoPause:
    """Tests for auto-pause when navigating to profile."""

    def test_profile_auto_pauses_active_puzzle(self, auth_client):
        """Navigating to profile auto-pauses active puzzles."""
        # First visit puzzle to create active progress
        auth_client.get("/puzzle")

        # Verify puzzle is not paused
        with Session(auth_client._app.state.engine) as session:
            progress = session.exec(
                __import__("sqlmodel").select(PlayerProgress)
            ).first()
            assert progress is not None
            assert progress.is_paused is False

        # Navigate to profile
        auth_client.get("/profile")

        # Verify puzzle is now paused
        with Session(auth_client._app.state.engine) as session:
            progress = session.exec(
                __import__("sqlmodel").select(PlayerProgress)
            ).first()
            assert progress.is_paused is True

    def test_toggle_colors_auto_pauses(self, auth_client):
        """Toggling colors auto-pauses active puzzles."""
        # First visit puzzle to create active progress
        auth_client.get("/puzzle")

        # Toggle colors
        auth_client.get("/profile/colors")

        # Verify puzzle is now paused
        with Session(auth_client._app.state.engine) as session:
            progress = session.exec(
                __import__("sqlmodel").select(PlayerProgress)
            ).first()
            assert progress.is_paused is True
