import React, { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import DashboardLayout from '../components/dashboard/DashboardLayout';
import { attendanceAPI } from '../api/attendance';
import { anomalyAPI } from '../api/anomalies';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, LineChart, Line, PieChart, Pie, Cell } from 'recharts';
import EmployeeAvatar from '../components/dashboard/EmployeeAvatar';
import EmployeeModal from '../components/dashboard/EmployeeModal';
import './DashboardMain.css';

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#14b8a6', '#f97316'];

const DashboardMain = () => {
    const navigate = useNavigate();
    const [attendanceData, setAttendanceData] = useState([]);
    const [anomalies, setAnomalies] = useState([]);
    const [loading, setLoading] = useState(true);
    const [selectedEmployee, setSelectedEmployee] = useState(null); // Modal state
    
    // Pagination & Filter States
    const [currentPage, setCurrentPage] = useState(1);
    const [searchTerm, setSearchTerm] = useState('');
    const [filterDate, setFilterDate] = useState('');
    const recordsPerPage = 8;

    useEffect(() => {
        const fetchDashboardData = async () => {
            try {
                const [attData, anomData] = await Promise.all([
                    attendanceAPI.getAllAttendance(),
                    anomalyAPI.getAnomalies().catch(e => {
                        console.error("Failed to fetch anomalies", e);
                        return [];
                    })
                ]);
                setAttendanceData(attData);
                setAnomalies(anomData);
            } catch (error) {
                console.error("Failed to fetch dashboard records", error);
            } finally {
                setLoading(false);
            }
        };
        fetchDashboardData();
        
        // Polling every 5 seconds
        const intervalId = setInterval(fetchDashboardData, 5000);
        return () => clearInterval(intervalId);
    }, []);

    // Derived stats, aggregation, and chart data
    const { stats, aggregatedData, chartDataDay, chartDataHour, chartDataRole, chartDataCamera, chartDataAvgDuration, chartDataTopEngaged, chartDataCameraRole, allRoles } = useMemo(() => {
        const dateObj = new Date();
        const year = dateObj.getFullYear();
        const month = String(dateObj.getMonth() + 1).padStart(2, '0');
        const day = String(dateObj.getDate()).padStart(2, '0');
        const today = `${year}-${month}-${day}`;

        // 1. Group records by employee AND day to compute "Visits" and "Duration"
        const grouped = {};
        const cameraDurations = {}; // camera_id -> total duration
        const dailyUniquePeople = {}; // day -> Set of employee_ids
        const dailyTotalDuration = {}; // day -> total duration in seconds
        
        const cameraRoleUniquePeople = {}; // camId -> { role: Set(employee_id) }
        const uniqueRoles = new Set();

        attendanceData.forEach(record => {
            if (!record.day || !record.date_created) return;
            
            // Unique People Tracking
            const dayStr = record.day;
            if (!dailyUniquePeople[dayStr]) dailyUniquePeople[dayStr] = new Set();
            dailyUniquePeople[dayStr].add(record.employee_id);

            // Daily Duration Tracking
            dailyTotalDuration[dayStr] = (dailyTotalDuration[dayStr] || 0) + (record.duration_seconds || 0);

            // Camera Duration Tracking
            const camId = record.camera_id || "Unknown";
            cameraDurations[camId] = (cameraDurations[camId] || 0) + (record.duration_seconds || 0);

            // Camera Role Tracking (Enterprise Stacked Bar - UNIQUE People)
            const roleKey = record.role || "Employee";
            if (!cameraRoleUniquePeople[camId]) cameraRoleUniquePeople[camId] = {};
            if (!cameraRoleUniquePeople[camId][roleKey]) cameraRoleUniquePeople[camId][roleKey] = new Set();
            cameraRoleUniquePeople[camId][roleKey].add(record.employee_id);
            uniqueRoles.add(roleKey);

            const key = `${record.employee_id}_${record.day}`;
            if (!grouped[key]) {
                grouped[key] = {
                    ...record,
                    look_count: record.look_count || 1, // now represents visits/sessions
                    first_seen: record.date_created,
                    last_seen: record.last_seen || record.date_created,
                    total_duration_seconds: record.duration_seconds || 0
                };
            } else {
                grouped[key].look_count += (record.look_count || 1);
                grouped[key].total_duration_seconds += (record.duration_seconds || 0);
                
                const recordFirst = new Date(record.date_created);
                if (recordFirst < new Date(grouped[key].first_seen)) {
                    grouped[key].first_seen = record.date_created;
                }
                const recordLast = new Date(record.last_seen || record.date_created);
                if (recordLast > new Date(grouped[key].last_seen)) {
                    grouped[key].last_seen = record.last_seen || record.date_created;
                }
            }
        });

        // 2. Sort aggregated data by last_seen
        const sortedAggregated = Object.values(grouped).sort((a, b) => new Date(b.last_seen) - new Date(a.last_seen));

        const presentToday = sortedAggregated.filter(record => record.day.startsWith(today)).length;
        const latest = sortedAggregated.length > 0 ? sortedAggregated[0] : null;

        // --- Chart Data Processing & Top Attender Logic ---
        const dayMap = {};
        const hourMap = {};
        const roleMap = {};
        const employeeCheckinCount = {};
        const employeeTotalDuration = {};
        const employeeObjects = {}; // name -> record for avatars

        const sevenDaysAgo = new Date();
        sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);

        // Process RAW attendanceData for accurate graphs
        attendanceData.forEach(record => {
            if (!record.day || !record.date_created) return;
            const recordDate = new Date(record.day);
            
            // Top Attender Logic (only last 7 days)
            if (recordDate >= sevenDaysAgo) {
                const empName = `${record.first_name} ${record.last_name}`;
                employeeCheckinCount[empName] = (employeeCheckinCount[empName] || 0) + 1;
                employeeTotalDuration[empName] = (employeeTotalDuration[empName] || 0) + (record.duration_seconds || 0);
                if (!employeeObjects[empName]) employeeObjects[empName] = record;
            }

            // Group by Day (for Bar Chart)
            const dayKey = recordDate.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' });
            dayMap[dayKey] = dailyUniquePeople[record.day]?.size || 0;

            // Group by Hour (for Line Chart)
            const h = new Date(record.date_created).getHours();
            const hourKey = `${h}:00`;
            hourMap[hourKey] = (hourMap[hourKey] || 0) + 1;

            // Group by Role
            const rKey = record.role || "Employee";
            roleMap[rKey] = (roleMap[rKey] || 0) + 1;
        });

        // Find Top Visitor (by Count of Visits)
        let topAttender = null;
        let topAttenderCount = 0;
        Object.entries(employeeCheckinCount).forEach(([name, count]) => {
            if (count > topAttenderCount) {
                topAttenderCount = count;
                topAttender = employeeObjects[name];
            }
        });

        const uniqueDates = [...new Set(attendanceData.map(r => r.day))].sort();
        const last7Days = uniqueDates.slice(-7);
        const processedChartDataDay = last7Days.map(dateStr => {
            const key = new Date(dateStr).toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' });
            return { name: key, people: dayMap[key] || 0 };
        });

        const processedChartDataAvgDuration = last7Days.map(dateStr => {
            const key = new Date(dateStr).toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' });
            const totalSecs = dailyTotalDuration[dateStr] || 0;
            const uniqueCount = dailyUniquePeople[dateStr]?.size || 1; // Avoid div by zero
            return { name: key, avgMins: parseFloat(((totalSecs / uniqueCount) / 60).toFixed(1)) };
        });

        // Top 5 Engaged Employees by Duration (Mins)
        const topEngagedEmployees = Object.entries(employeeTotalDuration)
            .map(([name, duration]) => ({ name, mins: parseFloat((duration / 60).toFixed(1)) }))
            .sort((a, b) => b.mins - a.mins)
            .slice(0, 5);

        const sortedHours = Object.keys(hourMap).sort((a, b) => parseInt(a) - parseInt(b));
        const processedChartDataHour = sortedHours.map(hour => ({ name: hour, checkins: hourMap[hour] }));

        const processedChartDataRole = Object.keys(roleMap).map(role => ({ name: role, value: roleMap[role] }));
        
        const processedChartDataCamera = Object.keys(cameraDurations).map(cam => ({
            name: cam,
            minutes: parseFloat((cameraDurations[cam] / 60).toFixed(1))
        }));

        // Camera Role Stacked Chart (Unique People per role per camera)
        const processedChartCameraRole = Object.keys(cameraRoleUniquePeople).map(cam => {
            const dataPoint = { name: cam };
            Object.entries(cameraRoleUniquePeople[cam]).forEach(([role, empSet]) => {
                dataPoint[role] = empSet.size;
            });
            return dataPoint;
        });

        return {
            stats: {
                totalPresent: presentToday,
                topAttender: topAttender ? {
                    name: `${topAttender.first_name} ${topAttender.last_name}`,
                    count: topAttenderCount,
                    imageUrl: topAttender.profile_image_url,
                    first: topAttender.first_name,
                    last: topAttender.last_name,
                    record: topAttender
                } : null,
                latestArrival: latest ? {
                    name: `${latest.first_name} ${latest.last_name}`,
                    time: new Date(latest.last_seen).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
                    imageUrl: latest.profile_image_url,
                    first: latest.first_name,
                    last: latest.last_name,
                    record: latest
                } : null
            },
            aggregatedData: sortedAggregated,
            chartDataDay: processedChartDataDay,
            chartDataHour: processedChartDataHour,
            chartDataRole: processedChartDataRole,
            chartDataCamera: processedChartDataCamera,
            chartDataAvgDuration: processedChartDataAvgDuration,
            chartDataTopEngaged: topEngagedEmployees,
            chartDataCameraRole: processedChartCameraRole,
            allRoles: Array.from(uniqueRoles)
        };
    }, [attendanceData]);

    const anomaliesToday = useMemo(() => {
        const todayStr = new Date().toISOString().split('T')[0];
        return anomalies.filter(anom => anom.detected_at && anom.detected_at.startsWith(todayStr)).length;
    }, [anomalies]);

    const anomalyChartData = useMemo(() => {
        const uniqueDates = [...new Set(attendanceData.map(r => r.day))].sort();
        const last7Days = uniqueDates.slice(-7);
        return last7Days.map(dateStr => {
            const count = anomalies.filter(anom => anom.detected_at && anom.detected_at.startsWith(dateStr)).length;
            const label = new Date(dateStr).toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' });
            return { name: label, count };
        });
    }, [anomalies, attendanceData]);

    // Apply Search and Date Filters on aggregated data
    const filteredRecords = useMemo(() => {
        return aggregatedData.filter(record => {
            const matchesSearch = 
                record.first_name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
                record.last_name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
                record.role?.toLowerCase().includes(searchTerm.toLowerCase());
            
            const matchesDate = filterDate ? record.day === filterDate : true;

            return matchesSearch && matchesDate;
        });
    }, [aggregatedData, searchTerm, filterDate]);

    useEffect(() => {
        setCurrentPage(1);
    }, [searchTerm, filterDate]);

    // Pagination
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
                        <h3>Employees Present Today</h3>
                        <p className="stat-value highlight-green">{stats.totalPresent}</p>
                    </div>
                    <div className="stat-card">
                        <h3>Most Frequent Visitor</h3>
                        {stats.topAttender ? (
                            <div className="stat-card-enhanced" style={{cursor: 'pointer'}} onClick={() => setSelectedEmployee(stats.topAttender.record)}>
                                <EmployeeAvatar imageUrl={stats.topAttender.imageUrl} firstName={stats.topAttender.first} lastName={stats.topAttender.last} />
                                <div className="stat-card-info">
                                    <span className="stat-card-name" title={stats.topAttender.name}>{stats.topAttender.name}</span>
                                    <span className="stat-card-sub">{stats.topAttender.count} visits (7 Days)</span>
                                </div>
                            </div>
                        ) : (
                            <p className="stat-value">None</p>
                        )}
                    </div>
                    <div className="stat-card">
                        <h3>Latest Arrival</h3>
                        {stats.latestArrival ? (
                            <div className="stat-card-enhanced" style={{cursor: 'pointer'}} onClick={() => setSelectedEmployee(stats.latestArrival.record)}>
                                <EmployeeAvatar imageUrl={stats.latestArrival.imageUrl} firstName={stats.latestArrival.first} lastName={stats.latestArrival.last} />
                                <div className="stat-card-info">
                                    <span className="stat-card-name" title={stats.latestArrival.name}>{stats.latestArrival.name}</span>
                                    <span className="stat-card-sub">{stats.latestArrival.time}</span>
                                </div>
                            </div>
                        ) : (
                            <p className="stat-value">None today</p>
                        )}
                    </div>
                    <div className="stat-card" style={{ cursor: 'pointer' }} onClick={() => navigate('/dashboard/anomalies')}>
                        <h3>Anomalies Today</h3>
                        <p className="stat-value" style={{ color: '#ef4444' }}>{anomaliesToday}</p>
                        <span className="stat-card-sub">{anomalies.length} total events logged</span>
                    </div>
                </div>

                {/* Charts Row 1 */}
                {attendanceData.length > 0 && !loading && (
                    <div className="charts-row">
                        <div className="chart-card">
                            <h3 className="section-title">Unique People per Day</h3>
                            <div className="chart-wrapper">
                                <ResponsiveContainer width="100%" height="100%">
                                    <BarChart data={chartDataDay}>
                                        <defs>
                                            <linearGradient id="colorPeople" x1="0" y1="0" x2="0" y2="1">
                                                <stop offset="5%" stopColor="#8b5cf6" stopOpacity={0.9}/>
                                                <stop offset="95%" stopColor="#c4b5fd" stopOpacity={0.2}/>
                                            </linearGradient>
                                        </defs>
                                        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                                        <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fill: '#94a3b8', fontSize: 12 }} dy={10} />
                                        <YAxis axisLine={false} tickLine={false} tick={{ fill: '#94a3b8', fontSize: 12 }} />
                                        <Tooltip cursor={{ fill: 'rgba(241, 245, 249, 0.5)' }} contentStyle={{ borderRadius: '12px', border: '1px solid #e2e8f0', boxShadow: '0 10px 15px -3px rgba(0,0,0,0.1)' }} />
                                        <Bar dataKey="people" fill="url(#colorPeople)" radius={[6, 6, 0, 0]} barSize={32} name="Unique People" />
                                    </BarChart>
                                </ResponsiveContainer>
                            </div>
                        </div>

                        <div className="chart-card">
                            <h3 className="section-title">Avg Duration per Person (Mins)</h3>
                            <div className="chart-wrapper">
                                <ResponsiveContainer width="100%" height="100%">
                                    <LineChart data={chartDataAvgDuration}>
                                        <defs>
                                            <filter id="shadowAvg" height="200%">
                                                <feDropShadow dx="0" dy="4" stdDeviation="4" floodColor="#f59e0b" floodOpacity="0.3" />
                                            </filter>
                                        </defs>
                                        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                                        <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fill: '#94a3b8', fontSize: 12 }} dy={10} />
                                        <YAxis axisLine={false} tickLine={false} tick={{ fill: '#94a3b8', fontSize: 12 }} />
                                        <Tooltip contentStyle={{ borderRadius: '12px', border: '1px solid #e2e8f0', boxShadow: '0 10px 15px -3px rgba(0,0,0,0.1)' }} />
                                        <Line type="monotone" dataKey="avgMins" stroke="#f59e0b" strokeWidth={4} filter="url(#shadowAvg)" dot={{ r: 5, fill: '#fff', strokeWidth: 3, stroke: '#f59e0b' }} activeDot={{ r: 8 }} name="Avg Mins" />
                                    </LineChart>
                                </ResponsiveContainer>
                            </div>
                        </div>

                        <div className="chart-card">
                            <h3 className="section-title">Time per Camera (Mins)</h3>
                            <div className="chart-wrapper">
                                <ResponsiveContainer width="100%" height="100%">
                                    <BarChart data={chartDataCamera} layout="vertical">
                                        <defs>
                                            <linearGradient id="colorCamera" x1="0" y1="0" x2="1" y2="0">
                                                <stop offset="5%" stopColor="#14b8a6" stopOpacity={0.8}/>
                                                <stop offset="95%" stopColor="#5eead4" stopOpacity={0.9}/>
                                            </linearGradient>
                                        </defs>
                                        <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#f1f5f9" />
                                        <XAxis type="number" axisLine={false} tickLine={false} tick={{ fill: '#94a3b8', fontSize: 12 }} />
                                        <YAxis dataKey="name" type="category" axisLine={false} tickLine={false} tick={{ fill: '#94a3b8', fontSize: 12 }} width={80} />
                                        <Tooltip cursor={{ fill: 'rgba(241, 245, 249, 0.5)' }} contentStyle={{ borderRadius: '12px', border: '1px solid #e2e8f0', boxShadow: '0 10px 15px -3px rgba(0,0,0,0.1)' }} />
                                        <Bar dataKey="minutes" fill="url(#colorCamera)" radius={[0, 6, 6, 0]} barSize={20} name="Minutes" />
                                    </BarChart>
                                </ResponsiveContainer>
                            </div>
                        </div>
                    </div>
                )}

                {/* Charts Row 2 */}
                {attendanceData.length > 0 && !loading && (
                    <div className="charts-row">
                        <div className="chart-card">
                            <h3 className="section-title">Top Engaged Employees (Time)</h3>
                            <div className="chart-wrapper">
                                <ResponsiveContainer width="100%" height="100%">
                                    <BarChart data={chartDataTopEngaged} layout="vertical">
                                        <defs>
                                            <linearGradient id="colorTop" x1="0" y1="0" x2="1" y2="0">
                                                <stop offset="5%" stopColor="#ec4899" stopOpacity={0.8}/>
                                                <stop offset="95%" stopColor="#f472b6" stopOpacity={0.9}/>
                                            </linearGradient>
                                        </defs>
                                        <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#f1f5f9" />
                                        <XAxis type="number" axisLine={false} tickLine={false} tick={{ fill: '#94a3b8', fontSize: 12 }} />
                                        <YAxis dataKey="name" type="category" axisLine={false} tickLine={false} tick={{ fill: '#94a3b8', fontSize: 12 }} width={100} />
                                        <Tooltip cursor={{ fill: 'rgba(241, 245, 249, 0.5)' }} contentStyle={{ borderRadius: '12px', border: '1px solid #e2e8f0', boxShadow: '0 10px 15px -3px rgba(0,0,0,0.1)' }} />
                                        <Bar dataKey="mins" fill="url(#colorTop)" radius={[0, 6, 6, 0]} barSize={20} name="Total Mins" />
                                    </BarChart>
                                </ResponsiveContainer>
                            </div>
                        </div>

                        <div className="chart-card">
                            <h3 className="section-title">Peak Interaction Hours</h3>
                            <div className="chart-wrapper">
                                <ResponsiveContainer width="100%" height="100%">
                                    <LineChart data={chartDataHour}>
                                        <defs>
                                            <filter id="shadowPeak" height="200%">
                                                <feDropShadow dx="0" dy="4" stdDeviation="4" floodColor="#10b981" floodOpacity="0.3" />
                                            </filter>
                                        </defs>
                                        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                                        <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fill: '#94a3b8', fontSize: 12 }} dy={10} />
                                        <YAxis axisLine={false} tickLine={false} tick={{ fill: '#94a3b8', fontSize: 12 }} />
                                        <Tooltip contentStyle={{ borderRadius: '12px', border: '1px solid #e2e8f0', boxShadow: '0 10px 15px -3px rgba(0,0,0,0.1)' }} />
                                        <Line type="monotone" dataKey="checkins" stroke="#10b981" strokeWidth={4} filter="url(#shadowPeak)" dot={{ r: 5, fill: '#fff', strokeWidth: 3, stroke: '#10b981' }} activeDot={{ r: 8 }} name="Interactions" />
                                    </LineChart>
                                </ResponsiveContainer>
                            </div>
                        </div>
                    </div>
                )}

                {/* Charts Row 3 */}
                {attendanceData.length > 0 && !loading && (
                    <div className="charts-row">
                        <div className="chart-card">
                            <h3 className="section-title">Role Distribution per Camera</h3>
                            <p style={{ fontSize: '13px', color: '#64748b', marginTop: '-8px', marginBottom: '8px' }}>
                                Unique individuals by role across cameras.
                            </p>
                            <div className="chart-wrapper">
                                <ResponsiveContainer width="100%" height="100%">
                                    <BarChart data={chartDataCameraRole} layout="vertical">
                                        <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#f1f5f9" />
                                        <XAxis type="number" axisLine={false} tickLine={false} tick={{ fill: '#94a3b8', fontSize: 12 }} />
                                        <YAxis dataKey="name" type="category" axisLine={false} tickLine={false} tick={{ fill: '#94a3b8', fontSize: 12 }} width={80} />
                                        <Tooltip cursor={{ fill: 'rgba(241, 245, 249, 0.5)' }} contentStyle={{ borderRadius: '12px', border: '1px solid #e2e8f0', boxShadow: '0 10px 15px -3px rgba(0,0,0,0.1)' }} />
                                        {allRoles.map((role, idx) => (
                                            <Bar 
                                                key={role} 
                                                dataKey={role} 
                                                stackId="a" 
                                                fill={COLORS[idx % COLORS.length]} 
                                                radius={idx === allRoles.length - 1 ? [0, 6, 6, 0] : [0, 0, 0, 0]} 
                                                name={role}
                                            />
                                        ))}
                                    </BarChart>
                                </ResponsiveContainer>
                            </div>
                        </div>
                        
                        <div className="chart-card">
                            <h3 className="section-title">Total Visits by Role</h3>
                            <div className="chart-wrapper">
                                <ResponsiveContainer width="100%" height="100%">
                                    <PieChart>
                                        <Pie data={chartDataRole} cx="50%" cy="50%" innerRadius={70} outerRadius={100} paddingAngle={5} dataKey="value" nameKey="name">
                                            {chartDataRole.map((entry, index) => (
                                                <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                                            ))}
                                        </Pie>
                                        <Tooltip contentStyle={{ borderRadius: '12px', border: '1px solid #e2e8f0', boxShadow: '0 10px 15px -3px rgba(0,0,0,0.1)' }} />
                                    </PieChart>
                                </ResponsiveContainer>
                            </div>
                        </div>

                        <div className="chart-card">
                            <h3 className="section-title">Anomaly Trend (7 Days)</h3>
                            <div className="chart-wrapper">
                                <ResponsiveContainer width="100%" height="100%">
                                    <LineChart data={anomalyChartData}>
                                        <defs>
                                            <filter id="shadowAnom" height="200%">
                                                <feDropShadow dx="0" dy="4" stdDeviation="4" floodColor="#ef4444" floodOpacity="0.3" />
                                            </filter>
                                        </defs>
                                        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                                        <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fill: '#94a3b8', fontSize: 12 }} dy={10} />
                                        <YAxis axisLine={false} tickLine={false} tick={{ fill: '#94a3b8', fontSize: 12 }} />
                                        <Tooltip contentStyle={{ borderRadius: '12px', border: '1px solid #e2e8f0', boxShadow: '0 10px 15px -3px rgba(0,0,0,0.1)' }} />
                                        <Line type="monotone" dataKey="count" stroke="#ef4444" strokeWidth={4} filter="url(#shadowAnom)" dot={{ r: 5, fill: '#fff', strokeWidth: 3, stroke: '#ef4444' }} activeDot={{ r: 8 }} name="Anomalies" />
                                    </LineChart>
                                </ResponsiveContainer>
                            </div>
                        </div>
                    </div>
                )}

                {/* Table Section */}
                <div className="table-section">
                    <div className="table-header-row">
                        <h2 className="section-title" style={{ margin: 0 }}>Live Attendance & Duration Log</h2>
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
                        <p className="loading-text">Loading live data...</p>
                    ) : filteredRecords.length === 0 ? (
                        <p className="loading-text">No records match your filters.</p>
                    ) : (
                        <div className="table-wrapper-flex">
                            <div className="table-responsive">
                                <table className="attendance-table">
                                    <thead>
                                        <tr>
                                            <th>Employee Name</th>
                                            <th>Role</th>
                                            <th>Date</th>
                                            <th>First Time In</th>
                                            <th>Last Seen</th>
                                            <th>Duration</th>
                                            <th>Sessions / Visits</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {currentRecords.map(record => {
                                            const durationMins = Math.floor(record.total_duration_seconds / 60);
                                            const durationSecs = Math.floor(record.total_duration_seconds % 60);
                                            const durationText = record.total_duration_seconds > 0 
                                                ? `${durationMins}m ${durationSecs}s` 
                                                : "Live";

                                            return (
                                                <tr key={`${record.employee_id}_${record.day}`} onClick={() => setSelectedEmployee(record)} style={{cursor: 'pointer'}}>
                                                    <td className="emp-name">
                                                        <EmployeeAvatar 
                                                            imageUrl={record.profile_image_url} 
                                                            firstName={record.first_name} 
                                                            lastName={record.last_name} 
                                                        />
                                                        {record.first_name} {record.last_name}
                                                    </td>
                                                    <td className="emp-role">
                                                        <span className="role-badge">{record.role || "Employee"}</span>
                                                    </td>
                                                    <td>{formatDate(record.day)}</td>
                                                    <td className="time-cell">{formatTime(record.first_seen)}</td>
                                                    <td className="time-cell">{formatTime(record.last_seen)}</td>
                                                    <td className="time-cell font-mono">{durationText}</td>
                                                    <td className="look-count-cell">
                                                        <div className="look-badge">{record.look_count}</div>
                                                    </td>
                                                </tr>
                                            );
                                        })}
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
            
            {/* Employee Details Modal */}
            <EmployeeModal 
                employee={selectedEmployee} 
                allAttendanceData={attendanceData} 
                onClose={() => setSelectedEmployee(null)} 
            />
        </DashboardLayout>
    );
};

export default DashboardMain;

