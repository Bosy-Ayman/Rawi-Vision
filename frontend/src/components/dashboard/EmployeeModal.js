import React, { useMemo } from 'react';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';
import EmployeeAvatar from './EmployeeAvatar';
import './EmployeeModal.css';

const EmployeeModal = ({ employee, allAttendanceData, onClose }) => {
    // Calculate deep stats for this specific employee
    const { stats, chartData, recentActivity } = useMemo(() => {
        if (!employee || !allAttendanceData) return { stats: {}, chartData: [], recentActivity: [] };

        // Filter all records for this employee (handle both employee object and attendance record object)
        const targetEmployeeId = employee.employee_id || employee.id;
        const empRecords = allAttendanceData.filter(r => r.employee_id === targetEmployeeId);
        
        // 1. Total Visits and Total Duration
        let totalVisits = 0;
        let totalDurationSeconds = 0;
        const cameraCounts = {};
        const dailyDurations = {};

        empRecords.forEach(record => {
            totalVisits += (record.look_count || 1);
            totalDurationSeconds += (record.duration_seconds || 0);

            // Camera tracking
            const camId = record.camera_id || "Unknown";
            cameraCounts[camId] = (cameraCounts[camId] || 0) + 1;

            // Daily tracking for chart
            if (record.day) {
                dailyDurations[record.day] = (dailyDurations[record.day] || 0) + (record.duration_seconds || 0);
            }
        });

        // 2. Favorite Camera
        let favoriteCamera = "None";
        let maxCamVisits = 0;
        Object.entries(cameraCounts).forEach(([cam, count]) => {
            if (count > maxCamVisits) {
                maxCamVisits = count;
                favoriteCamera = cam;
            }
        });

        // 3. Average Session Duration
        const avgSessionSeconds = totalVisits > 0 ? totalDurationSeconds / totalVisits : 0;
        
        // Format functions
        const formatDuration = (secs) => {
            if (secs < 60) return `${Math.floor(secs)}s`;
            const mins = Math.floor(secs / 60);
            const rSecs = Math.floor(secs % 60);
            if (mins < 60) return `${mins}m ${rSecs}s`;
            const hrs = Math.floor(mins / 60);
            const rMins = mins % 60;
            return `${hrs}h ${rMins}m`;
        };

        // 4. Chart Data (Duration per day)
        const uniqueDates = [...new Set(empRecords.map(r => r.day).filter(Boolean))].sort();
        const chartData = uniqueDates.slice(-7).map(dateStr => ({
            name: new Date(dateStr).toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' }),
            mins: parseFloat(((dailyDurations[dateStr] || 0) / 60).toFixed(1))
        }));

        // 5. Recent Activity (last 5 interactions)
        const recentActivity = [...empRecords]
            .sort((a, b) => new Date(b.date_created) - new Date(a.date_created))
            .slice(0, 5);

        return {
            stats: {
                totalVisits,
                totalDuration: formatDuration(totalDurationSeconds),
                favoriteCamera,
                avgSession: formatDuration(avgSessionSeconds)
            },
            chartData,
            recentActivity
        };

    }, [employee, allAttendanceData]);

    if (!employee) return null;

    const formatTime = (dateString) => {
        if (!dateString) return "N/A";
        return new Date(dateString).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    };

    return (
        <div className="modal-overlay" onClick={onClose}>
            <div className="modal-content" onClick={e => e.stopPropagation()}>
                <button className="modal-close" onClick={onClose}>×</button>
                
                <div className="modal-header">
                    <div className="modal-avatar-wrapper">
                        <EmployeeAvatar 
                            imageUrl={employee.profile_image_url} 
                            firstName={employee.first_name} 
                            lastName={employee.last_name} 
                            size={120}
                        />
                    </div>
                    <div className="modal-header-info">
                        <h2>{employee.first_name} {employee.last_name}</h2>
                        <span className="modal-role-badge">{employee.role || "Employee"}</span>
                    </div>
                </div>

                <div className="modal-body">
                    <div className="modal-body-layout">
                        {/* Left Column: Stats & Chart */}
                        <div className="modal-left-col">
                            <div className="modal-stats-grid">
                                <div className="modal-stat-card">
                                    <span className="modal-stat-label">Total Sessions</span>
                                    <span className="modal-stat-value">{stats.totalVisits}</span>
                                </div>
                                <div className="modal-stat-card">
                                    <span className="modal-stat-label">Total Time</span>
                                    <span className="modal-stat-value">{stats.totalDuration}</span>
                                </div>
                                <div className="modal-stat-card">
                                    <span className="modal-stat-label">Fav Camera</span>
                                    <span className="modal-stat-value truncate" title={stats.favoriteCamera}>{stats.favoriteCamera}</span>
                                </div>
                                <div className="modal-stat-card">
                                    <span className="modal-stat-label">Avg Session</span>
                                    <span className="modal-stat-value">{stats.avgSession}</span>
                                </div>
                            </div>

                            {chartData.length > 0 && (
                                <div className="modal-chart-section">
                                    <h3>Duration Trend (Last 7 Days)</h3>
                                    <div className="modal-chart-wrapper">
                                        <ResponsiveContainer width="100%" height={240}>
                                            <LineChart data={chartData}>
                                                <defs>
                                                    <filter id="shadowModalLine" height="200%">
                                                        <feDropShadow dx="0" dy="4" stdDeviation="4" floodColor="#3b82f6" floodOpacity="0.3" />
                                                    </filter>
                                                </defs>
                                                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                                                <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fill: '#94a3b8', fontSize: 11 }} dy={10} />
                                                <YAxis axisLine={false} tickLine={false} tick={{ fill: '#94a3b8', fontSize: 11 }} />
                                                <Tooltip contentStyle={{ borderRadius: '12px', border: '1px solid #e2e8f0', boxShadow: '0 10px 15px -3px rgba(0,0,0,0.1)' }} />
                                                <Line type="monotone" dataKey="mins" stroke="#3b82f6" strokeWidth={3} filter="url(#shadowModalLine)" dot={{ r: 4, fill: '#fff', strokeWidth: 2, stroke: '#3b82f6' }} name="Minutes" />
                                            </LineChart>
                                        </ResponsiveContainer>
                                    </div>
                                </div>
                            )}
                        </div>

                        {/* Right Column: Activity Log */}
                        <div className="modal-right-col">
                            <div className="modal-activity-section">
                                <h3>Recent Activity Log</h3>
                                <div className="activity-list">
                                    {recentActivity.map((activity, idx) => (
                                        <div key={idx} className="activity-item">
                                            <div className="activity-dot"></div>
                                            <div className="activity-details">
                                                <span className="activity-camera">Seen by {activity.camera_id || 'Unknown'}</span>
                                                <span className="activity-time">{new Date(activity.date_created).toLocaleDateString()} at {formatTime(activity.date_created)}</span>
                                            </div>
                                            <div className="activity-duration">
                                                {Math.floor((activity.duration_seconds || 0)/60)}m {Math.floor((activity.duration_seconds || 0)%60)}s
                                            </div>
                                        </div>
                                    ))}
                                    {recentActivity.length === 0 && (
                                        <p style={{ color: '#94a3b8', fontSize: '14px', fontStyle: 'italic' }}>No recent activity.</p>
                                    )}
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default EmployeeModal;
