import asyncio
import time
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import models
import security
from passlib.context import CryptContext

# Note: The 'check_same_thread': False here allows different threads
# in run_in_threadpool to use the sqlite connection.
engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
models.Base.metadata.create_all(engine)
SessionLocal = sessionmaker(bind=engine)

db = SessionLocal()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
hashed_pw = pwd_context.hash("mypassword")

user = models.User(email="test@example.com", hashed_password=hashed_pw, provider="email")
db.add(user)
db.commit()

async def concurrent_task():
    start = time.perf_counter()
    # Need to get a new session for concurrent tests as SQLAlchemy session isn't threadsafe
    # but run_in_threadpool is going to use different threads.
    # Actually if we pass the same db object it might error. Let's create a new db per task.
    local_db = SessionLocal()
    await security.authenticate_user(local_db, "test@example.com", "mypassword")
    local_db.close()
    return time.perf_counter() - start

async def main():
    start = time.perf_counter()
    tasks = [concurrent_task() for _ in range(10)]
    await asyncio.gather(*tasks)
    duration = time.perf_counter() - start
    print(f"10 Concurrent calls took {duration:.4f} seconds")

    start = time.perf_counter()
    for _ in range(10):
        local_db = SessionLocal()
        await security.authenticate_user(local_db, "test@example.com", "mypassword")
        local_db.close()
    duration = time.perf_counter() - start
    print(f"10 Sequential calls took {duration:.4f} seconds")

if __name__ == "__main__":
    asyncio.run(main())
