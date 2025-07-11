import asyncio
from typing import Dict, List
from fastapi import WebSocket

class ConnectionManager:
    """
    WebSocket 연결을 관리하는 중앙 관리자 클래스.
    - 활성 연결 저장 및 관리
    - 특정 클라이언트에게 메시지 전송
    - 모든 클라이언트에게 메시지 브로드캐스트
    """
    def __init__(self):
        # 활성 연결을 저장하는 딕셔너리. {client_id: WebSocket} 형태로 저장됩니다.
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        """새로운 WebSocket 연결을 수락하고 저장합니다."""
        await websocket.accept()
        self.active_connections[client_id] = websocket
        print(f"New connection: Client #{client_id} connected.")

    def disconnect(self, client_id: str):
        """WebSocket 연결을 해제하고 저장소에서 제거합니다."""
        if client_id in self.active_connections:
            # WebSocket 객체를 pop하여 연결을 명시적으로 닫을 필요는 없습니다.
            # FastAPI가 disconnect 시 자동으로 처리해줍니다.
            del self.active_connections[client_id]
            print(f"Connection closed: Client #{client_id} disconnected.")

    async def send_personal_message(self, message: dict, client_id: str):
        """특정 클라이언트에게 JSON 형태의 개인 메시지를 보냅니다."""
        if client_id in self.active_connections:
            websocket = self.active_connections[client_id]
            try:
                await websocket.send_json(message)
                print(f"Message sent to client #{client_id}: {message}")
            except Exception as e:
                # 클라이언트와의 연결이 비정상적으로 끊어졌을 경우 예외가 발생할 수 있습니다.
                print(f"Error sending message to client #{client_id}: {e}")
                self.disconnect(client_id)
    
    async def broadcast(self, message: dict):
        """연결된 모든 클라이언트에게 메시지를 브로드캐스트합니다."""
        # 동시에 여러 클라이언트에게 메시지를 보내기 위해 asyncio.gather를 사용합니다.
        tasks = [
            self.send_personal_message(message, client_id)
            for client_id in self.active_connections
        ]
        if tasks:
            await asyncio.gather(*tasks)
            print(f"Broadcast message to all clients: {message}")

# --- 싱글턴 인스턴스 ---
# 애플리케이션 전체에서 단 하나의 ConnectionManager 인스턴스를 사용하도록 만듭니다.
manager = ConnectionManager()