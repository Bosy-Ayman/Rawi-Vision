from kombu import Connection, Exchange, Queue
from kombu.mixins import ConsumerMixin
from attendance.schemas.attendance import AttendanceCreate
from attendance.repository.attendance import AttendanceRepository
from attendance.service.attendance import AttendanceService
from database import sessionlocal
import asyncio

exchange = Exchange('attendance', type="topic", durable=True)
attendance_queue = Queue('attendance_queue', exchange=exchange, routing_key='attendance.detected')

class AttendanceConsumer(ConsumerMixin):
    def __init__(self, connection):
        self.connection = connection
        self.loop = None
    
    def get_consumers(self, Consumer, channel):
        return [Consumer(queues=[attendance_queue], callbacks=[self.on_attendance_detected], accept=['json'])]
    
    def on_attendance_detected(self, body, message):
        print(f"[AttendanceConsumer] Message received: {body}")
        try:
            emp_id = body.get("emp_id")
            if not emp_id:
                message.reject(requeue=False)
                return
            
            if self.loop:
                print(f"[AttendanceConsumer] Scheduling DB task for employee: {emp_id}")
                future = asyncio.run_coroutine_threadsafe(self._handle(emp_id), self.loop)
                # Add a callback to log completion or error
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

    async def _handle(self, emp_id: str):
        print(f"[AttendanceConsumer] Starting DB session for {emp_id}...")
        async with sessionlocal() as session:
            repo = AttendanceRepository(db=session)
            service = AttendanceService(repository=repo)
            attendance_create = AttendanceCreate(employee_id=emp_id)
            print(f"[AttendanceConsumer] Calling create_attendance_record...")
            result = await service.create_attendance_record(attendance=attendance_create)
            print(f"[AttendanceConsumer] Service returned: {result}")

        