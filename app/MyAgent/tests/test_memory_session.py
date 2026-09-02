import os
import unittest
from unittest.mock import patch

from memory.session import MEMORY_ID_ENV_VAR, create_memory_session_manager


class CreateMemorySessionManagerTest(unittest.TestCase):
    def test_missing_memory_id_is_rejected(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, MEMORY_ID_ENV_VAR):
                create_memory_session_manager("user-123", "session-123")

    @patch("memory.session.AgentCoreMemorySessionManager")
    def test_memory_config_is_scoped_to_actor(self, manager_class):
        with patch.dict(
            os.environ,
            {
                MEMORY_ID_ENV_VAR: "memory-123",
                "AWS_REGION": "ap-northeast-1",
            },
            clear=True,
        ):
            result = create_memory_session_manager("user-123", "session-123")

        self.assertEqual(result, manager_class.return_value)

        config = manager_class.call_args.kwargs["agentcore_memory_config"]
        self.assertEqual(config.memory_id, "memory-123")
        self.assertEqual(config.actor_id, "user-123")
        self.assertEqual(config.session_id, "session-123")
        self.assertEqual(config.batch_size, 1)
        self.assertTrue(config.filter_restored_tool_context)
        self.assertIn("/users/{actorId}/facts", config.retrieval_config)
        self.assertEqual(
            manager_class.call_args.kwargs["region_name"],
            "ap-northeast-1",
        )


if __name__ == "__main__":
    unittest.main()
