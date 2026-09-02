import unittest
import re
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch
from zoneinfo import ZoneInfo

from agent.factory import create_agent
from agent.prompts import create_system_prompt


class SystemPromptTest(unittest.TestCase):
    def test_browser_prompt_requires_one_specific_session(self):
        prompt = create_system_prompt("browser-test-session")

        self.assertIn("`browser-test-session`", prompt)
        self.assertIn("Initialize that session once", prompt)
        self.assertIn(
            "Never close a session and then try to initialize another",
            prompt,
        )
        self.assertIn("Do not use Google Search", prompt)
        self.assertIn("Prefer official websites and primary sources", prompt)

    @patch("agent.prompts.datetime")
    def test_system_prompt_contains_current_japan_time(self, datetime_mock):
        datetime_mock.now.return_value = datetime(
            2026,
            8,
            17,
            15,
            30,
            tzinfo=ZoneInfo("Asia/Tokyo"),
        )

        prompt = create_system_prompt("browser-test-session")

        datetime_mock.now.assert_called_once_with(ZoneInfo("Asia/Tokyo"))
        self.assertIn("2026-08-17 15:30", prompt)
        self.assertIn("Timezone: Asia/Tokyo", prompt)


class CreateAgentTest(unittest.TestCase):
    @patch("agent.factory.create_tools", return_value=["customer-tool"])
    @patch("agent.factory.Agent")
    @patch("agent.factory.load_model")
    @patch("agent.factory.ReliableAgentCoreBrowser")
    def test_each_agent_gets_a_fresh_browser(
        self,
        browser_class,
        load_model,
        agent_class,
        _create_tools,
    ):
        first_browser = SimpleNamespace(browser="first-browser-tool")
        second_browser = SimpleNamespace(browser="second-browser-tool")
        browser_class.side_effect = [first_browser, second_browser]
        load_model.return_value = "model"

        create_agent()
        create_agent()

        self.assertEqual(browser_class.call_count, 2)
        first_tools = agent_class.call_args_list[0].kwargs["tools"]
        second_tools = agent_class.call_args_list[1].kwargs["tools"]
        self.assertEqual(first_tools, ["first-browser-tool", "customer-tool"])
        self.assertEqual(second_tools, ["second-browser-tool", "customer-tool"])

        first_prompt = agent_class.call_args_list[0].kwargs["system_prompt"]
        session_name = re.search(r"Use exactly `([^`]+)`", first_prompt).group(1)
        self.assertLessEqual(len(session_name), 36)

    @patch("agent.factory.create_tools", return_value=[])
    @patch("agent.factory.Agent")
    @patch("agent.factory.load_model", return_value="model")
    @patch("agent.factory.ReliableAgentCoreBrowser")
    def test_memory_session_manager_is_only_added_when_provided(
        self,
        browser_class,
        _load_model,
        agent_class,
        _create_tools,
    ):
        browser_class.return_value = SimpleNamespace(browser="browser-tool")
        session_manager = object()

        create_agent(session_manager=session_manager)

        self.assertIs(
            agent_class.call_args.kwargs["session_manager"],
            session_manager,
        )


if __name__ == "__main__":
    unittest.main()
