"""ReAct Agent Executor with Think-Act-Observe loop."""
import json
from typing import Any, AsyncGenerator, Dict, List, Optional
from datetime import datetime

from app.models import SSEEvent, ToolResult


class ReActStep:
    """Represents a single step in the ReAct loop."""

    def __init__(self, thought: str, action: Optional[str] = None, action_input: Optional[Dict] = None, observation: Optional[str] = None):
        self.thought = thought
        self.action = action
        self.action_input = action_input
        self.observation = observation
        self.timestamp = datetime.utcnow().isoformat()


class ReActExecutor:
    """
    ReAct (Reason + Act) Agent Executor.

    Implements the ReAct pattern:
    1. Thought: Agent reasons about what to do next
    2. Action: Agent selects and executes a tool
    3. Observation: Agent observes the result
    4. Repeat until task is complete
    """

    def __init__(self, tools: List[Dict[str, Any]], max_iterations: int = 5):
        """
        Initialize ReAct executor.

        Args:
            tools: List of available tools with name, description, and input_schema
            max_iterations: Maximum number of think-act-observe cycles
        """
        self.tools = tools
        self.max_iterations = max_iterations
        self.steps: List[ReActStep] = []

    def _build_react_prompt(self, query: str, steps: List[ReActStep]) -> str:
        """
        Build ReAct prompt with previous steps.

        Args:
            query: User's original question
            steps: Previous ReAct steps

        Returns:
            Formatted prompt for the LLM
        """
        tools_desc = "\n".join([
            f"- {tool['name']}: {tool['description']}"
            for tool in self.tools
        ])

        prompt = f"""You are a financial analysis agent using the ReAct (Reason + Act) framework.

Available tools:
{tools_desc}

Question: {query}

You should follow this format:

Thought: [Your reasoning about what to do next]
Action: [Tool name to use, or "Final Answer" if you have enough information]
Action Input: [Input for the tool as JSON, or your final answer]
Observation: [Result from the tool - this will be provided by the system]

"""

        if steps:
            prompt += "\nPrevious steps:\n"
            for i, step in enumerate(steps, 1):
                prompt += f"\nStep {i}:\n"
                prompt += f"Thought: {step.thought}\n"
                if step.action:
                    prompt += f"Action: {step.action}\n"
                if step.action_input:
                    prompt += f"Action Input: {json.dumps(step.action_input, ensure_ascii=False)}\n"
                if step.observation:
                    prompt += f"Observation: {step.observation}\n"

        prompt += "\nNow continue with your next thought and action:"
        return prompt

    def _parse_react_response(self, response: str) -> Dict[str, Any]:
        """
        Parse LLM response to extract thought, action, and action input.

        Args:
            response: Raw LLM response

        Returns:
            Dictionary with thought, action, and action_input
        """
        lines = response.strip().split("\n")
        result = {
            "thought": "",
            "action": None,
            "action_input": None
        }

        current_key = None
        current_value = []

        for line in lines:
            line = line.strip()
            if line.startswith("Thought:"):
                if current_key and current_value:
                    result[current_key] = "\n".join(current_value).strip()
                current_key = "thought"
                current_value = [line[8:].strip()]
            elif line.startswith("Action:"):
                if current_key and current_value:
                    result[current_key] = "\n".join(current_value).strip()
                current_key = "action"
                current_value = [line[7:].strip()]
            elif line.startswith("Action Input:"):
                if current_key and current_value:
                    result[current_key] = "\n".join(current_value).strip()
                current_key = "action_input"
                current_value = [line[13:].strip()]
            elif current_key:
                current_value.append(line)

        # Save last key
        if current_key and current_value:
            value = "\n".join(current_value).strip()
            if current_key == "action_input":
                try:
                    result[current_key] = json.loads(value)
                except json.JSONDecodeError:
                    result[current_key] = {"query": value}
            else:
                result[current_key] = value

        return result

    async def execute(
        self,
        query: str,
        llm_generate_func,
        tool_execute_func
    ) -> AsyncGenerator[SSEEvent, None]:
        """
        Execute ReAct loop.

        Args:
            query: User's question
            llm_generate_func: Async function to generate LLM response
            tool_execute_func: Async function to execute tools

        Yields:
            SSEEvent objects for streaming
        """
        self.steps = []

        for iteration in range(self.max_iterations):
            # Build prompt with previous steps
            prompt = self._build_react_prompt(query, self.steps)

            # Generate thought and action
            yield SSEEvent(
                type="react_iteration",
                iteration=iteration + 1,
                max_iterations=self.max_iterations
            )

            llm_response = await llm_generate_func(prompt)

            # Parse response
            parsed = self._parse_react_response(llm_response)

            yield SSEEvent(
                type="react_thought",
                thought=parsed["thought"]
            )

            # Check if we have final answer
            if parsed["action"] and "final answer" in parsed["action"].lower():
                yield SSEEvent(
                    type="react_final_answer",
                    answer=parsed["action_input"] if isinstance(parsed["action_input"], str) else json.dumps(parsed["action_input"])
                )
                break

            # Execute action
            if parsed["action"] and parsed["action_input"]:
                yield SSEEvent(
                    type="react_action",
                    action=parsed["action"],
                    action_input=parsed["action_input"]
                )

                # Execute tool
                tool_result = await tool_execute_func(parsed["action"], parsed["action_input"])

                observation = json.dumps(tool_result, ensure_ascii=False)
                yield SSEEvent(
                    type="react_observation",
                    observation=observation
                )

                # Record step
                step = ReActStep(
                    thought=parsed["thought"],
                    action=parsed["action"],
                    action_input=parsed["action_input"],
                    observation=observation
                )
                self.steps.append(step)
            else:
                # No valid action, break
                yield SSEEvent(
                    type="react_error",
                    message="Failed to parse action from LLM response"
                )
                break

        # Return final summary
        yield SSEEvent(
            type="react_complete",
            total_steps=len(self.steps)
        )
