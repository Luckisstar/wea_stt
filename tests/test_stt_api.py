
import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, MagicMock
from api_gateway.app.main import app  # Assuming your FastAPI app is named 'app' in main.py
from api_gateway.app import auth, models



# Mock get_db dependency
@pytest.fixture
def mock_db_session(mocker):
    mock_session = mocker.MagicMock()
    mocker.patch('api_gateway.app.db_session.get_db', return_value=mock_session)
    return mock_session

# Mock get_current_active_user dependency
@pytest.fixture
def mock_current_user(mocker):
    mock_user = models.User(username="test_user", email="test@example.com", hashed_password="hashed_password", is_active=True)
    mocker.patch('api_gateway.app.auth.get_current_active_user', return_value=mock_user)
    return mock_user



@pytest.mark.asyncio
async def test_create_transcription_success(mock_minio_client, mock_kafka_producer, mock_db_session, mock_current_user):
    async with AsyncClient(app=app, base_url="http://test") as ac:
        # Mock authentication (YOUR_TEST_TOKEN is not actually used due to mock_current_user)
        headers = {"Authorization": "Bearer YOUR_TEST_TOKEN"} 

        # Create a dummy audio file
        audio_content = b"RIFF\x00\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00D\xac\x00\x00\x80\xbb\x00\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
        files = {"file": ("test_audio.wav", audio_content, "audio/wav")}
        data = {"model": "base", "language": "en"}

        response = await ac.post("/v1/audio/transcriptions", headers=headers, files=files, data=data)
        assert response.status_code == 200
        assert "text" in response.json()
        assert response.json()["text"] == "Transcription in progress..."
        mock_minio_client.put_object.assert_called_once()
        mock_kafka_producer.send.assert_called_once()
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()

@pytest.mark.asyncio
async def test_create_transcription_no_file(mock_minio_client, mock_kafka_producer, mock_db_session, mock_current_user):
    async with AsyncClient(app=app, base_url="http://test") as ac:
        headers = {"Authorization": "Bearer YOUR_TEST_TOKEN"}
        data = {"model": "base", "language": "en"}
        response = await ac.post("/v1/audio/transcriptions", headers=headers, data=data)
        assert response.status_code == 422  # Unprocessable Entity (validation error)

@pytest.mark.asyncio
async def test_create_transcription_invalid_model(mock_minio_client, mock_kafka_producer, mock_db_session, mock_current_user):
    async with AsyncClient(app=app, base_url="http://test") as ac:
        headers = {"Authorization": "Bearer YOUR_TEST_TOKEN"}
        audio_content = b"dummy_audio_content"
        files = {"file": ("test_audio.wav", audio_content, "audio/wav")}
        data = {"model": "invalid_model", "language": "en"}
        response = await ac.post("/v1/audio/transcriptions", headers=headers, files=files, data=data)
        assert response.status_code == 422  # Unprocessable Entity (validation error)

@pytest.mark.asyncio
async def test_create_transcription_unauthenticated():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        audio_content = b"dummy_audio_content"
        files = {"file": ("test_audio.wav", audio_content, "audio/wav")}
        data = {"model": "base", "language": "en"}
        response = await ac.post("/v1/audio/transcriptions", files=files, data=data)
        assert response.status_code == 401  # Unauthorized
