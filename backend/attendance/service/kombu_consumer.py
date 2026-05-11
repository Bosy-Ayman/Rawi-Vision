from kombu import Connection, Exchange, Queue
from kombu.mixins import ConsumerMixin
from attendance import AttendanceService, AttendanceCreate
import asyncio

exchange = Exchange('attendance', type="topic", durable=True)
attendance_queue = Queue('attendance_queue', exchange=exchange, routing_key='attendance.detected')

class AttendanceConsumer(ConsumerMixin):
    def __init__(self, connection, attendance_service: AttendanceService):
        self.connection = connection
        self.attendance_service = attendance_service
    
    def get_consumers(self, Consumer, channel):
        return [Consumer(queues=[attendance_queue], callbacks=[self.on_attendance_detected], accept=['json'])]
    
    def on_attendance_detected(self, body, message):
        try:
            emp_id = body.get("emp_id")
            if not emp_id:
                message.reject(requeue=False)  
                return
            attendance_create = AttendanceCreate(employee_id=emp_id)
            asyncio.get_event_loop().run_until_complete(self.attendance_service.create_attendance_record(attendance=attendance_create))
            message.ack()
        except Exception as error:
            message.nack(requeue=False)  
            raise error

        