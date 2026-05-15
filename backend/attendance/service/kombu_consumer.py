from kombu import Connection, Exchange, Queue
from kombu.mixins import ConsumerMixin
from attendance import AttendanceService, AttendanceCreate
import asyncio

exchange = Exchange('attendance', type="topic", durable=True)
attendance_queue = Queue('attendance_queue', exchange=exchange, routing_key='attendance.detected')

engine = create_async_engine(os.getenv("DATABASE_URL"))
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

class AttendanceConsumer(ConsumerMixin):
    def __init__(self, connection):
        self.connection = connection
    
    def get_consumers(self, Consumer, channel):
        return [Consumer(queues=[attendance_queue], callbacks=[self.on_attendance_detected], accept=['json'])]
    
    def on_attendance_detected(self, body, message):
        try:
            emp_id = body.get("emp_id")
            if not emp_id:
                message.reject(requeue=False)
                return
            asyncio.run(self._handle(emp_id))
            message.ack()
        except Exception as error:
            message.nack(requeue=False)
            raise error

    async def _handle(self, emp_id: str):
        async with AsyncSessionLocal() as session:
            repo = AttendanceRepository(db=session)
            service = AttendanceService(repository=repo)
            attendance_create = AttendanceCreate(employee_id=emp_id)
            await service.create_attendance_record(attendance=attendance_create)

        