
import pytest
from unittest.mock import MagicMock, AsyncMock
from pytest_mock import MockerFixture

@pytest.fixture(scope="session")
def session_mocker(request) -> MockerFixture:
    """Session-scoped mocker fixture."""
    mocker = MockerFixture(request)
    yield mocker
    mocker.stopall()

@pytest.fixture(scope="session", autouse=True)
def mock_db_session_module(session_mocker):
    session_mocker.patch('api_gateway.app.db_session.create_engine')
    session_mocker.patch('api_gateway.app.db_session.sessionmaker')
    session_mocker.patch('api_gateway.app.models.Base.metadata.create_all')

@pytest.fixture(scope="session", autouse=True)
def mock_stt_module_clients(session_mocker):
    # Patch the 'producer' instance directly in the stt module
    mock_producer_instance = MagicMock()
    mock_producer_instance.send.return_value = AsyncMock() # KafkaProducer.send is often async
    mock_producer_instance.flush.return_value = None
    session_mocker.patch('api_gateway.app.routers.stt.producer', mock_producer_instance)

    # Patch the 'minio_client' instance directly in the stt module
    mock_minio_instance = MagicMock()
    mock_minio_instance.bucket_exists.return_value = True
    mock_minio_instance.make_bucket.return_value = None
    mock_minio_instance.put_object.return_value = None
    session_mocker.patch('api_gateway.app.routers.stt.minio_client', mock_minio_instance)
