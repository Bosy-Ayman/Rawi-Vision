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
        
        // Group employee records by day and camera to calculate non-overlapping intervals
        const intervals = {}; // day -> [{start, end, camId}]
        const cameraCounts = {};

        empRecords.forEach(record => {
            if (!record.day || !record.date_created) return;
            
            const start = new Date(record.date_created).getTime();
            const durationSec = record.duration_seconds || 0;
            let end = record.last_seen ? new Date(record.last_seen).getTime() : start;
            if (end <= start && durationSec > 0) {
                end = start + (durationSec * 1000);
            }

            const camId = record.camera_id || "Unknown";
            cameraCounts[camId] = (cameraCounts[camId] || 0) + 1;

            if (!intervals[record.day]) {
                intervals[record.day] = [];
            }
            intervals[record.day].push({ start, end });
        });

        let totalDurationSeconds = 0;
        let totalVisits = 0;
        const dailyDurations = {};

        // Merge daily intervals
        Object.entries(intervals).forEach(([dayStr, list]) => {
            const sorted = list.sort((a, b) => a.start - b.start);
            const merged = [];
            let current = { start: sorted[0].start, end: sorted[0].end };

            for (let i = 1; i < sorted.length; i++) {
                const item = sorted[i];
                if (item.start <= current.end) {
                    current.end = Math.max(current.end, item.end);
                } else {
                    merged.push(current);
                    current = { start: item.start, end: item.end };
                }
            }
            merged.push(current);

            const dayDurationMs = merged.reduce((sum, interval) => sum + (interval.end - interval.start), 0);
            const dayDurationSec = dayDurationMs / 1000;

            dailyDurations[dayStr] = dayDurationSec;
            totalDurationSeconds += dayDurationSec;
            // The actual number of distinct non-overlapping attendance sessions on this day
            totalVisits += merged.length;
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

        // 3. Average Session Duration based on actual sessions
        const avgSessionSeconds = totalVisits > 0 ? totalDurationSeconds / totalVisits : 0;
        
        // --- Calculate Smart Absence & Shift Adherence Performance ---
        let awayAlertsCount = 0;
        let totalMinutesAway = 0;
        let shiftAdherence = "100%";

        if (allAttendanceData) {
            // Find all out of bounds alerts for this specific employee
            const empIdStr = String(targetEmployeeId);
            const matchingAlerts = allAttendanceData.alerts 
                ? allAttendanceData.alerts.filter(a => String(a.employee_id) === empIdStr && a.anomaly_type === 'out_of_bounds')
                : [];
            
            awayAlertsCount = matchingAlerts.length;
            
            // Extract minutes from descriptions (e.g., "left room for 24.5 minutes")
            matchingAlerts.forEach(alert => {
                const match = alert.description.match(/for ([\d\.]+) minutes/);
                if (match) {
                    totalMinutesAway += parseFloat(match[1]);
                }
            });

            // Calculate shift adherence
            // A perfect shift is counted as the duration they are assigned (default 8 hours = 28800s if shift time not set)
            let targetShiftSec = 28800; 
            if (employee.assigned_shift_start && employee.assigned_shift_end) {
                const [sH, sM] = employee.assigned_shift_start.split(':').map(Number);
                const [eH, eM] = employee.assigned_shift_end.split(':').map(Number);
                const startMs = (sH * 60 + sM) * 60 * 1000;
                const endMs = (eH * 60 + eM) * 60 * 1000;
                if (endMs > startMs) {
                    targetShiftSec = (endMs - startMs) / 1000;
                }
            }

            // Days they actually came in:
            const daysCheckedIn = Object.keys(intervals).length;

            if (totalDurationSeconds > 0 && daysCheckedIn > 0) {
                // Adherence = (Time Present / Expected Shift Time for only checked in days) minus away time penalty
                const expectedPresence = targetShiftSec * daysCheckedIn;
                const activePresence = Math.max(0, totalDurationSeconds - (totalMinutesAway * 60));
                const rate = Math.min(100, Math.round((activePresence / expectedPresence) * 100));
                shiftAdherence = `${rate}%`;
            } else {
                // If they never checked in on any days (vacation / off), adherence is not penalised or remains N/A instead of 0%
                shiftAdherence = daysCheckedIn > 0 ? "0%" : "N/A (No Shifts)";
            }
        }

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
                avgSession: formatDuration(avgSessionSeconds),
                awayAlertsCount,
                totalMinutesAway: `${Math.round(totalMinutesAway)}m`,
                shiftAdherence
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

                            <div style={{ marginTop: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
                                <h3 style={{ margin: '0 0 4px 0', fontSize: '15px', color: '#f8fafc', fontWeight: '600' }}>
                                    Assigned Room Performance
                                </h3>
                                <div className="modal-stats-grid" style={{ gridTemplateColumns: 'repeat(3, 1fr)' }}>
                                    <div className="modal-stat-card" style={{ border: '1px solid rgba(16, 185, 129, 0.2)', background: 'rgba(16, 185, 129, 0.02)' }}>
                                        <span className="modal-stat-label" style={{ color: '#10b981' }}>Shift Adherence</span>
                                        <span className="modal-stat-value" style={{ color: '#10b981' }}>{stats.shiftAdherence}</span>
                                    </div>
                                    <div className="modal-stat-card" style={{ border: '1px solid rgba(239, 68, 68, 0.2)', background: 'rgba(239, 68, 68, 0.02)' }}>
                                        <span className="modal-stat-label" style={{ color: '#ef4444' }}>Away Alerts</span>
                                        <span className="modal-stat-value" style={{ color: '#ef4444' }}>{stats.awayAlertsCount}</span>
                                    </div>
                                    <div className="modal-stat-card" style={{ border: '1px solid rgba(245, 158, 11, 0.2)', background: 'rgba(245, 158, 11, 0.02)' }}>
                                        <span className="modal-stat-label" style={{ color: '#f59e0b' }}>Total Time Away</span>
                                        <span className="modal-stat-value" style={{ color: '#f59e0b' }}>{stats.totalMinutesAway}</span>
                                    </div>
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
