from kombu import Connection, Exchange, Queue
from kombu.mixins import ConsumerMixin
from attendance.schemas.attendance import AttendanceCreate
from attendance.repository.attendance import AttendanceRepository
from attendance.service.attendance import AttendanceService
from database import sessionlocal
import asyncio

exchange = Exchange('attendance', type="topic", durable=True)
attendance_queue = Queue('attendance_queue', exchange=exchange, routing_key='attendance.*')

class AttendanceConsumer(ConsumerMixin):
    def __init__(self, connection):
        self.connection = connection
        self.loop = None
    
    def get_consumers(self, Consumer, channel):
        return [Consumer(queues=[attendance_queue], callbacks=[self.on_attendance_message], accept=['json'])]
    
    def on_attendance_message(self, body, message):
        print(f"[AttendanceConsumer] Message received on {message.delivery_info.get('routing_key')}: {body}")
        try:
            emp_id = body.get("emp_id")
            camera_id = body.get("camera_id", "unknown")
            routing_key = message.delivery_info.get('routing_key')

            if not emp_id:
                message.reject(requeue=False)
                return

            if self.loop:
                if routing_key == 'attendance.detected':
                    future = asyncio.run_coroutine_threadsafe(self._handle_detected(emp_id, camera_id), self.loop)
                elif routing_key == 'attendance.left':
                    duration_seconds = body.get("duration_seconds", 0.0)
                    future = asyncio.run_coroutine_threadsafe(self._handle_left(emp_id, camera_id, duration_seconds), self.loop)
                else:
                    message.ack()
                    return

                def done_callback(f):
                    try:
                        f.result()
                        print(f"[AttendanceConsumer] DB Task completed for {emp_id}")
                    except Exception as e:
                        print(f"[AttendanceConsumer] DB TASK FAILED for {emp_id}: {e}")
                future.add_done_callback(done_callback)
            else:
                print("[AttendanceConsumer] ERROR: No event loop provided!")
            message.ack()
        except Exception as error:
            print(f"[AttendanceConsumer] ERROR: {error}")
            try:
                message.reject(requeue=True)
            except Exception:
                pass
            raise error

    async def _handle_detected(self, emp_id: str, camera_id: str):
        print(f"[AttendanceConsumer] Starting DB session for DETECTED {emp_id}...")
        async with sessionlocal() as session:
            repo = AttendanceRepository(db=session)
            service = AttendanceService(repository=repo)
            attendance_create = AttendanceCreate(employee_id=emp_id, camera_id=camera_id, duration_seconds=0.0)
            result = await service.create_attendance_record(attendance=attendance_create)
            print(f"[AttendanceConsumer] Service returned: {result}")

    async def _handle_left(self, emp_id: str, camera_id: str, duration_seconds: float):
        print(f"[AttendanceConsumer] Starting DB session for LEFT {emp_id} (duration: {duration_seconds}s)...")
        async with sessionlocal() as session:
            # 1. Update attendance record
            repo = AttendanceRepository(db=session)
            service = AttendanceService(repository=repo)
            result = await service.update_attendance_duration(employee_id=emp_id, camera_id=camera_id, duration_seconds=duration_seconds)
            print(f"[AttendanceConsumer] Update returned: {result}")

            # 2. Check room boundaries assignment alert (20 minutes = 1200 seconds)
            try:
                from employee_onboarding.models.employee import Employee
                from anomaly.models.anomaly import Anomaly, AnomalyType
                from sqlalchemy import select
                from datetime import datetime

                emp_stmt = select(Employee).where(Employee.id == emp_id)
                emp_res = await session.execute(emp_stmt)
                employee = emp_res.scalar_one_or_none()

                if employee and employee.assigned_camera_ids:
                    # Verify it's a scheduled routine day.
                    now = datetime.now()
                    current_day = now.weekday()  # 0 = Monday, 6 = Sunday
                    is_scheduled_day = False
                    if employee.assigned_days:
                        is_scheduled_day = current_day in employee.assigned_days
                    else:
                        is_scheduled_day = current_day < 5  # default to Mon-Fri if not specified
                    
                    # Verify current time falls within their shift window (if shift is assigned)
                    in_shift_hours = True
                    if employee.assigned_shift_start and employee.assigned_shift_end:
                        current_time_str = now.strftime("%H:%M")
                        in_shift_hours = (employee.assigned_shift_start <= current_time_str <= employee.assigned_shift_end)

                    if is_scheduled_day and in_shift_hours:
                        # If they were seen leaving or are absent from their assigned camera room for 20+ minutes during shift
                        if camera_id in employee.assigned_camera_ids and duration_seconds >= 1200:
                            desc = f"{employee.first_name} {employee.last_name} left their assigned room ({camera_id}) for {round(duration_seconds / 60, 1)} minutes."
                            new_anomaly = Anomaly(
                                anomaly_type=AnomalyType.OUT_OF_BOUNDS,
                                description=desc,
                                confidence_score=1.0,
                                camera_id=camera_id,
                                employee_id=str(emp_id)
                            )
                            session.add(new_anomaly)
                            await session.commit()
                            print(f"[AttendanceConsumer] Generated OUT_OF_BOUNDS alert for {employee.first_name}!")
            except Exception as e:
                print(f"[AttendanceConsumer] Alert processing failed: {e}")