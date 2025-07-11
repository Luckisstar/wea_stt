import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Chart as ChartJS, ArcElement, Tooltip, Legend, CategoryScale, LinearScale, BarElement, Title } from 'chart.js';
import { Pie, Bar } from 'react-chartjs-2';

ChartJS.register(ArcElement, Tooltip, Legend, CategoryScale, LinearScale, BarElement, Title);

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const StatisticsPage = () => {
    const [stats, setStats] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        const fetchStats = async () => {
            try {
                const token = localStorage.getItem('token');
                const response = await axios.get(`${API_URL}/v1/admin/stats`, {
                    headers: {
                        Authorization: `Bearer ${token}`,
                    },
                });
                setStats(response.data);
            } catch (err) {
                setError('Failed to fetch statistics.');
                console.error(err);
            } finally {
                setLoading(false);
            }
        };

        fetchStats();
    }, []);

    if (loading) return <div className="text-center py-4">Loading statistics...</div>;
    if (error) return <div className="text-center py-4 text-red-500">Error: {error}</div>;
    if (!stats) return <div className="text-center py-4">No statistics available.</div>;

    const pieData = {
        labels: ['Completed', 'Failed', 'Processing'],
        datasets: [
            {
                data: [stats.completed, stats.failed, stats.processing],
                backgroundColor: ['#4CAF50', '#F44336', '#FFC107'],
                borderColor: ['#4CAF50', '#F44336', '#FFC107'],
                borderWidth: 1,
            },
        ],
    };

    const barData = {
        labels: ['Total Requests', 'Completed', 'Failed', 'Processing'],
        datasets: [
            {
                label: 'Number of Requests',
                data: [stats.total_requests, stats.completed, stats.failed, stats.processing],
                backgroundColor: ['#2196F3', '#4CAF50', '#F44336', '#FFC107'],
                borderColor: ['#2196F3', '#4CAF50', '#F44336', '#FFC107'],
                borderWidth: 1,
            },
        ],
    };

    const barOptions = {
        responsive: true,
        plugins: {
            title: {
                display: true,
                text: 'STT Request Overview',
            },
        },
        scales: {
            y: {
                beginAtZero: true,
                title: {
                    display: true,
                    text: 'Count',
                },
            },
        },
    };

    return (
        <div className="container mx-auto p-4">
            <h1 className="text-3xl font-bold mb-6 text-center">STT System Statistics</h1>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
                <div className="bg-white p-6 rounded-lg shadow-md text-center">
                    <h2 className="text-xl font-semibold text-gray-700">Total Requests</h2>
                    <p className="text-4xl font-bold text-blue-600">{stats.total_requests}</p>
                </div>
                <div className="bg-white p-6 rounded-lg shadow-md text-center">
                    <h2 className="text-xl font-semibold text-gray-700">Completed</h2>
                    <p className="text-4xl font-bold text-green-600">{stats.completed}</p>
                </div>
                <div className="bg-white p-6 rounded-lg shadow-md text-center">
                    <h2 className="text-xl font-semibold text-gray-700">Failed</h2>
                    <p className="text-4xl font-bold text-red-600">{stats.failed}</p>
                </div>
                <div className="bg-white p-6 rounded-lg shadow-md text-center">
                    <h2 className="text-xl font-semibold text-gray-700">Success Rate</h2>
                    <p className="text-4xl font-bold text-purple-600">{stats.success_rate_percent}%</p>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                <div className="bg-white p-6 rounded-lg shadow-md flex flex-col items-center">
                    <h2 className="text-xl font-semibold text-gray-700 mb-4">Request Status Distribution</h2>
                    <div className="w-full max-w-md">
                        <Pie data={pieData} />
                    </div>
                </div>
                <div className="bg-white p-6 rounded-lg shadow-md">
                    <Bar data={barData} options={barOptions} />
                </div>
            </div>
        </div>
    );
};

export default StatisticsPage;
