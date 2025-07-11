import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { BrowserRouter as Router, Routes, Route, Link, Navigate } from 'react-router-dom';
import StatisticsPage from './components/StatisticsPage';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

// Dummy authentication for now
const isAuthenticated = () => {
  // In a real app, this would check for a valid token or session
  return localStorage.getItem('token') !== null;
};

const LoginPage = ({ setToken }) => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  const handleLogin = async (e) => {
    e.preventDefault();
    try {
      const response = await axios.post(`${API_BASE_URL}/v1/auth/login`, new URLSearchParams({
        username: username,
        password: password,
      }), {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded'
        }
      });
      localStorage.setItem('token', response.data.access_token);
      setToken(response.data.access_token);
      setError('');
    } catch (err) {
      setError('Invalid credentials');
      console.error("Login failed:", err);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-100">
      <div className="bg-white p-8 rounded-lg shadow-md w-full max-w-md">
        <h2 className="text-2xl font-bold mb-6 text-center">Login</h2>
        <form onSubmit={handleLogin}>
          <div className="mb-4">
            <label className="block text-gray-700 text-sm font-bold mb-2" htmlFor="username">Username</label>
            <input
              type="text"
              id="username"
              className="shadow appearance-none border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
            />
          </div>
          <div className="mb-6">
            <label className="block text-gray-700 text-sm font-bold mb-2" htmlFor="password">Password</label>
            <input
              type="password"
              id="password"
              className="shadow appearance-none border rounded w-full py-2 px-3 text-gray-700 mb-3 leading-tight focus:outline-none focus:shadow-outline"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          {error && <p className="text-red-500 text-xs italic mb-4">{error}</p>}
          <div className="flex items-center justify-between">
            <button
              type="submit"
              className="bg-blue-500 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded focus:outline-none focus:shadow-outline"
            >
              Sign In
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

const DashboardPage = () => {
  const [stats, setStats] = useState(null);
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const token = localStorage.getItem('token');
        const [statsRes, logsRes] = await Promise.all([
          axios.get(`${API_BASE_URL}/v1/admin/stats`, { headers: { Authorization: `Bearer ${token}` } }),
          axios.get(`${API_BASE_URL}/v1/admin/transcriptions?size=100`, { headers: { Authorization: `Bearer ${token}` } })
        ]);
        setStats(statsRes.data);
        setLogs(logsRes.data.items);
        setError('');
      } catch (err) {
        console.error("Failed to fetch data:", err);
        setError('데이터를 불러오는 데 실패했습니다. API 서버가 실행 중인지 확인하세요.');
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const StatCard = ({ title, value, colorClass }) => (
    <div className={`p-6 rounded-lg shadow-md ${colorClass}`}>
      <h3 className="text-lg font-semibold text-white">{title}</h3>
      <p className="text-3xl font-bold text-white mt-2">{value}</p>
    </div>
  );

  return (
    <div className="container mx-auto p-8">
      <header className="mb-8">
        <h1 className="text-4xl font-bold text-gray-800">📊 STT 시스템 관리 대시보드</h1>
      </header>

      {loading && <p className="text-center">로딩 중...</p>}
      {error && <p className="text-center text-red-500 bg-red-100 p-4 rounded-lg">{error}</p>}

      {stats && (
        <section className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          <StatCard title="총 요청 수" value={stats.total_requests.toLocaleString()} colorClass="bg-blue-500" />
          <StatCard title="처리 성공" value={stats.completed.toLocaleString()} colorClass="bg-green-500" />
          <StatCard title="처리 실패" value={stats.failed.toLocaleString()} colorClass="bg-red-500" />
          <StatCard title="성공률" value={`${stats.success_rate_percent}%`} colorClass="bg-indigo-500" />
        </section>
      )}

      <section className="bg-white p-6 rounded-lg shadow-md">
        <h2 className="text-2xl font-bold text-gray-700 mb-4">최근 처리 이력</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-left table-auto">
            <thead>
              <tr className="bg-gray-200 text-gray-600">
                <th className="p-3">상태</th>
                <th className="p-3">요청 시간</th>
                <th className="p-3">파일 이름</th>
                <th className="p-3">모델</th>
                <th className="p-3">언어</th>
                <th className="p-3">화자분리</th>
                <th className="p-3">에러 메시지</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((log) => (
                <tr key={log.request_id} className="border-b hover:bg-gray-50">
                  <td className="p-3">
                    <span className={`px-2 py-1 text-xs font-semibold rounded-full ${
                      log.status === 'completed' ? 'bg-green-100 text-green-800' :
                      log.status === 'failed' ? 'bg-red-100 text-red-800' : 'bg-yellow-100 text-yellow-800'}`
                    }>
                      {log.status}
                    </span>
                  </td>
                  <td className="p-3 text-sm text-gray-600">{new Date(log.created_at).toLocaleString()}</td>
                  <td className="p-3 font-medium text-gray-800">{log.filename}</td>
                  <td className="p-3">{log.model}</td>
                  <td className="p-3">{log.language}</td>
                  <td className="p-3">{log.diarization ? 'Yes' : 'No'}</td>
                  <td className="p-3 text-sm text-red-600 truncate max-w-xs">{log.error_message}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
};

function App() {
  const [token, setToken] = useState(localStorage.getItem('token'));

  const handleLogout = () => {
    localStorage.removeItem('token');
    setToken(null);
  };

  if (!token) {
    return <LoginPage setToken={setToken} />;
  }

  return (
    <Router>
      <div className="bg-gray-100 min-h-screen font-sans">
        <nav className="bg-white shadow-md p-4 flex justify-between items-center">
          <div className="text-2xl font-bold text-gray-800">Admin Dashboard</div>
          <div>
            <Link to="/dashboard" className="text-blue-600 hover:text-blue-800 px-3 py-2 rounded-md text-lg font-medium">Dashboard</Link>
            <Link to="/statistics" className="text-blue-600 hover:text-blue-800 px-3 py-2 rounded-md text-lg font-medium">Statistics</Link>
            <button onClick={handleLogout} className="ml-4 bg-red-500 hover:bg-red-700 text-white font-bold py-2 px-4 rounded">Logout</button>
          </div>
        </nav>
        <Routes>
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/statistics" element={<StatisticsPage />} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </div>
    </Router>
  );
}

export default App;
