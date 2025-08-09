"""
Main test module for Opitios Alpaca Trading API.
Basic unit tests that don't require API credentials.
"""
import pytest
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class TestBasicImports:
    """Test basic imports and module loading."""

    def test_main_module_import(self):
        """Test that main module can be imported."""
        try:
            import main
            assert hasattr(main, 'app')
            print("✅ Main module imported successfully")
        except ImportError as e:
            pytest.fail(f"Failed to import main module: {e}")

    def test_app_module_import(self):
        """Test that app modules can be imported."""
        try:
            from app import routes, models, middleware
            print("✅ App modules imported successfully")
        except ImportError as e:
            pytest.fail(f"Failed to import app modules: {e}")

    def test_config_import(self):
        """Test that config module can be imported."""
        try:
            import config
            assert hasattr(config, 'Config')
            print("✅ Config module imported successfully")
        except ImportError as e:
            pytest.fail(f"Failed to import config module: {e}")


class TestConfiguration:
    """Test configuration loading."""

    def test_config_class_exists(self):
        """Test that Config class exists and has required attributes."""
        from config import Config
        
        # Check that Config class has basic attributes
        assert hasattr(Config, 'ALPACA_API_KEY')
        assert hasattr(Config, 'ALPACA_SECRET_KEY')
        assert hasattr(Config, 'PAPER_TRADING')
        print("✅ Config class has required attributes")

    def test_secrets_file_structure(self, secrets_file_path):
        """Test that secrets file has correct structure."""
        if not secrets_file_path.exists():
            pytest.skip("Secrets file not found - this is expected in CI")
        
        import yaml
        try:
            with open(secrets_file_path, 'r') as f:
                secrets = yaml.safe_load(f)
            
            # Check basic structure
            assert 'accounts' in secrets
            assert isinstance(secrets['accounts'], dict)
            print("✅ Secrets file has correct structure")
            
        except Exception as e:
            pytest.fail(f"Failed to load secrets file: {e}")


class TestAppStructure:
    """Test application structure."""

    def test_app_directory_structure(self, project_root_path):
        """Test that required directories exist."""
        required_dirs = ['app', 'static', 'docs']
        
        for dir_name in required_dirs:
            dir_path = project_root_path / dir_name
            assert dir_path.exists(), f"Required directory '{dir_name}' not found"
        
        print("✅ Required directories exist")

    def test_app_modules_exist(self, project_root_path):
        """Test that required app modules exist."""
        app_dir = project_root_path / 'app'
        required_modules = [
            'routes.py', 'models.py', 'middleware.py', 
            'alpaca_client.py', 'connection_pool.py'
        ]
        
        for module_name in required_modules:
            module_path = app_dir / module_name
            assert module_path.exists(), f"Required module '{module_name}' not found"
        
        print("✅ Required app modules exist")


class TestHealthCheck:
    """Test basic health check functionality."""

    def test_health_check_function_exists(self):
        """Test that health check function exists."""
        try:
            from app.routes import health_check
            assert callable(health_check)
            print("✅ Health check function exists")
        except ImportError:
            pytest.fail("Health check function not found")

    def test_basic_app_creation(self):
        """Test that FastAPI app can be created."""
        try:
            from main import app
            assert app is not None
            assert hasattr(app, 'routes')
            print("✅ FastAPI app created successfully")
        except Exception as e:
            pytest.fail(f"Failed to create FastAPI app: {e}")


if __name__ == "__main__":
    # Run tests when executed directly
    pytest.main([__file__, "-v"])