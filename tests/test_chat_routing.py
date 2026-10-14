from __future__ import annotations

import unittest

import web_app


class ChatRoutingTests(unittest.TestCase):
    def test_modeling_and_approval_routes_precede_general_api_dialogue(self) -> None:
        page = web_app.CONVERSATIONAL_INDEX
        start = page.index("async function sendPrompt()")
        end = page.index("async function planModelFromPrompt()", start)
        handler = page[start:end]

        approval_position = handler.index("hasActiveStagedWorkflow()")
        modeling_position = handler.index("looksLikeStagedModelingTask(text)")
        api_position = handler.index('assistantConfig?.mode === "api"')

        self.assertLess(approval_position, api_position)
        self.assertLess(modeling_position, api_position)


if __name__ == "__main__":
    unittest.main()
