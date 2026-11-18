"""Run with: python -m unittest discover -s tests -v"""
import unittest

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database_pool import DatabasePool


class DatabasePoolTests(unittest.IsolatedAsyncioTestCase):
    async def test_session_context_and_repeated_initialization(self):
        pool = DatabasePool()
        try:
            await pool.initialize()
            first_engine = pool.engine
            await pool.initialize()
            self.assertIs(pool.engine, first_engine)
            async with pool.get_session() as session:
                self.assertIsInstance(session, AsyncSession)
        finally:
            await pool.close()
        self.assertIsNone(pool.engine)
        self.assertIsNone(pool.session_factory)

    async def test_uninitialized_session_fails_explicitly(self):
        with self.assertRaises(RuntimeError):
            DatabasePool().get_session()
