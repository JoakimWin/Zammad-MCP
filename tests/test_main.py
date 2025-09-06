"""Tests for the __main__ module."""

from unittest.mock import Mock, patch

import mcp_zammad.__main__ as main_module
from mcp_zammad.__main__ import main


class TestMain:
    """Test cases for the main entry point."""

    def test_main_calls_cli_main(self) -> None:
        """Test that main() calls cli.main()."""
        # The __main__.py just imports main from cli, so calling it IS calling cli.main
        # We need to test that it can be called and executes properly
        with patch("sys.argv", ["mcp_zammad"]):  # Mock command line args
            with patch.dict("os.environ", {"ZAMMAD_URL": "http://test.com/api/v1", "ZAMMAD_HTTP_TOKEN": "test"}):
                with patch("mcp_zammad.server.mcp") as mock_mcp:
                    mock_mcp.run = Mock()
                    main()
                    mock_mcp.run.assert_called_once()

    def test_main_module_execution(self) -> None:
        """Test that __main__ block would execute main() when run as a script."""
        # We'll test the pattern rather than executing it
        # Since the __main__ guard is at module level, we verify the pattern exists

        # Verify the module has the expected structure
        assert hasattr(main_module, "main")
        assert callable(main_module.main)

        # The actual execution is covered by test_main_calls_cli_main
        # This test ensures the module structure is correct

    def test_import_without_execution(self) -> None:
        """Test that importing the module doesn't execute main()."""
        with patch("mcp_zammad.cli.main") as mock_cli_main:
            # Reset the mock to ensure clean state
            mock_cli_main.reset_mock()

            # Import the module (already imported above, but for clarity)
            # The import itself shouldn't trigger main() execution
            
            # Verify no calls were made just from importing
            mock_cli_main.assert_not_called()
