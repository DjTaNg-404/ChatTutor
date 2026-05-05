"""
Database Migration Test Script for ChatTutor.

This script tests:
1. Database connection
2. Table creation
3. CRUD operations
4. User authentication flow

Usage:
    python scripts/test_db_migration.py
"""

import asyncio
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.engine import engine, async_session_maker, init_db, close_db
from app.db.models import User, Session, Task, Note
from app.db.crud import (
    create_user,
    get_user_by_username,
    get_user_by_id,
    save_session,
    load_session,
    get_or_create_task,
    list_tasks,
    update_task,
    delete_task,
)
from app.core.auth import hash_password, verify_password, create_access_token


async def test_database_connection():
    """Test 1: Database connection."""
    print("\n" + "=" * 60)
    print("Test 1: Database Connection")
    print("=" * 60)
    print(f"Database URL: {settings.DATABASE_URL}")

    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            print("✅ Database connection successful")
            return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False


async def test_table_creation():
    """Test 2: Table creation."""
    print("\n" + "=" * 60)
    print("Test 2: Table Creation")
    print("=" * 60)

    try:
        # Initialize database (creates tables)
        await init_db()
        print("✅ Tables created successfully")

        # Verify tables exist
        async with async_session_maker() as session:
            result = await session.execute(
                text("""
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'public'
                ORDER BY table_name
                """)
            )
            tables = [row[0] for row in result.all()]
            print(f"   Tables: {', '.join(tables)}")
            return True
    except Exception as e:
        print(f"❌ Table creation failed: {e}")
        return False


async def test_user_crud():
    """Test 3: User CRUD operations."""
    print("\n" + "=" * 60)
    print("Test 3: User CRUD Operations")
    print("=" * 60)

    async with async_session_maker() as db:
        try:
            # Create user
            test_username = "test_user"
            test_password = "test123"
            hashed = hash_password(test_password)

            user = await create_user(db, username=test_username, hashed_password=hashed)
            print(f"✅ User created: {user.username} (id={user.id})")

            # Get user by username
            found_user = await get_user_by_username(db, test_username)
            assert found_user is not None
            print(f"✅ User found by username: {found_user.username}")

            # Get user by ID
            found_user_by_id = await get_user_by_id(db, user.id)
            assert found_user_by_id is not None
            print(f"✅ User found by ID: {found_user_by_id.username}")

            # Verify password
            assert verify_password(test_password, user.hashed_password)
            print(f"✅ Password verification successful")

            # Test JWT token
            token = create_access_token(str(user.id), user.username)
            assert token is not None
            print(f"✅ JWT token created: {token[:20]}...")

            return True
        except Exception as e:
            print(f"❌ User CRUD failed: {e}")
            return False


async def test_session_crud():
    """Test 4: Session CRUD operations."""
    print("\n" + "=" * 60)
    print("Test 4: Session CRUD Operations")
    print("=" * 60)

    async with async_session_maker() as db:
        try:
            # Get test user
            user = await get_user_by_username(db, "test_user")
            if not user:
                print("❌ Test user not found")
                return False

            # Create session
            session_id = "test_session_001"
            task_id = "test_task"
            messages = [
                {"type": "human", "content": "Hello"},
                {"type": "ai", "content": "Hi there!"},
            ]

            saved = await save_session(
                db,
                user_id=user.id,
                session_id=session_id,
                task_id=task_id,
                messages=messages,
                topic="Test Topic",
            )
            print(f"✅ Session saved: {saved.session_id}")

            # Load session
            loaded = await load_session(db, user.id, session_id)
            assert loaded is not None
            print(f"✅ Session loaded: {loaded.session_id}")
            print(f"   Messages count: {len(loaded.messages) if loaded.messages else 0}")

            return True
        except Exception as e:
            print(f"❌ Session CRUD failed: {e}")
            return False


async def test_task_crud():
    """Test 5: Task CRUD operations."""
    print("\n" + "=" * 60)
    print("Test 5: Task CRUD Operations")
    print("=" * 60)

    async with async_session_maker() as db:
        try:
            # Get test user
            user = await get_user_by_username(db, "test_user")
            if not user:
                print("❌ Test user not found")
                return False

            # Create task
            task_id = "test_task_001"
            task = await get_or_create_task(
                db,
                user_id=user.id,
                task_id=task_id,
                title="Test Task",
                icon="📚",
            )
            print(f"✅ Task created: {task.task_id} - {task.title}")

            # List tasks
            tasks = await list_tasks(db, user.id)
            print(f"✅ User has {len(tasks)} task(s)")

            # Update task
            updated = await update_task(
                db,
                user_id=user.id,
                task_id=task_id,
                title="Updated Task",
                status="active",
            )
            print(f"✅ Task updated: {updated.title}")

            return True
        except Exception as e:
            print(f"❌ Task CRUD failed: {e}")
            return False


async def cleanup_test_data():
    """Cleanup test data."""
    print("\n" + "=" * 60)
    print("Cleanup Test Data")
    print("=" * 60)

    async with async_session_maker() as db:
        try:
            # Delete test user (cascade will delete related data)
            user = await get_user_by_username(db, "test_user")
            if user:
                from sqlalchemy import delete
                await db.execute(delete(User).where(User.id == user.id))
                await db.commit()
                print(f"✅ Test user deleted: {user.username}")
        except Exception as e:
            print(f"⚠️ Cleanup failed: {e}")


async def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("ChatTutor Database Migration Test")
    print("=" * 60)

    # Run tests
    results = []

    results.append(("Database Connection", await test_database_connection()))
    results.append(("Table Creation", await test_table_creation()))
    results.append(("User CRUD", await test_user_crud()))
    results.append(("Session CRUD", await test_session_crud()))
    results.append(("Task CRUD", await test_task_crud()))

    # Cleanup
    await cleanup_test_data()

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status}: {name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    # Close database connection
    await close_db()

    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
