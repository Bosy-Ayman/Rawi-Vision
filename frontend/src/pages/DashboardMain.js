import React, { useState, useEffect, useMemo } from 'react';
import DashboardLayout from '../components/dashboard/DashboardLayout';
import { attendanceAPI } from '../api/attendance';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, LineChart, Line } from 'recharts';
import EmployeeAvatar from '../components/dashboard/EmployeeAvatar';
import './DashboardMain.css';

const DashboardMain = () => {
    const [attendanceData, setAttendanceData] = useState([]);
    const [loading, setLoading] = useState(true);
    
    // Pagination & Filter States
    const [currentPage, setCurrentPage] = useState(1);
    const [searchTerm, setSearchTerm] = useState('');
    const [filterDate, setFilterDate] = useState('');
    const recordsPerPage = 8;

    useEffect(() => {
        const fetchAttendance = async () => {
            try {
                const data = await attendanceAPI.getAllAttendance();
                setAttendanceData(data);
            } catch (error) {
                console.error("Failed to fetch attendance records", error);
            } finally {
                setLoading(false);
            }
        };
        fetchAttendance();
    }, []);

    // Derived stats and chart data
    const { stats, sortedData, chartDataDay, chartDataHour } = useMemo(() => {
        const dateObj = new Date();
        const year = dateObj.getFullYear();
        const month = String(dateObj.getMonth() + 1).padStart(2, '0');
        const day = String(dateObj.getDate()).padStart(2, '0');
        const today = `${year}-${month}-${day}`;
        
        const presentToday = attendanceData.filter(record => {
            if (!record.day) return false;
            return record.day.startsWith(today);
        }).length;

        const sorted = [...attendanceData].sort((a, b) => new Date(b.date_created) - new Date(a.date_created));
        const latest = sorted.length > 0 ? sorted[0] : null;

        // --- Chart Data Processing & Top Attender Logic ---
        const dayMap = {};
        const hourMap = {};
        const employeeCheckinCount = {};

        // Calculate 7 days ago limit
        const sevenDaysAgo = new Date();
        sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);

        // Fill maps
        attendanceData.forEach(record => {
            if (!record.day || !record.date_created) return;
            
            const recordDate = new Date(record.day);
            
            // Top Attender Logic (only last 7 days)
            if (recordDate >= sevenDaysAgo) {
                const empName = `${record.first_name} ${record.last_name}`;
                employeeCheckinCount[empName] = (employeeCheckinCount[empName] || 0) + 1;
            }

            // Group by Day (for Bar Chart)
            const dayKey = recordDate.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' });
            dayMap[dayKey] = (dayMap[dayKey] || 0) + 1;

            // Group by Hour (for Line Chart)
            const h = new Date(record.date_created).getHours();
            const hourKey = `${h}:00`;
            hourMap[hourKey] = (hourMap[hourKey] || 0) + 1;
        });

        // Find Top Attender
        let topAttenderName = "No records";
        let topAttenderCount = 0;
        Object.entries(employeeCheckinCount).forEach(([name, count]) => {
            if (count > topAttenderCount) {
                topAttenderCount = count;
                topAttenderName = name;
            }
        });

        // Ensure chronological order for Bar Chart
        const uniqueDates = [...new Set(attendanceData.map(r => r.day))].sort();
        const last7Days = uniqueDates.slice(-7);
        const processedChartDataDay = last7Days.map(dateStr => {
            const key = new Date(dateStr).toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' });
            return { name: key, checkins: dayMap[key] || 0 };
        });

        // Ensure chronological order for Line Chart
        const sortedHours = Object.keys(hourMap).sort((a, b) => parseInt(a) - parseInt(b));
        const processedChartDataHour = sortedHours.map(hour => ({ name: hour, checkins: hourMap[hour] }));

        return {
            stats: {
                totalPresent: presentToday,
                topAttender: `${topAttenderName} (${topAttenderCount} days)`,
                latestArrival: latest ? `${latest.first_name} ${latest.last_name}` : "None today"
            },
            sortedData: sorted,
            chartDataDay: processedChartDataDay,
            chartDataHour: processedChartDataHour
        };
    }, [attendanceData]);

    // Apply Search and Date Filters
    const filteredRecords = useMemo(() => {
        return sortedData.filter(record => {
            const matchesSearch = 
                record.first_name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
                record.last_name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
                record.role?.toLowerCase().includes(searchTerm.toLowerCase());
            
            const matchesDate = filterDate ? record.day === filterDate : true;

            return matchesSearch && matchesDate;
        });
    }, [sortedData, searchTerm, filterDate]);

    // Reset pagination when filters change
    useEffect(() => {
        setCurrentPage(1);
    }, [searchTerm, filterDate]);

    // Pagination logic
    const indexOfLastRecord = currentPage * recordsPerPage;
    const indexOfFirstRecord = indexOfLastRecord - recordsPerPage;
    const currentRecords = filteredRecords.slice(indexOfFirstRecord, indexOfLastRecord);
    const totalPages = Math.ceil(filteredRecords.length / recordsPerPage);

    const paginate = (pageNumber) => setCurrentPage(pageNumber);

    const formatTime = (dateString) => {
        if (!dateString) return "N/A";
        const date = new Date(dateString);
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    };

    const formatDate = (dateString) => {
        if (!dateString) return "N/A";
        return new Date(dateString).toLocaleDateString();
    };

    return (
        <DashboardLayout title="Attendance Dashboard">
            <div className="dashboard-main-container">
                {/* Stats Row */}
                <div className="stats-row">
                    <div className="stat-card">
                        <h3>Present Today</h3>
                        <p className="stat-value highlight-green">{stats.totalPresent}</p>
                    </div>
                    <div className="stat-card">
                        <h3>Top Attender (7 Days)</h3>
                        <p className="stat-value truncate" title={stats.topAttender}>{stats.topAttender}</p>
                    </div>
                    <div className="stat-card">
                        <h3>Latest Arrival</h3>
                        <p className="stat-value truncate" title={stats.latestArrival}>{stats.latestArrival}</p>
                    </div>
                </div>

                {/* Charts Row */}
                {attendanceData.length > 0 && !loading && (
                    <div className="charts-row">
                        <div className="chart-card">
                            <h3 className="section-title">Attendance Over Time (Last 7 Days)</h3>
                            <div className="chart-wrapper">
                                <ResponsiveContainer width="100%" height="100%">
                                    <BarChart data={chartDataDay}>
                                        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                                        <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fill: '#64748b', fontSize: 12 }} dy={10} />
                                        <YAxis axisLine={false} tickLine={false} tick={{ fill: '#64748b', fontSize: 12 }} />
                                        <Tooltip cursor={{ fill: '#f1f5f9' }} contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgba(0,0,0,0.1)' }} />
                                        <Bar dataKey="checkins" fill="#3b82f6" radius={[4, 4, 0, 0]} barSize={40} />
                                    </BarChart>
                                </ResponsiveContainer>
                            </div>
                        </div>

                        <div className="chart-card">
                            <h3 className="section-title">Peak Arrival Times</h3>
                            <div className="chart-wrapper">
                                <ResponsiveContainer width="100%" height="100%">
                                    <LineChart data={chartDataHour}>
                                        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                                        <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fill: '#64748b', fontSize: 12 }} dy={10} />
                                        <YAxis axisLine={false} tickLine={false} tick={{ fill: '#64748b', fontSize: 12 }} />
                                        <Tooltip contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgba(0,0,0,0.1)' }} />
                                        <Line type="monotone" dataKey="checkins" stroke="#10b981" strokeWidth={3} dot={{ r: 4, fill: '#10b981', strokeWidth: 2, stroke: '#fff' }} activeDot={{ r: 6 }} />
                                    </LineChart>
                                </ResponsiveContainer>
                            </div>
                        </div>
                    </div>
                )}

                {/* Table Section */}
                <div className="table-section">
                    <div className="table-header-row">
                        <h2 className="section-title" style={{ margin: 0 }}>Live Attendance Log</h2>
                        <div className="table-filters">
                            <input 
                                type="date" 
                                className="filter-input date-filter"
                                value={filterDate}
                                onChange={(e) => setFilterDate(e.target.value)}
                            />
                            <input 
                                type="text" 
                                className="filter-input search-filter"
                                placeholder="Search Name or Role..."
                                value={searchTerm}
                                onChange={(e) => setSearchTerm(e.target.value)}
                            />
                        </div>
                    </div>

                    {loading ? (
                        <p className="loading-text">Loading live attendance data...</p>
                    ) : filteredRecords.length === 0 ? (
                        <p className="loading-text">No attendance records match your search filters.</p>
                    ) : (
                        <div className="table-wrapper-flex">
                            <div className="table-responsive">
                                <table className="attendance-table">
                                    <thead>
                                        <tr>
                                            <th>Employee Name</th>
                                            <th>Role</th>
                                            <th>Date</th>
                                            <th>Time In</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {currentRecords.map(record => (
                                            <tr key={record.id}>
                                                <td className="emp-name">
                                                    <EmployeeAvatar 
                                                        imageUrl={record.profile_image_url} 
                                                        firstName={record.first_name} 
                                                        lastName={record.last_name} 
                                                    />
                                                    {record.first_name} {record.last_name}
                                                </td>
                                                <td className="emp-role">{record.role || "Employee"}</td>
                                                <td>{formatDate(record.day)}</td>
                                                <td>{formatTime(record.date_created)}</td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                            
                            {/* Pagination Controls */}
                            {totalPages > 1 && (
                                <div className="pagination">
                                    <button 
                                        onClick={() => paginate(currentPage - 1)} 
                                        disabled={currentPage === 1}
                                        className="page-btn"
                                    >
                                        Prev
                                    </button>
                                    <span className="page-info">
                                        Page <span className="page-number">{currentPage}</span> of {totalPages}
                                    </span>
                                    <button 
                                        onClick={() => paginate(currentPage + 1)} 
                                        disabled={currentPage === totalPages}
                                        className="page-btn"
                                    >
                                        Next
                                    </button>
                                </div>
                            )}
                        </div>
                    )}
                </div>
            </div>
        </DashboardLayout>
    );
};

export default DashboardMain;
